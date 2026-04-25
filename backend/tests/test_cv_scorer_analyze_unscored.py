"""Tests for cv_scorer.analyze_unscored_jobs — entity filter + default CV fallback + no-text skip."""
import pytest
import asyncio
from sqlalchemy import null as sa_null
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def scorer_ready_db(test_db, monkeypatch):
    """In-memory DB with Setting rows scorer needs + SessionLocal patched."""
    from backend.models.db import Setting, CV

    # Core settings required by _score_job_inner
    settings = [
        ("scoring_rubric", "RUBRIC TEXT"),
        ("scoring_output_light", 'JSON: {"scores": {CV_NAMES_HERE}, "best_cv": "CV_NAME"}'),
        ("scoring_output_full", "FULL SCHEMA CV_NAMES_HERE CV_NAME"),
        ("llm_model", "claude-sonnet-4-6"),
        ("llm_provider", "claude_api"),
        ("prompt_caching_enabled", "true"),
        ("scoring_default_depth", "light"),
        ("fit_score_threshold", "9999"),  # disable Telegram alerts in tests
    ]
    for k, v in settings:
        test_db.add(Setting(key=k, value=v))

    # Seed a default CV (used when company has no selected_resume_ids)
    cv = CV(
        version="Default",
        filename="default.pdf",
        pdf_data=b"x",
        extracted_text="I am a product manager with 5 years experience at scale.",
        page_count=1,
    )
    test_db.add(cv)
    test_db.commit()

    # Point the default_cv_id setting at the seeded CV
    test_db.add(Setting(key="default_cv_id", value=str(cv.id)))
    test_db.commit()

    # Patch SessionLocal used inside cv_scorer so the module sees the test DB
    TestSession = sessionmaker(bind=test_db.get_bind())
    import backend.analyzer.cv_scorer as scorer
    monkeypatch.setattr(scorer, "SessionLocal", TestSession)

    # Fresh semaphore per test (avoid leaking state between tests)
    monkeypatch.setattr(scorer, "_get_scoring_semaphore",
                        lambda: asyncio.Semaphore(5))

    # analyze_unscored_jobs builds a query using `text("'{}'::jsonb")` which is
    # Postgres-specific syntax and fails under SQLite. Rewrite the `text()` call
    # inside the cv_scorer module's import path so it emits a SQLite-compatible
    # no-op predicate instead (matches no rows — empty string is never a valid
    # default for cv_scores).
    from sqlalchemy import text as _sa_text, sql as _sa_sql
    def _safe_text(expr):
        if expr == "'{}'::jsonb":
            # Empty-string literal — matches no real cv_scores rows under SQLite
            return _sa_text("''")
        return _sa_text(expr)
    # The function does `from sqlalchemy import ... text` inside the function body,
    # so patch the sqlalchemy module attribute.
    import sqlalchemy as _sa
    monkeypatch.setattr(_sa, "text", _safe_text)

    return {"db": test_db, "Session": TestSession, "cv": cv}


@pytest.mark.asyncio
async def test_analyze_unscored_jobs_only_scores_entities_with_auto_scoring(scorer_ready_db, monkeypatch):
    """Jobs from companies with auto_scoring_depth='off' should be skipped.

    Jobs from companies with auto_scoring_depth='light' should be scored.
    """
    from backend.models.db import Company, Job

    db = scorer_ready_db["db"]

    # Two companies: one with scoring enabled ('light'), one with 'off'
    co_on = Company(name="ScoreOnCo", scrape_urls=[], auto_scoring_depth="light")
    co_off = Company(name="ScoreOffCo", scrape_urls=[], auto_scoring_depth="off")
    db.add(co_on)
    db.add(co_off)
    db.commit()

    # Use unique, distinguishable descriptions so we can tell which job was scored
    desc_on = "SCORE_ME_ON: Senior product manager position. " + ("Detail. " * 10)
    desc_off = "SCORE_ME_OFF: Senior product manager position. " + ("Detail. " * 10)

    # cv_scores=sa_null() so the IS NULL branch of the unscored filter matches under SQLite.
    # (The PG `'{}'::jsonb` branch is patched to a no-op in the fixture.)
    job_on = Job(external_id="j1", content_hash="h1", company="ScoreOnCo",
                 title="Senior PM", url="https://x.com/1", status="new",
                 description=desc_on, cv_scores=sa_null())
    job_off = Job(external_id="j2", content_hash="h2", company="ScoreOffCo",
                  title="Senior PM", url="https://x.com/2", status="new",
                  description=desc_off, cv_scores=sa_null())
    db.add(job_on)
    db.add(job_off)
    db.commit()

    scored_markers = []

    async def fake_call_llm(prompt, system, max_tokens, cached_prefix=None):
        if "SCORE_ME_ON" in prompt:
            scored_markers.append("on")
        if "SCORE_ME_OFF" in prompt:
            scored_markers.append("off")
        return {
            "text": '{"scores":{"Default":75},"best_cv":"Default"}',
            "usage": {"input_tokens": 100, "output_tokens": 20,
                      "cache_read_tokens": 0, "cache_write_tokens": 0},
        }

    monkeypatch.setattr("backend.analyzer.cv_scorer.call_llm", fake_call_llm)
    monkeypatch.setattr("backend.analyzer.cv_scorer.log_llm_call", lambda **kw: None)

    from backend.analyzer.cv_scorer import analyze_unscored_jobs
    await analyze_unscored_jobs(status="new")

    assert "on" in scored_markers, (
        f"Expected ScoreOnCo job to be scored (auto_scoring_depth='light'); "
        f"scored_markers={scored_markers}"
    )
    assert "off" not in scored_markers, (
        f"Expected ScoreOffCo job to be SKIPPED (auto_scoring_depth='off'); "
        f"scored_markers={scored_markers}"
    )


