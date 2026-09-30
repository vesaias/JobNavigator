"""Provider-agnostic LLM client for scoring and analysis with automatic fallback."""
import asyncio
import logging
import os
import re
import uuid
from backend.models.db import SessionLocal, Setting

logger = logging.getLogger("jobnavigator.llm")


DEFAULT_PROVIDER = "claude_api"
DEFAULT_MODEL = "claude-sonnet-5"

# Reasoning-effort values each provider accepts; "" sends none, so the model uses its own default.
# The values a model takes vary inside one provider, so an unsupported pick fails with the provider's
# own error. antigravity_cli carries the effort in the model slug; ollama and lmstudio take none.
REASONING_EFFORTS = {
    "claude_api": ("low", "medium", "high", "xhigh", "max"),
    "claude_code": ("low", "medium", "high", "xhigh", "max"),
    "codex_cli": ("none", "low", "medium", "high", "xhigh", "max"),
    "openai": ("none", "low", "medium", "high", "xhigh", "max"),
    "openrouter": ("none", "minimal", "low", "medium", "high", "xhigh", "max"),
}
# The API providers count reasoning tokens against the output cap, and several current models reason
# by default (Sonnet 5, Opus 5.5, GPT-6 Sol). A cap sized for the answer alone can then go entirely to
# reasoning and return no text, so these calls get this much more room. Tokens are billed as used.
REASONING_HEADROOM = 16000
_CAPPED_PROVIDERS = ("claude_api", "openai", "openrouter")


def _get_setting(db, key, default=""):
    row = db.query(Setting).filter(Setting.key == key).first()
    return row.value if row and row.value else default


def resolve_llm_config(feature: str = "", db=None) -> dict:
    """Resolve the provider/model/api_key/effort a feature dispatches with: `<feature>_llm_*` setting -> primary `llm_*` setting -> shipped default. Single source of truth for both dispatch and logging."""
    own_db = db is None
    if own_db:
        db = SessionLocal()
    try:
        prefix = f"{feature}_" if feature else ""
        provider = _get_setting(db, f"{prefix}llm_provider", "")
        model = _get_setting(db, f"{prefix}llm_model", "")
        api_key = _get_setting(db, f"{prefix}llm_api_key", "")
        effort = _get_setting(db, f"{prefix}llm_effort", "")
        provider = provider or _get_setting(db, "llm_provider", "") or DEFAULT_PROVIDER
        if feature:
            model = model or _get_setting(db, "llm_model", "")
            api_key = api_key or _get_setting(db, "llm_api_key", "")
            # Effort values are per provider, so the Primary's effort carries over only to the same provider.
            if not effort and provider == (_get_setting(db, "llm_provider", "") or DEFAULT_PROVIDER):
                effort = _get_setting(db, "llm_effort", "")
        return {
            "provider": provider,
            "model": model or DEFAULT_MODEL,
            "api_key": api_key,
            "effort": effort,
        }
    finally:
        if own_db:
            db.close()


async def call_llm(prompt: str, system: str, max_tokens: int = 1200,
                   cached_prefix: str | None = None,
                   provider: str | None = None, model: str | None = None,
                   api_key: str | None = None, effort: str | None = None) -> dict:
    """Route to the configured LLM provider with retry + automatic fallback; provider/model/api_key/effort override the Primary for this call when given, else fall back to the llm_* settings."""
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
        if effort is None:
            effort = primary["effort"] if provider == primary["provider"] else ""
        fallback_provider = _get_setting(db, "llm_fallback_provider", "")
        fallback_model = _get_setting(db, "llm_fallback_model", "")
        fb_api_key = _get_setting(db, "llm_fallback_api_key", "")
        fb_effort = _get_setting(db, "llm_fallback_effort", "")
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
            res = await _dispatch(provider, model, api_key, prompt, system, max_tokens,
                                  cached_prefix=cached_prefix, effort=effort)
            return {**res, "provider": provider, "model": model}
        except Exception as e:
            last_primary_err = e
            if isinstance(e, NonRetryableLLMError):
                logger.warning(f"LLM primary failed, not retrying: {e}")
                break
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
                res = await _dispatch(fallback_provider, fallback_model, fb_api_key, prompt, system, max_tokens,
                                      cached_prefix=cached_prefix, effort=fb_effort)
                # Report the pair that actually answered so the caller logs the
                # fallback, not the primary it never reached.
                return {**res, "provider": fallback_provider, "model": fallback_model}
            except Exception as e:
                last_fallback_err = e
                if isinstance(e, NonRetryableLLMError):
                    logger.error(f"LLM fallback failed, not retrying: {e}")
                    break
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
    res = await _dispatch(provider, model, cfg["api_key"], prompt, system, max_tokens, effort=cfg["effort"])
    return {**res, "provider": provider, "model": model}


