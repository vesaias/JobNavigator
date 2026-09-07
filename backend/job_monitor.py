"""Job execution monitor — tracks running state and run history (Hangfire-style)."""
import asyncio
import contextvars
import logging
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from backend.models.db import SessionLocal, JobRun, Setting

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
}

# Which gate a launch_background job_type belongs to. Anything absent runs
# unlimited — scrapes and backups are already deduped by scope key.
_JOB_TYPE_LIMITER: dict[str, str] = {
    "analyze_job": "scoring",
    "score_resume": "scoring",
    "tailor_resume": "tailoring",
    "generate_cover_letter": "tailoring",
    "cache_job_page": "page_cache",
}

_limiters: dict[str, TaskLimiter] = {}


def _resolve_limit(name: str) -> int:
    setting_key, fallback = _LIMIT_SOURCES.get(name, (None, 4))
    if not setting_key:
        return fallback
    try:
        db = SessionLocal()
        try:
            row = db.query(Setting).filter(Setting.key == setting_key).first()
            return max(1, int(row.value)) if row and row.value else fallback
        finally:
            db.close()
    except Exception:
        return fallback


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


# Keyed by dedup key (e.g. "scrape_all" or "company_scrape:<uuid>")
_running: dict[str, RunningJob] = {}


def _make_key(job_type: str, scope_key: Optional[str] = None) -> str:
    if scope_key:
        return f"{job_type}:{scope_key}"
    return job_type


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


def mark_run_failed(reason: str) -> None:
    """Flag the currently tracked run as failed while still returning a summary."""
    if reason:
        _run_failure.set(str(reason)[:1000])


def _take_run_failure() -> Optional[str]:
    reason = _run_failure.get()
    _run_failure.set(None)
    return reason


class JobAlreadyRunningError(Exception):
    def __init__(self, job_type: str, elapsed_seconds: float):
        self.job_type = job_type
        self.elapsed_seconds = elapsed_seconds
        super().__init__(
            f"{job_type} is already running ({elapsed_seconds:.0f}s elapsed)"
        )


def is_running(job_type: str, scope_key: Optional[str] = None) -> Optional[RunningJob]:
    return _running.get(_make_key(job_type, scope_key))


def get_all_running() -> list[dict]:
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
        }
        for r in _running.values()
    ]


def _get_running_by_job_type(job_type: str) -> Optional[dict]:
    """Check if any job with the given job_type is running (ignoring scope_key)."""
    for key, r in _running.items():
        if r.job_type == job_type:
            now = datetime.now(timezone.utc)
            return {
                "run_id": str(r.run_id),
                "elapsed_seconds": round((now - r.started_at).total_seconds(), 1),
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
        db.add(run)
        db.commit()
    finally:
        db.close()


def _finish_job_run(run_id: uuid.UUID, status: str, result_summary: Optional[str], error: Optional[str]) -> None:
    db = SessionLocal()
    try:
        run = db.query(JobRun).filter(JobRun.id == run_id).first()
        if run:
            now = datetime.now(timezone.utc)
            run.status = status
            run.finished_at = now
            # SQLite (tests) hands back naive datetimes; treat them as UTC
            started = run.started_at if run.started_at.tzinfo else run.started_at.replace(tzinfo=timezone.utc)
            run.duration_seconds = round((now - started).total_seconds(), 1)
            run.result_summary = result_summary
            run.error = error
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
):
    """Async context manager: tracks a job run in-memory + DB. Raises JobAlreadyRunningError on duplicate."""
    key = _make_key(job_type, scope_key)

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
    )
    _running[key] = running_job

    try:
        _run_failure.set(None)
        yield running_job
        reason = _take_run_failure()
        _finish_job_run(run_id, "failed" if reason else "completed",
                        running_job.summary, reason)
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
    """Launch a coroutine as a background asyncio.Task with tracking; returns run_id immediately, raising JobAlreadyRunningError if already running."""
    key = _make_key(job_type, scope_key)

    existing = _running.get(key)
    if existing:
        elapsed = (datetime.now(timezone.utc) - existing.started_at).total_seconds()
        raise JobAlreadyRunningError(job_type, elapsed)

    run_id = uuid.uuid4()
    _insert_job_run(run_id, job_type, trigger, meta, target_job_id=target_job_id)

    started_at = datetime.now(timezone.utc)

    async def _wrapper():
        try:
            _run_failure.set(None)
            # The gate is taken here, before the worker runs, so a queued task
            # holds nothing but itself — no DB connection, no LLM slot.
            limiter = limiter_for_job_type(job_type)
            if limiter is None:
                result = await coro_func(*(func_args or ()), **(func_kwargs or {}))
            else:
                async with limiter:
                    result = await coro_func(*(func_args or ()), **(func_kwargs or {}))
            # A coroutine that returns a string is describing what it did.
            summary = result.strip() if isinstance(result, str) and result.strip() else None
            # …but it may also have reported a failure it handled itself.
            reason = _take_run_failure()
            _finish_job_run(run_id, "failed" if reason else "completed", summary, reason)
        except Exception as e:
            logger.error(f"Background job {job_type} failed: {e}")
            _finish_job_run(run_id, "failed", None, str(e))
        finally:
            _running.pop(key, None)

    task = asyncio.create_task(_wrapper())

    _running[key] = RunningJob(
        run_id=run_id,
        job_type=job_type,
        trigger=trigger,
        started_at=started_at,
        task=task,
        scope_key=scope_key,
        target_job_id=target_job_id,
        company_id=company_id,
    )

    return str(run_id)
