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


EUAN = """
<ul><li class="ecl-list-item"><div class="ecl-content-block__title"><a href="/vacancy/euaa-2026-024_en">Head of Business Support Sector (AD 8)</a></div></li>
<li class="ecl-list-item"><div class="ecl-content-block__title"><a href="/vacancy/procurement-officer_en">Procurement Officer at the Agency</a></div></li></ul>
"""

COE = """
<div class="article"><div class="article__header__text__title"><a href="/en_GB/careersmarketplace/JobDetail/1101">Head of Resource Management Division</a></div></div>
<div class="article"><div class="article__header__text__title"><a href="/en_GB/careersmarketplace/JobDetail/1102">Occupational psychologist (A2)</a></div></div>
"""

# Each card links its posting twice: an image link with no text, then the titled link. The
# country facets would match the broad /jobs/ selector.
EUROBRUSSELS = """
<a href="/jobs/belgium">Belgium (49) jobs in this country</a>
<div class="job"><a href="/job_display/301/acme"><img src="logo.png"></a><a href="/job_display/301/acme">HR Operations Assistant</a></div>
<div class="job"><a href="/job_display/302/beta"><img src="logo.png"></a><a href="/job_display/302/beta">Policy Officer in Social Protection</a></div>
"""

# A text-less link frees its URL only within its own selector's list: a later selector must not
# turn another link to the same page (here an "about" link) into a job.
ICON_THEN_OTHER_LIST = """
<div class="job-card"><a href="/positions/77">Senior Data Engineer, Platform</a></div>
<div class="job-card"><a href="/about/hiring-team"><img src="team.png"></a></div>
<div role="listitem"><a href="/about/hiring-team">Meet our hiring team and process</a></div>
"""


@pytest.mark.asyncio
async def test_europa_component_library_lists_are_found(page):
    assert await _titles(page, EUAN) == ["Head of Business Support Sector (AD 8)", "Procurement Officer at the Agency"]


@pytest.mark.asyncio
async def test_careers_marketplace_jobs_are_found(page):
    assert await _titles(page, COE) == ["Head of Resource Management Division", "Occupational psychologist (A2)"]


@pytest.mark.asyncio
async def test_an_image_link_does_not_hide_the_titled_link_to_the_same_job(page):
    assert await _titles(page, EUROBRUSSELS) == ["HR Operations Assistant", "Policy Officer in Social Protection"]


@pytest.mark.asyncio
async def test_a_text_less_link_does_not_let_a_later_selector_add_its_url(page):
    assert await _titles(page, ICON_THEN_OTHER_LIST) == ["Senior Data Engineer, Platform"]
