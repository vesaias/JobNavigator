"""JobSpy multi-board scraper. Reads all config from DB before each run."""
import asyncio
import json
import logging
import re
import time
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.models.db import SessionLocal, Search, Job, ScrapeLog, Setting, get_existing_external_ids
from backend.scraper.deduplicator import make_external_id, make_content_hash

logger = logging.getLogger("jobnavigator.scraper")


def get_setting_value(db: Session, key: str, default: str = "") -> str:
    row = db.query(Setting).filter(Setting.key == key).first()
    return row.value if row else default


def apply_title_filters(jobs_df, include_keywords: list, exclude_keywords: list):
    """Filter jobs by title include/exclude keywords (whole-word matching).
    Returns (kept_df, rejected_df)."""
    import pandas as pd

    if jobs_df is None or jobs_df.empty:
        return jobs_df, pd.DataFrame()

    mask = pd.Series(True, index=jobs_df.index)

    if include_keywords:
        pattern = "|".join(include_keywords)
        mask &= jobs_df["title"].str.contains(pattern, case=False, na=False)

    if exclude_keywords:
        pattern = "|".join(r'\b' + re.escape(kw) + r'\b' for kw in exclude_keywords)
        mask &= ~jobs_df["title"].str.contains(pattern, case=False, na=False, regex=True)

    return jobs_df[mask], jobs_df[~mask]


def apply_company_filter(jobs_df, company_filter: list):
    """Filter to specific companies if filter is non-empty (exact match, case-insensitive)."""
    if not company_filter or jobs_df is None or jobs_df.empty:
        return jobs_df
    cf_set = {cf.lower() for cf in company_filter}
    return jobs_df[jobs_df["company"].str.lower().isin(cf_set)]



