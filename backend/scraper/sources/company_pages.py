"""Company career-pages source — orchestrates ATS dispatch per URL.

Entry points:
  - scrape_single_career_page(company, shared_browser=None) — scrape one company's scrape_urls
  - scrape_career_pages(force=False) — batch over all active companies
  - scrape_url_mode(search) — URL-mode search handler (paste-URL)

Dispatch: _dispatch_ats(url, ...) detects the ATS by URL and calls the matching
ats.<name>.scrape; falls through to ats.generic.scrape if nothing matches.
"""
import asyncio
import logging
import time
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

from backend.models.db import (
    SessionLocal, Company, Job, ScrapeLog, Search, get_existing_external_ids,
)
from backend.scraper._shared.browser import _get_browser, _new_page, _close_page
from backend.scraper._shared.filters import _apply_company_filters
from backend.scraper._shared.dedup import make_external_id, make_content_hash
from backend.scraper.ats import (
    workday, greenhouse, lever, ashby, oracle_hcm,
    phenom, talentbrew, rippling, meta, google, generic,
)
from backend.scraper.ats._descriptions import _fetch_descriptions_parallel

logger = logging.getLogger("jobnavigator.scraper.sources.company_pages")


# ── ATS dispatcher ───────────────────────────────────────────────────────────

async def _dispatch_ats(url: str, debug: bool = False, shared_browser=None):
    """Detect ATS by URL; call the matching scraper; fall back to generic.

    Preserves the exact order of the original if/elif chain in
    scrape_single_career_page so behavior is identical.
    """
    # HTTP-based scrapers (no Playwright needed)
    if phenom.is_phenom(url):
        return await phenom.scrape(url, debug=debug)
    if talentbrew.is_talentbrew(url):
        return await talentbrew.scrape(url, debug=debug)
    if oracle_hcm.is_oracle_hcm(url):
        return await oracle_hcm.scrape(url, debug=debug)
    if lever.is_lever(url):
        return await lever.scrape(url, debug=debug)
    if workday.is_workday(url):
        return await workday.scrape(url, debug=debug)
    if ashby.is_ashby(url):
        return await ashby.scrape(url, debug=debug)
    if greenhouse.is_greenhouse(url):
        return await greenhouse.scrape(url, debug=debug)
    if rippling.is_rippling(url):
        return await rippling.scrape(url, debug=debug)
    # Playwright-based ATS scrapers (need browser)
    if meta.is_meta(url):
        return await meta.scrape(url, browser=shared_browser, debug=debug)
    if google.is_google(url):
        return await google.scrape(url, browser=shared_browser, debug=debug)
    # No ATS matched — generic fallback
    return await generic.scrape(url, browser=shared_browser, debug=debug)


def _needs_browser(urls):
    """True if any URL requires a real browser (not a pure-API ATS)."""
    for u in urls:
        u = (u or "").strip()
        if not u:
            continue
        if (phenom.is_phenom(u) or talentbrew.is_talentbrew(u) or oracle_hcm.is_oracle_hcm(u)
                or lever.is_lever(u) or workday.is_workday(u) or ashby.is_ashby(u)
                or greenhouse.is_greenhouse(u) or rippling.is_rippling(u)):
            continue
        # Meta, Google, levels.fyi, or generic Playwright — needs browser
        return True
    return False


# ── Per-company scraper ──────────────────────────────────────────────────────

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

    # Only launch a browser if at least one URL actually needs one. API-only
    # ATS batches (Lever, Greenhouse, etc.) don't need Chromium — skipping the
    # launch avoids failures on hosts without Playwright browsers installed (CI).
    needs_browser = _needs_browser(target_urls)
    own_browser = shared_browser is None and needs_browser
    pw = None
    browser = shared_browser
    try:
        if own_browser:
            pw, browser = await _get_browser()
        max_pages = getattr(company, 'max_pages', 5) or 5
        unique_jobs = []
        seen_urls = set()
        url_errors = []

        for target_url in target_urls:
            try:
                # Known-ATS dispatch; falls through to generic DOM scraper.
                # Generic path uses company.wait_for_selector + max_pages, so
                # keep its explicit handling here instead of routing through
                # _dispatch_ats's generic branch (which uses defaults).
                if (phenom.is_phenom(target_url) or talentbrew.is_talentbrew(target_url)
                        or oracle_hcm.is_oracle_hcm(target_url) or lever.is_lever(target_url)
                        or workday.is_workday(target_url) or ashby.is_ashby(target_url)
                        or greenhouse.is_greenhouse(target_url) or rippling.is_rippling(target_url)
                        or meta.is_meta(target_url) or google.is_google(target_url)):
                    page_jobs = await _dispatch_ats(target_url, debug=False, shared_browser=browser)
                else:
                    # Generic fallback with per-company wait_for_selector + max_pages
                    page = await _new_page(browser)
                    await generic._setup_route_blocks(page)
                    await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
                    wait_sel = getattr(company, 'wait_for_selector', None)
                    await generic._wait_for_content(page, wait_sel)
                    page_jobs = await generic._extract_all_pages(
                        page, target_url, max_pages, wait_for_selector=wait_sel,
                    )
                    await _close_page(page)
                for j in page_jobs:
                    if j["url"] not in seen_urls:
                        seen_urls.add(j["url"])
                        unique_jobs.append(j)
            except Exception as e:
                logger.warning(f"Scrape error on {target_url}: {e}")
                url_errors.append(f"{target_url}: {type(e).__name__}: {e}")

        if not unique_jobs:
            duration = time.time() - start_time
            return {
                "jobs_found": 0,
                "new_jobs": 0,
                "error": "; ".join(url_errors) if url_errors else None,
                "duration": duration,
            }

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
                    _phrase = getattr(job, "_h1b_matched_phrase", None) or "?"
                    logger.info(f"Skipping job (body exclusion): {j['title']} @ {j.get('company', '?')} — matched phrase: {_phrase!r}")
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

        return {
            "jobs_found": len(unique_jobs),
            "new_jobs": new_jobs,
            "error": "; ".join(url_errors) if url_errors else None,
            "duration": duration,
        }

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


# ── Batch scraper ────────────────────────────────────────────────────────────

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


# ── Search-level URL mode scraper ────────────────────────────────────────────

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
            await generic._setup_route_blocks(page)

            await page.goto(search.direct_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)

            unique_jobs = await generic._extract_all_pages(page, search.direct_url, max_pages=5)
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
