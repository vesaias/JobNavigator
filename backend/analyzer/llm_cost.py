"""LLM pricing and cost calculation.

Prices in USD per million tokens as of 2026-04. Update PRICING when models change.
Sources: https://www.anthropic.com/pricing, https://openai.com/pricing
"""
from typing import Optional

# Per million tokens, USD. Cache read = 10% of input, cache write = 125% of input.
PRICING: dict[str, dict] = {
    # Anthropic
    "claude-sonnet-4-6": {
        "input_per_mtok": 3.0,
        "output_per_mtok": 15.0,
        "cache_read_per_mtok": 0.30,
        "cache_write_per_mtok": 3.75,
    },
    "claude-opus-4-6": {
        "input_per_mtok": 15.0,
        "output_per_mtok": 75.0,
        "cache_read_per_mtok": 1.50,
        "cache_write_per_mtok": 18.75,
    },
    "claude-haiku-4-5-20251001": {
        "input_per_mtok": 1.0,
        "output_per_mtok": 5.0,
        "cache_read_per_mtok": 0.10,
        "cache_write_per_mtok": 1.25,
    },
    # OpenAI (no prompt caching discount — single rate)
    "gpt-4o": {
        "input_per_mtok": 2.50,
        "output_per_mtok": 10.0,
        "cache_read_per_mtok": 2.50,
        "cache_write_per_mtok": 2.50,
    },
    "gpt-4o-mini": {
        "input_per_mtok": 0.15,
        "output_per_mtok": 0.60,
        "cache_read_per_mtok": 0.15,
        "cache_write_per_mtok": 0.15,
    },
}


def get_pricing(model: str) -> Optional[dict]:
    """Return the pricing dict for a model, or None if unknown."""
    return PRICING.get(model)


def calc_cost(model: str,
              input_tokens: int = 0,
              output_tokens: int = 0,
              cache_read_tokens: int = 0,
              cache_write_tokens: int = 0) -> float:
    """Calculate USD cost for a single LLM call.

    Returns 0.0 for unknown models (with a warning in caller if desired).
    """
    p = PRICING.get(model)
    if not p:
        return 0.0
    return (
        input_tokens * p["input_per_mtok"] / 1_000_000
        + output_tokens * p["output_per_mtok"] / 1_000_000
        + cache_read_tokens * p["cache_read_per_mtok"] / 1_000_000
        + cache_write_tokens * p["cache_write_per_mtok"] / 1_000_000
    )