def run_jobspy_search(search: Search, proxy_url: str = None) -> dict:
    """Execute a single JobSpy search and return results dict."""
    start_time = time.time()

    try:
        from jobspy import scrape_jobs

        # Build source list — filter out 'direct' which is Playwright
        sources = [s for s in (search.sources or []) if s != "direct"]
        if not sources:
            return {"jobs_found": 0, "new_jobs": 0, "error": "No JobSpy sources configured"}

        kwargs = {
            "site_name": sources,
            "search_term": search.search_term or "",
            "location": search.location or "United States",
            "results_wanted": search.results_wanted or 50,
            "hours_old": search.hours_old or 24,
            "job_type": search.job_type or "fulltime",
            "country_indeed": "USA",
            "verbose": 2,
        }

        if search.is_remote is not None:
            kwargs["is_remote"] = search.is_remote

        if proxy_url:
            kwargs["proxies"] = [proxy_url]

        logger.info(f"Running JobSpy search: {search.name} — term='{search.search_term}', sources={sources}")
        jobs_df = scrape_jobs(**kwargs)

        if jobs_df is None or jobs_df.empty:
            duration = time.time() - start_time
            return {"jobs_found": 0, "new_jobs": 0, "error": None, "duration": duration}

        # Apply filters (merge global title exclude with per-search)
        db_excl = SessionLocal()
        try:
            global_title_excl = json.loads(get_setting_value(db_excl, "title_exclude_global", "[]"))
        except Exception:
            global_title_excl = []
        finally:
            db_excl.close()
        merged_exclude = list(set((search.title_exclude_keywords or []) + global_title_excl))
        jobs_df, rejected_df = apply_title_filters(
            jobs_df,
            search.title_include_keywords or [],
            merged_exclude,
        )
        jobs_df = apply_company_filter(jobs_df, search.company_filter or [])

        # Company exclude (global=full match, per-search=full match)
        db_excl = SessionLocal()
        try:
            global_exclude = json.loads(get_setting_value(db_excl, "company_exclude_global", "[]"))
            global_exclude_set = {e.lower() for e in global_exclude}
            search_exclude_set = {e.lower() for e in (search.company_exclude or [])}
            if (global_exclude_set or search_exclude_set) and jobs_df is not None and not jobs_df.empty:
                before = len(jobs_df)
                def _excl(name):
                    nl = str(name).lower()
                    if nl in global_exclude_set:
                        return True
                    return nl in search_exclude_set
                mask = jobs_df["company"].apply(_excl)
                jobs_df = jobs_df[~mask]
                if len(jobs_df) < before:
                    logger.info(f"Company exclude removed {before - len(jobs_df)} jobs")
        finally:
            db_excl.close()

        jobs_found = len(jobs_df)

        # Save to DB, dedup via external_id
        db = SessionLocal()
        new_jobs = 0
        try:
            existing_ids = get_existing_external_ids(db)

            for _, row in jobs_df.iterrows():
                company = str(row.get("company", "")) or ""
                title = str(row.get("title", "")) or ""
                url = str(row.get("job_url", "")) or ""
                ext_id = make_external_id(company, title, url)

                # Skip if already exists (URL-based dedup)
                if ext_id in existing_ids:
                    continue

                content_hash = make_content_hash(company, title)

                # Map source name
                site = str(row.get("site", "")).lower()
                source_map = {
                    "linkedin": "jobspy_linkedin",
                    "indeed": "jobspy_indeed",
                    "zip_recruiter": "jobspy_zip_recruiter",
                    "google": "jobspy_google",
                }
                source = source_map.get(site, f"jobspy_{site}")

                job = Job(
                    external_id=ext_id,
                    content_hash=content_hash,
                    company=company,
                    title=title,
                    url=url,
                    source=source,
                    search_id=search.id,
                    description=str(row.get("description", "")) or None,
                    location=str(row.get("location", "")) or None,
                    remote=None,  # JobSpy doesn't always return this reliably
                    status="new",
                    seen=False,
                    saved=False,
                )

                # Extract salary if present in JobSpy results
                min_amount = row.get("min_amount")
                max_amount = row.get("max_amount")
                if min_amount and str(min_amount) != "nan":
                    try:
                        job.salary_min = int(float(min_amount))
                        job.salary_source = "posting"
                    except (ValueError, TypeError):
                        pass
                if max_amount and str(max_amount) != "nan":
                    try:
                        job.salary_max = int(float(max_amount))
                        job.salary_source = "posting"
                    except (ValueError, TypeError):
                        pass

                # Run H-1B check + language check + salary extraction inline
                try:
                    from backend.analyzer.h1b_checker import check_job_h1b
                    from backend.analyzer.salary_extractor import apply_salary_to_job
                    import asyncio
                    asyncio.run(check_job_h1b(job, db))
                    from backend.models.db import find_company_by_name
                    company_obj = find_company_by_name(db, company)
                    h1b_median = company_obj.h1b_median_salary if company_obj else None
                    apply_salary_to_job(job, h1b_median)
                except Exception as analysis_err:
                    logger.warning(f"Inline analysis failed for {title}: {analysis_err}")

                # Skip jobs whose description contains exclusion phrases
                if job.h1b_jd_flag:
                    logger.info(f"Skipping job (body exclusion): {title} — {job.h1b_jd_snippet}")
                    continue

                try:
                    with db.begin_nested():
                        db.add(job)
                        db.flush()
                    new_jobs += 1
                    existing_ids.add(ext_id)
                except IntegrityError:
                    logger.debug(f"Duplicate external_id for '{title}' at {company}, skipping")
                    continue

            # Save filtered-out jobs as "ignored" for dedup purposes
            if rejected_df is not None and not rejected_df.empty:
                for _, row in rejected_df.iterrows():
                    company = str(row.get("company", "")) or ""
                    title = str(row.get("title", "")) or ""
                    url = str(row.get("job_url", "")) or ""
                    ext_id = make_external_id(company, title, url)

                    if ext_id in existing_ids:
                        continue

                    site = str(row.get("site", "")).lower()
                    source_map = {
                        "linkedin": "jobspy_linkedin",
                        "indeed": "jobspy_indeed",
                        "zip_recruiter": "jobspy_zip_recruiter",
                        "google": "jobspy_google",
                    }
                    source = source_map.get(site, f"jobspy_{site}")

                    job = Job(
                        external_id=ext_id,
                        company=company,
                        title=title,
                        url=url,
                        source=source,
                        search_id=search.id,
                        description=str(row.get("description", "")) or None,
                        location=str(row.get("location", "")) or None,
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

            db.commit()

            # Update search last_run_at
            search_obj = db.query(Search).filter(Search.id == search.id).first()
            if search_obj:
                search_obj.last_run_at = datetime.now(timezone.utc)
                db.commit()

        finally:
            db.close()

        duration = time.time() - start_time

        from backend.activity import log_activity
        log_activity("scrape", f"JobSpy search '{search.name}': {new_jobs} new / {jobs_found} found in {duration:.1f}s")

        return {"jobs_found": jobs_found, "new_jobs": new_jobs, "error": None, "duration": duration}

    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"JobSpy search failed for '{search.name}': {e}")

        from backend.activity import log_activity
        log_activity("scrape", f"JobSpy search '{search.name}' failed: {e}")

        return {"jobs_found": 0, "new_jobs": 0, "error": str(e), "duration": duration}


