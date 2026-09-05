"""Provider-agnostic LLM client for scoring and analysis with automatic fallback."""
import asyncio
import logging
from backend.models.db import SessionLocal, Setting

logger = logging.getLogger("jobnavigator.llm")


DEFAULT_PROVIDER = "claude_api"
DEFAULT_MODEL = "claude-sonnet-5"


def _get_setting(db, key, default=""):
    row = db.query(Setting).filter(Setting.key == key).first()
    return row.value if row and row.value else default


def resolve_llm_config(feature: str = "", db=None) -> dict:
    """Resolve the provider/model/api_key a feature dispatches with: `<feature>_llm_*` setting -> primary `llm_*` setting -> shipped default. Single source of truth for both dispatch and logging."""
    own_db = db is None
    if own_db:
        db = SessionLocal()
    try:
        prefix = f"{feature}_" if feature else ""
        provider = _get_setting(db, f"{prefix}llm_provider", "")
        model = _get_setting(db, f"{prefix}llm_model", "")
        api_key = _get_setting(db, f"{prefix}llm_api_key", "")
        if feature:
            provider = provider or _get_setting(db, "llm_provider", "")
            model = model or _get_setting(db, "llm_model", "")
            api_key = api_key or _get_setting(db, "llm_api_key", "")
        return {
            "provider": provider or DEFAULT_PROVIDER,
            "model": model or DEFAULT_MODEL,
            "api_key": api_key,
        }
    finally:
        if own_db:
            db.close()


async def call_llm(prompt: str, system: str, max_tokens: int = 1200,
                   cached_prefix: str | None = None,
                   provider: str | None = None, model: str | None = None,
                   api_key: str | None = None) -> dict:
    """Route to the configured LLM provider with retry + automatic fallback; provider/model/api_key override the Primary for this call when given, else fall back to the llm_* settings."""
    MAX_ATTEMPTS = 4
    BACKOFF_BASE = 2  # seconds: 2, 4, 8

    db = SessionLocal()
    try:
        primary = resolve_llm_config("", db=db)
        if provider is None:
            provider = primary["provider"]
        if model is None:
            model = primary["model"]
        if api_key is None:
            api_key = primary["api_key"]
        fallback_provider = _get_setting(db, "llm_fallback_provider", "")
        fallback_model = _get_setting(db, "llm_fallback_model", "")
        fb_api_key = _get_setting(db, "llm_fallback_api_key", "")
    finally:
        db.close()

    # Only claude_api supports explicit prompt caching — other providers get the
    # prefix concatenated into the prompt (no cache discount).
    caching = bool(cached_prefix) and provider == "claude_api"

    # Try primary with retries
    last_primary_err = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            logger.info(f"LLM call: provider={provider}, model={model}, attempt={attempt}/{MAX_ATTEMPTS}, caching={'on' if caching else 'off'}")
            res = await _dispatch(provider, model, api_key, prompt, system, max_tokens, cached_prefix=cached_prefix)
            return {**res, "provider": provider, "model": model}
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
        fb_caching = bool(cached_prefix) and fallback_provider == "claude_api"
        last_fallback_err = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                logger.info(f"LLM fallback: provider={fallback_provider}, model={fallback_model}, attempt={attempt}/{MAX_ATTEMPTS}, caching={'on' if fb_caching else 'off'}")
                res = await _dispatch(fallback_provider, fallback_model, fb_api_key, prompt, system, max_tokens, cached_prefix=cached_prefix)
                # Report the pair that actually answered so the caller logs the
                # fallback, not the primary it never reached.
                return {**res, "provider": fallback_provider, "model": fallback_model}
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


async def call_email_llm(prompt: str, system: str, max_tokens: int = 150) -> dict:
    """Route to email-specific LLM provider. Returns {text, usage}."""
    cfg = resolve_llm_config("email")
    provider, model = cfg["provider"], cfg["model"]

    logger.info(f"Email LLM call: provider={provider}, model={model}, max_tokens={max_tokens}")
    res = await _dispatch(provider, model, cfg["api_key"], prompt, system, max_tokens)
    return {**res, "provider": provider, "model": model}


async def call_cv_tailor_llm(prompt: str, system: str, max_tokens: int = 3000) -> dict:
    """Route to CV-tailoring-specific LLM provider. Returns {text, usage}."""
    cfg = resolve_llm_config("cv_tailor")
    provider, model = cfg["provider"], cfg["model"]

    logger.info(f"CV tailor LLM call: provider={provider}, model={model}, max_tokens={max_tokens}")
    res = await _dispatch(provider, model, cfg["api_key"], prompt, system, max_tokens)
    return {**res, "provider": provider, "model": model}


async def call_cover_letter_llm(prompt: str, system: str, max_tokens: int = 1500,
                                cached_prefix: str | None = None) -> dict:
    """Route to cover-letter-specific LLM provider; the resume + persona-preferences prefix caches on Claude API so regenerating in a different voice/length only pays for the JD suffix."""
    cfg = resolve_llm_config("cover_letter")
    provider, model = cfg["provider"], cfg["model"]

    logger.info(f"Cover-letter LLM call: provider={provider}, model={model}, max_tokens={max_tokens}, "
                f"caching={'on' if cached_prefix and provider == 'claude_api' else 'off'}")
    res = await _dispatch(provider, model, cfg["api_key"], prompt, system, max_tokens,
                          cached_prefix=cached_prefix)
    return {**res, "provider": provider, "model": model}


