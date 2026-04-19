"""Tests for the llm-costs stats aggregation."""
import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def seeded_db(monkeypatch):
    from backend.models.db import Base, LlmCallLog
    engine = create_engine("sqlite:///:memory:")
    LlmCallLog.__table__.create(engine)
    Session = sessionmaker(bind=engine)

    import backend.main as main_mod
    monkeypatch.setattr(main_mod, "SessionLocal", Session)

    s = Session()
    now = datetime.now(timezone.utc)
    # Day 0: 2 light scoring calls, 1 full
    s.add(LlmCallLog(purpose="score_light", model="claude-sonnet-4-6",
                     input_tokens=1000, output_tokens=100,
                     cache_read_tokens=0, cache_write_tokens=2400,
                     cost_usd=0.012, duration_ms=800, created_at=now))
    s.add(LlmCallLog(purpose="score_light", model="claude-sonnet-4-6",
                     input_tokens=1000, output_tokens=100,
                     cache_read_tokens=2400, cache_write_tokens=0,
                     cost_usd=0.004, duration_ms=500, created_at=now))
    s.add(LlmCallLog(purpose="score_full", model="claude-sonnet-4-6",
                     input_tokens=1200, output_tokens=1000,
                     cost_usd=0.019, duration_ms=1500, created_at=now))
    # 8 days ago: should be excluded from 7-day window
    s.add(LlmCallLog(purpose="score_light", model="claude-sonnet-4-6",
                     cost_usd=0.99, created_at=now - timedelta(days=8)))
    s.commit()
    yield s
    s.close()


def test_llm_costs_aggregation_7d(seeded_db):
    """7-day window groups by purpose + model."""
    from backend.main import _llm_costs_stats
    result = _llm_costs_stats(days=7)

    assert result["total_cost_usd"] == pytest.approx(0.035, rel=0.05)
    assert result["total_calls"] == 3

    # Grouping
    score_light = [r for r in result["by_purpose"] if r["purpose"] == "score_light"][0]
    assert score_light["calls"] == 2
    assert score_light["cost_usd"] == pytest.approx(0.016, rel=0.05)

    # Cache hit rate on score_light (calls with cache_read > 0 / all calls with cache involvement)
    assert score_light["cache_hit_ratio"] == pytest.approx(0.5, rel=0.05)  # 1 of 2 was a hit


def test_llm_costs_excludes_old_rows(seeded_db):
    """8-day-old row is not in 7-day window."""
    from backend.main import _llm_costs_stats
    result = _llm_costs_stats(days=7)
    # The $0.99 row is 8 days old, so should NOT appear
    assert result["total_cost_usd"] < 0.5
