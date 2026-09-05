"""R4-T1 · concurrency: scheduler vs manual runs, stale-run recovery, monitor/DB agreement.

`tracked_run` (scheduler) and `launch_background` (manual triggers) share one
in-memory `_running` dict keyed by `job_type[:scope_key]`, and each writes a
`JobRun` row. The invariant under test: exactly one live run per scope key, and
the DB row always agrees with the in-memory entry.

SQLite strips tz from DateTime(timezone=True), so a load listener re-applies UTC
— without it `cleanup_stale_runs()` subtracts a naive from an aware datetime.
"""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import event

from backend.tests.r4_support import (  # noqa: F401
    client, _clear_running_state, _no_outbound, assert_clean,
    make_company, make_search, MISSING_UUID,
)


@pytest.fixture(autouse=True)
def _utc_tz_on_jobrun_load():
    from backend.models.db import JobRun

    def _on_load(instance, context):
        for field in ("started_at", "finished_at"):
            v = getattr(instance, field, None)
            if v is not None and v.tzinfo is None:
                setattr(instance, field, v.replace(tzinfo=timezone.utc))

    event.listen(JobRun, "load", _on_load)
    yield
    event.remove(JobRun, "load", _on_load)


def _runs(db, **filters):
    from backend.models.db import JobRun
    db.expire_all()
    q = db.query(JobRun)
    for k, v in filters.items():
        q = q.filter(getattr(JobRun, k) == v)
    return q.all()


# ══ One live run per scope key ═══════════════════════════════════════════════

@pytest.mark.asyncio
async def test_manual_launch_is_refused_while_the_scheduler_holds_the_scope(test_db):
    """launch_background must not start a second run under a scope tracked_run owns."""
    import backend.job_monitor as jm

    async def _noop():
        return None

    async with jm.tracked_run("scrape_all", "scheduler"):
        with pytest.raises(jm.JobAlreadyRunningError):
            jm.launch_background("scrape_all", _noop, trigger="manual")
    # Only the scheduler's own row was written.
    assert len(_runs(test_db, job_type="scrape_all")) == 1


@pytest.mark.asyncio
async def test_scheduler_is_refused_while_a_manual_run_holds_the_scope(test_db):
    import backend.job_monitor as jm
    gate = asyncio.Event()

    async def _slow():
        await gate.wait()

    jm.launch_background("scrape_all", _slow, trigger="manual")
    with pytest.raises(jm.JobAlreadyRunningError):
        async with jm.tracked_run("scrape_all", "scheduler"):
            pass
    gate.set()
    await asyncio.sleep(0)
    assert len(_runs(test_db, job_type="scrape_all")) == 1


@pytest.mark.asyncio
async def test_scheduler_run_all_scrapes_skips_instead_of_raising(test_db, monkeypatch):
    """The scheduler swallows JobAlreadyRunningError so APScheduler is not poisoned."""
    import backend.job_monitor as jm
    from backend.scheduler import run_all_scrapes
    gate = asyncio.Event()

    async def _slow():
        await gate.wait()

    jm.launch_background("scrape_all", _slow, trigger="manual")
    await run_all_scrapes()          # must not raise
    gate.set()
    await asyncio.sleep(0)
    rows = _runs(test_db, job_type="scrape_all")
    assert len(rows) == 1 and rows[0].trigger == "manual"


@pytest.mark.asyncio
@pytest.mark.parametrize("fn_name", ["run_email_check", "send_daily_digest",
                                     "refresh_h1b_data", "run_auto_reject",
                                     "run_job_cleanup_auto", "run_db_backup"])
async def test_every_scheduled_job_skips_a_busy_scope_without_raising(test_db, fn_name):
    import backend.job_monitor as jm
    import backend.scheduler as sched

    job_type = {
        "run_email_check": "email_check", "send_daily_digest": "daily_digest",
        "refresh_h1b_data": "h1b_refresh", "run_auto_reject": "auto_reject",
        "run_job_cleanup_auto": "job_cleanup", "run_db_backup": "db_backup",
    }[fn_name]
    jm._running[job_type] = jm.RunningJob(
        run_id=uuid.uuid4(), job_type=job_type, trigger="manual",
        started_at=datetime.now(timezone.utc))
    await getattr(sched, fn_name)()   # must not raise
    assert _runs(test_db, job_type=job_type) == []


