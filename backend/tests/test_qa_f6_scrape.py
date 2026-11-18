"""QA F6 · scraping overlap and scheduler robustness.

R4-01  a manual scrape (Run all / one company / one search) is refused with 409
       `scheduled_scrape_running` while the scheduled scrape_all is live; two scoring
       sweeps never send the same job to the LLM twice (in-process claims).
R4-02  the owner's manual Run all no longer makes the scheduled tick skip every member:
       the tick runs for everyone else and names the left-out account in its summary;
       a manual single-company / single-search run leaves out only that row.
R4-03  one account's error inside the scheduled run is collected ("completed with
       errors"), scrape health and the summary still run; a broken fan-out still runs
       them and is marked failed.
T5-01/T5-04  a company (or search) deleted mid-run is skipped, the rest of the run
       continues, and a company deleted during its own ingest gets no rows.
R4-04  target keys keep the fragment and every query param; only scheme/host case,
       a trailing slash and the param order are normalised.
R4-06/T3-03  an empty or failed run stamps last_scraped_at / last_run_at (no re-fetch
       every tick); a board answering 404 is recorded as an error, not a warning.
"""
import asyncio
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from backend.accounts.context import current_account, unscoped, use_account
from backend.models.db import Account, Company, Job, JobRun, ScrapeLog, Search
from backend.tests.r4_support import (  # noqa: F401
    ACT_AS, client, _clear_running_state, assert_clean, make_job,
)


# ── fixtures / helpers ───────────────────────────────────────────────────────

@pytest.fixture
def accounts(test_db):
    a = test_db.query(Account).filter(Account.role == "owner").one()
    b = Account(name="Partner", role="member")
    test_db.add(b)
    test_db.commit()
    return a.id, b.id


@pytest.fixture
def offline(monkeypatch):
    """No network: no descriptions, no H-1B lookups, no pacing sleep."""
    import backend.analyzer.h1b_checker as h1b
    import backend.scraper.sources.company_pages as cp

    async def _no_desc(jobs):
        return []

    async def _no_h1b(job, db=None, company_lookup=None, phrases=None):
        job.h1b_jd_flag = False

    async def _instant(_s):
        return None
    monkeypatch.setattr(cp, "_fetch_descriptions_parallel", _no_desc)
    monkeypatch.setattr(h1b, "check_job_h1b", _no_h1b)
    monkeypatch.setattr(cp.asyncio, "sleep", _instant)


def _postings(slug):
    return [{"title": f"Product Manager {i}", "url": f"https://jobs.lever.co/{slug}/{i}"}
            for i in range(3)]


def _handler(monkeypatch, hook=None, result=None):
    """Stub the ATS handler: records URLs, optional `hook(url)` runs mid-fetch."""
    import backend.scraper.sources.company_pages as cp
    calls = []

    async def fake_dispatch(url, **kw):
        calls.append(url)
        if hook is not None:
            hook(url)
        if result is not None:
            return result(url)
        return _postings(url.rstrip("/").rsplit("/", 1)[-1])
    monkeypatch.setattr(cp, "_dispatch_ats", fake_dispatch)
    return calls


def _company(db, name="Acme", url="https://jobs.lever.co/acme", **kw):
    kw.setdefault("active", True)
    kw.setdefault("auto_scoring_depth", "off")
    c = Company(name=name, scrape_urls=[url], **kw)
    db.add(c)
    db.commit()
    return c


def _delete_company(cid):
    """Delete a company from another session, as a concurrent request would."""
    import backend.models.db as db_mod
    s = db_mod.SessionLocal()
    try:
        with unscoped():
            row = s.query(Company).filter(Company.id == cid).first()
            if row is not None:
                s.delete(row)
                s.commit()
    finally:
        s.close()


def _jobs_by_account(db):
    with unscoped():
        db.expire_all()
        rows = db.query(Job).all()
    out = {}
    for j in rows:
        out.setdefault(j.account_id, []).append(j.title)
    return out


def _logs(db):
    with unscoped():
        db.expire_all()
        return db.query(ScrapeLog).all()


def _scrape_runs(db):
    with unscoped():
        db.expire_all()
        return db.query(JobRun).filter(JobRun.job_type == "scrape_all").all()


