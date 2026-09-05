"""R4-T1 · /api/jobs contract under bad input.

Every test asserts the status code AND that nothing internal (stack trace, SQL,
container path) reaches the response body. Postgres-only behaviour (the
DataError -> 404 handler, negative LIMIT) is pinned in test_r4_live_contract.py,
because SQLite does not reproduce it.
"""
import pytest

from backend.tests.r4_support import (  # noqa: F401
    client, _clear_running_state, _no_outbound, assert_clean, assert_no_leak,
    make_job, make_search, big_string, EMOJI, MISSING_UUID,
)


# ── GET /api/jobs — filters and paging ───────────────────────────────────────

def test_list_jobs_empty_is_a_shaped_envelope(client):
    r = assert_clean(client.get("/api/jobs"), 200)
    assert r.json() == {"total": 0, "jobs": []}


@pytest.mark.parametrize("qs", [
    "status=zzz", "source=zzz", "company=", "title_search=",
    f"company={EMOJI}", f"title_search={EMOJI}",
    "min_score=0", "min_score=100", "max_score=0",
    "min_salary=0", "max_salary=0",
    "remote=true", "remote=false", "saved=true", "saved=false",
    "sort_by=date", "sort_by=score", "sort_by=salary", "sort_by=company",
    "limit=1", "limit=200", "offset=0",
])
def test_list_jobs_accepts_every_documented_filter(client, qs):
    assert_clean(client.get(f"/api/jobs?{qs}"), 200)


@pytest.mark.parametrize("qs,expected", [
    ("limit=201", 422),          # le=200
    ("limit=abc", 422),
    ("offset=-1", 422),          # ge=0
    ("sort_by=hax", 422),        # pattern
    ("min_score=abc", 422),
    ("remote=maybe", 422),
    ("saved=maybe", 422),
    ("min_salary=abc", 422),
])
def test_list_jobs_rejects_bad_query_types(client, qs, expected):
    assert_clean(client.get(f"/api/jobs?{qs}"), expected)


def test_list_jobs_huge_filter_string_is_not_an_error(client):
    """A 6 kB filter is silly but must not 500 or echo back a stack trace."""
    assert_clean(client.get("/api/jobs?title_search=" + "a" * 6000), 200, 414, 431)


@pytest.mark.xfail(strict=True, reason="R4-T1-07")
def test_list_jobs_rejects_negative_limit(client):
    """`limit` has le=200 but no lower bound; a negative one reaches LIMIT -5."""
    assert client.get("/api/jobs?limit=-5").status_code == 422


def test_list_jobs_negative_limit_never_leaks_internals(client):
    assert_no_leak(client.get("/api/jobs?limit=-5"))


# ── GET /api/jobs/{id} ───────────────────────────────────────────────────────

def test_get_job_missing_uuid_is_404(client):
    assert_clean(client.get(f"/api/jobs/{MISSING_UUID}"), 404)


def test_get_job_found(client, test_db):
    job = make_job(test_db)
    r = assert_clean(client.get(f"/api/jobs/{job.id}"), 200)
    assert r.json()["id"] == str(job.id)


def test_get_job_path_traversal_is_404(client):
    assert_clean(client.get("/api/jobs/../etc/passwd"), 404)


# ── PATCH /api/jobs/{id} ─────────────────────────────────────────────────────

def test_patch_job_missing_uuid_is_404(client):
    assert_clean(client.patch(f"/api/jobs/{MISSING_UUID}", json={"seen": True}), 404)


def test_patch_job_empty_body_is_a_noop_200(client, test_db):
    job = make_job(test_db)
    assert_clean(client.patch(f"/api/jobs/{job.id}", json={}), 200)


def test_patch_job_ignores_unknown_keys_silently(client, test_db):
    """Current contract: keys outside {seen, saved, status} are dropped, not rejected."""
    job = make_job(test_db)
    r = assert_clean(client.patch(f"/api/jobs/{job.id}",
                                 json={"nonsense": 1, "company": "Hijacked", "status": "skip"}), 200)
    body = r.json()
    assert body["status"] == "skip"
    assert body["company"] == "Acme", "an unlisted key was written through"