def test_manual_trigger_answers_409_while_the_scheduler_run_is_live(client):
    """The HTTP surface of the same guard."""
    import backend.job_monitor as jm
    jm._running["scrape_all"] = jm.RunningJob(
        run_id=uuid.uuid4(), job_type="scrape_all", trigger="scheduler",
        started_at=datetime.now(timezone.utc))
    assert_clean(client.post("/api/scrape/run-all"), 409)


def test_different_scope_keys_of_one_job_type_run_side_by_side(client, test_db, monkeypatch):
    import backend.scraper.sources.company_pages as cp
    gate = asyncio.Event()

    async def _slow(company):
        await gate.wait()
        return {}
    monkeypatch.setattr(cp, "scrape_single_career_page", _slow, raising=False)
    monkeypatch.setattr(cp, "record_company_scrape_log", lambda *a, **k: None, raising=False)

    a = make_company(test_db, name="A")
    b = make_company(test_db, name="B")
    assert_clean(client.post(f"/api/scrape/company/{a.id}"), 202)
    assert_clean(client.post(f"/api/scrape/company/{b.id}"), 202)
    import backend.job_monitor as jm
    assert len([r for r in jm._running.values() if r.job_type == "company_scrape"]) == 2
    gate.set()


def test_scheduler_jobs_view_reports_a_scoped_company_run_as_running(client, test_db):
    import backend.job_monitor as jm
    c = make_company(test_db, name="A", active=True, scrape_interval_minutes=30)
    jm._running[f"company_scrape:{c.id}"] = jm.RunningJob(
        run_id=uuid.uuid4(), job_type="company_scrape", trigger="manual",
        started_at=datetime.now(timezone.utc), scope_key=str(c.id), company_id=str(c.id))
    rows = assert_clean(client.get("/api/scheduler/jobs"), 200).json()
    row = next(r for r in rows if r["id"] == f"company_{c.id}")
    assert row["running"] and row["running"]["elapsed_seconds"] >= 0


# ══ In-memory state vs JobRun rows ═══════════════════════════════════════════

@pytest.mark.asyncio
async def test_tracked_run_row_matches_the_in_memory_entry_while_live(test_db):
    import backend.job_monitor as jm

    async with jm.tracked_run("scrape_all", "scheduler", scope_key="s1") as run:
        entry = jm._running["scrape_all:s1"]
        rows = _runs(test_db, job_type="scrape_all")
        assert len(rows) == 1
        assert str(rows[0].id) == str(entry.run_id) == str(run.run_id)
        assert rows[0].status == "running"
        run.summary = "12 sources"
    rows = _runs(test_db, job_type="scrape_all")
    assert rows[0].status == "completed" and rows[0].result_summary == "12 sources"
    assert "scrape_all:s1" not in jm._running


@pytest.mark.asyncio
async def test_tracked_run_marks_failed_and_re_raises(test_db):
    import backend.job_monitor as jm

    with pytest.raises(RuntimeError):
        async with jm.tracked_run("email_check", "scheduler"):
            raise RuntimeError("gmail exploded")
    row = _runs(test_db, job_type="email_check")[0]
    assert row.status == "failed" and "gmail exploded" in (row.error or "")
    assert "email_check" not in jm._running


@pytest.mark.asyncio
async def test_launch_background_failure_marks_the_row_and_frees_the_scope(test_db):
    import backend.job_monitor as jm

    async def _boom():
        raise RuntimeError("scraper exploded")

    jm.launch_background("scrape_all", _boom, trigger="manual")
    await asyncio.sleep(0.05)
    row = _runs(test_db, job_type="scrape_all")[0]
    assert row.status == "failed" and "scraper exploded" in (row.error or "")
    assert "scrape_all" not in jm._running


