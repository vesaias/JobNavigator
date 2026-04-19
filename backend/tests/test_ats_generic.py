"""Tests for ats/generic.py — DOM-fallback scraper for unknown career pages."""
import pytest


def test_generic_exposes_dom_helpers():
    """The 5 DOM helpers are reachable from ats.generic."""
    from backend.scraper.ats import generic
    assert hasattr(generic, "_setup_route_blocks")
    assert hasattr(generic, "_wait_for_content")
    assert hasattr(generic, "_extract_job_links_from_page")
    assert hasattr(generic, "_extract_all_pages")
    assert hasattr(generic, "_click_next_page")


def test_generic_exposes_scrape():
    """Public entry point matches other ATS modules' (is_match, scrape) interface."""
    from backend.scraper.ats import generic
    assert hasattr(generic, "scrape")


@pytest.mark.asyncio
async def test_generic_scrape_launches_browser_when_none(monkeypatch):
    """scrape() launches its own browser when none passed, and returns empty on no jobs."""
    from unittest.mock import AsyncMock, MagicMock

    mock_page = MagicMock()
    mock_page.goto = AsyncMock()
    mock_page.query_selector_all = AsyncMock(return_value=[])
    mock_page.evaluate = AsyncMock(return_value=None)
    mock_page.route = AsyncMock()
    mock_page.close = AsyncMock()
    mock_page._stealth_ctx = None

    mock_browser = MagicMock()
    mock_browser.new_context = AsyncMock(return_value=mock_browser)
    mock_browser.new_page = AsyncMock(return_value=mock_page)

    mock_pw = MagicMock()
    mock_pw.stop = AsyncMock()

    async def fake_get_browser():
        return mock_pw, mock_browser

    monkeypatch.setattr("backend.scraper.ats.generic._get_browser", fake_get_browser)

    async def fake_new_page(browser, viewport=None):
        return mock_page

    async def fake_close_page(page):
        pass

    monkeypatch.setattr("backend.scraper.ats.generic._new_page", fake_new_page)
    monkeypatch.setattr("backend.scraper.ats.generic._close_page", fake_close_page)

    from backend.scraper.ats.generic import scrape
    # Use a URL that matches no ATS (generic is the fallback)
    result = await scrape("https://unknown-career-page.example.com/jobs", max_pages=1)
    # Just verify it ran without crashing
    assert isinstance(result, (list, tuple))
