"""Round 4 · T5 regressions — template whitelist, auth throttle, analyze 404, tracer tokens.

Findings: R4-T5-01 (path traversal via the `template` field), R4-T5-06 (no rate limit on
the unauthenticated auth endpoints), R4-T5-07 (guessable tracer tokens), R4-T5-09 (a
well-formed but unknown job id 500s on the JobRun FK), R4-T5-12 (`https://` prefixed onto
`tel:`/`mailto:` contact values).
"""
import uuid

import pytest
from fastapi import HTTPException

from backend.api.routes_resumes import (
    TEMPLATES_DIR,
    _discover_templates,
    _is_traceable_url,
    _rewrite_urls_with_tracers,
    validate_template_name,
)
from backend.api.routes_cover_letters import TEMPLATES_DIR as CL_TEMPLATES_DIR
from backend.models.db import Resume, Setting, TracerLink


@pytest.fixture
def open_auth(test_db):
    """First-run mode: an empty dashboard_api_key row means no key is required."""
    test_db.add(Setting(key="dashboard_api_key", value=""))
    test_db.commit()


def _a_real_template() -> str:
    names = [t["id"] for t in _discover_templates()]
    assert names, "no résumé templates on disk"
    return "inter" if "inter" in names else names[0]


# ── R4-T5-01 · template name whitelist ───────────────────────────────────────

TRAVERSALS = [
    "../cover_letter_templates/garamond",
    "../../backend/resume_templates/inter",
    "../../../../etc",
    "/etc/passwd",
    "/etc",
    "..",
    ".",
    "./inter",
    "inter/../inter",
    "inter/",
    "\\..\\inter",
    "..%2f..%2fetc",          # a client that double-encodes gets the literal string
    "%2e%2e%2fgaramond",
    "Inter",                   # the folders are lowercase; no case-folding lookups
    "inter ",
    "",
    "in-ter",
]


@pytest.mark.parametrize("name", TRAVERSALS)
def test_template_name_rejects_anything_that_is_not_a_folder(name):
    for base in (TEMPLATES_DIR, CL_TEMPLATES_DIR):
        with pytest.raises(HTTPException) as exc:
            validate_template_name(name, base)
        assert exc.value.status_code == 422


@pytest.mark.parametrize("name", [None, 1, ["inter"], {"id": "inter"}])
def test_template_name_rejects_non_strings(name):
    with pytest.raises(HTTPException) as exc:
        validate_template_name(name, TEMPLATES_DIR)
    assert exc.value.status_code == 422


def test_template_name_accepts_every_discovered_template():
    for t in _discover_templates():
        assert validate_template_name(t["id"], TEMPLATES_DIR) == t["id"]


def test_render_html_rejects_a_traversal(test_db):
    from backend.api.routes_resumes import _render_html
    with pytest.raises(HTTPException) as exc:
        _render_html({}, "../cover_letter_templates/garamond", "letter")
    assert exc.value.status_code == 422


def test_cover_letter_render_rejects_a_traversal(test_db):
    from backend.api.routes_cover_letters import _render_html as cl_render
    with pytest.raises(HTTPException) as exc:
        cl_render({}, "../resume_templates/inter", "letter")
    assert exc.value.status_code == 422


def _make_resume(test_db) -> Resume:
    r = Resume(name="Base", is_base=True, template=_a_real_template(),
               page_format="letter", json_data={"header": {"name": "V"}})
    test_db.add(r)
    test_db.commit()
    return r


@pytest.mark.parametrize("payload", [
    "../cover_letter_templates/garamond",
    "%2e%2e%2fcover_letter_templates%2fgaramond",
    "/etc/passwd",
])
def test_pdf_template_query_param_cannot_escape_the_template_dir(api_client, test_db, open_auth, payload):
    r = _make_resume(test_db)
    resp = api_client.get(f"/api/resumes/{r.id}/pdf?template={payload}")
    assert resp.status_code == 422, resp.text


