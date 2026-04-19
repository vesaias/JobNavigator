"""Provider-agnostic LLM client for scoring and analysis with automatic fallback."""
import asyncio
import logging
from backend.models.db import SessionLocal, Setting

logger = logging.getLogger("jobnavigator.llm")


def _get_setting(db, key, default=""):
    row = db.query(Setting).filter(Setting.key == key).first()
    return row.value if row and row.value else default


async def call_llm(prompt: str, system: str, max_tokens: int = 1200) -> str:
    """Route to configured LLM provider with retry + automatic fallback.
    Tries primary 4 times with exponential backoff, then fallback 4 times."""
    MAX_ATTEMPTS = 4
    BACKOFF_BASE = 2  # seconds: 2, 4, 8

    db = SessionLocal()
    try:
        provider = _get_setting(db, "llm_provider", "claude_api")
        model = _get_setting(db, "llm_model", "claude-sonnet-4-6")
        api_key = _get_setting(db, "llm_api_key", "")
        base_url = _get_setting(db, "llm_base_url", "")
        fallback_provider = _get_setting(db, "llm_fallback_provider", "")
        fallback_model = _get_setting(db, "llm_fallback_model", "")
        fb_api_key = _get_setting(db, "llm_fallback_api_key", "")
        fb_base_url = _get_setting(db, "llm_fallback_base_url", "")
    finally:
        db.close()

    # Try primary with retries
    last_primary_err = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            logger.info(f"LLM call: provider={provider}, model={model}, attempt={attempt}/{MAX_ATTEMPTS}")
            return await _dispatch(provider, model, api_key, base_url, prompt, system, max_tokens)
        except Exception as e:
            last_primary_err = e
            if attempt < MAX_ATTEMPTS:
                wait = BACKOFF_BASE ** attempt  # 2, 4, 8
                logger.warning(f"LLM primary attempt {attempt}/{MAX_ATTEMPTS} failed: {e}, retrying in {wait}s")
                await asyncio.sleep(wait)
            else:
                logger.warning(f"LLM primary exhausted {MAX_ATTEMPTS} attempts: {e}")

    # Try fallback with retries
    if fallback_provider and fallback_model:
        last_fallback_err = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                logger.info(f"LLM fallback: provider={fallback_provider}, model={fallback_model}, attempt={attempt}/{MAX_ATTEMPTS}")
                return await _dispatch(fallback_provider, fallback_model, fb_api_key, fb_base_url, prompt, system, max_tokens)
            except Exception as e:
                last_fallback_err = e
                if attempt < MAX_ATTEMPTS:
                    wait = BACKOFF_BASE ** attempt
                    logger.warning(f"LLM fallback attempt {attempt}/{MAX_ATTEMPTS} failed: {e}, retrying in {wait}s")
                    await asyncio.sleep(wait)
                else:
                    logger.error(f"LLM fallback exhausted {MAX_ATTEMPTS} attempts: {e}")

        raise RuntimeError(
            f"Both LLM providers failed after {MAX_ATTEMPTS} attempts each. "
            f"Primary ({provider}/{model}): {last_primary_err}. "
            f"Fallback ({fallback_provider}/{fallback_model}): {last_fallback_err}"
        )

    raise last_primary_err


async def call_email_llm(prompt: str, system: str, max_tokens: int = 150) -> str:
    """Route to email-specific LLM provider, falling back to primary if not configured."""
    db = SessionLocal()
    try:
        # Read email-specific settings
        provider = _get_setting(db, "email_llm_provider", "")
        model = _get_setting(db, "email_llm_model", "")
        api_key = _get_setting(db, "email_llm_api_key", "")
        # Fall back to primary if email-specific not configured
        if not provider:
            provider = _get_setting(db, "llm_provider", "claude_api")
        if not model:
            model = _get_setting(db, "llm_model", "claude-sonnet-4-6")
        if not api_key:
            api_key = _get_setting(db, "llm_api_key", "")
        base_url = _get_setting(db, "llm_base_url", "")
    finally:
        db.close()

    logger.info(f"Email LLM call: provider={provider}, model={model}, max_tokens={max_tokens}")
    return await _dispatch(provider, model, api_key, base_url, prompt, system, max_tokens)


