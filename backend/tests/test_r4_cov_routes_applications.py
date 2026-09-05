"""R4-T6 · line coverage for the branches of `backend/api/routes_applications.py`
the contract pass (T1) never reached.

T1 drove the CRUD surface. What stayed dark was the page-caching machinery
(`_extract_clean_content`, `_fetch_with_playwright`, `_cache_job_page` and each
of its five failure arms), the posting-URL reader (`_company_from_url`,
`_is_ats_brand`, `_title_slug`, `_decode_entities`, `POST /extract`), the
interview `when_at` re-parse, and the whole `GET /{id}/prep` bundle.

Every test pins what the code does today. Nothing here is xfailed.
"""
import uuid as _uuid
from datetime import datetime, timedelta, timezone

import pytest

# Bound BEFORE `_no_outbound` replaces the module attribute with a no-op, so the
# real coroutine is still reachable from these tests.
from backend.api.routes_applications import _cache_job_page as real_cache_job_page

from backend.tests.r4_support import (  # noqa: F401
    client, _clear_running_state, _no_outbound, assert_clean,
    make_job, make_company, make_resume, set_setting,
)


# ── helpers ──────────────────────────────────────────────────────────────────

class _Resp:
    def __init__(self, text="", raise_exc=None):
        self.text = text
        self._raise = raise_exc

    def raise_for_status(self):
        if self._raise:
            raise self._raise


def _patch_url_safety(monkeypatch, *, safe_get=None, gate=None):
    """Point the SSRF helpers at test doubles.

    Both are imported inside the handlers, so patching the module attributes is
    what the running code sees.
    """
    import backend.scraper._shared.url_safety as us
    if safe_get is not None:
        async def _fake(*a, **kw):
            if isinstance(safe_get, BaseException):
                raise safe_get
            return safe_get
        monkeypatch.setattr(us, "safe_get", _fake)
    if gate is not None:
        def _gate(url):
            if isinstance(gate, BaseException):
                raise gate
            return None
        monkeypatch.setattr(us, "assert_public_http_url", _gate)


def _break_commit(monkeypatch):
    """Make every later `db.commit()` fail, and count the rollbacks.

    `_cache_job_page` records why it gave up by writing `cache_error` and
    committing; each of those writes has its own rollback arm for the case where
    even that commit fails (a dropped connection, a full disk). Call this AFTER
    the fixture rows are in place.
    """
    import backend.models.db as db_mod
    rolled = []
    Session = db_mod.SessionLocal.class_
    real_rollback = Session.rollback

    def _commit(self, *a, **k):
        raise RuntimeError("connection gone")

    def _rollback(self, *a, **k):
        rolled.append(1)
        return real_rollback(self, *a, **k)

    monkeypatch.setattr(Session, "commit", _commit)
    monkeypatch.setattr(Session, "rollback", _rollback)
    return rolled


def _make_app(db, **job_kw):
    from backend.models.db import Application
    job = make_job(db, **job_kw)
    app = Application(job_id=job.id, status="applied")
    db.add(app)
    db.commit()
    db.refresh(app)
    return app, job


# ── _extract_clean_content ───────────────────────────────────────────────────

def test_extract_clean_content_drops_chrome_and_controls():
    from backend.api.routes_applications import _extract_clean_content
    html = ("<html><body><nav>menu</nav><script>x=1</script><style>a{}</style>"
            "<form><input><button>Apply</button></form>"
            "<p>Real body text</p><footer>legal</footer></body></html>")
    clean, text = _extract_clean_content(html)
    assert "Real body text" in text
    for gone in ("menu", "x=1", "Apply", "legal"):
        assert gone not in text


def test_extract_clean_content_drops_hidden_nodes():
    from backend.api.routes_applications import _extract_clean_content
    html = ('<body><p aria-hidden="true">hidden a</p>'
            '<p style="display: none">hidden b</p><p>visible</p></body>')
    _, text = _extract_clean_content(html)
    assert "visible" in text
    assert "hidden a" not in text and "hidden b" not in text


def test_extract_clean_content_unwraps_unknown_tags_but_keeps_their_text():
    from backend.api.routes_applications import _extract_clean_content
    clean, text = _extract_clean_content("<body><marquee>kept text</marquee></body>")
    assert "kept text" in text
    assert "marquee" not in clean


