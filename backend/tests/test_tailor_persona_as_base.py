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


@pytest.mark.asyncio
async def test_tailor_persona_uses_persona_tailor_prompt(test_db, monkeypatch):
    """When base is persona AND persona_tailor_prompt is set, that prompt is used (not cv_tailor_prompt)."""
    job = Job(id=uuid.uuid4(), title="PM", company="Acme",
              description="JD", external_id="ext-persona-prompt")
    persona = Persona(id=1, resume_content={
        "summary": "S",
        "experience": [{"title": "PM", "company": "X", "dates": "2024", "bullets": ["b"]}],
        "skills": {},
    })
    test_db.add_all([job, persona])
    test_db.add(Setting(key="cv_tailor_prompt",
                        value="GENERIC PROMPT {resume_json} {job_description}"))
    test_db.add(Setting(key="persona_tailor_prompt",
                        value="PERSONA SPECIFIC {resume_json} {job_description}"))
    test_db.commit()

    captured = {}

    async def fake_call(prompt, system, max_tokens=3000):
        captured["prompt"] = prompt
        return {"text": '{"summary": "x", "experience": [{"bullets": ["y"]}], "skills": {}}',
                "usage": {}}

    monkeypatch.setattr("backend.analyzer.llm_client.call_cv_tailor_llm", fake_call)

    await routes_resumes._tailor_impl("persona", str(job.id), None)

    assert "PERSONA SPECIFIC" in captured["prompt"]
    assert "GENERIC PROMPT" not in captured["prompt"]


@pytest.mark.asyncio
async def test_tailor_persona_falls_back_when_persona_prompt_empty(test_db, monkeypatch):
    """If persona_tailor_prompt is empty/missing, _tailor_impl falls back to cv_tailor_prompt for persona too."""
    job = Job(id=uuid.uuid4(), title="PM", company="Acme",
              description="JD", external_id="ext-fallback")
    persona = Persona(id=1, resume_content={
        "summary": "S",
        "experience": [{"title": "PM", "company": "X", "dates": "2024", "bullets": ["b"]}],
        "skills": {},
    })
    test_db.add_all([job, persona])
    test_db.add(Setting(key="cv_tailor_prompt",
                        value="GENERIC PROMPT {resume_json} {job_description}"))
    # Note: no persona_tailor_prompt seeded → fallback path
    test_db.commit()

    captured = {}

    async def fake_call(prompt, system, max_tokens=3000):
        captured["prompt"] = prompt
        return {"text": '{"summary": "x", "experience": [{"bullets": ["y"]}], "skills": {}}',
                "usage": {}}

    monkeypatch.setattr("backend.analyzer.llm_client.call_cv_tailor_llm", fake_call)

    await routes_resumes._tailor_impl("persona", str(job.id), None)

    assert "GENERIC PROMPT" in captured["prompt"]


@pytest.mark.asyncio
async def test_tailor_resume_does_not_use_persona_prompt(test_db, monkeypatch):
    """When base is a regular Resume (not persona), persona_tailor_prompt is NOT used."""
    base_resume = Resume(id=uuid.uuid4(), name="PM", is_base=True,
                         json_data={"summary": "s", "experience": [], "skills": {}})
    job = Job(id=uuid.uuid4(), title="PM", company="Acme",
              description="JD", external_id="ext-resume-base")
    test_db.add_all([base_resume, job])
    test_db.add(Setting(key="cv_tailor_prompt",
                        value="GENERIC PROMPT {resume_json} {job_description}"))
    test_db.add(Setting(key="persona_tailor_prompt",
                        value="PERSONA ONLY {resume_json} {job_description}"))
    test_db.commit()

    captured = {}

    async def fake_call(prompt, system, max_tokens=3000):
        captured["prompt"] = prompt
        return {"text": '{"summary": "x", "experience": [], "skills": {}}', "usage": {}}

    monkeypatch.setattr("backend.analyzer.llm_client.call_cv_tailor_llm", fake_call)

    await routes_resumes._tailor_impl(str(base_resume.id), str(job.id), None)

    assert "GENERIC PROMPT" in captured["prompt"]
    assert "PERSONA ONLY" not in captured["prompt"]
