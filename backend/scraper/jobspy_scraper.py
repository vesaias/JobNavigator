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



# Back-compat shim — Task 18 (moved to sources/jobspy)
# `run_jobspy_search` is re-exported as the synchronous entry point so existing
# `asyncio.to_thread(run_jobspy_search, ...)` calls in this module continue to work.
from backend.scraper.sources.jobspy import _run_sync as run_jobspy_search  # noqa: F401,E402


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
