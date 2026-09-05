"""R4-T1 · /api/applications contract: bad input, duplicate submits, status order.

The status machine is the interesting part: transitions are recorded by
`record_transition()` and drive the Stats funnel + Sankey, so an out-of-order or
backwards move writes a real edge into the chart.
"""
import pytest

from backend.tests.r4_support import (  # noqa: F401
    client, _clear_running_state, _no_outbound, assert_clean, assert_no_leak,
    make_job, big_string, EMOJI, MISSING_UUID,
)

VALID = ["applied", "interview", "offer", "rejected"]


def _create(client, **kw):
    body = {"title": "Senior PM", "company": "Acme", "url": "https://x.com/jobs/1"}
    body.update(kw)
    return client.post("/api/applications", json=body)


# ── POST /api/applications ───────────────────────────────────────────────────

@pytest.mark.parametrize("body", [
    {}, {"title": "T"}, {"title": "T", "company": "C"},
    {"company": "C", "url": "u"}, {"title": "T", "url": "u"},
    {"title": None, "company": "C", "url": "u"},
    {"title": 5, "company": "C", "url": "u"},
    {"title": ["T"], "company": "C", "url": "u"},
])
def test_create_application_requires_the_three_fields(client, body):
    assert_clean(client.post("/api/applications", json=body), 422)


def test_create_application_accepts_empty_strings(client):
    """Current contract: `str` with no min_length, so "" is a legal title."""
    r = assert_clean(client.post("/api/applications",
                                json={"title": "", "company": "", "url": ""}), 200)
    assert r.json()["title"] == ""


def test_create_application_unicode_round_trips(client):
    r = assert_clean(_create(client, title=EMOJI, company="Señor 中文"), 200)
    assert r.json()["title"] == EMOJI


def test_create_application_duplicate_is_409_with_the_existing_id(client):
    first = assert_clean(_create(client), 200)
    dup = assert_clean(_create(client), 409)
    detail = dup.json()["detail"]
    assert detail["application_id"] == first.json()["id"]


def test_create_application_duplicate_via_a_different_url_spelling_is_409(client):
    """Dedup runs on the normalised URL, so tracking noise must not open a second row."""
    assert_clean(_create(client, url="https://x.com/jobs/1"), 200)
    assert_clean(_create(client, url="https://x.com/jobs/1?utm_source=li#top"), 409)


def test_create_application_duplicate_does_not_leave_a_half_written_job(client, test_db):
    from backend.models.db import Job, Application
    _create(client)
    _create(client)
    assert test_db.query(Job).count() == 1
    assert test_db.query(Application).count() == 1


@pytest.mark.parametrize("status", VALID)
def test_create_application_seeds_the_first_funnel_edge(client, test_db, status):
    from backend.models.db import Application
    r = assert_clean(_create(client, status=status, url=f"https://x.com/jobs/{status}"), 200)
    app = test_db.query(Application).filter(Application.id == r.json()["id"]).first()
    assert app.status_transitions[0] == {
        "from": None, "to": status,
        "at": app.status_transitions[0]["at"], "source": "ui",
    }


def test_create_application_unknown_status_falls_back_to_applied(client):
    r = assert_clean(_create(client, status="banana"), 200)
    assert r.json()["status"] == "applied"


@pytest.mark.parametrize("value", ["", "not-a-date", "2026-13-45", "99999-01-01", 12345])
def test_create_application_unparseable_applied_at_is_ignored(client, value):
    r = client.post("/api/applications", json={
        "title": "T", "company": "C", "url": f"https://x.com/{value}", "applied_at": value,
    })
    assert_clean(r, 200, 422)


def test_create_application_ten_megabyte_notes(client):
    r = client.post("/api/applications", json={
        "title": "T", "company": "C", "url": "https://x.com/big", "notes": big_string(10),
    })
    assert_clean(r, 200, 400, 413, 422)


@pytest.mark.parametrize("body", [[1, 2], "hi", 5, None])
def test_create_application_non_object_body_is_422(client, body):
    assert_clean(client.post("/api/applications", json=body), 422)


def test_create_application_ignores_unknown_fields(client):
    """Pydantic default is extra='ignore' — a stray key must not reach the model."""
    r = assert_clean(client.post("/api/applications", json={
        "title": "T", "company": "C", "url": "https://x.com/1", "id": MISSING_UUID,
        "status_transitions": [{"from": "offer", "to": "applied"}],
    }), 200)
    assert r.json()["id"] != MISSING_UUID


