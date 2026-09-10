"""R4 · connection-pool safety for background work.

The incident: the Feed was asked to score ~80 jobs. Each job became its own
`launch_background("analyze_job", …)` task, each task opened a session *before*
waiting on the scoring gate, and each then held that session across the LLM
call. Thirty of them drained the QueuePool (size 10 + overflow 20); everything
else — `/health` included — then blocked for the full 30 s pool_timeout and the
box climbed to 2.5 GB.

Two invariants are pinned here:

  1. Concurrency is bounded *before* a connection is taken: launching 30 fake
     scoring tasks never has more than `scoring_max_concurrent` sessions open,
     and an HTTP request stays answerable throughout.
  2. No session is open while the LLM call is awaited — asserted from inside
     the mocked call itself, so it cannot pass by accident.

Sessions are counted by wrapping `SessionLocal`, which every worker goes
through; that is a truer measure than pool internals under the test suite's
StaticPool.
"""
import asyncio

import pytest

from backend.tests.r4_support import client  # noqa: F401


class SessionCounter:
    """Counts sessions that are currently open, and the high-water mark."""

    def __init__(self):
        self.open = 0
        self.peak = 0

    def install(self, monkeypatch, *modules):
        """Wrap the `SessionLocal` each named module holds.

        Deliberately not `backend.models.db.SessionLocal` itself: the test DB
        fixture rebinds that object at teardown, and what matters here is the
        worker's own sessions, not the request-scoped ones.
        """
        import backend.models.db as db_mod
        real = db_mod.SessionLocal

        def _factory(*a, **kw):
            session = real(*a, **kw)
            self.open += 1
            self.peak = max(self.peak, self.open)
            real_close = session.close

            def _close(*ca, **ckw):
                if not getattr(session, "_jn_counted_closed", False):
                    session._jn_counted_closed = True
                    self.open -= 1
                return real_close(*ca, **ckw)

            session.close = _close
            return session

        for mod in modules:
            monkeypatch.setattr(mod, "SessionLocal", _factory, raising=False)
        return self


@pytest.fixture
def counter():
    return SessionCounter()


def _make_jobs(test_db, n):
    import uuid
    from sqlalchemy import null as sa_null
    from backend.models.db import Job

    ids = []
    for i in range(n):
        # cv_scores=NULL so the IS NULL branch of unscored_filter() matches.
        job = Job(id=uuid.uuid4(), external_id=f"pool-{i}", content_hash=f"pool-h-{i}",
                  company="Acme", title=f"Role {i}", url=f"https://x.test/{i}",
                  description="A job description long enough to be scoreable. " * 5,
                  status="new", cv_scores=sa_null())
        test_db.add(job)
        ids.append(str(job.id))
    test_db.commit()
    return ids


def _seed_resume(test_db):
    import uuid
    from backend.models.db import Resume

    test_db.add(Resume(id=uuid.uuid4(), name="PM", is_base=True,
                       json_data={"summary": "Ten years of product work.",
                                  "skills": {"core": ["Python"]}}))
    test_db.commit()


@pytest.fixture
def _fresh_limiters():
    """The gates are process-wide and cached; give each test its own."""
    import backend.job_monitor as jm
    jm.reset_limiter()
    yield
    jm.reset_limiter()


# ══ 1. Bounded concurrency, and the pool is never drained ════════════════════