def test_extract_clean_content_keeps_only_href_on_links():
    from backend.api.routes_applications import _extract_clean_content
    clean, _ = _extract_clean_content(
        '<body><a href="/apply" class="btn" onclick="go()">Apply here</a>'
        '<a name="anchor">bare</a></body>')
    assert 'href="/apply"' in clean and 'target="_blank"' in clean
    assert "onclick" not in clean and 'class="btn"' not in clean
    assert 'name="anchor"' not in clean


def test_extract_clean_content_strips_attributes_from_kept_tags():
    from backend.api.routes_applications import _extract_clean_content
    clean, _ = _extract_clean_content('<body><p id="x" data-y="z">text</p></body>')
    assert "<p>text</p>" in clean


def test_extract_clean_content_collapses_break_runs_and_empty_divs():
    from backend.api.routes_applications import _extract_clean_content
    clean, _ = _extract_clean_content(
        "<body>a<br><br><br><br>b<div></div><div></div><div></div>c</body>")
    assert clean.count("<br") <= 2
    assert clean.count("<div></div>") == 0


def test_extract_clean_content_without_a_body_uses_the_whole_soup():
    from backend.api.routes_applications import _extract_clean_content
    clean, text = _extract_clean_content("<p>fragment only</p>")
    assert "fragment only" in text and "fragment only" in clean


def test_extract_clean_content_caps_the_text_at_fifty_thousand_chars():
    from backend.api.routes_applications import _extract_clean_content
    _, text = _extract_clean_content("<body><p>" + ("word " * 40000) + "</p></body>")
    assert len(text) == 50_000


# ── _fetch_with_playwright ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_with_playwright_revalidates_the_url_before_launching(monkeypatch):
    """The SSRF gate runs first: a rejected URL never opens a browser."""
    from backend.scraper._shared.url_safety import UnsafeURLError
    import backend.scraper._shared.browser as br
    from backend.api.routes_applications import _fetch_with_playwright
    _patch_url_safety(monkeypatch, gate=UnsafeURLError("link-local"))
    opened = []
    monkeypatch.setattr(br, "_get_browser",
                        lambda *a, **k: opened.append(1), raising=False)
    with pytest.raises(UnsafeURLError):
        await _fetch_with_playwright("http://169.254.169.254/")
    assert opened == []


@pytest.mark.asyncio
async def test_fetch_with_playwright_returns_the_rendered_content(monkeypatch):
    """Happy path: the page is closed, then the browser, then the driver."""
    import backend.scraper._shared.browser as br
    from backend.api.routes_applications import _fetch_with_playwright
    _patch_url_safety(monkeypatch, gate=True)
    order = []

    class _Page:
        async def goto(self, url, **kw):
            order.append(("goto", url))

        async def wait_for_timeout(self, ms):
            order.append(("wait", ms))

        async def content(self):
            return "<html>rendered</html>"

    class _Browser:
        async def close(self):
            order.append(("browser.close",))

    class _PW:
        async def stop(self):
            order.append(("pw.stop",))

    async def _get_browser():
        return _PW(), _Browser()

    async def _new_page(browser):
        return _Page()

    async def _close_page(page):
        order.append(("page.close",))

    monkeypatch.setattr(br, "_get_browser", _get_browser)
    monkeypatch.setattr(br, "_new_page", _new_page)
    monkeypatch.setattr(br, "_close_page", _close_page)
    assert await _fetch_with_playwright("https://e.com/j") == "<html>rendered</html>"
    assert [o[0] for o in order] == ["goto", "wait", "page.close", "browser.close", "pw.stop"]


# ── _cache_job_page ──────────────────────────────────────────────────────────

_GOOD_HTML = "<html><body><p>" + ("Responsibilities and requirements. " * 30) + "</p></body></html>"


@pytest.mark.asyncio
async def test_cache_job_page_ignores_a_missing_job(test_db):
    """A job deleted between queueing and running is a no-op, not a crash."""
    await real_cache_job_page(str(_uuid.uuid4()), "https://e.com/j")


@pytest.mark.asyncio
async def test_cache_job_page_ignores_a_blank_url(test_db):
    job = make_job(test_db)
    await real_cache_job_page(str(job.id), "")
    test_db.refresh(job)
    assert job.cache_error is None and job.page_cached_at is None


@pytest.mark.asyncio
async def test_cache_job_page_records_an_unsafe_url(test_db, monkeypatch):
    from backend.scraper._shared.url_safety import UnsafeURLError
    _patch_url_safety(monkeypatch, gate=UnsafeURLError("private range"))
    job = make_job(test_db)
    await real_cache_job_page(str(job.id), "http://169.254.169.254/")
    test_db.refresh(job)
    assert job.cache_error.startswith("unsafe URL: ")
    assert job.cached_page_html is None


