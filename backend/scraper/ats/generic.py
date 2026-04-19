"""Generic CSS-selector fallback for career pages with no ATS match.

Launches a headless browser, extracts links matching common job-card selectors
(anchor tags with job-ish attributes, job title classes, etc.), paginates as
far as possible, and returns a list of {title, url} dicts filtered through
_validate_job.
"""
import asyncio
import logging
import re
from urllib.parse import urlparse

from backend.scraper._shared.browser import _get_browser, _new_page, _close_page
from backend.scraper._shared.filters import _validate_job

logger = logging.getLogger("jobnavigator.scraper.ats.generic")


# ── Route blocking ───────────────────────────────────────────────────────────

async def _setup_route_blocks(page):
    """Block unwanted endpoints (e.g. eightfold similar_positions widget)."""
    async def _block_handler(route):
        logger.info(f"Blocked request: {route.request.url}")
        await route.abort()
    await page.route(re.compile(r"similar_positions"), _block_handler)


# ── Wait for content ──────────────────────────────────────────────────────────

async def _wait_for_content(page, wait_for_selector: str = None):
    """Wait for page content to render. Uses custom selector if provided, else 3s delay."""
    if wait_for_selector and wait_for_selector.strip():
        try:
            await page.wait_for_selector(wait_for_selector.strip(), timeout=15000)
            await asyncio.sleep(1)  # Extra moment for JS to finish
        except Exception as e:
            logger.warning(f"wait_for_selector '{wait_for_selector}' timed out: {e}")
            await asyncio.sleep(3)  # Fallback
    else:
        await asyncio.sleep(3)


# ── Extract job links from current page ───────────────────────────────────────

async def _extract_job_links_from_page(page, base_url: str, debug: bool = False) -> list[dict]:
    """Extract and validate job links from the currently loaded page.

    If debug=True, returns ALL found links with validation status/reason.
    """
    jobs_by_url = {}      # URL -> job dict (valid jobs)
    rejected = []         # debug: rejected entries

    # Specific selectors first — if these find results, skip the broad ones
    specific_selectors = [
        '[class*="position-card"] a', '[class*="position-title"] a',
        '[data-automation-id="jobTitle"]',
        '.job-listing a', '.job-card a', '.opening a',
        '[data-job] a', '.career-listing a', '[role="listitem"] a',
        'a.js-view-job',
    ]
    # Broad URL-pattern selectors — only used as fallback
    broad_selectors = [
        'a[href*="/jobs/"]', 'a[href*="/job/"]',
        'a[href*="/position"]', 'a[href*="/opening"]', 'a[href*="/role"]',
        'a[href*="/viewjob"]', 'a[href*="/requisition"]',
        'a[href*="eightfold.ai/careers"]',
        'a[href*="/careers/"]',
    ]

    base_parsed = urlparse(base_url)
    seen_hrefs = set()  # track all hrefs we've checked (valid or not)

    # Remove footer/header from DOM to avoid extracting garbage links
    # (keep <nav> — pagination buttons may live inside it)
    await page.evaluate("""
        for (const tag of ['footer', 'header']) {
            document.querySelectorAll(tag).forEach(el => el.remove());
        }
    """)

    async def _run_selectors(selectors):
        for selector in selectors:
            try:
                elements = await page.query_selector_all(selector)
                for el in elements:
                    href = await el.get_attribute("href")
                    if not href:
                        continue

                    if href.startswith("/"):
                        href = f"{base_parsed.scheme}://{base_parsed.netloc}{href}"
                    elif not href.startswith("http"):
                        continue

                    # Skip entirely if we've already processed this href
                    if href in seen_hrefs:
                        continue
                    seen_hrefs.add(href)

                    # Try to get title from a heading element inside the <a>
                    text = None
                    for heading_sel in ('[class*="heading"]', '[class*="title"]', 'h2', 'h3', 'h4'):
                        heading_el = await el.query_selector(heading_sel)
                        if heading_el:
                            text = (await heading_el.inner_text() or "").strip()
                            if text:
                                break
                    if not text:
                        text = (await el.inner_text() or "").strip()
                    if '\n' in text:
                        lines = [l.strip() for l in text.split('\n') if l.strip()]
                        text = lines[0] if lines else ""

                    if not text:
                        if debug:
                            rejected.append({"title": "(empty)", "url": href, "selector": selector, "reason": "No text"})
                        continue

                    reason = _validate_job(text, href)
                    if reason is None:
                        jobs_by_url[href] = {"title": text, "url": href}
                    elif debug:
                        rejected.append({"title": text, "url": href, "selector": selector, "reason": reason})
            except Exception:
                continue

    # Run specific selectors first
    await _run_selectors(specific_selectors)

    # Only fall back to broad selectors if specific ones found nothing
    if not jobs_by_url:
        await _run_selectors(broad_selectors)

    if debug:
        return list(jobs_by_url.values()), rejected
    return list(jobs_by_url.values())


# ── Pagination ────────────────────────────────────────────────────────────────