@pytest.mark.asyncio
async def test_thirty_scoring_tasks_keep_open_sessions_under_the_gate(
        client, test_db, monkeypatch, counter, _fresh_limiters):
    """30 queued scoring tasks, LLM mocked with a sleep: never more sessions
    open at once than `scoring_max_concurrent`, and /health keeps answering."""
    from backend.models.db import Setting
    import backend.job_monitor as jm
    import backend.analyzer.cv_scorer as scorer

    test_db.add(Setting(key="scoring_max_concurrent", value="3"))
    test_db.commit()
    _seed_resume(test_db)
    job_ids = _make_jobs(test_db, 30)

    counter.install(monkeypatch, scorer)

    in_llm = {"now": 0, "peak": 0}

    async def fake_call_llm(*a, **kw):
        in_llm["now"] += 1
        in_llm["peak"] = max(in_llm["peak"], in_llm["now"])
        try:
            await asyncio.sleep(0.02)
            return {"text": '{"scores": {"PM": 71}, "best_cv": "PM"}',
                    "usage": {"input_tokens": 10, "output_tokens": 5,
                              "cache_read_tokens": 0, "cache_write_tokens": 0}}
        finally:
            in_llm["now"] -= 1

    monkeypatch.setattr(scorer, "call_llm", fake_call_llm)
    monkeypatch.setattr(scorer, "log_llm_call", lambda **kw: None)

    for i, jid in enumerate(job_ids):
        jm.launch_background("analyze_job", scorer.score_single_job, trigger="manual",
                             scope_key=f"pool-{i}",
                             func_kwargs={"job_id": jid, "depth": "light"})

    # …and the app answers while all 30 are queued.
    assert client.get("/health").status_code == 200

    deadline = asyncio.get_running_loop().time() + 20
    while any(r.job_type == "analyze_job" for r in jm._running.values()):
        assert asyncio.get_running_loop().time() < deadline, "scoring tasks never drained"
        await asyncio.sleep(0.02)

    assert client.get("/health").status_code == 200
    assert in_llm["peak"] <= 3, f"gate leaked: {in_llm['peak']} concurrent LLM calls"
    # The gate is taken before the first session is opened, so open sessions
    # track the gate, not the number of queued tasks.
    assert counter.peak <= 3, f"{counter.peak} sessions open at once (limit 3)"
    assert counter.open == 0, "a worker leaked a session"


@pytest.mark.asyncio
async def test_the_gate_is_taken_before_a_session_is_opened(
        client, test_db, monkeypatch, counter, _fresh_limiters):
    """A task waiting for its turn holds no connection at all."""
    from backend.models.db import Setting
    import backend.job_monitor as jm
    import backend.analyzer.cv_scorer as scorer

    test_db.add(Setting(key="scoring_max_concurrent", value="1"))
    test_db.commit()
    _seed_resume(test_db)
    job_ids = _make_jobs(test_db, 5)

    counter.install(monkeypatch, scorer)
    release = asyncio.Event()
    entered = asyncio.Event()

    async def fake_call_llm(*a, **kw):
        entered.set()
        await release.wait()
        return {"text": '{"scores": {"PM": 60}, "best_cv": "PM"}', "usage": {}}

    monkeypatch.setattr(scorer, "call_llm", fake_call_llm)
    monkeypatch.setattr(scorer, "log_llm_call", lambda **kw: None)

    for i, jid in enumerate(job_ids):
        jm.launch_background("analyze_job", scorer.score_single_job, trigger="manual",
                             scope_key=f"gate-{i}",
                             func_kwargs={"job_id": jid, "depth": "light"})

    await asyncio.wait_for(entered.wait(), timeout=5)
    # One task is mid-LLM and four are queued behind the gate: no session at all
    # should be open (the LLM phase holds none either).
    assert counter.open == 0, f"{counter.open} sessions open while 4 tasks are queued"
    release.set()

    deadline = asyncio.get_running_loop().time() + 20
    while any(r.job_type == "analyze_job" for r in jm._running.values()):
        assert asyncio.get_running_loop().time() < deadline, "scoring tasks never drained"
        await asyncio.sleep(0.02)


# ══ 2. No session is open across the LLM call ════════════════════════════════

@pytest.mark.asyncio
async def test_no_session_is_open_while_the_llm_call_is_awaited(
        test_db, monkeypatch, counter, _fresh_limiters):
    """Asserted from inside the mock, where a held connection cannot hide."""
    import backend.analyzer.cv_scorer as scorer

    _seed_resume(test_db)
    job_id = _make_jobs(test_db, 1)[0]
    counter.install(monkeypatch, scorer)

    seen = {}

    async def fake_call_llm(*a, **kw):
        seen["open_during_llm"] = counter.open
        await asyncio.sleep(0)
        return {"text": '{"scores": {"PM": 80}, "best_cv": "PM"}', "usage": {}}

    monkeypatch.setattr(scorer, "call_llm", fake_call_llm)
    monkeypatch.setattr(scorer, "log_llm_call", lambda **kw: None)

    await scorer.score_single_job(job_id, depth="light")

    assert seen["open_during_llm"] == 0, (
        f"{seen['open_during_llm']} session(s) held across the LLM call"
    )
    assert counter.open == 0
    # …and the result still landed.
    test_db.expire_all()
    from backend.models.db import Job
    job = test_db.query(Job).filter(Job.id == job_id).first()
    assert (job.cv_scores or {}).get("PM") == 80


