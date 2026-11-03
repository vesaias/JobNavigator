"""Generic career-page scraper (issue #48): a job title in a card's own <header> (ReliefWeb),
ICMPD's job rows and Drupal vacancy cards (EEAS) are found, the page's own header and footer
links still are not, and a cookie page is not a job. Runs a real Chromium page; skipped where
Playwright has no browser (CI)."""
import pytest
import pytest_asyncio

from backend.scraper._shared.filters import _validate_job
from backend.scraper.ats import generic

BASE = "https://careers.example.org/jobs"

RELIEFWEB = """
<header><a href="/job/1/home-banner">Humanitarian jobs home page link</a></header>
<main>
  <article class="rw-river-article--job"><header><h3><a href="/job/4100/field-coordinator">Field Monitoring Coordinator</a></h3></header></article>
  <article class="rw-river-article--job"><header><h3><a href="/job/4101/wash-officer">Water and Sanitation Officer</a></h3></header></article>
</main>
<footer><a href="/job/2/footer-link">Footer link to all the jobs</a></footer>
"""

ICMPD = """
<div class="jobs-item"><h6 class="title"><a href="/Home/JobOpeningDetails?jobOpeningId=1227">Junior Project Officer (LP1)</a></h6></div>
<div class="jobs-item"><h6 class="title"><a href="/Home/JobOpeningDetails?jobOpeningId=1228">Migration Research Coordinator</a></h6></div>
"""

EEAS = """
<div class="node node--type-vacancy"><div class="card"><h3 class="card-title"><a href="/delegations/kazakhstan/project-officer_en">Project Officer in Astana Delegation</a></h3></div></div>
<div class="node node--type-vacancy"><div class="card"><h3 class="card-title"><a href="/eeas/eulex-kosovo-call_en">EULEX Kosovo Call for Contributions</a></h3></div></div>
"""


@pytest_asyncio.fixture
async def page():
    pw = None
    try:
        from playwright.async_api import async_playwright
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=True)
    except Exception as e:   # no browser installed (CI)
        if pw is not None:
            await pw.stop()
        pytest.skip(f"no Chromium: {type(e).__name__}")
    pg = await browser.new_page()
    yield pg
    await browser.close()
    await pw.stop()


async def _titles(page, html):
    await page.set_content(f"<html><body>{html}</body></html>")
    return sorted(j["title"] for j in await generic._extract_job_links_from_page(page, BASE))


@pytest.mark.asyncio
async def test_a_title_in_a_cards_header_is_found_and_the_page_header_is_not(page):
    assert await _titles(page, RELIEFWEB) == ["Field Monitoring Coordinator", "Water and Sanitation Officer"]


@pytest.mark.asyncio
async def test_icmpd_job_rows_are_found(page):
    assert await _titles(page, ICMPD) == ["Junior Project Officer (LP1)", "Migration Research Coordinator"]


@pytest.mark.asyncio
async def test_drupal_vacancy_cards_are_found(page):
    assert await _titles(page, EEAS) == ["EULEX Kosovo Call for Contributions", "Project Officer in Astana Delegation"]


@pytest.mark.parametrize("title", ["How we use cookies", "Cookie policy", "Cookie notice for applicants"])
def test_a_cookie_page_is_not_a_job(title):
    assert _validate_job(title, "https://talent.ecb.europa.eu/careers/CookieSettings") is not None
