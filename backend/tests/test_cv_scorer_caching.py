"""Tests for cv_scorer prompt split into cached_prefix + per-job JD."""
import asyncio
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class FakeJob:
    def __init__(self, id="job-1", description="Job description here. " * 50):
        self.id = id
        self.description = description
        self.cached_page_text = None
        self.url = None


@pytest.fixture
def scorer_db(monkeypatch):
    """In-memory SQLite with Setting rows needed for scoring."""
    from backend.models.db import Setting, Base
    engine = create_engine("sqlite:///:memory:")
    Setting.__table__.create(engine)
    Session = sessionmaker(bind=engine)

    s = Session()
    s.add(Setting(key="scoring_rubric", value="RUBRIC TEXT"))
    s.add(Setting(key="scoring_output_light",
                  value='OUTPUT JSON: {"scores": {CV_NAMES_HERE}, "best_cv": "CV_NAME"}'))
    s.add(Setting(key="scoring_output_full",
                  value='FULL JSON SCHEMA HERE'))
    s.add(Setting(key="llm_model", value="claude-sonnet-4-6"))
    s.add(Setting(key="llm_provider", value="claude_api"))
    s.commit()
    s.close()

    # Patch SessionLocal in cv_scorer
    from backend.analyzer import cv_scorer
    monkeypatch.setattr(cv_scorer, "SessionLocal", Session)

    # Fresh semaphore per test
    monkeypatch.setattr(cv_scorer, "_get_scoring_semaphore",
                        lambda: asyncio.Semaphore(1))
    return Session


@pytest.mark.asyncio
async def test_score_job_sends_cached_prefix_with_rubric_and_cv(scorer_db, monkeypatch):
    """Rubric + CV text + schema go in cached_prefix, JD goes in the suffix prompt."""
    captured = {}

    async def fake_call_llm(prompt, system, max_tokens, cached_prefix=None):
        captured["prompt"] = prompt
        captured["cached_prefix"] = cached_prefix
        captured["system"] = system
        return {
            "text": '{"scores":{"PM":72},"best_cv":"PM"}',
            "usage": {"input_tokens": 100, "output_tokens": 20,
                      "cache_read_tokens": 0, "cache_write_tokens": 2400},
        }

    monkeypatch.setattr("backend.analyzer.cv_scorer.call_llm", fake_call_llm)
    # Stub the logger so no DB write is attempted
    monkeypatch.setattr("backend.analyzer.cv_scorer.log_llm_call", lambda **kw: None)

    from backend.analyzer import cv_scorer
    job = FakeJob(description="SENIOR PM ROLE job description here.")
    cv_texts = {"PM": "I am a PM with 5 years experience at scale."}

    result = await cv_scorer.score_job_sync(
        job, cv_texts, db=None, depth="light",
        preloaded_text="SENIOR PM ROLE description",
    )

    assert result is not None
    # cached_prefix should contain rubric + CV content + schema
    assert "RUBRIC TEXT" in captured["cached_prefix"]
    assert "I am a PM with 5 years experience" in captured["cached_prefix"]
    assert "OUTPUT JSON" in captured["cached_prefix"]

    # Per-job prompt should contain JOB DESCRIPTION marker but NOT rubric
    assert "SENIOR PM ROLE description" in captured["prompt"]
    assert "RUBRIC TEXT" not in captured["prompt"]
    assert "JOB DESCRIPTION" in captured["prompt"]


@pytest.mark.asyncio
async def test_score_job_logs_usage(scorer_db, monkeypatch):
    """log_llm_call is called with the usage dict + purpose + job_id + success=True."""
    captured_log = {}

    async def fake_call_llm(prompt, system, max_tokens, cached_prefix=None):
        return {
            "text": '{"scores":{"PM":80},"best_cv":"PM"}',
            "usage": {"input_tokens": 500, "output_tokens": 30,
                      "cache_read_tokens": 2400, "cache_write_tokens": 0},
        }

    def fake_log(**kwargs):
        captured_log.update(kwargs)

    monkeypatch.setattr("backend.analyzer.cv_scorer.call_llm", fake_call_llm)
    monkeypatch.setattr("backend.analyzer.cv_scorer.log_llm_call", fake_log)

    from backend.analyzer import cv_scorer
    job = FakeJob()
    await cv_scorer.score_job_sync(job, {"PM": "CV text"}, db=None, depth="light",
                                    preloaded_text="JD text")

    assert captured_log.get("purpose") == "score_light"
    assert captured_log.get("usage", {}).get("input_tokens") == 500
    assert captured_log.get("usage", {}).get("cache_read_tokens") == 2400
    assert captured_log.get("job_id") == job.id
    assert captured_log.get("success") is True


@pytest.mark.asyncio
async def test_score_job_full_depth_uses_score_full_purpose(scorer_db, monkeypatch):
    """depth='full' → purpose='score_full' in log."""
    captured_log = {}

    async def fake_call_llm(prompt, system, max_tokens, cached_prefix=None):
        return {
            "text": '{"scores":{"PM":80},"best_cv":"PM","summary":"good"}',
            "usage": {"input_tokens": 500, "output_tokens": 100,
                      "cache_read_tokens": 0, "cache_write_tokens": 0},
        }

    monkeypatch.setattr("backend.analyzer.cv_scorer.call_llm", fake_call_llm)
    monkeypatch.setattr("backend.analyzer.cv_scorer.log_llm_call",
                        lambda **kw: captured_log.update(kw))

    from backend.analyzer import cv_scorer
    job = FakeJob()
    await cv_scorer.score_job_sync(job, {"PM": "CV"}, db=None, depth="full",
                                    preloaded_text="JD")

    assert captured_log.get("purpose") == "score_full"