def _live_scheduled(jm):
    jm._running["scrape_all:" + jm.SCHEDULED_SCRAPE_SCOPE] = jm.RunningJob(
        run_id=uuid.uuid4(), job_type="scrape_all", trigger="scheduler",
        started_at=datetime.now(timezone.utc), scope_key=jm.SCHEDULED_SCRAPE_SCOPE,
        all_accounts=True)


# ══ R4-01 · manual scrapes refused while the scheduled scrape is live ═════════

def test_manual_scrapes_get_409_scheduled_scrape_running(client, test_db, accounts):
    import backend.job_monitor as jm
    a, b = accounts
    c = _company(test_db)
    s = Search(name="S", search_mode="keyword", search_term="pm", active=True)
    test_db.add(s)
    test_db.commit()
    with use_account(b):
        cb = _company(test_db, name="Acme B")
    _live_scheduled(jm)
    before = test_db.query(JobRun).count()

    for path, headers in (
        ("/api/scrape/run-all", {}),
        (f"/api/scrape/company/{c.id}", {}),
        (f"/api/searches/{s.id}/run", {}),
        ("/api/scrape/run-all", {ACT_AS: str(b)}),             # a member
        (f"/api/scrape/company/{cb.id}", {ACT_AS: str(b)}),
    ):
        r = assert_clean(client.post(path, headers=headers), 409)
        assert r.json()["detail"] == "scheduled_scrape_running", path
        assert "scheduled scrape is running" in r.json()["message"]
    test_db.expire_all()
    assert test_db.query(JobRun).count() == before          # nothing was started


@pytest.mark.asyncio
async def test_member_launch_refused_then_accepted_after_the_tick(test_db, accounts):
    import backend.job_monitor as jm
    a, b = accounts

    async def _noop():
        return None
    _live_scheduled(jm)
    with use_account(b):
        for jt, scope in (("scrape_all", None), ("company_scrape", "c1"), ("search_run", "s1")):
            with pytest.raises(jm.ScheduledScrapeRunningError):
                jm.launch_background(jt, _noop, trigger="manual", scope_key=scope)
        # other job types are not affected
        jm.launch_background("daily_digest", _noop, trigger="manual")
    jm._running.pop("scrape_all:" + jm.SCHEDULED_SCRAPE_SCOPE)
    with use_account(b):
        jm.launch_background("scrape_all", _noop, trigger="manual")
    await asyncio.sleep(0.05)


def test_ordinary_duplicate_keeps_the_old_409_text(client, test_db):
    import backend.job_monitor as jm
    jm._running["scrape_all"] = jm.RunningJob(
        run_id=uuid.uuid4(), job_type="scrape_all", trigger="manual",
        started_at=datetime.now(timezone.utc))
    r = assert_clean(client.post("/api/scrape/run-all"), 409)
    assert r.json()["detail"] == "scrape_all is already running"


# ── R4-01 · scoring sweeps claim their jobs ──────────────────────────────────

def _fake_scoring(monkeypatch):
    import backend.analyzer.cv_scorer as cs
    calls = []

    async def _score(job, cv_texts, db=None, depth="light", preloaded_text=None):
        calls.append((job.id, current_account.get()))
        await asyncio.sleep(0.01)              # the overlap window
        return {"scores": {"R": 10}, "best_cv": "R"}
    monkeypatch.setattr(cs, "score_job_sync", _score)
    monkeypatch.setattr(cs, "_get_default_resume", lambda db: {})
    monkeypatch.setattr(cs, "_get_resume_texts", lambda db: {"R": "cv text"})
    monkeypatch.setattr(cs, "_get_resume_texts_for_company", lambda db, c: {"R": "cv text"})
    return calls


@pytest.mark.asyncio
async def test_two_overlapping_sweeps_score_each_job_once(test_db, monkeypatch):
    import backend.analyzer.cv_scorer as cs
    calls = _fake_scoring(monkeypatch)
    _company(test_db, auto_scoring_depth="light")
    ids = [make_job(test_db, company="Acme", title=f"PM {i}", status="new",
                    description="x" * 80).id for i in range(10)]

    await asyncio.gather(cs.analyze_unscored_jobs("new"), cs.analyze_unscored_jobs("new"))

    assert sorted(j for j, _ in calls) == sorted(ids), "every job scored exactly once"
    assert cs.claimed_jobs() == frozenset()                 # claims released
    test_db.expire_all()
    assert all(j.cv_scores == {"R": 10} for j in test_db.query(Job).all())


