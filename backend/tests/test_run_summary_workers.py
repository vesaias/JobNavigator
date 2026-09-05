"""Every background job type's worker must return a summary string for JobRun.result_summary (free-form; that it exists is what's pinned)."""
import pytest

from backend.models.db import Company, Job, Resume, Search, Setting


@pytest.mark.asyncio
async def test_score_single_job_returns_summary(test_db, monkeypatch):
    import backend.analyzer.cv_scorer as scorer

    job = Job(company="Acme", title="Staff PM", url="https://acme.test/1",
              external_id="e1", description="Long job description " * 20, status="new")
    resume = Resume(name="PM", is_base=True, json_data={"summary": "x " * 60})
    test_db.add_all([job, resume])
    test_db.commit()

    async def fake_score(job_obj, cv_texts, db=None, depth="full", preloaded_text=None):
        return {"scores": {"PM": 84}, "best_cv": "PM"}

    monkeypatch.setattr(scorer, "score_job_sync", fake_score)

    summary = await scorer.score_single_job(str(job.id), cv_ids=[str(resume.id)], depth="light")
    assert isinstance(summary, str) and summary
    assert "Staff PM" in summary and "84" in summary and "light" in summary


@pytest.mark.asyncio
async def test_score_single_job_summarises_a_no_op(test_db, monkeypatch):
    """Even the early exits say why nothing happened, instead of a blank cell."""
    import uuid
    import backend.analyzer.cv_scorer as scorer

    summary = await scorer.score_single_job(str(uuid.uuid4()))
    assert summary == "Job not found"


@pytest.mark.asyncio
async def test_search_run_worker_returns_counts(test_db, monkeypatch):
    import backend.api.routes_searches as rs
    import backend.scraper.orchestrator as orch

    search = Search(name="Remote PM", search_mode="keyword", active=True)
    test_db.add(search)
    test_db.commit()

    async def fake_run(search_id, auto_score=None):
        return {"jobs_found": 12, "new_jobs": 4, "error": None, "duration": 3.0}

    monkeypatch.setattr(orch, "_run_search_by_id", fake_run)

    captured = {}

    def fake_launch(job_type, coro_func, **kw):
        captured["coro"] = coro_func
        return "run-1"

    monkeypatch.setattr("backend.job_monitor.launch_background", fake_launch)

    resp = await rs.trigger_search(str(search.id), db=test_db)
    assert resp["status"] == "running"

    summary = await captured["coro"]()
    assert summary == "Remote PM - 12 seen, +4 new"


@pytest.mark.asyncio
async def test_company_scrape_worker_still_returns_counts(test_db, monkeypatch):
    """The one job type that already had a summary keeps it."""
    pytest.importorskip("apscheduler")
    import backend.main as main_mod
    import backend.scraper.sources.company_pages as cp

    c = Company(name="Acme", active=True, playwright_enabled=True,
                scrape_urls=["https://jobs.lever.co/acme"], auto_scoring_depth="off")
    test_db.add(c)
    test_db.commit()

    async def fake_scrape(company, **kw):
        return {"jobs_found": 9, "new_jobs": 2, "duration": 1.0}

    monkeypatch.setattr(cp, "scrape_single_career_page", fake_scrape)

    captured = {}

    def fake_launch(job_type, coro_func, **kw):
        captured["coro"] = coro_func
        return "run-2"

    monkeypatch.setattr(main_mod, "launch_background", fake_launch)
    await main_mod.trigger_company_scrape(str(c.id))
    assert await captured["coro"]() == "Acme - 9 seen, +2 new"


@pytest.mark.asyncio
async def test_score_resume_worker_returns_summary(test_db, monkeypatch):
    """Needs the container (routes_resumes imports python-multipart)."""
    pytest.importorskip("multipart")
    import backend.api.routes_resumes as rr
    import backend.analyzer.cv_scorer as scorer

    job = Job(company="Acme", title="Staff PM", url="https://acme.test/2",
              external_id="e2", description="d " * 200, status="new")
    test_db.add(job)
    test_db.commit()
    copy = Resume(name="PM -> Acme", is_base=False, job_id=job.id,
                  json_data={"summary": "tailored summary " * 20})
    test_db.add(copy)
    test_db.commit()

    async def fake_score(job_obj, cv_texts, db=None, depth="full", preloaded_text=None):
        return {"scores": {"Tailored": 77}}

    monkeypatch.setattr(scorer, "score_job_sync", fake_score)

    summary = await rr._score_resume_impl(str(copy.id), "light")
    assert "Staff PM" in summary and "77" in summary


@pytest.mark.asyncio
async def test_tailor_worker_returns_summary(test_db, monkeypatch):
    """Needs the container (routes_resumes imports python-multipart)."""
    pytest.importorskip("multipart")
    import backend.api.routes_resumes as rr

    base = Resume(name="Base PM", is_base=True,
                  json_data={"summary": "s", "experience": [], "skills": []})
    job = Job(company="Acme", title="Staff PM", url="https://acme.test/3",
              external_id="e3", description="d " * 200, status="new")
    test_db.add_all([base, job])
    test_db.add(Setting(key="cv_tailor_prompt", value="{job_description} {resume_json}"))
    test_db.add(Setting(key="tailor_auto_quick_score", value="off"))
    test_db.commit()

    async def fake_llm(prompt, system, max_tokens=3000):
        return {"text": '{"summary": "tailored"}', "usage": {},
                "provider": "claude_code", "model": "claude-sonnet-5"}

    monkeypatch.setattr("backend.analyzer.llm_client.call_cv_tailor_llm", fake_llm)

    summary = await rr._tailor_impl(str(base.id), str(job.id), None)
    assert isinstance(summary, str) and "Created" in summary