async def _extract_all_pages(page, base_url: str, max_pages: int = 5, debug: bool = False, wait_for_selector: str = None) -> list[dict] | tuple:
    """Extract jobs from current page, then paginate through next pages."""
    all_jobs = []
    all_rejected = []
    pagination_debug = []
    seen_urls = set()

    for page_num in range(max_pages):
        if debug:
            page_jobs, page_rejected = await _extract_job_links_from_page(page, base_url, debug=True)
            all_rejected.extend(page_rejected)
        else:
            page_jobs = await _extract_job_links_from_page(page, base_url)

        # Add only new jobs (not seen on previous pages)
        new_on_page = 0
        for j in page_jobs:
            if j["url"] not in seen_urls:
                seen_urls.add(j["url"])
                all_jobs.append(j)
                new_on_page += 1

        logger.info(f"Page {page_num + 1}: found {len(page_jobs)} links, {new_on_page} new")

        if page_num >= max_pages - 1:
            break

        # Stop if this page found no new jobs (we've exhausted results)
        if new_on_page == 0:
            break

        result = await _click_next_page(page, debug=debug)
        if debug:
            pagination_debug.append({"page": page_num + 1, **result})
            if not result["clicked"]:
                break
        else:
            if not result:
                break

        await asyncio.sleep(2)

    if debug:
        return all_jobs, all_rejected, pagination_debug
    return all_jobs


async def _click_next_page(page, debug: bool = False) -> bool | dict:
    """Try to click a next page or load more button.

    Returns True/False normally. When debug=True, returns a dict with details.
    """
    debug_info = {"clicked": False, "candidates": []}

    # Detect eightfold pages by checking for their CSS module classes in the DOM
    is_eightfold = await page.query_selector('[class*="pagination-module_pagination"]') is not None
    if is_eightfold:
        next_selectors = [
            'button[class*="pagination-module_pagination-next"]',
            'button[aria-label="Next jobs"]',
        ]
    else:
        next_selectors = [
            'button[aria-label*="next" i]',
            'a[aria-label*="next" i]',
            'button[aria-label*="Next" i]',
            'a[aria-label*="Next" i]',
            '[data-automation-id="lnkNextPage"]',
            '.pagination-next a',
            '.pagination a.next',
            'a.next-page',
            'button.next-page',
            'li.next a',
            'button[aria-label*="load more" i]',
            'button[aria-label*="Load more" i]',
            'button[aria-label*="Show more" i]',
        ]

    if debug:
        debug_info["is_eightfold"] = is_eightfold

    # Scroll to bottom to trigger lazy-loaded pagination
    try:
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(1)
    except Exception:
        pass

    for selector in next_selectors:
        try:
            btn = await page.query_selector(selector)
            if btn:
                is_visible = await btn.is_visible()
                is_disabled = await btn.get_attribute("disabled")
                aria_disabled = await btn.get_attribute("aria-disabled")
                tag = await btn.evaluate("el => el.tagName")
                text = await btn.evaluate("el => el.innerText.trim().substring(0, 80)")
                candidate = {
                    "selector": selector, "tag": tag, "text": text,
                    "visible": is_visible, "disabled": bool(is_disabled),
                    "aria_disabled": aria_disabled,
                }
                if debug:
                    debug_info["candidates"].append(candidate)
                if is_visible and not is_disabled and aria_disabled != "true":
                    logger.info(f"Pagination: clicking [{selector}] tag={tag} text='{text}'")
                    try:
                        await btn.click(timeout=5000)
                    except Exception as click_err:
                        logger.warning(f"Pagination: click failed ({click_err}), trying dispatch_event")
                        if debug:
                            candidate["click_error"] = str(click_err)
                        try:
                            await btn.dispatch_event("click")
                        except Exception as de_err:
                            logger.warning(f"Pagination: dispatch_event also failed ({de_err})")
                            if debug:
                                candidate["dispatch_error"] = str(de_err)
                            continue
                    if debug:
                        debug_info["clicked"] = True
                        debug_info["clicked_via"] = candidate
                        return debug_info
                    return True
        except Exception as e:
            logger.warning(f"Pagination: selector {selector} error: {e}")
            continue

    # Text-based fallback — skip for eightfold (avoids false positives)
    text_patterns = ["Next", "Load more", "Show more", "Load More", "Show More"] if not is_eightfold else []
    for text_pat in text_patterns:
        try:
            btn = await page.query_selector(f'button:has-text("{text_pat}")')
            if not btn:
                btn = await page.query_selector(f'a:has-text("{text_pat}")')
            if btn:
                is_visible = await btn.is_visible()
                is_disabled = await btn.get_attribute("disabled")
                tag = await btn.evaluate("el => el.tagName")
                btn_text = await btn.evaluate("el => el.innerText.trim().substring(0, 80)")
                candidate = {
                    "selector": f':has-text("{text_pat}")', "tag": tag, "text": btn_text,
                    "visible": is_visible, "disabled": bool(is_disabled),
                }
                if debug:
                    debug_info["candidates"].append(candidate)
                if is_visible and not is_disabled:
                    box = await btn.bounding_box()
                    if box and box["width"] > 20 and box["height"] > 10:
                        logger.info(f"Pagination: clicking text='{text_pat}' tag={tag}")
                        await btn.click()
                        if debug:
                            debug_info["clicked"] = True
                            debug_info["clicked_via"] = candidate
                            return debug_info
                        return True
        except Exception:
            continue

    logger.info("Pagination: no next button found")
    if debug:
        return debug_info
    return False


# ── Public entry point ───────────────────────────────────────────────────────

async def scrape(url: str, browser=None, max_pages: int = 5, debug: bool = False) -> list[dict] | tuple:
    """Fallback scraper for career pages with no ATS match.

    Launches its own browser if one isn't passed. Navigates, waits for content,
    extracts job links via CSS selectors, paginates, returns jobs.
    """
    own_browser = browser is None
    pw = None
    if own_browser:
        pw, browser = await _get_browser()
    try:
        page = await _new_page(browser)
        try:
            await _setup_route_blocks(page)
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await _wait_for_content(page)
            result = await _extract_all_pages(page, url, max_pages=max_pages, debug=debug)
            return result
        finally:
            await _close_page(page)
    finally:
        if own_browser and pw is not None:
            await pw.stop()
