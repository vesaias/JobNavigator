"""Pin that Playwright-based ATS scrapers (Google, Meta) honour max_pages.

The actual scrape coroutine launches a real browser, which is too heavy for
unit tests. Instead we verify:
  1. Both signatures accept `max_pages`
  2. The pagination guard reads from `max_pages` (not the legacy hardcoded
     constants 50 / 20) — guarded via static source inspection
  3. _dispatch_ats forwards `max_pages` to google + meta scrapers
"""
import inspect
import re

from backend.scraper.ats import google as google_ats
from backend.scraper.ats import meta as meta_ats
from backend.scraper.sources import company_pages


def _signature_accepts(fn, kwarg: str) -> bool:
    return kwarg in inspect.signature(fn).parameters


def test_google_scrape_accepts_max_pages():
    assert _signature_accepts(google_ats.scrape, "max_pages")


def test_meta_scrape_accepts_max_pages():
    assert _signature_accepts(meta_ats.scrape, "max_pages")


def test_dispatch_ats_accepts_max_pages():
    assert _signature_accepts(company_pages._dispatch_ats, "max_pages")


def test_google_pagination_uses_max_pages_not_hardcoded_50():
    """Source must reference page_cap or max_pages in the while-guard, not literal 50."""
    src = inspect.getsource(google_ats.scrape)
    assert "while page_num < 50" not in src, (
        "google.scrape still has the hardcoded 50-page cap — max_pages plumbing missing"
    )
    assert re.search(r"while\s+page_num\s*<\s*page_cap", src), (
        "google.scrape should guard pagination with `page_cap` derived from max_pages"
    )


def test_meta_pagination_uses_max_pages_not_hardcoded_20():
    """Source must reference page_cap or max_pages in the while-guard, not literal 20."""
    src = inspect.getsource(meta_ats.scrape)
    assert "while page_num < 20" not in src, (
        "meta.scrape still has the hardcoded 20-page cap — max_pages plumbing missing"
    )
    assert re.search(r"while\s+page_num\s*<\s*page_cap", src), (
        "meta.scrape should guard pagination with `page_cap` derived from max_pages"
    )


def test_dispatch_ats_forwards_max_pages_to_google_and_meta():
    """The dispatcher source must show `max_pages=max_pages` in the google + meta branches."""
    src = inspect.getsource(company_pages._dispatch_ats)
    # Both calls should pass max_pages= explicitly
    assert "google.scrape(url, browser=shared_browser, max_pages=max_pages" in src
    assert "meta.scrape(url, browser=shared_browser, max_pages=max_pages" in src
