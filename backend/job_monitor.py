"""Job execution monitor — tracks running state and run history (Hangfire-style)."""
import asyncio
import contextvars
import logging
import re
import uuid
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from backend.accounts.context import current_account, owner_account_id, owner_context, owner_unlocked
from backend.models.db import SessionLocal, JobRun
from backend.accounts.settings import get_setting

logger = logging.getLogger("jobnavigator.monitor")


# ── Background concurrency limiters ────────────────────────────────────────
# One place decides how many background tasks of a kind may run at once. The
# gate is taken in launch_background's wrapper — BEFORE the worker opens its
# first DB session — so N queued tasks cost N cheap coroutines, not N pooled
# connections. Scoring 80 jobs used to fan out 80 tasks that each opened a
# session and then waited minutes on the LLM, which drained the QueuePool and
# left even /health unable to get a connection.


class TaskLimiter:
    """A named concurrency gate, re-entrant within one task.

    Re-entrancy matters because the same limit is enforced at two levels: the
    launcher takes it for a whole background run, and helpers such as
    `cv_scorer.score_job_sync` take it for their own LLM call (they are also
    reachable outside launch_background). A plain Semaphore would deadlock on
    the inner acquire; here the inner `async with` just bumps a per-task depth.
    """

    def __init__(self, name: str, value: int):
        self.name = name
        self.value = max(1, int(value))
        self._sem = asyncio.Semaphore(self.value)
        self._loop = None
        self._depth: contextvars.ContextVar[int] = contextvars.ContextVar(
            f"jn_limiter_{name}", default=0
        )

    def _semaphore(self) -> asyncio.Semaphore:
        # An asyncio.Semaphore binds to the loop that first blocks on it. The
        # app has one loop, but the test suite runs each case in a fresh one,
        # so rebind rather than raising "bound to a different event loop".
        loop = asyncio.get_running_loop()
        if self._loop is not loop:
            self._sem = asyncio.Semaphore(self.value)
            self._loop = loop
        return self._sem

    async def __aenter__(self):
        depth = self._depth.get()
        if depth == 0:
            await self._semaphore().acquire()
        self._depth.set(depth + 1)
        return self

    async def __aexit__(self, *exc_info):
        depth = self._depth.get() - 1
        self._depth.set(depth)
        if depth == 0:
            self._sem.release()
        return False


# name -> (settings key that carries the limit, fallback when unset/unreadable)
_LIMIT_SOURCES: dict[str, tuple[Optional[str], int]] = {
    "scoring": ("scoring_max_concurrent", 5),
    "tailoring": ("tailoring_max_concurrent", 2),
    # Page caching is httpx + BeautifulSoup and, on thin pages, a whole
    # Chromium. Four at a time is the difference between ~300 MB and the 2.5 GB
    # the box hit; it is deliberately not user-tunable.
    "page_cache": (None, 4),
    # Every scrape (Run all, one company, one search, the scheduled run) can start its own
    # Chromium; one at a time keeps two accounts' Run alls from doubling the memory.
    "scraping": ("scrape_max_concurrent", 1),
}
# Upper bounds a setting cannot exceed.
_LIMIT_MAX: dict[str, int] = {"scraping": 2}

# Which gate a launch_background job_type belongs to. Anything absent runs
# unlimited — backups are already deduped by scope key.
_JOB_TYPE_LIMITER: dict[str, str] = {
    "analyze_job": "scoring",
    "score_resume": "scoring",
    "tailor_resume": "tailoring",
    "generate_cover_letter": "tailoring",
    "cache_job_page": "page_cache",
    "scrape_all": "scraping",
    "company_scrape": "scraping",
    "search_run": "scraping",
}

_limiters: dict[str, TaskLimiter] = {}


def _resolve_limit(name: str) -> int:
    setting_key, fallback = _LIMIT_SOURCES.get(name, (None, 4))
    if not setting_key:
        return fallback
    try:
        db = SessionLocal()
        try:
            raw = get_setting(db, setting_key)
            value = max(1, int(raw)) if raw else fallback
        finally:
            db.close()
    except Exception:
        value = fallback
    return min(value, _LIMIT_MAX.get(name, value))


def get_limiter(name: str) -> TaskLimiter:
    """The process-wide gate called `name`, created on first use."""
    limiter = _limiters.get(name)
    if limiter is None:
        limiter = TaskLimiter(name, _resolve_limit(name))
        _limiters[name] = limiter
        logger.info("Background limiter '%s' initialized: max %d concurrent",
                    name, limiter.value)
    return limiter