@pytest.mark.parametrize("body", [[1, 2], "hello", 5, True, None])
def test_patch_job_non_object_body_is_422(client, test_db, body):
    job = make_job(test_db)
    assert_clean(client.patch(f"/api/jobs/{job.id}", json=body), 422)


def test_patch_job_unknown_status_value_is_accepted_verbatim(client, test_db):
    """Current contract: Job.status is a free String, no enum guard."""
    job = make_job(test_db)
    r = assert_clean(client.patch(f"/api/jobs/{job.id}", json={"status": "banana"}), 200)
    assert r.json()["status"] == "banana"


@pytest.mark.xfail(strict=True, reason="R4-T1-11")
def test_patch_job_rejects_a_wrongly_typed_value(client, test_db):
    """`saved` is a Boolean column; a string reaches the driver and blows up."""
    job = make_job(test_db)
    assert client.patch(f"/api/jobs/{job.id}", json={"saved": "banana"}).status_code in (400, 422)


def test_patch_job_wrong_type_never_leaks_internals(client, test_db):
    job = make_job(test_db)
    assert_no_leak(client.patch(f"/api/jobs/{job.id}", json={"saved": "banana"}))


def test_patch_job_emoji_status_round_trips(client, test_db):
    job = make_job(test_db)
    r = assert_clean(client.patch(f"/api/jobs/{job.id}", json={"status": EMOJI}), 200)
    assert r.json()["status"] == EMOJI


def test_patch_job_applied_creates_application_and_company_once(client, test_db):
    from backend.models.db import Application, Company
    job = make_job(test_db, company="Northwind")
    r1 = assert_clean(client.patch(f"/api/jobs/{job.id}", json={"status": "applied"}), 200)
    assert r1.json()["created_application_id"]
    assert r1.json()["created_company_id"]
    # A second "applied" must not create a duplicate application or company.
    r2 = assert_clean(client.patch(f"/api/jobs/{job.id}", json={"status": "applied"}), 200)
    assert r2.json()["created_application_id"] is None
    assert r2.json()["created_company_id"] is None
    assert test_db.query(Application).count() == 1
    assert test_db.query(Company).filter(Company.name == "Northwind").count() == 1


# ── POST /api/jobs/bulk-update ───────────────────────────────────────────────

def test_bulk_update_reports_missing_ids(client, test_db):
    job = make_job(test_db)
    r = assert_clean(client.post("/api/jobs/bulk-update", json={
        "job_ids": [str(job.id), MISSING_UUID], "updates": {"status": "skip"},
    }), 200)
    assert r.json() == {"updated": 1, "not_found": [MISSING_UUID]}


def test_bulk_update_empty_id_list_is_a_noop(client):
    r = assert_clean(client.post("/api/jobs/bulk-update",
                                json={"job_ids": [], "updates": {"status": "skip"}}), 200)
    assert r.json() == {"updated": 0, "not_found": []}


def test_bulk_update_drops_keys_outside_the_allow_list(client, test_db):
    job = make_job(test_db, company="Acme")
    assert_clean(client.post("/api/jobs/bulk-update", json={
        "job_ids": [str(job.id)], "updates": {"company": "Hijacked", "status": "skip"},
    }), 200)
    test_db.expire_all()
    from backend.models.db import Job
    assert test_db.get(Job, job.id).company == "Acme"


def test_bulk_update_missing_keys_is_a_noop(client):
    assert_clean(client.post("/api/jobs/bulk-update", json={}), 200)