async def call_cv_tailor_llm(prompt: str, system: str, max_tokens: int = 3000) -> str:
    """Route to CV-tailoring-specific LLM provider, falling back to primary if not configured."""
    db = SessionLocal()
    try:
        provider = _get_setting(db, "cv_tailor_llm_provider", "")
        model = _get_setting(db, "cv_tailor_llm_model", "")
        api_key = _get_setting(db, "cv_tailor_llm_api_key", "")
        if not provider:
            provider = _get_setting(db, "llm_provider", "claude_api")
        if not model:
            model = _get_setting(db, "llm_model", "claude-sonnet-4-6")
        if not api_key:
            api_key = _get_setting(db, "llm_api_key", "")
        base_url = _get_setting(db, "llm_base_url", "")
    finally:
        db.close()

    logger.info(f"CV tailor LLM call: provider={provider}, model={model}, max_tokens={max_tokens}")
    return await _dispatch(provider, model, api_key, base_url, prompt, system, max_tokens)


async def _dispatch(provider: str, model: str, api_key: str, base_url: str,
                    prompt: str, system: str, max_tokens: int) -> str:
    """Route to the correct provider."""
    if provider == "claude_api":
        return await _call_claude_api(prompt, system, model, api_key, max_tokens)
    elif provider == "claude_code":
        return await _call_claude_code(prompt, system, model, max_tokens)
    elif provider == "openai":
        return await _call_openai(prompt, system, model, api_key, max_tokens)
    elif provider == "ollama":
        return await _call_ollama(prompt, system, model, max_tokens)
    elif provider == "openai_compat":
        return await _call_openai(prompt, system, model, api_key, max_tokens, base_url=base_url)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


async def _call_claude_api(prompt: str, system: str, model: str, api_key: str,
                           max_tokens: int, cached_prefix: str | None = None) -> dict:
    """Call Claude via Anthropic SDK. Returns {text, usage} dict.

    When cached_prefix is provided, it's sent as a separate message block with
    cache_control={"type": "ephemeral"} so subsequent calls with the same prefix
    are served at cache-read price (~10x cheaper). The prefix should be >= 1024
    tokens (Sonnet/Opus minimum) or it's ignored for caching.
    """
    import anthropic
    key = api_key or __import__('os').getenv("ANTHROPIC_API_KEY", "")
    client = anthropic.AsyncAnthropic(api_key=key)

    if cached_prefix:
        content = [
            {"type": "text", "text": cached_prefix, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": prompt},
        ]
    else:
        content = prompt  # plain string — no cache_control

    response = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": content}],
    )

    # Extract usage — cache_* attributes may be absent on older SDK versions or non-cached calls
    usage = response.usage
    return {
        "text": response.content[0].text.strip(),
        "usage": {
            "input_tokens": getattr(usage, "input_tokens", 0),
            "output_tokens": getattr(usage, "output_tokens", 0),
            "cache_read_tokens": getattr(usage, "cache_read_input_tokens", 0) or 0,
            "cache_write_tokens": getattr(usage, "cache_creation_input_tokens", 0) or 0,
        },
    }


async def _call_claude_code(prompt: str, system: str, model: str, max_tokens: int) -> str:
    """Call Claude via claude CLI subprocess (uses Max/Pro subscription via OAuth token).
    Pipes prompt via stdin to avoid command-line length limits on large scoring prompts."""
    import os
    import json as _json
    full_prompt = f"{system}\n\n{prompt}"
    cmd = ["claude", "-p", "--output-format", "json"]
    if model:
        cmd.extend(["--model", model])

    # Build env: pass CLAUDE_CODE_OAUTH_TOKEN, explicitly EXCLUDE ANTHROPIC_API_KEY
    # so it uses subscription billing, not API credits
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    stdout, stderr = await process.communicate(input=full_prompt.encode())

    if process.returncode != 0:
        error = stderr.decode().strip()
        raise RuntimeError(f"claude-code subprocess failed (rc={process.returncode}): {error}")

    # Parse JSON output format — result is in the "result" field
    raw = stdout.decode().strip()
    try:
        data = _json.loads(raw)
        return data.get("result", raw)
    except _json.JSONDecodeError:
        return raw


async def _call_openai(prompt: str, system: str, model: str, api_key: str, max_tokens: int, base_url: str = None) -> str:
    """Call OpenAI or OpenAI-compatible API."""
    from openai import AsyncOpenAI
    kwargs = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    client = AsyncOpenAI(**kwargs)
    response = await client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content.strip()


async def _call_ollama(prompt: str, system: str, model: str, max_tokens: int) -> str:
    """Call local Ollama instance."""
    import httpx
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "system": system,
                "stream": False,
                "options": {"num_predict": max_tokens},
            },
        )
        response.raise_for_status()
        return response.json()["response"].strip()