@pytest.mark.asyncio
async def test_cache_job_page_records_an_unsafe_redirect_and_does_not_fall_back(test_db, monkeypatch):
    """A redirect into a private range must not be retried with Playwright."""
    from backend.scraper._shared.url_safety import UnsafeURLError
    import backend.api.routes_applications as ra
    _patch_url_safety(monkeypatch, gate=True, safe_get=UnsafeURLError("redirect to 10.0.0.1"))
    tried = []
    monkeypatch.setattr(ra, "_fetch_with_playwright", lambda url: tried.append(url))
    job = make_job(test_db)
    await real_cache_job_page(str(job.id), "https://e.com/j")
    test_db.refresh(job)
    assert job.cache_error.startswith("unsafe redirect: ")
    assert tried == []


@pytest.mark.asyncio
async def test_cache_job_page_stores_a_good_fetch_and_clears_a_stale_error(test_db, monkeypatch):
    _patch_url_safety(monkeypatch, gate=True, safe_get=_Resp(text=_GOOD_HTML))
    job = make_job(test_db)
    job.cache_error = "an error from last time"
    test_db.commit()
    await real_cache_job_page(str(job.id), "https://e.com/j")
    test_db.refresh(job)
    assert "Responsibilities" in job.cached_page_text
    assert job.cached_page_html and job.page_cached_at is not None
    assert job.cache_error is None


@pytest.mark.asyncio
async def test_cache_job_page_falls_back_to_playwright_when_httpx_fails(test_db, monkeypatch):
    import backend.api.routes_applications as ra
    _patch_url_safety(monkeypatch, gate=True, safe_get=RuntimeError("403 Forbidden"))

    async def _pw(url):
        return _GOOD_HTML

    monkeypatch.setattr(ra, "_fetch_with_playwright", _pw)
    job = make_job(test_db)
    await real_cache_job_page(str(job.id), "https://e.com/j")
    test_db.refresh(job)
    assert "Responsibilities" in job.cached_page_text
    assert job.cache_error is None


@pytest.mark.asyncio
async def test_cache_job_page_falls_back_on_thin_html_too(test_db, monkeypatch):
    """A 200 that renders almost nothing is treated as a miss, not a success."""
    import backend.api.routes_applications as ra
    _patch_url_safety(monkeypatch, gate=True,
                      safe_get=_Resp(text="<html><body><div id=root></div></body></html>"))

    async def _pw(url):
        return _GOOD_HTML

    monkeypatch.setattr(ra, "_fetch_with_playwright", _pw)
    job = make_job(test_db)
    await real_cache_job_page(str(job.id), "https://e.com/j")
    test_db.refresh(job)
    assert "Responsibilities" in job.cached_page_text


@pytest.mark.asyncio
async def test_cache_job_page_records_a_playwright_failure(test_db, monkeypatch):
    import backend.api.routes_applications as ra
    _patch_url_safety(monkeypatch, gate=True, safe_get=RuntimeError("connection reset"))

    async def _pw(url):
        raise RuntimeError("browser refused")

    monkeypatch.setattr(ra, "_fetch_with_playwright", _pw)
    job = make_job(test_db)
    await real_cache_job_page(str(job.id), "https://e.com/j")
    test_db.refresh(job)
    assert job.cache_error == "playwright: browser refused"
    assert job.cached_page_html is None


@pytest.mark.asyncio
async def test_cache_job_page_records_no_usable_content(test_db, monkeypatch):
    """Both fetchers succeeded but the page carries no text worth keeping."""
    import backend.api.routes_applications as ra
    _patch_url_safety(monkeypatch, gate=True, safe_get=_Resp(text="<html><body>hi</body></html>"))

    async def _pw(url):
        return "<html><body>hi</body></html>"

    monkeypatch.setattr(ra, "_fetch_with_playwright", _pw)
    job = make_job(test_db)
    await real_cache_job_page(str(job.id), "https://e.com/j")
    test_db.refresh(job)
    assert job.cache_error.startswith("no usable content (")


