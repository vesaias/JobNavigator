"""Company career-pages source — orchestrates ATS dispatch per URL; _dispatch_ats detects the ATS and calls the matching ats.<name>.scrape, falling through to ats.generic.scrape if nothing matches."""
import asyncio
import logging
import time
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

from backend.models.db import (
    SessionLocal, Company, Job, ScrapeLog, get_existing_external_ids,
)
from backend.scraper._shared.browser import _get_browser, _new_page, _close_page
from backend.scraper._shared.filters import _apply_company_filters
from backend.scraper._shared.dedup import make_external_id, make_content_hash, _normalize_url
from backend.scraper.ats import (
    workday, greenhouse, lever, ashby, oracle_hcm,
    phenom, talentbrew, rippling, smartrecruiters, meta, google, generic,
)
from backend.scraper.ats._descriptions import _fetch_descriptions_parallel

logger = logging.getLogger("jobnavigator.scraper.sources.company_pages")


# ── ATS dispatcher ───────────────────────────────────────────────────────────

async def _dispatch_ats(url: str, debug: bool = False, shared_browser=None, max_pages: int | None = None):
    """Detect ATS by URL and call the matching scraper, falling back to generic; order must match the if/elif chain in scrape_single_career_page, and `max_pages` only affects Playwright-paginated scrapers (Google, Meta) since HTTP-only ones are API-driven and unbounded."""
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
    if smartrecruiters.is_smartrecruiters(url):
        return await smartrecruiters.scrape(url, debug=debug)
    if meta.is_meta(url):
        return await meta.scrape(url, browser=shared_browser, max_pages=max_pages, debug=debug)
    if google.is_google(url):
        return await google.scrape(url, browser=shared_browser, max_pages=max_pages, debug=debug)
    return await generic.scrape(url, browser=shared_browser, debug=debug)


def _ats_labels_for(urls) -> str:
    """Return a comma-separated list of distinct ATS labels for these URLs, for activity-log messages (e.g. "Acme (Greenhouse): 3 new"); strips the API/AJAX/(Playwright) suffix from detect_scrape_type's labels for compactness."""
    from backend.api.routes_companies import detect_scrape_type
    labels = set()
    for u in urls:
        u = (u or "").strip()
        if not u:
            continue
        # "Workday API" → "Workday"; "Generic (Playwright)" → "Generic"; "TalentBrew AJAX" → "TalentBrew"
        label = detect_scrape_type(u).split(" ", 1)[0]
        labels.add(label)
    if not labels:
        return "?"
    return ", ".join(sorted(labels))


def record_company_scrape_log(company_id, company_name: str, result: dict, db=None):
    """Write the per-company ScrapeLog row for one career-page scrape; single source of truth for both the batch path and the manual single-company trigger so /api/scrape-log, is_warning and /health/entities see manual runs like scheduled ones. `db` lets a caller reuse an open session."""
    own_db = db is None
    if own_db:
        db = SessionLocal()
    try:
        is_warning = (
            result.get("jobs_found", 0) == 0
            and not result.get("error")
        )
        log = ScrapeLog(
            source=f"playwright_{company_name}",
            company_id=company_id,
            jobs_found=result.get("jobs_found", 0),
            new_jobs=result.get("new_jobs", 0),
            error=result.get("error"),
            is_warning=is_warning,
            duration_seconds=result.get("duration", 0),
        )
        db.add(log)
        db.commit()
    finally:
        if own_db:
            db.close()


def _needs_browser(urls):
    """True if any URL requires a real browser (not a pure-API ATS)."""
    for u in urls:
        u = (u or "").strip()
        if not u:
            continue
        if (phenom.is_phenom(u) or talentbrew.is_talentbrew(u) or oracle_hcm.is_oracle_hcm(u)
                or lever.is_lever(u) or workday.is_workday(u) or ashby.is_ashby(u)
                or greenhouse.is_greenhouse(u) or rippling.is_rippling(u)
                or smartrecruiters.is_smartrecruiters(u)):
            continue
        # Meta, Google, levels.fyi, or generic Playwright — needs browser
        return True
    return False


# ── Per-company scraper ──────────────────────────────────────────────────────

