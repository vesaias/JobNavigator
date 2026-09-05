"""R4-T6 coverage · job_monitor: `_get_running_by_job_type` and the mark_run_failed contract.

`mark_run_failed()` exists so a coroutine that swallows its own exception and
returns a human summary ("Scoring failed") still finishes as a *failed* JobRun —
the summary is kept as `result_summary`, the reason lands in `error`. These tests
pin both halves plus the ContextVar hygiene that keeps one run's reason out of
the next run's row.
"""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import sessionmaker


@pytest.fixture(autouse=True)
def _clean_monitor_globals():
    """No in-memory run and no pending failure reason may leak between tests."""
    import backend.job_monitor as jm
    jm._running.clear()
    jm._run_failure.set(None)
    yield
    jm._running.clear()
    jm._run_failure.set(None)


@pytest.fixture
def bound_session(test_db, monkeypatch):
    """Point job_monitor's SessionLocal at the in-memory test DB."""
    import backend.job_monitor as jm
    TestSession = sessionmaker(bind=test_db.get_bind())
    monkeypatch.setattr(jm, "SessionLocal", TestSession)
    return TestSession


def _run_row(TestSession, job_type):
    from backend.models.db import JobRun
    s = TestSession()
    try:
        return s.query(JobRun).filter_by(job_type=job_type).one()
    finally:
        s.close()


async def _drain(job_type):
    """Yield to the loop until launch_background's wrapper has finished."""
    import backend.job_monitor as jm
    for _ in range(200):
        await asyncio.sleep(0)
        if job_type not in jm._running:
            return
    raise AssertionError(f"background run {job_type} never finished")


# ── _get_running_by_job_type ────────────────────────────────────────────────


def test_get_running_by_job_type_finds_a_scoped_run():
    """A run registered under "type:scope" is still findable by its bare job_type."""
    import backend.job_monitor as jm

    started = datetime.now(timezone.utc) - timedelta(seconds=5)
    run_id = uuid.uuid4()
    jm._running["company_scrape:abc"] = jm.RunningJob(
        run_id=run_id, job_type="company_scrape", trigger="manual",
        started_at=started, scope_key="abc",
    )

    info = jm._get_running_by_job_type("company_scrape")
    assert info is not None
    assert info["run_id"] == str(run_id)
    # Only run_id + elapsed_seconds are exposed here (the scheduler card's needs).
    assert set(info) == {"run_id", "elapsed_seconds"}
    assert info["elapsed_seconds"] >= 5.0


def test_get_running_by_job_type_returns_none_for_other_types():
    """A different job_type running does not make this one look busy."""
    import backend.job_monitor as jm

    jm._running["email_check"] = jm.RunningJob(
        run_id=uuid.uuid4(), job_type="email_check", trigger="scheduler",
        started_at=datetime.now(timezone.utc),
    )
    assert jm._get_running_by_job_type("scrape_all") is None


def test_get_running_by_job_type_returns_none_when_idle():
    """Nothing running at all → None."""
    import backend.job_monitor as jm
    assert jm._get_running_by_job_type("scrape_all") is None


# ── mark_run_failed inside tracked_run ──────────────────────────────────────


@pytest.mark.asyncio
async def test_tracked_run_marked_failed_keeps_its_summary(bound_session):
    """mark_run_failed() flips the run to failed but the summary survives as result_summary."""
    import backend.job_monitor as jm

    async with jm.tracked_run("cov_tracked_failed", "scheduler") as run:
        run.summary = "0 of 3 jobs scored"
        jm.mark_run_failed("provider 529 overloaded")

    row = _run_row(bound_session, "cov_tracked_failed")
    assert row.status == "failed"
    assert row.result_summary == "0 of 3 jobs scored"
    assert row.error == "provider 529 overloaded"


@pytest.mark.asyncio
async def test_tracked_run_without_a_failure_completes(bound_session):
    """No mark_run_failed() → completed, no error, summary still recorded."""
    import backend.job_monitor as jm

    async with jm.tracked_run("cov_tracked_ok", "scheduler") as run:
        run.summary = "3 jobs scored"

    row = _run_row(bound_session, "cov_tracked_ok")
    assert row.status == "completed"
    assert row.result_summary == "3 jobs scored"
    assert row.error is None