def test_patch_resume_rejects_a_bad_template(api_client, test_db, open_auth):
    r = _make_resume(test_db)
    resp = api_client.patch(f"/api/resumes/{r.id}", json={"template": "../cover_letter_templates/garamond"})
    assert resp.status_code == 422
    test_db.refresh(r)
    assert r.template == _a_real_template()   # nothing was half-applied


def test_patch_resume_accepts_a_real_template(api_client, test_db, open_auth):
    r = _make_resume(test_db)
    resp = api_client.patch(f"/api/resumes/{r.id}", json={"template": _a_real_template()})
    assert resp.status_code == 200


def test_create_resume_rejects_a_bad_template(api_client, test_db, open_auth):
    resp = api_client.post("/api/resumes", json={"name": "X", "template": "../etc"})
    assert resp.status_code == 422


def test_patch_cover_letter_rejects_a_bad_template(api_client, test_db, open_auth):
    from backend.models.db import CoverLetter
    cl = CoverLetter(name="CL", template="inter", page_format="letter", json_data={})
    test_db.add(cl)
    test_db.commit()
    resp = api_client.patch(f"/api/cover-letters/{cl.id}", json={"template": "../resume_templates/inter"})
    assert resp.status_code == 422


# ── R4-T5-06 · auth throttle ─────────────────────────────────────────────────

@pytest.fixture
def keyed(test_db):
    """A configured dashboard key + an empty throttle table."""
    from backend.main import _reset_auth_throttle
    test_db.add(Setting(key="dashboard_api_key", value="right-key"))
    test_db.commit()
    _reset_auth_throttle()
    yield "right-key"
    _reset_auth_throttle()


def test_verify_throttles_after_ten_failures(api_client, keyed):
    for i in range(10):
        r = api_client.post("/api/auth/verify", json={"api_key": "wrong"})
        assert r.status_code == 401, f"attempt {i}: {r.status_code}"
    r = api_client.post("/api/auth/verify", json={"api_key": "wrong"})
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) >= 1
    # The correct key is refused too while the bucket is full — the lockout is per IP.
    assert api_client.post("/api/auth/verify", json={"api_key": keyed}).status_code == 429


def test_set_session_shares_the_same_bucket(api_client, keyed):
    for _ in range(10):
        assert api_client.post("/api/auth/set-session", json={"api_key": "wrong"}).status_code == 401
    r = api_client.post("/api/auth/verify", json={"api_key": "wrong"})
    assert r.status_code == 429


def test_a_success_clears_the_bucket(api_client, keyed):
    for _ in range(9):
        assert api_client.post("/api/auth/verify", json={"api_key": "wrong"}).status_code == 401
    assert api_client.post("/api/auth/verify", json={"api_key": keyed}).status_code == 200
    # Budget is back to full: nine more misses still answer 401.
    for _ in range(9):
        assert api_client.post("/api/auth/verify", json={"api_key": "wrong"}).status_code == 401


def test_throttle_buckets_are_per_ip(api_client, keyed):
    for _ in range(11):
        api_client.post("/api/auth/verify", json={"api_key": "wrong"},
                        headers={"X-Forwarded-For": "10.0.0.9"})
    assert api_client.post("/api/auth/verify", json={"api_key": "wrong"},
                           headers={"X-Forwarded-For": "10.0.0.9"}).status_code == 429
    assert api_client.post("/api/auth/verify", json={"api_key": "wrong"},
                           headers={"X-Forwarded-For": "10.0.0.10"}).status_code == 401


def test_the_window_expires(api_client, keyed, monkeypatch):
    import backend.main as main_mod
    for _ in range(11):
        api_client.post("/api/auth/verify", json={"api_key": "wrong"})
    assert api_client.post("/api/auth/verify", json={"api_key": "wrong"}).status_code == 429
    real = main_mod._time.monotonic
    monkeypatch.setattr(main_mod._time, "monotonic", lambda: real() + main_mod._AUTH_FAIL_WINDOW + 1)
    assert api_client.post("/api/auth/verify", json={"api_key": "wrong"}).status_code == 401


