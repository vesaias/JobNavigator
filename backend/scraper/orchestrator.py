"""Scraper orchestrator — single entry point for all scraping.

Public API:
  - run_all(force=False)           scheduled fan-out over all active searches + companies
  - run_search(search)             dispatch one search by search.search_mode
  - run_company(company, ...)      scrape one company's scrape_urls (delegates to sources.company_pages)

Scheduler + API triggers should import from here; internal sources/ modules are
implementation details.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from backend.models.db import (
    SessionLocal,
    Search,
    Company,
    Job,
    ScrapeLog,
    Setting,
)

logger = logging.getLogger("jobnavigator.scraper.orchestrator")


# ── Per-search dispatch ─────────────────────────────────────────────────────

async def run_search(search: Search, proxy_url: Optional[str] = None) -> dict:
    """Dispatch one search to its source module by search.search_mode.

    Returns the source module's result dict (jobs_found, new_jobs, error, duration).
    Raises ValueError on unknown search_mode.
    """
    mode = search.search_mode

    if mode == "keyword":
        from backend.scraper.sources.jobspy import run
        return await run(search, proxy_url=proxy_url)
    if mode == "url":
        from backend.scraper.sources.company_pages import scrape_url_mode
        return await scrape_url_mode(search)
    if mode == "levels_fyi":
        from backend.scraper.sources.levelsfyi import run
        return await run(search)
    if mode == "linkedin_personal":
        from backend.scraper.sources.linkedin_personal import run
        return await run(search)
    if mode == "jobright":
        from backend.scraper.sources.jobright import run
        return await run(search)
    if mode == "linkedin_extension":
        # No scraper — jobs come via POST /api/jobs/linkedin-import (Chrome extension push)
        return {
            "jobs_found": 0,
            "new_jobs": 0,
            "error": "linkedin_extension has no scraper (passive via Chrome extension)",
            "duration": 0,
        }

    raise ValueError(f"Unknown search_mode: {mode}")


# ── Per-company dispatch ────────────────────────────────────────────────────

async def run_company(company: Company, shared_browser=None) -> dict:
    """Scrape one company's scrape_urls. Delegates to sources.company_pages."""
    from backend.scraper.sources.company_pages import scrape_single_career_page
    return await scrape_single_career_page(company, shared_browser=shared_browser)


# ── Internal helpers ────────────────────────────────────────────────────────

def _get_setting_value(db, key: str, default: str = "") -> str:
    row = db.query(Setting).filter(Setting.key == key).first()
    return row.value if row else default


def _source_for_search(search: Search) -> str:
    """Source string used for ScrapeLog.source — matches old jobspy_scraper behavior."""
    source_map = {
        "keyword": "jobspy",
        "url": "playwright_url",
        "levels_fyi": "levels_fyi",
        "linkedin_personal": "linkedin_personal",
        "jobright": "jobright",
    }
    return source_map.get(search.search_mode, search.search_mode)


def _search_mode_is_valid(search: Search) -> bool:
    """Check if a search has a runnable configuration — preserves old behavior of
    skipping invalid searches rather than raising.

    URL / levels_fyi modes require direct_url; linkedin_extension has no scraper
    (passive capture only); other known modes are always runnable.
    """
    mode = search.search_mode
    if mode == "keyword":
        return True
    if mode == "url":
        return bool(search.direct_url)
    if mode == "levels_fyi":
        return bool(search.direct_url)
    if mode in ("linkedin_personal", "jobright"):
        return True
    return False


# ── Fan-out: all active searches + companies ────────────────────────────────

