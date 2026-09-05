"""Shared helpers for the R4-T1 backend contract + robustness pass.

`client` is the conftest `api_client` with two differences:
  * a known `dashboard_api_key` is seeded and sent on every request;
  * `raise_server_exceptions=False`, so an unhandled handler exception comes back
    as a 500 response we can assert on instead of blowing up the test.

Every contract test ends with `assert_clean(resp, ...)`: the status must be one
of the expected ones, must never be 500, and the body must not carry a stack
trace or a file path from inside the container.
"""
import json
import uuid
from unittest.mock import MagicMock

import pytest

# Text that must never appear in a response body reaching the browser.
LEAK_MARKERS = (
    "Traceback (most recent call last)",
    "/app/backend/",
    "site-packages",
    'File "',
    "sqlalchemy.exc",
    "psycopg2.errors",
    "InterfaceError",
)


API_KEY = "r4-test-key"


@pytest.fixture
def client(test_db, monkeypatch):
    """TestClient carrying a valid API key, with server exceptions surfaced as 500s.

    The key is a real (non-empty) one on purpose: the lifespan overwrites an
    empty `dashboard_api_key` with INITIAL_API_KEY, so "first-run mode" is not
    reachable through TestClient startup.
    """
    from fastapi.testclient import TestClient
    from backend.models.db import Setting

    test_db.add(Setting(key="dashboard_api_key", value=API_KEY))
    test_db.commit()

    import backend.main  # noqa: F401
    import backend.scraper.sources.linkedin_extension  # noqa: F401

    import backend.main as main_mod
    monkeypatch.setattr(main_mod, "create_tables", lambda: None)
    monkeypatch.setattr(main_mod, "run_seeds", lambda: None)
    monkeypatch.setattr(main_mod, "cleanup_stale_runs", lambda: None)

    import backend.scheduler as sched_mod
    monkeypatch.setattr(sched_mod, "configure_scheduler", lambda: None)
    fake_scheduler = MagicMock()
    fake_scheduler.start = MagicMock()
    fake_scheduler.shutdown = MagicMock()
    monkeypatch.setattr(sched_mod, "scheduler", fake_scheduler)

    import backend.models.db as db_mod

    def override_get_db():
        s = db_mod.SessionLocal()
        try:
            yield s
        finally:
            s.close()

    from backend.main import app
    from backend.models.db import get_db
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app, raise_server_exceptions=False) as c:
            c.headers.update({"X-API-Key": API_KEY})
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture(autouse=True)
def _no_outbound(monkeypatch):
    """Neutralise the fire-and-forget network work these handlers queue.

    TestClient runs BackgroundTasks inline, so without this every application
    create pays a real 6 s page fetch and an H-1B lookup.
    """
    async def _noop(*a, **k):
        return None

    import backend.api.routes_applications as ra
    import backend.api.routes_companies as rc
    import backend.analyzer.h1b_checker as h1b

    monkeypatch.setattr(ra, "_cache_job_page", _noop, raising=False)
    monkeypatch.setattr(rc, "_fire_h1b_async", _noop, raising=False)
    monkeypatch.setattr(h1b, "fetch_h1b_for_company_id", _noop, raising=False)
    monkeypatch.setattr(h1b, "refresh_all_h1b", _noop, raising=False)
    monkeypatch.setattr(h1b, "check_job_h1b", _noop, raising=False)

    async def _no_h1b(db, name, allow_live=False):
        return None
    monkeypatch.setattr(h1b, "resolve_company_h1b", _no_h1b, raising=False)


@pytest.fixture(autouse=True)
def _clear_running_state():
    """Never let one test's in-memory run leak into the next."""
    import backend.job_monitor as jm
    jm._running.clear()
    yield
    jm._running.clear()


def assert_clean(resp, *allowed):
    """Status is one of `allowed`, is never 500, and the body leaks no internals."""
    body = resp.text or ""
    assert resp.status_code != 500, f"500 leaked: {body[:400]}"
    for marker in LEAK_MARKERS:
        assert marker not in body, f"internal detail {marker!r} in body: {body[:400]}"
    if allowed:
        assert resp.status_code in allowed, \
            f"expected {allowed}, got {resp.status_code}: {body[:400]}"
    return resp


def assert_no_leak(resp):
    """Weaker guard for endpoints whose status we deliberately do not pin."""
    body = resp.text or ""
    for marker in LEAK_MARKERS:
        assert marker not in body, f"internal detail {marker!r} in body: {body[:400]}"
    return resp


# ── Payload generators ───────────────────────────────────────────────────────

MISSING_UUID = "00000000-0000-0000-0000-000000000000"
MALFORMED_IDS = ["abc", "not-a-uuid", "1", "%20", "../etc/passwd", "éè", "0" * 100]

EMOJI = "\U0001f680 Señor PM — 中文 \U0001f9e0"


def big_string(mb=10):
    """A string of roughly `mb` megabytes."""
    return "x" * (mb * 1024 * 1024)


def make_job(db, **kw):
    from backend.models.db import Job
    from backend.scraper._shared.dedup import make_external_id
    company = kw.pop("company", "Acme")
    title = kw.pop("title", "Senior PM")
    url = kw.pop("url", f"https://x.com/jobs/{uuid.uuid4().hex[:8]}")
    job = Job(
        external_id=kw.pop("external_id", make_external_id(company, title, url)),
        company=company, title=title, url=url,
        source=kw.pop("source", "test"), status=kw.pop("status", "new"),
        **kw,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def make_company(db, name="Acme", **kw):
    from backend.models.db import Company
    c = Company(name=name, **kw)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def make_search(db, name="S1", **kw):
    from backend.models.db import Search
    s = Search(name=name, **kw)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def make_resume(db, name="Base", is_base=True, **kw):
    from backend.models.db import Resume
    r = Resume(name=name, is_base=is_base, json_data=kw.pop("json_data", {"header": {"name": "A"}}), **kw)
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def make_persona(db):
    from backend.models.db import Persona
    p = db.query(Persona).filter(Persona.id == 1).first()
    if not p:
        p = Persona(id=1, contact={}, work_auth={}, demographics={},
                    compensation={}, preferences={}, resume_content={}, qa_bank=[])
        db.add(p)
        db.commit()
        db.refresh(p)
    return p


def set_setting(db, key, value):
    from backend.models.db import Setting
    row = db.query(Setting).filter(Setting.key == key).first()
    if row:
        row.value = value if isinstance(value, str) else json.dumps(value)
    else:
        db.add(Setting(key=key, value=value if isinstance(value, str) else json.dumps(value)))
    db.commit()
