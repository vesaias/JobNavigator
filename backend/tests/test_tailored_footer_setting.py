"""A base résumé's footer choice must not silently disable a new tailored copy."""
import asyncio

import pytest

from backend.models.db import Job, Resume, Setting


@pytest.mark.asyncio
async def test_tailor_resets_base_footer_flag(api_client, test_db, monkeypatch):
    test_db.add(Setting(key="dashboard_api_key", value=""))
    test_db.add(Setting(key="cv_tailor_prompt", value="p {resume_json} {job_description}"))
    test_db.add(Setting(key="tailor_auto_quick_score", value="false"))
    job = Job(external_id="footer-flag", content_hash="footer-flag-hash", company="Acme", title="PM", description="jd")
    test_db.add(job)
    test_db.flush()
    base = Resume(name="Base", is_base=True, template="inter", json_data={
        "summary": "s", "experience": [], "skills": {}, "footer_enabled": False,
    })
    test_db.add(base)
    test_db.commit()

    async def fake_call(prompt, system, max_tokens):
        return {"text": '{"summary":"tailored"}', "usage": {}}

    monkeypatch.setattr("backend.analyzer.llm_client.call_cv_tailor_llm", fake_call)
    import backend.job_monitor as monitor
    monkeypatch.setattr(monitor, "_running", {})
    import backend.api.routes_resumes as routes
    monkeypatch.setattr(routes, "_tailoring_semaphore", None, raising=False)

    response = api_client.post("/api/resumes/tailor", json={"base_resume_id": str(base.id), "job_id": str(job.id)})
    assert response.status_code == 202
    await asyncio.sleep(0.5)
    test_db.expire_all()
    copy = test_db.query(Resume).filter(Resume.parent_id == base.id).one()
    assert "footer_enabled" not in copy.json_data