@pytest.mark.asyncio
async def test_cache_job_page_records_an_unexpected_failure(test_db, monkeypatch):
    """An exception outside the fetch arms still lands in `cache_error`."""
    import backend.api.routes_applications as ra
    _patch_url_safety(monkeypatch, gate=True, safe_get=_Resp(text=_GOOD_HTML))

    def _boom(raw):
        raise ValueError("parser exploded")

    monkeypatch.setattr(ra, "_extract_clean_content", _boom)
    job = make_job(test_db)
    await real_cache_job_page(str(job.id), "https://e.com/j")
    test_db.refresh(job)
    assert job.cache_error == "parser exploded"


@pytest.mark.asyncio
async def test_cache_job_page_rolls_back_when_recording_an_unsafe_url_fails(test_db, monkeypatch):
    """Even the "write down why we refused" commit has a rollback arm."""
    from backend.scraper._shared.url_safety import UnsafeURLError
    job = make_job(test_db)
    _patch_url_safety(monkeypatch, gate=UnsafeURLError("private range"))
    rolled = _break_commit(monkeypatch)
    await real_cache_job_page(str(job.id), "http://169.254.169.254/")
    assert rolled


@pytest.mark.asyncio
async def test_cache_job_page_rolls_back_when_recording_an_unsafe_redirect_fails(test_db, monkeypatch):
    from backend.scraper._shared.url_safety import UnsafeURLError
    job = make_job(test_db)
    _patch_url_safety(monkeypatch, gate=True, safe_get=UnsafeURLError("redirect to 10.0.0.1"))
    rolled = _break_commit(monkeypatch)
    await real_cache_job_page(str(job.id), "https://e.com/j")
    assert rolled


@pytest.mark.asyncio
async def test_cache_job_page_rolls_back_when_recording_no_content_fails(test_db, monkeypatch):
    import backend.api.routes_applications as ra
    job = make_job(test_db)
    _patch_url_safety(monkeypatch, gate=True, safe_get=_Resp(text="<html><body>hi</body></html>"))

    async def _pw(url):
        return "<html><body>hi</body></html>"

    monkeypatch.setattr(ra, "_fetch_with_playwright", _pw)
    rolled = _break_commit(monkeypatch)
    await real_cache_job_page(str(job.id), "https://e.com/j")
    assert rolled


@pytest.mark.asyncio
async def test_cache_job_page_rolls_back_when_recording_an_unexpected_failure_fails(test_db, monkeypatch):
    import backend.api.routes_applications as ra
    job = make_job(test_db)
    _patch_url_safety(monkeypatch, gate=True, safe_get=_Resp(text=_GOOD_HTML))

    def _boom(raw):
        raise ValueError("parser exploded")

    monkeypatch.setattr(ra, "_extract_clean_content", _boom)
    rolled = _break_commit(monkeypatch)
    await real_cache_job_page(str(job.id), "https://e.com/j")
    assert rolled


# ── POST "" — the back-dated applied_at ──────────────────────────────────────

def test_create_application_back_dates_a_parseable_applied_at(client, test_db):
    from backend.models.db import Application
    r = assert_clean(client.post("/api/applications", json={
        "title": "PM", "company": "Acme", "url": "https://e.com/j",
        "applied_at": "2026-01-02T03:04:05+00:00"}), 200)
    app = test_db.query(Application).filter(
        Application.id == _uuid.UUID(r.json()["id"])).first()
    assert app.applied_at.year == 2026 and app.applied_at.month == 1


# ── GET "" — the tailored-résumé join ────────────────────────────────────────

def test_list_applications_reports_the_latest_tailored_resume(client, test_db):
    app, job = _make_app(test_db)
    older = make_resume(test_db, name="T1", is_base=False, job_id=job.id)
    newer = make_resume(test_db, name="T2", is_base=False, job_id=job.id)
    now = datetime.now(timezone.utc)
    older.updated_at = now - timedelta(hours=1)
    newer.updated_at = now
    test_db.commit()
    row = assert_clean(client.get("/api/applications"), 200).json()["applications"][0]
    assert row["tailored_resume_name"] == "T2"
    assert row["tailored_resume_id"] == str(newer.id)


def test_list_applications_flags_a_cover_letter(client, test_db):
    from backend.models.db import CoverLetter
    app, job = _make_app(test_db)
    test_db.add(CoverLetter(name="CL", job_id=job.id, json_data={}))
    test_db.commit()
    row = assert_clean(client.get("/api/applications"), 200).json()["applications"][0]
    assert row["has_cover_letter"] is True


# ── the posting-URL reader helpers ───────────────────────────────────────────

