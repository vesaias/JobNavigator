"""Private HTTP API, one provider per container; no Docker socket or database."""
import asyncio
import hmac
import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from . import runtime
from .auth import read_token
from .protocol import PROTOCOL_VERSION, SERVICES, CLITimeoutError, NonRetryableLLMError
from .schemas import Completion


def failure(status, kind, message):
    return JSONResponse(status_code=status, content={"protocol": PROTOCOL_VERSION,
                        "error": {"kind": kind, "message": message}})


def create_app(provider=None):
    provider = provider or os.getenv("JN_RUNNER_PROVIDER", "")
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.state.active_requests = 0
    # One uvicorn worker. Fast rejection avoids minutes spent waiting outside CLI timeouts.
    slots = asyncio.Semaphore(2)

    @app.middleware("http")
    async def authenticate(request: Request, call_next):
        if request.url.path == "/health" and request.method == "GET":
            return await call_next(request)
        try:
            token = read_token()
        except OSError:
            return failure(503, "non_retryable", "Runner credential is not initialized by the backend")
        supplied = request.headers.get("authorization", "")
        if not token or not hmac.compare_digest(supplied.encode(), f"Bearer {token}".encode()):
            return failure(401, "non_retryable", "Runner authentication failed")
        return await call_next(request)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        # Pydantic's default validation response can echo the body, including OAuth tokens.
        return failure(422, "non_retryable", "Invalid runner request or protocol version")

    @app.get("/health")
    async def health():
        return {"status": "ok", "provider": provider, "protocol": PROTOCOL_VERSION}

    @app.get("/v1/status")
    async def status():
        return {"management_version": 1, "protocol": PROTOCOL_VERSION,
                "provider": provider, "active_requests": app.state.active_requests}

    @app.post("/v1/complete")
    async def complete(body: Completion):
        if provider not in SERVICES:
            return failure(503, "non_retryable", "Runner provider is not configured")
        if body.provider != provider:
            return failure(409, "non_retryable", "Request provider does not match this runner")
        if slots.locked():
            return failure(503, "non_retryable", "Runner is busy; try again when a call finishes")
        async with slots:
            app.state.active_requests += 1
            secret = body.claude_token.get_secret_value()
            try:
                result = await runtime.execute(provider, body.prompt, body.system, body.model,
                                               body.max_tokens, account_id=body.account_id,
                                               claude_token=secret, effort=body.effort)
                return {"protocol": PROTOCOL_VERSION, "result": result}
            except CLITimeoutError as exc:
                return failure(504, "timeout", str(exc))
            except NonRetryableLLMError as exc:
                message = str(exc).replace(secret, "[redacted]") if secret else str(exc)
                return failure(422, "non_retryable", message)
            except RuntimeError as exc:
                message = str(exc).replace(secret, "[redacted]") if secret else str(exc)
                return failure(502, "retryable", message)
            except Exception:
                # Don't expose environment variables, paths or request bodies in tracebacks.
                return failure(500, "non_retryable", "Runner execution failed; check its installation")
            finally:
                app.state.active_requests -= 1

    return app


app = create_app()