async def run_all(force: bool = False):
    """Scheduled fan-out: dispatch all active searches + all active companies.

    Preserves the semantics of the original `jobspy_scraper.run_all_searches`:
    - First-run check: if no ScrapeLog rows exist, all existing jobs are marked
      as seen after the run so only truly new jobs trigger alerts.
    - Per-search interval check (skipped if force=True): skip searches whose
      `last_run_at + run_interval_minutes` is still in the future.
    - Invalid-config searches (e.g. url mode without direct_url) are logged
      and skipped.
    - linkedin_extension is not scheduler-driven; skipped silently here (those
      searches should be filtered out, but if one sneaks through we treat it
      the same as any other non-runnable config).
    - After each search, a ScrapeLog row is written and (if the search has
      auto_scoring_depth set and new jobs were found) `analyze_unscored_jobs`
      runs.
    - At the end, the Playwright career-pages batch runs via
      `scrape_career_pages(force=force)`.
    """
    db = SessionLocal()
    try:
        # First-run check: if no scrape logs exist yet, mark all existing jobs as seen
        first_run = db.query(ScrapeLog).count() == 0

        searches = db.query(Search).filter(Search.active == True).all()
        proxy_url = _get_setting_value(db, "proxy_url", "") or None

        logger.info(f"Running {len(searches)} active searches")

        for search in searches:
            # Per-search interval check (skipped for manual triggers)
            if not force and search.run_interval_minutes:
                if search.last_run_at:
                    elapsed = (datetime.now(timezone.utc) - search.last_run_at).total_seconds() / 60
                    if elapsed < search.run_interval_minutes:
                        logger.info(
                            f"Search '{search.name}' skipped — next run in "
                            f"{search.run_interval_minutes - elapsed:.0f}m"
                        )
                        continue

            # Skip invalid configs (matches old behavior — logged + continue, no raise)
            if not _search_mode_is_valid(search):
                logger.warning(f"Search '{search.name}' has invalid config, skipping")
                continue

            try:
                result = await run_search(search, proxy_url=proxy_url)
            except ValueError as e:
                # Unknown search_mode — log and skip, don't abort the whole batch
                logger.warning(f"Search '{search.name}': {e}, skipping")
                continue
            except Exception as e:
                logger.exception(f"Search '{search.name}' failed: {e}")
                result = {"jobs_found": 0, "new_jobs": 0, "error": str(e), "duration": 0}

            # Log the scrape
            log = ScrapeLog(
                search_id=search.id,
                source=_source_for_search(search),
                jobs_found=result.get("jobs_found", 0),
                new_jobs=result.get("new_jobs", 0),
                error=result.get("error"),
                duration_seconds=result.get("duration", 0),
            )
            db.add(log)
            db.commit()

            logger.info(
                f"Search '{search.name}': found={result.get('jobs_found', 0)}, "
                f"new={result.get('new_jobs', 0)}, duration={result.get('duration', 0):.1f}s"
            )

            # Auto CV-score if search has auto_scoring_depth enabled
            if search.auto_scoring_depth in ("light", "full") and result.get("new_jobs", 0) > 0:
                from backend.analyzer.cv_scorer import analyze_unscored_jobs
                await analyze_unscored_jobs(status="new")

        # Also run Playwright career page scrapes
        from backend.scraper.sources.company_pages import scrape_career_pages
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


# ── Single-search trigger (API) ─────────────────────────────────────────────

async def _run_search_by_id(search_id: str, auto_score: Optional[bool] = None) -> dict:
    """Fetch one search by ID and dispatch — used by the API trigger endpoint.

    Preserves semantics of the original `jobspy_scraper.run_single_search`:
    - auto_score override: if None, use search.auto_scoring_depth setting.
    - Writes a ScrapeLog row with the result.
    - Runs analyze_unscored_jobs(status="new") if scoring is enabled and new
      jobs were found.
    - Returns the result dict (or None if search not found — matches old
      behavior which returned None via `return`).
    """
    db = SessionLocal()
    try:
        search = db.query(Search).filter(Search.id == search_id).first()
        if not search:
            logger.error(f"Search {search_id} not found")
            return

        should_score = (
            auto_score
            if auto_score is not None
            else (search.auto_scoring_depth in ("light", "full"))
        )
        proxy_url = _get_setting_value(db, "proxy_url", "") or None

        if not _search_mode_is_valid(search):
            return

        try:
            result = await run_search(search, proxy_url=proxy_url)
        except ValueError:
            # Unknown mode — match old behavior (silent return)
            return

        log = ScrapeLog(
            search_id=search.id,
            source=_source_for_search(search),
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
