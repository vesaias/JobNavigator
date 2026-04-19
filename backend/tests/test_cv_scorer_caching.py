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
