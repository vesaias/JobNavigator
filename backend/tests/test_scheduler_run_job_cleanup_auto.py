"""Regression test: scheduler.run_job_cleanup_auto must not NameError on JobAlreadyRunningError."""
import pytest
from contextlib import asynccontextmanager


@pytest.mark.asyncio
async def test_run_job_cleanup_auto_handles_already_running(monkeypatch):
    """When tracked_run raises JobAlreadyRunningError, the function should return silently."""
    from backend import scheduler
    from backend.job_monitor import JobAlreadyRunningError

    @asynccontextmanager
    async def raising_tracked_run(*args, **kwargs):
        raise JobAlreadyRunningError("job_cleanup", 0.0)
        yield  # unreachable, but required for contextmanager signature

    # Patch the imported name inside job_monitor (scheduler imports it lazily)
    monkeypatch.setattr("backend.job_monitor.tracked_run", raising_tracked_run, raising=False)

    # Must not raise — JobAlreadyRunningError should be caught internally,
    # and no NameError from a stray `finally: db.close()` with unbound `db`.
    await scheduler.run_job_cleanup_auto()
