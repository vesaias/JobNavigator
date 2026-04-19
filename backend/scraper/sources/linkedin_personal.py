"""LinkedIn Personal source — scrapes /jobs/collections/recommended/ + /jobs/collections/top-applicant/.

Public entry points:
- `run(search)` — full scrape entry point for the scheduler / dispatch.
- `preview(search, db)` — UI dry-run endpoint that returns filtering diagnostics.
"""
import asyncio
import json
import logging
import os
import random
import re
import time
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

from backend.models.db import SessionLocal, Job, Search, Setting, get_existing_external_ids
from backend.scraper._shared.dedup import make_external_id, make_content_hash

logger = logging.getLogger("jobnavigator.linkedin")

COOKIE_PATH = "/tmp/linkedin_cookies.json"

# Delay ranges (seconds) — tuned to avoid 429s
DELAY_BETWEEN_CARDS = (1.5, 3.0)       # after clicking each card
DELAY_BEFORE_CLICK = (0.3, 0.7)        # before clicking a card
DELAY_PAGE_LOAD = (3.0, 5.0)           # after navigating to a new page
DELAY_BETWEEN_PAGES = (2.0, 4.0)       # between pagination pages
DELAY_BETWEEN_COLLECTIONS = (5.0, 8.0) # between collections
DELAY_ENRICHMENT = (5.0, 8.0)          # between enrichment page visits
DELAY_SCROLL = (1.0, 2.0)              # between scroll iterations

ALL_COLLECTIONS = {
    "recommended": "https://www.linkedin.com/jobs/collections/recommended/",
    "top-applicant": "https://www.linkedin.com/jobs/collections/top-applicant/",
}


async def _check_rate_limit(page) -> bool:
    """Check if LinkedIn is showing a 429 rate limit page. Returns True if rate-limited."""
    try:
        # LinkedIn 429 shows a specific error page or redirect
        url = page.url
        if "/429" in url or "too-many-requests" in url.lower():
            return True
        # Check page content for rate limit indicators
        title = await page.title()
        if title and ("429" in title or "too many" in title.lower()):
            return True
        # Check for the rate limit message in body
        body = await page.evaluate("() => document.body?.innerText?.substring(0, 500) || ''")
        if body and ("429" in body or "too many requests" in body.lower() or "rate limit" in body.lower()):
            return True
    except Exception:
        pass
    return False


class LinkedInRateLimitError(RuntimeError):
    """Raised when LinkedIn returns 429 and retries are exhausted."""
    pass


async def _handle_rate_limit(page, context_msg: str = "") -> bool:
    """If rate-limited, wait progressively and return True. Returns False if not rate-limited."""
    if not await _check_rate_limit(page):
        return False
    wait_time = random.uniform(60, 120)
    logger.warning(f"LinkedIn 429 rate limit detected{' — ' + context_msg if context_msg else ''}. "
                   f"Waiting {wait_time:.0f}s before retry...")
    await asyncio.sleep(wait_time)
    return True


async def _get_linkedin_browser():
    """Launch Playwright Chromium with stealth settings + cookie persistence."""
    from playwright.async_api import async_playwright
    from backend.scraper._shared.browser import _STEALTH_ARGS, _USER_AGENT

    pw = await async_playwright().start()
    browser = await pw.chromium.launch(
        headless=True,
        args=_STEALTH_ARGS,
    )
    context = await browser.new_context(
        user_agent=_USER_AGENT,
        viewport={"width": 1280, "height": 900},
    )
    await context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )

    # Load cookies if they exist
    if os.path.exists(COOKIE_PATH):
        try:
            with open(COOKIE_PATH, "r") as f:
                cookies = json.load(f)
            if cookies:
                await context.add_cookies(cookies)
                logger.info("Loaded LinkedIn cookies from cache")
        except Exception as e:
            logger.warning(f"Failed to load LinkedIn cookies: {e}")

    page = await context.new_page()
    return pw, browser, context, page


async def _is_logged_in(page) -> bool:
    """Check if current page shows a logged-in LinkedIn session."""
    try:
        # Check URL — login/checkpoint pages mean not logged in
        if "/login" in page.url or "/checkpoint" in page.url:
            return False
        # Look for feed nav or global nav elements present when logged in
        count = await page.locator('nav[aria-label="Primary"]').count()
        if count > 0:
            return True
        count = await page.locator('[data-alias="feed"]').count()
        if count > 0:
            return True
        # Check for profile icon
        count = await page.locator('img[alt*="Photo"]').count()
        if count > 0:
            return True
        return False
    except Exception:
        return False