@pytest.mark.asyncio
async def test_batch_pipeline_holds_no_session_across_the_llm_call(
        test_db, monkeypatch, counter, _fresh_limiters):
    """analyze_unscored_jobs used to keep one session open for a whole batch,
    LLM calls included."""
    import backend.analyzer.cv_scorer as scorer
    from backend.models.db import Job

    from backend.models.db import Setting
    _seed_resume(test_db)
    _make_jobs(test_db, 4)
    for job in test_db.query(Job).all():
        job.saved = True
    test_db.add(Setting(key="fit_score_threshold", value="999"))  # no Telegram round trip
    test_db.commit()

    counter.install(monkeypatch, scorer)
    peaks = []

    async def fake_call_llm(*a, **kw):
        peaks.append(counter.open)
        await asyncio.sleep(0)
        return {"text": '{"scores": {"PM": 65}, "best_cv": "PM"}', "usage": {}}

    monkeypatch.setattr(scorer, "call_llm", fake_call_llm)
    monkeypatch.setattr(scorer, "log_llm_call", lambda **kw: None)

    await scorer.analyze_unscored_jobs(status="saved")

    assert peaks and max(peaks) == 0, f"sessions open during LLM calls: {peaks}"
    assert counter.open == 0
    test_db.expire_all()
    assert all((j.cv_scores or {}).get("PM") == 65 for j in test_db.query(Job).all())


@pytest.mark.asyncio
async def test_a_failing_provider_does_not_loop_the_batch_pipeline(
        test_db, monkeypatch, counter, _fresh_limiters):
    """A transient failure leaves cv_scores NULL on purpose (retry next pass);
    the batch loop must still terminate rather than re-select the same rows."""
    import backend.analyzer.cv_scorer as scorer
    from backend.models.db import Job

    _seed_resume(test_db)
    _make_jobs(test_db, 3)
    for job in test_db.query(Job).all():
        job.saved = True
    test_db.commit()

    counter.install(monkeypatch, scorer)
    calls = {"n": 0}

    async def fake_call_llm(*a, **kw):
        calls["n"] += 1
        raise RuntimeError("provider down")

    monkeypatch.setattr(scorer, "call_llm", fake_call_llm)
    monkeypatch.setattr(scorer, "log_llm_call", lambda **kw: None)

    await asyncio.wait_for(scorer.analyze_unscored_jobs(status="saved"), timeout=10)

    assert calls["n"] == 3, f"each job tried exactly once, got {calls['n']}"
    test_db.expire_all()
    assert all(j.cv_scores in (None, {}) for j in test_db.query(Job).all())


# ══ 3. Page caching is bounded too ═══════════════════════════════════════════

@pytest.mark.asyncio
async def test_page_caching_is_bounded_and_holds_no_session_while_fetching(
        test_db, monkeypatch, counter, _fresh_limiters):
    """Twelve concurrent caches: at most four fetch at a time (one Chromium
    each, in the worst case) and none holds a connection while fetching."""
    import backend.api.routes_applications as ra

    job_ids = _make_jobs(test_db, 12)
    counter.install(monkeypatch, ra)

    live = {"now": 0, "peak": 0, "sessions": []}

    async def fake_safe_get(url, **kw):
        live["now"] += 1
        live["peak"] = max(live["peak"], live["now"])
        live["sessions"].append(counter.open)
        try:
            await asyncio.sleep(0.02)
        finally:
            live["now"] -= 1

        class _Resp:
            text = "<html><body>" + ("Real job description content. " * 40) + "</body></html>"

            def raise_for_status(self):
                return None
        return _Resp()

    monkeypatch.setattr("backend.scraper._shared.url_safety.safe_get", fake_safe_get)
    monkeypatch.setattr("backend.scraper._shared.url_safety.assert_public_http_url",
                        lambda url: None)

    await asyncio.gather(*[ra._cache_job_page(jid, f"https://x.test/{i}")
                           for i, jid in enumerate(job_ids)])

    assert live["peak"] <= 4, f"{live['peak']} page fetches at once (limit 4)"
    assert max(live["sessions"]) == 0, (
        f"a session was held during a page fetch: {live['sessions']}"
    )
    assert counter.open == 0

    test_db.expire_all()
    from backend.models.db import Job
    cached = test_db.query(Job).filter(Job.page_cached_at.isnot(None)).count()
    assert cached == 12


# ══ 4. The gate itself ═══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_the_gate_is_reentrant_within_one_task(_fresh_limiters):
    """A worker inside the launcher's gate calling a helper that guards itself
    must not deadlock on its own gate."""
    import backend.job_monitor as jm

    limiter = jm.TaskLimiter("reentrancy-probe", 1)
    async with limiter:
        async with limiter:      # would block forever on a plain Semaphore
            pass
    # …and the slot really was given back.
    await asyncio.wait_for(limiter.__aenter__(), timeout=1)
    await limiter.__aexit__(None, None, None)