def reset_limiter(name: Optional[str] = None) -> None:
    """Drop cached limiters so the next use re-reads its limit from settings."""
    if name is None:
        _limiters.clear()
    else:
        _limiters.pop(name, None)


def limiter_for_job_type(job_type: str) -> Optional[TaskLimiter]:
    name = _JOB_TYPE_LIMITER.get(job_type)
    return get_limiter(name) if name else None

# ── In-memory running state ────────────────────────────────────────────────


@dataclass
class RunningJob:
    run_id: uuid.UUID
    job_type: str
    trigger: str
    started_at: datetime
    task: Optional[asyncio.Task] = None
    scope_key: Optional[str] = None
    target_job_id: Optional[uuid.UUID] = None
    # The Company this run targets, when it has one (company_scrape); carried separately from
    # scope_key so the dashboard can match a running scrape to a row by id, not by name+time.
    company_id: Optional[str] = None
    # "What this run did", shown in Stats > Run history; set via `run.summary = ...` in
    # tracked_run, or by a launch_background coroutine returning a string.
    summary: Optional[str] = None
    # Same dict stored on the JobRun row: what this run is about (which résumés a
    # scoring run covers, which base a tailor copies from). Read by /monitor/in-flight?detail=1.
    meta: Optional[dict] = None
    # The account the run acts for (MT-6). None = the owner (entries made before MT-6,
    # and install-wide system runs).
    account_id: Optional[uuid.UUID] = None
    # QA F3 / R2-08: the run writes into every account (the scheduled scrape_all fan-out,
    # the H-1B refresh), whatever its account_id says.
    all_accounts: bool = False
    # Queued behind its gate (another scrape, the scoring limit): started_at is reset when
    # the run gets its slot, so queue time is not counted as run time.
    waiting: bool = False
    # The outcome of a launch_background run, set when it ends, for a caller that holds
    # this object (`wait_for_run`): the failure text (None = completed) and what the run
    # created (`note_run_created`). The JobRun row carries the same.
    error: Optional[str] = None
    created: Optional[dict] = None


# Keyed by dedup key (e.g. "scrape_all" or "company_scrape:<uuid>"); a member's runs
# carry "@<account id>" so each account dedups its own runs (see _make_key).
_running: dict[str, RunningJob] = {}

# Runs that act on the whole install: one at a time for everyone, keyed and shown as
# the owner's. Everything else is per account.
INSTALL_WIDE_JOB_TYPES = frozenset({"db_backup", "h1b_refresh"})   # LinkedIn session refresh is per account since MT-16


# Job types whose run writes into every account's rows (R2-08).
ALL_ACCOUNT_JOB_TYPES = frozenset({"h1b_refresh"})


# ── Account removal guard (QA F3 / R2-08) ──────────────────────────────────
# DELETE /accounts/{id} asks `runs_touching(id)` before its pg_dump and again after it.
# Meanwhile the account is marked as being removed: no run starts for it, no all-account
# run starts at all, and `for_each_account` skips it. `for_each_account` also registers
# the accounts it is about to visit (`fanning_out`), so a scheduled per-account sweep
# counts as busy for an account it has not reached yet.
_removing: set = set()
_fanouts: dict = {}          # id(token) -> frozenset of account ids still to visit or visiting


def begin_removal(account_id) -> None:
    _removing.add(account_id)


def end_removal(account_id) -> None:
    _removing.discard(account_id)


def is_removing(account_id) -> bool:
    return account_id is not None and account_id in _removing


@contextmanager
def fanning_out(account_ids):
    token = object()
    _fanouts[id(token)] = frozenset(a for a in account_ids if a is not None)
    try:
        yield
    finally:
        _fanouts.pop(id(token), None)


def runs_touching(account_id) -> list:
    """Descriptions of in-memory work that writes (or is about to write) into
    `account_id`: its own runs, every all-account run, every per-account sweep that
    includes it."""
    out = []
    for r in list(_running.values()):
        if r.account_id == account_id or r.all_accounts:
            out.append(r.job_type)
    if any(account_id in ids for ids in list(_fanouts.values())):
        out.append("scheduled per-account job")
    return out