@pytest.mark.parametrize("slug,expected", [
    ("clear-street", "Clear Street"),
    ("BoschGroup", "BoschGroup"),
    ("acme_corp.two three", "Acme Corp Two Three"),
    ("", ""),
    (None, ""),
])
def test_title_slug(slug, expected):
    from backend.api.routes_applications import _title_slug
    assert _title_slug(slug) == expected


@pytest.mark.parametrize("name", ["Greenhouse", "Lever", "Workday Jobs", "LinkedIn",
                                  "Jobs", "Careers", "Job Board"])
def test_is_ats_brand_rejects_board_names_and_chrome(name):
    from backend.api.routes_applications import _is_ats_brand
    assert _is_ats_brand(name) is True


@pytest.mark.parametrize("name", ["Acme", "Clear Street", "Vercel"])
def test_is_ats_brand_accepts_a_real_employer(name):
    from backend.api.routes_applications import _is_ats_brand
    assert _is_ats_brand(name) is False


def test_is_ats_brand_treats_empty_as_not_a_brand():
    """An empty value is "nothing found", which is not the same as "a board"."""
    from backend.api.routes_applications import _is_ats_brand
    assert _is_ats_brand("") is False
    assert _is_ats_brand("   ") is False
    assert _is_ats_brand(None) is False


@pytest.mark.parametrize("url,expected", [
    ("https://boards.greenhouse.io/vercel/jobs/123", "Vercel"),
    ("https://job-boards.greenhouse.io/clear-street/jobs/9", "Clear Street"),
    ("https://boards.greenhouse.io/embed/job_board?for=stripe", "Stripe"),
    ("https://jobs.lever.co/anthropic/abc-123", "Anthropic"),
    ("https://jobs.ashbyhq.com/ramp/xyz", "Ramp"),
    ("https://acme.wd5.myworkdayjobs.com/External/job/1", "Acme"),
])
def test_company_from_url_reads_the_board_slug(url, expected):
    from backend.api.routes_applications import _company_from_url
    assert _company_from_url(url) == expected


@pytest.mark.parametrize("url", [
    "", None,
    "https://example.com/careers/senior-pm",     # not a known board
    "https://boards.greenhouse.io/jobs",         # slug is pure chrome
])
def test_company_from_url_returns_none_when_it_cannot_tell(url):
    from backend.api.routes_applications import _company_from_url
    assert _company_from_url(url) is None


def test_company_from_url_survives_an_unparseable_url(monkeypatch):
    """A malformed board URL must never break the reader — the helper answers
    None rather than raising into the endpoint."""
    import backend.api.routes_applications as ra
    import urllib.parse

    def _boom(url):
        raise ValueError("bad url")

    monkeypatch.setattr(urllib.parse, "urlparse", _boom)
    assert ra._company_from_url("https://boards.greenhouse.io/x/jobs/1") is None


def test_company_from_url_survives_a_raising_board_predicate(monkeypatch):
    from backend.api.routes_applications import _company_from_url
    import backend.scraper.ats.greenhouse as gh

    def _boom(url):
        raise RuntimeError("regex blew up")

    monkeypatch.setattr(gh, "is_greenhouse", _boom)
    assert _company_from_url("https://boards.greenhouse.io/x/jobs/1") is None


@pytest.mark.parametrize("raw,expected", [
    ("R&amp;D Lead", "R&D Lead"),
    ("R&amp;amp;D Lead", "R&D Lead"),
    ("plain", "plain"),
    ("", ""),
    (None, None),
])
def test_decode_entities_unescapes_repeatedly(raw, expected):
    from backend.api.routes_applications import _decode_entities
    assert _decode_entities(raw) == expected


# ── POST /extract ────────────────────────────────────────────────────────────

def test_extract_reads_json_ld_job_posting(client, monkeypatch):
    _patch_url_safety(monkeypatch, gate=True, safe_get=_Resp(text="""
        <html><head><script type="application/ld+json">
        {"@type":"JobPosting","title":"Staff PM &amp; Lead",
         "hiringOrganization":{"name":"Acme Corp"}}
        </script></head><body></body></html>"""))
    body = assert_clean(client.post("/api/applications/extract",
                                    json={"url": "https://e.com/j"}), 200).json()
    assert body == {"title": "Staff PM & Lead", "company": "Acme Corp"}


