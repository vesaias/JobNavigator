"""Pytest fixtures for JobNavigator tests."""
import os
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock

# Force SQLite for tests before any imports that touch the engine
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")


def pytest_configure(config):
    """Register markers here too — the container runs pytest from /app, where the
    repo's pytest.ini is not mounted."""
    config.addinivalue_line(
        "markers",
        "live: hits the running stack over HTTP (read-only); auto-skips when unreachable",
    )


# ── Anthropic mock fixtures ───────────────────────────────────────────────

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


# ── DB + TestClient fixtures ─────────────────────────────────────────────

@pytest.fixture
def test_db():
    """In-memory SQLite DB with all tables; rebinds the shared SessionLocal so already-imported modules hit the test DB."""
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool
    import backend.models.db as db_mod
    from backend.models.db import Base

    # Patch Uuid.bind_processor once so string-shaped UUID binds work under SQLite.
    import uuid as _uuid
    from sqlalchemy.sql.sqltypes import Uuid as _SAUuid
    if not getattr(_SAUuid, "_jn_test_patched", False):
        _orig_bind = _SAUuid.bind_processor

        def _lenient_bind(self, dialect):
            character_based = (
                not dialect.supports_native_uuid or not self.native_uuid
            )
            if character_based and self.as_uuid:
                def process(value):
                    if value is None:
                        return None
                    if isinstance(value, _uuid.UUID):
                        return value.hex
                    return _uuid.UUID(str(value)).hex
                return process
            return _orig_bind(self, dialect)

        _SAUuid.bind_processor = _lenient_bind
        _SAUuid._jn_test_patched = True

    # StaticPool keeps a single shared connection so all sessions see the same DB.
    test_engine = create_engine(
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
        Base.metadata.create_all(test_engine)
    finally:
        for col, sd in stashed:
            col.server_default = sd

    # Rebind the shared SessionLocal (and engine ref) so top-level importers hit the test DB.
    original_engine = db_mod.engine
    original_bind = db_mod.SessionLocal.kw.get("bind")
    db_mod.engine = test_engine
    db_mod.SessionLocal.configure(bind=test_engine)

    session = db_mod.SessionLocal()
    try:
        yield session
    finally:
        session.close()
        db_mod.SessionLocal.configure(bind=original_bind)
        db_mod.engine = original_engine
        test_engine.dispose()


@pytest.fixture
def api_client(test_db, monkeypatch):
    """FastAPI TestClient for endpoint tests; test_db already rebound SessionLocal, so this only stubs lifespan deps and the scheduler."""
    from fastapi.testclient import TestClient

    # Pre-import backend.main + heavy modules so lazy imports capture bindings before monkeypatches.
    import backend.main  # noqa: F401
    import backend.scraper.sources.linkedin_extension  # noqa: F401

    # Stub the lifespan dependencies so TestClient startup is a no-op.
    import backend.main as main_mod
    monkeypatch.setattr(main_mod, "create_tables", lambda: None)
    monkeypatch.setattr(main_mod, "run_seeds", lambda: None)
    monkeypatch.setattr(main_mod, "cleanup_stale_runs", lambda: None)
    # Prevent the real scheduler from booting.
    import backend.scheduler as sched_mod
    monkeypatch.setattr(sched_mod, "configure_scheduler", lambda: None)
    fake_scheduler = MagicMock()
    fake_scheduler.start = MagicMock()
    fake_scheduler.shutdown = MagicMock()
    monkeypatch.setattr(sched_mod, "scheduler", fake_scheduler)

    # Override get_db so route handlers share the test DB session.
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
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)


# ── httpx + Telegram mock fixtures ───────────────────────────────────────

@pytest.fixture
def mock_httpx(monkeypatch):
    """Replace httpx.AsyncClient with a MagicMock returning a canned response; returns {"client", "response"} for inspection."""
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
    """Replace the Telegram notifier's httpx call with a recorder; returns a list of {"url", "json"} dicts."""
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
