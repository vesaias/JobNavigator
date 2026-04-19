"""Tests for sources/company_pages.py — ATS dispatch logic."""
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_dispatch_routes_workday_url(monkeypatch):
    """Workday URL calls ats.workday.scrape, not any other ATS."""
    called = {"which": None}

    async def fake_workday(url, **kw):
        called["which"] = "workday"
        return []

    async def fake_greenhouse(url, **kw):
        called["which"] = "greenhouse"
        return []

    monkeypatch.setattr("backend.scraper.ats.workday.scrape", fake_workday)
    monkeypatch.setattr("backend.scraper.ats.greenhouse.scrape", fake_greenhouse)

    from backend.scraper.sources.company_pages import _dispatch_ats
    await _dispatch_ats("https://nvidia.wd5.myworkdayjobs.com/Site")
    assert called["which"] == "workday"


@pytest.mark.asyncio
async def test_dispatch_routes_greenhouse_url(monkeypatch):
    called = {"which": None}

    async def fake_greenhouse(url, **kw):
        called["which"] = "greenhouse"
        return []

    monkeypatch.setattr("backend.scraper.ats.greenhouse.scrape", fake_greenhouse)

    from backend.scraper.sources.company_pages import _dispatch_ats
    await _dispatch_ats("https://boards.greenhouse.io/acme")
    assert called["which"] == "greenhouse"


@pytest.mark.asyncio
async def test_dispatch_routes_lever_url(monkeypatch):
    called = {"which": None}
    async def fake_lever(url, **kw):
        called["which"] = "lever"; return []
    monkeypatch.setattr("backend.scraper.ats.lever.scrape", fake_lever)

    from backend.scraper.sources.company_pages import _dispatch_ats
    await _dispatch_ats("https://jobs.lever.co/acme")
    assert called["which"] == "lever"


@pytest.mark.asyncio
async def test_dispatch_routes_ashby_url(monkeypatch):
    called = {"which": None}
    async def fake_ashby(url, **kw):
        called["which"] = "ashby"; return []
    monkeypatch.setattr("backend.scraper.ats.ashby.scrape", fake_ashby)

    from backend.scraper.sources.company_pages import _dispatch_ats
    await _dispatch_ats("https://jobs.ashbyhq.com/acme")
    assert called["which"] == "ashby"


@pytest.mark.asyncio
async def test_dispatch_routes_rippling_url(monkeypatch):
    called = {"which": None}
    async def fake_rippling(url, **kw):
        called["which"] = "rippling"; return []
    monkeypatch.setattr("backend.scraper.ats.rippling.scrape", fake_rippling)

    from backend.scraper.sources.company_pages import _dispatch_ats
    await _dispatch_ats("https://ats.rippling.com/acme/jobs")
    assert called["which"] == "rippling"


@pytest.mark.asyncio
async def test_dispatch_falls_back_to_generic(monkeypatch):
    """Unknown career-page URL falls through to ats.generic.scrape."""
    called = {"which": None}

    async def fake_generic(url, **kw):
        called["which"] = "generic"
        return []

    # Also mock all specific ATS to return False detection
    monkeypatch.setattr("backend.scraper.ats.generic.scrape", fake_generic)

    from backend.scraper.sources.company_pages import _dispatch_ats
    await _dispatch_ats("https://unknown-ats-vendor.example.com/careers")
    assert called["which"] == "generic"


def test_company_pages_module_exports():
    """Module re-exports the 3 orchestrator functions."""
    from backend.scraper.sources import company_pages
    assert hasattr(company_pages, "scrape_single_career_page")
    assert hasattr(company_pages, "scrape_career_pages")
    assert hasattr(company_pages, "scrape_url_mode")
    assert hasattr(company_pages, "_dispatch_ats")