async def _login(page, context, email: str, password: str):
    """Log in to LinkedIn with credentials. Raises on CAPTCHA/challenge."""
    logger.info("Logging in to LinkedIn...")
    await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(random.uniform(1.5, 3.0))

    await page.fill("#username", email)
    await asyncio.sleep(random.uniform(0.5, 1.0))
    await page.fill("#password", password)
    await asyncio.sleep(random.uniform(0.5, 1.0))
    await page.click('button[type="submit"]')

    # Wait for navigation
    try:
        await page.wait_for_url(
            lambda url: "/feed" in url or "/jobs" in url or "/mynetwork" in url,
            timeout=30000,
        )
    except Exception:
        # Check for security challenge / CAPTCHA
        current_url = page.url
        if "/checkpoint" in current_url or "/challenge" in current_url:
            raise RuntimeError(
                "LinkedIn security challenge detected (CAPTCHA or verification). "
                "Log in manually in a browser first to clear the challenge, then retry."
            )
        if "/login" in current_url:
            raise RuntimeError(
                "LinkedIn login failed — still on login page. Check credentials."
            )
        # Might have landed on an unexpected page but still logged in
        if not await _is_logged_in(page):
            raise RuntimeError(f"LinkedIn login failed — landed on unexpected page: {current_url}")

    # Save cookies
    await _save_cookies(context)
    logger.info("LinkedIn login successful, cookies saved")


async def _save_cookies(context):
    """Persist browser cookies to disk for session reuse."""
    try:
        cookies = await context.cookies()
        with open(COOKIE_PATH, "w") as f:
            json.dump(cookies, f)
    except Exception as e:
        logger.warning(f"Failed to save LinkedIn cookies: {e}")


async def _ensure_logged_in(page, context, email: str, password: str):
    """Navigate to LinkedIn and ensure we're logged in (cookie or credential login)."""
    # Try loading feed with existing cookies
    await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(random.uniform(2.0, 3.5))

    if await _is_logged_in(page):
        logger.info("LinkedIn session active via cookies")
        return

    # Cookies didn't work — do credential login
    if not email or not password:
        raise RuntimeError(
            "LinkedIn cookies expired and no credentials configured. "
            "Set linkedin_email and linkedin_password in Settings."
        )
    await _login(page, context, email, password)


def _parse_salary_text(text: str) -> dict:
    """Parse salary string like '$120K/yr - $180K/yr' or '$120,000/yr - $180,000/yr' into min/max ints."""
    result = {"salary_min": None, "salary_max": None, "salary_text": None}
    if not text:
        return result

    text = text.strip()
    # Match $120K, $120,000, $120000, $120.5K etc.
    amounts = []
    for m in re.finditer(r'\$([\d,]+(?:\.\d+)?)\s*([Kk])?', text):
        num = float(m.group(1).replace(",", ""))
        if m.group(2):  # K suffix
            num *= 1000
        elif num < 1000:
            # Bare number under 1000 is likely in thousands (e.g. "$120" meaning $120K)
            num *= 1000
        amounts.append(int(num))

    if amounts:
        result["salary_text"] = text
        result["salary_min"] = amounts[0]
        if len(amounts) >= 2:
            result["salary_max"] = amounts[-1]
    return result


async def _extract_detail_description(page) -> str:
    """Extract job description text from the right-side detail panel."""
    for sel in [
        '[class*="jobs-description-content__text"]',
        '[class*="jobs-description__content"]',
        '[class*="jobs-box__html-content"]',
        '.jobs-description',
        '#job-details',
    ]:
        el = await page.query_selector(sel)
        if el:
            text = (await el.inner_text()).strip()
            if text and len(text) > 30:
                return text
    return ""


async def _extract_detail_salary(page) -> str:
    """Extract salary text from the detail panel top card / insights area.

    LinkedIn renders salary in the job insights section above the description.
    It lives inside the top card alongside location, workplace type, etc.
    We scan all text nodes in the insights/top-card area for dollar amounts.
    """
    # Strategy 1: specific salary selectors
    for sel in [
        '[class*="salary-main-rail"]',
        '[class*="compensation"]',
        '[class*="job-details-jobs-unified-top-card__job-insight"]',
    ]:
        els = await page.query_selector_all(sel)
        for el in els:
            text = (await el.inner_text()).strip()
            if text and "$" in text:
                # Extract just the salary line from multi-line insight text
                for line in text.split("\n"):
                    line = line.strip()
                    if "$" in line:
                        return line
    # Strategy 2: scan the entire top card for any $ amount
    for sel in [
        '[class*="jobs-unified-top-card"]',
        '[class*="job-details-jobs-unified-top-card"]',
        '[class*="top-card"]',
    ]:
        el = await page.query_selector(sel)
        if el:
            text = (await el.inner_text()).strip()
            for line in text.split("\n"):
                line = line.strip()
                if "$" in line and re.search(r'\$[\d,]+', line):
                    return line
    # Strategy 3: look for the metadata wrapper in cards (visible on the left panel)
    for sel in [
        '[class*="job-card-container__metadata-wrapper"]',
        '[class*="metadata-wrapper"]',
    ]:
        # Find the currently active/selected card
        active = await page.query_selector('[class*="job-card--active"]') or await page.query_selector('[class*="job-card-list__entity--active"]')
        if active:
            el = await active.query_selector(sel)
            if el:
                text = (await el.inner_text()).strip()
                if "$" in text:
                    return text
    return ""