def _owner_id() -> Optional[uuid.UUID]:
    try:
        return owner_account_id()
    except Exception:
        return None


def _run_account(job_type: Optional[str] = None) -> Optional[uuid.UUID]:
    """The account a run started now belongs to: the context's, None (= owner) for the
    owner, for no context, and for install-wide job types."""
    if job_type in INSTALL_WIDE_JOB_TYPES:
        return None
    acc = current_account.get()
    if acc is None or acc == _owner_id():
        return None
    return acc


def _viewer_account() -> Optional[uuid.UUID]:
    """The account whose runs the caller sees, in the same None-means-owner form."""
    return _run_account()


def _make_key(job_type: str, scope_key: Optional[str] = None, account_id: Optional[uuid.UUID] = None) -> str:
    """Dedup key. The owner keeps the pre-MT-6 keys ("scrape_all", "company_scrape:<id>");
    a member's key adds "@<account>", so account B can start the same job for itself
    while A's run is going (409 only within one account)."""
    key = f"{job_type}:{scope_key}" if scope_key else job_type
    return f"{key}@{account_id}" if account_id is not None else key


def visible_running(all_accounts: bool = False) -> list[RunningJob]:
    """In-memory runs of the current account. `all_accounts=True` is the hook for the
    owner's "every account" view (later UI work); nothing passes it yet."""
    if all_accounts:
        return list(_running.values())
    viewer = _viewer_account()
    return [r for r in list(_running.values()) if r.account_id == viewer]


# ── "Finished, but it did not work" ────────────────────────────────────────
# Some tracked coroutines swallow their own exception and return a human summary
# instead ("Scoring failed" when the LLM provider is down). The run then reads as
# `completed` in Stats and as an OK toast in the dashboard, and the outage is
# only visible in llm_call_log (R4-T1-28). A coroutine calls mark_run_failed()
# to say "keep my summary, but this run failed, and here is why".
#
# A ContextVar keeps it per-task: launch_background's wrapper runs in its own
# task context, and each scheduled job owns its own too, so two concurrent runs
# never see each other's reason.
_run_failure: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "jn_run_failure", default=None
)


# A DBAPI error string carries the failed statement, its bound parameters and
# the driver module path. JobRun.error stored all three, and
# /api/monitor/history returned them to the browser. Reduce the text to the
# message before it is stored, and again before it is returned, because rows
# written before this fix still hold the raw string.
MAX_RUN_ERROR_CHARS = 1000
_SQL_BLOCK = "[SQL:"
_DRIVER_PREFIX_RE = re.compile(r"^\((?:\w+\.)+(\w+)\)\s*")


def sanitize_run_error(error: Optional[str]) -> Optional[str]:
    """Return the message of a run error without the SQL, the parameters or the driver module path."""
    if error is None:
        return None
    text = str(error).split(_SQL_BLOCK, 1)[0].strip()
    text = _DRIVER_PREFIX_RE.sub(r"\1: ", text)
    if len(text) > MAX_RUN_ERROR_CHARS:
        text = text[:MAX_RUN_ERROR_CHARS].rstrip() + "..."
    return text or None


def mark_run_failed(reason: str) -> None:
    """Flag the currently tracked run as failed while still returning a summary."""
    if reason:
        _run_failure.set(str(reason)[:MAX_RUN_ERROR_CHARS])


def _take_run_failure() -> Optional[str]:
    reason = _run_failure.get()
    _run_failure.set(None)
    return reason


# What the tracked run created, for a caller that follows it by run id: the ids go to
# JobRun.meta["created"], because result_summary is text for people. Per task, like
# _run_failure; a new dict on each note, so a run launched from inside another one
# (which copies the context) never shares its parent's dict.
_run_created: contextvars.ContextVar[Optional[dict]] = contextvars.ContextVar(
    "jn_run_created", default=None
)


def note_run_created(**ids) -> None:
    """Record ids of what the currently tracked run created (resume_id, chained_run_id, ...)."""
    _run_created.set({**(_run_created.get() or {}), **{k: str(v) for k, v in ids.items() if v}})


def _take_run_created() -> Optional[dict]:
    created = _run_created.get()
    _run_created.set(None)
    return created


# The run that the current task is, for a worker that reports progress while it runs
# (set by launch_background and tracked_run; a run launched from inside another one
# sets its own).
_current_run: contextvars.ContextVar[Optional["RunningJob"]] = contextvars.ContextVar(
    "jn_current_run", default=None
)


