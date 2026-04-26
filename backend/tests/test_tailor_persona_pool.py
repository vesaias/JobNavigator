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
    # Persona summary is NOT appended to the base summary anymore — base resume's
    # summary is its tuned framing; mixing voices confuses the LLM.
    assert "Persona summary fragment" not in prompt, \
        "Persona summary should NOT be merged into base summary"


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


# ── Tests for the new persona-merge helpers ─────────────────────────────────

from backend.api.routes_resumes import (
    _normalize_company, _normalize_title_root,
    _bullet_jaccard, _numeric_anchors, _is_duplicate_bullet,
    _merge_persona_experience,
)


def test_normalize_company_strips_suffix_and_case():
    assert _normalize_company("Acme Inc.") == "acme"
    assert _normalize_company("ACME CORP") == "acme"
    assert _normalize_company("  Acme  ") == "acme"
    assert _normalize_company("Foo GmbH") == "foo"
    assert _normalize_company("") == ""
    assert _normalize_company(None) == ""


def test_normalize_title_root_collapses_pm_variants():
    assert _normalize_title_root("Senior Project Manager") == "manager"
    assert _normalize_title_root("Senior Product Manager") == "manager"
    assert _normalize_title_root("Senior Technical Program Manager") == "manager"
    assert _normalize_title_root("Software Engineer") == "engineer"
    assert _normalize_title_root("Data Analyst") == "analyst"
    assert _normalize_title_root("Operations Intern") == "intern"
    assert _normalize_title_root("Janitor") == "janitor"


def test_numeric_anchors_extracts_metrics():
    assert _numeric_anchors("Reduced errors by 30%") == {"30%"}
    assert _numeric_anchors("Shipped $350M+ to 40,000+ clients") == {"$350M+", "40,000+"}
    assert _numeric_anchors("No numbers here") == set()


def test_bullet_jaccard_basic():
    j = _bullet_jaccard("Shipping the platform", "Shipped the platform")
    assert j > 0.9


def test_is_duplicate_bullet_identical():
    a = "Reduced **P1/P2 incident impact by 40%** by designing structured post-release"
    b = "Reduced **P1/P2 incident impact by 40%** by designing structured post-release"
    assert _is_duplicate_bullet(a, b) is True


def test_is_duplicate_bullet_unrelated():
    assert _is_duplicate_bullet(
        "Architected the wealth platform",
        "Designed an unrelated thing about banking",
    ) is False


def test_merge_normalizes_company_and_title():
    """'Senior Project Manager @ Additiv' + 'Senior Product Manager @ Additiv' merge
    into ONE entry — same company, both roots collapse to 'manager'."""
    base = [{"title": "Senior Project Manager", "company": "Additiv", "dates": "2023-2024",
             "bullets": ["Built X"]}]
    persona = [{"title": "Senior Product Manager", "company": "Additiv", "dates": "2023-2024",
                "bullets": ["Built Y"]}]
    out = _merge_persona_experience(base, persona)
    assert len(out) == 1
    assert "Built X" in out[0]["bullets"]
    assert "Built Y" in out[0]["bullets"]


def test_merge_drops_duplicate_bullets():
    base = [{"title": "PM", "company": "Acme",
             "bullets": ["Reduced **P1/P2 incident impact by 40%** via post-release"]}]
    persona = [{"title": "PM", "company": "Acme",
                "bullets": ["Reduced **P1/P2 incident impact by 40%** via post-release"]}]
    out = _merge_persona_experience(base, persona)
    assert len(out) == 1
    assert len(out[0]["bullets"]) == 1


def test_merge_keeps_distinct_bullets():
    base = [{"title": "PM", "company": "Acme",
             "bullets": ["Built SQL synthetic data generator for staging"]}]
    persona = [{"title": "PM", "company": "Acme",
                "bullets": ["Led 12-engineer cross-functional team"]}]
    out = _merge_persona_experience(base, persona)
    assert len(out) == 1
    assert any("12-engineer" in b for b in out[0]["bullets"])
    assert any("SQL" in b for b in out[0]["bullets"])


def test_merge_appends_new_companies():
    base = [{"title": "PM", "company": "Acme", "bullets": ["a"]}]
    persona = [{"title": "PM", "company": "BetaCo", "bullets": ["b"]}]
    out = _merge_persona_experience(base, persona)
    assert len(out) == 2
    assert {e["company"] for e in out} == {"Acme", "BetaCo"}


def test_merge_company_suffix_normalized():
    base = [{"title": "PM", "company": "Acme Inc.", "bullets": ["base"]}]
    persona = [{"title": "PM", "company": "Acme", "bullets": ["persona"]}]
    out = _merge_persona_experience(base, persona)
    assert len(out) == 1


def test_merge_does_not_mutate_input():
    base = [{"title": "PM", "company": "Acme", "bullets": ["a"]}]
    persona = [{"title": "PM", "company": "Acme", "bullets": ["b"]}]
    base_snapshot = [{**e, "bullets": list(e["bullets"])} for e in base]
    _merge_persona_experience(base, persona)
    assert base == base_snapshot