# ── PATCH /api/applications/{id} ─────────────────────────────────────────────

def _app_id(client):
    return _create(client).json()["id"]


def test_patch_application_missing_id_is_404(client):
    assert_clean(client.patch(f"/api/applications/{MISSING_UUID}", json={"notes": "x"}), 404)


@pytest.mark.parametrize("bad", ["banana", "", "APPLIED", "Applied", 5, None])
def test_patch_application_rejects_an_unknown_status(client, bad):
    aid = _app_id(client)
    assert_clean(client.patch(f"/api/applications/{aid}", json={"status": bad}), 400)


@pytest.mark.parametrize("bad", [["applied"], {"to": "applied"}])
@pytest.mark.xfail(strict=True, reason="R4-T1-16")
def test_patch_application_rejects_an_unhashable_status(client, bad):
    """`updates["status"] not in VALID_STATUSES` raises TypeError for a list/dict."""
    aid = _app_id(client)
    assert client.patch(f"/api/applications/{aid}", json={"status": bad}).status_code == 400


def test_patch_application_error_lists_the_legal_statuses(client):
    aid = _app_id(client)
    r = client.patch(f"/api/applications/{aid}", json={"status": "banana"})
    assert sorted(VALID) == sorted(
        [s.strip(" '") for s in r.json()["detail"].split("[")[1].split("]")[0].split(",")]
    )


def test_patch_application_forward_transition_records_an_edge(client, test_db):
    from backend.models.db import Application
    aid = _app_id(client)
    assert_clean(client.patch(f"/api/applications/{aid}", json={"status": "interview"}), 200)
    app = test_db.query(Application).filter(Application.id == aid).first()
    test_db.refresh(app)
    assert app.status == "interview"
    assert app.status_transitions[-1]["from"] == "applied"
    assert app.status_transitions[-1]["to"] == "interview"


def test_patch_application_same_status_twice_records_one_edge(client, test_db):
    from backend.models.db import Application
    aid = _app_id(client)
    client.patch(f"/api/applications/{aid}", json={"status": "interview"})
    client.patch(f"/api/applications/{aid}", json={"status": "interview"})
    app = test_db.query(Application).filter(Application.id == aid).first()
    test_db.refresh(app)
    assert len(app.status_transitions) == 2   # seed edge + one move


def test_patch_application_backwards_transition_is_allowed_and_logged(client, test_db):
    """Current contract: the funnel has no ordering guard — offer -> applied is legal."""
    from backend.models.db import Application
    aid = _app_id(client)
    client.patch(f"/api/applications/{aid}", json={"status": "offer"})
    assert_clean(client.patch(f"/api/applications/{aid}", json={"status": "applied"}), 200)
    app = test_db.query(Application).filter(Application.id == aid).first()
    test_db.refresh(app)
    assert app.status_transitions[-1] == {
        "from": "offer", "to": "applied",
        "at": app.status_transitions[-1]["at"], "source": "ui",
    }


def test_patch_application_out_of_order_skips_a_stage(client, test_db):
    """applied -> offer with no interview: allowed, and one edge, not two."""
    from backend.models.db import Application
    aid = _app_id(client)
    client.patch(f"/api/applications/{aid}", json={"status": "offer"})
    app = test_db.query(Application).filter(Application.id == aid).first()
    test_db.refresh(app)
    assert [t["to"] for t in app.status_transitions] == ["applied", "offer"]


@pytest.mark.xfail(strict=True, reason="R4-T1-15")
def test_patch_application_cannot_leave_a_terminal_rejected_state_silently(client):
    """Reviving a rejected application should be an explicit reopen, not a plain PATCH.

    Today it just writes a rejected -> interview edge into the Sankey.
    """
    aid = _app_id(client)
    client.patch(f"/api/applications/{aid}", json={"status": "rejected"})
    r = client.patch(f"/api/applications/{aid}", json={"status": "interview"})
    assert r.status_code == 409


def test_patch_application_drops_keys_outside_the_allow_list(client, test_db):
    from backend.models.db import Application
    aid = _app_id(client)
    assert_clean(client.patch(f"/api/applications/{aid}",
                             json={"job_id": MISSING_UUID, "id": MISSING_UUID,
                                   "status_transitions": [], "notes": "kept"}), 200)
    app = test_db.query(Application).filter(Application.id == aid).first()
    test_db.refresh(app)
    assert app.notes == "kept"
    assert str(app.id) == aid
    assert app.status_transitions != []


