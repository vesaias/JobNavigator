"""LLM helper endpoints — live model catalogs for the Settings model picker; OpenRouter's and Cheaper Inference's are public, OpenAI/Anthropic require a resolved API key, and results are cached ~1h per provider."""
import os
import re
import time
import logging
import httpx
from fastapi import APIRouter, HTTPException
from backend.models.db import SessionLocal
from backend.accounts.settings import get_setting

logger = logging.getLogger("jobnavigator.llm")
router = APIRouter(prefix="/llm", tags=["settings"])

_CACHE_TTL = 3600  # 1 hour
_cache = {}  # provider, or (provider, key) for a keyed catalog -> {"at": float, "models": list}

def _resolve_key(db, provider: str) -> str:
    """The provider's API key (one per provider, so a key set while only Scoring used that
    provider counts too, R30 B4), else its env var. A member on its own Models section sees only
    its own key (get_setting never falls back to the owner's there, QA F5) and never the `.env`
    key, which is the owner's (R3-02)."""
    from backend.accounts.settings import PROVIDER_KEY_SETTINGS
    from backend.analyzer.llm_client import provider_api_key
    key = provider_api_key(db, provider)
    if key or provider not in PROVIDER_KEY_SETTINGS:
        return key
    from backend.accounts.credentials import own_login_account
    if own_login_account(db) is not None:
        return ""
    return os.getenv(PROVIDER_KEY_SETTINGS[provider].upper(), "")


def _builtin_models(provider: str) -> list:
    """The seeded default catalog entries for `provider`, shaped like a live catalog."""
    import json
    from backend.seed import DEFAULT_SETTINGS
    entries = json.loads(DEFAULT_SETTINGS["llm_models_list"][0])
    ids = sorted({e["model"] for e in entries if e.get("provider") == provider})
    return [{"id": m, "name": m} for m in ids]


async def _fetch_openrouter() -> list:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get("https://openrouter.ai/api/v1/models")
        resp.raise_for_status()
        data = resp.json().get("data", [])
    out = []
    for m in data:
        pricing = m.get("pricing") or {}
        out.append({
            "id": m.get("id"),
            "name": m.get("name") or m.get("id"),
            "context_length": m.get("context_length"),
            "prompt_price": pricing.get("prompt"),
            "completion_price": pricing.get("completion"),
        })
    return out


async def _fetch_openai(key: str) -> list:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get("https://api.openai.com/v1/models",
                                headers={"Authorization": f"Bearer {key}"})
        resp.raise_for_status()
        data = resp.json().get("data", [])
    out = []
    for m in data:
        mid = m.get("id", "")
        # Keep chat-capable families; skip embeddings/audio/image/moderation.
        if mid.startswith("gpt") or re.match(r"^(o\d|chatgpt)", mid):
            out.append({"id": mid, "name": mid})
    return out


async def _fetch_anthropic(key: str) -> list:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get("https://api.anthropic.com/v1/models?limit=1000",
                                headers={"x-api-key": key,
                                         "anthropic-version": "2023-06-01"})
        resp.raise_for_status()
        data = resp.json().get("data", [])
    return [{"id": m.get("id"), "name": m.get("display_name") or m.get("id")} for m in data]


async def _fetch_opencode_go(key: str) -> list:
    """OpenCode Go models from its OpenAI-compatible endpoint; the catalog is public, so a
    missing key still lists what exists."""
    from backend.analyzer.llm_client import OPENCODE_GO_BASE_URL
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{OPENCODE_GO_BASE_URL}/models", headers=headers)
        resp.raise_for_status()
        data = resp.json().get("data", [])
    return [{"id": m.get("id"), "name": m.get("id")} for m in data if m.get("id")]


async def _fetch_cheaper_inference() -> list:
    """Cheaper Inference models from its public catalog (no key needed), limited to the text
    models served on /chat/completions, the endpoint this provider calls."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get("https://api.cheaperinference.com/public/models")
        resp.raise_for_status()
        data = resp.json().get("models", [])
    return [{"id": m.get("id"), "name": m.get("id"), "context_length": m.get("context_length")}
            for m in data
            if m.get("id") and m.get("model_type") == "text"
            and "/v1/chat/completions" in (m.get("supported_endpoints") or [])]


@router.get("/efforts")
async def list_efforts():
    """Reasoning-effort values per provider for the Settings pickers; a provider not listed takes none."""
    from backend.analyzer.llm_client import REASONING_EFFORTS
    return {"efforts": {p: list(v) for p, v in REASONING_EFFORTS.items()}}


@router.get("/models")
async def list_models(provider: str = "openrouter"):
    """Live model catalog for a provider, cached ~1h; openrouter and cheaper_inference need no key, openai/claude_api use a configured key or env fallback (400 if none, 502 if the provider rejects it); claude_code borrows the Anthropic key and falls back to the built-in list without one."""
    now = time.time()
    db = SessionLocal()
    key = ""
    try:
        if provider in ("openrouter", "cheaper_inference"):
            pass
        elif provider == "opencode_go":
            # Go's catalog is public: an empty key (none set, or a member on own without one)
            # still lists it; a key, when set, is the account's own (cached per key below).
            key = _resolve_key(db, "opencode_go")
        elif provider in ("openai", "claude_api", "claude_code"):
            # Claude Code (subscription) serves the same models as Claude API, so it
            # shares the Anthropic catalog — resolved via any configured Anthropic key.
            key_provider = "claude_api" if provider == "claude_code" else provider
            key = _resolve_key(db, key_provider)
            if not key and provider == "claude_code":
                # Subscription users usually have no API key: serve the built-in Claude list rather than a 400.
                return {"models": _builtin_models("claude_code"), "cached": False, "builtin": True}
            if not key:
                label = "OpenAI" if provider == "openai" else "Anthropic"
                raise HTTPException(400, f"No {label} API key configured — set one in Settings first.")
        else:
            raise HTTPException(400, f"Live model search is not supported for provider '{provider}'.")
    finally:
        db.close()

    # MT-15: a keyed catalog is cached per key, so an account with its own key never gets the
    # list another account's key fetched (an OpenAI org's catalog can differ).
    # (in memory only, like the key itself; never logged or returned)
    cache_key = (provider, key) if key else provider
    hit = _cache.get(cache_key)
    if hit and (now - hit["at"]) < _CACHE_TTL:
        return {"models": hit["models"], "cached": True}
    if provider == "openrouter":
        fetch = _fetch_openrouter()
    elif provider == "opencode_go":
        fetch = _fetch_opencode_go(key)
    elif provider == "cheaper_inference":
        fetch = _fetch_cheaper_inference()
    else:
        fetch = _fetch_openai(key) if provider == "openai" else _fetch_anthropic(key)

    try:
        models = await fetch
    except HTTPException:
        raise
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (401, 403):
            raise HTTPException(502, "The provider rejected the configured API key.")
        logger.warning("model fetch failed (%s): %s", provider, e)
        if hit:
            return {"models": hit["models"], "cached": True, "stale": True}
        raise HTTPException(502, "Could not reach the provider's model catalog.")
    except Exception as e:
        logger.warning("model fetch failed (%s): %s", provider, e)
        if hit:
            return {"models": hit["models"], "cached": True, "stale": True}
        raise HTTPException(502, "Could not reach the provider's model catalog.")

    models = [m for m in models if m.get("id")]
    models.sort(key=lambda m: m["id"])
    _cache[cache_key] = {"at": now, "models": models}
    return {"models": models, "cached": False}