@pytest.mark.asyncio
async def test_launch_background_string_return_becomes_the_summary(test_db):
    import backend.job_monitor as jm

    async def _ok():
        return "  4 sources - +2 new  "

    jm.launch_background("scrape_all", _ok, trigger="manual")
    await asyncio.sleep(0.05)
    assert _runs(test_db, job_type="scrape_all")[0].result_summary == "4 sources - +2 new"


@pytest.mark.asyncio
async def test_no_orphan_running_rows_after_a_burst_of_runs(test_db):
    """Ten runs across two scopes leave zero in-memory entries and zero 'running' rows."""
    import backend.job_monitor as jm

    async def _ok():
        return "done"

    for i in range(10):
        scope = f"s{i % 2}"
        while jm.is_running("company_scrape", scope):
            await asyncio.sleep(0.01)
        jm.launch_background("company_scrape", _ok, trigger="manual", scope_key=scope)
    await asyncio.sleep(0.2)
    assert jm._running == {}
    assert _runs(test_db, job_type="company_scrape", status="running") == []
    assert len(_runs(test_db, job_type="company_scrape")) == 10


# ══ Stale-run recovery (container killed mid-run) ════════════════════════════

def test_cleanup_stale_runs_fails_every_orphan_row(test_db):
    """Simulates the process dying mid-run: rows say 'running', memory is empty."""
    from backend.models.db import JobRun
    from backend.job_monitor import cleanup_stale_runs

    started = datetime.now(timezone.utc) - timedelta(minutes=45)
    for jt in ("scrape_all", "email_check", "company_scrape"):
        test_db.add(JobRun(id=uuid.uuid4(), job_type=jt, trigger="scheduler",
                           status="running", started_at=started))
    test_db.add(JobRun(id=uuid.uuid4(), job_type="db_backup", trigger="scheduler",
                       status="completed", started_at=started,
                       finished_at=started + timedelta(seconds=3)))
    test_db.commit()

    assert cleanup_stale_runs() == 3
    test_db.expire_all()
    stale = test_db.query(JobRun).filter(JobRun.status == "failed").all()
    assert len(stale) == 3
    for row in stale:
        assert row.error == "Process restarted"
        assert row.finished_at is not None
        assert row.duration_seconds and row.duration_seconds > 0
    assert test_db.query(JobRun).filter(JobRun.status == "completed").count() == 1


def test_cleanup_stale_runs_is_idempotent(test_db):
    from backend.models.db import JobRun
    from backend.job_monitor import cleanup_stale_runs

    test_db.add(JobRun(id=uuid.uuid4(), job_type="scrape_all", trigger="scheduler",
                       status="running",
                       started_at=datetime.now(timezone.utc) - timedelta(minutes=5)))
    test_db.commit()
    assert cleanup_stale_runs() == 1
    assert cleanup_stale_runs() == 0


def test_cleanup_stale_runs_on_an_empty_table(test_db):
    from backend.job_monitor import cleanup_stale_runs
    assert cleanup_stale_runs() == 0


def test_monitor_history_shows_a_recovered_run_as_failed(client, test_db):
    from backend.models.db import JobRun
    from backend.job_monitor import cleanup_stale_runs

    test_db.add(JobRun(id=uuid.uuid4(), job_type="scrape_all", trigger="scheduler",
                       status="running",
                       started_at=datetime.now(timezone.utc) - timedelta(minutes=5)))
    test_db.commit()
    cleanup_stale_runs()
    rows = assert_clean(client.get("/api/monitor/history?job_type=scrape_all"), 200).json()
    assert rows[0]["status"] == "failed" and rows[0]["error"] == "Process restarted"