def current_run_id() -> Optional[str]:
    run = _current_run.get()
    return str(run.run_id) if run else None


def save_run_meta(meta: dict) -> None:
    """Replace the meta of the currently tracked run, in memory and on its JobRun row,
    so a reader of the run sees its progress before it ends."""
    run = _current_run.get()
    if run is None:
        return
    run.meta = meta
    db = SessionLocal()
    try:
        row = (db.query(JobRun).filter(JobRun.id == run.run_id)
               .execution_options(jn_unscoped=True).first())
        if row:
            row.meta = meta
            db.commit()
    finally:
        db.close()


async def wait_for_run(run_id) -> Optional["RunningJob"]:
    """Wait until the launch_background run with this id ends; return it with its outcome
    (`error`, `created`), or None when no such run is running in this process.
    `asyncio.wait`, so that cancelling the waiter does not cancel the run."""
    run = next((r for r in _running.values() if str(r.run_id) == str(run_id)), None)
    if run is not None and run.task is not None:
        await asyncio.wait({run.task})
    return run


class JobAlreadyRunningError(Exception):
    def __init__(self, job_type: str, elapsed_seconds: float):
        self.job_type = job_type
        self.elapsed_seconds = elapsed_seconds
        super().__init__(
            f"{job_type} is already running ({elapsed_seconds:.0f}s elapsed)"
        )


class AccountBeingRemovedError(JobAlreadyRunningError):
    """A run would write into an account that is being removed (R2-08). A subclass of
    JobAlreadyRunningError so every caller's 409 / "Scheduler skipped" path handles it."""
    def __init__(self, job_type: str):
        Exception.__init__(self, f"{job_type} not started: an account is being removed")
        self.job_type = job_type
        self.elapsed_seconds = 0.0


def _refuse_during_removal(job_type: str, account, all_accounts: bool) -> None:
    if is_removing(account) or (all_accounts and _removing):
        raise AccountBeingRemovedError(job_type)


# ── Scrape overlap (QA F6 / R4-01, R4-02) ──────────────────────────────────
# The scheduled scrape_all is one install-wide run that ingests into every account. A
# manual scrape (Run all, one company, one search) started while it is live would fetch
# and ingest the same targets for the same account a second time, so it is refused with
# 409 `scheduled_scrape_running`. The reverse is not refused: a scheduled tick that finds
# manual scrapes in flight runs for everything else and leaves those out
# (`manual_scrape_scopes`), recording them in its summary.
SCRAPE_JOB_TYPES = frozenset({"scrape_all", "company_scrape", "search_run"})
# The scheduled run's scope key: it never collides with the owner's manual Run all
# ("scrape_all"), so that manual run no longer makes the whole tick skip (R4-02).
SCHEDULED_SCRAPE_SCOPE = "scheduled"


class ScheduledScrapeRunningError(JobAlreadyRunningError):
    """A manual scrape was asked for while the scheduled scrape_all is live (R4-01)."""
    code = "scheduled_scrape_running"

    def __init__(self, job_type: str, elapsed_seconds: float):
        Exception.__init__(self, _scheduled_scrape_message(job_type, elapsed_seconds))
        self.job_type = job_type
        self.elapsed_seconds = elapsed_seconds


def _scheduled_scrape_message(job_type: str, elapsed_seconds: float) -> str:
    return (f"{job_type} not started: the scheduled scrape is running "
            f"({elapsed_seconds:.0f}s elapsed); try again when it finishes")


def scheduled_scrape_run() -> Optional[RunningJob]:
    """The live scheduled scrape_all, if any."""
    for r in list(_running.values()):
        if r.job_type == "scrape_all" and r.trigger == "scheduler":
            return r
    return None


def _refuse_during_scheduled_scrape(job_type: str, trigger: str) -> None:
    if job_type not in SCRAPE_JOB_TYPES or trigger == "scheduler":
        return
    live = scheduled_scrape_run()
    if live is not None:
        elapsed = (datetime.now(timezone.utc) - live.started_at).total_seconds()
        raise ScheduledScrapeRunningError(job_type, elapsed)


