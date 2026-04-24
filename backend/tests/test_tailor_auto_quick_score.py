"""Tailor → auto quick-score chain (Task 5 of 12)."""
import asyncio
import uuid
import pytest
from unittest.mock import AsyncMock

from backend.models.db import Setting, Resume, Job


def _seed(test_db):
    test_db.add(Setting(key="dashboard_api_key", value=""))
    test_db.add(Setting(key="cv_tailor_prompt", value="p {resume_json} {job_description}"))


@pytest.mark.asyncio
async def test_auto_score_launches_when_setting_is_true(test_db, monkeypatch):
    """When tailor_auto_quick_score='true', _tailor_impl launches score_single_job too."""
    _seed(test_db)
    test_db.add(Setting(key="tailor_auto_quick_score", value="true"))

    job = Job(external_id="chain1", content_hash="c1", company="Acme", title="PM", description="jd")
    test_db.add(job)
    test_db.flush()
    base = Resume(name="Base", is_base=True, template="inter",
                  json_data={"summary": "s", "experience": [], "skills": {}})
    test_db.add(base)
    test_db.commit()

    async def fake_call(prompt, system, max_tokens):
        return {"text": '{"summary":"tailored"}', "usage": {}}
    monkeypatch.setattr("backend.analyzer.llm_client.call_cv_tailor_llm", fake_call)

    launched: list[tuple[str, str | None]] = []

    def recorder(job_type, *a, **kw):
        launched.append((job_type, kw.get("scope_key")))
        return str(uuid.uuid4())
    monkeypatch.setattr("backend.api.routes_resumes.launch_background", recorder, raising=False)

    import backend.api.routes_resumes as rr
    monkeypatch.setattr(rr, "_tailoring_semaphore", None, raising=False)

    await rr._tailor_impl(str(base.id), str(job.id), None)

    assert any(jt == "analyze_job" for jt, _ in launched), f"Expected analyze_job launch, got {launched}"


@pytest.mark.asyncio
async def test_auto_score_skipped_when_setting_is_false(test_db, monkeypatch):
    """When tailor_auto_quick_score='false', no extra launch."""
    _seed(test_db)
    test_db.add(Setting(key="tailor_auto_quick_score", value="false"))

    job = Job(external_id="chain2", content_hash="c2", company="Acme", title="PM", description="jd")
    test_db.add(job)
    test_db.flush()
    base = Resume(name="Base", is_base=True, template="inter",
                  json_data={"summary": "s", "experience": [], "skills": {}})
    test_db.add(base)
    test_db.commit()

    async def fake_call(prompt, system, max_tokens):
        return {"text": '{"summary":"tailored"}', "usage": {}}
    monkeypatch.setattr("backend.analyzer.llm_client.call_cv_tailor_llm", fake_call)

    launched = []

    def recorder(job_type, *a, **kw):
        launched.append(job_type)
        return str(uuid.uuid4())
    monkeypatch.setattr("backend.api.routes_resumes.launch_background", recorder, raising=False)

    import backend.api.routes_resumes as rr
    monkeypatch.setattr(rr, "_tailoring_semaphore", None, raising=False)

    await rr._tailor_impl(str(base.id), str(job.id), None)

    assert "analyze_job" not in launched, f"Expected no analyze_job launch, got {launched}"
