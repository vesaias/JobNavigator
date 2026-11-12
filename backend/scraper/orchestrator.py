"""Scraper orchestrator: single entry point (run_all/run_search/run_company) that
scheduler + API triggers import from; internal sources/ modules are implementation details.

Accounts (MT-8): run_all() is the shared-scrape fan-out — identical targets of different
accounts are fetched once and ingested per account (see backend/scraper/targets.py). A
manual run of one search (_run_search_by_id) or company feeds only the caller's account."""
import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from backend.models.db import (
    SessionLocal,
    Search,
    Company,
    Job,
    ScrapeLog,
)

logger = logging.getLogger("jobnavigator.scraper.orchestrator")


# ── Per-search dispatch ─────────────────────────────────────────────────────

async def run_search(search: Search, proxy_url: Optional[str] = None, shared=None) -> dict:
    """Dispatch one search to its source module (`search_modes.SEARCH_MODES[mode].module`);
    returns the module's result dict, or raises ValueError on an unknown mode.

    `shared` (MT-8 `SharedFetch`) is passed only to the shareable modes and only when set, and
    `proxy_url` only to the modes that take one, so a single search calls exactly as before."""
    import importlib
    from backend.scraper.search_modes import get_mode
    mode = get_mode(search.search_mode)
    if mode is None:
        raise ValueError(f"Unknown search_mode: {search.search_mode}")
    if mode.extension:
        # No scraper: jobs come from the Chrome extension (POST /api/jobs/linkedin-import for
        # passive LinkedIn capture, POST /api/jobs/save-from-extension for Save to Job Feed).
        return {
            "jobs_found": 0,
            "new_jobs": 0,
            "error": f"{search.search_mode} has no scraper (jobs arrive from the Chrome extension)",
            "duration": 0,
        }
    module = importlib.import_module(f"backend.scraper.sources.{mode.module}")
    kwargs = {}
    if mode.takes_proxy:
        kwargs["proxy_url"] = proxy_url
    if mode.shareable and shared is not None:
        kwargs["shared"] = shared
    minutes = search_timeout_minutes()
    try:
        return await asyncio.wait_for(module.run(search, **kwargs), minutes * 60)
    except asyncio.TimeoutError:
        # The scheduler runs one scrape at a time: a search that never returns stops
        # every later run. Cancel it and report the failure on its ScrapeLog row.
        raise RuntimeError(
            f"Search did not finish in {minutes} min and was cancelled"
            " (JN_SEARCH_TIMEOUT_MINUTES)") from None


def search_timeout_minutes() -> int:
    """The longest time one search may run. The default is above the longest correct run:
    LinkedIn Personal reads 2 collections of 20 pages, and a slow host needs 7 min per page."""
    try:
        return max(1, int(os.getenv("JN_SEARCH_TIMEOUT_MINUTES") or 360))
    except ValueError:
        return 360


# ── Per-company dispatch ────────────────────────────────────────────────────

async def run_company(company: Company, shared_browser=None) -> dict:
    """Scrape one company's scrape_urls. Delegates to sources.company_pages."""
    from backend.scraper.sources.company_pages import scrape_single_career_page
    return await scrape_single_career_page(company, shared_browser=shared_browser)


# ── Internal helpers ────────────────────────────────────────────────────────

def _get_setting_value(db, key: str, default: str = "") -> str:
    from backend.accounts.settings import get_setting
    return get_setting(db, key, default)


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
    k = str(key or "").lower()
    if k in SOURCE_LABELS:
        return SOURCE_LABELS[k]
    from backend.scraper.sources.apify import PRESETS   # Apify boards name themselves
    return PRESETS[k].label if k in PRESETS else str(key or "")


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
    """Postings the title filters rejected, summed across boards; JobSpy still writes them as `ignored` for dedup (so its stored rows can exceed "N seen"), Apify does not store them."""
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
    from backend.scraper.search_modes import get_mode
    mode = get_mode(search.search_mode)
    return mode.source if mode else search.search_mode


def _search_mode_is_valid(search: Search) -> bool:
    """True if a search has a runnable configuration (`search_config_error` is None for a mode
    with a scraper); invalid configs are skipped, not raised."""
    from backend.scraper.search_modes import get_mode
    mode = get_mode(search.search_mode)
    return bool(mode and mode.runnable) and search_config_error(search) is None


def search_config_error(search) -> Optional[str]:
    """A human reason this search cannot run as configured, or None. The scheduler skips an
    invalid config silently; the manual trigger reads this so the run history says why instead
    of leaving it at "nothing ran"."""
    from backend.scraper.search_modes import config_error
    return config_error(search)


# ── Fan-out: all active searches + companies ────────────────────────────────

