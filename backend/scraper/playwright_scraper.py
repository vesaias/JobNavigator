"""Playwright direct career page scraper + URL mode scraper."""
import asyncio
import json
import logging
import re
import time
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import httpx

from sqlalchemy.exc import IntegrityError

from backend.models.db import SessionLocal, Company, Job, ScrapeLog, Search, get_existing_external_ids
from backend.scraper.deduplicator import make_external_id, make_content_hash

logger = logging.getLogger("jobnavigator.playwright")


# ── Re-exports from _shared (Task 2) ──────────────────────────────────────────
from backend.scraper._shared.urls import (  # noqa: F401
    _get_url_tracking_params, _clean_application_url,
    host_matches, path_contains,
)
# Back-compat aliases for existing callers inside this file
_host_matches = host_matches
_path_contains = path_contains


# ── Re-exports from _shared (Task 3) ──────────────────────────────────────────
from backend.scraper._shared.filters import (  # noqa: F401
    GARBAGE_TITLES, GARBAGE_SUBSTRINGS, _LOCALE_NAMES,
    _tokenize, _parse_expr, _parse_and, _parse_atom, _eval_expr,
    match_title_expr, _validate_job, _apply_company_filters,
)


# ── Re-exports from ats/_descriptions (Task 6) ────────────────────────────────
from backend.scraper.ats._descriptions import (  # noqa: F401
    _fetch_job_description, _fetch_description_ats, _fetch_descriptions_parallel,
)


# ── Re-exports from ats/workday (Task 7) ──────────────────────────────────────
from backend.scraper.ats.workday import (  # noqa: F401
    is_workday, scrape as _scrape_workday, _parse_workday_url, _LOCALE_PATH_RE,
)
_is_workday = is_workday  # back-compat alias


# Back-compat re-exports — Task 1 (migrated to _shared/browser.py)
from backend.scraper._shared.browser import (  # noqa: F401
    _STEALTH_ARGS, _USER_AGENT,
    _get_browser, _new_page, _close_page,
)


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


# ── Oracle HCM scraper ───────────────────────────────────────────────────────

def _is_oracle_hcm(url: str) -> bool:
    return "oraclecloud.com/hcmUI/CandidateExperience" in url or "/sites/" in url and "/jobs" in url and _oracle_hcm_host(url) is not None

# Map custom career domains to their Oracle HCM API backend
_ORACLE_HCM_HOSTS = {
    "careers.oracle.com": "eeho.fa.us2.oraclecloud.com",
}

