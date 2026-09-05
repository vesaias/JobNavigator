"""freehire orchestrator wiring + preview/run pipeline (no network); uses the shared `test_db` fixture, which rebinds the module-level SessionLocal so run()'s internal session hits the test DB."""
import json
import pytest

from backend.models.db import Setting, Search, Job


def _job(title, company, url, desc="Great role", slug="s"):
    return {"title": title, "company": company, "url": url, "location": "US",
            "description": desc, "posted": None, "public_slug": slug,
            "seniority": None, "employment_type": None}


# ── orchestrator wiring ─────────────────────────────────────────────────────

def test_validity_requires_url_or_term():
    from backend.scraper import orchestrator
    assert orchestrator._search_mode_is_valid(Search(search_mode="freehire", search_term="go")) is True
    assert orchestrator._search_mode_is_valid(Search(search_mode="freehire", direct_url="https://freehire.me/?x=1")) is True
    assert orchestrator._search_mode_is_valid(Search(search_mode="freehire")) is False


def test_source_label():
    from backend.scraper import orchestrator
    assert orchestrator._source_for_search(Search(search_mode="freehire")) == "freehire"


@pytest.mark.asyncio
async def test_dispatch_routes_to_freehire(monkeypatch):
    from backend.scraper import orchestrator
    import backend.scraper.sources.freehire as fh
    called = {}

    async def fake_run(search, **kw):
        called["ok"] = True
        return {"jobs_found": 0, "new_jobs": 0, "error": None, "duration": 0}

    monkeypatch.setattr(fh, "run", fake_run)
    await orchestrator.run_search(Search(search_mode="freehire", search_term="go"))
    assert called.get("ok") is True


# ── preview() filtering ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_preview_applies_title_and_body_filters(monkeypatch, test_db):
    test_db.add(Setting(key="body_exclusion_phrases", value=json.dumps(["us citizen only"])))
    test_db.commit()
    import backend.scraper.sources.freehire as fh

    jobs = [
        _job("Backend Engineer", "Acme", "https://a/1", desc="Great backend role", slug="s1"),
        _job("Data Intern", "Acme", "https://a/2", desc="entry role", slug="s2"),
        _job("Senior Engineer", "BadCo", "https://a/3", desc="US citizen only please", slug="s3"),
    ]

    async def fake_collect(_search):
        return jobs
    monkeypatch.setattr(fh, "_collect", fake_collect)

    search = Search(name="t", search_mode="freehire", search_term="engineer",
                    title_exclude_keywords=["intern"], company_exclude=[])
    r = await fh.preview(search, test_db)

    assert r["raw_count"] == 3
    by = {j["title"]: j for j in r["jobs"]}
    assert by["Backend Engineer"]["kept"] is True
    assert by["Data Intern"]["kept"] is False and "intern" in (by["Data Intern"]["reason"] or "").lower()
    assert by["Senior Engineer"]["kept"] is False and "Body exclusion" in (by["Senior Engineer"]["reason"] or "")
    assert r["after_filter"] == 1


# ── run() save + dedup + title filter ───────────────────────────────────────

@pytest.mark.asyncio
async def test_run_saves_dedups_and_filters(monkeypatch, test_db):
    search = Search(name="t", search_mode="freehire", search_term="engineer",
                    results_wanted=10, title_exclude_keywords=["intern"], company_exclude=[])
    test_db.add(search)
    test_db.commit()

    import backend.scraper.sources.freehire as fh

    async def fake_collect(_search):
        return [
            _job("Backend Engineer", "Acme", "https://a/1", slug="s1"),
            _job("Backend Engineer", "Acme", "https://a/1", slug="s1"),  # duplicate url
            _job("Data Intern", "Acme", "https://a/2", slug="s2"),        # excluded by title
        ]
    monkeypatch.setattr(fh, "_collect", fake_collect)

    async def noop_analyze(job, db=None, h1b_median=None):
        pass
    monkeypatch.setattr(fh, "analyze_inline", noop_analyze)
    monkeypatch.setattr("backend.activity.log_activity", lambda *a, **k: None)

    res = await fh.run(search)
    assert res["error"] is None
    assert res["new_jobs"] == 1  # dup url deduped, intern filtered

    test_db.expire_all()
    saved = test_db.query(Job).all()
    assert len(saved) == 1
    assert saved[0].source == "freehire"
    assert saved[0].title == "Backend Engineer"


@pytest.mark.asyncio
async def test_run_skips_body_excluded_jobs(monkeypatch, test_db):
    search = Search(name="t", search_mode="freehire", results_wanted=10,
                    search_term="engineer", title_exclude_keywords=[], company_exclude=[])
    test_db.add(search)
    test_db.commit()

    import backend.scraper.sources.freehire as fh

    async def fake_collect(_search):
        return [
            _job("Clean Role", "Acme", "https://a/1", slug="s1"),
            _job("Citizens Only Role", "Acme", "https://a/2", desc="must be a citizen", slug="s2"),
        ]
    monkeypatch.setattr(fh, "_collect", fake_collect)

    async def analyze(job, db=None, h1b_median=None):
        if "citizen" in (job.description or "").lower():
            job.h1b_jd_flag = True  # simulate body-exclusion match
    monkeypatch.setattr(fh, "analyze_inline", analyze)
    monkeypatch.setattr("backend.activity.log_activity", lambda *a, **k: None)

    res = await fh.run(search)
    assert res["new_jobs"] == 1  # the citizen-flagged job is skipped

    test_db.expire_all()
    titles = [j.title for j in test_db.query(Job).all()]
    assert titles == ["Clean Role"]


@pytest.mark.asyncio
async def test_run_applies_annual_salary_only(monkeypatch, test_db):
    search = Search(name="t", search_mode="freehire", results_wanted=10,
                    search_term="e", title_exclude_keywords=[], company_exclude=[])
    test_db.add(search)
    test_db.commit()

    import backend.scraper.sources.freehire as fh

    def with_sal(title, url, smin, smax, period):
        j = _job(title, "Acme", url, slug=url)
        j.update(salary_min=smin, salary_max=smax, salary_currency="USD", salary_period=period)
        return j

    async def fake_collect(_search):
        return [with_sal("Yearly", "https://a/1", 150000, 200000, "year"),
                with_sal("Monthly", "https://a/2", 9000, 11000, "month")]
    monkeypatch.setattr(fh, "_collect", fake_collect)

    async def noop(job, db=None, h1b_median=None):
        pass
    monkeypatch.setattr(fh, "analyze_inline", noop)
    monkeypatch.setattr("backend.activity.log_activity", lambda *a, **k: None)

    await fh.run(search)
    test_db.expire_all()
    rows = {j.title: j for j in test_db.query(Job).all()}
    assert rows["Yearly"].salary_min == 150000 and rows["Yearly"].salary_max == 200000
    assert rows["Yearly"].salary_source == "posting"
    assert rows["Monthly"].salary_min is None  # month period not stored as annual
