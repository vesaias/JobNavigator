"""Persona-as-virtual-Resume scoring helpers."""
import pytest
from backend.models.db import Persona
from backend.analyzer import cv_scorer


def test_get_persona_text_empty_returns_empty_dict(test_db):
    """No persona row → {}."""
    out = cv_scorer._get_persona_text(test_db)
    assert out == {}


def test_get_persona_text_blank_resume_content_returns_empty_dict(test_db):
    """Persona row with empty resume_content → {} (don't return blank entry)."""
    test_db.add(Persona(id=1, resume_content={}))
    test_db.commit()
    out = cv_scorer._get_persona_text(test_db)
    assert out == {}


def test_get_persona_text_returns_persona_keyed_dict(test_db):
    """Persona with resume_content → {'Persona': flattened_text}."""
    test_db.add(Persona(id=1, resume_content={
        "summary": "Senior PM with 10 years of FinTech experience.",
        "experience": [{"title": "PM", "company": "Acme", "dates": "2020-2024",
                        "bullets": ["Shipped X", "Led Y"]}],
    }))
    test_db.commit()
    out = cv_scorer._get_persona_text(test_db)
    assert list(out.keys()) == ["Persona"]
    assert "Senior PM" in out["Persona"]
    assert "Shipped X" in out["Persona"]


from backend.models.db import Resume, Setting, Company
import uuid


def _seed_persona(db, summary="P-summary"):
    db.add(Persona(id=1, resume_content={"summary": summary}))
    db.commit()


def _seed_resume(db, name="PM"):
    r = Resume(id=uuid.uuid4(), name=name, is_base=True,
               json_data={"summary": f"{name}-summary"})
    db.add(r)
    db.commit()
    return r


def test_get_resume_texts_includes_persona_when_populated(test_db):
    _seed_resume(test_db, "PM")
    _seed_persona(test_db)
    out = cv_scorer._get_resume_texts(test_db)
    assert "PM" in out
    assert "Persona" in out


def test_get_resume_texts_omits_persona_when_empty(test_db):
    _seed_resume(test_db, "PM")
    out = cv_scorer._get_resume_texts(test_db)
    assert "PM" in out
    assert "Persona" not in out


def test_get_default_resume_persona_id(test_db):
    _seed_resume(test_db, "PM")
    _seed_persona(test_db)
    test_db.add(Setting(key="default_resume_id", value="persona"))
    test_db.commit()
    out = cv_scorer._get_default_resume(test_db)
    assert list(out.keys()) == ["Persona"]


def test_get_resume_texts_for_company_persona_in_selection(test_db):
    r = _seed_resume(test_db, "PM")
    _seed_persona(test_db)
    company = Company(id=uuid.uuid4(), name="Acme", selected_resume_ids=["persona"])
    test_db.add(company)
    test_db.commit()
    out = cv_scorer._get_resume_texts_for_company(test_db, company)
    assert list(out.keys()) == ["Persona"]


def test_get_resume_texts_for_company_mixed_selection(test_db):
    r = _seed_resume(test_db, "PM")
    _seed_persona(test_db)
    company = Company(id=uuid.uuid4(), name="Acme",
                      selected_resume_ids=[str(r.id), "persona"])
    test_db.add(company)
    test_db.commit()
    out = cv_scorer._get_resume_texts_for_company(test_db, company)
    assert "PM" in out
    assert "Persona" in out


from unittest.mock import patch, AsyncMock
from backend.models.db import Job


@pytest.mark.asyncio
async def test_score_single_job_persona_id_uses_persona_text(test_db, monkeypatch):
    """score_single_job(cv_ids=['persona']) flattens persona.resume_content into the LLM call."""
    job = Job(id=uuid.uuid4(), title="PM", company="Acme",
              external_id="ext-persona-test",
              description="Looking for a PM with FinTech experience")
    test_db.add(job)
    _seed_persona(test_db, summary="Strong FinTech PM")
    test_db.commit()
    job_id = str(job.id)

    captured = {}

    async def fake_score_job_sync(job_obj, cv_texts, db=None, depth="full", preloaded_text=None):
        captured["cv_texts"] = cv_texts
        return {"Persona": {"score": 80, "summary": "Good fit"}}

    monkeypatch.setattr("backend.analyzer.cv_scorer.score_job_sync", fake_score_job_sync)
    monkeypatch.setattr("backend.analyzer.cv_scorer._get_job_text", AsyncMock(return_value="JD text"))

    await cv_scorer.score_single_job(job_id, cv_ids=["persona"], depth="full")

    assert "Persona" in captured["cv_texts"]
    assert "Strong FinTech PM" in captured["cv_texts"]["Persona"]
