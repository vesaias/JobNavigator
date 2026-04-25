"""Meta Careers scraper (Playwright DOM).

Detection: hostname-based match on metacareers.com (strict, not substring).
Public interface: is_meta(url), scrape(url, browser=None, debug=False).

Meta renders job cards client-side via React. Each card is an <a> linking to
/profile/job_details/{job_id} with an <h3> for the title. URL query params
handle all filtering (roles, offices, teams) server-side.
Pagination via "next" button (aria-label='Button to select next week').
"""
import asyncio
import logging

from backend.scraper._shared.browser import _get_browser, _new_page, _close_page
from backend.scraper._shared.urls import host_matches
from backend.scraper._shared.filters import _validate_job

logger = logging.getLogger("jobnavigator.scraper.ats.meta")


def is_meta(url: str) -> bool:
    """Check if URL is a Meta Careers job search page."""
    return host_matches(url, "metacareers.com")


async def scrape(url: str, browser=None, max_pages: int | None = None, debug: bool = False) -> list[dict] | tuple:
    """Scrape Meta Careers using Playwright DOM extraction.

    Meta renders job cards client-side via React. Each card is an <a> linking to
    /profile/job_details/{job_id} with an <h3> for the title. URL query params
    handle all filtering (roles, offices, teams) server-side.
    Pagination via "next" button (aria-label='Button to select next week').

    `max_pages` caps how many result pages to walk. None preserves the
    historical 20-page safety limit; pass a positive int (typically the
    Company.max_pages setting) to honour the operator's pagination budget.
    """
    page_cap = max_pages if (max_pages is not None and max_pages > 0) else 20
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

        # Wait for job cards to render
        try:
            await page.wait_for_selector('a[href*="/profile/job_details/"]', timeout=15000)
        except Exception:
            logger.warning("Meta: job card selector timed out, trying fallback wait")
            await asyncio.sleep(5)
        await asyncio.sleep(2)

        # Dismiss cookie banner via JS (overlay blocks normal clicks)
        await page.evaluate("""
            const btns = document.querySelectorAll('button');
            for (const b of btns) {
                if (b.textContent.includes('Accept All')) { b.click(); break; }
            }
        """)
        await asyncio.sleep(0.5)

        # Paginate through all pages
        seen_ids = set()
        page_num = 0
        while page_num < page_cap:
            page_num += 1
            links = await page.query_selector_all('a[href*="/profile/job_details/"]')
            page_count = 0

            for link in links:
                href = await link.get_attribute("href") or ""
                job_id = href.split("/profile/job_details/")[-1].rstrip("/").split("?")[0]
                if not job_id or job_id in seen_ids:
                    continue
                seen_ids.add(job_id)
                page_count += 1

                h3 = await link.query_selector("h3")
                title = (await h3.inner_text()).strip() if h3 else ""
                job_url = f"https://www.metacareers.com/v2/jobs/{job_id}/"

                reason = _validate_job(title, job_url)
                if reason is None:
                    jobs.append({"title": title, "url": job_url})
                elif debug:
                    rejected.append({"title": title, "url": job_url, "selector": "meta_careers", "reason": reason})

            logger.info(f"Meta: page {page_num} — {page_count} new jobs")

            # Click next page button via JS (avoids overlay interception)
            next_btn = page.locator("[aria-label='Button to select next week']")
            if await next_btn.count() == 0:
                break
            disabled = await next_btn.get_attribute("aria-disabled")
            if disabled == "true":
                break
            await next_btn.evaluate("el => el.click()")
            await asyncio.sleep(2)
            try:
                await page.wait_for_selector('a[href*="/profile/job_details/"]', timeout=10000)
            except Exception:
                pass

    except Exception as e:
        logger.error(f"Meta scraper error: {e}")
        if debug:
            rejected.append({"title": "(error)", "url": url, "selector": "meta_careers", "reason": str(e)})
    finally:
        if page:
            await _close_page(page)
        if own_browser:
            if browser:
                await browser.close()
            if pw:
                await pw.stop()

    logger.info(f"Meta: {len(jobs)} jobs extracted, {len(rejected)} rejected")
    if debug:
        return jobs, rejected
    return jobs