@pytest.mark.asyncio
async def test_sweep_claims_are_released_when_a_sweep_fails(test_db, monkeypatch):
    import backend.analyzer.cv_scorer as cs
    _fake_scoring(monkeypatch)
    _company(test_db, auto_scoring_depth="light")
    make_job(test_db, company="Acme", title="PM", status="new", description="x" * 80)

    seen = []

    def _boom(job):
        seen.append(cs.claimed_jobs())        # claimed by now
        raise RuntimeError("row unreadable")
    monkeypatch.setattr(cs, "_job_text_from_row", _boom)
    with pytest.raises(RuntimeError):
        await cs.analyze_unscored_jobs("new")
    assert len(seen) == 1 and len(seen[0]) == 1
    assert cs.claimed_jobs() == frozenset()


@pytest.mark.asyncio
async def test_member_manual_and_scheduled_sweep_overlap_scores_once(test_db, accounts, monkeypatch):
    """The R4-01 T5 shape: the member's sweep and the scheduled sweep for the same member
    overlap -> 10 LLM calls for 10 jobs (was 20)."""
    import backend.analyzer.cv_scorer as cs
    from backend.accounts.background import acting_as
    a, b = accounts
    calls = _fake_scoring(monkeypatch)
    with use_account(b):
        _company(test_db, auto_scoring_depth="light")
        for i in range(10):
            make_job(test_db, company="Acme", title=f"PM {i}", status="new",
                     description="x" * 80)

    async def _sweep():
        with acting_as(b):
            await cs.analyze_unscored_jobs("new")
    await asyncio.gather(_sweep(), _sweep())
    assert len(calls) == 10 and {acc for _, acc in calls} == {b}


# ══ R4-02 · the owner's manual Run all does not skip the members' tick ═══════

@pytest.mark.asyncio
async def test_scheduled_tick_runs_for_members_during_the_owners_manual_run(
        test_db, accounts, monkeypatch, offline):
    import backend.job_monitor as jm
    from backend.scheduler import run_all_scrapes
    a, b = accounts
    calls = _handler(monkeypatch)
    _company(test_db, url="https://jobs.lever.co/owner-co")
    with use_account(b):
        _company(test_db, name="Member Co", url="https://jobs.lever.co/member-co")
    gate = asyncio.Event()

    async def _slow():
        await gate.wait()
    jm.launch_background("scrape_all", _slow, trigger="manual")   # the owner's Run all

    await run_all_scrapes()
    gate.set()
    await asyncio.sleep(0.05)

    assert calls == ["https://jobs.lever.co/member-co"], "the member's target ran, the owner's did not"
    assert set(_jobs_by_account(test_db)) == {b}
    runs = {r.trigger: r for r in _scrape_runs(test_db)}
    assert set(runs) == {"manual", "scheduler"}
    sched = runs["scheduler"]
    assert sched.status == "completed"
    assert "skipped (manual run in progress): Owner" in sched.result_summary
    assert "+3 new" in sched.result_summary


@pytest.mark.asyncio
async def test_scheduled_tick_leaves_out_only_a_company_being_scraped_by_hand(
        test_db, accounts, monkeypatch, offline):
    import backend.job_monitor as jm
    from backend.scheduler import run_all_scrapes
    a, b = accounts
    calls = _handler(monkeypatch)
    _company(test_db, url="https://jobs.lever.co/owner-co")
    with use_account(b):
        busy = _company(test_db, name="Busy", url="https://jobs.lever.co/busy-co")
        _company(test_db, name="Idle", url="https://jobs.lever.co/idle-co")
    jm._running[f"company_scrape:{busy.id}@{b}"] = jm.RunningJob(
        run_id=uuid.uuid4(), job_type="company_scrape", trigger="manual",
        started_at=datetime.now(timezone.utc), scope_key=str(busy.id),
        company_id=str(busy.id), account_id=b)

    await run_all_scrapes()

    assert sorted(calls) == ["https://jobs.lever.co/idle-co", "https://jobs.lever.co/owner-co"]
    sched = [r for r in _scrape_runs(test_db) if r.trigger == "scheduler"][0]
    assert sched.status == "completed" and "skipped" not in sched.result_summary


