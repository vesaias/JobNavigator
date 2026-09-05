"""LLM pricing and cost calculation, in USD per million tokens, keyed by (provider, model) since the same model can be billed differently across providers (e.g. Anthropic API vs. Claude Code subscription).
claude_api/openai use static tables (update when models change); openrouter is fetched live (refresh_openrouter_prices); claude_code/ollama are always $0."""
import time as _time
import logging
from typing import Optional

logger = logging.getLogger("jobnavigator.llm_cost")

# ── Anthropic (cache read = 10% input, 5m cache write = 125% input) ──────────
_CLAUDE_FABLE_5 = {"input_per_mtok": 10.0, "output_per_mtok": 50.0, "cache_read_per_mtok": 1.00, "cache_write_per_mtok": 12.50}
_CLAUDE_OPUS = {  # Opus 5 / 4.8 / 4.7 / 4.6 / 4.5 share the $5/$25 card
    "input_per_mtok": 5.0, "output_per_mtok": 25.0, "cache_read_per_mtok": 0.50, "cache_write_per_mtok": 6.25,
}
_CLAUDE_SONNET_5 = {  # Sonnet 5 — $2/$10 is now the standard price
    "input_per_mtok": 2.0, "output_per_mtok": 10.0, "cache_read_per_mtok": 0.20, "cache_write_per_mtok": 2.50,
}
_CLAUDE_SONNET_46 = {  # Sonnet 4.6 / 4.5 — $3/$15
    "input_per_mtok": 3.0, "output_per_mtok": 15.0, "cache_read_per_mtok": 0.30, "cache_write_per_mtok": 3.75,
}
_CLAUDE_HAIKU = {"input_per_mtok": 1.0, "output_per_mtok": 5.0, "cache_read_per_mtok": 0.10, "cache_write_per_mtok": 1.25}


def _oa(inp: float, out: float, cache_read: Optional[float] = None) -> dict:
    """OpenAI entry — no separate cache-write charge; cache read = cached-input price."""
    return {"input_per_mtok": inp, "output_per_mtok": out,
            "cache_read_per_mtok": cache_read if cache_read is not None else inp,
            "cache_write_per_mtok": inp}


# Per million tokens, USD.
PRICING: dict[str, dict[str, dict]] = {
    "claude_api": {
        "claude-fable-5": _CLAUDE_FABLE_5,
        "claude-opus-5": _CLAUDE_OPUS,
        "claude-opus-4-8": _CLAUDE_OPUS,
        "claude-opus-4-7": _CLAUDE_OPUS,
        "claude-opus-4-6": _CLAUDE_OPUS,
        "claude-opus-4-5": _CLAUDE_OPUS,
        "claude-sonnet-5": _CLAUDE_SONNET_5,
        "claude-sonnet-4-6": _CLAUDE_SONNET_46,
        "claude-sonnet-4-5": _CLAUDE_SONNET_46,
        "claude-haiku-4-5": _CLAUDE_HAIKU,
        "claude-haiku-4-5-20251001": _CLAUDE_HAIKU,  # legacy dated id
    },
    "openai": {
        "gpt-5.6-luna": _oa(0.20, 1.20, 0.02),
        "gpt-5.4": _oa(2.50, 15.0, 0.25),
        "gpt-5.4-mini": _oa(0.75, 4.50, 0.075),
        "gpt-5.4-nano": _oa(0.20, 1.25, 0.02),
        "gpt-5.2": _oa(1.75, 14.0, 0.175),
        "gpt-4o": _oa(2.50, 10.0, 1.25),
        "gpt-4o-mini": _oa(0.15, 0.60, 0.075),
        "o3": _oa(2.0, 8.0, 0.50),
        "o3-mini": _oa(1.10, 4.40, 0.55),
        "o3-pro": _oa(20.0, 80.0),
        "o4-mini": _oa(1.10, 4.40, 0.275),
    },
}

# Providers whose calls are covered by flat subscription / local compute — always $0.
FREE_PROVIDERS: set[str] = {"claude_code", "ollama"}

# ── OpenRouter live pricing ──────────────────────────────────────────────────
_OR_PRICES: dict[str, dict] = {}   # slug -> per-Mtok pricing dict
_OR_FETCHED_AT: float = 0.0
_OR_TTL = 12 * 3600  # refresh at most every 12h


async def refresh_openrouter_prices(force: bool = False) -> None:
    """Pull live per-model pricing from OpenRouter and cache it (per-Mtok); non-fatal (keeps previous cache on error), TTL-gated unless force."""
    global _OR_FETCHED_AT
    if not force and _OR_PRICES and (_time.time() - _OR_FETCHED_AT) < _OR_TTL:
        return
    try:
        import httpx
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get("https://openrouter.ai/api/v1/models")
            resp.raise_for_status()
            data = resp.json().get("data", [])
        prices = {}
        for m in data:
            mid = m.get("id")
            pr = m.get("pricing") or {}
            try:
                inp = float(pr.get("prompt") or 0) * 1_000_000
                out = float(pr.get("completion") or 0) * 1_000_000
                cr = float(pr.get("input_cache_read") or 0) * 1_000_000
            except (TypeError, ValueError):
                continue
            if mid and (inp or out):
                prices[mid] = {
                    "input_per_mtok": inp,
                    "output_per_mtok": out,
                    "cache_read_per_mtok": cr or inp * 0.1,
                    "cache_write_per_mtok": inp,
                }
        if prices:
            _OR_PRICES.clear()
            _OR_PRICES.update(prices)
            _OR_FETCHED_AT = _time.time()
            logger.info("OpenRouter pricing refreshed: %d models", len(prices))
    except Exception as e:
        logger.warning("OpenRouter price refresh failed (keeping cache): %s", e)


def get_pricing(provider: str, model: str) -> Optional[dict]:
    """Return the pricing dict for a (provider, model), or None if unknown."""
    if provider == "openrouter":
        return _OR_PRICES.get(model)
    return PRICING.get(provider, {}).get(model)


def calc_cost(provider: str, model: str,
              input_tokens: int = 0,
              output_tokens: int = 0,
              cache_read_tokens: int = 0,
              cache_write_tokens: int = 0) -> float:
    """Calculate USD cost for a single LLM call; returns 0.0 for FREE_PROVIDERS (claude_code, ollama) or an unpriced (provider, model) combo."""
    if provider in FREE_PROVIDERS:
        return 0.0
    p = get_pricing(provider, model)
    if not p:
        return 0.0
    return (
        input_tokens * p["input_per_mtok"] / 1_000_000
        + output_tokens * p["output_per_mtok"] / 1_000_000
        + cache_read_tokens * p["cache_read_per_mtok"] / 1_000_000
        + cache_write_tokens * p["cache_write_per_mtok"] / 1_000_000
    )
