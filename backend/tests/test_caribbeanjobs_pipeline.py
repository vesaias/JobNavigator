"""caribbeanjobs orchestrator wiring + preview/run pipeline (no network); uses the shared `test_db`
fixture, which rebinds the module-level SessionLocal so run() hits the test DB."""
import json

import pytest

from backend.models.db import Setting, Search, Job
from backend.scraper.sources import caribbeanjobs


def _job(title, company, url, desc="Great role", salary_min=None, salary_max=None, expired=False):
    return {"title": title, "company": company, "url": url, "location": "Jamaica",
            "description": desc, "posted": None, "employment_type": "", "expired": expired,
            "salary_min": salary_min, "salary_max": salary_max}


def _patch_fetch(monkeypatch, jobs, details=None):
    async def fake_listings(client, base, keywords, wanted):
        return jobs

    async def fake_details(client, candidates):
        return {j["url"]: dict(j) for j in candidates} if details is None else details

    monkeypatch.setattr(caribbeanjobs, "_fetch_listings", fake_listings)
    monkeypatch.setattr(caribbeanjobs, "_fetch_details", fake_details)


# ── orchestrator wiring ─────────────────────────────────────────────────────

def test_validity_requires_url_or_term():
    from backend.scraper import orchestrator
    assert orchestrator._search_mode_is_valid(Search(search_mode="caribbeanjobs", search_term="engineer")) is True
    assert orchestrator._search_mode_is_valid(Search(search_mode="caribbeanjobs", direct_url="https://www.caribbeanjobs.com/ShowResults.aspx?Keywords=x")) is True
    assert orchestrator._search_mode_is_valid(Search(search_mode="caribbeanjobs")) is False


def test_source_label():
    from backend.scraper import orchestrator
    assert orchestrator._source_for_search(Search(search_mode="caribbeanjobs")) == "caribbeanjobs"


def test_search_config_error_names_the_missing_query():
    """The scheduler skips an invalid config silently; this is the message the manual trigger
    surfaces instead of "nothing ran"."""
    from backend.scraper import orchestrator
    err = orchestrator.search_config_error(Search(search_mode="caribbeanjobs"))
    assert "CaribbeanJobs.com" in err and "search term or a URL" in err
    assert orchestrator.search_config_error(Search(search_mode="caribbeanjobs", search_term="x")) is None
    assert orchestrator.search_config_error(Search(search_mode="caribbeanjobs", direct_url="https://www.caribbeanjobs.com/ShowResults.aspx?x=1")) is None
    assert "freehire.me" in orchestrator.search_config_error(Search(search_mode="freehire"))
    assert orchestrator.search_config_error(Search(search_mode="keyword")) is None


@pytest.mark.asyncio
async def test_dispatch_routes_to_caribbeanjobs(monkeypatch):
    from backend.scraper import orchestrator
    called = {}

    async def fake_run(search, **kw):
        called["ok"] = True
        return {"jobs_found": 0, "new_jobs": 0, "error": None, "duration": 0}

    monkeypatch.setattr(caribbeanjobs, "run", fake_run)
    await orchestrator.run_search(Search(search_mode="caribbeanjobs", search_term="engineer"))
    assert called.get("ok") is True


# ── preview() filtering ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_preview_applies_title_body_and_expired_filters(monkeypatch, test_db):
    test_db.add(Setting(key="body_exclusion_phrases", value=json.dumps(["us citizen only"])))
    test_db.commit()

    _patch_fetch(monkeypatch, [
        _job("Backend Engineer", "Acme", "https://cj/1", desc="Great backend role"),
        _job("Data Intern", "Acme", "https://cj/2", desc="entry role"),
        _job("Senior Engineer", "BadCo", "https://cj/3", desc="US citizen only please"),
        _job("Old Engineer", "Acme", "https://cj/4", desc="fine role", expired=True),
    ])

    search = Search(name="t", search_mode="caribbeanjobs", search_term="engineer",
                    title_exclude_keywords=["intern"], company_exclude=[])
    r = await caribbeanjobs.preview(search, test_db)

    assert r["raw_count"] == 4
    by = {j["title"]: j for j in r["jobs"]}
    assert by["Backend Engineer"]["kept"] is True
    assert by["Data Intern"]["kept"] is False and "intern" in (by["Data Intern"]["reason"] or "").lower()
    assert by["Senior Engineer"]["kept"] is False and "Body exclusion" in (by["Senior Engineer"]["reason"] or "")
    assert by["Old Engineer"]["kept"] is False and "Expired" in (by["Old Engineer"]["reason"] or "")
    assert r["after_filter"] == 1