@pytest.mark.asyncio
async def test_scheduled_tick_leaves_out_a_search_being_run_by_hand(test_db, monkeypatch):
    import backend.job_monitor as jm
    import backend.scraper.orchestrator as orch
    ran = []

    async def _run_search(search, proxy_url=None, **kw):
        ran.append(search.name)
        return {"jobs_found": 1, "new_jobs": 0, "error": None, "duration": 0}
    monkeypatch.setattr(orch, "run_search", _run_search)
    s1 = Search(name="Busy", search_mode="keyword", search_term="a", active=True)
    s2 = Search(name="Idle", search_mode="keyword", search_term="b", active=True)
    test_db.add_all([s1, s2])
    test_db.commit()
    jm._running[f"search_run:{s1.id}"] = jm.RunningJob(
        run_id=uuid.uuid4(), job_type="search_run", trigger="manual",
        started_at=datetime.now(timezone.utc), scope_key=str(s1.id))

    await orch.run_all(force=True, skip=jm.manual_scrape_scopes())
    assert ran == ["Idle"]


# ══ R4-03 · one account's error does not fail the scheduled run ══════════════

def _fake_tick(monkeypatch, run_all=None, saved=None):
    import backend.analyzer.cv_scorer as cs
    import backend.scheduler as sched
    import backend.scraper.orchestrator as orch
    health = []

    async def _run_all(*a, **k):
        return {}
    monkeypatch.setattr(orch, "run_all", run_all or _run_all)

    async def _saved(status="saved"):
        if saved:
            saved(status)
    monkeypatch.setattr(cs, "analyze_unscored_jobs", _saved)

    async def _health(since=None):
        health.append(since)
    monkeypatch.setattr(sched, "check_scrape_health", _health)
    return health


@pytest.mark.asyncio
async def test_member_scoring_error_is_collected_not_fatal(test_db, accounts, monkeypatch):
    from backend.scheduler import run_all_scrapes
    a, b = accounts
    scored = []

    def _saved(status):
        scored.append(current_account.get())
        if current_account.get() == b:
            raise RuntimeError("bad default_resume_id")
    health = _fake_tick(monkeypatch, saved=_saved)

    await run_all_scrapes()

    assert scored == [a, b]
    assert len(health) == 1, "scrape health still ran"
    run = _scrape_runs(test_db)[0]
    assert run.status == "completed" and run.error is None
    assert ("completed with errors (1): Partner: saved-job scoring: "
            "RuntimeError: bad default_resume_id") in run.result_summary


@pytest.mark.asyncio
async def test_fan_out_errors_reach_the_summary(test_db, accounts, monkeypatch):
    from backend.scheduler import run_all_scrapes
    a, b = accounts

    async def _run_all(*a_, **k):
        return {"errors": [{"account": b, "where": "company Acme",
                            "error": "IntegrityError: boom"}]}
    _fake_tick(monkeypatch, run_all=_run_all)
    await run_all_scrapes()
    run = _scrape_runs(test_db)[0]
    assert run.status == "completed"
    assert "completed with errors (1): Partner: company Acme: IntegrityError: boom" in run.result_summary


@pytest.mark.asyncio
async def test_broken_fan_out_still_scores_checks_health_and_summarises(test_db, accounts, monkeypatch):
    from backend.scheduler import run_all_scrapes
    a, b = accounts
    scored = []

    async def _run_all(*a_, **k):
        raise RuntimeError("fan-out exploded")
    health = _fake_tick(monkeypatch, run_all=_run_all,
                        saved=lambda s: scored.append(current_account.get()))
    await run_all_scrapes()                     # must not raise
    assert scored == [a, b] and len(health) == 1
    run = _scrape_runs(test_db)[0]
    assert run.status == "failed" and "fan-out exploded" in run.error
    assert run.result_summary                   # the summary was written


@pytest.mark.asyncio
async def test_real_run_all_collects_a_members_sweep_error(test_db, accounts, monkeypatch, offline):
    """End to end through the real fan-out: B's post-batch scoring sweep raises; A's
    scrape and the run are fine, B's error is in the summary."""
    import backend.analyzer.cv_scorer as cs
    import backend.scheduler as sched
    from backend.scheduler import run_all_scrapes
    a, b = accounts
    _handler(monkeypatch)
    _company(test_db, url="https://jobs.lever.co/owner-co", auto_scoring_depth="light")
    with use_account(b):
        _company(test_db, name="Member Co", url="https://jobs.lever.co/member-co",
                 auto_scoring_depth="light")
    swept = []

    async def _sweep(status="saved"):
        swept.append((current_account.get(), status))
        if status == "new" and current_account.get() == b:
            raise RuntimeError("member sweep broke")
    monkeypatch.setattr(cs, "analyze_unscored_jobs", _sweep)

    async def _health(since=None):
        swept.append("health")
    monkeypatch.setattr(sched, "check_scrape_health", _health)

    await run_all_scrapes()
    assert (a, "new") in swept and (b, "new") in swept and "health" in swept
    run = _scrape_runs(test_db)[0]
    assert run.status == "completed"
    assert "Partner: company scoring sweep: RuntimeError: member sweep broke" in run.result_summary


