"""R4-T1 · failure injection: LLM 429/529/timeout, Gmail token expiry, Telegram down.

Every dependency here is remote and will fail in production sooner or later. The
contract under test is that a failure degrades one feature and never takes the
scheduler, the run history or the job row with it.
"""
import asyncio
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import event

from backend.tests.r4_support import (  # noqa: F401
    client, _clear_running_state, _no_outbound, assert_clean,
    make_job, make_resume, set_setting,
)


@pytest.fixture(autouse=True)
def _utc_tz_on_jobrun_load():
    from backend.models.db import JobRun

    def _on_load(instance, context):
        for field in ("started_at", "finished_at"):
            v = getattr(instance, field, None)
            if v is not None and v.tzinfo is None:
                setattr(instance, field, v.replace(tzinfo=timezone.utc))

    event.listen(JobRun, "load", _on_load)
    yield
    event.remove(JobRun, "load", _on_load)


@pytest.fixture(autouse=True)
def _no_backoff_sleep(monkeypatch):
    """call_llm backs off 2/4/8 s per attempt — 14 s per provider without this."""
    import backend.analyzer.llm_client as lc
    real_sleep = asyncio.sleep

    async def _instant(seconds, *a, **kw):
        # Only the retry backoff (2/4/8 s) is skipped; short waits tests use to let
        # a background task finish stay real.
        await real_sleep(0 if seconds >= 2 else seconds)
    monkeypatch.setattr(lc.asyncio, "sleep", _instant)


# ── Fault factories ──────────────────────────────────────────────────────────

class RateLimited(Exception):
    """Stand-in for a provider 429."""


class Overloaded(Exception):
    """Stand-in for a provider 529."""


FAULTS = {
    "429": RateLimited("rate_limit_error"),
    "529": Overloaded("overloaded_error"),
    "timeout": asyncio.TimeoutError("read timeout"),
    "connection": ConnectionError("connection reset by peer"),
}


def _scored_job(db, **kw):
    return make_job(db, description="We need a product manager. " * 20, **kw)


def _seed_scoring(db):
    set_setting(db, "scoring_rubric", "Score 0-100.")
    set_setting(db, "scoring_output_light", '{"scores": {CV_NAMES_HERE}}')
    set_setting(db, "scoring_output_full", '{"scores": {CV_NAMES_HERE}}')
    set_setting(db, "prompt_caching_enabled", "false")
    return make_resume(db, name="Base", json_data={
        "header": {"name": "A"},
        "experience": [{"title": "PM", "company": "X",
                        "bullets": ["Shipped a product", "Led a team"]}],
        "skills": ["product", "roadmap"],
    })


# ══ LLM failures during scoring ══════════════════════════════════════════════

@pytest.mark.asyncio
@pytest.mark.parametrize("fault", list(FAULTS))
async def test_llm_failure_leaves_the_job_unscored(test_db, monkeypatch, fault):
    import backend.analyzer.llm_client as lc
    from backend.analyzer.cv_scorer import score_single_job
    from backend.models.db import Job

    resume = _seed_scoring(test_db)
    job = _scored_job(test_db)

    async def _boom(*a, **k):
        raise FAULTS[fault]
    monkeypatch.setattr(lc, "_dispatch", _boom)

    summary = await score_single_job(str(job.id), cv_ids=[str(resume.id)], depth="light")
    assert summary == "Scoring failed"
    test_db.expire_all()
    fresh = test_db.query(Job).filter(Job.id == job.id).first()
    assert not fresh.cv_scores
    assert fresh.best_cv_score is None


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", list(FAULTS))
async def test_llm_failure_is_recorded_in_the_llm_call_log(test_db, monkeypatch, fault):
    import backend.analyzer.llm_client as lc
    from backend.analyzer.cv_scorer import score_single_job
    from backend.models.db import LlmCallLog

    resume = _seed_scoring(test_db)
    job = _scored_job(test_db)

    async def _boom(*a, **k):
        raise FAULTS[fault]
    monkeypatch.setattr(lc, "_dispatch", _boom)

    await score_single_job(str(job.id), cv_ids=[str(resume.id)], depth="light")
    test_db.expire_all()
    rows = test_db.query(LlmCallLog).all()
    assert len(rows) == 1
    assert rows[0].success is False
    assert rows[0].error