@pytest.mark.asyncio
async def test_the_gate_still_blocks_across_tasks(_fresh_limiters):
    """Re-entrancy is per task — a second task waits its turn."""
    import backend.job_monitor as jm

    limiter = jm.TaskLimiter("cross-task-probe", 1)
    order = []
    release = asyncio.Event()

    async def first():
        async with limiter:
            order.append("first-in")
            await release.wait()
            order.append("first-out")

    async def second():
        async with limiter:
            order.append("second-in")

    t1 = asyncio.create_task(first())
    await asyncio.sleep(0.01)
    t2 = asyncio.create_task(second())
    await asyncio.sleep(0.01)
    assert order == ["first-in"], "the second task got in while the first held the gate"
    release.set()
    await asyncio.gather(t1, t2)
    assert order == ["first-in", "first-out", "second-in"]


def test_scoring_gate_reads_its_limit_from_settings(test_db, _fresh_limiters):
    from backend.models.db import Setting
    import backend.job_monitor as jm

    test_db.add(Setting(key="scoring_max_concurrent", value="7"))
    test_db.commit()
    assert jm.get_limiter("scoring").value == 7
    # A settings change drops the cached gate so the next use re-reads it.
    from backend.analyzer.cv_scorer import reset_scoring_semaphore
    reset_scoring_semaphore()
    test_db.query(Setting).filter(Setting.key == "scoring_max_concurrent").first().value = "2"
    test_db.commit()
    assert jm.get_limiter("scoring").value == 2


def test_page_cache_gate_is_a_small_fixed_limit(_fresh_limiters):
    import backend.job_monitor as jm
    assert jm.get_limiter("page_cache").value == 4


# ══ 5. A drained pool answers 503, it does not hang ══════════════════════════

def test_a_pool_timeout_answers_503_from_a_handler(client, monkeypatch):
    """pool_timeout is 5 s on the real engine; whatever raises must become a
    503 with Retry-After, never a 500 or a stack trace."""
    from sqlalchemy.exc import TimeoutError as PoolTimeout
    from backend.main import app
    from backend.models.db import get_db

    def _boom():
        raise PoolTimeout("QueuePool limit of size 20 overflow 10 reached")

    app.dependency_overrides[get_db] = _boom
    try:
        resp = client.get("/api/jobs/feed-stats")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 503
    assert resp.headers.get("Retry-After") == "5"
    assert "QueuePool" not in resp.text


def test_health_needs_no_database(client, monkeypatch):
    """/health must answer with the pool fully drained — it is the endpoint the
    dashboard and the operator poll when everything else is stuck."""
    from sqlalchemy.exc import TimeoutError as PoolTimeout
    import backend.main as main_mod

    def _drained(*a, **kw):
        raise PoolTimeout("QueuePool limit of size 20 overflow 10 reached")

    monkeypatch.setattr(main_mod, "SessionLocal", _drained)
    assert client.get("/health").status_code == 200


def test_the_auth_middleware_answers_503_when_the_pool_is_drained(client, monkeypatch):
    """The middleware runs outside FastAPI's exception handlers, so it needs its
    own guard — without it a drained pool surfaced as a bare connection error."""
    from sqlalchemy.exc import TimeoutError as PoolTimeout
    import backend.main as main_mod

    class _DrainedSession:
        def query(self, *a, **kw):
            raise PoolTimeout("QueuePool limit of size 20 overflow 10 reached")

        def close(self):
            return None

    monkeypatch.setattr(main_mod, "SessionLocal", lambda *a, **kw: _DrainedSession())
    resp = client.get("/api/jobs/feed-stats")
    assert resp.status_code == 503
    assert resp.headers.get("Retry-After") == "5"


def test_the_engine_fails_fast_instead_of_hanging():
    """Documents the pool settings the fix depends on (Postgres only — the test
    engine is SQLite, so read them off the module's kwargs)."""
    import backend.models.db as db_mod
    kwargs = db_mod._engine_kwargs
    if "pool_size" not in kwargs:      # SQLite test run
        pytest.skip("pool args are Postgres-only")
    assert kwargs["pool_timeout"] <= 10, "a drained pool must fail fast"
    assert kwargs["pool_size"] + kwargs["max_overflow"] <= 40
