"""Pytest fixtures for JobNavigator tests."""
import os
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock

# Force SQLite for tests before any imports that touch the engine
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")


# ── Anthropic mock fixtures (existing — kept as-is) ──────────────────────────

@pytest.fixture
def mock_anthropic_response():
    """Factory for a fake anthropic.messages.create response."""
    def _make(text: str = '{"scores":{"CV":75},"best_cv":"CV"}',
              input_tokens: int = 1000,
              output_tokens: int = 50,
              cache_read: int = 0,
              cache_write: int = 0):
        resp = MagicMock()
        resp.content = [MagicMock(text=text)]
        resp.usage = MagicMock(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_input_tokens=cache_read,
            cache_creation_input_tokens=cache_write,
        )
        return resp
    return _make


@pytest.fixture
def mock_anthropic_client(mock_anthropic_response, monkeypatch):
    """Replace anthropic.AsyncAnthropic with a mock that returns a canned response."""
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=mock_anthropic_response())

    def _fake_ctor(*args, **kwargs):
        return client

    import anthropic
    monkeypatch.setattr(anthropic, "AsyncAnthropic", _fake_ctor)
    return client


# ── NEW: DB + TestClient fixtures ────────────────────────────────────────────

@pytest.fixture
def test_db():
    """In-memory SQLite DB with all models' tables created.

    Yields a Session. Tests can add/query rows directly. Each test gets a fresh DB.

    Notes on SQLite compatibility:
    - PostgreSQL UUID columns are automatically mapped to CHAR(32) by SQLAlchemy under SQLite.
    - Job.short_id uses server_default=text("nextval('jobs_short_id_seq')") which SQLite
      cannot parse; we strip server_defaults for CREATE TABLE via a DDL event listener.
    """
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.schema import CreateTable
    from backend.models.db import Base

    # StaticPool keeps a single shared connection so all sessions see the same
    # in-memory SQLite database.
    from sqlalchemy.pool import StaticPool
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Strip PG-specific server_defaults that SQLite cannot parse (e.g. nextval()).
    stashed = []
    for table in Base.metadata.tables.values():
        for col in table.columns:
            if col.server_default is not None:
                stashed.append((col, col.server_default))
                col.server_default = None
    try:
        Base.metadata.create_all(engine)
    finally:
        for col, sd in stashed:
            col.server_default = sd

    TestSession = sessionmaker(bind=engine)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def api_client(test_db, monkeypatch):
    """FastAPI TestClient with SessionLocal patched to use test_db's engine.

    Use for any test that hits an HTTP endpoint. The app lifespan (which runs
    Postgres-specific create_tables/seed/migrations) is bypassed — the fixture
    provides its own SQLite schema via test_db.
    """
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker

    # Import backend.main and its transitive dependencies FIRST so that any
    # module-level `from backend.models.db import SessionLocal` binds to the
    # production Postgres sessionmaker (not the test sessionmaker we install
    # below). Otherwise any sibling module imported lazily through the app
    # boot chain would permanently capture the test sessionmaker and break
    # subsequent tests.
    import backend.main  # noqa: F401
    import backend.scraper.sources.linkedin_extension  # noqa: F401

    # Point backend.models.db.SessionLocal at the test engine
    test_sessionmaker = sessionmaker(bind=test_db.get_bind())

    import backend.models.db as db_mod
    monkeypatch.setattr(db_mod, "SessionLocal", test_sessionmaker)

    # Stub the lifespan dependencies so TestClient startup is a no-op.
    import backend.main as main_mod
    monkeypatch.setattr(main_mod, "create_tables", lambda: None)
    monkeypatch.setattr(main_mod, "run_seeds", lambda: None)
    monkeypatch.setattr(main_mod, "cleanup_stale_runs", lambda: None)
    monkeypatch.setattr(main_mod, "SessionLocal", test_sessionmaker)
    # Prevent the real scheduler from booting.
    import backend.scheduler as sched_mod
    monkeypatch.setattr(sched_mod, "configure_scheduler", lambda: None)
    fake_scheduler = MagicMock()
    fake_scheduler.start = MagicMock()
    fake_scheduler.shutdown = MagicMock()
    monkeypatch.setattr(sched_mod, "scheduler", fake_scheduler)

    # Override the FastAPI get_db generator dependency
    def override_get_db():
        s = test_sessionmaker()
        try:
            yield s
        finally:
            s.close()

    from backend.main import app
    from backend.models.db import get_db
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)


# ── NEW: httpx + Telegram mock fixtures ──────────────────────────────────────

@pytest.fixture
def mock_httpx(monkeypatch):
    """Replace httpx.AsyncClient with a MagicMock that returns a canned response.

    Returns a dict: {"client": <mock>, "response": <mock>} so tests can inspect or
    reconfigure behavior.
    """
    resp = MagicMock()
    resp.status_code = 200
    resp.json = MagicMock(return_value={})
    resp.text = ""
    resp.raise_for_status = MagicMock()

    client = MagicMock()
    client.get = AsyncMock(return_value=resp)
    client.post = AsyncMock(return_value=resp)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: client)
    return {"client": client, "response": resp}


@pytest.fixture
def mock_telegram(monkeypatch):
    """Replace the Telegram notifier's httpx call with a recorder.

    Returns a list of {"url", "json"} dicts captured during the test.
    """
    sent = []

    async def fake_post(url, json=None, **kwargs):
        sent.append({"url": url, "json": json})
        resp = MagicMock()
        resp.status_code = 200
        resp.json = MagicMock(return_value={"ok": True})
        resp.raise_for_status = MagicMock()
        return resp

    client = MagicMock()
    client.post = AsyncMock(side_effect=fake_post)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: client)
    return sent