def _record_search_log(db, search: Search, result: dict, run_id=None, started_at=None) -> ScrapeLog:
    """The ScrapeLog row of one search run, under the current account. A clean run that
    found nothing is a warning (same rule company scrapes use) so /health/entities can flag
    a search that quietly stopped returning results."""
    breakdown = result.get("source_breakdown") or None
    # QA F6 / R4-06: every finished attempt stamps last_run_at, also an empty or failed
    # one (the source modules stamp only after a non-empty ingest), so a search with its
    # own interval is not re-run on every tick. The error / warning lives on this row.
    # QA V-02: the scheduled batch passes its start time, so the interval is measured
    # start to start (see targets._elapsed_due).
    search.last_run_at = started_at or datetime.now(timezone.utc)
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
        run_id=run_id,
    )
    db.add(log)
    db.commit()
    return log


async def run_all(force: bool = False, account_ids=None, skip=None):
    """Scheduled fan-out over all active searches + companies: marks existing jobs seen on a first run, skips due/invalid/extension-mode searches, logs + optionally scores each search, then runs the Playwright company sweep.

    MT-8: `account_ids=None` covers every account (the scheduler); the manual run-all passes
    the caller's account only. Searches are grouped into targets
    (`backend.scraper.targets.search_key`): a due target is fetched once and each
    subscribing search ingests it under its own account, writing its own ScrapeLog row
    (rows of one fetch share a `run_id`). One subscriber failing does not stop the others.
    The post-search scoring sweep and the first-run "mark seen" are per account.

    QA F6: `skip` (a `job_monitor.ManualScrapeScopes`) names the searches and companies a
    manual scrape is fetching right now; the scheduled run leaves them out. A search
    deleted mid-run is skipped. Errors outside a source's own result (an ingest crash, a
    scoring sweep) come back in `errors` ({"account", "where", "error"}) for the summary."""
    import uuid
    from backend.accounts.background import account_session, acting_as
    from backend.accounts.context import current_account
    from backend.scraper.search_modes import is_extension
    from backend.scraper.targets import (
        group_targets, is_shareable_search, load_active, reusable_key, search_due,
        search_fetch_params, search_key, search_target_due, shared_fetch_for,
        split_search_targets,
    )
    db = SessionLocal()
    errors: list = []
    skip_search_ids = set(getattr(skip, "search_ids", None) or ())
    skip_company_ids = set(getattr(skip, "company_ids", None) or ())
    try:
        searches = load_active(db, Search, account_ids)
        from backend.models.db import Company
        companies = load_active(db, Company, account_ids)
        # Plain (id, name, account) per search: later commits expire the rows (T5-01).
        ident = {id(s): (s.id, s.name, s.account_id) for s in searches}

        # First run, per account: an account with no ScrapeLog yet gets its existing jobs
        # marked seen afterwards, so only truly new ones trigger alerts.
        accounts = []
        for acc in [current_account.get()] + [r.account_id for r in searches + companies]:
            if acc not in accounts:
                accounts.append(acc)
        if account_ids is not None:
            accounts = [a for a in accounts if a in account_ids] or accounts[:1]
        first_run_accounts = []
        for acc in accounts:
            with account_session(acc, SessionLocal) as adb:
                if adb.query(ScrapeLog).count() == 0:
                    first_run_accounts.append(acc)

        proxy_url = _get_setting_value(db, "proxy_url", "") or None
        # The scheduler period, for the due checks (QA V-02).
        try:
            tick = int(_get_setting_value(db, "scrape_interval_minutes", "60") or 0)
        except (TypeError, ValueError):
            tick = 0

        runnable = []
        for search in searches:
            # Passive-only modes (extension push endpoints) are not scheduler-driven —
            # skip silently to keep logs clean.
            if is_extension(search.search_mode):
                continue
            if str(search.id) in skip_search_ids:
                logger.info(f"Search '{search.name}' skipped: a manual run of it is in progress")
                continue
            # Skip invalid configs — logged and skipped rather than raising.
            if not _search_mode_is_valid(search):
                logger.warning(f"Search '{search.name}' has invalid config, skipping")
                continue
            runnable.append(search)

        def _key(s):
            return search_key(s) if is_shareable_search(s) else (s.search_mode, "own", str(s.id))
        # QA F10 / R4-05: JobSpy subscribers share one fetch only when their
        # results_wanted / hours_old are close; otherwise they are separate fetches.
        targets = split_search_targets(group_targets(runnable, _key))
        logger.info(f"Running {len(runnable)} active searches as {len(targets)} targets")
        sweep_accounts = []

        now = datetime.now(timezone.utc)
        from backend.scraper.sources.company_pages import _row_still_there
        for target in targets:
            # T5-01: drop subscribers deleted since the load before reading their attributes.
            alive = [s for s in target.subscribers if _row_still_there(db, s)]
            if not alive:
                continue
            target.subscribers = alive
            # Interval check (skipped for manual triggers): due when any subscriber is due.
            if not force:
                due, _effective = search_target_due(target, now, tick)
                if not due:
                    for search in target.subscribers:
                        _, elapsed, interval = search_due(search, now, tick)
                        logger.info(f"Search '{search.name}' skipped — next run in {interval - elapsed:.0f}m")
                    continue

            run_id = uuid.uuid4()
            # Every shareable target gets a SharedFetch, even with one subscriber, so a later
            # run (another account's Run all, the scheduled scrape) can reuse it; per-account
            # modes (own session, paid Apify) keep calling their source directly.
            shared = (shared_fetch_for(target.key, search_fetch_params(target.subscribers))
                      if reusable_key(target.key) else None)
            for search in target.subscribers:
                sid, sname, account = ident[id(search)]
                # QA F10 / R1-05: each subscriber works in a fresh session of its own
                # account, never in the batch session that loaded every account's rows
                # (its identity map and lazy loads would ignore the context switch).
                with account_session(account, SessionLocal) as sdb:
                    try:
                        # QA F6 / T5-01: a search (or account) deleted mid-run is skipped.
                        search = sdb.query(Search).filter(Search.id == sid).first()
                        if search is None:
                            logger.info(f"Search '{sname}' was deleted during the run, skipped")
                            continue
                        try:
                            kwargs = {"shared": shared} if shared is not None else {}
                            result = await run_search(search, proxy_url=proxy_url, **kwargs)
                        except ValueError as e:
                            # Unknown search_mode — log and skip, don't abort the whole batch
                            logger.warning(f"Search '{sname}': {e}, skipping")
                            continue
                        except Exception as e:
                            logger.exception(f"Search '{sname}' failed: {e}")
                            result = {"jobs_found": 0, "new_jobs": 0, "error": str(e), "duration": 0}

                        auto_depth = search.auto_scoring_depth
                        _record_search_log(sdb, search, result, run_id=run_id, started_at=now)
                        breakdown = result.get("source_breakdown") or None
                        if source_errors(breakdown):
                            logger.warning(
                                f"Search '{sname}': {describe_source_errors(breakdown)}"
                            )

                        logger.info(
                            f"Search '{sname}': found={result.get('jobs_found', 0)}, "
                            f"new={result.get('new_jobs', 0)}, duration={result.get('duration', 0):.1f}s"
                            + (f" (shared fetch, {len(target.subscribers)} subscribers)" if target.shared else "")
                        )

                        # Auto CV-score: mark the account for one pool sweep after all searches
                        # (the sweep is a common pool — per-search invocations re-walked it N times).
                        if (auto_depth in ("light", "full") and result.get("new_jobs", 0) > 0
                                and account not in sweep_accounts):
                            sweep_accounts.append(account)
                    except Exception as e:
                        # e.g. the ScrapeLog write failed: this subscriber only. Roll back
                        # before anything else touches the session (T5-01).
                        try:
                            sdb.rollback()
                        except Exception:
                            pass
                        try:
                            gone = sdb.query(Search.id).filter(Search.id == sid).first() is None
                        except Exception:
                            gone = False
                        if gone:
                            logger.info(f"Search '{sname}' was deleted during the run, skipped: {e}")
                            continue
                        logger.exception(f"Search '{sname}' ingest failed, others continue: {e}")
                        errors.append({"account": account, "where": f"search {sname}",
                                       "error": f"{type(e).__name__}: {e}"})
            # End the batch session's read transaction and expire its rows, so the next
            # target's due/deleted checks read fresh values.
            db.commit()

        for acc in sweep_accounts:
            # Contained: a scoring failure must not abort the rest of scrape_all
            # (career-page scrapes below would never run).
            with acting_as(acc):
                try:
                    from backend.analyzer.cv_scorer import analyze_unscored_jobs
                    await analyze_unscored_jobs(status="new")
                except Exception as e:
                    logger.exception(f"Post-search scoring sweep failed (scrape continues): {e}")
                    errors.append({"account": acc, "where": "search scoring sweep",
                                   "error": f"{type(e).__name__}: {e}"})

        from backend.scraper.sources import company_pages
        cp_kwargs = {"force": force}
        if account_ids is not None:
            cp_kwargs["account_ids"] = account_ids
        if skip_company_ids:
            cp_kwargs["skip_company_ids"] = skip_company_ids
        company_summary = await company_pages.scrape_career_pages(**cp_kwargs) or {}
        errors.extend(company_summary.get("errors") or [])

        # First-run: mark all jobs as seen so only truly new ones trigger alerts
        for acc in first_run_accounts:
            with account_session(acc, SessionLocal) as adb:
                try:
                    unseen = adb.query(Job).filter(Job.seen == False).all()
                    for j in unseen:
                        j.seen = True
                    adb.commit()
                    logger.info(f"First run: marked {len(unseen)} existing jobs as seen")
                except Exception as e:   # one account's bookkeeping, never the run (R4-03)
                    adb.rollback()
                    logger.exception(f"First-run mark-seen failed: {e}")
                    errors.append({"account": acc, "where": "first-run mark seen",
                                   "error": f"{type(e).__name__}: {e}"})

        # Handed to the caller so a manual run's summary can say what did not run
        # (companies with no URLs, or — scheduler only — companies not yet due), and the
        # scheduled run's summary which accounts hit errors.
        return {"companies": company_summary, "errors": errors}
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
        # A manual run fetches for, and feeds, only this account (MT-8): no shared fetch,
        # a run_id of its own.
        import uuid
        log = _record_search_log(db, search, result, run_id=uuid.uuid4())
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
