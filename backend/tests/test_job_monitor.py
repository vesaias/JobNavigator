"""Tests for job_monitor — tracked_run + launch_background + cleanup_stale_runs.

Notes on SQLite compatibility:
- SQLite does not preserve timezone on DateTime(timezone=True) columns. Values stored
  tz-aware come back tz-naive on read. Production code in job_monitor computes
  `datetime.now(timezone.utc) - run.started_at`, which raises TypeError under SQLite.
  We attach a SQLAlchemy 'load' event listener on JobRun that re-applies UTC after
  load, matching PostgreSQL behavior in production.
- The UUID column of JobRun.id is mapped to CHAR(32) under SQLite. Production code
  passes `uuid.UUID` objects which work for insert; for queries we look up by
  `job_type` to avoid UUID-type binding quirks.
"""
import asyncio
import pytest
from datetime import datetime, timezone
from sqlalchemy import event
from sqlalchemy.orm import sessionmaker


@pytest.fixture(autouse=True)
def _utc_tz_on_jobrun_load():
    """Re-attach UTC tz on loaded JobRun datetimes (SQLite strips tz)."""
    from backend.models.db import JobRun

    def _on_load(instance, context):
        for field in ("started_at", "finished_at"):
            v = getattr(instance, field, None)
            if v is not None and v.tzinfo is None:
                setattr(instance, field, v.replace(tzinfo=timezone.utc))

    event.listen(JobRun, "load", _on_load)
    yield
    event.remove(JobRun, "load", _on_load)


@pytest.fixture(autouse=True)
def _clear_running_state():
    """Ensure the in-memory _running dict is empty between tests."""
    import backend.job_monitor as jm
    jm._running.clear()
    yield
    jm._running.clear()


@pytest.mark.asyncio
async def test_tracked_run_writes_running_then_completed(test_db, monkeypatch):
    """tracked_run writes a JobRun row: status starts 'running', ends 'completed' on clean exit."""
    from backend.models.db import JobRun
    import backend.job_monitor as jm

    TestSession = sessionmaker(bind=test_db.get_bind())
    monkeypatch.setattr(jm, "SessionLocal", TestSession)

    async with jm.tracked_run("test_job_a", "scheduler"):
        # While inside the context, the in-memory _running should have our entry.
        assert "test_job_a" in jm._running

    s = TestSession()
    runs = s.query(JobRun).filter_by(job_type="test_job_a").all()
    s.close()
    assert len(runs) == 1
    assert runs[0].status == "completed"
    assert runs[0].started_at is not None
    assert runs[0].finished_at is not None
    # In-memory state cleared after exit
    assert "test_job_a" not in jm._running


@pytest.mark.asyncio
async def test_tracked_run_marks_failed_on_exception(test_db, monkeypatch):
    """Exception inside the with-block marks the JobRun as 'failed' with the error message."""
    from backend.models.db import JobRun
    import backend.job_monitor as jm

    TestSession = sessionmaker(bind=test_db.get_bind())
    monkeypatch.setattr(jm, "SessionLocal", TestSession)

    with pytest.raises(RuntimeError, match="boom"):
        async with jm.tracked_run("test_job_b", "scheduler"):
            raise RuntimeError("boom")

    s = TestSession()
    runs = s.query(JobRun).filter_by(job_type="test_job_b").all()
    s.close()
    assert len(runs) == 1
    assert runs[0].status == "failed"
    assert "boom" in (runs[0].error or "")
    assert "test_job_b" not in jm._running


@pytest.mark.asyncio
async def test_tracked_run_raises_already_running(test_db, monkeypatch):
    """Concurrent tracked_run of the same job_type raises JobAlreadyRunningError."""
    import backend.job_monitor as jm

    TestSession = sessionmaker(bind=test_db.get_bind())
    monkeypatch.setattr(jm, "SessionLocal", TestSession)

    started = asyncio.Event()
    released = asyncio.Event()

    async def long_task():
        async with jm.tracked_run("test_job_c", "scheduler"):
            started.set()
            await released.wait()

    async def conflicting_task():
        await started.wait()
        try:
            async with jm.tracked_run("test_job_c", "scheduler"):
                raise AssertionError("should have raised JobAlreadyRunningError")
        except jm.JobAlreadyRunningError as e:
            released.set()
            return ("raised", e.job_type, e.elapsed_seconds)

    long_fut = asyncio.create_task(long_task())
    conflict_fut = asyncio.create_task(conflicting_task())

    result = await conflict_fut
    await long_fut

    assert result[0] == "raised"
    assert result[1] == "test_job_c"
    assert result[2] >= 0.0


def test_cleanup_stale_runs_marks_orphans_failed(test_db, monkeypatch):
    """Startup cleanup: 'running' rows from a previous process → 'failed' with restart note."""
    from backend.models.db import JobRun
    import backend.job_monitor as jm

    TestSession = sessionmaker(bind=test_db.get_bind())
    monkeypatch.setattr(jm, "SessionLocal", TestSession)

    # Seed 2 orphan running rows + 1 already-completed row (should not be touched).
    s = TestSession()
    s.add(JobRun(
        job_type="orphan_job_1",
        trigger="scheduler",
        status="running",
        started_at=datetime.now(timezone.utc),
    ))
    s.add(JobRun(
        job_type="orphan_job_2",
        trigger="manual",
        status="running",
        started_at=datetime.now(timezone.utc),
    ))
    s.add(JobRun(
        job_type="done_job",
        trigger="scheduler",
        status="completed",
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
    ))
    s.commit()
    s.close()

    count = jm.cleanup_stale_runs()
    assert count == 2

    s2 = TestSession()
    orphan1 = s2.query(JobRun).filter_by(job_type="orphan_job_1").first()
    orphan2 = s2.query(JobRun).filter_by(job_type="orphan_job_2").first()
    done = s2.query(JobRun).filter_by(job_type="done_job").first()
    s2.close()

    assert orphan1.status == "failed"
    assert orphan1.finished_at is not None
    assert "restart" in (orphan1.error or "").lower()

    assert orphan2.status == "failed"
    assert "restart" in (orphan2.error or "").lower()

    # Completed row should remain untouched.
    assert done.status == "completed"
    assert done.error is None


@pytest.mark.asyncio
async def test_launch_background_returns_run_id_and_executes(test_db, monkeypatch):
    """launch_background returns a run_id string AND actually runs the coroutine factory."""
    from backend.models.db import JobRun
    import backend.job_monitor as jm

    TestSession = sessionmaker(bind=test_db.get_bind())
    monkeypatch.setattr(jm, "SessionLocal", TestSession)

    executed = asyncio.Event()

    async def worker():
        executed.set()

    run_id = jm.launch_background("bg_exec_test", worker, trigger="manual")
    assert isinstance(run_id, str)
    assert len(run_id) > 0

    # Wait for the coroutine body to run
    await asyncio.wait_for(executed.wait(), timeout=2.0)

    # Drain the background task so the _finish_job_run wrapper commits before we query.
    for _ in range(50):
        await asyncio.sleep(0)
        if "bg_exec_test" not in jm._running:
            break

    s = TestSession()
    run = s.query(JobRun).filter_by(job_type="bg_exec_test").first()
    s.close()
    assert run is not None
    assert run.status == "completed"
    assert run.trigger == "manual"
