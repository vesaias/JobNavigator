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


# ── Re-exports from ats/greenhouse (Task 8 follow-up fix) ────────────────────
from backend.scraper.ats.greenhouse import (  # noqa: F401
    is_greenhouse, scrape as _scrape_greenhouse, _parse_greenhouse_url,
)
_is_greenhouse = is_greenhouse  # back-compat alias for internal calls at lines 889, 890, 1110


# ── Re-exports from ats/lever (Task 9) ────────────────────────────────────────
from backend.scraper.ats.lever import (  # noqa: F401
    is_lever, scrape as _scrape_lever,
)
_is_lever = is_lever  # back-compat alias


# ── Re-exports from ats/ashby (Task 10) ───────────────────────────────────────
from backend.scraper.ats.ashby import (  # noqa: F401
    is_ashby, scrape as _scrape_ashby,
)
_is_ashby = is_ashby  # back-compat alias


# ── Re-exports from ats/oracle_hcm (Task 11) ──────────────────────────────────
from backend.scraper.ats.oracle_hcm import (  # noqa: F401
    is_oracle_hcm, scrape as _scrape_oracle_hcm,
    _oracle_hcm_host, _ORACLE_HCM_HOSTS,
)
_is_oracle_hcm = is_oracle_hcm  # back-compat alias


# ── Re-exports from ats/phenom (Task 12) ──────────────────────────────────────
from backend.scraper.ats.phenom import (  # noqa: F401
    is_phenom, scrape as _scrape_phenom, _parse_phenom_url,
)
_is_phenom_post = is_phenom  # back-compat alias (note: old name had _post suffix)


# ── Re-exports from ats/talentbrew (Task 13) ─────────────────────────────────
from backend.scraper.ats.talentbrew import (  # noqa: F401
    is_talentbrew, scrape as _scrape_talentbrew_ajax,
)
_is_talentbrew_ajax = is_talentbrew  # back-compat alias (note: old name had _ajax suffix)


# ── Re-exports from ats/rippling (Task 14) ───────────────────────────────────
from backend.scraper.ats.rippling import (  # noqa: F401
    is_rippling, scrape as _scrape_rippling, _parse_rippling_url,
)
_is_rippling = is_rippling  # back-compat alias


# Back-compat re-exports — Task 1 (migrated to _shared/browser.py)
from backend.scraper._shared.browser import (  # noqa: F401
    _STEALTH_ARGS, _USER_AGENT,
    _get_browser, _new_page, _close_page,
)


# ── Re-exports from ats/generic (Task 16) ────────────────────────────────────
from backend.scraper.ats.generic import (  # noqa: F401
    _setup_route_blocks, _wait_for_content,
    _extract_job_links_from_page, _extract_all_pages, _click_next_page,
)


# ── Re-exports from ats/meta + ats/google (Task 15) ──────────────────────────
from backend.scraper.ats.meta import (  # noqa: F401
    is_meta, scrape as _scrape_meta_careers,
)
_is_meta_careers = is_meta

from backend.scraper.ats.google import (  # noqa: F401
    is_google, scrape as _scrape_google_careers,
)
_is_google_careers = is_google


# ── Re-exports from sources/company_pages (Task 17) ──────────────────────────
from backend.scraper.sources.company_pages import (  # noqa: F401
    scrape_single_career_page, scrape_career_pages, scrape_url_mode,
)


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
