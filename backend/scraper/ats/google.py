"""Google Careers scraper (Playwright DOM).

Detection: substring check on "google.com/about/careers" (NOTE: lenient — a URL with
that substring anywhere, including in query strings, matches. Kept verbatim from
original production code).
Public interface: is_google(url), scrape(url, browser=None, debug=False).

Job cards are <li class="lLd3Je"> with <h3 class="QJPWVe"> for titles
and <a href="jobs/results/{id}-slug"> for links.
Pagination via <a aria-label="Go to next page">.
"""
import asyncio
import logging

from backend.scraper._shared.browser import _get_browser, _new_page, _close_page
from backend.scraper._shared.filters import _validate_job

logger = logging.getLogger("jobnavigator.scraper.ats.google")


def is_google(url: str) -> bool:
    """Check if URL is a Google Careers job search page."""
    return "google.com/about/careers" in url.lower()


async def scrape(url: str, browser=None, max_pages: int | None = None, debug: bool = False) -> list[dict] | tuple:
    """Scrape Google Careers using Playwright DOM extraction.

    Job cards are <li class="lLd3Je"> with <h3 class="QJPWVe"> for titles
    and <a href="jobs/results/{id}-slug"> for links.
    Pagination via <a aria-label="Go to next page">.

    `max_pages` caps how many result pages to walk. None preserves the
    historical 50-page safety limit; pass a positive int (typically the
    Company.max_pages setting) to honour the operator's pagination budget.
    """
    page_cap = max_pages if (max_pages is not None and max_pages > 0) else 50
    own_browser = browser is None
    pw = None
    if own_browser:
        pw, browser = await _get_browser()

    jobs = []
    rejected = []
    page = None
    try:
        page = await _new_page(browser)
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)

        # Wait for job card links to render
        try:
            await page.wait_for_selector("a[href*='jobs/results/']", timeout=15000)
        except Exception:
            logger.warning("Google Careers: job link selector timed out")
            await asyncio.sleep(5)
        await asyncio.sleep(2)

        # Dismiss cookie consent if present
        try:
            consent = page.locator('button:has-text("Accept all")')
            if await consent.count() > 0:
                await consent.first.click(timeout=3000)
                await asyncio.sleep(0.5)
        except Exception:
            pass

        # Paginate through all pages
        seen_ids = set()
        page_num = 0
        while page_num < page_cap:
            page_num += 1
            links = await page.query_selector_all("a[href*='jobs/results/']")
            page_count = 0

            for link in links:
                href = await link.get_attribute("href") or ""
                if not href:
                    continue

                # Extract job ID from path
                # href: jobs/results/141618563805782726-product-manager-i-geo?...
                path_part = href.split("jobs/results/")[-1].split("?")[0]
                job_id = path_part.split("-")[0] if path_part else ""
                if not job_id or job_id in seen_ids:
                    continue
                seen_ids.add(job_id)
                page_count += 1

                # Title from <h3> in the parent card (h3 is a sibling, not inside <a>)
                h3_handle = await link.evaluate_handle("el => (el.closest('li') || el.parentElement).querySelector('h3')")
                title = (await h3_handle.evaluate("el => el ? el.innerText : ''")).strip()

                # Build canonical URL
                job_url = f"https://www.google.com/about/careers/applications/jobs/results/{path_part}"

                reason = _validate_job(title, job_url)
                if reason is None:
                    jobs.append({"title": title, "url": job_url})
                elif debug:
                    rejected.append({"title": title, "url": job_url, "selector": "google_careers", "reason": reason})

            logger.info(f"Google Careers: page {page_num} — {page_count} new jobs")

            # Click next page
            next_link = page.locator("a[aria-label='Go to next page']")
            if await next_link.count() == 0:
                break
            try:
                await next_link.click(timeout=5000)
                await asyncio.sleep(2)
                await page.wait_for_selector("li.lLd3Je", timeout=10000)
            except Exception:
                break

    except Exception as e:
        logger.error(f"Google Careers scraper error: {e}")
        if debug:
            rejected.append({"title": "(error)", "url": url, "selector": "google_careers", "reason": str(e)})
    finally:
        if page:
            await _close_page(page)
        if own_browser:
            if browser:
                await browser.close()
            if pw:
                await pw.stop()

    logger.info(f"Google Careers: {len(jobs)} jobs extracted, {len(rejected)} rejected")
    if debug:
        return jobs, rejected
    return jobs