@pytest.mark.asyncio
async def test_analyze_unscored_skips_jobs_with_no_text(scorer_ready_db, monkeypatch):
    """A job with no description, no cached page, and no URL should be marked _skipped
    (not sent to the LLM). This is the 'true skip' / sentinel code path.

    Note: SPA-garbage detection happens inside `_fetch_job_description` (live fetch),
    not inside `analyze_unscored_jobs` — a job whose stored description is JSON garbage
    would still be scored. This test verifies the real no-text skip path instead.
    """
    from backend.models.db import Company, Job

    db = scorer_ready_db["db"]

    co = Company(name="NoTextCo", scrape_urls=[], auto_scoring_depth="light")
    db.add(co)
    db.commit()

    # No description, no cached page, no URL → _get_job_text returns None
    no_text_job = Job(
        external_id="nt1", content_hash="hnt1", company="NoTextCo",
        title="Senior PM", url=None, status="new",
        description=None, cv_scores=sa_null(),
    )
    db.add(no_text_job)
    db.commit()

    call_llm_invocations = []

    async def fake_call_llm(prompt, system, max_tokens, cached_prefix=None):
        call_llm_invocations.append(True)
        return {
            "text": '{"scores":{"Default":75},"best_cv":"Default"}',
            "usage": {"input_tokens": 100, "output_tokens": 20,
                      "cache_read_tokens": 0, "cache_write_tokens": 0},
        }

    monkeypatch.setattr("backend.analyzer.cv_scorer.call_llm", fake_call_llm)
    monkeypatch.setattr("backend.analyzer.cv_scorer.log_llm_call", lambda **kw: None)

    from backend.analyzer.cv_scorer import analyze_unscored_jobs
    await analyze_unscored_jobs(status="new")

    assert not call_llm_invocations, "Expected no LLM call for job with no text"

    # The job should have been tagged with the skip sentinel so it is not retried.
    db.refresh(no_text_job)
    assert no_text_job.cv_scores == {"_skipped": "no_text_available"}, (
        f"Expected _skipped sentinel, got cv_scores={no_text_job.cv_scores}"
    )


@pytest.mark.asyncio
async def test_analyze_unscored_uses_default_cv_when_no_selected(scorer_ready_db, monkeypatch):
    """A company with empty selected_resume_ids falls back to the default CV from settings."""
    from backend.models.db import Company, Job

    db = scorer_ready_db["db"]

    # selected_resume_ids=[] → fallback to default CV
    co = Company(name="DefaultCVCo", scrape_urls=[], auto_scoring_depth="light",
                 selected_resume_ids=[])
    db.add(co)
    db.commit()

    job = Job(external_id="d1", content_hash="hd1", company="DefaultCVCo",
              title="Senior PM", url="https://x.com/d1", status="new",
              description="Senior product manager position. " * 10,
              cv_scores=sa_null())
    db.add(job)
    db.commit()

    captured = {}

    async def fake_call_llm(prompt, system, max_tokens, cached_prefix=None):
        captured["prefix"] = cached_prefix or ""
        return {
            "text": '{"scores":{"Default":75},"best_cv":"Default"}',
            "usage": {"input_tokens": 100, "output_tokens": 20,
                      "cache_read_tokens": 0, "cache_write_tokens": 0},
        }

    monkeypatch.setattr("backend.analyzer.cv_scorer.call_llm", fake_call_llm)
    monkeypatch.setattr("backend.analyzer.cv_scorer.log_llm_call", lambda **kw: None)

    from backend.analyzer.cv_scorer import analyze_unscored_jobs
    await analyze_unscored_jobs(status="new")

    # The default CV's extracted_text should be embedded in the cached prefix
    prefix = captured.get("prefix", "")
    assert "product manager with 5 years experience" in prefix.lower(), (
        f"Expected default CV text in cached_prefix; got: {prefix[:300]}"
    )
