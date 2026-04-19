"""Tests for llm_logger.log_llm_call."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def test_db(monkeypatch):
    """In-memory SQLite, patched into llm_logger.SessionLocal."""
    from backend.models.db import Base, LlmCallLog
    engine = create_engine("sqlite:///:memory:")
    LlmCallLog.__table__.create(engine)
    Session = sessionmaker(bind=engine)

    # Patch SessionLocal used by llm_logger
    import backend.analyzer.llm_logger as llm_logger
    monkeypatch.setattr(llm_logger, "SessionLocal", Session)

    session = Session()
    yield session
    session.close()


def test_log_llm_call_persists_row(test_db):
    from backend.analyzer.llm_logger import log_llm_call
    from backend.models.db import LlmCallLog

    log_llm_call(
        purpose="score_light",
        provider="claude_api",
        model="claude-sonnet-4-6",
        usage={
            "input_tokens": 1200,
            "output_tokens": 200,
            "cache_read_tokens": 0,
            "cache_write_tokens": 2400,
        },
        duration_ms=850,
        success=True,
    )

    row = test_db.query(LlmCallLog).first()
    assert row is not None
    assert row.purpose == "score_light"
    assert row.provider == "claude_api"
    assert row.input_tokens == 1200
    assert row.cache_write_tokens == 2400
    assert row.cost_usd > 0


def test_log_llm_call_computes_cost(test_db):
    """Cost should be computed from the pricing table."""
    from backend.analyzer.llm_logger import log_llm_call
    from backend.models.db import LlmCallLog

    log_llm_call(
        purpose="score_full",
        provider="claude_api",
        model="claude-sonnet-4-6",
        usage={
            "input_tokens": 1000,
            "output_tokens": 200,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
        },
        duration_ms=500,
    )
    row = test_db.query(LlmCallLog).first()
    # 1000*3/1M + 200*15/1M = 0.003 + 0.003 = 0.006
    assert abs(row.cost_usd - 0.006) < 1e-6


def test_log_llm_call_failure_never_raises(test_db, monkeypatch):
    """Logging errors should never bubble up to the caller."""
    from backend.analyzer import llm_logger

    def broken_session():
        raise RuntimeError("DB is down")

    monkeypatch.setattr(llm_logger, "SessionLocal", broken_session)

    # Should not raise — logger swallows errors
    llm_logger.log_llm_call(
        purpose="email",
        provider="claude_api",
        model="claude-haiku-4-5-20251001",
        usage={"input_tokens": 100, "output_tokens": 20,
               "cache_read_tokens": 0, "cache_write_tokens": 0},
    )


def test_log_llm_call_with_job_id(test_db):
    """job_id is stored when provided."""
    import uuid
    from backend.analyzer.llm_logger import log_llm_call
    from backend.models.db import LlmCallLog

    job_id = uuid.uuid4()
    log_llm_call(
        purpose="score_full",
        provider="claude_api",
        model="claude-sonnet-4-6",
        usage={"input_tokens": 1000, "output_tokens": 100,
               "cache_read_tokens": 0, "cache_write_tokens": 0},
        job_id=job_id,
    )
    row = test_db.query(LlmCallLog).first()
    assert row.job_id == job_id


def test_log_llm_call_failure_records_error(test_db):
    """When success=False, error text is stored."""
    from backend.analyzer.llm_logger import log_llm_call
    from backend.models.db import LlmCallLog

    log_llm_call(
        purpose="score_light",
        provider="claude_api",
        model="claude-sonnet-4-6",
        usage={"input_tokens": 0, "output_tokens": 0,
               "cache_read_tokens": 0, "cache_write_tokens": 0},
        success=False,
        error="529 overloaded",
    )
    row = test_db.query(LlmCallLog).first()
    assert row.success is False
    assert row.error == "529 overloaded"


def test_log_llm_call_claude_code_cost_is_zero(test_db):
    """claude_code is subscription — cost should be 0 regardless of tokens."""
    from backend.analyzer.llm_logger import log_llm_call
    from backend.models.db import LlmCallLog

    log_llm_call(
        purpose="score_light",
        provider="claude_code",
        model="claude-sonnet-4-6",
        usage={"input_tokens": 10000, "output_tokens": 5000,
               "cache_read_tokens": 0, "cache_write_tokens": 0},
        duration_ms=500,
    )
    row = test_db.query(LlmCallLog).first()
    assert row.provider == "claude_code"
    assert row.cost_usd == 0.0
