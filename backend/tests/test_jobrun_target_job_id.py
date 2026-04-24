"""JobRun.target_job_id column + filter behavior (Task 1 of 12)."""
import uuid
from backend.models.db import JobRun


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
