"""End-to-end: tailor endpoint → in-flight map → completion (Task 12 of 12)."""
import asyncio
import uuid
import pytest

from backend.models.db import Setting, Resume, Job


@pytest.mark.asyncio
async def test_tailor_end_to_end(api_client, test_db, monkeypatch):
    test_db.add(Setting(key="dashboard_api_key", value=""))
    test_db.add(Setting(key="cv_tailor_prompt", value="p {resume_json} {job_description}"))
    test_db.add(Setting(key="tailor_auto_quick_score", value="false"))  # keep test simple

    job = Job(external_id="e2e1", content_hash="e2e1c", company="Acme", title="PM", description="jd")
    test_db.add(job)
    test_db.flush()
    base = Resume(name="Base", is_base=True, template="inter",
                  json_data={"summary": "s", "experience": [], "skills": {}})
    test_db.add(base)
    test_db.commit()

    # Slow-but-finishing LLM stub — blocks until we flip the event.
    call_started = asyncio.Event()
    call_finish = asyncio.Event()

    async def fake_call(prompt, system, max_tokens):
        call_started.set()
        await call_finish.wait()
        return {"text": '{"summary":"tailored"}', "usage": {}}
    monkeypatch.setattr("backend.analyzer.llm_client.call_cv_tailor_llm", fake_call)

    import backend.job_monitor as mon
    monkeypatch.setattr(mon, "_running", {})
    import backend.api.routes_resumes as rr
    monkeypatch.setattr(rr, "_tailoring_semaphore", None, raising=False)

    # Kick off tailor
    resp = api_client.post(
        "/api/resumes/tailor",
        json={"base_resume_id": str(base.id), "job_id": str(job.id)},
    )
    assert resp.status_code == 202

    # Wait until the wrapper entered the LLM call
    await asyncio.wait_for(call_started.wait(), timeout=5)

    # While running: /in-flight should show tailor_resume for this job
    resp = api_client.get(f"/api/monitor/in-flight?job_ids={job.id}")
    assert resp.status_code == 200
    assert "tailor_resume" in resp.json().get(str(job.id), [])

    # /jobs should also expose in_flight
    resp = api_client.get("/api/jobs")
    row = next(r for r in resp.json()["jobs"] if r["id"] == str(job.id))
    assert "tailor_resume" in row["in_flight"]

    # Let the LLM finish + wrapper commit
    call_finish.set()
    await asyncio.sleep(0.3)

    # After completion: in-flight empty, tailored resume exists
    resp = api_client.get(f"/api/monitor/in-flight?job_ids={job.id}")
    assert resp.json() == {}

    test_db.expire_all()
    resumes = test_db.query(Resume).filter(Resume.parent_id == base.id).all()
    assert len(resumes) == 1
    assert resumes[0].job_id == job.id
