"""Persist LLM call metrics to the llm_call_log table. Non-fatal on errors."""
import logging
from typing import Optional
from uuid import UUID

from backend.models.db import SessionLocal, LlmCallLog
from backend.analyzer.llm_cost import calc_cost

logger = logging.getLogger("jobnavigator.llm_logger")


def log_llm_call(
    purpose: str,
    model: str,
    usage: dict,
    duration_ms: int = 0,
    job_id: Optional[UUID] = None,
    success: bool = True,
    error: Optional[str] = None,
) -> None:
    """Insert a row into llm_call_log. Swallows DB errors — logging must never break scoring.

    usage: {input_tokens, output_tokens, cache_read_tokens, cache_write_tokens}
    """
    try:
        cost = calc_cost(
            model,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            cache_read_tokens=usage.get("cache_read_tokens", 0),
            cache_write_tokens=usage.get("cache_write_tokens", 0),
        )
        db = SessionLocal()
        try:
            row = LlmCallLog(
                purpose=purpose,
                model=model,
                job_id=job_id,
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                cache_read_tokens=usage.get("cache_read_tokens", 0),
                cache_write_tokens=usage.get("cache_write_tokens", 0),
                cost_usd=cost,
                duration_ms=duration_ms,
                success=success,
                error=(error[:500] if error else None),  # truncate long error strings
            )
            db.add(row)
            db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"log_llm_call failed (non-fatal): {e}")