@pytest.mark.asyncio
async def test_for_each_account_collects_into_errors(test_db, accounts):
    from backend.accounts.background import for_each_account
    a, b = accounts
    errors = []

    async def _body():
        if current_account.get() == a:
            raise ValueError("owner broke")
    await for_each_account("x", _body, errors=errors)       # no raise
    assert errors == [{"account": a, "where": "x", "error": "ValueError: owner broke"}]
    with pytest.raises(ValueError):
        await for_each_account("x", _body)                  # top-level use: re-raised


# ══ T5-01 / T5-04 · deleted mid-run ═══════════════════════════════════════════

@pytest.mark.asyncio
async def test_subscriber_deleted_during_the_shared_fetch_is_skipped(
        test_db, accounts, monkeypatch, offline):
    import backend.scraper.sources.company_pages as cp
    a, b = accounts
    _company(test_db, url="https://jobs.lever.co/acme")
    with use_account(b):
        doomed = _company(test_db, name="Acme B", url="https://jobs.lever.co/acme")
    _company(test_db, name="Zeta", url="https://jobs.lever.co/zeta")
    doomed_id = doomed.id

    def _hook(url):
        if url.endswith("/acme"):
            _delete_company(doomed_id)
    calls = _handler(monkeypatch, hook=_hook)

    summary = await cp.scrape_career_pages(force=True)

    assert calls == ["https://jobs.lever.co/acme", "https://jobs.lever.co/zeta"]
    assert {"name": "Acme B", "reason": "deleted during the run"} in summary["skipped"]
    assert summary["failed"] == 0 and summary["errors"] == []
    jobs = _jobs_by_account(test_db)
    assert set(jobs) == {a} and len(jobs[a]) == 6           # Acme + Zeta for the owner
    assert all(l.account_id == a for l in _logs(test_db))


@pytest.mark.asyncio
async def test_subscriber_deleted_before_its_target_starts_is_skipped(
        test_db, accounts, monkeypatch, offline):
    """Deleted during an earlier target: the expired row would raise ObjectDeletedError
    in the due check / attribute reads (T5-01)."""
    import backend.scraper.sources.company_pages as cp
    a, b = accounts
    _company(test_db, name="Zeta", url="https://jobs.lever.co/zeta")
    _company(test_db, url="https://jobs.lever.co/acme")
    with use_account(b):
        doomed = _company(test_db, name="Acme B", url="https://jobs.lever.co/acme")
    doomed_id = doomed.id

    def _hook(url):
        if url.endswith("/zeta"):
            _delete_company(doomed_id)
    calls = _handler(monkeypatch, hook=_hook)

    summary = await cp.scrape_career_pages(force=False)      # the due check reads rows too

    assert calls == ["https://jobs.lever.co/zeta", "https://jobs.lever.co/acme"]
    assert {"name": "Acme B", "reason": "deleted during the run"} in summary["skipped"]
    assert set(_jobs_by_account(test_db)) == {a}


@pytest.mark.asyncio
async def test_company_deleted_during_its_own_ingest_gets_no_rows(
        test_db, accounts, monkeypatch, offline):
    """T5-04: the delete lands while B's descriptions are fetched; B's ingest is thrown
    away (no jobs of a company it just deleted), A is unaffected."""
    import backend.scraper.sources.company_pages as cp
    a, b = accounts
    _company(test_db, url="https://jobs.lever.co/acme")
    with use_account(b):
        doomed = _company(test_db, name="Acme B", url="https://jobs.lever.co/acme")
    doomed_id = doomed.id
    _handler(monkeypatch)

    async def _desc(jobs):
        if current_account.get() == b:
            _delete_company(doomed_id)
        return []
    monkeypatch.setattr(cp, "_fetch_descriptions_parallel", _desc)

    summary = await cp.scrape_career_pages(force=True)
    assert {"name": "Acme B", "reason": "deleted during the run"} in summary["skipped"]
    jobs = _jobs_by_account(test_db)
    assert b not in jobs and len(jobs[a]) == 3
    assert [l.account_id for l in _logs(test_db)] == [a]