async def call_cv_tailor_llm(prompt: str, system: str, max_tokens: int = 3000) -> dict:
    """Route to CV-tailoring-specific LLM provider. Returns {text, usage}."""
    cfg = resolve_llm_config("cv_tailor")
    provider, model = cfg["provider"], cfg["model"]

    logger.info(f"CV tailor LLM call: provider={provider}, model={model}, max_tokens={max_tokens}")
    res = await _dispatch(provider, model, cfg["api_key"], prompt, system, max_tokens, effort=cfg["effort"])
    return {**res, "provider": provider, "model": model}


async def call_cover_letter_llm(prompt: str, system: str, max_tokens: int = 1500,
                                cached_prefix: str | None = None) -> dict:
    """Route to cover-letter-specific LLM provider; the resume + persona-preferences prefix caches on Claude API so regenerating in a different voice/length only pays for the JD suffix."""
    cfg = resolve_llm_config("cover_letter")
    provider, model = cfg["provider"], cfg["model"]

    logger.info(f"Cover-letter LLM call: provider={provider}, model={model}, max_tokens={max_tokens}, "
                f"caching={'on' if cached_prefix and provider == 'claude_api' else 'off'}")
    res = await _dispatch(provider, model, cfg["api_key"], prompt, system, max_tokens,
                          cached_prefix=cached_prefix, effort=cfg["effort"])
    return {**res, "provider": provider, "model": model}


async def call_autofill_llm(prompt: str, system: str, max_tokens: int = 400,
                            cached_prefix: str | None = None) -> dict:
    """Route to autofill-specific LLM provider; the persona + qa_bank prefix caches on Claude API so regenerating with a different length/company only pays for the per-question suffix."""
    cfg = resolve_llm_config("autofill")
    provider, model = cfg["provider"], cfg["model"]

    logger.info(f"Autofill LLM call: provider={provider}, model={model}, max_tokens={max_tokens}, "
                f"caching={'on' if cached_prefix and provider == 'claude_api' else 'off'}")
    res = await _dispatch(provider, model, cfg["api_key"], prompt, system, max_tokens,
                          cached_prefix=cached_prefix, effort=cfg["effort"])
    return {**res, "provider": provider, "model": model}


async def call_autofill_llm_stream(prompt: str, system: str, max_tokens: int = 400,
                                   cached_prefix: str | None = None):
    """Streaming version of call_autofill_llm; claude_api, openai, openrouter and opencode_go stream natively, other providers fall back to a single full-answer chunk."""
    cfg = resolve_llm_config("autofill")
    provider, model, api_key = cfg["provider"], cfg["model"], cfg["api_key"]
    effort = _supported_effort(provider, cfg["effort"])
    cap = _output_cap(provider, max_tokens, effort)

    if provider == "claude_api":
        async for c in _stream_claude(prompt, system, model, api_key, cap, cached_prefix, effort):
            yield c
        return
    combined = f"{cached_prefix}\n\n{prompt}" if cached_prefix else prompt
    if provider in ("openai", "openrouter", "opencode_go"):
        base = {"openrouter": OPENROUTER_BASE_URL, "opencode_go": OPENCODE_GO_BASE_URL}.get(provider)
        async for c in _stream_openai(combined, system, model, api_key, cap, base, effort):
            yield c
        return
    # Non-streaming providers can't emit tokens as they generate, so simulate it:
    # fetch the full answer, then yield word-sized chunks so the draft still animates.
    import asyncio, re
    res = await _dispatch(provider, model, api_key, prompt, system, max_tokens,
                          cached_prefix=cached_prefix, effort=effort)
    text = res.get("text", "") or ""
    for tok in re.findall(r"\S+\s*", text):
        yield tok
        await asyncio.sleep(0.012)