async def _extract_apply_url(page, job_id: str = "") -> str:
    """Extract external apply URL from the Apply button or embedded data.

    LinkedIn external Apply buttons are <a> tags with href pointing to
    /redir/redirect/?url=<encoded_real_url>. Easy Apply is a <button> (no href).
    """
    from urllib.parse import urlparse, parse_qs, unquote

    # Strategy 1: Find <a> tags whose text is "Apply" (not "Easy Apply")
    apply_url = await page.evaluate("""
    () => {
        const links = document.querySelectorAll('a');
        for (const a of links) {
            const text = (a.textContent || '').trim();
            // Match "Apply" but not "Easy Apply" or "Save & apply"
            if (text === 'Apply' || text === 'Apply now') {
                const href = a.getAttribute('href') || '';
                if (href && href.includes('/redir/redirect') || href.startsWith('http')) {
                    return href;
                }
            }
        }
        // Fallback: any <a> with href containing /redir/redirect
        for (const a of links) {
            const href = a.getAttribute('href') || '';
            if (href.includes('/redir/redirect')) {
                return href;
            }
        }
        return '';
    }
    """)

    if apply_url:
        # Parse the real URL from LinkedIn's redirect wrapper
        parsed = urlparse(apply_url)
        url_param = parse_qs(parsed.query).get("url", [])
        if url_param:
            return unquote(url_param[0])
        # If no url param but it's already external, return as-is
        apply_host = (parsed.hostname or "").lower()
        if not (apply_host == "linkedin.com" or apply_host.endswith(".linkedin.com")):
            return apply_url

    # Strategy 2: Search <code> elements (legacy LinkedIn pages)
    code_url = await _search_code_elements_for_apply_url(page, job_id)
    if code_url:
        return code_url

    return ""


async def _search_code_elements_for_apply_url(page, job_id: str = "") -> str:
    """Search <code> elements in current page DOM for JSON containing apply URL."""
    try:
        apply_url = await page.evaluate("""
        (jobId) => {
            const codes = document.querySelectorAll('code');
            for (const code of codes) {
                try {
                    const text = code.textContent;
                    if (!text || text.length < 20) continue;
                    // Quick text checks before expensive JSON parse
                    if (!text.includes('companyApplyUrl') && !text.includes('applyUrl')
                        && !text.includes('applyStarter')) continue;
                    // If we have a job ID, prefer code blocks that reference it
                    if (jobId && !text.includes(jobId)) continue;

                    const trimmed = text.trim();
                    if (!trimmed.startsWith('{') && !trimmed.startsWith('[')) continue;
                    const data = JSON.parse(trimmed);

                    function findApplyUrl(obj, depth) {
                        if (depth > 8 || !obj || typeof obj !== 'object') return null;
                        // Direct field: companyApplyUrl
                        if (typeof obj.companyApplyUrl === 'string'
                            && obj.companyApplyUrl.startsWith('http')) {
                            return obj.companyApplyUrl;
                        }
                        // Nested in applyMethod
                        if (obj.applyMethod && typeof obj.applyMethod === 'object') {
                            if (typeof obj.applyMethod.companyApplyUrl === 'string'
                                && obj.applyMethod.companyApplyUrl.startsWith('http')) {
                                return obj.applyMethod.companyApplyUrl;
                            }
                        }
                        // applyStarters array
                        if (Array.isArray(obj.applyStarters)) {
                            for (const s of obj.applyStarters) {
                                if (s && typeof s.companyApplyUrl === 'string'
                                    && s.companyApplyUrl.startsWith('http')) {
                                    return s.companyApplyUrl;
                                }
                            }
                        }
                        // applyUrl (non-LinkedIn)
                        if (typeof obj.applyUrl === 'string'
                            && obj.applyUrl.startsWith('http')
                            && !obj.applyUrl.includes('linkedin.com')) {
                            return obj.applyUrl;
                        }
                        // Recurse
                        if (Array.isArray(obj)) {
                            for (const item of obj) {
                                const found = findApplyUrl(item, depth + 1);
                                if (found) return found;
                            }
                        } else {
                            for (const key of Object.keys(obj)) {
                                const found = findApplyUrl(obj[key], depth + 1);
                                if (found) return found;
                            }
                        }
                        return null;
                    }

                    const found = findApplyUrl(data, 0);
                    if (found) return found;
                } catch(e) { /* JSON parse error or other — skip */ }
            }

            // Fallback: check <script type="application/ld+json"> for JobPosting
            const scripts = document.querySelectorAll('script[type="application/ld+json"]');
            for (const script of scripts) {
                try {
                    const data = JSON.parse(script.textContent);
                    const items = Array.isArray(data) ? data : [data];
                    for (const item of items) {
                        if (item['@type'] === 'JobPosting') {
                            if (item.url && !item.url.includes('linkedin.com'))
                                return item.url;
                        }
                    }
                } catch(e) {}
            }

            return '';
        }
        """, job_id)
        if apply_url:
            logger.debug(f"Found apply URL for job {job_id}: {apply_url[:80]}")
            return apply_url
    except Exception as e:
        logger.debug(f"Code element apply URL search failed: {e}")
    return ""


