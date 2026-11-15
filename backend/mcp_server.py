"""MCP server at /api/mcp: tools for MCP clients such as Claude Code.

Each tool is one request to this backend's own REST API, sent in-process (no socket) with
the caller's own credentials (`_FORWARDED`). The auth middleware in
`backend.main` therefore checks the tool call exactly as it checks a REST call: the
install password, the account, the account's data scope. A tool holds no query logic.
Read tools send a GET; the few write tools send the POST that the dashboard sends for
the same action.

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
# Every header the auth middleware reads: the two of an API client and the cookies of
# a browser session. Whatever let the MCP request in must also let the tool's request
# in; a subset made the tool fail with a 401 after the MCP request itself passed.
_FORWARDED = ("x-api-key", "x-account-token", "cookie")
_ERROR_CHARS = 500

server = MCPServer(
    "JobNavigator",
    instructions=(
        "A JobNavigator install: jobs, searches, applications, resumes, "
        "cover letters, scrape runs and logs. All data belongs to the account of the "
        "X-Account-Token header. Most tools only read. update_jobs, tailor_resume and "
        "generate_cover_letter change data; the last two start LLM runs in the "
        "background, so start at most 2 runs, then wait with list_in_flight."
    ),
)


def _tool(**hints):
    # structured_output=False: the reply is the API's JSON text, sent one time.
    return server.tool(annotations=ToolAnnotations(openWorldHint=False, **hints),
                       structured_output=False)


_read_tool = _tool(readOnlyHint=True)


def _present(values: dict) -> dict:
    return {k: v for k, v in values.items() if v is not None}


async def _request(ctx: Context, method: str, path: str, *, params=None, body=None) -> str:
    """The JSON text of `method path` on this backend, as the caller of the tool."""
    from backend.main import app  # at call time: backend.main imports this module

    sent = ctx.headers or {}
    headers = {name: sent[name] for name in _FORWARDED if sent.get(name)}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                 base_url="http://jobnavigator") as client:
        resp = await client.request(method, path, params=params, json=body, headers=headers)
    if resp.status_code >= 400:
        raise ToolError(f"{method} {path} returned {resp.status_code}: {resp.text[:_ERROR_CHARS]}")
    return resp.text


async def _get(ctx: Context, path: str, **params) -> str:
    return await _request(ctx, "GET", path, params=_present(params))


async def _post(ctx: Context, path: str, **body) -> str:
    return await _request(ctx, "POST", path, body=_present(body))


# ── Read tools ───────────────────────────────────────────────────────────────

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
    `limit` is 200 at most. A row has `tailored_resume_id` when the job has a tailored
    resume. Use `get_job` for the description and the scoring report.
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


@_read_tool
async def list_in_flight(ctx: Context, job_ids: Optional[str] = None) -> str:
    """Runs in progress per job: {job_id: [{job_type, meta}]}, for example `tailor_resume`.

    `job_ids` is a comma-separated list of job ids. A job that is absent has no run now.
    """
    return await _get(ctx, "/api/monitor/in-flight", job_ids=job_ids, detail=True)


@_read_tool
async def get_run(ctx: Context, run_id: str) -> str:
    """One background run by its `run_id`: status, times and the error text of a failure."""
    return await _get(ctx, f"/api/monitor/run/{run_id}")


@_read_tool
async def list_resumes(ctx: Context, is_base: Optional[bool] = None) -> str:
    """Resumes without their content.

    `is_base=true` keeps the base resumes. `is_base=false` keeps the copies tailored
    for a job (they have `job_id`).
    """
    return await _get(ctx, "/api/resumes", is_base=is_base)


@_read_tool
async def list_cover_letters(ctx: Context, job_id: Optional[str] = None) -> str:
    """Cover letters, most recently updated first, optionally for one job."""
    return await _get(ctx, "/api/cover-letters", job_id=job_id)


@_read_tool
async def get_resume(ctx: Context, resume_id: str) -> str:
    """One resume with its content (`json_data`: header, summary, experience, skills)."""
    return await _get(ctx, f"/api/resumes/{resume_id}")


@_read_tool
async def get_cover_letter(ctx: Context, cover_letter_id: str) -> str:
    """One cover letter with its text (`json_data`), for a form that takes text, not a file."""
    return await _get(ctx, f"/api/cover-letters/{cover_letter_id}")


@_read_tool
async def get_persona(ctx: Context) -> str:
    """The Persona of the account: contact data and career facts for application forms."""
    return await _get(ctx, "/api/persona")


# ── Write tools ──────────────────────────────────────────────────────────────

@_tool(readOnlyHint=False, destructiveHint=False, idempotentHint=True)
async def update_jobs(ctx: Context, job_ids: list[str], status: Optional[str] = None,
                      saved: Optional[bool] = None, seen: Optional[bool] = None) -> str:
    """Set `status`, `saved` or `seen` on many jobs in one call.

    Usual `status` values: `new`, `saved`, `applied`, `skip`. The reply has `updated`
    (a count), `not_found` (ids) and `previous` ({job_id: the values before this call}).
    Keep `previous` to undo the change. For an application that was sent, use
    `mark_job_applied`: this tool sets the status only and creates no application.
    """
    updates = _present({"status": status, "saved": saved, "seen": seen})
    if not updates:
        raise ToolError("Give at least one of status, saved, seen")
    return await _post(ctx, "/api/jobs/bulk-update", job_ids=job_ids, updates=updates)


@_tool(readOnlyHint=False, destructiveHint=False, idempotentHint=True)
async def mark_job_applied(ctx: Context, job_id: str) -> str:
    """Record that the application for one job was sent: status `applied`.

    As in the dashboard, this creates the application (and the company when it is new).
    The reply is the job with `created_application_id` and `created_company_id`.
    """
    return await _request(ctx, "PATCH", f"/api/jobs/{job_id}", body={"status": "applied"})


@_tool(readOnlyHint=False, destructiveHint=True, idempotentHint=False)
async def tailor_resume(ctx: Context, base_resume_id: str, job_id: str) -> str:
    """Start a background LLM run that tailors a base resume for a job.

    The run replaces the tailored copy that the job already has. The reply has `run_id`
    and `chain_score`: a scoring run of that depth follows the tailor and also uses the
    runner. Wait with `list_in_flight` or `get_run`; then `get_job` has the new
    `tailored_resume_id`. A run for the same pair that is in progress gives a 409.
    """
    return await _post(ctx, "/api/resumes/tailor", base_resume_id=base_resume_id, job_id=job_id)


@_tool(readOnlyHint=False, destructiveHint=False, idempotentHint=False)
async def generate_cover_letter(ctx: Context, resume_id: str, job_id: str,
                                cover_letter_id: Optional[str] = None,
                                length: Optional[str] = None,
                                voice: Optional[str] = None) -> str:
    """Start a background LLM run that writes a cover letter from a resume for a job.

    Use the tailored copy of the job as `resume_id` when it exists. With
    `cover_letter_id` the run rewrites that letter; without it the run creates a letter.
    The reply has `run_id`. Wait with `list_in_flight` or `get_run`; then
    `list_cover_letters` with the `job_id` has the letter.
    """
    return await _post(ctx, "/api/cover-letters/generate", resume_id=resume_id,
                       job_id=job_id, cover_letter_id=cover_letter_id, length=length,
                       voice=voice)


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
