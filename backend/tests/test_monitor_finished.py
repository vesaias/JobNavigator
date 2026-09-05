"""GET /api/monitor/finished — recently-finished per-job runs, with status; lets the dashboard resolve OK/NOK using the run's actual status, which can't be inferred from job fields for re-runs."""
import uuid
from datetime import datetime, timezone, timedelta
from backend.models.db import Setting, JobRun


def _seed(test_db):
    test_db.add(Setting(key="dashboard_api_key", value=""))
    test_db.commit()


def _run(test_db, job_id, job_type, status, finished_at):
    r = JobRun(job_type=job_type, trigger="manual", status=status,
               target_job_id=job_id, finished_at=finished_at)
    test_db.add(r)
    test_db.commit()
    return r


def test_finished_reports_status_by_job(api_client, test_db):
    _seed(test_db)
    job_a = uuid.uuid4()
    now = datetime.now(timezone.utc)
    _run(test_db, job_a, "tailor_resume", "completed", now)
    _run(test_db, job_a, "analyze_job", "failed", now)
    resp = api_client.get(f"/api/monitor/finished?job_ids={job_a}")
    assert resp.status_code == 200
    got = {(d["job_type"], d["status"]) for d in resp.json()}
    assert ("tailor_resume", "completed") in got
    assert ("analyze_job", "failed") in got
    assert all(d["target_job_id"] == str(job_a) for d in resp.json())


def test_finished_excludes_still_running(api_client, test_db):
    _seed(test_db)
    job_a = uuid.uuid4()
    _run(test_db, job_a, "tailor_resume", "running", None)
    resp = api_client.get(f"/api/monitor/finished?job_ids={job_a}")
    assert resp.json() == []


def test_finished_filters_by_job_ids(api_client, test_db):
    _seed(test_db)
    job_a, job_b = uuid.uuid4(), uuid.uuid4()
    now = datetime.now(timezone.utc)
    _run(test_db, job_a, "tailor_resume", "completed", now)
    _run(test_db, job_b, "tailor_resume", "completed", now)
    resp = api_client.get(f"/api/monitor/finished?job_ids={job_a}")
    assert {d["target_job_id"] for d in resp.json()} == {str(job_a)}


def test_finished_filters_by_since(api_client, test_db):
    _seed(test_db)
    job_a = uuid.uuid4()
    now = datetime.now(timezone.utc)
    _run(test_db, job_a, "tailor_resume", "completed", now - timedelta(minutes=10))
    _run(test_db, job_a, "analyze_job", "completed", now)
    since_ms = int((now - timedelta(minutes=1)).timestamp() * 1000)
    resp = api_client.get(f"/api/monitor/finished?job_ids={job_a}&since={since_ms}")
    assert {d["job_type"] for d in resp.json()} == {"analyze_job"}