async def scrape_single_career_page(company: Company, shared_browser=None,
                                     known_external_ids: set = None) -> dict:
    """Scrape a single company career page via company.scrape_urls, optionally reusing shared_browser; `known_external_ids`, when passed, is the batch's dedup set loaded once and mutated in place so later companies see earlier inserts."""
    start_time = time.time()

    target_urls = company.scrape_urls or []

    target_urls = [u.strip() for u in target_urls if u and u.strip()]

    if not target_urls:
        return {"jobs_found": 0, "new_jobs": 0, "error": "No career page URLs"}

    # Only launch a browser if a URL needs one; API-only ATS batches (Lever, Greenhouse, etc.)
    # skip Chromium, avoiding failures on hosts without Playwright browsers installed (CI).
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
                # Handled explicitly here (not via _dispatch_ats's generic branch) because generic
                # needs company.wait_for_selector + max_pages, not _dispatch_ats's defaults.
                if (phenom.is_phenom(target_url) or talentbrew.is_talentbrew(target_url)
                        or oracle_hcm.is_oracle_hcm(target_url) or lever.is_lever(target_url)
                        or workday.is_workday(target_url) or ashby.is_ashby(target_url)
                        or greenhouse.is_greenhouse(target_url) or rippling.is_rippling(target_url)
                        or smartrecruiters.is_smartrecruiters(target_url)
                        or meta.is_meta(target_url) or google.is_google(target_url)):
                    page_jobs = await _dispatch_ats(target_url, debug=False, shared_browser=browser, max_pages=max_pages)
                else:
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

        db = SessionLocal()
        new_jobs = 0
        try:
            existing_ids = known_external_ids if known_external_ids is not None else get_existing_external_ids(db)
            # Per-company hoist for the per-job H-1B scan, avoiding a Settings read + JSON parse
            # and a company lookup per job.
            from backend.analyzer.h1b_checker import load_exclusion_phrases
            _phrases = load_exclusion_phrases(db)
            _company_lookup = {company.name.strip().lower(): company}

            jobs_needing_desc = []
            for j in unique_jobs:
                ext_id = make_external_id(company.name, j["title"], j["url"])
                content_hash = make_content_hash(company.name, j["title"])
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
                    company=company.name,
                    title=j["title"],
                    url=_normalize_url(j["url"]) or j["url"],
                    source="direct",
                    status="new",
                    seen=False,
                    saved=False,
                    description=desc,
                )

                # Always run even without a description — the company-level LCA check doesn't need it.
                try:
                    from backend.analyzer.h1b_checker import check_job_h1b
                    from backend.analyzer.salary_extractor import apply_salary_to_job
                    await check_job_h1b(job, db, company_lookup=_company_lookup, phrases=_phrases)
                    apply_salary_to_job(job, getattr(job, "_h1b_median", None))
                except Exception as analysis_err:
                    logger.warning(f"Inline analysis failed for {j['title']}: {analysis_err}")

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
                    url=_normalize_url(j["url"]) or j["url"],
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
        ats_label = _ats_labels_for(target_urls)
        log_activity("scrape", f"{company.name} ({ats_label}): {new_jobs} new / {len(unique_jobs)} found in {duration:.1f}s", company=company.name)

        return {
            "jobs_found": len(unique_jobs),
            "new_jobs": new_jobs,
            "error": "; ".join(url_errors) if url_errors else None,
            "duration": duration,
        }

    except Exception as e:
        duration = time.time() - start_time
        ats_label = _ats_labels_for(target_urls)
        logger.error(f"{company.name} ({ats_label}) scrape failed: {e}")

        from backend.activity import log_activity
        log_activity("scrape", f"{company.name} ({ats_label}) failed: {e}", company=company.name)

        return {"jobs_found": 0, "new_jobs": 0, "error": str(e), "duration": duration}
    finally:
        if own_browser:
            if browser:
                await browser.close()
            if pw:
                await pw.stop()


# ── Batch scraper ────────────────────────────────────────────────────────────

