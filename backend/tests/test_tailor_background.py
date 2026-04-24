"""Tailoring semaphore + background-job behavior (Task 3 of 12)."""
import asyncio
import pytest
from unittest.mock import AsyncMock

from backend.models.db import Setting


def test_semaphore_default_is_two(test_db, monkeypatch):
    """Absent setting → limit 2."""
    import backend.api.routes_resumes as rr
    monkeypatch.setattr(rr, "_tailoring_semaphore", None, raising=False)
    sem = rr._get_tailoring_semaphore()
    assert sem._value == 2


def test_semaphore_reads_setting(test_db, monkeypatch):
    """Setting override is honored."""
    test_db.add(Setting(key="tailoring_max_concurrent", value="5"))
    test_db.commit()
    import backend.api.routes_resumes as rr
    monkeypatch.setattr(rr, "_tailoring_semaphore", None, raising=False)
    sem = rr._get_tailoring_semaphore()
    assert sem._value == 5


def test_reset_clears_cached_semaphore(monkeypatch):
    """reset_tailoring_semaphore() forces re-read on next call."""
    import backend.api.routes_resumes as rr
    monkeypatch.setattr(rr, "_tailoring_semaphore", asyncio.Semaphore(99), raising=False)
    rr.reset_tailoring_semaphore()
    assert rr._tailoring_semaphore is None


@pytest.mark.asyncio
async def test_tailor_endpoint_returns_202_with_run_id(api_client, test_db, monkeypatch):
    """POST /api/resumes/tailor returns 202 + run_id; body never blocks on LLM."""
    from backend.models.db import Resume, Job
    import uuid as _uuid

    test_db.add(Setting(key="dashboard_api_key", value=""))
    test_db.add(Setting(key="cv_tailor_prompt", value="prompt {resume_json} {job_description}"))

    job = Job(external_id="t1", content_hash="t1c", company="Acme", title="PM",
              description="Looking for PM with 3 years exp")
    test_db.add(job)
    test_db.flush()
    base = Resume(name="Base", is_base=True, template="inter",
                  json_data={"summary": "s", "experience": [], "skills": {}})
    test_db.add(base)
    test_db.commit()

    # Stub the LLM so the impl can't block; we're testing the plumbing
    import backend.api.routes_resumes as rr
    async def fake_call(prompt, system, max_tokens):
        return {"text": '{"summary":"tailored"}', "usage": {}}
    monkeypatch.setattr("backend.analyzer.llm_client.call_cv_tailor_llm", fake_call)
    monkeypatch.setattr(rr, "_tailoring_semaphore", None, raising=False)
    import backend.job_monitor as mon
    monkeypatch.setattr(mon, "_running", {})

    resp = api_client.post(
        "/api/resumes/tailor",
        json={"base_resume_id": str(base.id), "job_id": str(job.id)},
    )
    assert resp.status_code == 202
    body = resp.json()
    assert "run_id" in body
    assert body.get("status") == "running"


@pytest.mark.asyncio
async def test_tailor_creates_job_run_with_target_job_id(api_client, test_db, monkeypatch):
    """Launched JobRun has target_job_id set to the Job we're tailoring for."""
    from backend.models.db import Resume, Job, JobRun

    test_db.add(Setting(key="dashboard_api_key", value=""))
    test_db.add(Setting(key="cv_tailor_prompt", value="prompt {resume_json} {job_description}"))

    job = Job(external_id="t2", content_hash="t2c", company="Acme", title="PM", description="jd")
    test_db.add(job)
    test_db.flush()
    base = Resume(name="Base", is_base=True, template="inter",
                  json_data={"summary": "s", "experience": [], "skills": {}})
    test_db.add(base)
    test_db.commit()

    async def fake_call(prompt, system, max_tokens):
        return {"text": '{"summary":"tailored"}', "usage": {}}
    monkeypatch.setattr("backend.analyzer.llm_client.call_cv_tailor_llm", fake_call)
    import backend.job_monitor as mon
    monkeypatch.setattr(mon, "_running", {})
    import backend.api.routes_resumes as rr
    monkeypatch.setattr(rr, "_tailoring_semaphore", None, raising=False)

    resp = api_client.post(
        "/api/resumes/tailor",
        json={"base_resume_id": str(base.id), "job_id": str(job.id)},
    )
    assert resp.status_code == 202

    await asyncio.sleep(0.2)  # let wrapper run + finish

    test_db.expire_all()
    row = test_db.query(JobRun).filter(JobRun.job_type == "tailor_resume").first()
    assert row is not None
    assert row.target_job_id == job.id