@pytest.mark.asyncio
async def test_llm_failure_run_is_visible_in_the_run_history(test_db, monkeypatch):
    """launch_background wraps the scorer, so the outage must be inspectable later."""
    import backend.analyzer.llm_client as lc
    import backend.job_monitor as jm
    from backend.analyzer.cv_scorer import score_single_job
    from backend.models.db import JobRun

    resume = _seed_scoring(test_db)
    job = _scored_job(test_db)

    async def _boom(*a, **k):
        raise FAULTS["529"]
    monkeypatch.setattr(lc, "_dispatch", _boom)

    jm.launch_background("analyze_job", score_single_job, trigger="manual",
                         scope_key=str(job.id), target_job_id=job.id,
                         func_kwargs={"job_id": str(job.id), "cv_ids": [str(resume.id)],
                                      "depth": "light"})
    await asyncio.sleep(0.2)
    test_db.expire_all()
    row = test_db.query(JobRun).filter(JobRun.job_type == "analyze_job").first()
    assert row.result_summary == "Scoring failed"


@pytest.mark.asyncio
@pytest.mark.xfail(strict=True, reason="R4-T1-28")
async def test_llm_failure_marks_the_run_failed_not_completed(test_db, monkeypatch):
    """A provider outage reads as a green run in Stats and as an OK toast in the UI,
    because the scorer swallows the error and returns a summary string."""
    import backend.analyzer.llm_client as lc
    import backend.job_monitor as jm
    from backend.analyzer.cv_scorer import score_single_job
    from backend.models.db import JobRun

    resume = _seed_scoring(test_db)
    job = _scored_job(test_db)

    async def _boom(*a, **k):
        raise FAULTS["529"]
    monkeypatch.setattr(lc, "_dispatch", _boom)

    jm.launch_background("analyze_job", score_single_job, trigger="manual",
                         scope_key=str(job.id), target_job_id=job.id,
                         func_kwargs={"job_id": str(job.id), "cv_ids": [str(resume.id)],
                                      "depth": "light"})
    await asyncio.sleep(0.2)
    test_db.expire_all()
    row = test_db.query(JobRun).filter(JobRun.job_type == "analyze_job").first()
    assert row.status == "failed" and row.error


@pytest.mark.asyncio
async def test_a_malformed_llm_response_is_not_persisted(test_db, monkeypatch):
    import backend.analyzer.llm_client as lc
    from backend.analyzer.cv_scorer import score_single_job
    from backend.models.db import Job

    resume = _seed_scoring(test_db)
    job = _scored_job(test_db)

    async def _junk(*a, **k):
        return {"text": '{"scores": null}', "usage": {}}
    monkeypatch.setattr(lc, "_dispatch", _junk)

    assert await score_single_job(str(job.id), cv_ids=[str(resume.id)],
                                  depth="light") == "Scoring failed"
    test_db.expire_all()
    assert not test_db.query(Job).filter(Job.id == job.id).first().cv_scores


@pytest.mark.asyncio
async def test_partial_llm_scores_still_persist_what_arrived(test_db, monkeypatch):
    import backend.analyzer.llm_client as lc
    from backend.analyzer.cv_scorer import score_single_job
    from backend.models.db import Job

    resume = _seed_scoring(test_db)
    job = _scored_job(test_db)

    async def _ok(*a, **k):
        return {"text": '{"scores": {"Base": 72}, "best_cv": "Base"}', "usage": {}}
    monkeypatch.setattr(lc, "_dispatch", _ok)

    await score_single_job(str(job.id), cv_ids=[str(resume.id)], depth="light")
    test_db.expire_all()
    fresh = test_db.query(Job).filter(Job.id == job.id).first()
    assert fresh.cv_scores == {"Base": 72} and fresh.best_cv_score == 72


# ══ Retry + fallback inside call_llm ═════════════════════════════════════════

