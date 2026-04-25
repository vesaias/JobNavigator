"""POST /api/analyze/{job_id} must thread target_job_id so the per-job monitor sees it."""
import uuid
from unittest.mock import patch
import pytest
from backend.models.db import Job, Setting


@pytest.mark.asyncio
async def test_analyze_endpoint_threads_target_job_id(test_db, api_client):
    """After POST, /api/monitor/in-flight?job_ids=<id> should return [analyze_job] for that job."""
    # First-run mode: empty dashboard_api_key → no auth required.
    test_db.add(Setting(key="dashboard_api_key", value=""))
    job = Job(id=uuid.uuid4(), title="PM", company="Acme",
              description="Looking for a PM", external_id="ext-target-test")
    test_db.add(job)
    test_db.commit()
    job_id = str(job.id)

    # Stub score_single_job to a slow no-op so we can observe the in-flight registration
    # without invoking the LLM.
    async def slow_noop(*args, **kwargs):
        import asyncio
        await asyncio.sleep(0.5)

    with patch("backend.analyzer.cv_scorer.score_single_job", slow_noop):
        resp = api_client.post(f"/api/analyze/{job_id}?depth=light", json={"cv_ids": []})
        assert resp.status_code == 202

        # Immediately query the per-job monitor — the run should be visible.
        monitor_resp = api_client.get(f"/api/monitor/in-flight?job_ids={job_id}")
        assert monitor_resp.status_code == 200
        data = monitor_resp.json()
        assert job_id in data, f"Run not visible to monitor (target_job_id missing): {data}"
        assert "analyze_job" in data[job_id]