@pytest.mark.asyncio
async def test_company_deleted_late_in_its_ingest_is_caught_by_the_locked_recheck(
        test_db, accounts, monkeypatch, offline):
    """The delete lands during the per-job H-1B check (after the inserts started): the
    locked re-check before the commit sees it, skips the company and writes no log row.
    (Throwing the flushed rows away is a Postgres guarantee: pysqlite commits a SAVEPOINT
    opened outside BEGIN on RELEASE, so rows are not asserted here; see the F6 PG check.)"""
    import backend.analyzer.h1b_checker as h1b
    a, b = accounts
    import backend.scraper.sources.company_pages as cp
    _company(test_db, url="https://jobs.lever.co/acme")
    with use_account(b):
        doomed = _company(test_db, name="Acme B", url="https://jobs.lever.co/acme")
    doomed_id = doomed.id
    _handler(monkeypatch)

    async def _h1b(job, db=None, company_lookup=None, phrases=None):
        job.h1b_jd_flag = False
        if current_account.get() == b:
            _delete_company(doomed_id)
    monkeypatch.setattr(h1b, "check_job_h1b", _h1b)

    summary = await cp.scrape_career_pages(force=True)
    assert {"name": "Acme B", "reason": "deleted during the run"} in summary["skipped"]
    assert summary["failed"] == 0
    assert [l.account_id for l in _logs(test_db)] == [a]


@pytest.mark.asyncio
async def test_crash_after_the_delete_is_a_skip_not_a_failure(test_db, accounts, monkeypatch, offline):
    """The ingest raises (e.g. the ScrapeLog FK on Postgres) after the company is gone:
    the handler rolls back first and records nothing for the vanished row."""
    import backend.scraper.sources.company_pages as cp
    a, b = accounts
    _company(test_db, url="https://jobs.lever.co/owner-co")
    with use_account(b):
        doomed = _company(test_db, name="Acme B", url="https://jobs.lever.co/b-co")
    doomed_id = doomed.id
    real = cp.scrape_single_career_page

    async def _single(company, **kw):
        if current_account.get() == b:
            _delete_company(doomed_id)
            raise RuntimeError("scrape_log_company_id_fkey")
        return await real(company, **kw)
    monkeypatch.setattr(cp, "scrape_single_career_page", _single)
    _handler(monkeypatch)

    summary = await cp.scrape_career_pages(force=True)
    assert summary["failed"] == 0 and summary["errors"] == []
    assert {"name": "Acme B", "reason": "deleted during the run"} in summary["skipped"]
    assert [l.account_id for l in _logs(test_db)] == [a]


@pytest.mark.asyncio
async def test_search_deleted_mid_run_is_skipped(test_db, monkeypatch):
    import backend.scraper.orchestrator as orch
    s1 = Search(name="First", search_mode="keyword", search_term="a", active=True)
    s2 = Search(name="Second", search_mode="keyword", search_term="b", active=True)
    test_db.add_all([s1, s2])
    test_db.commit()
    s2_id = s2.id
    ran = []

    async def _run_search(search, proxy_url=None, **kw):
        ran.append(search.name)
        import backend.models.db as db_mod
        s = db_mod.SessionLocal()
        try:
            s.query(Search).filter(Search.id == s2_id).delete()
            s.commit()
        finally:
            s.close()
        return {"jobs_found": 1, "new_jobs": 0, "error": None, "duration": 0}
    monkeypatch.setattr(orch, "run_search", _run_search)

    out = await orch.run_all(force=True)
    assert ran == ["First"] and out["errors"] == []
    assert [l.search_id for l in _logs(test_db)] == [s1.id]


