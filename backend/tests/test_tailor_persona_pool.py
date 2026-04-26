"""_tailor_impl must merge Persona.resume_content into the resume_sections dict
sent to the LLM, so the model has access to a richer bullet/skill pool."""
import uuid
import pytest
from backend.models.db import Resume, Persona, Setting, Job
from backend.api import routes_resumes


@pytest.mark.asyncio
async def test_tailor_merges_persona_into_resume_sections(test_db, monkeypatch):
    """When persona has resume_content, the prompt sent to the LLM includes persona bullets/skills."""
    base_resume = Resume(
        id=uuid.uuid4(), name="PM-base", is_base=True,
        json_data={
            "summary": "Base summary.",
            "experience": [
                {"title": "PM", "company": "BaseCo", "dates": "2022-2024",
                 "bullets": ["Base bullet"]},
            ],
            "skills": {"languages": ["Python"]},
        },
    )
    job = Job(id=uuid.uuid4(), title="Senior PM", company="Acme",
              description="Looking for a Senior PM with FinTech experience",
              external_id="ext-tailor-persona")
    persona = Persona(id=1, resume_content={
        "summary": "Persona summary fragment.",
        "experience": [
            {"title": "Sr. PM", "company": "PersonaCo", "dates": "2020-2022",
             "bullets": ["Persona bullet — FinTech specific"]},
        ],
        "skills": {"languages": ["Python", "TypeScript"], "domains": ["FinTech"]},
    })
    test_db.add_all([base_resume, job, persona])
    test_db.add(Setting(key="cv_tailor_prompt",
                        value="Resume:\n{resume_json}\n\nJD:\n{job_description}"))
    test_db.commit()

    captured = {}

    async def fake_call(prompt, system, max_tokens=3000):
        captured["prompt"] = prompt
        captured["system"] = system
        return {"text": '{"summary": "merged", "experience": [], "skills": {}}', "usage": {}}

    monkeypatch.setattr("backend.analyzer.llm_client.call_cv_tailor_llm", fake_call)

    await routes_resumes._tailor_impl(str(base_resume.id), str(job.id), None)

    prompt = captured.get("prompt", "")
    assert "Persona bullet" in prompt, f"Persona experience bullet not in tailor prompt:\n{prompt}"
    assert "FinTech" in prompt, "Persona FinTech skill not merged into tailor prompt"
    assert "TypeScript" in prompt, "Persona language skill not merged"
    assert "Base bullet" in prompt, "Base resume bullet was overwritten"
    assert "Persona summary fragment" in prompt, "Persona summary not merged"


@pytest.mark.asyncio
async def test_tailor_works_when_persona_empty(test_db, monkeypatch):
    """Tailor still works when persona has no resume_content (no merge happens)."""
    base_resume = Resume(
        id=uuid.uuid4(), name="PM-base", is_base=True,
        json_data={"summary": "Just summary",
                   "experience": [{"title": "PM", "company": "X", "dates": "2024",
                                   "bullets": ["b"]}],
                   "skills": {"a": ["b"]}},
    )
    job = Job(id=uuid.uuid4(), title="PM", company="Acme",
              description="JD text", external_id="ext-no-persona")
    test_db.add_all([base_resume, job])
    test_db.add(Setting(key="cv_tailor_prompt",
                        value="Resume:\n{resume_json}\n\nJD:\n{job_description}"))
    test_db.commit()

    async def fake_call(prompt, system, max_tokens=3000):
        return {"text": '{"summary": "x", "experience": [], "skills": {}}', "usage": {}}

    monkeypatch.setattr("backend.analyzer.llm_client.call_cv_tailor_llm", fake_call)

    await routes_resumes._tailor_impl(str(base_resume.id), str(job.id), None)


@pytest.mark.asyncio
async def test_tailor_dedupes_overlapping_experience(test_db, monkeypatch):
    """If persona has an experience entry with same (title, company) as base, no duplicate."""
    base_resume = Resume(
        id=uuid.uuid4(), name="PM-base", is_base=True,
        json_data={
            "summary": "S",
            "experience": [{"title": "PM", "company": "Acme", "dates": "2022-2024",
                            "bullets": ["base"]}],
            "skills": {},
        },
    )
    job = Job(id=uuid.uuid4(), title="PM", company="X",
              description="JD", external_id="ext-dedupe-exp")
    persona = Persona(id=1, resume_content={
        "summary": "",
        "experience": [{"title": "PM", "company": "Acme", "dates": "2022-2024",
                        "bullets": ["persona override"]}],
        "skills": {},
    })
    test_db.add_all([base_resume, job, persona])
    test_db.add(Setting(key="cv_tailor_prompt",
                        value="Resume:\n{resume_json}\n\nJD:\n{job_description}"))
    test_db.commit()

    captured = {}

    async def fake_call(prompt, system, max_tokens=3000):
        captured["prompt"] = prompt
        return {"text": '{"summary": "x", "experience": [], "skills": {}}', "usage": {}}

    monkeypatch.setattr("backend.analyzer.llm_client.call_cv_tailor_llm", fake_call)

    await routes_resumes._tailor_impl(str(base_resume.id), str(job.id), None)

    prompt = captured["prompt"]
    # Base bullet should appear; persona's overlap should NOT add a second PM@Acme entry
    assert prompt.count('"company": "Acme"') == 1
    assert "base" in prompt
