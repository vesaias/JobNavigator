"""Persist LLM call metrics to the llm_call_log table. Non-fatal on errors."""
import logging
import time
from contextlib import asynccontextmanager
from typing import Optional
from uuid import UUID

from backend.models.db import SessionLocal, LlmCallLog
from backend.analyzer.llm_cost import calc_cost

logger = logging.getLogger("jobnavigator.llm_logger")


def log_llm_call(
    purpose: str,
    provider: str,
    model: str,
    usage: dict,
    duration_ms: int = 0,
    job_id: Optional[UUID] = None,
    success: bool = True,
    error: Optional[str] = None,
) -> None:
    """Insert a row into llm_call_log; swallows DB errors so logging never breaks scoring. usage: {input_tokens, output_tokens, cache_read_tokens, cache_write_tokens}."""
    try:
        cost = calc_cost(
            provider,
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
                provider=provider,
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


@asynccontextmanager
async def track_llm_call(purpose: str, provider: str, model: str, job_id=None):
    """Async context manager that times an LLM call and logs it to llm_call_log; the caller must set tracker.usage (or call tracker.record(resp)) so a fallback dispatch is logged as the model that actually answered."""
    started = time.monotonic()

    class _Tracker:
        def __init__(self, provider, model):
            self.usage = {"input_tokens": 0, "output_tokens": 0,
                          "cache_read_tokens": 0, "cache_write_tokens": 0}
            self.provider = provider
            self.model = model

        def record(self, resp):
            """Take usage + the dispatched provider/model off an LLM response dict."""
            if isinstance(resp, dict):
                self.usage = resp.get("usage") or self.usage
                self.provider = resp.get("provider") or self.provider
                self.model = resp.get("model") or self.model
            return resp

    t = _Tracker(provider, model)
    success = True
    error = None
    try:
        yield t
    except Exception as e:
        success = False
        error = str(e)
        raise
    finally:
        try:
            # Keep OpenRouter live pricing fresh (TTL-gated) so cost is accurate.
            if t.provider == "openrouter":
                try:
                    from backend.analyzer.llm_cost import refresh_openrouter_prices
                    await refresh_openrouter_prices()
                except Exception:
                    pass
            log_llm_call(
                purpose=purpose,
                provider=t.provider,
                model=t.model,
                usage=t.usage,
                duration_ms=int((time.monotonic() - started) * 1000),
                job_id=job_id,
                success=success,
                error=error,
            )
        except Exception as e:
            logger.warning(f"track_llm_call finally block failed (non-fatal): {e}")