async def _enrich_apply_urls(page, jobs: list[dict]):
    """Navigate to individual job pages to extract apply URLs for jobs that don't have one.

    Called as a separate pass after all cards are collected from a collection,
    so it won't break card element references during the main scrape loop.
    """
    needs_enrichment = [j for j in jobs if not j.get("apply_url")]
    if not needs_enrichment:
        logger.info("All jobs already have apply URLs, skipping enrichment")
        return

    logger.info(f"Enriching apply URLs for {len(needs_enrichment)} jobs via individual pages")
    enriched = 0
    rate_limit_hits = 0
    for idx, j in enumerate(needs_enrichment):
        job_id = j["job_id"]
        try:
            await page.goto(
                f"https://www.linkedin.com/jobs/view/{job_id}/",
                wait_until="domcontentloaded",
                timeout=15000,
            )
            await asyncio.sleep(random.uniform(*DELAY_ENRICHMENT))

            # 429 check — abort enrichment gracefully (jobs are already collected)
            if await _handle_rate_limit(page, f"enrichment {idx+1}/{len(needs_enrichment)}"):
                rate_limit_hits += 1
                if rate_limit_hits >= 2:
                    logger.warning(f"Hit 429 twice during enrichment, skipping remaining {len(needs_enrichment) - idx} URLs")
                    break
                # Retry after wait
                await page.goto(
                    f"https://www.linkedin.com/jobs/view/{job_id}/",
                    wait_until="domcontentloaded",
                    timeout=15000,
                )
                await asyncio.sleep(random.uniform(*DELAY_ENRICHMENT))
                if await _check_rate_limit(page):
                    logger.warning(f"Still rate-limited after retry, skipping remaining {len(needs_enrichment) - idx} URLs")
                    break

            # Use _extract_apply_url which finds <a> Apply button with /redir/redirect href
            url = await _extract_apply_url(page, job_id)
            if url:
                j["apply_url"] = url
                j["url"] = url
                enriched += 1
                logger.debug(f"Enriched apply URL for {job_id}: {url[:80]}")
        except Exception as e:
            logger.debug(f"Apply URL enrichment failed for {job_id}: {e}")

    logger.info(f"Apply URL enrichment: {enriched}/{len(needs_enrichment)} jobs enriched")


async def _scroll_job_list(page):
    """Scroll the left-side job list panel via mouse wheel to load all lazy-rendered cards.

    LinkedIn only renders ~7 cards initially and lazy-loads more on scroll.
    Mouse wheel on the job list area is the reliable trigger.
    """
    count_js = "() => document.querySelectorAll('a[href*=\"/jobs/view/\"]').length"
    initial_count = await page.evaluate(count_js)

    first_card = await page.query_selector('a[href*="/jobs/view/"]')
    if not first_card:
        return

    box = await first_card.bounding_box()
    if not box:
        return

    # Move mouse over the job list area
    await page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)

    prev_count = initial_count
    no_change = 0
    for i in range(20):
        await page.mouse.wheel(0, 600)
        await asyncio.sleep(random.uniform(*DELAY_SCROLL))
        cur = await page.evaluate(count_js)
        if cur > prev_count:
            prev_count = cur
            no_change = 0
        else:
            no_change += 1
            if no_change >= 3:
                break

    final_count = await page.evaluate(count_js)
    if final_count > initial_count:
        logger.info(f"Scroll loaded {final_count - initial_count} cards ({initial_count} → {final_count})")