def scheduled_scrape_conflict_response(e: JobAlreadyRunningError):
    """The 409 body of a refused manual scrape: `scheduled_scrape_running` for the R4-01
    case (the dashboard tells the user to wait), the usual text otherwise."""
    from fastapi.responses import JSONResponse
    if isinstance(e, ScheduledScrapeRunningError):
        # Rebuilt from the fields, not str(e): no exception text goes to a client.
        message = _scheduled_scrape_message(str(e.job_type), float(e.elapsed_seconds))
        return JSONResponse(status_code=409, content={
            "detail": ScheduledScrapeRunningError.code, "message": message})
    return JSONResponse(status_code=409, content={"detail": f"{e.job_type} is already running"})


@dataclass
class ManualScrapeScopes:
    """What manual scrapes are fetching right now, for the scheduled tick to leave out."""
    accounts: set            # accounts with a manual Run all in flight (owner = its real id)
    company_ids: set         # companies with a manual single-company scrape in flight
    search_ids: set          # searches with a manual single-search run in flight

    def __bool__(self):
        return bool(self.accounts or self.company_ids or self.search_ids)


def manual_scrape_scopes() -> ManualScrapeScopes:
    out = ManualScrapeScopes(set(), set(), set())
    for r in list(_running.values()):
        if r.trigger == "scheduler" or r.job_type not in SCRAPE_JOB_TYPES:
            continue
        if r.job_type == "scrape_all":
            out.accounts.add(r.account_id if r.account_id is not None else _owner_id())
        elif r.job_type == "company_scrape" and r.scope_key:
            out.company_ids.add(str(r.scope_key))
        elif r.job_type == "search_run" and r.scope_key:
            out.search_ids.add(str(r.scope_key))
    return out


def is_running(job_type: str, scope_key: Optional[str] = None) -> Optional[RunningJob]:
    """The current account's run of this job type and scope, if one is going."""
    return _running.get(_make_key(job_type, scope_key, _run_account(job_type)))


def get_all_running(all_accounts: bool = False) -> list[dict]:
    now = datetime.now(timezone.utc)
    return [
        {
            "run_id": str(r.run_id),
            "job_type": r.job_type,
            "trigger": r.trigger,
            "started_at": r.started_at.isoformat(),
            "elapsed_seconds": round((now - r.started_at).total_seconds(), 1),
            "scope_key": r.scope_key,
            "target_job_id": str(r.target_job_id) if r.target_job_id else None,
            "company_id": str(r.company_id) if r.company_id else None,
            "waiting": r.waiting,
        }
        for r in visible_running(all_accounts)
    ]


def _get_running_by_job_type(job_type: str) -> Optional[dict]:
    """Check if any of the current account's jobs with the given job_type is running (ignoring scope_key)."""
    runs = list(_running.values()) if job_type in INSTALL_WIDE_JOB_TYPES else visible_running()
    for r in runs:
        if r.job_type == job_type:
            now = datetime.now(timezone.utc)
            return {
                "run_id": str(r.run_id),
                "elapsed_seconds": round((now - r.started_at).total_seconds(), 1),
                "waiting": r.waiting,
            }
    return None


# ── DB helpers ──────────────────────────────────────────────────────────────


def _insert_job_run(
    run_id: uuid.UUID,
    job_type: str,
    trigger: str,
    meta: Optional[dict],
    target_job_id: Optional[uuid.UUID] = None,
) -> None:
    # QA F4 / R1-07: an install-wide run (backup, H-1B refresh) is the owner's, whoever
    # triggered it (a member with the owner unlock); other runs take the context's account.
    account = _owner_id() if job_type in INSTALL_WIDE_JOB_TYPES else None
    db = SessionLocal()
    try:
        run = JobRun(
            id=run_id,
            job_type=job_type,
            trigger=trigger,
            status="running",
            meta=meta,
            target_job_id=target_job_id,
        )
        if account is not None:
            run.account_id = account
        db.add(run)
        db.commit()
    finally:
        db.close()


def _restart_job_run(run_id: uuid.UUID, started_at: datetime) -> None:
    """Move a queued run's start to the moment it got its slot."""
    db = SessionLocal()
    try:
        run = (db.query(JobRun).filter(JobRun.id == run_id)
               .execution_options(jn_unscoped=True).first())
        if run:
            run.started_at = started_at
            db.commit()
    except Exception as e:   # bookkeeping only; the run itself goes on
        logger.warning(f"Could not restart the clock of run {run_id}: {e}")
    finally:
        db.close()