def test_extract_accepts_a_string_hiring_organization(client, monkeypatch):
    _patch_url_safety(monkeypatch, gate=True, safe_get=_Resp(text="""
        <html><head><script type="application/ld+json">
        [{"@type":"JobPosting","title":"PM","hiringOrganization":"Acme Corp"}]
        </script></head><body></body></html>"""))
    body = assert_clean(client.post("/api/applications/extract",
                                    json={"url": "https://e.com/j"}), 200).json()
    assert body["company"] == "Acme Corp"


def test_extract_skips_unparseable_and_non_object_json_ld(client, monkeypatch):
    """A broken or scalar ld+json block is stepped over, not fatal — the
    OpenGraph layer below it still answers."""
    _patch_url_safety(monkeypatch, gate=True, safe_get=_Resp(text="""
        <html><head>
        <script type="application/ld+json">{not json at all</script>
        <script type="application/ld+json">["a string", 7]</script>
        <meta property="og:title" content="Fallback Title">
        <meta property="og:site_name" content="Acme Corp">
        </head><body></body></html>"""))
    body = assert_clean(client.post("/api/applications/extract",
                                    json={"url": "https://e.com/j"}), 200).json()
    assert body == {"title": "Fallback Title", "company": "Acme Corp"}


def test_extract_drops_a_board_brand_from_og_site_name(client, monkeypatch):
    """og:site_name on an ATS board is the board, so the URL slug wins instead."""
    _patch_url_safety(monkeypatch, gate=True, safe_get=_Resp(text=
        '<html><head><meta property="og:site_name" content="Greenhouse">'
        '<title>Senior PM | Greenhouse</title></head><body></body></html>'))
    body = assert_clean(client.post("/api/applications/extract", json={
        "url": "https://boards.greenhouse.io/vercel/jobs/1"}), 200).json()
    assert body["company"] == "Vercel"
    assert body["title"] == "Senior PM"


def test_extract_falls_back_to_the_hostname(client, monkeypatch):
    _patch_url_safety(monkeypatch, gate=True,
                      safe_get=_Resp(text="<html><body>nothing</body></html>"))
    body = assert_clean(client.post("/api/applications/extract", json={
        "url": "https://www.acme.com/careers/1"}), 200).json()
    assert body["company"] == "Acme"


def test_extract_leaves_company_empty_rather_than_naming_a_board(client, monkeypatch):
    _patch_url_safety(monkeypatch, gate=True,
                      safe_get=_Resp(text="<html><body>nothing</body></html>"))
    body = assert_clean(client.post("/api/applications/extract", json={
        "url": "https://www.linkedin.com/jobs/view/1"}), 200).json()
    assert body["company"] is None


def test_extract_refuses_an_unsafe_url(client, monkeypatch):
    from backend.scraper._shared.url_safety import UnsafeURLError
    _patch_url_safety(monkeypatch, gate=UnsafeURLError("loopback"))
    r = assert_clean(client.post("/api/applications/extract",
                                 json={"url": "http://127.0.0.1/"}), 400)
    assert "Unsafe URL" in r.text


def test_extract_still_answers_200_when_the_fetch_fails(client, monkeypatch):
    """The modal keeps working offline: a failed fetch degrades to the URL-only
    reading rather than an error."""
    _patch_url_safety(monkeypatch, gate=True, safe_get=RuntimeError("timed out"))
    body = assert_clean(client.post("/api/applications/extract", json={
        "url": "https://jobs.lever.co/anthropic/1"}), 200).json()
    assert body == {"title": None, "company": "Anthropic"}


def test_extract_reraises_an_httpexception_from_the_fetch(client, monkeypatch):
    from fastapi import HTTPException
    _patch_url_safety(monkeypatch, gate=True, safe_get=HTTPException(418, "teapot"))
    assert_clean(client.post("/api/applications/extract",
                             json={"url": "https://e.com/j"}), 418)


# ── interviews ───────────────────────────────────────────────────────────────

def test_patch_interview_reparses_when_at(client, test_db):
    """A zone-less calendar value is read as UTC; an empty one clears the date."""
    app, _ = _make_app(test_db)
    iv = assert_clean(client.post(f"/api/applications/{app.id}/interviews",
                                  json={"what": "Screen"}), 201).json()
    r = assert_clean(client.patch(f"/api/applications/interviews/{iv['id']}",
                                  json={"when_at": "2026-09-09T14:00"}), 200).json()
    assert r["when_at"].startswith("2026-09-09T14:00")
    r2 = assert_clean(client.patch(f"/api/applications/interviews/{iv['id']}",
                                   json={"when_at": ""}), 200).json()
    assert r2["when_at"] is None