@pytest.mark.asyncio
async def test_company_sweep_runs_before_the_search_results_are_scored(test_db, monkeypatch):
    """Scoring is one LLM call per new job: a search that brings 100 new jobs must not hold
    the company scrapes back until all of them are scored."""
    import backend.analyzer.cv_scorer as cs
    import backend.scraper.orchestrator as orch
    from backend.scraper.sources import company_pages
    test_db.add(Search(name="Auto", search_mode="keyword", search_term="a", active=True,
                       auto_scoring_depth="light"))
    test_db.commit()
    order = []

    async def _run_search(search, proxy_url=None, **kw):
        order.append("search")
        return {"jobs_found": 100, "new_jobs": 100, "error": None, "duration": 0}

    async def _companies(**kw):
        order.append("companies")
        return {}

    async def _sweep(status="saved"):
        order.append(f"score {status}")
    monkeypatch.setattr(orch, "run_search", _run_search)
    monkeypatch.setattr(company_pages, "scrape_career_pages", _companies)
    monkeypatch.setattr(cs, "analyze_unscored_jobs", _sweep)

    out = await orch.run_all(force=True)
    assert order == ["search", "companies", "score new"] and out["errors"] == []


# ══ R4-04 · target URL key ════════════════════════════════════════════════════

def test_target_url_keeps_fragment_and_every_query_param(test_db):
    from backend.scraper.targets import target_url
    from backend.tests.r4_support import set_setting
    # the posting-dedup list must not shape list targets
    set_setting(test_db, "dedup_tracking_params", '["from", "mode", "source", "ref"]')
    berlin = "https://careers.x.com/#/jobs?location=Berlin"
    austin = "https://careers.x.com/#/jobs?location=Austin"
    assert target_url(berlin) != target_url(austin)
    assert target_url(berlin).endswith("#/jobs?location=Berlin")
    assert target_url("https://x.eightfold.ai/careers?from=20") != target_url("https://x.eightfold.ai/careers")
    jpm = "https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX/requisitions?mode=location"
    assert "mode=location" in target_url(jpm)
    assert target_url("https://wd5.myworkdayjobs.com/x?source=careers") != \
        target_url("https://wd5.myworkdayjobs.com/x")
    assert target_url("https://jobs.x.com/?utm_source=li") != target_url("https://jobs.x.com/")


def test_target_url_normalises_only_case_slash_and_order():
    from backend.scraper.targets import target_url
    assert target_url("HTTPS://Jobs.Lever.CO/acme/?b=2&a=1") == "https://jobs.lever.co/acme?a=1&b=2"
    # path case is meaningful and kept
    assert target_url("https://x.com/Careers") != target_url("https://x.com/careers")
    # a request spec is compared verbatim
    assert target_url("POST|https://x.com/api|{}") == "POST|https://x.com/api|{}"


@pytest.mark.asyncio
async def test_fragment_routes_are_two_targets_two_fetches(test_db, accounts, monkeypatch, offline):
    """The R4-04 collapse: before, B got A's Berlin list and never saw Austin."""
    import backend.scraper.sources.company_pages as cp
    a, b = accounts
    berlin = "https://careers.x.com/#/jobs?location=Berlin"
    austin = "https://careers.x.com/#/jobs?location=Austin"

    def _result(url):
        city = url.rsplit("=", 1)[-1]
        return [{"title": f"PM {city}", "url": f"https://careers.x.com/jobs/{city}"}]
    monkeypatch.setattr(cp, "_needs_browser", lambda urls: False)
    calls = _handler(monkeypatch, result=_result)
    _company(test_db, name="X", url=berlin)
    with use_account(b):
        _company(test_db, name="X", url=austin)
    # the fake handler stands in for every URL
    monkeypatch.setattr(cp.lever, "is_lever", lambda u: True)

    await cp.scrape_career_pages(force=True)
    assert sorted(calls) == sorted([berlin, austin])
    jobs = _jobs_by_account(test_db)
    assert jobs[a] == ["PM Berlin"] and jobs[b] == ["PM Austin"]


def test_tracking_looking_param_is_a_separate_company_target(test_db, accounts):
    from backend.scraper.targets import company_key
    a, b = accounts
    c1 = _company(test_db, url="https://acme.wd5.myworkdayjobs.com/Careers?source=x")
    with use_account(b):
        c2 = _company(test_db, url="https://acme.wd5.myworkdayjobs.com/Careers")
        c3 = _company(test_db, name="Acme 3", url="HTTPS://ACME.wd5.myworkdayjobs.com/Careers/")
    assert company_key(c1) != company_key(c2) == company_key(c3)


# ══ R4-06 / T3-03 · empty or failed runs stamp the timestamp; 404 is an error ══