@pytest.mark.asyncio
async def test_primary_is_retried_four_times_before_the_fallback(test_db, monkeypatch):
    import backend.analyzer.llm_client as lc
    set_setting(test_db, "llm_provider", "claude_api")
    set_setting(test_db, "llm_model", "primary-model")
    set_setting(test_db, "llm_fallback_provider", "openai")
    set_setting(test_db, "llm_fallback_model", "fallback-model")

    calls = []

    async def _dispatch(provider, model, api_key, prompt, system, max_tokens,
                        cached_prefix=None):
        calls.append(model)
        if model == "primary-model":
            raise FAULTS["529"]
        return {"text": "ok", "usage": {}}
    monkeypatch.setattr(lc, "_dispatch", _dispatch)

    res = await lc.call_llm("p", "s")
    assert calls.count("primary-model") == 4
    assert calls.count("fallback-model") == 1
    assert res["provider"] == "openai" and res["model"] == "fallback-model"


@pytest.mark.asyncio
async def test_a_transient_primary_failure_does_not_reach_the_fallback(test_db, monkeypatch):
    import backend.analyzer.llm_client as lc
    set_setting(test_db, "llm_provider", "claude_api")
    set_setting(test_db, "llm_model", "primary-model")
    set_setting(test_db, "llm_fallback_provider", "openai")
    set_setting(test_db, "llm_fallback_model", "fallback-model")

    calls = []

    async def _dispatch(provider, model, api_key, prompt, system, max_tokens,
                        cached_prefix=None):
        calls.append(model)
        if len(calls) == 1:
            raise FAULTS["429"]
        return {"text": "ok", "usage": {}}
    monkeypatch.setattr(lc, "_dispatch", _dispatch)

    res = await lc.call_llm("p", "s")
    assert calls == ["primary-model", "primary-model"]
    assert res["model"] == "primary-model"


@pytest.mark.asyncio
async def test_both_providers_down_raises_one_error_naming_both(test_db, monkeypatch):
    import backend.analyzer.llm_client as lc
    set_setting(test_db, "llm_provider", "claude_api")
    set_setting(test_db, "llm_model", "primary-model")
    set_setting(test_db, "llm_fallback_provider", "openai")
    set_setting(test_db, "llm_fallback_model", "fallback-model")

    async def _boom(*a, **k):
        raise FAULTS["timeout"]
    monkeypatch.setattr(lc, "_dispatch", _boom)

    with pytest.raises(RuntimeError) as e:
        await lc.call_llm("p", "s")
    assert "primary-model" in str(e.value) and "fallback-model" in str(e.value)


@pytest.mark.asyncio
async def test_without_a_fallback_the_primary_error_propagates(test_db, monkeypatch):
    import backend.analyzer.llm_client as lc
    set_setting(test_db, "llm_provider", "claude_api")
    set_setting(test_db, "llm_model", "primary-model")
    set_setting(test_db, "llm_fallback_provider", "")
    set_setting(test_db, "llm_fallback_model", "")

    async def _boom(*a, **k):
        raise FAULTS["429"]
    monkeypatch.setattr(lc, "_dispatch", _boom)

    with pytest.raises(RateLimited):
        await lc.call_llm("p", "s")


@pytest.mark.asyncio
async def test_the_fallback_pair_is_what_gets_logged(test_db, monkeypatch):
    """A cost row must name the provider that answered, not the one that timed out."""
    import backend.analyzer.llm_client as lc
    from backend.analyzer.cv_scorer import score_single_job
    from backend.models.db import LlmCallLog

    resume = _seed_scoring(test_db)
    job = _scored_job(test_db)
    set_setting(test_db, "llm_provider", "claude_api")
    set_setting(test_db, "llm_model", "primary-model")
    set_setting(test_db, "llm_fallback_provider", "openai")
    set_setting(test_db, "llm_fallback_model", "fallback-model")

    async def _dispatch(provider, model, api_key, prompt, system, max_tokens,
                        cached_prefix=None):
        if model == "primary-model":
            raise FAULTS["529"]
        return {"text": '{"scores": {"Base": 60}}', "usage": {}}
    monkeypatch.setattr(lc, "_dispatch", _dispatch)

    await score_single_job(str(job.id), cv_ids=[str(resume.id)], depth="light")
    test_db.expire_all()
    row = test_db.query(LlmCallLog).first()
    assert row.provider == "openai" and row.model == "fallback-model"
    assert row.success is True