async def _stream_claude(prompt, system, model, api_key, max_tokens, cached_prefix, effort=""):
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
                                      messages=[{"role": "user", "content": content}],
                                      **_claude_effort_kwargs(effort)) as stream:
        async for text in stream.text_stream:
            yield text


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
# OpenRouter app attribution (lists the app on openrouter.ai/apps); ignored by other endpoints.
OPENROUTER_HEADERS = {"HTTP-Referer": "https://github.com/vesaias/JobNavigator", "X-Title": "JobNavigator"}

# OpenCode Go is a subscription whose models are served over an HTTP API
# (https://opencode.ai/zen/go/v1) with a Go API key. Go asks each client to identify itself with
# its own user agent and to send a stable session id per conversation (`x-opencode-session`) for
# routing and prompt caching; a missing session id is a 400 MissingSessionID, and a generic SDK
# user agent is what the docs warn against.
OPENCODE_GO_BASE_URL = "https://opencode.ai/zen/go/v1"
OPENCODE_USER_AGENT = "JobNavigator/1.0 (+https://github.com/vesaias/JobNavigator)"
_OPENCODE_SESSION = str(uuid.uuid4())   # stable for this backend process


def _openai_client(api_key: str, base_url: str | None):
    from openai import AsyncOpenAI
    if base_url == OPENROUTER_BASE_URL:
        headers = OPENROUTER_HEADERS
    elif base_url == OPENCODE_GO_BASE_URL:
        # Identify as JobNavigator, not the SDK, and send the session id Go routes on.
        headers = {"User-Agent": OPENCODE_USER_AGENT, "x-opencode-session": _OPENCODE_SESSION}
    else:
        headers = None
    return AsyncOpenAI(api_key=api_key, base_url=base_url, default_headers=headers)


def _claude_effort_kwargs(effort: str) -> dict:
    """Request kwargs for a Claude effort. The pinned SDK predates `output_config`, so it goes in the body."""
    return {"extra_body": {"output_config": {"effort": effort}}} if effort else {}


def _openai_kwargs(max_tokens: int, effort: str, base_url: str | None) -> dict:
    """The output cap and effort for an OpenAI-compatible request. OpenAI's reasoning models reject
    `max_tokens`, and `max_completion_tokens` is the cap every OpenAI chat model takes; compatible
    endpoints (OpenRouter, LM Studio) still read `max_tokens`. OpenRouter takes effort as `reasoning`."""
    kwargs = {"max_completion_tokens" if base_url is None else "max_tokens": max_tokens}
    if effort and base_url == OPENROUTER_BASE_URL:
        kwargs["extra_body"] = {"reasoning": {"effort": effort}}
    elif effort:
        kwargs["reasoning_effort"] = effort
    return kwargs


def _supported_effort(provider: str, effort: str) -> str:
    """The effort to send, or "" when the provider has no such value (a pick left from another provider)."""
    if effort and effort not in REASONING_EFFORTS.get(provider, ()):
        logger.warning(f"Reasoning effort {effort!r} is not a {provider} value; the model default applies")
        return ""
    return effort or ""


def _output_cap(provider: str, max_tokens: int, effort: str) -> int:
    """The cap to send. Claude API models reason by default, so they always get
    REASONING_HEADROOM. OpenAI and OpenRouter get it only when an effort is set: with the
    empty default a non-reasoning model such as gpt-4o (16,384 output ceiling) would be
    sent max_completion_tokens=16,600 and refuse every call. "none" never reasons.
    opencode_go also reasons by default and its picker has no effort to lower, so it always
    gets the room too."""
    if effort == "none":
        return max_tokens
    if provider == "opencode_go":
        return max_tokens + REASONING_HEADROOM
    if provider not in _CAPPED_PROVIDERS:
        return max_tokens
    if provider != "claude_api" and not effort:
        return max_tokens
    return max_tokens + REASONING_HEADROOM


