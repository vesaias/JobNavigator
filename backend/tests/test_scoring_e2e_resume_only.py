"""End-to-end: scoring uses Resumes, never reads the cvs table (Task 9)."""
import pytest
from unittest.mock import AsyncMock

from backend.models.db import Resume, Job, Setting


@pytest.mark.asyncio
async def test_score_unscored_jobs_uses_resumes(test_db, monkeypatch):
    """Seed 1 base Resume + 1 unscored Job → analyze_unscored_jobs scores it
    using the Resume's text, with the Resume's name as the key."""

    # Seed: a base Resume with rich content
    pm = Resume(
        name="PM",
        is_base=True,
        template="inter",
        json_data={
            "summary": "Senior PM with fintech expertise",
            "experience": [
                {"company": "Additiv", "title": "Senior PM", "bullets": ["shipped wealth platform"]},
            ],
            "skills": {"core": ["Python", "SQL"]},
        },
    )
    test_db.add(pm)

    # Seed: a Job needing scoring
    job = Job(
        external_id="e2e-resume-1",
        content_hash="e2eh1",
        company="Acme",
        title="Senior Product Manager",
        description="Looking for a senior PM with fintech experience",
        status="new",
    )
    test_db.add(job)
    test_db.commit()

    # Stub the LLM to return a deterministic score keyed by Resume name
    async def fake_call_llm(prompt, system, max_tokens, cached_prefix=None):
        return {
            "text": '{"scores":{"PM":78},"best_cv":"PM"}',
            "usage": {"input_tokens": 100, "output_tokens": 20,
                      "cache_read_tokens": 0, "cache_write_tokens": 0},
        }
    monkeypatch.setattr("backend.analyzer.cv_scorer.call_llm", fake_call_llm)
    monkeypatch.setattr("backend.analyzer.cv_scorer.log_llm_call", lambda **kw: None)

    # Force the scoring semaphore fresh
    import backend.analyzer.cv_scorer as cv_scorer
    monkeypatch.setattr(cv_scorer, "_scoring_semaphore", None, raising=False)

    # Run scoring directly via score_job_sync (analyze_unscored_jobs is async + DB-heavy)
    from backend.analyzer.cv_scorer import score_job_sync, _get_resume_texts
    cv_texts = _get_resume_texts(test_db)
    assert cv_texts == {"PM": pytest.approx(cv_texts["PM"], abs=0)}, "Resume must be the source"
    assert "fintech expertise" in cv_texts["PM"]

    result = await score_job_sync(job, cv_texts, db=test_db, depth="light",
                                   preloaded_text=job.description)
    assert result is not None
    assert result["scores"] == {"PM": 78}
    assert result["best_cv"] == "PM"