# ══ Gmail ════════════════════════════════════════════════════════════════════

def _fake_httpx(monkeypatch, module, *, status=200, payload=None, raises=None):
    """Point a module's httpx.AsyncClient at a canned response (or an exception)."""
    from unittest.mock import AsyncMock, MagicMock
    import httpx

    resp = MagicMock()
    resp.status_code = status
    resp.text = "" if payload is None else str(payload)
    resp.json = MagicMock(return_value=payload or {})

    async def _call(*a, **k):
        if raises:
            raise raises
        return resp

    c = MagicMock()
    c.get = AsyncMock(side_effect=_call)
    c.post = AsyncMock(side_effect=_call)
    c.__aenter__ = AsyncMock(return_value=c)
    c.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kw: c, raising=False)
    return c


@pytest.mark.asyncio
async def test_gmail_token_expiry_returns_no_token_and_does_not_raise(test_db, monkeypatch):
    import backend.email_monitor.gmail_client as gc
    monkeypatch.setattr(gc, "GMAIL_REFRESH_TOKEN", "expired-token")
    _fake_httpx(monkeypatch, gc, status=400,
                payload={"error": "invalid_grant", "error_description": "Token expired"})
    assert await gc._get_access_token() == ""
    assert await gc.check_emails() is None


@pytest.mark.asyncio
async def test_gmail_token_expiry_leaves_the_scheduler_run_completed(test_db, monkeypatch):
    """An expired token is an operator problem, not a crashed job."""
    import backend.email_monitor.gmail_client as gc
    from backend.scheduler import run_email_check
    from backend.models.db import JobRun

    monkeypatch.setattr(gc, "GMAIL_REFRESH_TOKEN", "expired-token")
    _fake_httpx(monkeypatch, gc, status=400, payload={"error": "invalid_grant"})

    await run_email_check()
    test_db.expire_all()
    row = test_db.query(JobRun).filter(JobRun.job_type == "email_check").first()
    assert row.status == "completed" and row.result_summary == "No new replies"


@pytest.mark.asyncio
async def test_gmail_network_failure_marks_the_run_failed_without_killing_the_scheduler(
        test_db, monkeypatch):
    import backend.email_monitor.gmail_client as gc
    from backend.scheduler import run_email_check
    from backend.models.db import JobRun

    monkeypatch.setattr(gc, "GMAIL_REFRESH_TOKEN", "tok")
    _fake_httpx(monkeypatch, gc, raises=ConnectionError("gmail unreachable"))

    with pytest.raises(ConnectionError):
        await run_email_check()      # APScheduler catches and logs this
    test_db.expire_all()
    row = test_db.query(JobRun).filter(JobRun.job_type == "email_check").first()
    assert row.status == "failed" and "gmail unreachable" in (row.error or "")
    import backend.job_monitor as jm
    assert "email_check" not in jm._running


@pytest.mark.asyncio
async def test_gmail_list_error_response_is_swallowed(test_db, monkeypatch):
    """A 403 on the messages list must not raise — the next tick retries."""
    import backend.email_monitor.gmail_client as gc
    monkeypatch.setattr(gc, "GMAIL_REFRESH_TOKEN", "tok")

    from unittest.mock import AsyncMock, MagicMock
    token_resp = MagicMock(status_code=200)
    token_resp.json = MagicMock(return_value={"access_token": "at"})
    list_resp = MagicMock(status_code=403, text="quota exceeded")

    c = MagicMock()
    c.post = AsyncMock(return_value=token_resp)
    c.get = AsyncMock(return_value=list_resp)
    c.__aenter__ = AsyncMock(return_value=c)
    c.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(gc.httpx, "AsyncClient", lambda **kw: c)

    assert await gc.check_emails() is None


