"""Test LlmCallLog model persistence."""
import pytest
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def test_db():
    """In-memory SQLite with only LlmCallLog table created."""
    from backend.models.db import Base, LlmCallLog
    engine = create_engine("sqlite:///:memory:")
    LlmCallLog.__table__.create(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_llm_call_log_model_exists():
    """LlmCallLog is importable from models.db."""
    from backend.models.db import LlmCallLog
    assert LlmCallLog.__tablename__ == "llm_call_log"


def test_llm_call_log_can_insert(test_db):
    """A row with all expected columns can be inserted and retrieved."""
    from backend.models.db import LlmCallLog
    row = LlmCallLog(
        purpose="score_light",
        provider="claude_api",
        model="claude-sonnet-4-6",
        input_tokens=1200,
        output_tokens=200,
        cache_read_tokens=0,
        cache_write_tokens=2400,
        cost_usd=0.012,
        duration_ms=850,
        success=True,
    )
    test_db.add(row)
    test_db.commit()
    back = test_db.query(LlmCallLog).first()
    assert back.purpose == "score_light"
    assert back.provider == "claude_api"
    assert back.model == "claude-sonnet-4-6"
    assert back.input_tokens == 1200
    assert back.cache_write_tokens == 2400
    assert abs(back.cost_usd - 0.012) < 1e-6
    assert back.success is True


def test_llm_call_log_defaults(test_db):
    """Columns with defaults don't require explicit values."""
    from backend.models.db import LlmCallLog
    row = LlmCallLog(purpose="email", model="claude-haiku-4-5-20251001")
    test_db.add(row)
    test_db.commit()
    back = test_db.query(LlmCallLog).first()
    assert back.provider == ""
    assert back.input_tokens == 0
    assert back.output_tokens == 0
    assert back.cache_read_tokens == 0
    assert back.cache_write_tokens == 0
    assert back.cost_usd == 0.0
    assert back.duration_ms == 0
    assert back.success is True
    assert back.id is not None  # UUID auto-generated
    assert back.created_at is not None