@pytest.mark.asyncio
async def test_empty_reason_does_not_flag_the_run(bound_session):
    """mark_run_failed("") is falsy and must leave the run completed."""
    import backend.job_monitor as jm

    async with jm.tracked_run("cov_empty_reason", "scheduler") as run:
        run.summary = "nothing to do"
        jm.mark_run_failed("")

    row = _run_row(bound_session, "cov_empty_reason")
    assert row.status == "completed"
    assert row.error is None


@pytest.mark.asyncio
async def test_failure_reason_is_truncated_to_1000_chars(bound_session):
    """A pathological provider blob is cut to 1000 characters before it is stored."""
    import backend.job_monitor as jm

    async with jm.tracked_run("cov_long_reason", "scheduler"):
        jm.mark_run_failed("z" * 4000)

    row = _run_row(bound_session, "cov_long_reason")
    assert row.status == "failed"
    assert row.error == "z" * 1000


@pytest.mark.asyncio
async def test_failure_reason_does_not_leak_into_the_next_run(bound_session):
    """The ContextVar is cleared on entry and taken on exit — run 2 is clean."""
    import backend.job_monitor as jm

    async with jm.tracked_run("cov_leak_first", "scheduler"):
        jm.mark_run_failed("first run broke")
    async with jm.tracked_run("cov_leak_second", "scheduler"):
        pass

    first = _run_row(bound_session, "cov_leak_first")
    second = _run_row(bound_session, "cov_leak_second")
    assert first.status == "failed" and first.error == "first run broke"
    assert second.status == "completed" and second.error is None


@pytest.mark.asyncio
async def test_an_exception_beats_a_marked_failure(bound_session):
    """A raised exception takes the except branch: error is the exception, summary is dropped."""
    import backend.job_monitor as jm

    with pytest.raises(RuntimeError, match="hard stop"):
        async with jm.tracked_run("cov_raise_over_mark", "scheduler") as run:
            run.summary = "partial work"
            jm.mark_run_failed("soft reason")
            raise RuntimeError("hard stop")

    row = _run_row(bound_session, "cov_raise_over_mark")
    assert row.status == "failed"
    assert row.result_summary is None
    assert "hard stop" in (row.error or "")


# ── mark_run_failed inside launch_background ────────────────────────────────


@pytest.mark.asyncio
async def test_launch_background_summary_plus_marked_failure(bound_session):
    """A coroutine returning a summary AND calling mark_run_failed: failed + summary kept."""
    import backend.job_monitor as jm

    async def worker():
        jm.mark_run_failed("all 3 LLM calls failed")
        return "  0 of 3 jobs scored  "

    jm.launch_background("cov_bg_failed", worker, trigger="manual")
    await _drain("cov_bg_failed")

    row = _run_row(bound_session, "cov_bg_failed")
    assert row.status == "failed"
    assert row.result_summary == "0 of 3 jobs scored"   # stripped by the wrapper
    assert row.error == "all 3 LLM calls failed"


@pytest.mark.asyncio
async def test_launch_background_blank_summary_is_not_stored(bound_session):
    """A whitespace-only return value is not a summary; without a failure the run completes."""
    import backend.job_monitor as jm

    async def worker():
        return "   "

    jm.launch_background("cov_bg_blank", worker, trigger="manual")
    await _drain("cov_bg_blank")

    row = _run_row(bound_session, "cov_bg_blank")
    assert row.status == "completed"
    assert row.result_summary is None
    assert row.error is None


@pytest.mark.asyncio
async def test_launch_background_failure_does_not_leak_to_the_next_launch(bound_session):
    """Two sequential background runs: only the one that marked itself is failed."""
    import backend.job_monitor as jm

    async def flagging():
        jm.mark_run_failed("boom")
        return "did half"

    async def clean():
        return "did all"

    jm.launch_background("cov_bg_leak_a", flagging, trigger="manual")
    await _drain("cov_bg_leak_a")
    jm.launch_background("cov_bg_leak_b", clean, trigger="manual")
    await _drain("cov_bg_leak_b")

    a = _run_row(bound_session, "cov_bg_leak_a")
    b = _run_row(bound_session, "cov_bg_leak_b")
    assert a.status == "failed" and a.error == "boom"
    assert b.status == "completed" and b.error is None and b.result_summary == "did all"