# ══ Telegram ═════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["network", "http_500", "timeout"])
async def test_telegram_send_failure_returns_false_instead_of_raising(monkeypatch, kind):
    import backend.notifier.telegram as tg
    monkeypatch.setattr(tg, "TELEGRAM_BOT_TOKEN", "bot-token")

    if kind == "network":
        _fake_httpx(monkeypatch, tg, raises=ConnectionError("telegram down"))
    elif kind == "timeout":
        _fake_httpx(monkeypatch, tg, raises=asyncio.TimeoutError("timeout"))
    else:
        _fake_httpx(monkeypatch, tg, status=500, payload={"ok": False})

    assert await tg._send_message("123", "hello") is False


@pytest.mark.asyncio
async def test_telegram_unconfigured_returns_false(monkeypatch):
    import backend.notifier.telegram as tg
    monkeypatch.setattr(tg, "TELEGRAM_BOT_TOKEN", "")
    assert await tg._send_message("123", "hello") is False


@pytest.mark.asyncio
async def test_a_dead_telegram_does_not_fail_the_scrape_health_check(test_db, monkeypatch):
    import backend.notifier.telegram as tg
    from backend.models.db import ScrapeLog
    from backend.scheduler import check_scrape_health

    for _ in range(3):
        test_db.add(ScrapeLog(source="indeed", jobs_found=0, new_jobs=0,
                              is_warning=True, ran_at=datetime.now(timezone.utc)))
    test_db.commit()

    monkeypatch.setattr(tg, "TELEGRAM_BOT_TOKEN", "bot-token")
    monkeypatch.setattr(tg, "_is_enabled", lambda: True, raising=False)
    monkeypatch.setattr(tg, "_get_chat_id", lambda: "123", raising=False)

    async def _boom(*a, **k):
        raise ConnectionError("telegram down")
    monkeypatch.setattr(tg, "_send_message", _boom, raising=False)

    await check_scrape_health()      # must not raise


@pytest.mark.asyncio
async def test_a_dead_telegram_leaves_the_scrape_run_completed(test_db, monkeypatch):
    import backend.notifier.telegram as tg
    import backend.scraper.orchestrator as orch
    import backend.analyzer.cv_scorer as scorer
    from backend.models.db import JobRun, ScrapeLog
    from backend.scheduler import run_all_scrapes

    for _ in range(3):
        test_db.add(ScrapeLog(source="indeed", jobs_found=0, new_jobs=0,
                              is_warning=True, ran_at=datetime.now(timezone.utc)))
    test_db.commit()

    async def _noop(*a, **k):
        return {}

    async def _one_empty_source(*a, **k):
        from backend.models.db import SessionLocal
        s = SessionLocal()
        try:
            s.add(ScrapeLog(source="indeed", jobs_found=0, new_jobs=0, is_warning=True,
                            ran_at=datetime.now(timezone.utc)))
            s.commit()
        finally:
            s.close()
        return {}
    monkeypatch.setattr(orch, "run_all", _one_empty_source)
    monkeypatch.setattr(scorer, "analyze_unscored_jobs", _noop)
    monkeypatch.setattr(tg, "_is_enabled", lambda: True, raising=False)
    monkeypatch.setattr(tg, "_get_chat_id", lambda: "123", raising=False)

    async def _boom(*a, **k):
        raise ConnectionError("telegram down")
    monkeypatch.setattr(tg, "_send_message", _boom, raising=False)

    await run_all_scrapes()
    test_db.expire_all()
    row = test_db.query(JobRun).filter(JobRun.job_type == "scrape_all").first()
    assert row.status == "completed"
    assert row.result_summary and "1 source" in row.result_summary


@pytest.mark.asyncio
async def test_telegram_test_trigger_survives_a_dead_bot(client, test_db, monkeypatch):
    import backend.notifier.telegram as tg
    from backend.models.db import JobRun

    async def _boom():
        raise ConnectionError("telegram down")
    monkeypatch.setattr(tg, "send_test_message", _boom, raising=False)

    assert_clean(client.post("/api/telegram/test"), 202)
    await asyncio.sleep(0.05)
    test_db.expire_all()
    row = test_db.query(JobRun).filter(JobRun.job_type == "telegram_test").first()
    assert row.status == "failed"
    # The failure reason stays in the run history, not in the HTTP response.
    assert "telegram down" not in client.post("/api/telegram/test").text
