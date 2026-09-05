"""A malformed LLM response ({"scores": null} / non-dict scores) must be treated as a transient failure (return None), never crash the scoring batch."""
import asyncio
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class FakeJob:
    def __init__(self, id="job-1", description="Job description here. " * 50):
        self.id = id
        self.company = "Acme"
        self.title = "Senior PM"
        self.description = description
        self.cached_page_text = None
        self.url = None


@pytest.fixture
def scorer_db(monkeypatch):
    from backend.models.db import Setting
    engine = create_engine("sqlite:///:memory:")
    Setting.__table__.create(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    s.add(Setting(key="scoring_rubric", value="RUBRIC"))
    s.add(Setting(key="scoring_output_light", value='{"scores": {CV_NAMES_HERE}}'))
    s.add(Setting(key="scoring_output_full", value='FULL'))
    s.add(Setting(key="llm_model", value="claude-sonnet-4-6"))
    s.add(Setting(key="llm_provider", value="claude_api"))
    s.commit()
    s.close()
    from backend.analyzer import cv_scorer
    monkeypatch.setattr(cv_scorer, "SessionLocal", Session)
    monkeypatch.setattr(cv_scorer, "_get_scoring_semaphore", lambda: asyncio.Semaphore(1))
    monkeypatch.setattr("backend.analyzer.cv_scorer.log_llm_call", lambda **kw: None)
    return Session


def _llm_returning(text):
    async def fake_call_llm(prompt, system, max_tokens, cached_prefix=None, **kwargs):
        return {"text": text,
                "usage": {"input_tokens": 1, "output_tokens": 1,
                          "cache_read_tokens": 0, "cache_write_tokens": 0}}
    return fake_call_llm


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_response", [
    '{"scores": null, "best_cv": "PM"}',      # explicit null — .get default does NOT apply
    '{"scores": "high", "best_cv": "PM"}',    # non-dict
    '{"scores": [], "best_cv": "PM"}',        # wrong type
    '{"scores": {}, "best_cv": "PM"}',        # empty — nothing scored
    '{"best_cv": "PM"}',                      # key absent
])
async def test_malformed_scores_returns_none(scorer_db, monkeypatch, bad_response):
    monkeypatch.setattr("backend.analyzer.cv_scorer.call_llm", _llm_returning(bad_response))
    from backend.analyzer import cv_scorer
    result = await cv_scorer.score_job_sync(
        FakeJob(), {"PM": "cv text"}, db=None, depth="light",
        preloaded_text="JD text",
    )
    assert result is None, f"expected transient-failure None for {bad_response!r}"


@pytest.mark.asyncio
async def test_valid_scores_still_succeed(scorer_db, monkeypatch):
    monkeypatch.setattr("backend.analyzer.cv_scorer.call_llm",
                        _llm_returning('{"scores": {"PM": 72}, "best_cv": "PM"}'))
    from backend.analyzer import cv_scorer
    result = await cv_scorer.score_job_sync(
        FakeJob(), {"PM": "cv text"}, db=None, depth="light",
        preloaded_text="JD text",
    )
    assert result is not None
    assert result["scores"] == {"PM": 72}
