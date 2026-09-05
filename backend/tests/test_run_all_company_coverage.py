"""A manual run-all must cover every active company with scrape URLs: active+URLs is the whole gate (playwright_enabled is not consulted), force=True ignores per-company intervals, one company's failure does not end the batch, and the summary names every company that did not run with the reason."""
from datetime import datetime, timedelta, timezone

import pytest

from backend.models.db import Company, ScrapeLog


@pytest.fixture
def no_sleep(monkeypatch):
    """The batch paces itself with asyncio.sleep(2) between companies."""
    import backend.scraper.sources.company_pages as cp

    async def _instant(_seconds):
        return None

    monkeypatch.setattr(cp.asyncio, "sleep", _instant)


def _fake_scraper(monkeypatch, results=None, raises=()):
    """Stub scrape_single_career_page: no network, no browser."""
    import backend.scraper.sources.company_pages as cp
    seen = []

    async def fake(company, **kw):
        seen.append(company.name)
        if company.name in raises:
            raise RuntimeError("boom")
        return (results or {}).get(
            company.name, {"jobs_found": 1, "new_jobs": 0, "error": None, "duration": 0.1}
        )

    monkeypatch.setattr(cp, "scrape_single_career_page", fake)
    return seen


def _company(db, name, **kw):
    kw.setdefault("active", True)
    kw.setdefault("playwright_enabled", True)
    kw.setdefault("scrape_urls", [f"https://jobs.lever.co/{name.lower()}"])
    kw.setdefault("auto_scoring_depth", "off")
    c = Company(name=name, **kw)
    db.add(c)
    db.commit()
    return c


@pytest.mark.asyncio
async def test_manual_run_covers_companies_with_playwright_disabled(test_db, monkeypatch, no_sleep):
    from backend.scraper.sources.company_pages import scrape_career_pages

    _company(test_db, "Enabled")
    _company(test_db, "Anthropic", playwright_enabled=False)   # created by "applied"
    seen = _fake_scraper(monkeypatch)

    summary = await scrape_career_pages(force=True)

    assert sorted(seen) == ["Anthropic", "Enabled"]
    assert summary["scraped"] == 2 and summary["skipped"] == []
    assert {r.source for r in test_db.query(ScrapeLog).all()} == {
        "playwright_Enabled", "playwright_Anthropic",
    }


@pytest.mark.asyncio
async def test_manual_run_ignores_the_per_company_interval(test_db, monkeypatch, no_sleep):
    from backend.scraper.sources.company_pages import scrape_career_pages

    _company(test_db, "JustRan", scrape_interval_minutes=600,
             last_scraped_at=datetime.now(timezone.utc) - timedelta(minutes=5))
    seen = _fake_scraper(monkeypatch)

    summary = await scrape_career_pages(force=True)
    assert seen == ["JustRan"], "a manual run-all must not honour the interval"
    assert summary["skipped"] == []


@pytest.mark.asyncio
async def test_scheduled_run_still_honours_the_interval_and_says_so(test_db, monkeypatch, no_sleep):
    from backend.scraper.sources.company_pages import scrape_career_pages

    _company(test_db, "JustRan", scrape_interval_minutes=600,
             last_scraped_at=datetime.now(timezone.utc) - timedelta(minutes=5))
    _company(test_db, "Due", scrape_interval_minutes=10,
             last_scraped_at=datetime.now(timezone.utc) - timedelta(minutes=90))
    seen = _fake_scraper(monkeypatch)

    summary = await scrape_career_pages(force=False)
    assert seen == ["Due"]
    assert [s["name"] for s in summary["skipped"]] == ["JustRan"]
    assert summary["skipped"][0]["reason"].startswith("not due")


@pytest.mark.asyncio
async def test_one_company_failure_does_not_stop_the_others(test_db, monkeypatch, no_sleep):
    from backend.scraper.sources.company_pages import scrape_career_pages

    _company(test_db, "AAA")
    _company(test_db, "BBB")
    _company(test_db, "CCC")
    seen = _fake_scraper(monkeypatch, raises=("BBB",))

    summary = await scrape_career_pages(force=True)

    assert seen == ["AAA", "BBB", "CCC"], "the batch carried on past the failure"
    assert summary["failed"] == 1
    rows = {r.source: r for r in test_db.query(ScrapeLog).all()}
    assert set(rows) == {"playwright_AAA", "playwright_BBB", "playwright_CCC"}
    assert "boom" in (rows["playwright_BBB"].error or "")
    assert rows["playwright_AAA"].error is None


@pytest.mark.asyncio
async def test_summary_names_active_companies_without_urls(test_db, monkeypatch, no_sleep):
    from backend.scraper.sources.company_pages import scrape_career_pages

    _company(test_db, "HasUrls")
    _company(test_db, "NoUrls", scrape_urls=[])
    _company(test_db, "BlankUrl", scrape_urls=["  "])
    _company(test_db, "Paused", active=False)
    seen = _fake_scraper(monkeypatch)

    summary = await scrape_career_pages(force=True)

    assert seen == ["HasUrls"]
    assert sorted(s["name"] for s in summary["skipped"]) == ["BlankUrl", "NoUrls"]
    assert {s["reason"] for s in summary["skipped"]} == {"no scrape URLs"}
    # an inactive company is off on purpose — not a skip to report
    assert "Paused" not in [s["name"] for s in summary["skipped"]]


@pytest.mark.asyncio
async def test_run_all_hands_the_company_summary_up(test_db, monkeypatch, no_sleep):
    """POST /api/scrape/run-all builds its run summary from this."""
    import backend.scraper.orchestrator as orch

    _company(test_db, "NoUrls", scrape_urls=[])
    _fake_scraper(monkeypatch)

    out = await orch.run_all(force=True)
    assert [s["name"] for s in out["companies"]["skipped"]] == ["NoUrls"]