async def _stream_openai(prompt, system, model, api_key, max_tokens, base_url=None, effort=""):
    client = _openai_client(api_key, base_url)
    stream = await client.chat.completions.create(
        model=model, stream=True,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        **_openai_kwargs(max_tokens, effort, base_url),
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            yield delta


async def _dispatch(provider: str, model: str, api_key: str,
                    prompt: str, system: str, max_tokens: int,
                    cached_prefix: str | None = None, effort: str = "") -> dict:
    """Route to the correct provider; only `claude_api` supports prompt caching, others get cached_prefix concatenated into the prompt (no cache discount). `effort` reaches only the providers in REASONING_EFFORTS."""
    effort = _supported_effort(provider, effort)
    max_tokens = _output_cap(provider, max_tokens, effort)
    if provider == "claude_api":
        return await _call_claude_api(prompt, system, model, api_key, max_tokens,
                                      cached_prefix=cached_prefix, effort=effort)
    combined = f"{cached_prefix}\n\n{prompt}" if cached_prefix else prompt
    if provider == "claude_code":
        return await _call_claude_code(combined, system, model, max_tokens, effort=effort)
    elif provider == "codex_cli":
        return await _call_codex_cli(combined, system, model, max_tokens, effort=effort)
    elif provider == "antigravity_cli":
        return await _call_antigravity_cli(combined, system, model, max_tokens)
    elif provider == "openai":
        return await _call_openai(combined, system, model, api_key, max_tokens, effort=effort)
    elif provider == "openrouter":
        # OpenRouter is OpenAI-API-compatible — same client, different base URL.
        # One key reaches every vendor's models (model slug is vendor-prefixed).
        return await _call_openai(combined, system, model, api_key, max_tokens,
                                  base_url=OPENROUTER_BASE_URL, effort=effort)
    elif provider == "opencode_go":
        # OpenCode Go (subscription) over its OpenAI-compatible endpoint; the model id is bare
        # (the CLI's `opencode-go/` prefix is a CLI alias, not part of the HTTP API).
        return await _call_opencode_go(combined, system, model, api_key, max_tokens, effort=effort)
    elif provider == "lmstudio":
        # LM Studio serves an OpenAI-compatible API on :1234; no key (client wants a non-empty string).
        # Override with LMSTUDIO_BASE_URL when the backend is containerized (e.g. http://host.docker.internal:1234/v1).
        base = os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
        # Thinking models (e.g. Qwen3) burn the whole max_tokens budget on reasoning and
        # return empty content; disable thinking for these structured-output calls.
        # LM Studio's OpenAI-compatible endpoint takes reasoning_effort="none" to turn it off.
        return await _call_openai(combined, system, model, api_key or "lm-studio", max_tokens,
                                  base_url=base,
                                  extra_body={"reasoning_effort": "none"})
    elif provider == "ollama":
        return await _call_ollama(combined, system, model, max_tokens)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


async def _call_claude_api(prompt: str, system: str, model: str, api_key: str,
                           max_tokens: int, cached_prefix: str | None = None, effort: str = "") -> dict:
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
        **_claude_effort_kwargs(effort),
    )

    # A model that thinks puts a thinking block first; the pinned SDK reads it as a TextBlock
    # with text=None, so only blocks typed "text" are the answer.
    text = "".join(b.text or "" for b in response.content if getattr(b, "type", "") == "text").strip()
    if not text and response.stop_reason == "max_tokens":
        raise NonRetryableLLMError(
            f"{model} used the whole output cap on reasoning and returned no text; lower the reasoning effort")

    # Extract usage — cache_* attributes may be absent on older SDK versions or non-cached calls
    usage = response.usage
    return {
        "text": text,
        "usage": {
            "input_tokens": getattr(usage, "input_tokens", 0),
            "output_tokens": getattr(usage, "output_tokens", 0),
            "cache_read_tokens": getattr(usage, "cache_read_input_tokens", 0) or 0,
            "cache_write_tokens": getattr(usage, "cache_creation_input_tokens", 0) or 0,
        },
    }