async def scrape_career_pages(force: bool = False) -> dict:
    """Scrape career pages for every active company with a scrape URL (gated only on `active` and having a URL, deliberately not `playwright_enabled`), honoring per-company or global scrape_interval_minutes unless force=True skips interval checks; one company's failure is logged to its own ScrapeLog row without ending the batch, and one shared Playwright browser serves all companies that need it."""
    from backend.models.db import Setting
    db = SessionLocal()
    shared_pw = None
    shared_browser = None
    skipped: list[dict] = []
    scraped = 0
    failed = 0
    try:
        global_interval_row = db.query(Setting).filter(Setting.key == "scrape_interval_minutes").first()
        global_interval = int(global_interval_row.value) if global_interval_row else 60

        active = db.query(Company).filter(Company.active == True).all()

        companies = []
        for c in active:
            if c.scrape_urls and any((u or "").strip() for u in c.scrape_urls):
                companies.append(c)
            else:
                skipped.append({"name": c.name, "reason": "no scrape URLs"})

        logger.info(
            f"Playwright: {len(companies)} companies with scrape URLs"
            + (f", {len(skipped)} active without URLs" if skipped else "")
        )

        any_needs_browser = any(_needs_browser(c.scrape_urls or []) for c in companies)
        if any_needs_browser:
            shared_pw, shared_browser = await _get_browser()
            logger.info("Playwright: launched shared browser for batch scrape")

        # Dedup set loaded once for the whole batch (avoids re-materializing ~14k external_ids
        # per company); mutated in place so later companies dedup against earlier inserts.
        batch_external_ids = get_existing_external_ids(db)

        now = datetime.now(timezone.utc)
        sweep_needed = False
        for company in companies:
            # Per-company interval check; a manual run (force=True) runs every active company
            # with URLs — the interval only paces the scheduler.
            if not force:
                interval = company.scrape_interval_minutes or global_interval
                if company.last_scraped_at:
                    # a naive timestamp (SQLite, or a legacy row) is UTC
                    last = company.last_scraped_at
                    if last.tzinfo is None:
                        last = last.replace(tzinfo=timezone.utc)
                    elapsed = (now - last).total_seconds() / 60
                    if elapsed < interval:
                        logger.debug(f"Skipping {company.name}: scraped {elapsed:.0f}m ago (interval={interval}m)")
                        skipped.append({
                            "name": company.name,
                            "reason": f"not due ({elapsed:.0f}m of {interval}m)",
                        })
                        continue

            # One company's failure must never take the batch down: the scraper's own errors come
            # back as a result dict, and anything else (browser death, a DB error while logging)
            # is recorded as this company's failure so the loop carries on.
            try:
                result = await scrape_single_career_page(company, shared_browser=shared_browser,
                                                         known_external_ids=batch_external_ids)
                record_company_scrape_log(company.id, company.name, result, db=db)
                scraped += 1
                if result.get("error"):
                    failed += 1

                logger.info(
                    f"Playwright {company.name}: found={result['jobs_found']}, new={result['new_jobs']}"
                )

                # Mark for one pool sweep at batch end rather than per company — the sweep picks up
                # all unscored auto-score jobs (including retries), so per-company would re-walk it N times.
                if company.auto_scoring_depth in ("light", "full") and result.get("new_jobs", 0) > 0:
                    sweep_needed = True
            except Exception as e:
                failed += 1
                logger.exception(f"Company '{company.name}' failed, batch continues: {e}")
                try:
                    db.rollback()
                    record_company_scrape_log(
                        company.id, company.name,
                        {"jobs_found": 0, "new_jobs": 0, "error": f"{type(e).__name__}: {e}", "duration": 0},
                    )
                except Exception:
                    logger.exception(f"Could not record the failure of '{company.name}'")

            await asyncio.sleep(2)

        if sweep_needed:
            try:
                from backend.analyzer.cv_scorer import analyze_unscored_jobs
                await analyze_unscored_jobs(status="new")
            except Exception as e:
                logger.exception(f"Post-batch scoring sweep failed (scrape results are saved): {e}")

        if skipped:
            logger.info(
                "Company scrapes skipped: "
                + ", ".join(f"{s['name']} ({s['reason']})" for s in skipped)
            )
        return {"scraped": scraped, "failed": failed, "skipped": skipped}
    finally:
        if shared_browser:
            await shared_browser.close()
        if shared_pw:
            await shared_pw.stop()
        db.close()