async def run_all_searches(force: bool = False):
    """Run all active search configs via JobSpy. If force=True, skip interval checks."""
    db = SessionLocal()
    try:
        # First-run check: if no scrape logs exist yet, mark all existing jobs as seen
        first_run = db.query(ScrapeLog).count() == 0

        searches = db.query(Search).filter(Search.active == True).all()
        proxy_url = get_setting_value(db, "proxy_url", "")
        if not proxy_url:
            proxy_url = None

        logger.info(f"Running {len(searches)} active searches")

        for search in searches:
            # Per-search interval check (skipped for manual triggers)
            if not force and search.run_interval_minutes:
                if search.last_run_at:
                    elapsed = (datetime.now(timezone.utc) - search.last_run_at).total_seconds() / 60
                    if elapsed < search.run_interval_minutes:
                        logger.info(f"Search '{search.name}' skipped — next run in {search.run_interval_minutes - elapsed:.0f}m")
                        continue

            if search.search_mode == "keyword":
                result = await asyncio.to_thread(run_jobspy_search, search, proxy_url)
            elif search.search_mode == "url" and search.direct_url:
                # URL mode uses Playwright
                from backend.scraper.playwright_scraper import scrape_url_mode
                result = await scrape_url_mode(search)
            elif search.search_mode == "levels_fyi" and search.direct_url:
                from backend.scraper.playwright_scraper import scrape_levelsfyi_mode
                result = await scrape_levelsfyi_mode(search)
            elif search.search_mode == "linkedin_personal":
                from backend.scraper.linkedin_scraper import scrape_linkedin_personal
                result = await scrape_linkedin_personal(search)
            elif search.search_mode == "jobright":
                from backend.scraper.jobright_scraper import scrape_jobright
                result = await scrape_jobright(search)
            else:
                logger.warning(f"Search '{search.name}' has invalid config, skipping")
                continue

            # Log the scrape
            source_map = {"keyword": "jobspy", "url": "playwright_url", "levels_fyi": "levels_fyi", "linkedin_personal": "linkedin_personal", "jobright": "jobright"}
            log = ScrapeLog(
                search_id=search.id,
                source=source_map.get(search.search_mode, search.search_mode),
                jobs_found=result.get("jobs_found", 0),
                new_jobs=result.get("new_jobs", 0),
                error=result.get("error"),
                duration_seconds=result.get("duration", 0),
            )
            db.add(log)
            db.commit()

            logger.info(
                f"Search '{search.name}': found={result['jobs_found']}, "
                f"new={result['new_jobs']}, duration={result.get('duration', 0):.1f}s"
            )

            # Auto CV-score if search has auto_scoring_depth enabled
            if search.auto_scoring_depth in ("light", "full") and result.get("new_jobs", 0) > 0:
                from backend.analyzer.cv_scorer import analyze_unscored_jobs
                await analyze_unscored_jobs(status="new")

        # Also run Playwright career page scrapes
        from backend.scraper.playwright_scraper import scrape_career_pages
        await scrape_career_pages(force=force)

        # First-run: mark all jobs as seen so only truly new ones trigger alerts
        if first_run:
            unseen = db.query(Job).filter(Job.seen == False).all()
            for j in unseen:
                j.seen = True
            db.commit()
            logger.info(f"First run: marked {len(unseen)} existing jobs as seen")

    finally:
        db.close()


async def run_single_search(search_id: str, auto_score: bool = None):
    """Run a single search config. auto_score: True/False override, None=use search.auto_scoring_depth."""
    db = SessionLocal()
    try:
        search = db.query(Search).filter(Search.id == search_id).first()
        if not search:
            logger.error(f"Search {search_id} not found")
            return

        should_score = auto_score if auto_score is not None else (search.auto_scoring_depth in ("light", "full"))
        proxy_url = get_setting_value(db, "proxy_url", "") or None

        if search.search_mode == "keyword":
            result = await asyncio.to_thread(run_jobspy_search, search, proxy_url)
        elif search.search_mode == "url" and search.direct_url:
            from backend.scraper.playwright_scraper import scrape_url_mode
            result = await scrape_url_mode(search)
        elif search.search_mode == "levels_fyi" and search.direct_url:
            from backend.scraper.playwright_scraper import scrape_levelsfyi_mode
            result = await scrape_levelsfyi_mode(search)
        elif search.search_mode == "linkedin_personal":
            from backend.scraper.linkedin_scraper import scrape_linkedin_personal
            result = await scrape_linkedin_personal(search)
        elif search.search_mode == "jobright":
            from backend.scraper.jobright_scraper import scrape_jobright
            result = await scrape_jobright(search)
        else:
            return

        source_map = {"keyword": "jobspy", "url": "playwright_url", "levels_fyi": "levels_fyi", "linkedin_personal": "linkedin_personal", "jobright": "jobright"}
        log = ScrapeLog(
            search_id=search.id,
            source=source_map.get(search.search_mode, search.search_mode),
            jobs_found=result.get("jobs_found", 0),
            new_jobs=result.get("new_jobs", 0),
            error=result.get("error"),
            duration_seconds=result.get("duration", 0),
        )
        db.add(log)
        db.commit()

        if should_score and result and result.get("new_jobs", 0) > 0:
            from backend.analyzer.cv_scorer import analyze_unscored_jobs
            await analyze_unscored_jobs(status="new")

        return result
    finally:
        db.close()