@pytest.mark.asyncio
async def test_empty_board_stamps_last_scraped_at_and_is_not_refetched(
        test_db, monkeypatch, offline):
    import backend.scraper.sources.company_pages as cp
    calls = _handler(monkeypatch, result=lambda url: [])
    c = _company(test_db)

    await cp.scrape_career_pages(force=False)
    await cp.scrape_career_pages(force=False)

    assert len(calls) == 1, "not due again within its interval"
    test_db.expire_all()
    assert c.last_scraped_at is not None
    (log,) = _logs(test_db)
    assert log.is_warning and log.error is None


@pytest.mark.asyncio
async def test_failed_fetch_stamps_last_scraped_at_with_the_error(test_db, monkeypatch, offline):
    import backend.scraper.sources.company_pages as cp
    calls = []

    async def _down(url, **kw):
        calls.append(url)
        raise ConnectionError("board down")
    monkeypatch.setattr(cp, "_dispatch_ats", _down)
    c = _company(test_db)

    await cp.scrape_career_pages(force=False)
    await cp.scrape_career_pages(force=False)

    assert len(calls) == 1
    test_db.expire_all()
    assert c.last_scraped_at is not None
    (log,) = _logs(test_db)
    assert "board down" in log.error and not log.is_warning


class _Resp(SimpleNamespace):
    pass


def _fake_httpx(monkeypatch, module, status):
    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, **k):
            return _Resp(status_code=status, text="")

        async def post(self, url, **k):
            return _Resp(status_code=status, text="")
    monkeypatch.setattr(module.httpx, "AsyncClient", _Client)


@pytest.mark.asyncio
@pytest.mark.parametrize("mod_name,url", [
    ("greenhouse", "https://boards.greenhouse.io/hextechnologies"),
    ("lever", "https://jobs.lever.co/gone"),
    ("ashby", "https://jobs.ashbyhq.com/gone"),
    ("rippling", "https://ats.rippling.com/gone/jobs"),
    ("smartrecruiters", "https://jobs.smartrecruiters.com/Gone"),
])
async def test_board_404_raises_board_not_found(monkeypatch, mod_name, url, test_db):
    import importlib
    from backend.scraper._shared.errors import BoardNotFoundError
    mod = importlib.import_module(f"backend.scraper.ats.{mod_name}")
    _fake_httpx(monkeypatch, mod, 404)
    with pytest.raises(BoardNotFoundError, match="HTTP 404"):
        await mod.scrape(url)
    # the preview (debug) path still reports it as a rejected row
    jobs, rejected = await mod.scrape(url, debug=True)
    assert jobs == [] and any("404" in r["reason"] for r in rejected)


@pytest.mark.asyncio
async def test_board_500_stays_a_quiet_empty_result(monkeypatch, test_db):
    import backend.scraper.ats.greenhouse as gh
    _fake_httpx(monkeypatch, gh, 503)
    assert await gh.scrape("https://boards.greenhouse.io/acme") == []


@pytest.mark.asyncio
async def test_404_board_is_recorded_as_an_error_and_stamped(test_db, monkeypatch, offline):
    """T3-03: Hex's Greenhouse board gone -> error row (not a warning), stamped."""
    import backend.scraper.ats.greenhouse as gh
    import backend.scraper.sources.company_pages as cp
    _fake_httpx(monkeypatch, gh, 404)
    c = _company(test_db, name="Hex", url="https://boards.greenhouse.io/hextechnologies")

    summary = await cp.scrape_career_pages(force=True)

    assert summary["failed"] == 1
    (log,) = _logs(test_db)
    assert "Greenhouse board 'hextechnologies' not found (HTTP 404)" in log.error
    assert log.is_warning is False
    test_db.expire_all()
    assert c.last_scraped_at is not None


@pytest.mark.asyncio
async def test_empty_search_run_stamps_last_run_at(test_db, monkeypatch):
    import backend.scraper.orchestrator as orch
    ran = []

    async def _empty(search, proxy_url=None, **kw):
        ran.append(search.name)
        return {"jobs_found": 0, "new_jobs": 0, "error": "indeed: 429", "duration": 0}
    monkeypatch.setattr(orch, "run_search", _empty)
    s = Search(name="S", search_mode="keyword", search_term="pm", active=True,
               run_interval_minutes=60)
    test_db.add(s)
    test_db.commit()

    await orch.run_all(force=False)
    await orch.run_all(force=False)

    assert ran == ["S"], "not re-run on the next tick"
    test_db.expire_all()
    assert s.last_run_at is not None
    assert [l.error for l in _logs(test_db)] == ["indeed: 429"]