def test_patch_application_empty_body_is_a_noop_200(client):
    aid = _app_id(client)
    assert_clean(client.patch(f"/api/applications/{aid}", json={}), 200)


@pytest.mark.parametrize("body", [[1], "x", 3, None])
def test_patch_application_non_object_body_is_422(client, body):
    aid = _app_id(client)
    assert_clean(client.patch(f"/api/applications/{aid}", json=body), 422)


def test_patch_application_ten_megabyte_notes(client):
    aid = _app_id(client)
    r = client.patch(f"/api/applications/{aid}", json={"notes": big_string(10)})
    assert_clean(r, 200, 400, 413, 422)


# ── DELETE /api/applications/{id} ────────────────────────────────────────────

def test_delete_application_missing_id_is_404(client):
    assert_clean(client.delete(f"/api/applications/{MISSING_UUID}"), 404)


def test_delete_application_releases_the_job(client, test_db):
    from backend.models.db import Job
    aid = _app_id(client)
    assert_clean(client.delete(f"/api/applications/{aid}"), 200)
    job = test_db.query(Job).first()
    test_db.refresh(job)
    assert job.status == "saved"


def test_delete_application_twice_is_404_the_second_time(client):
    aid = _app_id(client)
    assert_clean(client.delete(f"/api/applications/{aid}"), 200)
    assert_clean(client.delete(f"/api/applications/{aid}"), 404)


# ── Listing ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("qs,expected", [
    ("", 200), ("status=applied", 200), ("status=zzz", 200),
    ("limit=1", 200), ("limit=2000", 200), ("limit=2001", 422),
    ("offset=0", 200), ("offset=-1", 422), ("limit=abc", 422),
])
def test_list_applications_query_contract(client, qs, expected):
    assert_clean(client.get(f"/api/applications?{qs}"), expected)


def test_list_applications_rejects_negative_limit(client):
    assert client.get("/api/applications?limit=-5").status_code == 422


# ── Interviews ───────────────────────────────────────────────────────────────

def test_add_interview_missing_application_is_404(client):
    assert_clean(client.post(f"/api/applications/{MISSING_UUID}/interviews",
                             json={"what": "Screen"}), 404)


def test_add_interview_requires_what(client):
    aid = _app_id(client)
    assert_clean(client.post(f"/api/applications/{aid}/interviews", json={}), 422)


def test_add_interview_then_patch_and_delete(client):
    aid = _app_id(client)
    r = assert_clean(client.post(f"/api/applications/{aid}/interviews",
                                json={"what": "Screen"}), 201)
    iid = r.json()["id"]
    assert_clean(client.patch(f"/api/applications/interviews/{iid}", json={"what": EMOJI}), 200)
    assert_clean(client.delete(f"/api/applications/interviews/{iid}"), 200)
    assert_clean(client.delete(f"/api/applications/interviews/{iid}"), 404)


def test_patch_missing_interview_is_404(client):
    assert_clean(client.patch(f"/api/applications/interviews/{MISSING_UUID}",
                              json={"what": "x"}), 404)


def test_add_interview_bad_when_at_never_500(client):
    aid = _app_id(client)
    r = client.post(f"/api/applications/{aid}/interviews",
                    json={"what": "Screen", "when_at": "not-a-date"})
    assert_clean(r, 201, 400, 422)


# ── Prep bundle + extract ────────────────────────────────────────────────────

def test_prep_bundle_missing_application_is_404(client):
    assert_clean(client.get(f"/api/applications/{MISSING_UUID}/prep"), 404)


@pytest.mark.parametrize("url", ["", "not a url", "ftp://x", "javascript:alert(1)",
                                 "http://127.0.0.1:5432/", "http://169.254.169.254/"])
def test_extract_refuses_or_fails_cleanly_on_hostile_urls(client, url):
    r = client.post("/api/applications/extract", json={"url": url})
    assert_clean(r, 200, 400, 403, 422, 502)


def test_extract_requires_a_url_field(client):
    assert_clean(client.post("/api/applications/extract", json={}), 422)


# ── R4 fix-loop regression (R4-T1-07) ────────────────────────────────────────

@pytest.mark.parametrize("qs", ["limit=-5", "limit=-1"])
def test_list_applications_negative_limit_is_422(client, qs):
    assert_clean(client.get(f"/api/applications?{qs}"), 422)