def test_patch_interview_unparseable_when_at_clears_it(client, test_db):
    app, _ = _make_app(test_db)
    iv = assert_clean(client.post(f"/api/applications/{app.id}/interviews",
                                  json={"what": "Screen", "when_at": "2026-09-09T14:00"}), 201).json()
    r = assert_clean(client.patch(f"/api/applications/interviews/{iv['id']}",
                                  json={"when_at": "next tuesday"}), 200).json()
    assert r["when_at"] is None


def test_patch_interview_updates_the_text_fields(client, test_db):
    app, _ = _make_app(test_db)
    iv = assert_clean(client.post(f"/api/applications/{app.id}/interviews",
                                  json={"what": "Screen"}), 201).json()
    r = assert_clean(client.patch(f"/api/applications/interviews/{iv['id']}", json={
        "what": "Onsite", "where_text": "London", "status": "done",
        "prep": "read the S-1"}), 200).json()
    assert r["what"] == "Onsite" and r["where_text"] == "London"
    assert r["status"] == "done" and r["prep"] == "read the S-1"


def test_delete_interview_twice_is_404_the_second_time(client, test_db):
    app, _ = _make_app(test_db)
    iv = assert_clean(client.post(f"/api/applications/{app.id}/interviews",
                                  json={"what": "Screen"}), 201).json()
    assert_clean(client.delete(f"/api/applications/interviews/{iv['id']}"), 200)
    assert_clean(client.delete(f"/api/applications/interviews/{iv['id']}"), 404)


# ── GET /{app_id}/prep ───────────────────────────────────────────────────────

def test_prep_bundle_assembles_role_resume_posting_and_ask(client, test_db):
    app, job = _make_app(test_db, company="Acme", title="Senior PM",
                         url="https://e.com/j", location="London", remote=True,
                         salary_min=100000, salary_max=140000)
    app.notes = "referred   by   Dana"
    app.cv_version_used = "PM"
    test_db.commit()
    make_resume(test_db, name="PM", json_data={
        "header": {"name": "A Candidate"}, "summary": "Ten years of product."})
    set_setting(test_db, "prep_ask", "Give me five questions.")
    text = assert_clean(client.get(f"/api/applications/{app.id}/prep"), 200).json()["text"]
    assert text.startswith("# Senior PM at Acme")
    assert "- Location: London (remote)" in text
    assert "- Listed salary: $100K–$140K" in text
    assert "- Posting: https://e.com/j" in text
    assert "- Stage: Applied" in text
    assert "- My notes on this application: referred by Dana" in text
    assert "## My résumé — PM" in text
    assert "## The posting" in text
    assert "Give me five questions." in text


def test_prep_bundle_lists_booked_interviews_with_their_prep_notes(client, test_db):
    from backend.models.db import Interview
    app, _ = _make_app(test_db)
    test_db.add(Interview(application_id=app.id, what="Hiring manager",
                          when_at=datetime(2026, 9, 9, 14, 0, tzinfo=timezone.utc),
                          where_text="Zoom", status="scheduled", prep="read the S-1"))
    test_db.add(Interview(application_id=app.id, what="Panel", status="done"))
    test_db.commit()
    text = assert_clean(client.get(f"/api/applications/{app.id}/prep"), 200).json()["text"]
    assert "- Interviews booked:" in text
    assert "Hiring manager — Wed 09 Sep 2026, 14:00 · Zoom (scheduled)" in text
    assert "prep note: read the S-1" in text
    assert "Panel — unscheduled (done)" in text


def test_prep_bundle_prefers_the_tailored_copy_over_the_base(client, test_db):
    app, job = _make_app(test_db)
    app.cv_version_used = "PM"
    test_db.commit()
    make_resume(test_db, name="PM", json_data={"summary": "the base"})
    make_resume(test_db, name="PM — Acme", is_base=False, job_id=job.id,
                json_data={"summary": "the tailored copy"})
    text = assert_clean(client.get(f"/api/applications/{app.id}/prep"), 200).json()["text"]
    assert "## My résumé — PM — Acme" in text
    assert "the tailored copy" in text


def test_prep_bundle_demotes_the_resume_headings(client, test_db):
    """`_flatten_resume` emits its own `## Summary`; inside the bundle it has to
    read as part of the résumé, not as a sibling of "The posting"."""
    app, _ = _make_app(test_db)
    app.cv_version_used = "PM"
    test_db.commit()
    make_resume(test_db, name="PM", json_data={"summary": "Ten years."})
    text = assert_clean(client.get(f"/api/applications/{app.id}/prep"), 200).json()["text"]
    assert "### Summary" in text
    assert "\n## Summary" not in text