# ── run() save + dedup + filters ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_saves_dedups_and_filters(monkeypatch, test_db):
    search = Search(name="t", search_mode="caribbeanjobs", search_term="engineer",
                    results_wanted=10, title_exclude_keywords=["intern"], company_exclude=[])
    test_db.add(search)
    test_db.commit()

    _patch_fetch(monkeypatch, [
        _job("Backend Engineer", "Acme", "https://cj/1"),
        _job("Backend Engineer", "Acme", "https://cj/1"),   # duplicate url
        _job("Data Intern", "Acme", "https://cj/2"),         # excluded by title
    ])

    async def noop_analyze(job, db=None, h1b_median=None, arrangement=None):
        pass
    monkeypatch.setattr(caribbeanjobs, "analyze_inline", noop_analyze)
    monkeypatch.setattr("backend.activity.log_activity", lambda *a, **k: None)

    res = await caribbeanjobs.run(search)
    assert res["error"] is None
    assert res["new_jobs"] == 1

    test_db.expire_all()
    saved = test_db.query(Job).all()
    assert len(saved) == 1
    assert saved[0].source == "caribbeanjobs"
    assert saved[0].title == "Backend Engineer"


@pytest.mark.asyncio
async def test_run_skips_body_excluded_and_expired_jobs(monkeypatch, test_db):
    search = Search(name="t", search_mode="caribbeanjobs", results_wanted=10,
                    search_term="engineer", title_exclude_keywords=[], company_exclude=[])
    test_db.add(search)
    test_db.commit()

    _patch_fetch(monkeypatch, [
        _job("Clean Role", "Acme", "https://cj/1"),
        _job("Citizens Only Role", "Acme", "https://cj/2", desc="must be a citizen"),
        _job("Expired Role", "Acme", "https://cj/3", expired=True),
    ])

    async def analyze(job, db=None, h1b_median=None, arrangement=None):
        if "citizen" in (job.description or "").lower():
            job.h1b_jd_flag = True
    monkeypatch.setattr(caribbeanjobs, "analyze_inline", analyze)
    monkeypatch.setattr("backend.activity.log_activity", lambda *a, **k: None)

    res = await caribbeanjobs.run(search)
    assert res["new_jobs"] == 1

    test_db.expire_all()
    assert [j.title for j in test_db.query(Job).all()] == ["Clean Role"]


@pytest.mark.asyncio
async def test_run_reports_a_seen_count_for_an_already_stored_job(monkeypatch, test_db):
    """A re-run of an already-imported search must not read as "0 seen": jobs_found is the
    pre-dedup count (like freehire), so the run summary and the health flag stay honest."""
    search = Search(name="t", search_mode="caribbeanjobs", results_wanted=10,
                    search_term="engineer", title_exclude_keywords=[], company_exclude=[])
    test_db.add(search)
    test_db.commit()

    _patch_fetch(monkeypatch, [_job("Fixed Role", "Acme", "https://cj/1")])

    async def noop(job, db=None, h1b_median=None, arrangement=None):
        pass
    monkeypatch.setattr(caribbeanjobs, "analyze_inline", noop)
    monkeypatch.setattr("backend.activity.log_activity", lambda *a, **k: None)

    first = await caribbeanjobs.run(search)
    assert first["jobs_found"] == 1 and first["new_jobs"] == 1

    second = await caribbeanjobs.run(search)
    assert second["new_jobs"] == 0
    assert second["jobs_found"] == 1   # seen before dedup, not 0


@pytest.mark.asyncio
async def test_run_stores_a_detail_salary_as_posting(monkeypatch, test_db):
    search = Search(name="t", search_mode="caribbeanjobs", results_wanted=10,
                    search_term="engineer", title_exclude_keywords=[], company_exclude=[])
    test_db.add(search)
    test_db.commit()

    listing = _job("Paid Role", "Acme", "https://cj/1")
    details = {"https://cj/1": {**listing, "salary_min": 85000, "salary_max": 95000}}
    _patch_fetch(monkeypatch, [listing], details=details)

    async def noop_analyze(job, db=None, h1b_median=None, arrangement=None):
        pass
    monkeypatch.setattr(caribbeanjobs, "analyze_inline", noop_analyze)
    monkeypatch.setattr("backend.activity.log_activity", lambda *a, **k: None)

    await caribbeanjobs.run(search)
    test_db.expire_all()
    row = test_db.query(Job).filter(Job.title == "Paid Role").first()
    assert row.salary_min == 85000 and row.salary_max == 95000
    assert row.salary_source == "posting"
