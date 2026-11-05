"""HTTP transport to optional CLI runners. Account policy stays in llm_client."""
import os

import httpx

from backend.cli_runner.auth import ensure_token
from backend.cli_runner.protocol import (
    AGY_TIMEOUT, CLI_TIMEOUT, PROTOCOL_VERSION, SERVICES, CLITimeoutError,
    NonRetryableLLMError,
)


async def complete(provider, prompt, system, model, max_tokens, *, account_id=None,
                   claude_token="", effort=""):
    from backend.runner_management import enabled, manager_url
    service = SERVICES[provider]
    env_name = "JN_" + service.upper().replace("-", "_") + "_URL"
    base = os.getenv(env_name, f"http://{service}:8000").rstrip("/")
    if enabled():
        base = manager_url()
    payload = {"protocol": PROTOCOL_VERSION, "provider": provider, "prompt": prompt, "system": system,
               "model": model, "max_tokens": max_tokens, "effort": effort,
               "account_id": str(account_id) if account_id is not None else None,
               "claude_token": claude_token}
    # Codex performs a login-status check (up to 30s) before the completion.
    limit = AGY_TIMEOUT if provider == "antigravity_cli" else CLI_TIMEOUT + 30
    try:
        token = ensure_token()
    except (OSError, RuntimeError):
        raise NonRetryableLLMError("Cannot read or create the shared runner credential") from None
    try:
        # Never inherit a host HTTP proxy for this private service connection.
        async with httpx.AsyncClient(timeout=httpx.Timeout(limit + 10, connect=5), trust_env=False) as client:
            response = await client.post(f"{base}/v1/complete", json=payload,
                                         headers={"Authorization": f"Bearer {token}"})
    except httpx.ConnectError:
        if enabled():
            raise NonRetryableLLMError(
                "Runner manager is unavailable. Check provider status in Settings > Models and the runner-manager service.") from None
        raise NonRetryableLLMError(
            f"{service} is unavailable. Enable its Compose profile and run "
            f"`docker compose up -d {service}`.") from None
    except httpx.TransportError:
        # A lost response may already have consumed subscription quota. Don't replay it.
        raise NonRetryableLLMError(f"Lost connection to {service}; execution outcome is unknown") from None
    try:
        data = response.json()
        if not isinstance(data, dict) or data.get("protocol") != PROTOCOL_VERSION:
            raise ValueError("protocol mismatch")
        if not response.is_success:
            error = data.get("error") or {}
            message = str(error.get("message") or f"{service} failed")
            kind = error.get("kind")
            if kind == "timeout":
                raise CLITimeoutError(message)
            if kind == "non_retryable":
                raise NonRetryableLLMError(message)
            if kind == "retryable":
                raise RuntimeError(message)
            raise ValueError("unknown error")
        result = data["result"]
        if not isinstance(result, dict) or not isinstance(result.get("text"), str) or not isinstance(result.get("usage"), dict):
            raise ValueError("invalid result")
        return result
    except (ValueError, KeyError, TypeError, AttributeError):
        raise NonRetryableLLMError(
            f"{service} returned an incompatible response; rebuild/pull the backend and runner together") from None
