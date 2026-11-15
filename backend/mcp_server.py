"""MCP server at /api/mcp: read tools for MCP clients such as Claude Code.

Each tool is one GET on this backend's own REST API, sent in-process (no socket) with
the caller's `X-API-Key` and `X-Account-Token` headers. The auth middleware in
`backend.main` therefore checks the tool call exactly as it checks a REST call: the
install password, the account, the account's data scope. A tool holds no query logic.

Transport: streamable HTTP, stateless, plain JSON replies (no SSE stream, no session).
See docs/MCP.md for the client setup.
"""
from contextlib import asynccontextmanager
from typing import Literal, Optional

import httpx
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations

PATH = "/api/mcp"
# The headers the auth middleware reads from an API client. Cookies are for browsers.
_FORWARDED = ("x-api-key", "x-account-token")
_ERROR_CHARS = 500

server = MCPServer(
    "JobNavigator",
    instructions=(
        "Read-only view of a JobNavigator install: jobs, searches, companies, "
        "applications, scrape runs and logs. All data belongs to the account of the "
        "X-Account-Token header."
    ),
)


def _read_tool(fn):
    # structured_output=False: the reply is the API's JSON text, sent one time.
    return server.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False),
                       structured_output=False)(fn)


async def _get(ctx: Context, path: str, **params) -> str:
    """The JSON text of GET `path` on this backend, as the caller of the tool."""
    from backend.main import app  # at call time: backend.main imports this module

    sent = ctx.headers or {}
    headers = {name: sent[name] for name in _FORWARDED if sent.get(name)}
    query = {k: v for k, v in params.items() if v is not None}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                 base_url="http://jobnavigator") as client:
        resp = await client.get(path, params=query, headers=headers)
    if resp.status_code >= 400:
        raise ToolError(f"GET {path} returned {resp.status_code}: {resp.text[:_ERROR_CHARS]}")
    return resp.text


# ── Tools ────────────────────────────────────────────────────────────────────

@_read_tool
async def get_stats(ctx: Context) -> str:
    """Counts of jobs (total, new, saved) and of applications by status."""
    return await _get(ctx, "/api/stats")


@_read_tool
async def list_jobs(
    ctx: Context,
    status: Optional[str] = None,
    company: Optional[str] = None,
    min_score: Optional[int] = None,
    max_score: Optional[int] = None,
    search_id: Optional[str] = None,
    source: Optional[str] = None,
    saved: Optional[bool] = None,
    remote: Optional[bool] = None,
    location: Optional[str] = None,
    title_search: Optional[str] = None,
    sort_by: Literal["date", "score", "salary", "company"] = "date",
    limit: int = 20,
    offset: int = 0,
) -> str:
    """Job listings without the long text fields, plus the total count of matches.

    `status`, `company` and `source` accept comma-separated values. `min_score` and
    `max_score` filter on the best resume score (0-100). `search_id` is the id of a
    search from `list_searches`. `title_search` is a substring of the title.
    `limit` is 200 at most. Use `get_job` for the description and the scoring report.
    """
    return await _get(ctx, "/api/jobs", brief=True, status=status, company=company,
                      min_score=min_score, max_score=max_score, search_id=search_id,
                      source=source, saved=saved, remote=remote, location=location,
                      title_search=title_search, sort_by=sort_by, limit=limit, offset=offset)


@_read_tool
async def get_job(ctx: Context, job_id: str) -> str:
    """One job with all fields: description, scores, scoring report, H-1B data."""
    return await _get(ctx, f"/api/jobs/{job_id}")


@_read_tool
async def list_searches(ctx: Context) -> str:
    """All job-board searches with their configuration and the result of the last run."""
    return await _get(ctx, "/api/searches")


@_read_tool
async def list_companies(ctx: Context, active: Optional[bool] = None,
                         tier: Optional[int] = None) -> str:
    """Tracked companies with their career-page scrape configuration and counts."""
    return await _get(ctx, "/api/companies", active=active, tier=tier)


@_read_tool
async def list_applications(
    ctx: Context,
    status: Optional[Literal["applied", "interview", "offer", "rejected"]] = None,
    limit: int = 50,
    offset: int = 0,
) -> str:
    """Job applications, most recently updated first, plus the total count."""
    return await _get(ctx, "/api/applications", status=status, limit=limit, offset=offset)


@_read_tool
async def list_scheduled_jobs(ctx: Context) -> str:
    """Scheduler jobs (scrapes, email check, digest, backup): schedule, next run, state."""
    return await _get(ctx, "/api/scheduler/jobs")


@_read_tool
async def list_active_runs(ctx: Context) -> str:
    """Background runs in progress now (scrapes, scoring, email check), with elapsed time."""
    return await _get(ctx, "/api/monitor/active")


@_read_tool
async def list_run_history(ctx: Context, job_type: Optional[str] = None,
                           status: Optional[str] = None, limit: int = 30,
                           offset: int = 0) -> str:
    """Finished and running background runs, newest first.

    `job_type` is an exact run type such as `scrape_all` or `email_check`.
    """
    return await _get(ctx, "/api/monitor/history", job_type=job_type, status=status,
                      limit=limit, offset=offset)


@_read_tool
async def get_scrape_log(ctx: Context, errors_only: bool = False,
                         warnings_only: bool = False, limit: int = 30) -> str:
    """Scrape history per search and company, with the counts per job board.

    `errors_only` keeps the failed scrapes. `warnings_only` keeps the scrapes that
    returned 0 results.
    """
    return await _get(ctx, "/api/scrape-log", errors_only=errors_only,
                      warnings_only=warnings_only, limit=limit)


@_read_tool
async def list_failing_sources(ctx: Context, window: int = 3) -> str:
    """Active companies and searches whose last `window` scrapes all failed or returned 0 results."""
    return await _get(ctx, "/api/health/entities", window=window)


@_read_tool
async def get_activity_log(ctx: Context, type: Optional[str] = None,
                           company: Optional[str] = None, limit: int = 50,
                           offset: int = 0) -> str:
    """Activity log entries, newest first. `type` is exact; `company` is a substring."""
    return await _get(ctx, "/api/activity-log", type=type, company=company,
                      limit=limit, offset=offset)


@_read_tool
async def list_runners(ctx: Context) -> str:
    """State of the CLI runner containers (Claude Code, Codex, Antigravity)."""
    return await _get(ctx, "/api/llm/runners")


# ── ASGI endpoint ────────────────────────────────────────────────────────────

class _Endpoint:
    """The ASGI app behind the `/api/mcp` route.

    The SDK's session manager starts one time per instance, and the app lifespan starts
    more than one time in a test run. `run()` therefore builds a new HTTP app for each
    lifespan, and this object stays the stable route target.
    """

    def __init__(self):
        self._app = None

    async def __call__(self, scope, receive, send):
        if self._app is None:  # the app lifespan did not start (some test clients)
            await send({"type": "http.response.start", "status": 503,
                        "headers": [(b"content-type", b"text/plain")]})
            await send({"type": "http.response.body", "body": b"MCP server is not started"})
            return
        await self._app(scope, receive, send)

    @asynccontextmanager
    async def run(self):
        app = server.streamable_http_app(
            streamable_http_path=PATH, stateless_http=True, json_response=True,
            # The SDK's Host and Origin allowlist guards servers that have no auth on
            # localhost. Here the auth middleware rejects each request without the
            # install password header, and the public host name is not known in advance.
            transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
        )
        async with server.session_manager.run():
            self._app = app
            try:
                yield
            finally:
                self._app = None


endpoint = _Endpoint()
