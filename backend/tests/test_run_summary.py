"""JobRun.result_summary must actually reach the DB.

Before this, both tracked_run and launch_background hard-coded None, so every
completed run in Stats > Run history showed a bare status with no account of
what it did. Two routes now carry a summary: a tracked_run body assigns
`run.summary`, and a launch_background coroutine returns a string.

SQLite fixtures mirror test_job_monitor.py — see its module docstring for why
the tz listener and the query-by-job_type pattern are needed.
"""
import asyncio
from datetime import timezone

import pytest
from sqlalchemy import event
from sqlalchemy.orm import sessionmaker

import backend.job_monitor as jm
from backend.models.db import JobRun


@pytest.fixture(autouse=True)
def _utc_tz_on_jobrun_load():
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
    jm._running.clear()
    yield
    jm._running.clear()


@pytest.fixture
def session(test_db, monkeypatch):
    monkeypatch.setattr(jm, "SessionLocal", sessionmaker(bind=test_db.get_bind()))
    return test_db


def _row(db, job_type):
    db.expire_all()
    return db.query(JobRun).filter(JobRun.job_type == job_type).first()


@pytest.mark.asyncio
async def test_tracked_run_persists_assigned_summary(session):
    async with jm.tracked_run("summary_job_a", "scheduler") as run:
        run.summary = "8 sources - +14 new"

    row = _row(session, "summary_job_a")
    assert row.status == "completed"
    assert row.result_summary == "8 sources - +14 new"


@pytest.mark.asyncio
async def test_tracked_run_without_summary_stays_none(session):
    async with jm.tracked_run("summary_job_b", "scheduler"):
        pass

    row = _row(session, "summary_job_b")
    assert row.status == "completed"
    assert row.result_summary is None


@pytest.mark.asyncio
async def test_failed_run_records_error_not_summary(session):
    with pytest.raises(ValueError):
        async with jm.tracked_run("summary_job_c", "scheduler") as run:
            run.summary = "should not be kept"
            raise ValueError("boom")

    row = _row(session, "summary_job_c")
    assert row.status == "failed"
    assert row.error == "boom"
    # a failure is described by its error, not a summary written before the raise
    assert row.result_summary is None


@pytest.mark.asyncio
async def test_launch_background_uses_returned_string(session):
    async def worker():
        return "  3 replies classified  "

    jm.launch_background("summary_job_d", worker)
    await asyncio.sleep(0.1)

    row = _row(session, "summary_job_d")
    assert row.status == "completed"
    assert row.result_summary == "3 replies classified"   # stripped


@pytest.mark.asyncio
@pytest.mark.parametrize("returned,label", [(None, "none"), (0, "zero"), ("", "empty"), ("   ", "blank"), ({"a": 1}, "dict")])
async def test_launch_background_ignores_non_string_returns(session, returned, label):
    async def worker():
        return returned

    job_type = f"summary_job_e_{label}"
    jm.launch_background(job_type, worker)
    await asyncio.sleep(0.1)

    row = _row(session, job_type)
    assert row.status == "completed"
    assert row.result_summary is None