# Called (each as its own task) when a scrape-gated run ends: the LinkedIn employer-link
# lookup (scheduler.lookup_after_scrape) is registered at start when the scheduler runs.
_after_scrape_hooks: list = []


def on_scrape_finished(hook) -> None:
    if hook not in _after_scrape_hooks:
        _after_scrape_hooks.append(hook)


def _scrape_finished() -> None:
    for hook in list(_after_scrape_hooks):
        try:
            asyncio.get_running_loop().create_task(hook())
        except Exception as e:  # never fails the scrape that just ended
            logger.warning(f"after-scrape hook {getattr(hook, '__name__', hook)}: {e}")


@asynccontextmanager
async def _gated(limiter: Optional["TaskLimiter"], running_job: "RunningJob"):
    """Hold `limiter` around the run; while it waits the run shows as waiting, and its
    clock (in memory and on the JobRun row) starts when it gets the slot."""
    if limiter is None:
        yield
        return
    running_job.waiting = True
    ran = False
    try:
        async with limiter:
            running_job.waiting = False
            running_job.started_at = datetime.now(timezone.utc)
            _restart_job_run(running_job.run_id, running_job.started_at)
            ran = True
            yield
    finally:
        running_job.waiting = False
        if ran and limiter.name == "scraping":
            _scrape_finished()


def _finish_job_run(run_id: uuid.UUID, status: str, result_summary: Optional[str], error: Optional[str],
                    created: Optional[dict] = None) -> None:
    db = SessionLocal()
    try:
        # By its own (random, unique) id: an install-wide run belongs to the owner even
        # when a member's context finishes it (R1-07).
        run = (db.query(JobRun).filter(JobRun.id == run_id)
               .execution_options(jn_unscoped=True).first())
        if run:
            now = datetime.now(timezone.utc)
            run.status = status
            run.finished_at = now
            # SQLite (tests) hands back naive datetimes; treat them as UTC
            started = run.started_at if run.started_at.tzinfo else run.started_at.replace(tzinfo=timezone.utc)
            run.duration_seconds = round((now - started).total_seconds(), 1)
            run.result_summary = result_summary
            run.error = sanitize_run_error(error)
            if created:
                run.meta = {**(run.meta or {}), "created": created}
            db.commit()
    finally:
        db.close()


def cleanup_stale_runs() -> int:
    """Mark any 'running' JobRun records as 'failed' (process restarted). Called at startup."""
    db = SessionLocal()
    try:
        stale = db.query(JobRun).filter(JobRun.status == "running").all()
        count = len(stale)
        now = datetime.now(timezone.utc)
        for run in stale:
            run.status = "failed"
            run.finished_at = now
            run.duration_seconds = round((now - run.started_at).total_seconds(), 1) if run.started_at else 0
            run.error = "Process restarted"
        db.commit()
        if count:
            logger.info(f"Cleaned up {count} stale job run(s) from previous process")
        return count
    finally:
        db.close()


# ── Context manager for scheduler use ──────────────────────────────────────


@asynccontextmanager
async def tracked_run(
    job_type: str,
    trigger: str = "scheduler",
    scope_key: Optional[str] = None,
    meta: Optional[dict] = None,
    target_job_id: Optional[uuid.UUID] = None,
    company_id: Optional[str] = None,
    all_accounts: bool = False,
):
    """Async context manager: tracks a job run in-memory + DB. Raises JobAlreadyRunningError on duplicate.
    `all_accounts=True` marks a run that writes into every account (R2-08)."""
    # Per-account scheduler jobs enter here under acting_as(account) (MT-7), so the run,
    # its dedup key and its rows belong to that account; with no context (install-level
    # jobs, direct calls) it acts for the owner.
    with owner_context():
        async with _tracked_run(job_type, trigger, scope_key, meta, target_job_id, company_id,
                                all_accounts) as rj:
            yield rj