async def _scrape_page_with_clicks(page, seen_ids: set, collection_name: str) -> list[dict]:
    """Extract all cards on the current page by clicking each to load the detail panel.

    For each card: extract title/company/location from the card, then click it
    to load the right-side detail panel for salary + description.
    Returns list of fully enriched job dicts.
    """
    await _scroll_job_list(page)

    job_links = await page.query_selector_all('a[href*="/jobs/view/"]')
    # Build ordered unique list
    ordered = []
    for link in job_links:
        try:
            href = await link.get_attribute("href") or ""
            match = re.search(r"/jobs/view/(\d+)", href)
            if not match:
                continue
            job_id = match.group(1)
            if job_id in seen_ids:
                continue
            seen_ids.add(job_id)
            ordered.append((job_id, link))
        except Exception:
            continue

    if not ordered:
        return []

    jobs = []
    for idx, (job_id, link) in enumerate(ordered):
        try:
            job_url = f"https://www.linkedin.com/jobs/view/{job_id}/"

            # --- Card-level extraction ---
            title = ""
            sr_span = await link.query_selector("span.sr-only")
            if sr_span:
                title = (await sr_span.inner_text()).strip()
            if not title:
                aria = await link.get_attribute("aria-label") or ""
                if aria:
                    title = aria.strip()
            if not title:
                for sel in ["h3", "h4"]:
                    el = await link.query_selector(sel)
                    if el:
                        title = (await el.inner_text()).strip()
                        if title:
                            break
            if not title:
                continue

            # Clean LinkedIn title suffixes
            title = re.sub(r'\s+with verification$', '', title, flags=re.IGNORECASE)

            company = ""
            location = ""
            card_li = await link.evaluate_handle("el => el.closest('li')")
            card_el = card_li.as_element() if card_li else None
            if card_el:
                for sel in ['[class*="subtitle"]', '[class*="company"]', '[class*="artdeco-entity-lockup__subtitle"]']:
                    el = await card_el.query_selector(sel)
                    if el:
                        company = (await el.inner_text()).strip()
                        if company:
                            break
                for sel in ['[class*="caption"]', '[class*="location"]', '[class*="artdeco-entity-lockup__caption"]']:
                    el = await card_el.query_selector(sel)
                    if el:
                        location = (await el.inner_text()).strip()
                        if location:
                            break

            # --- Click card to load detail panel ---
            try:
                await link.scroll_into_view_if_needed()
                await asyncio.sleep(random.uniform(*DELAY_BEFORE_CLICK))
                await link.click()
                # Wait for detail panel to update — watch for description element
                try:
                    await page.wait_for_selector(
                        '[class*="jobs-description-content__text"], [class*="jobs-description__content"], #job-details',
                        timeout=5000,
                    )
                except Exception:
                    pass
                await asyncio.sleep(random.uniform(*DELAY_BETWEEN_CARDS))

                # Check for 429 after loading detail
                if await _handle_rate_limit(page, f"card {idx+1}/{len(ordered)}"):
                    # After waiting, re-click to retry
                    try:
                        await link.click()
                        await asyncio.sleep(random.uniform(*DELAY_BETWEEN_CARDS))
                    except Exception:
                        pass
            except Exception as click_err:
                logger.debug(f"Click failed for {job_id}: {click_err}")

            # --- Detail panel extraction ---
            description = await _extract_detail_description(page)
            salary_text = await _extract_detail_salary(page)
            salary_info = _parse_salary_text(salary_text)
            apply_url = await _extract_apply_url(page, job_id)

            # Use external apply URL as primary if available
            primary_url = apply_url if apply_url else job_url

            jobs.append({
                "title": title,
                "company": company,
                "url": primary_url,
                "linkedin_url": job_url,
                "apply_url": apply_url,
                "location": location,
                "job_id": job_id,
                "collection": collection_name,
                "description": description,
                "salary_text": salary_info["salary_text"],
                "salary_min": salary_info["salary_min"],
                "salary_max": salary_info["salary_max"],
            })
        except Exception as e:
            logger.debug(f"Error processing card {job_id}: {e}")
            continue

    return jobs