@pytest.mark.xfail(strict=True, reason="R4-T1-12")
def test_bulk_update_reports_a_malformed_id_instead_of_aborting(client, test_db):
    """The endpoint promises a `not_found` list; one junk id must not kill the batch."""
    job = make_job(test_db)
    r = client.post("/api/jobs/bulk-update", json={
        "job_ids": [str(job.id), "not-a-uuid"], "updates": {"status": "skip"},
    })
    assert r.status_code == 200
    assert r.json()["updated"] == 1
    assert "not-a-uuid" in r.json()["not_found"]


def test_bulk_update_malformed_id_never_leaks_internals(client, test_db):
    job = make_job(test_db)
    assert_no_leak(client.post("/api/jobs/bulk-update", json={
        "job_ids": [str(job.id), "not-a-uuid"], "updates": {"status": "skip"},
    }))


def test_bulk_update_ten_thousand_ids_stays_shaped(client):
    ids = [MISSING_UUID] * 10000
    r = assert_clean(client.post("/api/jobs/bulk-update",
                                json={"job_ids": ids, "updates": {"seen": True}}), 200)
    assert r.json()["updated"] == 0


# ── POST /api/jobs/save-from-extension ───────────────────────────────────────

@pytest.mark.parametrize("body", [
    {}, {"title": "T"}, {"title": "T", "company": "C"},
    {"title": "", "company": "C", "url": "https://x.com/1"},
    {"title": "  ", "company": "  ", "url": "  "},
    {"title": None, "company": None, "url": None},
])
def test_save_from_extension_requires_title_company_url(client, body):
    assert_clean(client.post("/api/jobs/save-from-extension", json=body), 400)


@pytest.mark.parametrize("bad", [5, ["T"], {"t": 1}, True])
@pytest.mark.xfail(strict=True, reason="R4-T1-20")
def test_save_from_extension_wrongly_typed_title_is_400_not_500(client, bad):
    """`(body.get("title") or "").strip()` raises AttributeError on a non-string."""
    r = client.post("/api/jobs/save-from-extension",
                    json={"title": bad, "company": "C", "url": "https://x.com/1"})
    assert r.status_code in (400, 422)


@pytest.mark.parametrize("bad", [5, ["T"], {"t": 1}])
def test_save_from_extension_wrongly_typed_title_never_leaks_internals(client, bad):
    assert_no_leak(client.post("/api/jobs/save-from-extension",
                               json={"title": bad, "company": "C", "url": "https://x.com/1"}))


def test_save_from_extension_creates_then_dedupes(client, test_db):
    body = {"title": "Senior PM", "company": "Acme", "url": "https://x.com/jobs/9"}
    r1 = assert_clean(client.post("/api/jobs/save-from-extension", json=body), 200)
    assert r1.json()["new"] is True
    r2 = assert_clean(client.post("/api/jobs/save-from-extension", json=body), 200)
    assert r2.json()["new"] is False
    assert r2.json()["id"] == r1.json()["id"]


def test_save_from_extension_dedupes_across_url_spellings(client, test_db):
    base = {"title": "Senior PM", "company": "Acme"}
    r1 = client.post("/api/jobs/save-from-extension",
                     json={**base, "url": "https://x.com/jobs/9"})
    r2 = client.post("/api/jobs/save-from-extension",
                     json={**base, "url": "https://x.com/jobs/9?utm_source=li#top"})
    assert_clean(r1, 200)
    assert_clean(r2, 200)
    assert r2.json()["id"] == r1.json()["id"]


def test_save_from_extension_unicode_round_trips(client):
    r = assert_clean(client.post("/api/jobs/save-from-extension", json={
        "title": EMOJI, "company": "Señor Corp 中文", "url": "https://x.com/jobs/é",
    }), 200)
    assert r.json()["title"] == EMOJI


def test_save_from_extension_ten_megabyte_description(client):
    """A pathological paste must be stored or refused — never a 500."""
    r = client.post("/api/jobs/save-from-extension", json={
        "title": "Big", "company": "Acme", "url": "https://x.com/jobs/big",
        "description": big_string(10),
    })
    assert_clean(r, 200, 400, 413, 422)