# ── R4-T5-09 · analyze a job that does not exist ─────────────────────────────

def test_analyze_unknown_job_id_is_404(api_client, test_db, open_auth):
    resp = api_client.post(f"/api/analyze/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert resp.json()["detail"]


def test_analyze_malformed_job_id_is_still_404(api_client, test_db, open_auth):
    assert api_client.post("/api/analyze/not-a-uuid").status_code == 404


def test_analyze_writes_no_job_run_for_an_unknown_id(api_client, test_db, open_auth):
    from backend.models.db import JobRun
    api_client.post(f"/api/analyze/{uuid.uuid4()}")
    assert test_db.query(JobRun).count() == 0


# ── R4-T5-07 / R4-T5-12 · tracer links ───────────────────────────────────────

@pytest.fixture
def tracer_on(test_db):
    test_db.add_all([
        Setting(key="tracer_links_enabled", value="true"),
        Setting(key="tracer_links_base_url", value="https://example.test"),
    ])
    test_db.commit()


def _rewrite(test_db, items):
    r = Resume(name="R", is_base=True, template=_a_real_template(),
               page_format="letter", json_data={"header": {"contact_items": items}})
    test_db.add(r)
    test_db.commit()
    out = _rewrite_urls_with_tracers(r.json_data, str(r.id), test_db)
    return out["header"]["contact_items"]


@pytest.mark.parametrize("url", [
    "tel:+15551234567",
    "mailto:someone@example.com",
    "sms:+15551234567",
    "SMS:+15551234567",
    "skype:live.someone",
    "someone@gmail.com",
])
def test_non_web_contact_values_are_left_alone(test_db, tracer_on, url):
    items = _rewrite(test_db, [{"text": "Contact", "url": url}])
    assert items[0]["url"] == url
    assert test_db.query(TracerLink).count() == 0


@pytest.mark.parametrize("url", ["tel:+1555", "mailto:a@b.co", "sms:+1555", "a@b.co", "", "   "])
def test_is_traceable_url_says_no(url):
    assert _is_traceable_url(url) is False


@pytest.mark.parametrize("url", ["https://x.com", "http://x.com", "x.com", "linkedin.com/in/v"])
def test_is_traceable_url_says_yes(url):
    assert _is_traceable_url(url) is True


def test_a_web_url_still_gets_a_tracer(test_db, tracer_on):
    items = _rewrite(test_db, [{"text": "Site", "url": "viktoresadze.com"}])
    assert items[0]["url"].startswith("https://example.test/cv/")
    link = test_db.query(TracerLink).one()
    assert link.destination_url == "https://viktoresadze.com"


def test_random_tokens_are_long_and_unguessable(test_db, tracer_on):
    """No job → no deterministic short_id, so the token is the random fallback."""
    tokens = set()
    for i in range(5):
        items = _rewrite(test_db, [{"text": "Site", "url": f"site{i}.example"}])
        tokens.add(items[0]["url"].rsplit("/", 1)[-1])
    assert len(tokens) == 5
    for t in tokens:
        assert len(t) >= 8, t


def test_random_tokens_come_from_secrets(test_db, tracer_on, monkeypatch):
    """`random` (Mersenne Twister) must not be what stands behind a tracer token."""
    import random as _random
    def _boom(*a, **kw):
        raise AssertionError("tracer token drawn from random, not secrets")
    monkeypatch.setattr(_random, "choices", _boom)
    monkeypatch.setattr(_random, "choice", _boom)
    items = _rewrite(test_db, [{"text": "Site", "url": "site.example"}])
    assert items[0]["url"].startswith("https://example.test/cv/")