@asynccontextmanager
async def _tracked_run(job_type, trigger, scope_key, meta, target_job_id, company_id,
                       all_accounts=False):
    account = _run_account(job_type)
    key = _make_key(job_type, scope_key, account)
    all_accounts = all_accounts or job_type in ALL_ACCOUNT_JOB_TYPES
    _refuse_during_removal(job_type, current_account.get(), all_accounts)
    _refuse_during_scheduled_scrape(job_type, trigger)

    existing = _running.get(key)
    if existing:
        elapsed = (datetime.now(timezone.utc) - existing.started_at).total_seconds()
        raise JobAlreadyRunningError(job_type, elapsed)

    run_id = uuid.uuid4()
    _insert_job_run(run_id, job_type, trigger, meta, target_job_id=target_job_id)

    running_job = RunningJob(
        run_id=run_id,
        job_type=job_type,
        trigger=trigger,
        started_at=datetime.now(timezone.utc),
        scope_key=scope_key,
        target_job_id=target_job_id,
        company_id=company_id,
        meta=meta,
        account_id=account,
        all_accounts=all_accounts,
    )
    _running[key] = running_job
    # The scheduled scrape takes the scrape gate too, so it waits for a manual scrape
    # instead of running beside it; other scheduler jobs are not gated here.
    limiter = limiter_for_job_type(job_type) if job_type in SCRAPE_JOB_TYPES else None

    try:
        _run_failure.set(None)
        _run_created.set(None)
        _current_run.set(running_job)
        async with _gated(limiter, running_job):
            yield running_job
        reason = _take_run_failure()
        _finish_job_run(run_id, "failed" if reason else "completed",
                        running_job.summary, reason, _take_run_created())
    except Exception as e:
        _finish_job_run(run_id, "failed", None, str(e))
        raise
    finally:
        _running.pop(key, None)


# ── Background launcher for manual triggers ────────────────────────────────


def launch_background(
    job_type: str,
    coro_func,
    trigger: str = "manual",
    scope_key: Optional[str] = None,
    meta: Optional[dict] = None,
    func_args: tuple = (),
    func_kwargs: Optional[dict] = None,
    target_job_id: Optional[uuid.UUID] = None,
    company_id: Optional[str] = None,
) -> str:
    """Launch a coroutine as a background asyncio.Task with tracking; returns run_id immediately, raising JobAlreadyRunningError if the current account already runs it."""
    account = _run_account(job_type)
    key = _make_key(job_type, scope_key, account)
    all_accounts = job_type in ALL_ACCOUNT_JOB_TYPES
    _refuse_during_removal(job_type, current_account.get(), all_accounts)
    _refuse_during_scheduled_scrape(job_type, trigger)

    existing = _running.get(key)
    if existing:
        elapsed = (datetime.now(timezone.utc) - existing.started_at).total_seconds()
        raise JobAlreadyRunningError(job_type, elapsed)

    run_id = uuid.uuid4()
    # MT-2: the task copies the caller's context (the request's account); a caller with
    # none (startup, tests) runs as the owner.
    with owner_context():
        _insert_job_run(run_id, job_type, trigger, meta, target_job_id=target_job_id)

    running_job = RunningJob(
        run_id=run_id,
        job_type=job_type,
        trigger=trigger,
        started_at=datetime.now(timezone.utc),
        scope_key=scope_key,
        target_job_id=target_job_id,
        company_id=company_id,
        meta=meta,
        account_id=account,
        all_accounts=all_accounts,
    )

    async def _wrapper():
        # QA F4 / R1-08: the owner unlock is a 15-minute browser grant checked when the
        # job was launched; it must not ride along for the task's whole (hours-long)
        # lifetime.
        with owner_unlocked(False), owner_context():
            await _run()

    async def _run():
        try:
            _run_failure.set(None)
            _run_created.set(None)
            _current_run.set(running_job)
            # The gate is taken here, before the worker runs, so a queued task
            # holds nothing but itself — no DB connection, no LLM slot.
            async with _gated(limiter_for_job_type(job_type), running_job):
                result = await coro_func(*(func_args or ()), **(func_kwargs or {}))
            # A coroutine that returns a string is describing what it did.
            summary = result.strip() if isinstance(result, str) and result.strip() else None
            # …but it may also have reported a failure it handled itself.
            reason = _take_run_failure()
            running_job.error = sanitize_run_error(reason)
            running_job.created = _take_run_created()
            _finish_job_run(run_id, "failed" if reason else "completed", summary, reason,
                            running_job.created)
        except Exception as e:
            logger.error(f"Background job {job_type} failed: {e}")
            running_job.error = sanitize_run_error(str(e)) or "The run failed"
            _finish_job_run(run_id, "failed", None, str(e))
        finally:
            _running.pop(key, None)

    running_job.task = asyncio.create_task(_wrapper())
    _running[key] = running_job

    return str(run_id)
