"""Tests for H-1B flag application in jobspy source."""
import pytest
import inspect


def test_jobspy_does_not_use_asyncio_run():
    """The source must NOT contain asyncio.run() calls — they fail nested in worker threads."""
    import backend.scraper.sources.jobspy as jobspy_src
    source = inspect.getsource(jobspy_src)
    assert "asyncio.run(check_job_h1b" not in source
    assert "asyncio.run(scan_jd_for_h1b_flags" not in source


def test_jobspy_has_sync_h1b_helper():
    """Expose a sync-callable helper that's safe inside asyncio.to_thread workers."""
    from backend.scraper.sources import jobspy as jobspy_src
    # Either _apply_h1b_inline or a module-level sync helper must exist
    assert hasattr(jobspy_src, "_apply_h1b_inline") or hasattr(jobspy_src, "scan_jd_for_h1b_flags_sync")


def test_apply_h1b_inline_sets_flag_on_match(monkeypatch):
    """When the async scan flags the JD, the sync helper must preserve that flag on the job."""
    from backend.scraper.sources import jobspy as jobspy_src

    # Stub the async scan to set the flag
    async def fake_async_scan(job, db=None):
        job.h1b_jd_flag = True
        job.h1b_jd_snippet = "no visa sponsorship"

    monkeypatch.setattr(
        "backend.analyzer.h1b_checker.check_job_h1b",
        fake_async_scan,
    )

    from backend.models.db import Job
    job = Job(
        external_id="x", content_hash="c", company="Acme", title="Senior PM",
        url="https://x.com/1", description="We do NOT sponsor visas.",
    )

    # Call the helper — whatever its name is (grep for it first)
    if hasattr(jobspy_src, "_apply_h1b_inline"):
        jobspy_src._apply_h1b_inline(job)
    else:
        # fallback name
        jobspy_src.scan_jd_for_h1b_flags_sync(job)

    assert getattr(job, "h1b_jd_flag", None) is True


def test_apply_h1b_inline_tolerates_exception(monkeypatch):
    """When the async scan raises, the helper logs and doesn't propagate."""
    from backend.scraper.sources import jobspy as jobspy_src

    async def broken_async_scan(job, db=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "backend.analyzer.h1b_checker.check_job_h1b",
        broken_async_scan,
    )

    from backend.models.db import Job
    job = Job(external_id="x", content_hash="c", company="Acme", title="PM",
              url="https://x.com/1", description="...")

    # Should not raise
    if hasattr(jobspy_src, "_apply_h1b_inline"):
        jobspy_src._apply_h1b_inline(job)
    else:
        jobspy_src.scan_jd_for_h1b_flags_sync(job)
