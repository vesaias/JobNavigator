"""Tailor → auto quick-score chain."""
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


# ── the tailor response announces the chained score ─────────────────────────

@pytest.mark.parametrize("value,expected", [
    ("off", None), ("false", None), ("0", None),
    ("light", "light"), ("true", "light"), ("", "light"),
    ("full", "full"), ("nonsense", "light"),
])
def test_resolve_chain_score_depth(test_db, value, expected):
    """Setting `tailor_auto_quick_score` (seeded default 'light') maps to a depth."""
    import backend.api.routes_resumes as rr
    test_db.add(Setting(key="tailor_auto_quick_score", value=value))
    test_db.commit()
    assert rr._resolve_chain_score_depth(test_db) == expected


def test_resolve_chain_score_depth_defaults_to_light_when_unset(test_db):
    import backend.api.routes_resumes as rr
    assert rr._resolve_chain_score_depth(test_db) == "light"


@pytest.mark.asyncio
async def test_tailor_response_reports_chain_score(test_db, monkeypatch):
    """POST /resumes/tailor tells the UI whether a score will follow, and at what depth."""
    import backend.api.routes_resumes as rr

    _seed(test_db)
    test_db.add(Setting(key="tailor_auto_quick_score", value="full"))
    job = Job(external_id="chain3", content_hash="c3", company="Acme", title="PM", description="jd")
    test_db.add(job)
    test_db.flush()
    base = Resume(name="Base", is_base=True, template="inter",
                  json_data={"summary": "s", "experience": [], "skills": {}})
    test_db.add(base)
    test_db.commit()

    monkeypatch.setattr(rr, "launch_background",
                        lambda *a, **kw: str(uuid.uuid4()), raising=False)

    resp = await rr.tailor_resume({"base_resume_id": str(base.id), "job_id": str(job.id)}, db=test_db)
    assert resp["chain_score"] == "full"

    # A freeform tailor has no job to score against, so nothing is chained.
    resp = await rr.tailor_resume({"base_resume_id": str(base.id),
                                   "job_description": "a pasted description"}, db=test_db)
    assert resp["chain_score"] == "off"


@pytest.mark.asyncio
async def test_tailor_response_reports_off_when_chain_disabled(test_db, monkeypatch):
    import backend.api.routes_resumes as rr

    _seed(test_db)
    test_db.add(Setting(key="tailor_auto_quick_score", value="off"))
    job = Job(external_id="chain4", content_hash="c4", company="Acme", title="PM", description="jd")
    test_db.add(job)
    test_db.flush()
    base = Resume(name="Base", is_base=True, template="inter",
                  json_data={"summary": "s", "experience": [], "skills": {}})
    test_db.add(base)
    test_db.commit()

    monkeypatch.setattr(rr, "launch_background",
                        lambda *a, **kw: str(uuid.uuid4()), raising=False)

    resp = await rr.tailor_resume({"base_resume_id": str(base.id), "job_id": str(job.id)}, db=test_db)
    assert resp["chain_score"] == "off"
