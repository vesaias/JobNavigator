"""Job execution monitor — tracks running state and run history (Hangfire-style)."""
import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from backend.models.db import SessionLocal, JobRun

logger = logging.getLogger("jobnavigator.monitor")

# ── In-memory running state ────────────────────────────────────────────────


@dataclass
class RunningJob:
    run_id: uuid.UUID
    job_type: str
    trigger: str
    started_at: datetime
    task: Optional[asyncio.Task] = None
    scope_key: Optional[str] = None


# Keyed by dedup key (e.g. "scrape_all" or "company_scrape:<uuid>")
_running: dict[str, RunningJob] = {}


def _make_key(job_type: str, scope_key: Optional[str] = None) -> str:
    if scope_key:
        return f"{job_type}:{scope_key}"
    return job_type


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


def _insert_job_run(run_id: uuid.UUID, job_type: str, trigger: str, meta: Optional[dict]) -> None:
    db = SessionLocal()
    try:
        run = JobRun(
            id=run_id,
            job_type=job_type,
            trigger=trigger,
            status="running",
            meta=meta,
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
            run.duration_seconds = round((now - run.started_at).total_seconds(), 1)
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
async def tracked_run(job_type: str, trigger: str = "scheduler", scope_key: Optional[str] = None, meta: Optional[dict] = None):
    """Async context manager: tracks a job run in-memory + DB. Raises JobAlreadyRunningError on duplicate."""
    key = _make_key(job_type, scope_key)

    existing = _running.get(key)
    if existing:
        elapsed = (datetime.now(timezone.utc) - existing.started_at).total_seconds()
        raise JobAlreadyRunningError(job_type, elapsed)

    run_id = uuid.uuid4()
    _insert_job_run(run_id, job_type, trigger, meta)

    running_job = RunningJob(
        run_id=run_id,
        job_type=job_type,
        trigger=trigger,
        started_at=datetime.now(timezone.utc),
        scope_key=scope_key,
    )
    _running[key] = running_job

    try:
        yield running_job
        _finish_job_run(run_id, "completed", None, None)
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
) -> str:
    """Launch a coroutine as a background asyncio.Task with tracking. Returns run_id immediately.
    Raises JobAlreadyRunningError if already running."""
    key = _make_key(job_type, scope_key)

    existing = _running.get(key)
    if existing:
        elapsed = (datetime.now(timezone.utc) - existing.started_at).total_seconds()
        raise JobAlreadyRunningError(job_type, elapsed)

    run_id = uuid.uuid4()
    _insert_job_run(run_id, job_type, trigger, meta)

    started_at = datetime.now(timezone.utc)

    async def _wrapper():
        try:
            await coro_func(*(func_args or ()), **(func_kwargs or {}))
            _finish_job_run(run_id, "completed", None, None)
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
    )

    return str(run_id)