async def _call_claude_code(prompt: str, system: str, model: str, max_tokens: int, effort: str = "") -> dict:
    """Call Claude via claude CLI subprocess. Returns {text, usage}. Caching not supported."""
    import os
    import json as _json
    full_prompt = f"{system}\n\n{prompt}"
    cmd = ["claude", "-p", "--output-format", "json"]
    if model:
        cmd.extend(["--model", model])
    if effort:
        # A level the model lacks steps down to the highest one it has, so no error comes back.
        cmd.extend(["--effort", effort])

    # Build env: pass CLAUDE_CODE_OAUTH_TOKEN, explicitly EXCLUDE ANTHROPIC_API_KEY
    # so it uses subscription billing, not API credits
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}

    rc, stdout, stderr = await _run_cli(cmd, full_prompt.encode(), env=env)

    if rc != 0:
        error = stderr.decode(errors="replace").strip()
        raise RuntimeError(f"claude-code subprocess failed (rc={rc}): {error}")

    raw = stdout.decode().strip()
    try:
        data = _json.loads(raw)
        text = data.get("result", raw)
    except _json.JSONDecodeError:
        data, text = None, raw

    # `claude -p --output-format json` reports a refusal, an overload or a hit
    # quota as a rc=0 envelope with is_error set. Returning its text as if it
    # were the answer buried the reason in whatever the caller did next.
    if isinstance(data, dict) and (data.get("is_error") or data.get("subtype") not in (None, "success")):
        reason = (str(text or "").strip() or str(data.get("error") or "").strip()
                  or str(data.get("subtype") or "").strip() or "no reason given")
        if _QUOTA_RE.search(reason):
            raise NonRetryableLLMError(f"Claude Code usage limit reached: {reason[:300]}")
        raise RuntimeError(f"Claude Code reported an error: {reason[:300]}")
    if not str(text or "").strip():
        # Retryable on purpose: an empty completion is a bad minute, not a bad setup.
        raise RuntimeError("Claude Code returned an empty reply")

    return {
        "text": text.strip(),
        "usage": {"input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0, "cache_write_tokens": 0},
    }


class CLITimeoutError(RuntimeError):
    """A CLI that outran its wall clock, carrying whatever it printed before the kill."""

    def __init__(self, message: str, stdout: bytes = b"", stderr: bytes = b""):
        super().__init__(message)
        self.stdout = stdout
        self.stderr = stderr


class NonRetryableLLMError(RuntimeError):
    """A failure a retry cannot fix (not logged in, usage limit); call_llm goes straight to the fallback."""


CLI_TIMEOUT = 300   # seconds one subscription-CLI completion may take before it is killed
# codex exec processes share one auth.json and rewrite it on token refresh; OpenAI's docs say not
# to run many against the same file, so at most two at a time whatever the scoring limiter allows.
_codex_gate = asyncio.Semaphore(2)
_CODEX_LOGIN_HINT = "run `docker compose exec backend codex login --device-auth`"
_QUOTA_RE = re.compile(r"usage limit|rate limit|quota|too many requests|\b429\b", re.I)
# agy refreshes one shared OAuth token file, so hold the same limit codex gets.
_agy_gate = asyncio.Semaphore(2)
_AGY_LOGIN_HINT = "run `docker compose exec -it backend agy` and sign in"
_AGY_AUTH_RE = re.compile(r"authentication (required|failed)|not logged in|sign in", re.I)
_AGY_STATE = "~/.gemini/antigravity-cli"
# The deny list the image ships. It lives outside the state directory because agy rewrites
# settings.json on every start, and a read-only copy there only makes that write fail.
_AGY_SETTINGS_SOURCE = "/opt/antigravity-settings.json"


async def _run_cli(cmd: list[str], stdin: bytes, env: dict | None = None, timeout: float = CLI_TIMEOUT,
                   cwd: str | None = None):
    """Run a CLI to completion with a hard timeout; returns (rc, stdout, stderr)."""
    process = await asyncio.create_subprocess_exec(
        *cmd, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE, env=env, cwd=cwd,
    )
    reader = asyncio.ensure_future(process.communicate(input=stdin))
    try:
        # shield, so a timeout does not cancel the read: after the kill the same task
        # hands back what the process managed to print, which is how a caller can still
        # clean up after a call that hung.
        stdout, stderr = await asyncio.wait_for(asyncio.shield(reader), timeout)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        partial = (b"", b"")
        try:
            partial = await asyncio.wait_for(reader, 5) or partial
        except (asyncio.TimeoutError, OSError, ValueError, TypeError):
            pass
        raise CLITimeoutError(f"{cmd[0]} timed out after {int(timeout)}s", *partial)
    return process.returncode, stdout, stderr


async def _call_codex_cli(prompt: str, system: str, model: str, max_tokens: int, effort: str = "") -> dict:
    """Call Codex CLI using its existing ChatGPT login; run in an empty read-only workspace."""
    import json as _json
    import os
    import tempfile

    # like ANTHROPIC_API_KEY for claude_code: the plan pays, never an API key that happens to be set
    env = {k: v for k, v in os.environ.items() if k not in ("OPENAI_API_KEY", "CODEX_API_KEY")}
    async with _codex_gate:
        # `codex exec` without a login retries for ~15 s and then prints a 401 storm; the status
        # check answers in milliseconds and names the fix
        rc, _, _ = await _run_cli(["codex", "login", "status"], b"", env=env, timeout=30)
        if rc != 0:
            raise NonRetryableLLMError(f"Codex CLI is not logged in — {_CODEX_LOGIN_HINT}")

        full_prompt = f"{system}\n\n{prompt}"
        with tempfile.TemporaryDirectory(prefix="jobnavigator-codex-") as workdir:
            cmd = [
                "codex", "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules",
                "--skip-git-repo-check", "--sandbox", "read-only", "--color", "never",
                "-c", "web_search=disabled", "-c", "history.persistence=none",
                "-c", "check_for_update_on_startup=false",
                "--json", "-C", workdir,
            ]
            if model:
                cmd.extend(["--model", model])
            if effort:
                # -c parses its value as TOML, so the string is quoted.
                cmd.extend(["-c", f'model_reasoning_effort="{effort}"'])
            cmd.append("-")
            rc, stdout, stderr = await _run_cli(cmd, full_prompt.encode(), env=env)

    raw = stdout.decode(errors="replace").strip()
    text = ""
    failed = ""      # turn.failed carries the one readable reason (401, usage limit, model unknown)
    last_error = ""  # transport-level `error` events, the fallback reason when the turn never fails
    usage = {"input_tokens": 0, "output_tokens": 0,
             "cache_read_tokens": 0, "cache_write_tokens": 0}
    for line in raw.splitlines():
        try:
            event = _json.loads(line)
        except _json.JSONDecodeError:
            continue
        kind = event.get("type")
        if kind == "item.completed":
            item = event.get("item") or {}
            if item.get("type") == "agent_message" and item.get("text"):
                text = item["text"]
        elif kind == "turn.completed":
            token_usage = event.get("usage") or {}
            usage.update({
                "input_tokens": token_usage.get("input_tokens", 0) or 0,
                "output_tokens": token_usage.get("output_tokens", 0) or 0,
                "cache_read_tokens": token_usage.get("cached_input_tokens", 0) or 0,
            })
        elif kind == "turn.failed":
            failed = str((event.get("error") or {}).get("message") or "")
        elif kind == "error":
            last_error = str(event.get("message") or "")

    if failed or rc != 0:
        err_lines = stderr.decode(errors="replace").strip().splitlines()
        reason = failed or last_error or (err_lines[-1] if err_lines else "no output")
        if "401" in reason or "Unauthorized" in reason:
            raise NonRetryableLLMError(f"Codex CLI is not logged in — {_CODEX_LOGIN_HINT} ({reason})")
        if _QUOTA_RE.search(reason):
            raise NonRetryableLLMError(f"Codex usage limit reached: {reason}")
        raise RuntimeError(f"codex exec failed (rc={rc}): {reason}")
    if not text:
        raise RuntimeError("codex exec completed without an agent response")
    return {"text": text.strip(), "usage": usage}


def _agy_events(stdout: bytes):
    """Every NDJSON event agy printed, skipping any line that is not one."""
    import json as _json
    for line in stdout.decode(errors="replace").splitlines():
        try:
            yield _json.loads(line)
        except _json.JSONDecodeError:
            continue


def _agy_conversation_id(stdout: bytes) -> str:
    """The id agy gave this call. The init event carries it before any answer, which is all
    a timed-out call leaves behind."""
    for event in _agy_events(stdout):
        cid = event.get("conversation_id") or (event.get("result") or {}).get("conversation_id")
        if cid:
            return str(cid)
    return ""


def _agy_install_settings() -> list[str]:
    """Put the shipped deny list where agy reads it, and answer with the rules it must honour.
    agy rewrites settings.json as it starts, so the file has to be writable: pinning a
    read-only copy there makes the write fail and drops the CLI onto its defaults."""
    import json as _json
    import shutil
    import os
    target = os.path.join(os.path.expanduser(_AGY_STATE), "settings.json")
    try:
        with open(_AGY_SETTINGS_SOURCE, encoding="utf-8") as fh:
            source = fh.read()
    except OSError as e:
        raise NonRetryableLLMError(
            f"Antigravity deny list is missing at {_AGY_SETTINGS_SOURCE} ({e}); "
            "the agent would run unconstrained, so the call is refused")
    os.makedirs(os.path.dirname(target), exist_ok=True)
    try:
        current = open(target, encoding="utf-8").read()
    except OSError:
        current = ""
    if current != source:
        tmp = f"{target}.jobnavigator.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(source)
        shutil.move(tmp, target)
    return list(_json.loads(source).get("permissions", {}).get("deny", []))


def _agy_assert_denied(log_path: str, rules: list[str]) -> None:
    """Fail the call unless agy's own log says it loaded every deny rule.
    Without this the CLI can silently fall back to defaults and hand the agent
    `run_command` and `write_file` back, and nothing in the answer would show it."""
    try:
        with open(log_path, encoding="utf-8", errors="replace") as fh:
            loaded = [ln for ln in fh if "CLI settings initialized" in ln]
    except OSError:
        loaded = []
    if not loaded:
        raise NonRetryableLLMError(
            "Antigravity CLI never reported its permissions, so the deny list cannot be "
            "confirmed; the call is refused rather than run unconstrained")
    line = loaded[-1]
    missing = [r for r in rules if r not in line]
    if missing:
        raise NonRetryableLLMError(
            f"Antigravity CLI started without the deny rules {missing}; "
            "it would be free to read files and run commands, so the call is refused")


def _agy_discard(conversation_id: str) -> None:
    """Delete the per-call transcript agy writes. It holds the whole prompt — the resume text —
    and nothing reads it back, so it is disk growth and a copy of user data we do not want."""
    import glob
    import os
    import shutil
    home = os.path.expanduser(_AGY_STATE)
    for path in (*glob.glob(f"{home}/conversations/{conversation_id}.db*"),
                 f"{home}/presence/{conversation_id}.lock",
                 f"{home}/annotations/{conversation_id}.pbtxt",
                 f"{home}/brain/{conversation_id}"):
        try:
            shutil.rmtree(path) if os.path.isdir(path) else os.remove(path)
        except OSError:
            pass   # a leftover file is untidy, never a reason to fail a scored job


async def _call_antigravity_cli(prompt: str, system: str, model: str, max_tokens: int) -> dict:
    """Call Antigravity CLI on its Google subscription. The prompt rides on stdin as one NDJSON
    line because `-p` reads argv and argv caps near 128 KB. `max_tokens` is ignored: the CLI
    exposes no output cap. Tool use is blocked by a deny list installed before each call and
    confirmed from agy's own log afterwards — `--sandbox` restricts the terminal only, never
    the file tools."""
    import json as _json
    import os
    import tempfile

    # like ANTHROPIC_API_KEY for claude_code: the plan pays, never a key that happens to be set
    env = {k: v for k, v in os.environ.items()
           if k not in ("GEMINI_API_KEY", "GOOGLE_API_KEY",
                        "GOOGLE_APPLICATION_CREDENTIALS", "AGY_ADC_AUTH")}
    message = _json.dumps({"event": "user",
                           "message": {"role": "user", "content": f"{system}\n\n{prompt}"}})

    denied = _agy_install_settings()
    stdout = b""
    try:
        async with _agy_gate:
            with tempfile.TemporaryDirectory(prefix="jobnavigator-agy-") as workdir:
                # The log goes in the temp directory: it holds the permissions line this
                # call is checked against, and ~16 KB per call has no business surviving.
                log_path = os.path.join(workdir, "cli.log")
                # `-p` always swallows the next token, so it goes last with an attached empty value.
                cmd = ["agy", "--input-format", "stream-json", "--output-format", "stream-json",
                       "--print-timeout", f"{int(CLI_TIMEOUT)}s", "--log-file", log_path]
                if model:
                    cmd.extend(["--model", model])
                cmd.append("-p=")
                rc, stdout, stderr = await _run_cli(cmd, (message + "\n").encode(),
                                                    env=env, cwd=workdir)
                _agy_assert_denied(log_path, denied)
    except CLITimeoutError as e:
        stdout = e.stdout
        raise
    finally:
        # A timeout kills agy before the result event, so the id comes from the init event.
        # The transcript has to go exactly in that case too — it holds the whole prompt.
        conversation_id = _agy_conversation_id(stdout)
        if conversation_id:
            _agy_discard(conversation_id)

    result = {}
    for event in _agy_events(stdout):
        if event.get("event") == "result":
            result = event.get("result") or {}

    if result.get("status") != "SUCCESS" or rc != 0:
        err_lines = stderr.decode(errors="replace").strip().splitlines()
        reason = str(result.get("error") or "") or (err_lines[-1] if err_lines else "no output")
        if _AGY_AUTH_RE.search(reason):
            raise NonRetryableLLMError(f"Antigravity CLI is not logged in — {_AGY_LOGIN_HINT} ({reason})")
        if _QUOTA_RE.search(reason):
            raise NonRetryableLLMError(f"Antigravity usage limit reached: {reason}")
        raise RuntimeError(f"agy failed (rc={rc}): {reason}")

    text = str(result.get("response") or "").strip()
    if not text:
        raise RuntimeError("agy completed without a response")
    usage = result.get("usage") or {}
    return {
        "text": text,
        "usage": {
            "input_tokens": usage.get("input_tokens", 0) or 0,
            "output_tokens": usage.get("output_tokens", 0) or 0,
            "cache_read_tokens": usage.get("cache_read_tokens", 0) or 0,
            "cache_write_tokens": 0,
        },
    }


async def _call_openai(prompt: str, system: str, model: str, api_key: str, max_tokens: int,
                       base_url: str | None = None, extra_body: dict | None = None, effort: str = "") -> dict:
    """Call the OpenAI API, or any OpenAI-compatible endpoint via base_url."""
    client = _openai_client(api_key, base_url)  # base_url=None → OpenAI default
    kwargs = _openai_kwargs(max_tokens, effort, base_url)
    if extra_body:
        kwargs["extra_body"] = {**kwargs.get("extra_body", {}), **extra_body}
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        **kwargs,
    )
    choice = response.choices[0]
    text = (choice.message.content or "").strip()
    if not text and choice.finish_reason == "length":
        raise NonRetryableLLMError(
            f"{model} used the whole output cap on reasoning and returned no text; lower the reasoning effort")
    usage = response.usage
    return {
        "text": text,
        "usage": {
            "input_tokens": getattr(usage, "prompt_tokens", 0),
            "output_tokens": getattr(usage, "completion_tokens", 0),
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
        },
    }


async def _call_opencode_go(prompt: str, system: str, model: str, api_key: str, max_tokens: int,
                            effort: str = "") -> dict:
    """OpenCode Go over its OpenAI-compatible HTTP API. A Go API key is required, so a missing
    key is a config error, not a retry."""
    try:
        return await _call_openai(prompt, system, model, api_key, max_tokens,
                                  base_url=OPENCODE_GO_BASE_URL, effort=effort)
    except NonRetryableLLMError:
        raise
    except Exception as e:
        status = getattr(e, "status_code", None)
        body = str(e)
        if status == 401 or "Missing API key" in body:
            raise NonRetryableLLMError(
                "OpenCode Go needs an API key — paste it under Settings › AI") from e
        if status in (400, 404) and "model" in body.lower():
            # Go serves only some models on /chat/completions; GPT and Grok use /responses, and
            # MiniMax and Qwen use the Anthropic /messages API.
            raise NonRetryableLLMError(
                f"OpenCode Go does not serve '{model}' on the chat/completions endpoint — pick a "
                f"model whose endpoint is /chat/completions (GPT, Grok, MiniMax and Qwen use others)") from e
        raise


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