def test_stale_recovery_does_not_touch_a_run_that_is_genuinely_live(test_db):
    """A restart clears memory too, so this documents the limitation, not a fix.

    `cleanup_stale_runs()` runs only in the lifespan, when `_running` is empty by
    construction — but if it were ever called mid-process it would fail a live run.
    """
    from backend.models.db import JobRun
    from backend.job_monitor import cleanup_stale_runs
    import backend.job_monitor as jm

    rid = uuid.uuid4()
    test_db.add(JobRun(id=rid, job_type="scrape_all", trigger="manual", status="running",
                       started_at=datetime.now(timezone.utc)))
    test_db.commit()
    jm._running["scrape_all"] = jm.RunningJob(run_id=rid, job_type="scrape_all",
                                              trigger="manual",
                                              started_at=datetime.now(timezone.utc))
    assert cleanup_stale_runs() == 1        # current behaviour: memory is not consulted
    test_db.expire_all()
    assert test_db.query(JobRun).filter(JobRun.id == rid).first().status == "failed"
    assert "scrape_all" in jm._running       # …while the monitor still shows it running


@pytest.mark.xfail(strict=True, reason="R4-T1-27")
def test_stale_recovery_should_skip_runs_the_monitor_still_owns(test_db):
    """A mid-process call must not fail a run the in-memory monitor is still driving."""
    from backend.models.db import JobRun
    from backend.job_monitor import cleanup_stale_runs
    import backend.job_monitor as jm

    rid = uuid.uuid4()
    test_db.add(JobRun(id=rid, job_type="scrape_all", trigger="manual", status="running",
                       started_at=datetime.now(timezone.utc)))
    test_db.commit()
    jm._running["scrape_all"] = jm.RunningJob(run_id=rid, job_type="scrape_all",
                                              trigger="manual",
                                              started_at=datetime.now(timezone.utc))
    assert cleanup_stale_runs() == 0


# ══ Monitor endpoints agree with memory ══════════════════════════════════════

@pytest.mark.asyncio
async def test_monitor_active_and_in_flight_agree_with_running_state(client, test_db):
    import backend.job_monitor as jm
    jid = uuid.uuid4()
    gate = asyncio.Event()

    async def _slow():
        await gate.wait()

    jm.launch_background("analyze_job", _slow, trigger="manual",
                         scope_key=f"{jid}:on-save", target_job_id=jid)
    active = client.get("/api/monitor/active").json()
    in_flight = client.get("/api/monitor/in-flight").json()
    assert len(active) == 1 and active[0]["target_job_id"] == str(jid)
    assert in_flight == {str(jid): ["analyze_job"]}
    assert _runs(test_db, job_type="analyze_job")[0].status == "running"

    gate.set()
    await asyncio.sleep(0.05)
    assert client.get("/api/monitor/active").json() == []
    assert client.get("/api/monitor/in-flight").json() == {}
    assert _runs(test_db, job_type="analyze_job")[0].status == "completed"


@pytest.mark.asyncio
async def test_finished_run_shows_up_in_monitor_finished(client, test_db):
    import backend.job_monitor as jm
    jid = uuid.uuid4()

    async def _ok():
        return "scored"

    jm.launch_background("analyze_job", _ok, trigger="manual",
                         scope_key=str(jid), target_job_id=jid)
    await asyncio.sleep(0.05)
    rows = client.get(f"/api/monitor/finished?job_ids={jid}").json()
    assert rows and rows[0]["status"] == "completed"


@pytest.mark.asyncio
async def test_failed_run_shows_up_in_monitor_finished_as_failed(client, test_db):
    import backend.job_monitor as jm
    jid = uuid.uuid4()

    async def _boom():
        raise RuntimeError("nope")

    jm.launch_background("analyze_job", _boom, trigger="manual",
                         scope_key=str(jid), target_job_id=jid)
    await asyncio.sleep(0.05)
    rows = client.get(f"/api/monitor/finished?job_ids={jid}").json()
    assert rows and rows[0]["status"] == "failed"
    # …and the reason stays server-side.
    assert "nope" not in client.get(f"/api/monitor/finished?job_ids={jid}").text
