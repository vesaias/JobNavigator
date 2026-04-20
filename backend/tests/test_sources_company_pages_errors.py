"""Regression: per-URL exceptions must bubble up to the caller's result['error']."""
import pytest
from unittest.mock import MagicMock


class FakeCompany:
    """Minimal company stub with the attributes scrape_single_career_page reads."""
    def __init__(self, urls):
        self.id = "c-1"
        self.name = "Acme"
        self.scrape_urls = urls
        self.last_scraped_at = None
        self.scrape_interval_minutes = None
        self.title_include_expr = ""
        self.title_exclude_keywords = []
        self.selected_cv_ids = []
        self.auto_scoring_depth = "off"


@pytest.mark.asyncio
async def test_scrape_single_career_page_reports_url_errors(monkeypatch):
    """When one URL in scrape_urls fails, result['error'] must NOT be None."""
    call_count = {"n": 0}

    async def fake_dispatch(url, **kw):
        call_count["n"] += 1
        if "fails" in url:
            raise RuntimeError("simulated scrape failure for broken URL")
        return []

    monkeypatch.setattr(
        "backend.scraper.sources.company_pages._dispatch_ats",
        fake_dispatch,
    )

    # Stub SessionLocal so the function can construct its own session cheaply
    monkeypatch.setattr(
        "backend.scraper.sources.company_pages.SessionLocal",
        lambda: MagicMock(),
    )

    # Use Lever URLs so _dispatch_ats is actually called (vs generic Playwright path)
    from backend.scraper.sources.company_pages import scrape_single_career_page
    company = FakeCompany([
        "https://jobs.lever.co/ok-company",
        "https://jobs.lever.co/fails-company",
    ])
    result = await scrape_single_career_page(company)

    # The key assertion: error is NOT None
    assert result.get("error") is not None, (
        f"Expected error field to contain URL failure details, got None. Full result: {result}"
    )
    # And it should mention the failing URL or the exception text
    err = str(result["error"]).lower()
    assert "fails-company" in err or "simulated" in err


@pytest.mark.asyncio
async def test_scrape_single_career_page_no_error_when_all_succeed(monkeypatch):
    """All URLs succeed → error is None (no false positives)."""
    async def fake_dispatch(url, **kw):
        return []

    monkeypatch.setattr(
        "backend.scraper.sources.company_pages._dispatch_ats",
        fake_dispatch,
    )
    monkeypatch.setattr(
        "backend.scraper.sources.company_pages.SessionLocal",
        lambda: MagicMock(),
    )

    # Use Lever URLs so _dispatch_ats is actually called (vs generic Playwright path)
    from backend.scraper.sources.company_pages import scrape_single_career_page
    company = FakeCompany([
        "https://jobs.lever.co/company-one",
        "https://jobs.lever.co/company-two",
    ])
    result = await scrape_single_career_page(company)

    assert result.get("error") is None, (
        f"Expected no error on all-success path, got: {result['error']}"
    )
