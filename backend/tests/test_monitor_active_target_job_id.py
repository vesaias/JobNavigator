"""get_all_running() exposes target_job_id (Task 10 of 12)."""
import uuid
from datetime import datetime, timezone


def test_active_includes_target_job_id(monkeypatch):
    """Each entry in /api/monitor/active returns target_job_id (str or None)."""
    from backend.job_monitor import RunningJob, get_all_running
    import backend.job_monitor as mon

    job_uuid = uuid.uuid4()
    fake = {
        "tailor_resume:base1:job1": RunningJob(
            run_id=uuid.uuid4(),
            job_type="tailor_resume",
            trigger="manual",
            started_at=datetime.now(timezone.utc),
            scope_key="base1:job1",
            target_job_id=job_uuid,
        ),
        "scrape_all": RunningJob(
            run_id=uuid.uuid4(),
            job_type="scrape_all",
            trigger="scheduler",
            started_at=datetime.now(timezone.utc),
            scope_key=None,
            target_job_id=None,
        ),
    }
    monkeypatch.setattr(mon, "_running", fake)

    rows = get_all_running()
    assert len(rows) == 2
    by_type = {r["job_type"]: r for r in rows}
    assert by_type["tailor_resume"]["target_job_id"] == str(job_uuid)
    assert by_type["scrape_all"]["target_job_id"] is None