async def _scrape_collection(page, url: str, collection_name: str) -> list[dict]:
    """Scrape a LinkedIn collection: paginate via ?start=N, click each card for detail panel."""
    logger.info(f"Scraping LinkedIn collection: {collection_name}")

    PAGE_SIZE = 25
    all_jobs = []
    seen_ids = set()

    rate_limit_hits = 0
    for page_num in range(20):  # up to 500 jobs
        start = page_num * PAGE_SIZE
        page_url = f"{url}?start={start}" if "?" not in url else f"{url}&start={start}"
        logger.info(f"Loading {collection_name} page {page_num + 1} (start={start})")

        await page.goto(page_url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(random.uniform(*DELAY_PAGE_LOAD))

        # 429 detection with retry
        if await _handle_rate_limit(page, f"page {page_num + 1}"):
            rate_limit_hits += 1
            # Retry the same page after wait
            await page.goto(page_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(random.uniform(*DELAY_PAGE_LOAD))
            if await _check_rate_limit(page):
                if rate_limit_hits >= 2 or not all_jobs:
                    # No jobs collected yet or repeated — raise so caller reports error
                    raise LinkedInRateLimitError(
                        f"LinkedIn 429 rate limit on {collection_name} page {page_num + 1}. "
                        f"Try again in 15-30 minutes."
                    )
                # We have some jobs already, stop gracefully
                logger.warning(f"Still rate-limited after retry, returning {len(all_jobs)} jobs collected so far")
                break

        page_jobs = await _scrape_page_with_clicks(page, seen_ids, collection_name)
        logger.info(f"Page {page_num + 1}: {len(page_jobs)} new jobs")

        if not page_jobs:
            logger.info(f"No new jobs on page {page_num + 1}, stopping pagination")
            break

        all_jobs.extend(page_jobs)

        if (page_num + 1) % 3 == 0:
            logger.info(f"Progress: {len(all_jobs)} total jobs from {collection_name}")

        await asyncio.sleep(random.uniform(*DELAY_BETWEEN_PAGES))

    logger.info(f"Extracted {len(all_jobs)} jobs from {collection_name}")
    return all_jobs


async def run(search: Search) -> dict:
    """Main entry point for linkedin_personal search mode. Scrape collections and save to DB."""
    start_time = time.time()

    pw = None
    browser = None
    context = None
    try:
        # Read credentials from settings
        db_settings = SessionLocal()
        try:
            email_row = db_settings.query(Setting).filter(Setting.key == "linkedin_email").first()
            pass_row = db_settings.query(Setting).filter(Setting.key == "linkedin_password").first()
            email = email_row.value if email_row else ""
            password = pass_row.value if pass_row else ""
        finally:
            db_settings.close()

        # Determine which collections to scrape
        collections_to_scrape = search.sources or ["recommended", "top-applicant"]
        collections_to_scrape = [c for c in collections_to_scrape if c in ALL_COLLECTIONS]
        if not collections_to_scrape:
            collections_to_scrape = list(ALL_COLLECTIONS.keys())

        # Launch browser and log in
        pw, browser, context, page = await _get_linkedin_browser()
        await _ensure_logged_in(page, context, email, password)

        # Scrape each collection (errors per collection are non-fatal)
        all_jobs = []
        for i, coll_name in enumerate(collections_to_scrape):
            if i > 0:
                await asyncio.sleep(random.uniform(*DELAY_BETWEEN_COLLECTIONS))
            coll_url = ALL_COLLECTIONS[coll_name]
            try:
                coll_jobs = await _scrape_collection(page, coll_url, coll_name)
                all_jobs.extend(coll_jobs)
            except Exception as coll_err:
                logger.warning(f"Collection '{coll_name}' error (continuing): {coll_err}")

        # Deduplicate by job_id across collections
        seen_ids = set()
        unique_jobs = []
        for j in all_jobs:
            if j["job_id"] not in seen_ids:
                seen_ids.add(j["job_id"])
                unique_jobs.append(j)

        # Apply search-level + global title filters
        from backend.models.db import get_global_title_exclude
        _gte_db = SessionLocal()
        try:
            _global_title_excl = get_global_title_exclude(_gte_db)
        finally:
            _gte_db.close()
        include_kw = search.title_include_keywords or []
        exclude_kw = list(set((search.title_exclude_keywords or []) + _global_title_excl))
        kept_jobs = []
        for j in unique_jobs:
            title_lower = j["title"].lower()
            if include_kw and not any(kw.lower() in title_lower for kw in include_kw):
                continue
            if exclude_kw and any(re.search(r'\b' + re.escape(kw) + r'\b', title_lower) for kw in exclude_kw):
                continue
            kept_jobs.append(j)

        # Company exclude (global + per-search)
        db_excl = SessionLocal()
        try:
            from backend.scraper.sources.jobspy import get_setting_value
            global_exclude = json.loads(get_setting_value(db_excl, "company_exclude_global", "[]"))
            global_exclude_set = {e.lower() for e in global_exclude}
            search_exclude_set = {e.lower() for e in (search.company_exclude or [])}
            if global_exclude_set or search_exclude_set:
                before = len(kept_jobs)
                kept_jobs = [
                    j for j in kept_jobs
                    if (j.get("company") or "").lower() not in global_exclude_set
                    and (j.get("company") or "").lower() not in search_exclude_set
                ]
                if len(kept_jobs) < before:
                    logger.info(f"LinkedIn: company exclude removed {before - len(kept_jobs)} jobs")
        finally:
            db_excl.close()

        jobs_found = len(kept_jobs)

        # Enrich apply URLs — only for kept jobs, after all filtering (non-fatal)
        if kept_jobs:
            try:
                await _enrich_apply_urls(page, kept_jobs)
            except Exception as enrich_err:
                logger.warning(f"Apply URL enrichment error (continuing): {enrich_err}")

        # Save to DB
        db = SessionLocal()
        new_jobs = 0
        try:
            existing_ids = get_existing_external_ids(db)
            # Load existing LinkedIn job IDs to skip jobs already imported via extension
            existing_li_ids = {r[0] for r in db.query(Job.linkedin_job_id).filter(Job.linkedin_job_id != None).all()}

            for j in kept_jobs:
                # Use apply URL (company career page) as primary, LinkedIn URL as fallback
                job_url = j.get("apply_url") or j["url"]
                linkedin_url = j.get("linkedin_url") or j["url"]

                # Check if this LinkedIn ID was already imported via extension
                li_id = j.get("job_id") or ""
                if li_id and li_id in existing_li_ids:
                    continue

                ext_id = make_external_id(j["company"], j["title"], job_url)
                if ext_id in existing_ids:
                    continue
                # Also check LinkedIn URL to avoid duplicates across URL formats
                if job_url != linkedin_url:
                    alt_id = make_external_id(j["company"], j["title"], linkedin_url)
                    if alt_id in existing_ids:
                        continue

                content_hash = make_content_hash(j["company"], j["title"])

                job = Job(
                    external_id=ext_id,
                    content_hash=content_hash,
                    linkedin_job_id=li_id or None,
                    company=j["company"],
                    title=j["title"],
                    url=job_url,
                    source="linkedin_personal",
                    search_id=search.id,
                    location=j.get("location") or None,
                    description=j.get("description") or None,
                    status="new",
                    seen=False,
                    saved=False,
                )

                # Salary from LinkedIn card/detail
                if j.get("salary_min"):
                    job.salary_min = j["salary_min"]
                    job.salary_source = "posting"
                if j.get("salary_max"):
                    job.salary_max = j["salary_max"]
                    job.salary_source = "posting"

                # H-1B check + language check + salary extraction
                try:
                    from backend.analyzer.h1b_checker import check_job_h1b
                    from backend.analyzer.salary_extractor import apply_salary_to_job
                    await check_job_h1b(job, db)
                    from backend.models.db import find_company_by_name
                    company_obj = find_company_by_name(db, j["company"])
                    h1b_median = company_obj.h1b_median_salary if company_obj else None
                    apply_salary_to_job(job, h1b_median)
                except Exception as e:
                    logger.warning(f"Inline analysis failed for {j['title']}: {e}")

                if job.h1b_jd_flag:
                    logger.info(f"Skipping job (body exclusion): {j['title']} — {job.h1b_jd_snippet}")
                    continue

                # Use savepoint so one duplicate doesn't kill the whole batch
                try:
                    with db.begin_nested():
                        db.add(job)
                        db.flush()
                    new_jobs += 1
                    existing_ids.add(ext_id)
                except IntegrityError:
                    logger.debug(f"Duplicate external_id for '{j['title']}' at {j.get('company')}, skipping")
                    continue

            # Update last_run_at
            search_obj = db.query(Search).filter(Search.id == search.id).first()
            if search_obj:
                search_obj.last_run_at = datetime.now(timezone.utc)

            db.commit()
        finally:
            db.close()

        # Save cookies on success
        await _save_cookies(context)

        duration = time.time() - start_time
        from backend.activity import log_activity
        log_activity("scrape", f"LinkedIn personal '{search.name}': {new_jobs} new / {jobs_found} found in {duration:.1f}s")

        return {"jobs_found": jobs_found, "new_jobs": new_jobs, "error": None, "duration": duration}

    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"LinkedIn personal scrape failed for '{search.name}': {e}")
        from backend.activity import log_activity
        log_activity("scrape", f"LinkedIn personal '{search.name}' failed: {e}")
        return {"jobs_found": 0, "new_jobs": 0, "error": str(e), "duration": duration}
    finally:
        if browser:
            await browser.close()
        if pw:
            await pw.stop()


async def preview(search, db) -> dict:
    """Test endpoint handler — scrape collections, apply filters, enrich URLs, return results.

    Resilient: errors in individual stages (collection scrape, enrichment) don't
    discard results from earlier stages. Partial results returned with warnings.
    """
    import time as _time
    start = _time.time()

    pw = None
    browser = None
    context = None
    page = None
    all_jobs = []
    warnings = []
    collections_to_scrape = []

    # --- Phase 1: Browser setup + login ---
    try:
        email_row = db.query(Setting).filter(Setting.key == "linkedin_email").first()
        pass_row = db.query(Setting).filter(Setting.key == "linkedin_password").first()
        email = email_row.value if email_row else ""
        password = pass_row.value if pass_row else ""

        collections_to_scrape = search.sources or ["recommended", "top-applicant"]
        collections_to_scrape = [c for c in collections_to_scrape if c in ALL_COLLECTIONS]
        if not collections_to_scrape:
            collections_to_scrape = list(ALL_COLLECTIONS.keys())

        pw, browser, context, page = await _get_linkedin_browser()
        await _ensure_logged_in(page, context, email, password)
    except Exception as e:
        # Login failure is fatal — no partial results possible
        if browser:
            await browser.close()
        if pw:
            await pw.stop()
        return {
            "search_name": search.name,
            "error": str(e),
            "config": {"mode": "linkedin_personal", "collections": collections_to_scrape},
        }

    # --- Phase 2: Scrape collections (errors are non-fatal per collection) ---
    try:
        for i, coll_name in enumerate(collections_to_scrape):
            if i > 0:
                await asyncio.sleep(random.uniform(*DELAY_BETWEEN_COLLECTIONS))
            coll_url = ALL_COLLECTIONS[coll_name]
            try:
                coll_jobs = await _scrape_collection(page, coll_url, coll_name)
                all_jobs.extend(coll_jobs)
            except Exception as coll_err:
                msg = f"{coll_name}: {coll_err}"
                logger.warning(f"Collection scrape error: {msg}")
                warnings.append(msg)

        await _save_cookies(context)

        # --- Phase 3: Filtering ---
        seen_ids = set()
        unique_jobs = []
        for j in all_jobs:
            if j["job_id"] not in seen_ids:
                seen_ids.add(j["job_id"])
                unique_jobs.append(j)

        raw_count = len(unique_jobs)
        from backend.models.db import get_global_title_exclude
        _global_title_excl = get_global_title_exclude(db)
        include_kw = search.title_include_keywords or []
        exclude_kw = list(set((search.title_exclude_keywords or []) + _global_title_excl))

        global_exclude_row = db.query(Setting).filter(Setting.key == "company_exclude_global").first()
        global_exclude = json.loads(global_exclude_row.value) if global_exclude_row and global_exclude_row.value else []
        global_exclude_set = {e.lower() for e in global_exclude}
        search_exclude = [e.lower() for e in (search.company_exclude or [])]
        search_exclude_set = set(search_exclude)
        all_exclude = list(global_exclude_set | search_exclude_set)

        body_row = db.query(Setting).filter(Setting.key == "body_exclusion_phrases").first()
        body_phrases = []
        if body_row and body_row.value:
            try:
                body_phrases = json.loads(body_row.value)
            except json.JSONDecodeError:
                pass

        from collections import Counter
        collection_counts = Counter(j["collection"] for j in unique_jobs) if unique_jobs else Counter()
        company_counts = Counter(j["company"] for j in unique_jobs if j.get("company"))
        company_breakdown = dict(company_counts.most_common(20))

        kept_jobs = []
        results = []
        for j in unique_jobs:
            title = j["title"]
            title_lower = title.lower()
            kept = True
            reason = None

            if include_kw and not any(kw.lower() in title_lower for kw in include_kw):
                kept = False
                reason = f"No match for: {', '.join(include_kw)}"
            if kept and exclude_kw:
                matched = [kw for kw in exclude_kw if re.search(r'\b' + re.escape(kw) + r'\b', title_lower)]
                if matched:
                    kept = False
                    reason = f"Excluded by: {', '.join(matched)}"
            if kept and (global_exclude_set or search_exclude_set):
                company_lower = (j.get("company") or "").lower()
                if company_lower in global_exclude_set:
                    kept = False
                    reason = f"Company excluded (global): {company_lower}"
                elif company_lower in search_exclude_set:
                    kept = False
                    reason = f"Company excluded: {company_lower}"
            if kept and body_phrases:
                desc_text = j.get("description") or ""
                if desc_text:
                    from backend.analyzer.h1b_checker import scan_jd_for_h1b_flags
                    body_result = scan_jd_for_h1b_flags(desc_text, body_phrases)
                    if body_result["jd_flag"]:
                        kept = False
                        reason = f"Body exclusion: {body_result['jd_snippet'][:80] if body_result['jd_snippet'] else 'matched'}"

            if kept:
                kept_jobs.append(j)
            results.append({"job": j, "kept": kept, "reason": reason})

        # --- Phase 4: Enrich apply URLs (non-fatal) ---
        if kept_jobs:
            try:
                await _enrich_apply_urls(page, kept_jobs)
            except Exception as enrich_err:
                msg = f"Apply URL enrichment: {enrich_err}"
                logger.warning(msg)
                warnings.append(msg)

    except Exception as e:
        # Unexpected error during filtering — still return whatever we have
        warnings.append(f"Processing error: {e}")
        logger.error(f"Test processing error: {e}")
    finally:
        if browser:
            await browser.close()
        if pw:
            await pw.stop()

    duration = round(_time.time() - start, 1)

    if not all_jobs:
        return {
            "search_name": search.name,
            "duration": duration,
            "raw_count": 0,
            "after_filter": 0,
            "source_breakdown": {"linkedin_personal": 0},
            "company_breakdown": {},
            "include_keywords": search.title_include_keywords or [],
            "exclude_keywords": search.title_exclude_keywords or [],
            "company_exclude": [],
            "jobs": [],
            "warnings": warnings or None,
            "config": {"mode": "linkedin_personal", "collections": collections_to_scrape},
        }

    # Build final results list
    final_results = []
    for r in results:
        j = r["job"]
        salary = None
        if j.get("salary_min"):
            salary = f"${j['salary_min']:,}"
            if j.get("salary_max"):
                salary += f" – ${j['salary_max']:,}"
        elif j.get("salary_text"):
            salary = j["salary_text"]

        desc = j.get("description") or ""
        has_desc = bool(desc and len(desc) > 50)
        display_url = j.get("apply_url") or j.get("url", "")

        final_results.append({
            "title": j["title"],
            "company": j.get("company", ""),
            "url": display_url,
            "linkedin_url": j.get("linkedin_url", ""),
            "source": "linkedin_personal",
            "location": j.get("location", ""),
            "salary": salary,
            "has_description": has_desc,
            "desc_length": len(desc) if has_desc else 0,
            "kept": r["kept"],
            "reason": r["reason"],
            "collection": j.get("collection", ""),
        })

    after_filter = sum(1 for r in final_results if r["kept"])

    return {
        "search_name": search.name,
        "duration": duration,
        "raw_count": raw_count,
        "after_filter": after_filter,
        "source_breakdown": dict(collection_counts),
        "company_breakdown": company_breakdown,
        "include_keywords": include_kw,
        "exclude_keywords": exclude_kw,
        "company_exclude": all_exclude,
        "jobs": final_results,
        "warnings": warnings or None,
        "config": {"mode": "linkedin_personal", "collections": collections_to_scrape},
    }