@pytest.mark.asyncio
async def test_score_job_respects_prompt_caching_disabled(scorer_db, monkeypatch):
    """When prompt_caching_enabled='false' in settings, cached_prefix is passed as None."""
    from backend.models.db import Setting
    s = scorer_db()
    s.add(Setting(key="prompt_caching_enabled", value="false"))
    s.commit()
    s.close()

    captured = {}

    async def fake_call_llm(prompt, system, max_tokens, cached_prefix=None):
        captured["cached_prefix"] = cached_prefix
        return {
            "text": '{"scores":{"PM":75},"best_cv":"PM"}',
            "usage": {"input_tokens": 100, "output_tokens": 20,
                      "cache_read_tokens": 0, "cache_write_tokens": 0},
        }

    monkeypatch.setattr("backend.analyzer.cv_scorer.call_llm", fake_call_llm)
    monkeypatch.setattr("backend.analyzer.cv_scorer.log_llm_call", lambda **kw: None)

    from backend.analyzer import cv_scorer
    job = FakeJob()
    await cv_scorer.score_job_sync(job, {"PM": "CV text"}, db=None, depth="light",
                                    preloaded_text="JD text")

    assert captured["cached_prefix"] is None


@pytest.mark.asyncio
async def test_score_job_caching_enabled_by_default(scorer_db, monkeypatch):
    """When prompt_caching_enabled is absent (no row) or 'true', cached_prefix is forwarded."""
    captured = {}

    async def fake_call_llm(prompt, system, max_tokens, cached_prefix=None):
        captured["cached_prefix"] = cached_prefix
        return {
            "text": '{"scores":{"PM":75},"best_cv":"PM"}',
            "usage": {"input_tokens": 100, "output_tokens": 20,
                      "cache_read_tokens": 0, "cache_write_tokens": 0},
        }

    monkeypatch.setattr("backend.analyzer.cv_scorer.call_llm", fake_call_llm)
    monkeypatch.setattr("backend.analyzer.cv_scorer.log_llm_call", lambda **kw: None)

    from backend.analyzer import cv_scorer
    job = FakeJob()
    await cv_scorer.score_job_sync(job, {"PM": "CV text"}, db=None, depth="light",
                                    preloaded_text="JD text")

    assert captured["cached_prefix"] is not None
    assert "RUBRIC TEXT" in captured["cached_prefix"]


@pytest.mark.asyncio
async def test_score_job_logs_failure_when_call_llm_raises(scorer_db, monkeypatch):
    """When call_llm raises, log_llm_call still runs with success=False + error."""
    captured_log = {}

    async def fake_call_llm(prompt, system, max_tokens, cached_prefix=None):
        raise RuntimeError("simulated provider outage")

    monkeypatch.setattr("backend.analyzer.cv_scorer.call_llm", fake_call_llm)
    monkeypatch.setattr("backend.analyzer.cv_scorer.log_llm_call",
                        lambda **kw: captured_log.update(kw))

    from backend.analyzer import cv_scorer
    job = FakeJob()
    result = await cv_scorer.score_job_sync(job, {"PM": "CV"}, db=None, depth="light",
                                             preloaded_text="JD")

    assert result is None
    assert captured_log.get("success") is False
    assert "simulated provider outage" in (captured_log.get("error") or "")
    assert captured_log.get("purpose") == "score_light"
    assert captured_log.get("job_id") == job.id


@pytest.mark.asyncio
async def test_score_job_no_cvs_returns_none(scorer_db, monkeypatch):
    """Empty cv_texts dict → _score_job_inner returns None (no scoring attempted)."""
    from backend.analyzer import cv_scorer
    job = FakeJob()
    # Don't stub call_llm — if it's reached, the test should fail
    result = await cv_scorer.score_job_sync(
        job, {}, db=None, depth="light", preloaded_text="JD text",
    )
    assert result is None


@pytest.mark.asyncio
async def test_score_job_llm_error_returns_none_without_skipped_marker(scorer_db, monkeypatch):
    """LLM exception → result is None AND no _skipped sentinel persisted.

    This is the key contract: a transient LLM failure must NOT permanently mark the
    job as un-rescoreable. The scheduler retries None-result jobs on the next pass.
    """
    async def broken_llm(prompt, system, max_tokens, cached_prefix=None):
        raise RuntimeError("simulated LLM outage")

    monkeypatch.setattr("backend.analyzer.cv_scorer.call_llm", broken_llm)
    monkeypatch.setattr("backend.analyzer.cv_scorer.log_llm_call", lambda **kw: None)

    from backend.analyzer import cv_scorer
    job = FakeJob()
    result = await cv_scorer.score_job_sync(
        job, {"PM": "CV text"}, db=None, depth="light", preloaded_text="JD text",
    )

    assert result is None
    # If the function returns a dict on error, it MUST NOT contain _skipped markers
    # that prevent the scheduler from rescoring
    if isinstance(result, dict):
        assert result.get("_skipped") is None, (
            "LLM failure must not set a _skipped marker — job should be re-scorable"
        )
