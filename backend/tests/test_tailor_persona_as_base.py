"""POST /api/resumes/tailor with base_resume_id='persona' uses Persona.resume_content
as the base, producing a Resume row with parent_id=None."""
import uuid
import pytest
from backend.models.db import Resume, Persona, Setting, Job
from backend.api import routes_resumes


@pytest.mark.asyncio
async def test_tailor_with_persona_as_base(test_db, monkeypatch):
    """base_resume_id='persona' → persona content drives the prompt; output has parent_id=None."""
    job = Job(id=uuid.uuid4(), title="Lead PM", company="Acme",
              description="Need a Lead PM for our FinTech platform",
              external_id="ext-tailor-from-persona")
    persona = Persona(id=1, resume_content={
        "summary": "Persona-only summary.",
        "experience": [
            {"title": "PM", "company": "PersonaCo", "dates": "2020-2024",
             "bullets": ["Persona-only bullet"]},
        ],
        "skills": {"languages": ["Python"]},
    })
    test_db.add_all([job, persona])
    test_db.add(Setting(key="cv_tailor_prompt",
                        value="Resume:\n{resume_json}\n\nJD:\n{job_description}"))
    test_db.commit()

    captured = {}

    async def fake_call(prompt, system, max_tokens=3000):
        captured["prompt"] = prompt
        return {"text": '{"summary": "tailored", "experience": [{"bullets": ["x"]}], "skills": {}}',
                "usage": {}}

    monkeypatch.setattr("backend.analyzer.llm_client.call_cv_tailor_llm", fake_call)

    await routes_resumes._tailor_impl("persona", str(job.id), None)

    # Persona content is in the prompt
    prompt = captured["prompt"]
    assert "Persona-only bullet" in prompt
    assert "Persona-only summary" in prompt

    # Output Resume row exists with parent_id=None and name starts with "Persona →"
    tailored = test_db.query(Resume).filter(Resume.is_base == False).first()
    assert tailored is not None
    assert tailored.parent_id is None
    assert tailored.name.startswith("Persona")
    assert "Acme" in tailored.name


@pytest.mark.asyncio
async def test_tailor_with_persona_as_base_skips_double_merge(test_db, monkeypatch):
    """When persona is the base, the auto-merge block is skipped (no double-include)."""
    job = Job(id=uuid.uuid4(), title="PM", company="X",
              description="JD", external_id="ext-no-double")
    persona = Persona(id=1, resume_content={
        "summary": "S",
        "experience": [{"title": "PM", "company": "C", "dates": "2024",
                        "bullets": ["b1"]}],
        "skills": {},
    })
    test_db.add_all([job, persona])
    test_db.add(Setting(key="cv_tailor_prompt",
                        value="Resume:\n{resume_json}\n\nJD:\n{job_description}"))
    test_db.commit()

    captured = {}

    async def fake_call(prompt, system, max_tokens=3000):
        captured["prompt"] = prompt
        return {"text": '{"summary": "x", "experience": [{"bullets": ["y"]}], "skills": {}}',
                "usage": {}}

    monkeypatch.setattr("backend.analyzer.llm_client.call_cv_tailor_llm", fake_call)

    await routes_resumes._tailor_impl("persona", str(job.id), None)

    prompt = captured["prompt"]
    # Only ONE PM/C entry (no double-merge)
    assert prompt.count('"company": "C"') == 1


def test_tailor_endpoint_rejects_empty_persona(test_db, api_client):
    """POST /resumes/tailor with base_resume_id='persona' but persona has no resume_content → 400."""
    job = Job(id=uuid.uuid4(), title="PM", company="Acme",
              description="JD", external_id="ext-empty-persona")
    test_db.add_all([job, Persona(id=1, resume_content={})])
    test_db.add(Setting(key="dashboard_api_key", value=""))
    test_db.add(Setting(key="cv_tailor_prompt", value="t"))
    test_db.commit()
    resp = api_client.post("/api/resumes/tailor",
                           json={"base_resume_id": "persona", "job_id": str(job.id)})
    assert resp.status_code == 400
    assert "resume_content" in resp.json()["detail"]