def test_prep_bundle_says_so_when_the_resume_is_unavailable(client, test_db):
    app, _ = _make_app(test_db)
    text = assert_clean(client.get(f"/api/applications/{app.id}/prep"), 200).json()["text"]
    assert "[résumé content unavailable]" in text


def test_prep_bundle_survives_a_resume_that_cannot_be_flattened(client, test_db, monkeypatch):
    import backend.analyzer.cv_scorer as scorer
    app, _ = _make_app(test_db)
    app.cv_version_used = "PM"
    test_db.commit()
    make_resume(test_db, name="PM", json_data={"summary": "x"})

    def _boom(data):
        raise ValueError("bad shape")

    monkeypatch.setattr(scorer, "_flatten_resume", _boom)
    text = assert_clean(client.get(f"/api/applications/{app.id}/prep"), 200).json()["text"]
    assert "[résumé content unavailable]" in text


def test_prep_bundle_says_so_when_no_posting_text_was_captured(client, test_db):
    app, _ = _make_app(test_db, description=None)
    text = assert_clean(client.get(f"/api/applications/{app.id}/prep"), 200).json()["text"]
    assert "[no posting text was captured]" in text


def test_prep_bundle_prefers_the_cached_page_over_the_description(client, test_db):
    app, job = _make_app(test_db, description="the short description")
    job.cached_page_text = "the full cached posting"
    test_db.commit()
    text = assert_clean(client.get(f"/api/applications/{app.id}/prep"), 200).json()["text"]
    assert "the full cached posting" in text
    assert "the short description" not in text


def test_prep_include_setting_drops_the_optional_sections(client, test_db):
    app, _ = _make_app(test_db, description="posting body")
    app.notes = "private note"
    app.cv_version_used = "PM"
    test_db.commit()
    make_resume(test_db, name="PM", json_data={"summary": "x"})
    # A blank value falls back to the default trio, so name a section that does
    # not exist to switch all three off.
    set_setting(test_db, "prep_include", "none")
    text = assert_clean(client.get(f"/api/applications/{app.id}/prep"), 200).json()["text"]
    assert "## My résumé" not in text
    assert "## The posting" not in text
    assert "private note" not in text
    assert "## What I need from you" in text


def test_prep_include_blank_falls_back_to_the_default_trio(client, test_db):
    app, _ = _make_app(test_db, description="posting body")
    set_setting(test_db, "prep_include", "")
    text = assert_clean(client.get(f"/api/applications/{app.id}/prep"), 200).json()["text"]
    assert "## My résumé" in text and "## The posting" in text


def test_prep_bundle_defaults_the_ask_when_the_setting_is_blank(client, test_db):
    app, _ = _make_app(test_db)
    set_setting(test_db, "prep_ask", "   ")
    text = assert_clean(client.get(f"/api/applications/{app.id}/prep"), 200).json()["text"]
    assert text.rstrip().endswith("Prepare me for this interview.")


def test_prep_bundle_names_an_untitled_posting_unknown(client, test_db):
    """`Application.job_id` is NOT NULL, so the job is always there; a job with
    no title/company is what the "Unknown" fallbacks actually guard against."""
    app, _ = _make_app(test_db, company="", title="")
    text = assert_clean(client.get(f"/api/applications/{app.id}/prep"), 200).json()["text"]
    assert text.startswith("# Unknown Role at Unknown Company")


@pytest.mark.parametrize("lo,hi,expected", [
    (100000, 140000, "$100K–$140K"),
    (120000, 120000, "$120K"),
    (None, 90000, "$90K"),
    (90000, None, "$90K"),
])
def test_prep_bundle_formats_the_salary_band(client, test_db, lo, hi, expected):
    app, _ = _make_app(test_db, salary_min=lo, salary_max=hi)
    text = assert_clean(client.get(f"/api/applications/{app.id}/prep"), 200).json()["text"]
    assert "- Listed salary: " + expected in text


def test_prep_bundle_omits_the_salary_line_when_there_is_none(client, test_db):
    app, _ = _make_app(test_db, salary_min=None, salary_max=None)
    text = assert_clean(client.get(f"/api/applications/{app.id}/prep"), 200).json()["text"]
    assert "Listed salary" not in text