def _oracle_hcm_host(url: str) -> str | None:
    """Return the Oracle HCM API host for a given URL, or None."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host == "oraclecloud.com" or host.endswith(".oraclecloud.com"):
        return parsed.netloc
    return _ORACLE_HCM_HOSTS.get(host)


async def _scrape_oracle_hcm(url: str, debug: bool = False) -> list[dict] | tuple:
    """Fetch Oracle HCM job listings via REST API."""
    import json
    from urllib.parse import parse_qs, urlparse as _urlparse, unquote

    parsed = _urlparse(url)
    ui_origin = f"{parsed.scheme}://{parsed.netloc}"
    api_host = _oracle_hcm_host(url)
    api_origin = f"https://{api_host}" if api_host else ui_origin
    params = parse_qs(parsed.query)

    # Extract site number from path: .../sites/CX_1001/jobs
    path_parts = parsed.path.split("/")
    site = ""
    for i, p in enumerate(path_parts):
        if p == "sites" and i + 1 < len(path_parts):
            site = path_parts[i + 1]
            break

    # Detect path prefix: oraclecloud.com URLs need /hcmUI/CandidateExperience,
    # custom domains (e.g. careers.oracle.com) route directly
    job_path_prefix = ""
    if "hcmUI/CandidateExperience" in parsed.path:
        job_path_prefix = "/hcmUI/CandidateExperience"

    # Build facets list
    facets = []
    categories = params.get("selectedCategoriesFacet", [""])[0].replace("%3B", ";")
    location_id = params.get("locationId", [""])[0]
    locations_facet = params.get("selectedLocationsFacet", [""])[0].replace("%3B", ";")
    posting_dates = params.get("selectedPostingDatesFacet", [""])[0]
    flex_fields = unquote(params.get("selectedFlexFieldsFacets", [""])[0])

    if posting_dates:
        facets.append(f"POSTING_DATES;{posting_dates}")
    if categories:
        facets.append(f"CATEGORIES;{categories}")
    if location_id:
        facets.append(f"LOCATIONS;{location_id}")
    elif locations_facet:
        facets.append(f"LOCATIONS;{locations_facet}")
    if flex_fields:
        facets.append(f"FLEX_FIELDS;{flex_fields}")
    facets_str = "|".join(facets)

    last_facet = params.get("lastSelectedFacet", ["POSTING_DATES"])[0]

    jobs = []
    rejected = []
    offset = 0
    limit = 200

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        while True:
            finder_parts = [
                f"siteNumber={site}",
                f"facetsList={facets_str}",
                f"lastSelectedFacet={last_facet}",
            ]
            if categories:
                finder_parts.append(f"selectedCategoriesFacet={categories}")
            if location_id:
                finder_parts.append(f"selectedLocationsFacet={location_id}")
            elif locations_facet:
                finder_parts.append(f"selectedLocationsFacet={locations_facet}")
            if posting_dates:
                finder_parts.append(f"selectedPostingDatesFacet={posting_dates}")
            if flex_fields:
                finder_parts.append(f"selectedFlexFieldsFacets={flex_fields}")
            finder_parts.extend([
                "sortBy=POSTING_DATES_DESC",
                f"limit={limit}",
                f"offset={offset}",
            ])

            api_url = (
                f"{api_origin}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
                f"?onlyData=true&expand=requisitionList.secondaryLocations,flexFieldsFacet.values"
                f"&finder=findReqs;{','.join(finder_parts)}"
            )

            resp = await client.get(api_url)
            data = json.loads(resp.text)

            items = data.get("items", [])
            if not items:
                break

            req_list = items[0].get("requisitionList", [])
            total = items[0].get("TotalJobsCount", 0)

            for req in req_list:
                title = req.get("Title", "").strip()
                req_id = req.get("Id", "")
                job_url = f"{ui_origin}{job_path_prefix}/en/sites/{site}/job/{req_id}"
                reason = _validate_job(title, job_url)
                if reason is None:
                    jobs.append({"title": title, "url": job_url})
                elif debug:
                    rejected.append({"title": title, "url": job_url, "selector": "oracle_hcm_api", "reason": reason})

            offset += len(req_list)
            if offset >= total or len(req_list) == 0:
                break

    logger.info(f"Oracle HCM: fetched {len(jobs)} jobs from {api_origin}/.../{site}")
    if debug:
        return jobs, rejected
    return jobs


# ── Phenom People scraper (Cisco, etc.) ──────────────────────────────────────

def _is_phenom_post(url: str) -> bool:
    return url.strip().upper().startswith("POST|")


def _parse_phenom_url(raw: str) -> tuple[str, dict]:
    """Parse 'POST|https://host/widgets|{json payload}' format."""
    import json
    parts = raw.strip().split("|", 2)
    endpoint = parts[1].strip()
    if len(parts) > 2:
        # Collapse runs of whitespace (from textarea line-wrapping) before parsing
        cleaned = re.sub(r'\s+', ' ', parts[2].strip())
        payload = json.loads(cleaned)
    else:
        payload = {}
    return endpoint, payload


async def _scrape_phenom(raw_url: str, debug: bool = False) -> list[dict] | tuple:
    """Fetch jobs from a Phenom People /widgets POST API."""
    import json
    endpoint, base_payload = _parse_phenom_url(raw_url)
    parsed = urlparse(endpoint)
    origin = f"{parsed.scheme}://{parsed.netloc}"

    # Ensure we fetch all results in large batches
    base_payload["from"] = 0
    base_payload["size"] = 200
    base_payload.setdefault("jobs", True)
    ddo_key = base_payload.get("ddoKey", "refineSearch")
    base_payload.setdefault("ddoKey", ddo_key)

    logger.info(f"Phenom API: endpoint={endpoint} ddoKey={ddo_key}")
    logger.info(f"Phenom API: selected_fields={base_payload.get('selected_fields', 'NONE')}")

    jobs = []
    rejected = []
    offset = 0

    headers = {
        "Content-Type": "application/json",
        "Referer": f"{origin}/",
    }

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        while True:
            base_payload["from"] = offset
            resp = await client.post(endpoint, json=base_payload, headers=headers)
            data = json.loads(resp.text)

            rs = data.get(ddo_key, {})
            total = rs.get("totalHits", 0)
            job_list = rs.get("data", {}).get("jobs", [])

            if offset == 0:
                logger.info(f"Phenom API: totalHits={total}")

            if not job_list:
                break

            for j in job_list:
                title = j.get("title", "").strip()
                job_id = j.get("jobId", "")
                job_url = j.get("applyUrl") or f"{origin}/global/en/job/{job_id}"
                # Strip trailing /apply to get the job detail page
                if job_url.endswith("/apply"):
                    job_url = job_url[:-6]
                reason = _validate_job(title, job_url)
                if reason is None:
                    jobs.append({"title": title, "url": job_url})
                elif debug:
                    rejected.append({"title": title, "url": job_url, "selector": "phenom_api", "reason": reason})

            offset += len(job_list)
            if offset >= total:
                break

    logger.info(f"Phenom API: fetched {len(jobs)} jobs from {endpoint}")
    if debug:
        return jobs, rejected
    return jobs


# ── TalentBrew AJAX scraper ──────────────────────────────────────────────────

async def _scrape_talentbrew_ajax(url: str, debug: bool = False) -> list[dict] | tuple:
    """Fetch TalentBrew AJAX search-results URL via HTTP and parse job links from JSON."""
    import json
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    jobs = []
    rejected = []
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(url, headers={"X-Requested-With": "XMLHttpRequest"})

    data = json.loads(resp.text)
    results_html = data.get("results", "")

    for m in re.finditer(r'<a\s[^>]*href="(/job/[^"]+)"[^>]*>(.*?)</a>', results_html, re.DOTALL):
        href, raw_title = m.group(1), m.group(2)
        title = re.sub(r'<[^>]+>', '', raw_title).strip()
        if '\n' in title:
            title = title.split('\n')[0].strip()
        full_url = f"{origin}{href}"
        reason = _validate_job(title, full_url)
        if reason is None:
            jobs.append({"title": title, "url": full_url})
        elif debug:
            rejected.append({"title": title, "url": full_url, "selector": "talentbrew_ajax", "reason": reason})

    logger.info(f"TalentBrew AJAX: parsed {len(jobs)} valid jobs from {url[:80]}...")
    if debug:
        return jobs, rejected
    return jobs


def _is_talentbrew_ajax(url: str) -> bool:
    """Check if URL is a TalentBrew AJAX search-results endpoint (BlackRock, Intuit, etc.)."""
    return "/search-jobs/results?" in url.lower()


# ── Lever scraper ─────────────────────────────────────────────────────────────

def _is_lever(url: str) -> bool:
    """Check if URL is a Lever job board (jobs.lever.co/<company>)."""
    return "jobs.lever.co/" in url.lower()


async def _scrape_lever(url: str, debug: bool = False) -> list[dict] | tuple:
    """Fetch jobs from Lever's public JSON API.

    Forwards supported filters from the original URL query string:
    department, team, location, commitment.
    """
    import json
    from urllib.parse import parse_qs
    parsed = urlparse(url)
    # Extract company slug from path: /plaid or /plaid/
    path_parts = [p for p in parsed.path.strip("/").split("/") if p]
    if not path_parts:
        if debug:
            return [], [{"title": "(none)", "url": url, "selector": "lever_api", "reason": "No company slug in URL"}]
        return []
    company_slug = path_parts[0]

    # Build API URL, forwarding supported Lever filters
    api_url = f"https://api.lever.co/v0/postings/{company_slug}?mode=json"
    qs = parse_qs(parsed.query)
    for param in ("department", "team", "location", "commitment"):
        if param in qs:
            api_url += f"&{param}={qs[param][0]}"

    jobs = []
    rejected = []

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(api_url)
        if resp.status_code != 200:
            logger.warning(f"Lever API returned {resp.status_code} for {company_slug}")
            if debug:
                return [], [{"title": "(none)", "url": api_url, "selector": "lever_api", "reason": f"HTTP {resp.status_code}"}]
            return []

        postings = json.loads(resp.text)
        for p in postings:
            title = (p.get("text") or "").strip()
            job_url = p.get("hostedUrl") or ""
            reason = _validate_job(title, job_url)
            if reason is None:
                jobs.append({"title": title, "url": job_url})
            elif debug:
                rejected.append({"title": title, "url": job_url, "selector": "lever_api", "reason": reason})

    logger.info(f"Lever API: fetched {len(jobs)} jobs for {company_slug}")
    if debug:
        return jobs, rejected
    return jobs


# ── Ashby scraper ────────────────────────────────────────────────────────────

def _is_ashby(url: str) -> bool:
    """Check if URL is an Ashby job board (jobs.ashbyhq.com)."""
    return _host_matches(url, "jobs.ashbyhq.com")


async def _scrape_ashby(url: str, debug: bool = False) -> list[dict] | tuple:
    """Fetch jobs from Ashby's public JSON API.

    API returns all jobs; departmentId/locationId filtering is applied client-side.
    """
    import json
    from urllib.parse import parse_qs

    parsed = urlparse(url)
    # Company slug from path: /ramp or /ramp/
    path_parts = [p for p in parsed.path.strip("/").split("/") if p]
    if not path_parts:
        if debug:
            return [], [{"title": "(none)", "url": url, "selector": "ashby_api", "reason": "No company slug in URL"}]
        return []
    company_slug = path_parts[0]

    # Extract filter params from URL query string
    qs = parse_qs(parsed.query)
    filter_dept_ids = set(qs.get("departmentId", []))
    filter_location_ids = set(qs.get("locationId", []))
    filter_team_ids = set(qs.get("teamId", []))

    api_url = f"https://api.ashbyhq.com/posting-api/job-board/{company_slug}"
    logger.info(f"Ashby API: {api_url} dept_filter={len(filter_dept_ids)} loc_filter={len(filter_location_ids)} team_filter={len(filter_team_ids)}")

    jobs = []
    rejected = []

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(api_url)
        if resp.status_code != 200:
            logger.warning(f"Ashby API returned {resp.status_code} for {company_slug}")
            if debug:
                return [], [{"title": "(none)", "url": api_url, "selector": "ashby_api", "reason": f"HTTP {resp.status_code}"}]
            return []

        data = json.loads(resp.text)

        # Ashby embeds ID→name mappings in the page HTML, not in the API response.
        # Fetch page once to resolve both departmentId and locationId filters.
        dept_names = set()
        loc_names = set()
        team_names = set()
        if filter_dept_ids or filter_location_ids or filter_team_ids:
            try:
                page_resp = await client.get(url, headers={"Accept": "text/html", "User-Agent": _USER_AGENT})
                page_text = page_resp.text
                for dept_id in filter_dept_ids:
                    m = re.search(
                        rf'"id"\s*:\s*"{re.escape(dept_id)}"[^}}]*?"name"\s*:\s*"([^"]+)"',
                        page_text,
                    )
                    if m:
                        dept_names.add(m.group(1))
                for loc_id in filter_location_ids:
                    # Location mapping uses "locationId"/"locationName" in job entries
                    m = re.search(
                        rf'"locationId"\s*:\s*"{re.escape(loc_id)}"[^}}]*?"locationName"\s*:\s*"([^"]+)"',
                        page_text,
                    )
                    if m:
                        loc_names.add(m.group(1))
                for team_id in filter_team_ids:
                    m = re.search(
                        rf'"id"\s*:\s*"{re.escape(team_id)}"[^}}]*?"name"\s*:\s*"([^"]+)"',
                        page_text,
                    )
                    if m:
                        team_names.add(m.group(1))
                logger.info(f"Ashby: resolved depts={dept_names}, locs={loc_names}, teams={team_names}")
            except Exception as e:
                logger.warning(f"Ashby: could not resolve filter names: {e}")

        for posting in data.get("jobs", []):
            if not posting.get("isListed", True):
                continue

            title = (posting.get("title") or "").strip()
            job_url = posting.get("jobUrl") or ""

            # Apply department filter if specified
            if dept_names:
                job_dept = (posting.get("department") or "").strip()
                if job_dept not in dept_names:
                    if debug:
                        rejected.append({"title": title, "url": job_url, "selector": "ashby_api", "reason": f"Department '{job_dept}' not in filter {dept_names}"})
                    continue

            # Apply team filter if specified
            if team_names:
                job_team = (posting.get("team") or "").strip()
                if job_team not in team_names:
                    if debug:
                        rejected.append({"title": title, "url": job_url, "selector": "ashby_api", "reason": f"Team '{job_team}' not in filter {team_names}"})
                    continue

            # Apply location filter if specified
            if loc_names:
                job_loc = (posting.get("location") or "").strip()
                if not any(ln.lower() in job_loc.lower() for ln in loc_names):
                    if debug:
                        rejected.append({"title": title, "url": job_url, "selector": "ashby_api", "reason": f"Location '{job_loc}' not in filter {loc_names}"})
                    continue

            reason = _validate_job(title, job_url)
            if reason is None:
                jobs.append({"title": title, "url": job_url})
            elif debug:
                rejected.append({"title": title, "url": job_url, "selector": "ashby_api", "reason": reason})

    logger.info(f"Ashby API: fetched {len(jobs)} jobs for {company_slug}")
    if debug:
        return jobs, rejected
    return jobs


# ── Google Careers scraper (Playwright DOM) ────────────────────────────────

def _is_google_careers(url: str) -> bool:
    """Check if URL is a Google Careers job search page."""
    return "google.com/about/careers" in url.lower()


async def _scrape_google_careers(url: str, browser=None, debug: bool = False) -> list[dict] | tuple:
    """Scrape Google Careers using Playwright DOM extraction.

    Job cards are <li class="lLd3Je"> with <h3 class="QJPWVe"> for titles
    and <a href="jobs/results/{id}-slug"> for links.
    Pagination via <a aria-label="Go to next page">.
    """
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
        while page_num < 50:  # Safety limit
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


# ── Meta Careers scraper (Playwright DOM) ──────────────────────────────────

def _is_meta_careers(url: str) -> bool:
    """Check if URL is a Meta Careers job search page."""
    return _host_matches(url, "metacareers.com")


async def _scrape_meta_careers(url: str, browser=None, debug: bool = False) -> list[dict] | tuple:
    """Scrape Meta Careers using Playwright DOM extraction.

    Meta renders job cards client-side via React. Each card is an <a> linking to
    /profile/job_details/{job_id} with an <h3> for the title. URL query params
    handle all filtering (roles, offices, teams) server-side.
    Pagination via "next" button (aria-label='Button to select next week').
    """
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
        while page_num < 20:  # Safety limit
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


# ── Rippling scraper ────────────────────────────────────────────────────────

def _is_rippling(url: str) -> bool:
    """Check if URL is a Rippling ATS board (ats.rippling.com or rippling.com/careers)."""
    if _host_matches(url, "ats.rippling.com"):
        return True
    return _host_matches(url, "rippling.com") and _path_contains(url, "/careers")


def _parse_rippling_url(url: str) -> tuple[str, dict]:
    """Parse Rippling URL into (board_slug, query_filters).

    Supported URL formats:
      - https://ats.rippling.com/{slug}/jobs?department=Product&workLocation=...
      - https://www.rippling.com/careers/open-roles  (defaults to board slug 'rippling')
    """
    from urllib.parse import parse_qs

    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    filters = {}

    # Extract board slug from ats.rippling.com/{slug}/...
    if _host_matches(url, "ats.rippling.com"):
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        slug = parts[0] if parts else "rippling"
    else:
        # rippling.com/careers/... → default board
        slug = "rippling"

    if "department" in qs:
        filters["department"] = qs["department"][0]
    if "workLocation" in qs:
        filters["workLocation"] = qs["workLocation"][0]
    if "searchTerm" in qs:
        filters["searchTerm"] = qs["searchTerm"][0]

    return slug, filters


async def _scrape_rippling(url: str, debug: bool = False) -> list[dict] | tuple:
    """Fetch jobs from Rippling's public ATS API.

    API returns a flat JSON array of all jobs. The server-side filter params
    are unreliable, so department/workLocation filtering is done client-side.
    Multi-location jobs appear multiple times (same UUID, different workLocation);
    we deduplicate by UUID, preferring locations that match the filter.
    """
    import json

    slug, filters = _parse_rippling_url(url)
    api_url = f"https://api.rippling.com/platform/api/ats/v1/board/{slug}/jobs"
    filter_dept = filters.get("department", "").lower()
    filter_loc = filters.get("workLocation", "").lower()

    logger.info(f"Rippling API: {api_url} dept_filter='{filter_dept}' loc_filter='{filter_loc}'")

    jobs = []
    rejected = []

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        # Fetch all jobs — don't pass filter params (API ignores them)
        resp = await client.get(api_url)
        if resp.status_code != 200:
            logger.warning(f"Rippling API returned {resp.status_code} for {slug}")
            if debug:
                return [], [{"title": "(none)", "url": api_url, "selector": "rippling_api", "reason": f"HTTP {resp.status_code}"}]
            return []

        postings = json.loads(resp.text)
        logger.info(f"Rippling API: {len(postings)} entries for {slug}")

        # Deduplicate by UUID — multi-location jobs repeat with different workLocation.
        # Keep the entry whose location best matches the filter.
        seen_uuids: dict[str, list] = {}
        for posting in postings:
            uuid = posting.get("uuid", "")
            seen_uuids.setdefault(uuid, []).append(posting)

        logger.info(f"Rippling API: {len(seen_uuids)} unique jobs after UUID dedup")

        for uuid, entries in seen_uuids.items():
            # Pick the best location entry: prefer filter match, then US, then first
            best = entries[0]
            all_locs = []
            for e in entries:
                loc = e.get("workLocation", {})
                loc_label = loc.get("label", "") if isinstance(loc, dict) else str(loc)
                all_locs.append(loc_label)
                if filter_loc and filter_loc in loc_label.lower():
                    best = e
                elif not filter_loc and "United States" in loc_label:
                    best = e

            title = (best.get("name") or "").strip()
            job_url = best.get("url") or ""
            dept = best.get("department", {})
            dept_label = dept.get("label", "") if isinstance(dept, dict) else str(dept)
            loc = best.get("workLocation", {})
            loc_label = loc.get("label", "") if isinstance(loc, dict) else str(loc)

            # Department filter (case-insensitive match)
            if filter_dept and filter_dept != dept_label.lower():
                if debug:
                    rejected.append({"title": title, "url": job_url, "selector": "rippling_api",
                                     "reason": f"Department '{dept_label}' != '{filters.get('department', '')}'"})
                continue

            # Location filter — check if ANY of the job's locations match.
            # "United States" also matches "City, ST" patterns (2-letter US state codes).
            if filter_loc:
                def _loc_matches(loc_str: str) -> bool:
                    lower = loc_str.lower()
                    if filter_loc in lower:
                        return True
                    # US filter: match "City, XX" where XX is a US state abbreviation
                    if "united states" in filter_loc:
                        parts = loc_str.rsplit(", ", 1)
                        if len(parts) == 2 and re.match(r'^[A-Z]{2}$', parts[1]):
                            return True
                    return False

                if not any(_loc_matches(loc) for loc in all_locs):
                    if debug:
                        rejected.append({"title": title, "url": job_url, "selector": "rippling_api",
                                         "reason": f"No location matches '{filters.get('workLocation', '')}' (has: {', '.join(all_locs[:3])})"})
                    continue

            reason = _validate_job(title, job_url)
            if reason is None:
                jobs.append({"title": title, "url": job_url})
            elif debug:
                rejected.append({"title": title, "url": job_url, "selector": "rippling_api", "reason": reason})

    logger.info(f"Rippling API: fetched {len(jobs)} jobs for {slug}")
    if debug:
        return jobs, rejected
    return jobs


# ── Main scrape function ─────────────────────────────────────────────────────

async def scrape_single_career_page(company: Company, shared_browser=None) -> dict:
    """Scrape a single company career page using Playwright.

    Uses company.scrape_urls (unified list of career/search URLs).
    If shared_browser is provided, uses it instead of launching a new one.
    """
    start_time = time.time()

    target_urls = company.scrape_urls or []

    # Filter empty strings
    target_urls = [u.strip() for u in target_urls if u and u.strip()]

    if not target_urls:
        return {"jobs_found": 0, "new_jobs": 0, "error": "No career page URLs"}

    own_browser = shared_browser is None
    pw = None
    browser = shared_browser
    try:
        if own_browser:
            pw, browser = await _get_browser()
        max_pages = getattr(company, 'max_pages', 5) or 5
        unique_jobs = []
        seen_urls = set()

        for target_url in target_urls:
            try:
                # HTTP-based scrapers (no Playwright needed)
                if _is_phenom_post(target_url):
                    page_jobs = await _scrape_phenom(target_url)
                elif _is_talentbrew_ajax(target_url):
                    page_jobs = await _scrape_talentbrew_ajax(target_url)
                elif _is_oracle_hcm(target_url):
                    page_jobs = await _scrape_oracle_hcm(target_url)
                elif _is_lever(target_url):
                    page_jobs = await _scrape_lever(target_url)
                elif _is_workday(target_url):
                    page_jobs = await _scrape_workday(target_url)
                elif _is_ashby(target_url):
                    page_jobs = await _scrape_ashby(target_url)
                elif _is_greenhouse(target_url):
                    page_jobs = await _scrape_greenhouse(target_url)
                elif _is_rippling(target_url):
                    page_jobs = await _scrape_rippling(target_url)
                elif _is_meta_careers(target_url):
                    page_jobs = await _scrape_meta_careers(target_url, browser=browser)
                elif _is_google_careers(target_url):
                    page_jobs = await _scrape_google_careers(target_url, browser=browser)
                else:
                    page = await _new_page(browser)
                    await _setup_route_blocks(page)
                    await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
                    wait_sel = getattr(company, 'wait_for_selector', None)
                    await _wait_for_content(page, wait_sel)
                    page_jobs = await _extract_all_pages(page, target_url, max_pages, wait_for_selector=wait_sel)
                    await _close_page(page)
                for j in page_jobs:
                    if j["url"] not in seen_urls:
                        seen_urls.add(j["url"])
                        unique_jobs.append(j)
            except Exception as e:
                logger.warning(f"Scrape error on {target_url}: {e}")

        if not unique_jobs:
            duration = time.time() - start_time
            return {"jobs_found": 0, "new_jobs": 0, "error": None, "duration": duration}

        # Apply per-company + global title filters
        from backend.models.db import get_global_title_exclude
        _gte_db = SessionLocal()
        try:
            _global_title_excl = get_global_title_exclude(_gte_db)
        finally:
            _gte_db.close()
        filtered_out = []
        has_filters = (
            (company.title_include_expr and company.title_include_expr.strip())
            or (company.title_exclude_keywords and len(company.title_exclude_keywords) > 0)
            or _global_title_excl
        )
        if has_filters:
            before_count = len(unique_jobs)
            unique_jobs, filtered_out = _apply_company_filters(unique_jobs, company, _global_title_excl)
            logger.info(
                f"Keyword filter for {company.name}: {before_count} -> {len(unique_jobs)} kept, {len(filtered_out)} ignored"
            )

        # Save to DB
        db = SessionLocal()
        new_jobs = 0
        try:
            existing_ids = get_existing_external_ids(db)

            # Pre-filter jobs that need description fetching (not already in DB)
            jobs_needing_desc = []
            for j in unique_jobs:
                ext_id = make_external_id(company.name, j["title"], j["url"])
                content_hash = make_content_hash(company.name, j["title"])
                if ext_id in existing_ids:
                    continue
                j["_ext_id"] = ext_id
                j["_content_hash"] = content_hash
                jobs_needing_desc.append(j)

            # Fetch descriptions in parallel for new jobs
            if jobs_needing_desc:
                desc_results = await _fetch_descriptions_parallel(jobs_needing_desc)
                desc_map = {}
                for result in desc_results:
                    if isinstance(result, Exception):
                        continue
                    job_dict, desc = result
                    desc_map[job_dict["url"]] = desc
            else:
                desc_map = {}

            for j in jobs_needing_desc:
                ext_id = j["_ext_id"]
                content_hash = j["_content_hash"]
                desc = desc_map.get(j["url"])

                job = Job(
                    external_id=ext_id,
                    content_hash=content_hash,
                    company=company.name,
                    title=j["title"],
                    url=j["url"],
                    source="direct",
                    status="new",
                    seen=False,
                    saved=False,
                    description=desc,
                )

                # Run H-1B check + salary extraction
                # Always run even without description — company-level LCA check doesn't need it
                try:
                    from backend.analyzer.h1b_checker import check_job_h1b
                    from backend.analyzer.salary_extractor import apply_salary_to_job
                    await check_job_h1b(job, db)
                    h1b_median = company.h1b_median_salary if hasattr(company, 'h1b_median_salary') else None
                    apply_salary_to_job(job, h1b_median)
                except Exception as analysis_err:
                    logger.warning(f"Inline analysis failed for {j['title']}: {analysis_err}")

                # Skip jobs flagged for body exclusion
                if job.h1b_jd_flag:
                    logger.info(f"Skipping job (body exclusion): {j['title']} — {job.h1b_jd_snippet}")
                    job.status = "ignored"

                try:
                    with db.begin_nested():
                        db.add(job)
                        db.flush()
                    if job.status == "new":
                        new_jobs += 1
                    existing_ids.add(ext_id)
                except IntegrityError:
                    logger.debug(f"Duplicate external_id for '{j['title']}' at {company.name}, skipping")
                    continue

            # Save filtered-out jobs as "ignored" for dedup purposes
            for j in filtered_out:
                ext_id = make_external_id(company.name, j["title"], j["url"])
                if ext_id in existing_ids:
                    continue

                job = Job(
                    external_id=ext_id,
                    content_hash=make_content_hash(company.name, j["title"]),
                    company=company.name,
                    title=j["title"],
                    url=j["url"],
                    source="direct",
                    status="ignored",
                    seen=False,
                    saved=False,
                )
                try:
                    with db.begin_nested():
                        db.add(job)
                        db.flush()
                    existing_ids.add(ext_id)
                except IntegrityError:
                    continue

            comp = db.query(Company).filter(Company.id == company.id).first()
            if comp:
                comp.last_scraped_at = datetime.now(timezone.utc)

            db.commit()
        finally:
            db.close()

        duration = time.time() - start_time

        from backend.activity import log_activity
        log_activity("scrape", f"Playwright {company.name}: {new_jobs} new / {len(unique_jobs)} found in {duration:.1f}s", company=company.name)

        return {"jobs_found": len(unique_jobs), "new_jobs": new_jobs, "error": None, "duration": duration}

    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Playwright scrape failed for {company.name}: {e}")

        from backend.activity import log_activity
        log_activity("scrape", f"Playwright {company.name} failed: {e}", company=company.name)

        return {"jobs_found": 0, "new_jobs": 0, "error": str(e), "duration": duration}
    finally:
        if own_browser:
            if browser:
                await browser.close()
            if pw:
                await pw.stop()


# ── Batch scraper ─────────────────────────────────────────────────────────────

async def scrape_career_pages(force: bool = False):
    """Scrape career pages for all active companies with playwright_enabled=True.

    Per-company intervals: if company.scrape_interval_minutes is set, skip
    companies that were scraped more recently than their interval. Otherwise
    use the global scrape_interval_minutes setting (companies are always
    scraped when the global scheduler fires, unless they have a custom interval).

    If force=True, skip interval checks entirely (used by manual triggers).

    Launches ONE shared browser for all companies that need Playwright,
    instead of one browser per company.
    """
    from backend.models.db import Setting
    db = SessionLocal()
    shared_pw = None
    shared_browser = None
    try:
        # Read global default interval
        global_interval_row = db.query(Setting).filter(Setting.key == "scrape_interval_minutes").first()
        global_interval = int(global_interval_row.value) if global_interval_row else 60

        companies = db.query(Company).filter(
            Company.active == True,
            Company.playwright_enabled == True,
        ).all()

        companies = [
            c for c in companies
            if c.scrape_urls and any(u.strip() for u in c.scrape_urls)
        ]

        logger.info(f"Playwright: {len(companies)} companies with scrape URLs")

        # Check if any company needs a real browser (not just API-based scrapers)
        def _needs_browser(urls):
            for u in urls:
                u = (u or "").strip()
                if not u:
                    continue
                if (_is_phenom_post(u) or _is_talentbrew_ajax(u) or _is_oracle_hcm(u)
                        or _is_lever(u) or _is_workday(u) or _is_ashby(u)
                        or _is_greenhouse(u) or _is_rippling(u)):
                    continue
                # Meta, Google, levels.fyi, or generic Playwright — needs browser
                return True
            return False

        # Launch shared browser if any company needs it
        any_needs_browser = any(_needs_browser(c.scrape_urls or []) for c in companies)
        if any_needs_browser:
            shared_pw, shared_browser = await _get_browser()
            logger.info("Playwright: launched shared browser for batch scrape")

        now = datetime.now(timezone.utc)
        for company in companies:
            # Per-company interval check (skipped for manual triggers)
            if not force:
                interval = company.scrape_interval_minutes or global_interval
                if company.last_scraped_at:
                    elapsed = (now - company.last_scraped_at).total_seconds() / 60
                    if elapsed < interval:
                        logger.debug(f"Skipping {company.name}: scraped {elapsed:.0f}m ago (interval={interval}m)")
                        continue

            result = await scrape_single_career_page(company, shared_browser=shared_browser)

            is_warning = (
                result.get("jobs_found", 0) == 0
                and not result.get("error")
            )

            log = ScrapeLog(
                source=f"playwright_{company.name}",
                company_id=company.id,
                jobs_found=result.get("jobs_found", 0),
                new_jobs=result.get("new_jobs", 0),
                error=result.get("error"),
                is_warning=is_warning,
                duration_seconds=result.get("duration", 0),
            )
            db.add(log)
            db.commit()

            logger.info(
                f"Playwright {company.name}: found={result['jobs_found']}, new={result['new_jobs']}"
            )

            # Auto CV-score if company has auto_scoring_depth enabled
            if company.auto_scoring_depth in ("light", "full") and result.get("new_jobs", 0) > 0:
                from backend.analyzer.cv_scorer import analyze_unscored_jobs
                await analyze_unscored_jobs(status="new")

            await asyncio.sleep(2)

    finally:
        if shared_browser:
            await shared_browser.close()
        if shared_pw:
            await shared_pw.stop()
        db.close()


# ── Search-level URL mode scraper ─────────────────────────────────────────────

async def scrape_url_mode(search: Search) -> dict:
    """URL mode: visit a direct URL and extract job listings via Playwright."""
    start_time = time.time()

    if not search.direct_url:
        return {"jobs_found": 0, "new_jobs": 0, "error": "No direct URL configured"}

    pw = None
    browser = None
    try:
        pw, browser = await _get_browser()
        page = await _new_page(browser)
        try:
            await _setup_route_blocks(page)

            await page.goto(search.direct_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)

            unique_jobs = await _extract_all_pages(page, search.direct_url, max_pages=5)
        finally:
            await _close_page(page)

        db = SessionLocal()
        new_jobs = 0
        try:
            existing_ids = get_existing_external_ids(db)

            # Pre-filter and fetch descriptions in parallel
            jobs_needing_desc = []
            for j in unique_jobs:
                ext_id = make_external_id("", j["title"], j["url"])
                content_hash = make_content_hash("", j["title"])
                if ext_id in existing_ids:
                    continue
                j["_ext_id"] = ext_id
                j["_content_hash"] = content_hash
                jobs_needing_desc.append(j)

            if jobs_needing_desc:
                desc_results = await _fetch_descriptions_parallel(jobs_needing_desc)
                desc_map = {}
                for result in desc_results:
                    if isinstance(result, Exception):
                        continue
                    job_dict, desc = result
                    desc_map[job_dict["url"]] = desc
            else:
                desc_map = {}

            for j in jobs_needing_desc:
                ext_id = j["_ext_id"]
                content_hash = j["_content_hash"]
                desc = desc_map.get(j["url"])

                job = Job(
                    external_id=ext_id,
                    content_hash=content_hash,
                    company="",
                    title=j["title"],
                    url=j["url"],
                    source="playwright_direct",
                    search_id=search.id,
                    status="new",
                    seen=False,
                    saved=False,
                    description=desc,
                )

                try:
                    from backend.analyzer.h1b_checker import check_job_h1b
                    from backend.analyzer.salary_extractor import apply_salary_to_job
                    await check_job_h1b(job, db)
                    apply_salary_to_job(job)
                except Exception as analysis_err:
                    logger.warning(f"Inline analysis failed for {j['title']}: {analysis_err}")

                if job.h1b_jd_flag:
                    job.status = "ignored"

                try:
                    with db.begin_nested():
                        db.add(job)
                        db.flush()
                    if job.status == "new":
                        new_jobs += 1
                    existing_ids.add(ext_id)
                except IntegrityError:
                    continue

            search_obj = db.query(Search).filter(Search.id == search.id).first()
            if search_obj:
                search_obj.last_run_at = datetime.now(timezone.utc)

            db.commit()
        finally:
            db.close()

        duration = time.time() - start_time

        from backend.activity import log_activity
        log_activity("scrape", f"URL mode '{search.name}': {new_jobs} new / {len(unique_jobs)} found in {duration:.1f}s")

        return {"jobs_found": len(unique_jobs), "new_jobs": new_jobs, "error": None, "duration": duration}

    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"URL mode scrape failed for '{search.name}': {e}")

        from backend.activity import log_activity
        log_activity("scrape", f"URL mode '{search.name}' failed: {e}")

        return {"jobs_found": 0, "new_jobs": 0, "error": str(e), "duration": duration}
    finally:
        if browser:
            await browser.close()
        if pw:
            await pw.stop()


# ── Levels.fyi scraper ────────────────────────────────────────────────────────

def _is_levelsfyi(url: str) -> bool:
    """Check if URL is a levels.fyi job search page."""
    return "levels.fyi" in url.lower() and "/jobs" in url.lower()


def _parse_levelsfyi_salary(location_text: str) -> tuple[str, str | None, int | None, int | None]:
    """Parse levels.fyi location+salary string like 'San Francisco, CA · Remote · $200K - $300K'.
    Returns (location, work_arrangement, salary_min, salary_max).
    """
    if not location_text:
        return ("", None, None, None)

    # The separator can be a unicode middle dot or a regular dot
    parts = [p.strip() for p in re.split(r'\s*[·\u00b7]\s*', location_text)]
    location = parts[0] if parts else ""
    work_arrangement = None
    salary_min = salary_max = None

    for part in parts[1:]:
        part_lower = part.lower().strip()
        if part_lower in ("remote", "on-site", "hybrid"):
            work_arrangement = part.strip()
        elif "$" in part:
            amounts = re.findall(r'\$(\d+(?:\.\d+)?)\s*[Kk]?', part)
            for i, amt in enumerate(amounts):
                val = int(float(amt))
                if val < 10000:
                    val *= 1000
                if i == 0:
                    salary_min = val
                elif i == 1:
                    salary_max = val

    return (location, work_arrangement, salary_min, salary_max)


async def _levelsfyi_extract_jobs_from_card(card, page, seen_ids: set, debug: bool = False):
    """Extract all job links from a single company card. Returns (jobs, rejected)."""
    jobs = []
    rejected_list = []

    company_name = ""
    try:
        h2 = await card.query_selector('h2')
        if h2:
            company_name = (await h2.inner_text()).strip()
    except Exception:
        pass

    scope = card if card else page
    links = await scope.query_selector_all('a[href*="jobId="]')

    for link in links:
        href = await link.get_attribute("href") or ""
        if not href:
            continue

        job_id_match = re.search(r'jobId=(\d+)', href)
        if not job_id_match:
            continue
        job_id = job_id_match.group(1)
        if job_id in seen_ids:
            continue
        seen_ids.add(job_id)

        title = ""
        try:
            title_el = await link.query_selector('[class*="__companyJobTitle"]')
            if title_el:
                title = await title_el.evaluate("""el => {
                    const clone = el.cloneNode(true);
                    const spans = clone.querySelectorAll('span');
                    spans.forEach(s => s.remove());
                    return clone.textContent.trim();
                }""")
        except Exception:
            pass

        location = ""
        salary_min = salary_max = None
        try:
            loc_el = await link.query_selector('[class*="__companyJobLocation"]')
            if loc_el:
                loc_text = (await loc_el.inner_text()).strip()
                location, _, salary_min, salary_max = _parse_levelsfyi_salary(loc_text)
        except Exception:
            pass

        date_posted = ""
        try:
            date_el = await link.query_selector('[class*="__companyJobDate"]')
            if date_el:
                date_posted = (await date_el.inner_text()).strip()
        except Exception:
            pass

        job_url = f"https://www.levels.fyi/jobs?jobId={job_id}"

        if not title:
            if debug:
                rejected_list.append({"title": "(empty)", "url": job_url, "company": company_name, "reason": "No title"})
            continue

        jobs.append({
            "title": title,
            "url": job_url,
            "company": company_name,
            "location": location,
            "salary_min": salary_min,
            "salary_max": salary_max,
            "date_posted": date_posted,
        })

    return jobs, rejected_list


async def _levelsfyi_extract_detail(page, job_url: str) -> dict:
    """Visit a levels.fyi job detail page and extract application URL, salary, and description.

    Extracts from __NEXT_DATA__ JSON: pageProps.initialJobDetails contains
    applicationUrl, minBaseSalary/maxBaseSalary, baseSalaryCurrency, description.
    Returns dict with application_url, salary_min, salary_max, description.
    """
    result = {"application_url": None, "salary_min": None, "salary_max": None, "description": None}

    try:
        await page.goto(job_url, wait_until="domcontentloaded", timeout=20000)

        # __NEXT_DATA__ is SSR — available immediately on domcontentloaded
        try:
            next_data = await page.evaluate("""() => {
                const el = document.getElementById('__NEXT_DATA__');
                if (!el) return null;
                try { return JSON.parse(el.textContent); } catch { return null; }
            }""")

            if next_data:
                props = next_data.get("props", {}).get("pageProps", {})
                job_data = (
                    props.get("initialJobDetails")
                    or props.get("job")
                    or props.get("jobData")
                    or props.get("initialJob")
                    or {}
                )

                # Application URL
                app_url = job_data.get("applicationUrl") or job_data.get("applyUrl") or ""
                if app_url:
                    result["application_url"] = _clean_application_url(app_url)

                # Description (plain text from JSON)
                desc = job_data.get("description") or ""
                if len(desc) > 50:
                    result["description"] = desc[:30000]

                # Salary: prefer base, fallback to total (USD only)
                currency = (job_data.get("baseSalaryCurrency") or job_data.get("currency") or "USD").upper()
                if currency == "USD":
                    sal_min = job_data.get("minBaseSalary") or job_data.get("minTotalSalary")
                    sal_max = job_data.get("maxBaseSalary") or job_data.get("maxTotalSalary")
                    if sal_min and isinstance(sal_min, (int, float)) and sal_min > 0:
                        result["salary_min"] = int(sal_min)
                    if sal_max and isinstance(sal_max, (int, float)) and sal_max > 0:
                        result["salary_max"] = int(sal_max)
        except Exception as e:
            logger.debug(f"levels.fyi detail __NEXT_DATA__ extraction failed for {job_url}: {e}")

    except Exception as e:
        logger.debug(f"levels.fyi detail page failed for {job_url}: {e}")

    return result


async def _scrape_levelsfyi(url: str, browser=None, debug: bool = False, max_pages: int = 50) -> list[dict] | tuple:
    """Scrape levels.fyi job listings using Playwright DOM extraction.

    levels.fyi encrypts its API responses, so we must render the page and extract
    from the DOM. Job cards are grouped by company, with a[href*="jobId="] links
    containing title, location, and salary info.

    Strategy:
    1. Load the page with filters from URL
    2. Pass 1 — Paginate: extract visible jobs from each page
    3. Pass 3 — Enrich: fetch detail pages for application URLs, descriptions, salaries

    Returns list of dicts with title, url, company, location, salary_min, salary_max.
    If debug=True, returns tuple: (jobs, rejected).
    """
    own_browser = browser is None
    pw = None
    if own_browser:
        pw, browser = await _get_browser()

    jobs = []
    rejected = []
    page = None
    page_num = 0
    try:
        page = await _new_page(browser)
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)

        # Wait for job cards to render (client-side decryption + React render)
        try:
            await page.wait_for_selector('a[href*="jobId="]', timeout=20000)
        except Exception:
            logger.warning("levels.fyi: job card selector timed out, trying fallback wait")
            await asyncio.sleep(8)
        await asyncio.sleep(3)

        # Dismiss cookie consent + onboarding modal overlay via JS
        # (Playwright .click() fails because the onboarding overlay intercepts pointer events)
        try:
            await page.evaluate("""() => {
                // Accept cookies via JS click (bypasses overlay)
                const cookieBtn = document.querySelector('[data-cky-tag="accept-button"]');
                if (cookieBtn) cookieBtn.click();
                // Remove onboarding overlay that blocks pointer events
                // Do NOT click closeButton — it triggers React re-render that unmounts content
                document.querySelectorAll('[class*="onboarding-modal"][class*="overlay"]').forEach(el => el.remove());
            }""")
        except Exception:
            pass

        seen_ids = set()

        # ── Pass 1: Paginate through search results ──────────────────────
        while page_num < max_pages:
            page_num += 1

            # Primary card selector, with fallback using :has() pseudo-class
            cards = await page.query_selector_all('[class*="company-jobs-preview-card"][class*="__container"]')
            if not cards:
                cards = await page.query_selector_all('div:has(> a[href*="jobId="])')
            if not cards:
                cards = [None]

            page_count = 0
            for card in cards:
                card_jobs, card_rejected = await _levelsfyi_extract_jobs_from_card(card, page, seen_ids, debug)
                jobs.extend(card_jobs)
                rejected.extend(card_rejected)
                page_count += len(card_jobs)

            logger.info(f"levels.fyi: page {page_num} — {page_count} new jobs ({len(jobs)} total)")

            # Click next pagination button
            has_next = False
            try:
                pag_buttons = await page.query_selector_all('[class*="paginationButton"] button.MuiButton-root')
                if not pag_buttons:
                    logger.info("levels.fyi: no pagination buttons, single page")
                    break

                next_page = page_num + 1
                for btn in pag_buttons:
                    btn_text = (await btn.inner_text()).strip()
                    if btn_text == str(next_page):
                        # Snapshot current job IDs before navigating
                        old_links = await page.query_selector_all('a[href*="jobId="]')
                        old_first_href = ""
                        if old_links:
                            old_first_href = await old_links[0].get_attribute("href") or ""

                        # Use JS click to bypass any overlay interception
                        await btn.evaluate("el => el.click()")
                        has_next = True
                        logger.info(f"levels.fyi: clicked page {next_page}")

                        # Wait for React SPA re-render: either first job link changes
                        # or the clicked button becomes "outlined" (current page indicator)
                        for _wait in range(15):
                            await asyncio.sleep(1)
                            try:
                                new_links = await page.query_selector_all('a[href*="jobId="]')
                                new_first = ""
                                if new_links:
                                    new_first = await new_links[0].get_attribute("href") or ""
                                if new_first and new_first != old_first_href:
                                    break  # Content changed
                                # Also check if MUI button got outlined class (current page)
                                cur_btns = await page.query_selector_all('[class*="paginationButton"] button.MuiButton-root')
                                for cb in cur_btns:
                                    cb_text = (await cb.inner_text()).strip()
                                    cb_class = await cb.get_attribute("class") or ""
                                    if cb_text == str(next_page) and "outlined" in cb_class.lower():
                                        break
                                else:
                                    continue
                                break  # outlined button found
                            except Exception:
                                continue
                        else:
                            logger.warning(f"levels.fyi: page {next_page} content didn't change after 15s")

                        await asyncio.sleep(1)  # Extra settle time
                        break

                if not has_next:
                    logger.info(f"levels.fyi: no button for page {next_page}, done paginating")
                    break

            except Exception as e:
                logger.warning(f"levels.fyi pagination error: {e}")
                break

            if page_count == 0 and page_num > 2:
                logger.info("levels.fyi: 0 new jobs for 2+ consecutive pages, stopping")
                break

        # ── Pass 3: Enrich jobs with detail page data (concurrent) ────────
        if jobs:
            NUM_TABS = 5
            start_p3 = time.time()
            logger.info(f"levels.fyi: Pass 3 — enriching {len(jobs)} jobs with {NUM_TABS} tabs")
            enriched = 0
            detail_pages = []

            try:
                for _ in range(NUM_TABS):
                    detail_pages.append(await _new_page(browser))

                # Each tab processes its own slice — no contention
                async def _worker(_tab_idx, pg, job_slice):
                    nonlocal enriched
                    for j in job_slice:
                        job_id_match = re.search(r'jobId=(\d+)', j["url"])
                        if not job_id_match:
                            continue
                        detail_url = f"https://www.levels.fyi/jobs?jobId={job_id_match.group(1)}"
                        try:
                            detail = await _levelsfyi_extract_detail(pg, detail_url)
                            if detail.get("application_url"):
                                j["application_url"] = detail["application_url"]
                            if detail.get("description"):
                                j["description"] = detail["description"]
                            if detail.get("salary_min") and (not j.get("salary_min") or detail["salary_min"] != j["salary_min"]):
                                j["salary_min"] = detail["salary_min"]
                                j["salary_max"] = detail.get("salary_max")
                            enriched += 1
                        except Exception as e:
                            logger.debug(f"levels.fyi: detail failed for {j.get('title', '?')}: {e}")

                # Split jobs into N slices, one per tab
                slices = [[] for _ in range(NUM_TABS)]
                for i, j in enumerate(jobs):
                    slices[i % NUM_TABS].append(j)

                await asyncio.gather(*[
                    _worker(idx, detail_pages[idx], slices[idx])
                    for idx in range(NUM_TABS)
                ])

                logger.info(f"levels.fyi: Pass 3 done — enriched {enriched}/{len(jobs)} jobs in {time.time() - start_p3:.1f}s")
            finally:
                for dp in detail_pages:
                    await _close_page(dp)

    except Exception as e:
        logger.error(f"levels.fyi scraper error: {e}")
        if debug:
            rejected.append({"title": "(error)", "url": url, "company": "", "reason": str(e)})
    finally:
        if page:
            await _close_page(page)
        if own_browser:
            if browser:
                await browser.close()
            if pw:
                await pw.stop()

    logger.info(f"levels.fyi: {len(jobs)} jobs extracted, {len(rejected)} rejected across {page_num} pages")
    if debug:
        return jobs, rejected
    return jobs


async def scrape_levelsfyi_mode(search: Search) -> dict:
    """Levels.fyi search mode: scrape filtered job listings and save to DB."""
    start_time = time.time()

    if not search.direct_url or not _is_levelsfyi(search.direct_url):
        return {"jobs_found": 0, "new_jobs": 0, "error": "No levels.fyi URL configured"}

    pw = None
    browser = None
    try:
        pw, browser = await _get_browser()
        search_max_pages = search.max_pages or 50
        raw_jobs = await _scrape_levelsfyi(search.direct_url, browser=browser, max_pages=search_max_pages)

        # Retry up to 3 times if 0 results (levels.fyi rate-limiting / slow render)
        retry_delays = [10, 20, 30]
        for attempt, delay in enumerate(retry_delays, 1):
            if raw_jobs:
                break
            logger.info(f"levels.fyi: 0 results, retry {attempt}/3 in {delay}s")
            await asyncio.sleep(delay)
            raw_jobs = await _scrape_levelsfyi(search.direct_url, browser=browser, max_pages=search_max_pages)

        # Apply search-level + global title filters
        from backend.models.db import get_global_title_exclude as _gte
        _gte_db2 = SessionLocal()
        try:
            _global_title_excl2 = _gte(_gte_db2)
        finally:
            _gte_db2.close()
        include_kw = search.title_include_keywords or []
        exclude_kw = list(set((search.title_exclude_keywords or []) + _global_title_excl2))
        kept_jobs = []
        for j in raw_jobs:
            title_lower = j["title"].lower()
            if include_kw and not any(kw.lower() in title_lower for kw in include_kw):
                continue
            if exclude_kw and any(re.search(r'\b' + re.escape(kw) + r'\b', title_lower) for kw in exclude_kw):
                continue
            kept_jobs.append(j)

        # Company exclude (global=full match, per-search=full match)
        db_excl = SessionLocal()
        try:
            from backend.scraper.jobspy_scraper import get_setting_value
            global_exclude = json.loads(get_setting_value(db_excl, "company_exclude_global", "[]"))
            global_exclude_set = {e.lower() for e in global_exclude}
            search_exclude_set = {e.lower() for e in (search.company_exclude or [])}
            if global_exclude_set or search_exclude_set:
                before = len(kept_jobs)
                def _company_excluded(company_name):
                    cl = (company_name or "").lower()
                    if cl in global_exclude_set:
                        return True
                    return cl in search_exclude_set
                kept_jobs = [j for j in kept_jobs if not _company_excluded(j.get("company"))]
                if len(kept_jobs) < before:
                    logger.info(f"levels.fyi: company exclude removed {before - len(kept_jobs)} jobs")

            # Body exclusion description check — drop jobs with exclusion phrases (H-1B + language)
            body_phrases_raw = get_setting_value(db_excl, "body_exclusion_phrases", "[]")
            try:
                body_phrases = json.loads(body_phrases_raw)
            except json.JSONDecodeError:
                body_phrases = []
            if body_phrases:
                from backend.analyzer.h1b_checker import scan_jd_for_h1b_flags
                before = len(kept_jobs)
                filtered = []
                for j in kept_jobs:
                    desc = j.get("description") or ""
                    if desc:
                        result = scan_jd_for_h1b_flags(desc, body_phrases)
                        if result["jd_flag"]:
                            logger.info(f"levels.fyi: body exclusion drop: {j['title']} @ {j.get('company', '?')}")
                            continue
                    filtered.append(j)
                kept_jobs = filtered
                if len(kept_jobs) < before:
                    logger.info(f"levels.fyi: body exclusion check removed {before - len(kept_jobs)} jobs")
        finally:
            db_excl.close()

        # Apply per-company title filters
        db_temp = SessionLocal()
        try:
            from collections import defaultdict
            by_company = defaultdict(list)
            for j in kept_jobs:
                by_company[j.get("company", "")].append(j)

            from backend.models.db import get_global_title_exclude
            _gte_list = get_global_title_exclude(db_temp)
            filtered_jobs = []
            for company_name, company_jobs in by_company.items():
                if not company_name:
                    # Still apply global title exclude even for unknown companies
                    if _gte_list:
                        kept, _ = _apply_company_filters(company_jobs, type('', (), {'title_include_expr': None, 'title_exclude_keywords': []})(), _gte_list)
                        filtered_jobs.extend(kept)
                    else:
                        filtered_jobs.extend(company_jobs)
                    continue
                from backend.models.db import find_company_by_name
                company_obj = find_company_by_name(db_temp, company_name)
                if company_obj and (company_obj.title_exclude_keywords or (company_obj.title_include_expr and company_obj.title_include_expr.strip()) or _gte_list):
                    kept, rej = _apply_company_filters(company_jobs, company_obj, _gte_list)
                    if rej:
                        logger.info(f"levels.fyi: company filter '{company_name}' removed {len(rej)} jobs: {[r['title'] for r in rej[:5]]}")
                    filtered_jobs.extend(kept)
                else:
                    filtered_jobs.extend(company_jobs)
            kept_jobs = filtered_jobs
        finally:
            db_temp.close()

        jobs_found = len(kept_jobs)

        # Save to DB
        db = SessionLocal()
        new_jobs = 0
        try:
            existing_ids = get_existing_external_ids(db)
            for j in kept_jobs:
                # Use application_url as primary URL if available, fallback to levels.fyi URL
                apply_url = j.get("application_url") or ""
                levelsfyi_url = j["url"]
                job_url = apply_url if apply_url else levelsfyi_url

                # Dual dedup: check both application URL and levels.fyi URL
                ext_id = make_external_id(j["company"], j["title"], job_url)
                if ext_id in existing_ids:
                    continue
                # Also check the other URL format to handle transition from old data
                if apply_url and apply_url != levelsfyi_url:
                    alt_id = make_external_id(j["company"], j["title"], levelsfyi_url)
                    if alt_id in existing_ids:
                        continue

                content_hash = make_content_hash(j["company"], j["title"])

                job = Job(
                    external_id=ext_id,
                    content_hash=content_hash,
                    company=j["company"],
                    title=j["title"],
                    url=job_url,
                    source="levels_fyi",
                    search_id=search.id,
                    location=j.get("location") or None,
                    description=j.get("description") or None,
                    status="new",
                    seen=False,
                    saved=False,
                )

                if j.get("salary_min"):
                    job.salary_min = j["salary_min"]
                    job.salary_source = "levels_fyi"
                if j.get("salary_max"):
                    job.salary_max = j["salary_max"]
                    job.salary_source = "levels_fyi"

                # H-1B check + salary extraction
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

        duration = time.time() - start_time

        from backend.activity import log_activity
        log_activity("scrape", f"levels.fyi '{search.name}': {new_jobs} new / {jobs_found} found in {duration:.1f}s")

        return {"jobs_found": jobs_found, "new_jobs": new_jobs, "error": None, "duration": duration}

    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"levels.fyi scrape failed for '{search.name}': {e}")

        from backend.activity import log_activity
        log_activity("scrape", f"levels.fyi '{search.name}' failed: {e}")

        return {"jobs_found": 0, "new_jobs": 0, "error": str(e), "duration": duration}
    finally:
        if browser:
            await browser.close()
        if pw:
            await pw.stop()