async def call_autofill_llm(prompt: str, system: str, max_tokens: int = 400,
                            cached_prefix: str | None = None) -> dict:
    """Route to autofill-specific LLM provider; the persona + qa_bank prefix caches on Claude API so regenerating with a different length/company only pays for the per-question suffix."""
    cfg = resolve_llm_config("autofill")
    provider, model = cfg["provider"], cfg["model"]

    logger.info(f"Autofill LLM call: provider={provider}, model={model}, max_tokens={max_tokens}, "
                f"caching={'on' if cached_prefix and provider == 'claude_api' else 'off'}")
    res = await _dispatch(provider, model, cfg["api_key"], prompt, system, max_tokens,
                          cached_prefix=cached_prefix)
    return {**res, "provider": provider, "model": model}


async def call_autofill_llm_stream(prompt: str, system: str, max_tokens: int = 400,
                                   cached_prefix: str | None = None):
    """Streaming version of call_autofill_llm; claude_api and openai/openrouter stream natively, other providers fall back to a single full-answer chunk."""
    cfg = resolve_llm_config("autofill")
    provider, model, api_key = cfg["provider"], cfg["model"], cfg["api_key"]

    if provider == "claude_api":
        async for c in _stream_claude(prompt, system, model, api_key, max_tokens, cached_prefix):
            yield c
        return
    combined = f"{cached_prefix}\n\n{prompt}" if cached_prefix else prompt
    if provider in ("openai", "openrouter"):
        base = "https://openrouter.ai/api/v1" if provider == "openrouter" else None
        async for c in _stream_openai(combined, system, model, api_key, max_tokens, base):
            yield c
        return
    # Non-streaming providers can't emit tokens as they generate, so simulate it:
    # fetch the full answer, then yield word-sized chunks so the draft still animates.
    import asyncio, re
    res = await _dispatch(provider, model, api_key, prompt, system, max_tokens, cached_prefix=cached_prefix)
    text = res.get("text", "") or ""
    for tok in re.findall(r"\S+\s*", text):
        yield tok
        await asyncio.sleep(0.012)


async def _stream_claude(prompt, system, model, api_key, max_tokens, cached_prefix):
    import anthropic, os
    key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
    client = anthropic.AsyncAnthropic(api_key=key)
    if cached_prefix:
        content = [
            {"type": "text", "text": cached_prefix, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": prompt},
        ]
    else:
        content = prompt
    async with client.messages.stream(model=model, max_tokens=max_tokens, system=system,
                                      messages=[{"role": "user", "content": content}]) as stream:
        async for text in stream.text_stream:
            yield text


async def _stream_openai(prompt, system, model, api_key, max_tokens, base_url=None):
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    stream = await client.chat.completions.create(
        model=model, max_tokens=max_tokens, stream=True,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            yield delta


async def _dispatch(provider: str, model: str, api_key: str,
                    prompt: str, system: str, max_tokens: int,
                    cached_prefix: str | None = None) -> dict:
    """Route to the correct provider; only `claude_api` supports prompt caching, others get cached_prefix concatenated into the prompt (no cache discount)."""
    if provider == "claude_api":
        return await _call_claude_api(prompt, system, model, api_key, max_tokens, cached_prefix=cached_prefix)
    combined = f"{cached_prefix}\n\n{prompt}" if cached_prefix else prompt
    if provider == "claude_code":
        return await _call_claude_code(combined, system, model, max_tokens)
    elif provider == "openai":
        return await _call_openai(combined, system, model, api_key, max_tokens)
    elif provider == "openrouter":
        # OpenRouter is OpenAI-API-compatible — same client, different base URL.
        # One key reaches every vendor's models (model slug is vendor-prefixed).
        return await _call_openai(combined, system, model, api_key, max_tokens,
                                  base_url="https://openrouter.ai/api/v1")
    elif provider == "ollama":
        return await _call_ollama(combined, system, model, max_tokens)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


async def _call_claude_api(prompt: str, system: str, model: str, api_key: str,
                           max_tokens: int, cached_prefix: str | None = None) -> dict:
    """Call Claude via the Anthropic SDK; cached_prefix is sent as a separate cache_control block for ~10x cheaper reuse, but is ignored below the 1024-token (Sonnet/Opus) minimum."""
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


async def _call_claude_code(prompt: str, system: str, model: str, max_tokens: int) -> dict:
    """Call Claude via claude CLI subprocess. Returns {text, usage}. Caching not supported."""
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

    raw = stdout.decode().strip()
    try:
        data = _json.loads(raw)
        text = data.get("result", raw)
    except _json.JSONDecodeError:
        text = raw

    return {
        "text": text.strip(),
        "usage": {"input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0, "cache_write_tokens": 0},
    }


async def _call_openai(prompt: str, system: str, model: str, api_key: str, max_tokens: int,
                       base_url: str | None = None) -> dict:
    """Call the OpenAI API, or any OpenAI-compatible endpoint via base_url."""
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)  # base_url=None → OpenAI default
    response = await client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    )
    usage = response.usage
    return {
        "text": response.choices[0].message.content.strip(),
        "usage": {
            "input_tokens": getattr(usage, "prompt_tokens", 0),
            "output_tokens": getattr(usage, "completion_tokens", 0),
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
        },
    }


async def _call_ollama(prompt: str, system: str, model: str, max_tokens: int) -> dict:
    """Call local Ollama instance. Returns {text, usage}."""
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
        data = response.json()
    return {
        "text": data["response"].strip(),
        "usage": {
            "input_tokens": data.get("prompt_eval_count", 0),
            "output_tokens": data.get("eval_count", 0),
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
        },
    }
