"""Pytest fixtures for JobNavigator tests."""
import os
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock

# Force SQLite for tests before any imports that touch the engine
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
# MT-2: a query on an account-owned model without an account context raises in tests
# instead of falling back to the owner. MT_STRICT=0 turns that off for a local run.
os.environ.setdefault("MT_STRICT", "1")
# The app's lifespan must not start the runner sync loop: in a live backend container
# (JN_RUNNER_MANAGEMENT=1) it would read the test DB from a thread, hang the shutdown
# and send the test accounts' providers to the real runner manager. Unset, as in CI:
# the backend then defaults to off and the manager's own tests to on.
os.environ.pop("JN_RUNNER_MANAGEMENT", None)


def pytest_configure(config):
    """Register markers here too — the container runs pytest from /app, where the
    repo's pytest.ini is not mounted."""
    config.addinivalue_line(
        "markers",
        "live: hits the running stack over HTTP (read-only); auto-skips when unreachable",
    )
    config.addinivalue_line(
        "markers",
        "mt_no_owner: test_db creates no owner account and runs the test unscoped (MT-1 migration tests)",
    )
    config.addinivalue_line(
        "markers",
        "h1b_prefetch: keep the scrapers' real H-1B prefetch (stubbed out by default: no network)",
    )


@pytest.fixture(autouse=True)
def _no_h1b_prefetch(request, monkeypatch):
    """S2-01: every ingest loop now resolves its new companies' H-1B data up front
    (`prefetch_h1b`). Source tests that stub `analyze_inline` never reached MyVisaJobs
    before; keep it that way. Tests marked `h1b_prefetch` get the real one."""
    if request.node.get_closest_marker("h1b_prefetch"):
        yield
        return

    async def _none(names, slugs=None, ttl_days=None):
        return 0

    monkeypatch.setattr("backend.scraper._shared.analysis.prefetch_company_h1b", _none)
    yield


@pytest.fixture(autouse=True)
def _clean_auth_throttle():
    """The per-IP auth failure counter (R4-T5-06) is process-global by design, so a test
    that posts wrong keys would otherwise lock out the tests that follow it."""
    import sys

    def _reset():
        mod = sys.modules.get("backend.main")
        if mod is not None:
            mod._reset_auth_throttle()
        auth = sys.modules.get("backend.accounts.auth")
        if auth is not None:
            auth.reset_pin_cooldowns()   # MT-10 per-account PIN cooldowns
            auth.forget_touches()        # MT-11 last_active_at throttle
            auth.invalidate_accounts_cache()   # QA F9 T6-02
        tg = sys.modules.get("backend.notifier.telegram")
        if tg is not None:
            tg.reset_link_state()        # QA F8: link codes + per-chat/global wrong-code counters

    _reset()
    yield
    _reset()


@pytest.fixture(autouse=True)
def _no_reused_fetches():
    """Cross-run fetch reuse (`targets.shared_fetch_for`) keeps recent fetches in-process;
    one test's fake postings must never reach the next test's run."""
    from backend.scraper.targets import reset_shared_fetches
    reset_shared_fetches()
    yield
    reset_shared_fetches()


@pytest.fixture(autouse=True)
def _mt_unscoped_by_default():
    """Tests that build their own throwaway engine (no accounts table, no owner) run
    unscoped, as before MT-2. The shared `test_db` fixture switches back to scoped and
    runs the test as its owner account."""
    from backend.accounts.context import unscoped
    with unscoped():
        yield


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
        resp.content = [MagicMock(type="text", text=text)]
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
def test_db(request):
    """In-memory SQLite DB with all tables; rebinds the shared SessionLocal so already-imported modules hit the test DB.

    MT-2: the DB gets an owner account and the test runs in its account context, as every
    request and background run does in production. `@pytest.mark.mt_no_owner` skips both
    and runs the test inside `unscoped()` instead."""
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

    from backend.accounts import context as mt
    session = db_mod.SessionLocal()
    if request.node.get_closest_marker("mt_no_owner"):
        account_ctx = mt.unscoped()
    else:
        owner = db_mod.Account(name="Owner", role="owner", color=db_mod.ACCOUNT_COLORS[0])
        session.add(owner)
        session.commit()
        mt.remember_owner(test_engine, owner.id)
        account_ctx = mt.use_account(owner.id)
    scoped_token = mt._unscoped.set(False)  # undo _mt_unscoped_by_default
    try:
        with account_ctx:
            yield session
    finally:
        mt._unscoped.reset(scoped_token)
        session.close()
        db_mod.SessionLocal.configure(bind=original_bind)
        db_mod.engine = original_engine
        test_engine.dispose()


@pytest.fixture
def no_account_ctx(test_db):
    """QA F4 / R1-09: `test_db`, but the test body runs with NO account context (not the
    owner, not unscoped, no owner unlock) — exactly what APScheduler or a fresh task sees.
    In strict mode any query on account-owned rows that its entry point did not scope
    raises, so background entry points tested here must set their own context."""
    from backend.accounts.context import no_account_context
    with no_account_context():
        yield test_db


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


# SQLite gives a column typed UUID NUMERIC affinity, so a random hex id made only of digits
# and one 'e' (e.g. '1234e567...') is stored as a float and reads back as inf. CHAR(32)
# gives it TEXT affinity, which is what the hex strings are.
from sqlalchemy.ext.compiler import compiles as _compiles  # noqa: E402
from sqlalchemy.dialects.postgresql import UUID as _PGUUID  # noqa: E402
from sqlalchemy.sql.sqltypes import Uuid as _SAUuidType  # noqa: E402


@_compiles(_PGUUID, "sqlite")
@_compiles(_SAUuidType, "sqlite")
def _uuid_as_text_on_sqlite(type_, compiler, **kw):
    return "CHAR(32)"
