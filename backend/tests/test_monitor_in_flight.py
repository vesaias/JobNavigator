"""GET /api/monitor/in-flight — per-job active-op lookup (Task 6 of 12)."""
import asyncio
import pytest
import uuid
from backend.models.db import Setting


def _seed(test_db):
    test_db.add(Setting(key="dashboard_api_key", value=""))
    test_db.commit()


def _install_fake_running(monkeypatch, entries):
    """Fake in-memory _running dict. entries = [(key, job_type, target_job_id)]."""
    from backend.job_monitor import RunningJob
    from datetime import datetime, timezone
    fake = {}
    for key, jt, target in entries:
        fake[key] = RunningJob(
            run_id=uuid.uuid4(),
            job_type=jt,
            trigger="manual",
            started_at=datetime.now(timezone.utc),
            scope_key=key,
            target_job_id=target,
        )
    import backend.job_monitor as mon
    monkeypatch.setattr(mon, "_running", fake)


def test_in_flight_returns_per_job_map(api_client, test_db, monkeypatch):
    """Multiple active ops → grouped by target_job_id."""
    _seed(test_db)
    job_a, job_b = uuid.uuid4(), uuid.uuid4()
    _install_fake_running(monkeypatch, [
        (f"tailor_resume:{job_a}", "tailor_resume", job_a),
        (f"analyze_job:{job_a}", "analyze_job", job_a),
        (f"tailor_resume:{job_b}", "tailor_resume", job_b),
        ("scrape_all", "scrape_all", None),  # scheduler op, not per-job — ignored
    ])
    resp = api_client.get("/api/monitor/in-flight")
    assert resp.status_code == 200
    data = resp.json()
    # Keys are string UUIDs
    assert set(data.get(str(job_a), [])) == {"tailor_resume", "analyze_job"}
    assert set(data.get(str(job_b), [])) == {"tailor_resume"}
    # scheduler-level op with no target_job_id must not appear as a value anywhere
    assert "scrape_all" not in [jt for types in data.values() for jt in types]


def test_in_flight_filters_by_job_ids(api_client, test_db, monkeypatch):
    """?job_ids=<id> returns only that job's entry."""
    _seed(test_db)
    job_a, job_b = uuid.uuid4(), uuid.uuid4()
    _install_fake_running(monkeypatch, [
        (f"tailor_resume:{job_a}", "tailor_resume", job_a),
        (f"tailor_resume:{job_b}", "tailor_resume", job_b),
    ])
    resp = api_client.get(f"/api/monitor/in-flight?job_ids={job_a}")
    assert resp.status_code == 200
    data = resp.json()
    assert str(job_a) in data
    assert str(job_b) not in data


def test_in_flight_empty_when_nothing_running(api_client, test_db, monkeypatch):
    _seed(test_db)
    import backend.job_monitor as mon
    monkeypatch.setattr(mon, "_running", {})
    resp = api_client.get("/api/monitor/in-flight")
    assert resp.status_code == 200
    assert resp.json() == {}
