"""Scraper orchestrator: single entry point (run_all/run_search/run_company) that
scheduler + API triggers import from; internal sources/ modules are implementation details."""
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
    """Dispatch one search to its source module by search.search_mode; returns the module's result dict, or raises ValueError on an unknown mode."""
    mode = search.search_mode

    if mode == "keyword":
        from backend.scraper.sources.jobspy import run
        return await run(search, proxy_url=proxy_url)
    if mode == "levels_fyi":
        from backend.scraper.sources.levelsfyi import run
        return await run(search)
    if mode == "linkedin_personal":
        from backend.scraper.sources.linkedin_personal import run
        return await run(search)
    if mode == "jobright":
        from backend.scraper.sources.jobright import run
        return await run(search)
    if mode == "freehire":
        from backend.scraper.sources.freehire import run
        return await run(search)
    if mode == "caribbeanjobs":
        from backend.scraper.sources.caribbeanjobs import run
        return await run(search)
    if mode == "linkedin_extension":
        # No scraper — jobs come via POST /api/jobs/linkedin-import (Chrome extension push)
        return {
            "jobs_found": 0,
            "new_jobs": 0,
            "error": "linkedin_extension has no scraper (passive via Chrome extension)",
            "duration": 0,
        }
    if mode == "extension":
        # No scraper — jobs come via POST /api/jobs/save-from-extension (manual Save-to-Feed button)
        return {
            "jobs_found": 0,
            "new_jobs": 0,
            "error": "extension has no scraper (manual save via Chrome extension)",
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


# ── Per-source outcome helpers ───────────────────────────────────────────────
# A multi-board search stores {"indeed": {"seen": 9, "new": 0}, "zip_recruiter":
# {"error": "403"}} on ScrapeLog; these three helpers are the only readers.

SOURCE_LABELS = {
    "indeed": "Indeed",
    "linkedin": "LinkedIn",
    "zip_recruiter": "ZipRecruiter",
    "google": "Google",
    "glassdoor": "Glassdoor",
    "bayt": "Bayt",
    "naukri": "Naukri",
    "bdjobs": "BDJobs",
}


def source_label(key: str) -> str:
    """"zip_recruiter" -> "ZipRecruiter"; unknown boards keep their raw key."""
    return SOURCE_LABELS.get(str(key or "").lower(), str(key or ""))


def source_errors(breakdown) -> list:
    """[(source_key, error), ...] for every board that reported a failure."""
    if not isinstance(breakdown, dict):
        return []
    out = []
    for key, val in breakdown.items():
        if isinstance(val, dict) and val.get("error"):
            out.append((str(key), str(val["error"])))
    return out


def describe_source_errors(breakdown) -> str:
    """"zip_recruiter: 403 · indeed: 503" (empty when clean)."""
    return " · ".join(f"{key}: {err}" for key, err in source_errors(breakdown))


def empty_sources(breakdown) -> list:
    """Configured boards that returned no rows at all and reported no failure.

    The test reads `returned`, the count the source module takes before any
    filter runs. `seen` and `filtered` cannot answer this: a board whose rows the
    title filter rejects leaves `seen` at 0, and `filtered` counts only rejected
    rows that were new enough to store, so both read 0 from the second run on
    while the board keeps delivering rows.

    A row written before `returned` existed carries no such key. Those entries
    are skipped, because an old row holds no evidence either way.
    """
    if not isinstance(breakdown, dict):
        return []
    return [
        str(key) for key, val in breakdown.items()
        if isinstance(val, dict) and not val.get("error")
        and "returned" in val and not (val.get("returned") or 0)
    ]


def run_is_warning(result: dict, breakdown) -> bool:
    """True when one run needs a human look.

    Three conditions, any of which is enough:
    | Condition                             | Example                          |
    | ------------------------------------- | -------------------------------- |
    | A board refused the request           | ZipRecruiter 403                 |
    | A configured board returned no rows   | Indeed 0 while LinkedIn gave 40  |
    | The run found nothing and said nothing| every board empty, error is None |

    The per-board test matters because the total hides it: LinkedIn 40 plus
    Indeed 0 sums to 40, and the run used to be recorded as healthy.
    """
    return bool(
        source_errors(breakdown)
        or empty_sources(breakdown)
        or (result.get("jobs_found", 0) == 0 and not result.get("error"))
    )


def filtered_count(breakdown) -> int:
    """Postings the title filters rejected, summed across boards; rejected postings are still written as `ignored` for dedup, so a run's stored rows can exceed its "N seen" count."""
    if not isinstance(breakdown, dict):
        return 0
    return sum(int(v.get("filtered") or 0) for v in breakdown.values()
               if isinstance(v, dict))


def summarize_search_run(label: str, result: dict) -> str:
    """The Run-history line for one search run, read back from the ScrapeLog row it wrote (same convention as scheduler._scrape_summary) so the summary can't disagree with the log."""
    if not isinstance(result, dict):
        return f"{label} - nothing ran"

    found = result.get("jobs_found", 0)
    new = result.get("new_jobs", 0)
    breakdown = result.get("source_breakdown")
    log_id = result.get("scrape_log_id")
    if log_id:
        db = SessionLocal()
        try:
            row = db.query(ScrapeLog).filter(ScrapeLog.id == log_id).first()
            if row:
                found = row.jobs_found or 0
                new = row.new_jobs or 0
                breakdown = row.source_breakdown
        except Exception as e:          # a summary must never break the run
            logger.warning(f"Could not read back ScrapeLog {log_id}: {e}")
        finally:
            db.close()

    summary = f"{label} - {found} seen, +{new} new"
    filtered = filtered_count(breakdown)
    if filtered:
        summary += f", {filtered} filtered out"
    # Name the boards that hard-failed, so "9 seen, +0 new" can't be mistaken
    # for a quiet day on every configured source.
    failed = describe_source_errors(breakdown)
    if failed:
        summary += f" · {failed}"
    # A board that answered with an empty list is the silent case the total
    # hides, so name it too.
    empty = empty_sources(breakdown)
    if empty:
        summary += f" · no rows from {', '.join(empty)}"
    return summary


def _source_for_search(search: Search) -> str:
    """Source string used for ScrapeLog.source."""
    source_map = {
        "keyword": "jobspy",
        "levels_fyi": "levels_fyi",
        "linkedin_personal": "linkedin_personal",
        "jobright": "jobright",
        "freehire": "freehire",
        "caribbeanjobs": "caribbeanjobs",
    }
    return source_map.get(search.search_mode, search.search_mode)


def _search_mode_is_valid(search: Search) -> bool:
    """True if a search has a runnable configuration (levels_fyi requires direct_url; other known modes are always runnable); invalid configs are skipped, not raised."""
    mode = search.search_mode
    if mode == "keyword":
        return True
    if mode == "levels_fyi":
        return bool(search.direct_url)
    if mode in ("linkedin_personal", "jobright"):
        return True
    if mode == "freehire":
        return bool(search.direct_url or search.search_term)
    if mode == "caribbeanjobs":
        return bool(search.direct_url or search.search_term)
    return False


# Sources that scrape a keyword board have no account-based "recommended" feed, so without a
# term or a pre-filtered URL there is nothing to ask them for.
_NEEDS_QUERY_MODES = ("freehire", "caribbeanjobs")


def search_config_error(search) -> Optional[str]:
    """A human reason this search cannot run as configured, or None. The scheduler skips an
    invalid config silently; the manual trigger reads this so the run history says why instead
    of leaving it at "nothing ran"."""
    if search.search_mode in _NEEDS_QUERY_MODES and not (search.direct_url or search.search_term):
        label = "CaribbeanJobs.com" if search.search_mode == "caribbeanjobs" else "freehire.me"
        return f"{label} needs a search term or a URL before it can run"
    return None


# ── Fan-out: all active searches + companies ────────────────────────────────

async def run_all(force: bool = False):
    """Scheduled fan-out over all active searches + companies: marks existing jobs seen on a first run, skips due/invalid/extension-mode searches, logs + optionally scores each search, then runs the Playwright company sweep."""
    db = SessionLocal()
    try:
        first_run = db.query(ScrapeLog).count() == 0

        searches = db.query(Search).filter(Search.active == True).all()
        proxy_url = _get_setting_value(db, "proxy_url", "") or None

        logger.info(f"Running {len(searches)} active searches")
        search_sweep_needed = False

        for search in searches:
            # Passive-only modes (extension push endpoints) are not scheduler-driven —
            # skip silently to keep logs clean.
            if search.search_mode in ("linkedin_extension", "extension"):
                continue

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

            # Skip invalid configs — logged and skipped rather than raising.
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

            # A clean run that found nothing is a warning (same rule company scrapes
            # use) so /health/entities can flag a search that quietly stopped returning results.
            breakdown = result.get("source_breakdown") or None
            failed_sources = source_errors(breakdown)
            log = ScrapeLog(
                search_id=search.id,
                source=_source_for_search(search),
                jobs_found=result.get("jobs_found", 0),
                new_jobs=result.get("new_jobs", 0),
                error=result.get("error"),
                is_warning=run_is_warning(result, breakdown),
                source_breakdown=breakdown,
                duration_seconds=result.get("duration", 0),
            )
            db.add(log)
            db.commit()

            if failed_sources:
                logger.warning(
                    f"Search '{search.name}': {describe_source_errors(breakdown)}"
                )

            logger.info(
                f"Search '{search.name}': found={result.get('jobs_found', 0)}, "
                f"new={result.get('new_jobs', 0)}, duration={result.get('duration', 0):.1f}s"
            )

            # Auto CV-score: mark for one pool sweep after all searches (the
            # sweep is a common pool — per-search invocations re-walked it N times).
            if search.auto_scoring_depth in ("light", "full") and result.get("new_jobs", 0) > 0:
                search_sweep_needed = True

        if search_sweep_needed:
            # Contained: a scoring failure must not abort the rest of scrape_all
            # (career-page scrapes below would never run).
            try:
                from backend.analyzer.cv_scorer import analyze_unscored_jobs
                await analyze_unscored_jobs(status="new")
            except Exception as e:
                logger.exception(f"Post-search scoring sweep failed (scrape continues): {e}")

        from backend.scraper.sources.company_pages import scrape_career_pages
        company_summary = await scrape_career_pages(force=force) or {}

        # First-run: mark all jobs as seen so only truly new ones trigger alerts
        if first_run:
            unseen = db.query(Job).filter(Job.seen == False).all()
            for j in unseen:
                j.seen = True
            db.commit()
            logger.info(f"First run: marked {len(unseen)} existing jobs as seen")

        # Handed to the caller so a manual run's summary can say what did not run
        # (companies with no URLs, or — scheduler only — companies not yet due).
        return {"companies": company_summary}
    finally:
        db.close()


# ── Single-search trigger (API) ─────────────────────────────────────────────

async def _run_search_by_id(search_id: str, auto_score: Optional[bool] = None) -> dict:
    """Fetch one search by ID and dispatch (used by the API trigger endpoint); writes a ScrapeLog row and runs analyze_unscored_jobs if scoring is enabled and new jobs were found. Returns None if the search isn't found."""
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
            # Name the reason in the log; the API does the same for a manual trigger.
            reason = search_config_error(search)
            logger.warning(
                f"Search '{search.name}' has invalid config, skipping"
                + (f": {reason}" if reason else "")
            )
            return

        try:
            result = await run_search(search, proxy_url=proxy_url)
        except ValueError:
            return  # unknown mode: silent return

        breakdown = result.get("source_breakdown") or None
        failed_sources = source_errors(breakdown)
        log = ScrapeLog(
            search_id=search.id,
            source=_source_for_search(search),
            jobs_found=result.get("jobs_found", 0),
            new_jobs=result.get("new_jobs", 0),
            error=result.get("error"),
            # R3-A-03 plus the silent zero: see run_is_warning().
            is_warning=run_is_warning(result, breakdown),
            source_breakdown=breakdown,
            duration_seconds=result.get("duration", 0),
        )
        db.add(log)
        db.commit()
        # Hand the caller the row it should summarise, so the Run-history line
        # and the audit row are read from the same place.
        result["scrape_log_id"] = str(log.id)

        if failed_sources:
            logger.warning(f"Search '{search.name}': {describe_source_errors(breakdown)}")

        if should_score and result and result.get("new_jobs", 0) > 0:
            from backend.analyzer.cv_scorer import analyze_unscored_jobs
            await analyze_unscored_jobs(status="new")

        return result
    finally:
        db.close()
