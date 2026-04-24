"""GET /api/jobs returns in_flight array per row (Task 7 of 12)."""
import uuid
from datetime import datetime, timezone

import pytest
from backend.models.db import Setting, Job


def test_list_jobs_includes_in_flight_for_running_ops(api_client, test_db, monkeypatch):
    """Job with running tailor op → in_flight:['tailor_resume'] in list response."""
    test_db.add(Setting(key="dashboard_api_key", value=""))
    job = Job(external_id="lf1", content_hash="lf1", company="Acme", title="PM", status="new")
    test_db.add(job)
    test_db.commit()

    from backend.job_monitor import RunningJob
    import backend.job_monitor as mon
    monkeypatch.setattr(mon, "_running", {
        f"tailor_resume:{job.id}": RunningJob(
            run_id=uuid.uuid4(),
            job_type="tailor_resume",
            trigger="manual",
            started_at=datetime.now(timezone.utc),
            scope_key=str(job.id),
            target_job_id=job.id,
        )
    })

    resp = api_client.get("/api/jobs")
    assert resp.status_code == 200
    rows = resp.json().get("jobs", [])
    assert len(rows) == 1
    assert rows[0]["in_flight"] == ["tailor_resume"]


def test_list_jobs_in_flight_defaults_to_empty(api_client, test_db, monkeypatch):
    test_db.add(Setting(key="dashboard_api_key", value=""))
    job = Job(external_id="lf2", content_hash="lf2", company="Acme", title="PM", status="new")
    test_db.add(job)
    test_db.commit()

    import backend.job_monitor as mon
    monkeypatch.setattr(mon, "_running", {})

    resp = api_client.get("/api/jobs")
    rows = resp.json().get("jobs", [])
    assert rows[0]["in_flight"] == []
