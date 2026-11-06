"""Private authenticated lifecycle API. Its request schema cannot describe containers."""
import asyncio
from contextlib import asynccontextmanager
import hmac
import os
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict

from backend.cli_runner.auth import read_token
from backend.cli_runner.schemas import Completion
from backend.cli_runner.protocol import PROTOCOL_VERSION
from .controller import Catalog, Controller
from .docker import Docker, DockerError


class Desired(BaseModel):
    model_config = ConfigDict(extra="forbid")
    providers: list[Literal["codex_cli", "claude_code", "antigravity_cli"]]


def error(status, message):
    return JSONResponse(status_code=status, content={"protocol": PROTOCOL_VERSION,
                        "error": {"kind": "non_retryable", "message": message}})


def create_app(controller=None):
    management_enabled = os.getenv("JN_RUNNER_MANAGEMENT", "1").lower() in ("1", "true", "yes")
    @asynccontextmanager
    async def lifespan(app):
        control = controller
        if control is None:
            docker = Docker()
            project = None if os.getenv("JN_COMPOSE_PROJECT", "").strip() else await docker.own_project()
            control = Controller(docker, Catalog.environment(project))
        app.state.controller = control
        task = asyncio.create_task(app.state.controller.loop()) if management_enabled else None
        try:
            yield
        finally:
            if task is not None:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            await app.state.controller.close()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def authenticate(request: Request, call_next):
        if request.url.path == "/health" and request.method == "GET":
            return await call_next(request)
        try:
            token = read_token()
        except OSError:
            return error(503, "Runner credential is not initialized by the backend")
        supplied = request.headers.get("authorization", "")
        if not token or not hmac.compare_digest(supplied.encode(), f"Bearer {token}".encode()):
            return error(401, "Runner manager authentication failed")
        if not management_enabled:
            return error(409, "Automatic runner management is disabled")
        return await call_next(request)

    @app.exception_handler(RequestValidationError)
    async def invalid(request, exc):
        return error(422, "Invalid runner manager request")

    @app.get("/health")
    async def health():
        return {"status": "ok", "management_version": 1}

    @app.put("/v1/desired")
    async def desired(body: Desired, request: Request):
        control = request.app.state.controller
        control.desired(body.providers)
        return control.snapshot()

    @app.post("/v1/retry")
    async def retry(body: Desired, request: Request):
        control = request.app.state.controller
        control.retry(body.providers)
        return control.snapshot()

    @app.post("/v1/complete")
    async def complete(body: Completion, request: Request):
        try:
            response = await request.app.state.controller.complete(body)
            return Response(content=response.content, status_code=response.status_code,
                            media_type="application/json")
        except DockerError as exc:
            return error(503, str(exc))

    return app


app = create_app()
