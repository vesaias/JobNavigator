"""Tests for orchestrator.py — entry-point dispatch."""
import pytest
from unittest.mock import AsyncMock, MagicMock


def test_orchestrator_exposes_run_all():
    from backend.scraper import orchestrator
    assert hasattr(orchestrator, "run_all")


def test_orchestrator_exposes_run_search():
    from backend.scraper import orchestrator
    assert hasattr(orchestrator, "run_search")


def test_orchestrator_exposes_run_company():
    from backend.scraper import orchestrator
    assert hasattr(orchestrator, "run_company")


@pytest.mark.asyncio
async def test_run_search_dispatches_keyword(monkeypatch):
    """search_mode='keyword' routes to sources.jobspy."""
    called = {"src": None}

    async def fake_jobspy(search, proxy_url=None):
        called["src"] = "jobspy"
        return {"jobs_found": 0, "new_jobs": 0, "error": None, "duration": 0}

    monkeypatch.setattr("backend.scraper.sources.jobspy.run", fake_jobspy)

    class FakeSearch:
        id = "s-1"
        search_mode = "keyword"

    from backend.scraper.orchestrator import run_search
    await run_search(FakeSearch())
    assert called["src"] == "jobspy"


@pytest.mark.asyncio
async def test_run_search_dispatches_url_mode(monkeypatch):
    called = {"src": None}
    async def fake_url(search):
        called["src"] = "url"; return {}
    monkeypatch.setattr("backend.scraper.sources.company_pages.scrape_url_mode", fake_url)

    class FakeSearch:
        id = "s-1"; search_mode = "url"

    from backend.scraper.orchestrator import run_search
    await run_search(FakeSearch())
    assert called["src"] == "url"


@pytest.mark.asyncio
async def test_run_search_dispatches_levelsfyi(monkeypatch):
    called = {"src": None}
    async def fake_levels(search):
        called["src"] = "levels_fyi"; return {}
    monkeypatch.setattr("backend.scraper.sources.levelsfyi.run", fake_levels)

    class FakeSearch:
        id = "s-1"; search_mode = "levels_fyi"

    from backend.scraper.orchestrator import run_search
    await run_search(FakeSearch())
    assert called["src"] == "levels_fyi"


@pytest.mark.asyncio
async def test_run_search_dispatches_linkedin_personal(monkeypatch):
    called = {"src": None}
    async def fake_li(search):
        called["src"] = "linkedin_personal"; return {}
    monkeypatch.setattr("backend.scraper.sources.linkedin_personal.run", fake_li)

    class FakeSearch:
        id = "s-1"; search_mode = "linkedin_personal"

    from backend.scraper.orchestrator import run_search
    await run_search(FakeSearch())
    assert called["src"] == "linkedin_personal"


@pytest.mark.asyncio
async def test_run_search_dispatches_jobright(monkeypatch):
    called = {"src": None}
    async def fake_jr(search):
        called["src"] = "jobright"; return {}
    monkeypatch.setattr("backend.scraper.sources.jobright.run", fake_jr)

    class FakeSearch:
        id = "s-1"; search_mode = "jobright"

    from backend.scraper.orchestrator import run_search
    await run_search(FakeSearch())
    assert called["src"] == "jobright"


@pytest.mark.asyncio
async def test_run_search_linkedin_extension_is_noop(monkeypatch):
    """linkedin_extension has no scraper — jobs arrive via POST /api/jobs/linkedin-import."""
    class FakeSearch:
        id = "s-1"; search_mode = "linkedin_extension"

    from backend.scraper.orchestrator import run_search
    result = await run_search(FakeSearch())
    # Should return without raising; result should indicate no scrape happened
    assert result is not None
    assert result.get("jobs_found", 0) == 0


@pytest.mark.asyncio
async def test_run_search_raises_on_unknown_mode():
    class FakeSearch:
        id = "s-1"; search_mode = "unknown_mode"

    from backend.scraper.orchestrator import run_search
    with pytest.raises(ValueError):
        await run_search(FakeSearch())


@pytest.mark.asyncio
async def test_run_company_delegates_to_company_pages(monkeypatch):
    called = {"name": None}

    async def fake_scrape(company, shared_browser=None):
        called["name"] = company.name
        return {"jobs_found": 0, "new_jobs": 0}

    monkeypatch.setattr(
        "backend.scraper.sources.company_pages.scrape_single_career_page",
        fake_scrape,
    )

    class FakeCompany:
        name = "Acme"
        scrape_urls = ["https://x.com"]

    from backend.scraper.orchestrator import run_company
    await run_company(FakeCompany())
    assert called["name"] == "Acme"