@pytest.mark.parametrize("body", [[1, 2], "hello", 5, None])
def test_save_from_extension_non_object_body_is_422(client, body):
    assert_clean(client.post("/api/jobs/save-from-extension", json=body), 422)


# ── POST /api/jobs/linkedin-import ───────────────────────────────────────────

def test_linkedin_import_no_ids_is_accepted_zero(client):
    r = assert_clean(client.post("/api/jobs/linkedin-import", json={"linkedin_ids": []}), 200)
    assert r.json()["accepted"] == 0


def test_linkedin_import_missing_key_is_accepted_zero(client):
    r = assert_clean(client.post("/api/jobs/linkedin-import", json={}), 200)
    assert r.json()["accepted"] == 0


def test_linkedin_import_filters_falsy_ids(client, monkeypatch):
    import backend.api.routes_jobs as rj

    async def _noop(ids):
        return None
    monkeypatch.setattr(rj, "_scrape_linkedin_ids", _noop)
    r = assert_clean(client.post("/api/jobs/linkedin-import",
                                 json={"linkedin_ids": ["", None, 0, "4012345"]}), 200)
    assert r.json()["accepted"] == 1


@pytest.mark.xfail(strict=True, reason="R4-T1-13")
def test_linkedin_import_non_json_body_is_422_not_500(client):
    """The handler does a bare `await request.json()` — a junk body is an unhandled 500."""
    r = client.post("/api/jobs/linkedin-import", content=b"not json",
                    headers={"Content-Type": "application/json"})
    assert r.status_code in (400, 422)


@pytest.mark.xfail(strict=True, reason="R4-T1-14")
def test_linkedin_import_non_iterable_ids_is_422_not_500(client, monkeypatch):
    """`{"linkedin_ids": 5}` reaches a for-loop over an int."""
    import backend.api.routes_jobs as rj

    async def _noop(ids):
        return None
    monkeypatch.setattr(rj, "_scrape_linkedin_ids", _noop)
    assert client.post("/api/jobs/linkedin-import",
                       json={"linkedin_ids": 5}).status_code in (400, 422)


@pytest.mark.xfail(strict=True, reason="R4-T1-14")
def test_linkedin_import_string_ids_is_rejected_not_split_into_characters(client, monkeypatch):
    """A bare string is iterated per character — seven bogus "ids" for one job."""
    import backend.api.routes_jobs as rj

    async def _noop(ids):
        return None
    monkeypatch.setattr(rj, "_scrape_linkedin_ids", _noop)
    r = client.post("/api/jobs/linkedin-import", json={"linkedin_ids": "4012345"})
    assert r.status_code in (400, 422) or r.json()["accepted"] == 1


def test_linkedin_import_second_call_is_409_while_running(client, monkeypatch):
    import asyncio
    import backend.api.routes_jobs as rj
    gate = asyncio.Event()

    async def _slow(ids):
        await gate.wait()
    monkeypatch.setattr(rj, "_scrape_linkedin_ids", _slow)

    r1 = assert_clean(client.post("/api/jobs/linkedin-import", json={"linkedin_ids": ["1"]}), 200)
    assert r1.json()["run_id"]
    r2 = client.post("/api/jobs/linkedin-import", json={"linkedin_ids": ["2"]})
    assert_clean(r2, 409)
    gate.set()


# ── /api/jobs/{id} sub-resources ─────────────────────────────────────────────

def test_cached_page_missing_job_is_404(client):
    assert_clean(client.get(f"/api/jobs/{MISSING_UUID}/cached-page"), 404)


def test_cached_page_without_cache_is_404(client, test_db):
    job = make_job(test_db)
    assert_clean(client.get(f"/api/jobs/{job.id}/cached-page"), 404)


def test_unscored_ids_default_limit_is_fine(client):
    """Postgres-only SQL (`cv_scores::text`) — only the shape is asserted here."""
    r = client.get("/api/jobs/unscored-ids")
    assert_no_leak(r)
