"""JobRun.target_job_id column + filter behavior (Task 1 of 12)."""
import uuid
import asyncio
import pytest
from datetime import timezone
from sqlalchemy import event
from backend.models.db import JobRun


@pytest.fixture(autouse=True)
def _utc_tz_on_jobrun_load():
    """Re-attach UTC tz on loaded JobRun datetimes (SQLite strips tz).

    Mirrors the fixture in test_job_monitor.py — without it, tracked_run()'s
    _finish_job_run fails with 'can't subtract offset-naive and offset-aware
    datetimes' because SQLite DateTime(timezone=True) columns come back naive.
    """
    def _on_load(instance, context):
        for field in ("started_at", "finished_at"):
            v = getattr(instance, field, None)
            if v is not None and v.tzinfo is None:
                setattr(instance, field, v.replace(tzinfo=timezone.utc))

    event.listen(JobRun, "load", _on_load)
    yield
    event.remove(JobRun, "load", _on_load)


def test_target_job_id_column_nullable(test_db):
    """Legacy rows without target_job_id stay unchanged."""
    assert hasattr(JobRun, "target_job_id")
    row = JobRun(job_type="scrape_all", trigger="scheduler", status="running")
    test_db.add(row)
    test_db.commit()
    back = test_db.query(JobRun).filter(JobRun.job_type == "scrape_all").first()
    assert back.target_job_id is None


def test_target_job_id_stores_uuid(test_db):
    job_uuid = uuid.uuid4()
    row = JobRun(
        job_type="tailor_resume",
        trigger="manual",
        status="running",
        target_job_id=job_uuid,
    )
    test_db.add(row)
    test_db.commit()
    back = test_db.query(JobRun).filter(JobRun.job_type == "tailor_resume").first()
    assert back.target_job_id == job_uuid


def test_target_job_id_indexed_for_filter(test_db):
    """Filter by target_job_id returns only matching rows."""
    job_a, job_b = uuid.uuid4(), uuid.uuid4()
    test_db.add_all([
        JobRun(job_type="tailor_resume", trigger="manual", status="running", target_job_id=job_a),
        JobRun(job_type="analyze_job",  trigger="manual", status="running", target_job_id=job_a),
        JobRun(job_type="tailor_resume", trigger="manual", status="running", target_job_id=job_b),
    ])
    test_db.commit()
    rows = test_db.query(JobRun).filter(JobRun.target_job_id == job_a).all()
    assert len(rows) == 2
    assert {r.job_type for r in rows} == {"tailor_resume", "analyze_job"}


@pytest.mark.asyncio
async def test_launch_background_persists_target_job_id(test_db, monkeypatch):
    """launch_background(target_job_id=X) should write X into the JobRun row."""
    # Reset running state for test isolation
    import backend.job_monitor as mon
    monkeypatch.setattr(mon, "_running", {})

    job_uuid = uuid.uuid4()

    async def noop():
        pass

    from backend.job_monitor import launch_background
    run_id = launch_background(
        "tailor_resume", noop, trigger="manual",
        scope_key=str(job_uuid), target_job_id=job_uuid,
    )
    assert run_id

    # Give the wrapper a chance to finish
    await asyncio.sleep(0.05)

    row = test_db.query(JobRun).filter(JobRun.id == uuid.UUID(run_id)).first()
    assert row is not None
    assert row.target_job_id == job_uuid


@pytest.mark.asyncio
async def test_tracked_run_persists_target_job_id(test_db, monkeypatch):
    """tracked_run(target_job_id=X) should write X into the JobRun row."""
    import backend.job_monitor as mon
    monkeypatch.setattr(mon, "_running", {})

    job_uuid = uuid.uuid4()

    from backend.job_monitor import tracked_run
    async with tracked_run("analyze_job", trigger="scheduler", target_job_id=job_uuid):
        pass

    row = test_db.query(JobRun).filter(JobRun.job_type == "analyze_job").first()
    assert row is not None
    assert row.target_job_id == job_uuid
