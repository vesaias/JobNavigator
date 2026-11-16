"""JobSpy-backed keyword search source — searches LinkedIn, Indeed, ZipRecruiter, Google Jobs via a single multi-board request."""
import asyncio
import json
import logging
import re
import time
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.countries import DEFAULT_COUNTRY, compose_location
from backend.models.db import SessionLocal, Search, Job, get_existing_external_ids
from backend.accounts.settings import get_setting
from backend.scraper._shared.dedup import make_external_id, make_content_hash
from backend.scraper._shared.posting_links import counts_as_new, employer_link
from backend.scraper._shared.postings import is_short_link, resolve_short_link
from backend.scraper._shared.filters import include_pattern

logger = logging.getLogger("jobnavigator.scraper.sources.jobspy")


def _clean(v):
    """Null-safe scalar → clean string, or None when empty; a bare str(cell) on a pandas NaN yields the literal text 'nan', which passes emptiness checks downstream and broke resume tailoring."""
    import pandas as pd
    try:
        if v is None or pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass  # non-scalar (list/array) — fall through and stringify
    s = str(v).strip()
    return s or None


def _jobspy_yearly(interval, *amounts) -> bool:
    """True when a JobSpy row's pay may be stored as a yearly salary: its interval is yearly or
    unstated, and each amount given is at least 1000 (JobSpy runs without enforce_annual_salary,
    so an hourly row carries the hourly figure). Not annualised, as no source does that."""
    unit = (_clean(interval) or "yearly").lower()
    if unit not in ("yearly", "annual", "year"):
        return False
    try:
        return all(float(a) >= 1000 for a in amounts if _clean(a) is not None)
    except (TypeError, ValueError):
        return False


def _apply_h1b_inline(job, db=None, company_lookup=None, phrases=None, loop=None) -> None:
    """Sync-safe H-1B JD scan: runs check_job_h1b in an event loop for asyncio.to_thread() workers; batch callers should pass a shared `loop` plus `company_lookup`/`phrases` to skip per-job DB lookups."""
    import asyncio as _asyncio
    from backend.analyzer.h1b_checker import check_job_h1b

    try:
        own_loop = loop is None
        if own_loop:
            loop = _asyncio.new_event_loop()
        try:
            loop.run_until_complete(check_job_h1b(job, db=db, company_lookup=company_lookup, phrases=phrases))
        finally:
            if own_loop:
                loop.close()
    except Exception as e:
        logger.warning(f"_apply_h1b_inline failed for job {getattr(job, 'id', '?')}: {e}")


# A board that fails does not stop the others; jobspy (1.4+) names each failed board and its
# error in `jobs_df.attrs["errors"]`, keyed by the same site values we pass in `site_name`.


def _condense_error(msg: str) -> str:
    """"ZipRecruiter response status code 403" -> "403"; anything else trimmed."""
    text = " ".join(str(msg).split())
    m = re.search(r"\b([45]\d\d)\b", text)
    if m:
        return m.group(1)
    return text[:120]


# Known blocks: the board refuses this scraper on every measured run, and no query
# change helps. Each signature maps to a stable text. Every other failure keeps
# its condensed text, so a failure nobody diagnosed stays visible as it is.
# The frontend flags the same two boards in frontend/src/sourceBlocks.js.
ZIP_RECRUITER_REDIRECTED = "the US site redirects this location to a regional ZipRecruiter site, which this scraper does not read: HTTP 307"
ZIP_RECRUITER_BLOCKED = "the server refuses the requests that this scraper sends: HTTP 403"
# The capture sees the log line, not the page. A real page with zero jobs logs the
# same error, so the Google text names the likely cause, not a certain one.
GOOGLE_BLOCKED = "the server returned no job data, which is usually a JavaScript check page that this scraper cannot read"
_KNOWN_BLOCKS = {
    # jobspy/ziprecruiter/__init__.py logs only "response status code <n>" at ERROR,
    # without the body. From an EU address the US site answers 307 to its .de site.
    "zip_recruiter": [
        (re.compile(r"response status code 307\b", re.I), ZIP_RECRUITER_REDIRECTED),
        (re.compile(r"response status code 403\b", re.I), ZIP_RECRUITER_BLOCKED),
    ],
    # jobspy/google/__init__.py fails with this when page 1 has neither jobs nor a cursor
    # ("no job data returned" since 1.4, "returned no job data" before).
    "google": [(re.compile(r"returned no job data|no job data returned", re.I), GOOGLE_BLOCKED)],
}


def _describe_error(key: str, msg: str) -> str:
    """The stable text for a known block signature of this board, else _condense_error(msg)."""
    for signature, text in _KNOWN_BLOCKS.get(key, ()):
        if signature.search(str(msg)):
            return text
    return _condense_error(msg)


def _board_errors(errors: dict, jobs_df, sources) -> dict:
    """The board errors to report for one scrape_jobs() call: only the boards this run asked for.

    A Google board that returned rows was not blocked, so a "no job data" error
    on it is dropped (cross-talk from another run, or a later page). A different
    Google failure keeps its text.
    """
    returned = set()
    if jobs_df is not None and not jobs_df.empty and "site" in jobs_df.columns:
        returned = {str(s).lower() for s in jobs_df["site"].unique()}
    return {k: v for k, v in (errors or {}).items()
            if k in sources and not (k == "google" and v == GOOGLE_BLOCKED and k in returned)}


def _errors_of(jobs_df) -> dict:
    """{board: text} for each board that failed in one scrape_jobs() call."""
    raw = (getattr(jobs_df, "attrs", None) or {}).get("errors") or {}
    return {str(site).lower(): _describe_error(str(site).lower(), msg) for site, msg in raw.items()}


def jobspy_kwargs(search, proxy_url: str = None) -> dict:
    """The scrape_jobs() arguments for one keyword search (the scheduled run and Test share them).

    jobspy 1.4 rejects a country it does not know with a ValueError for the whole call; a
    search saved with a country it has since dropped says so instead of searching the US.
    """
    from backend.countries import normalize_country
    sources = [s for s in (search.sources or []) if s != "direct"]
    country = normalize_country(search.country or DEFAULT_COUNTRY)
    if country is None:
        raise ValueError(f"Indeed has no site for the country {search.country!r} any more; "
                         f"pick another country for this search")
    kwargs = {
        "site_name": sources,
        "search_term": search.search_term or "",
        "location": compose_location(search.location, search.country),
        "results_wanted": search.results_wanted or 50,
        "hours_old": search.hours_old or 24,
        "job_type": search.job_type or "fulltime",
        "country_indeed": country,
        "verbose": 2,
    }
    if search.is_remote is not None:
        kwargs["is_remote"] = search.is_remote
    if proxy_url:
        kwargs["proxies"] = [proxy_url]
    return kwargs


def _merge_source_errors(breakdown: dict, errors: dict) -> dict:
    """Fold captured per-board errors into the seen/new breakdown."""
    for key, err in (errors or {}).items():
        breakdown.setdefault(key, {"seen": 0, "new": 0})["error"] = err
    return breakdown


def _count_returned(breakdown: dict, jobs_df) -> dict:
    """Write `returned`, the unfiltered row count, for every configured board.

    An empty frame is real evidence, so every board gets 0. A frame that holds
    rows but no `site` column is no evidence at all: the key is left off
    entirely, because empty_sources() skips an entry without it, and a run that
    stored jobs must never report "no rows from linkedin, indeed".
    """
    empty = jobs_df is None or jobs_df.empty
    if not empty and "site" not in jobs_df.columns:
        return breakdown
    counts = {} if empty else {
        str(site).lower(): int(n)
        for site, n in jobs_df["site"].value_counts().items()
    }
    for key in set(breakdown) | set(counts):
        breakdown.setdefault(key, {"seen": 0, "new": 0})["returned"] = counts.get(key, 0)
    return breakdown


# Boards whose `is_remote` reads the board's own remote tag (python-jobspy 1.4.1): Indeed's
# remote attribute unless it is also tagged hybrid, Glassdoor's remoteWorkTypes, ZipRecruiter's
# locationTypes. LinkedIn and Google still guess it from the title, location or text, which
# marked "remote state" (Terraform) remote, so theirs stays unused.
_TAGGED_REMOTE_BOARDS = frozenset({"indeed", "glassdoor", "zip_recruiter"})


def _structured_arrangement(row, site: str):
    """What the board itself says about the work arrangement, for apply_arrangement_to_job.

    Naukri's `work_from_home_type` names it; a tagged board's `is_remote` True means remote.
    False only means "not tagged remote", so it is no answer (None) and the JD cascade decides.
    """
    wfh = _clean(row.get("work_from_home_type"))
    if wfh:
        return wfh
    if site in _TAGGED_REMOTE_BOARDS and str(row.get("is_remote")) == "True":
        return True
    return None


def _employer_link(row, url: str, loop):
    """The employer's own posting for a JobSpy row (`job_url_direct`: Indeed, ZipRecruiter,
    Naukri and BDJobs fill it when the job is not hosted on the board), or None.

    A short link (grnh.se) is followed first, on the run's event loop; a link that names
    no known employer system is kept only when it leaves the board's own site.
    """
    from urllib.parse import urlparse
    direct = _clean(row.get("job_url_direct"))
    if not direct or not direct.startswith(("http://", "https://")):
        return None
    if is_short_link(direct):
        try:
            direct = loop.run_until_complete(resolve_short_link(direct))
        except Exception as e:
            logger.debug(f"Short link {direct} not resolved: {e}")
    link = employer_link(direct)
    if link:
        return link
    board = (urlparse(url).hostname or "").removeprefix("www.")
    host = (urlparse(direct).hostname or "").removeprefix("www.")
    return direct if host and host != board and not host.endswith("." + board) else None


def _fill_linkedin_descriptions(jobs_df, existing_ids, loop) -> int:
    """JobSpy's LinkedIn rows carry no description (its per-job fetch is off): new ones get it
    from LinkedIn's public job page (no account), paced, before they are stored. Writes into
    jobs_df; returns how many were filled."""
    from backend.scraper._shared.employer_text import missing_descriptions
    if jobs_df is None or jobs_df.empty or "site" not in jobs_df.columns:
        return 0
    todo = []
    for idx, row in jobs_df.iterrows():
        url = _clean(row.get("job_url")) or ""
        if str(row.get("site", "")).lower() != "linkedin" or _clean(row.get("description")) or not url:
            continue
        if make_external_id(_clean(row.get("company")) or "", _clean(row.get("title")) or "", url) in existing_ids:
            continue
        todo.append({"idx": idx, "url": url, "description": None})
    if not todo:
        return 0
    filled = loop.run_until_complete(missing_descriptions(todo))
    if "description" not in jobs_df.columns:
        jobs_df["description"] = None
    jobs_df["description"] = jobs_df["description"].astype(object)
    for t in todo:
        if t["description"]:
            jobs_df.at[t["idx"], "description"] = t["description"]
    return filled


def get_setting_value(db: Session, key: str, default: str = "") -> str:
    """Read a single Setting row's value by key, returning ``default`` if not set."""
    return get_setting(db, key, default)


def apply_title_filters(jobs_df, include_keywords: list, exclude_keywords: list):
    """Filter jobs by title include/exclude keywords (whole-word matching); returns (kept_df, rejected_df)."""
    import pandas as pd

    if jobs_df is None or jobs_df.empty:
        return jobs_df, pd.DataFrame()

    mask = pd.Series(True, index=jobs_df.index)

    if include_keywords:
        pattern = "|".join(include_pattern(kw) for kw in include_keywords)
        mask &= jobs_df["title"].str.contains(pattern, case=False, na=False, regex=True)

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


def trim_postings(jobs_df, results_wanted: int, hours_old: int,
                  fetched_results: int, fetched_hours: int):
    """Cut a shared fetch (MT-8, made at the largest results_wanted / hours_old among the
    subscribers) down to one account's own values.

    - hours_old: rows whose `date_posted` is older than the account's window are dropped.
      JobSpy dates are day-granular, so the cut is too (a row posted on the cutoff day is
      kept); a row without a date is kept, as JobSpy itself would have returned it.
    - results_wanted: JobSpy's limit is per board, so the first N rows of each board are
      kept, in the order the boards returned them.
    Nothing is touched when the account's values equal the fetched ones."""
    import pandas as pd
    from datetime import timedelta
    if jobs_df is None or jobs_df.empty:
        return jobs_df
    if hours_old and fetched_hours and hours_old < fetched_hours and "date_posted" in jobs_df.columns:
        cutoff = pd.Timestamp((datetime.now(timezone.utc) - timedelta(hours=hours_old)).date())
        posted = pd.to_datetime(jobs_df["date_posted"], errors="coerce")
        jobs_df = jobs_df[posted.isna() | (posted >= cutoff)]
    if results_wanted and fetched_results and results_wanted < fetched_results and not jobs_df.empty:
        if "site" in jobs_df.columns:
            jobs_df = jobs_df.groupby("site", sort=False, group_keys=False).head(results_wanted)
        else:
            jobs_df = jobs_df.head(results_wanted)
    return jobs_df


def _run_sync(search, proxy_url: str = None, shared=None) -> dict:
    """Execute a single JobSpy search and return results dict.

    `shared` (a `backend.scraper.targets.SharedFetch`, MT-8): searches of several accounts
    with the same target key share one `scrape_jobs()` call made at the largest
    results_wanted / hours_old; this search then trims its copy to its own values and runs
    its own filters, dedup and checks under the current account."""
    start_time = time.time()
    # One entry per configured board so a failure is visible next to boards that worked;
    # seeded here (not after the call) so failure paths can still say what was asked for.
    breakdown = {}

    try:
        from jobspy import scrape_jobs

        # Build source list — filter out 'direct' which is Playwright
        sources = [s for s in (search.sources or []) if s != "direct"]
        if not sources:
            return {"jobs_found": 0, "new_jobs": 0, "ignored_jobs": 0,
                    "error": "No JobSpy sources configured", "source_breakdown": {}}
        breakdown = {s: {"seen": 0, "new": 0} for s in sources}

        kwargs = jobspy_kwargs(search, proxy_url)

        if shared is None:
            logger.info(f"Running JobSpy search: {search.name} — term='{search.search_term}', sources={sources}")
            jobs_df = scrape_jobs(**kwargs)
            captured = _errors_of(jobs_df)
        else:
            own_results, own_hours = kwargs["results_wanted"], kwargs["hours_old"]
            kwargs["results_wanted"] = shared.params.get("results_wanted") or own_results
            kwargs["hours_old"] = shared.params.get("hours_old") or own_hours

            def _fetch():
                logger.info(f"Running shared JobSpy search: {search.name} — term='{search.search_term}', "
                            f"sources={sources}, results={kwargs['results_wanted']}, hours={kwargs['hours_old']}")
                df = scrape_jobs(**kwargs)
                return df, _errors_of(df)
            jobs_df, captured = shared.get_sync(_fetch)
            jobs_df = trim_postings(jobs_df, own_results, own_hours,
                                    kwargs["results_wanted"], kwargs["hours_old"])
        _merge_source_errors(breakdown, _board_errors(captured, jobs_df, sources))
        # Rows each board returned, counted here — before the title filter, the
        # company allow-list and the company exclude. It is the only truthful
        # answer to "did this board deliver anything at all?": `seen` counts what
        # survived the filters, and `filtered` counts only rejected rows that
        # were new enough to store, so a rejected row already in the database
        # leaves both at 0 on every run after the first.
        _count_returned(breakdown, jobs_df)

        if jobs_df is None or jobs_df.empty:
            duration = time.time() - start_time
            return {"jobs_found": 0, "new_jobs": 0, "ignored_jobs": 0, "error": None,
                    "duration": duration, "source_breakdown": breakdown}

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

        # Company exclude (global=full match, per-search=full match,
        # plus active companies when search.exclude_active_companies is on)
        db_excl = SessionLocal()
        try:
            from backend.scraper._shared.filters import build_search_exclude_sets
            global_exclude_set, search_exclude_set = build_search_exclude_sets(db_excl, search)
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

        # Per-board `seen` counted after filtering, so sum(seen) == jobs_found.
        if jobs_df is not None and not jobs_df.empty and "site" in jobs_df.columns:
            for site_name, count in jobs_df["site"].value_counts().items():
                key = str(site_name).lower()
                breakdown.setdefault(key, {"seen": 0, "new": 0})["seen"] = int(count)

        # Save to DB, dedup via external_id
        db = SessionLocal()
        new_jobs = 0
        # Rejected rows are still written as status "ignored" so the next run dedups them;
        # count them too, since otherwise storing 8 rows could report only "6 seen, +6 new".
        ignored_jobs = 0
        # Hoisted per run (not per job): one event loop, one company lookup, one parsed phrase list —
        # avoids a fresh loop + full company scan + Settings JSON-parse thousands of times per scrape.
        import asyncio as _asyncio
        from backend.models.db import build_company_lookup
        from backend.analyzer.h1b_checker import load_exclusion_phrases
        h1b_loop = _asyncio.new_event_loop()
        try:
            existing_ids = get_existing_external_ids(db)
            company_lookup = build_company_lookup(db)
            phrases = load_exclusion_phrases(db)

            # The loop below writes rows; H-1B lookups for the new jobs happen before it (S2-01).
            # Non-fatal like `_apply_h1b_inline`: without it the jobs keep what the cache has.
            from backend.scraper._shared.analysis import prefetch_h1b
            _new_companies = [
                _clean(r.get("company")) for _, r in jobs_df.iterrows()
                if make_external_id(_clean(r.get("company")) or "", _clean(r.get("title")) or "",
                                    _clean(r.get("job_url")) or "") not in existing_ids
            ]
            _prefetch = prefetch_h1b(_new_companies)
            try:
                h1b_loop.run_until_complete(_prefetch)
            except Exception as e:
                _prefetch.close()
                logger.warning(f"JobSpy H-1B prefetch skipped for '{search.name}': {e}")

            try:
                _filled = _fill_linkedin_descriptions(jobs_df, existing_ids, h1b_loop)
                if _filled:
                    logger.info(f"JobSpy: LinkedIn description for {_filled} new jobs in '{search.name}'")
            except Exception as e:  # the jobs are stored without one, as before
                logger.warning(f"JobSpy LinkedIn descriptions skipped for '{search.name}': {e}")

            for _, row in jobs_df.iterrows():
                company = _clean(row.get("company")) or ""
                title = _clean(row.get("title")) or ""
                url = _clean(row.get("job_url")) or ""
                ext_id = make_external_id(company, title, url)

                if ext_id in existing_ids:
                    continue

                content_hash = make_content_hash(company, title)
                apply_url = _employer_link(row, url, h1b_loop)

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
                    apply_url=apply_url,
                    source=source,
                    search_id=search.id,
                    description=_clean(row.get("description")),
                    location=_clean(row.get("location")),
                    # Set below from the board's own remote tag where it has one
                    # (_structured_arrangement), else from the JD cascade.
                    remote=None,
                    status="new",
                    seen=False,
                    saved=False,
                )

                # Extract salary if present in JobSpy results. Only a yearly amount (or one
                # with no interval) is stored; hourly/daily/weekly/monthly pay is not a yearly
                # figure, and a "yearly" one under 1000 is not a salary.
                min_amount = row.get("min_amount")
                max_amount = row.get("max_amount")
                if not _jobspy_yearly(row.get("interval"), min_amount, max_amount):
                    min_amount = max_amount = None
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

                # H-1B check + salary extraction inline, using the shared loop/lookup/phrases hoisted above.
                _apply_h1b_inline(job, db, company_lookup=company_lookup, phrases=phrases, loop=h1b_loop)
                try:
                    from backend.analyzer.salary_extractor import apply_salary_to_job
                    from backend.analyzer.work_arrangement import apply_arrangement_to_job
                    from backend.analyzer.location import apply_location_to_job
                    apply_salary_to_job(job, getattr(job, "_h1b_median", None))
                    apply_arrangement_to_job(job, structured=_structured_arrangement(row, site))
                    apply_location_to_job(job)
                except Exception as analysis_err:
                    logger.warning(f"Inline salary analysis failed for {title}: {analysis_err}")

                if job.h1b_jd_flag:
                    _phrase = getattr(job, "_h1b_matched_phrase", None) or "?"
                    logger.info(f"Skipping job (body exclusion): {title} @ {company} — matched phrase: {_phrase!r}")
                    continue

                try:
                    with db.begin_nested():
                        db.add(job)
                        db.flush()
                    if counts_as_new(job):
                        new_jobs += 1
                        breakdown.setdefault(site or "unknown", {"seen": 0, "new": 0})["new"] += 1
                    existing_ids.add(ext_id)
                except IntegrityError:
                    logger.debug(f"Duplicate external_id for '{title}' at {company}, skipping")
                    continue
                except Exception as e:
                    logger.warning(f"Insert failed for '{title}' at {company} ({url}): {e}")
                    continue

            # Save filtered-out jobs as "ignored" for dedup purposes
            if rejected_df is not None and not rejected_df.empty:
                for _, row in rejected_df.iterrows():
                    company = _clean(row.get("company")) or ""
                    title = _clean(row.get("title")) or ""
                    url = _clean(row.get("job_url")) or ""
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
                        description=_clean(row.get("description")),
                        location=_clean(row.get("location")),
                        status="ignored",
                        seen=False,
                        saved=False,
                    )
                    try:
                        with db.begin_nested():
                            db.add(job)
                            db.flush()
                        existing_ids.add(ext_id)
                        ignored_jobs += 1
                        entry = breakdown.setdefault(site or "unknown", {"seen": 0, "new": 0})
                        entry["filtered"] = entry.get("filtered", 0) + 1
                    except IntegrityError:
                        continue
                    except Exception as e:
                        logger.warning(f"Insert failed for ignored job '{title}' at {company} ({url}): {e}")
                        continue

            db.commit()

            search_obj = db.query(Search).filter(Search.id == search.id).first()
            if search_obj:
                search_obj.last_run_at = datetime.now(timezone.utc)
                db.commit()

        finally:
            h1b_loop.close()
            db.close()

        duration = time.time() - start_time

        from backend.activity import log_activity
        log_activity("scrape", f"JobSpy search '{search.name}': {new_jobs} new / {jobs_found} found"
                     + (f" ({ignored_jobs} filtered out)" if ignored_jobs else "")
                     + f" in {duration:.1f}s")

        return {"jobs_found": jobs_found, "new_jobs": new_jobs, "ignored_jobs": ignored_jobs,
                "error": None, "duration": duration, "source_breakdown": breakdown}

    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"JobSpy search failed for '{search.name}': {e}")

        from backend.activity import log_activity
        log_activity("scrape", f"JobSpy search '{search.name}' failed: {e}")

        return {"jobs_found": 0, "new_jobs": 0, "ignored_jobs": 0, "error": str(e),
                "duration": duration, "source_breakdown": breakdown}


async def run(search, proxy_url: str = None, shared=None) -> dict:
    """Async entry point — offloads the synchronous JobSpy call to a thread (the account
    context travels with it: to_thread copies the contextvars)."""
    if shared is None:
        return await asyncio.to_thread(_run_sync, search, proxy_url)
    return await asyncio.to_thread(_run_sync, search, proxy_url, shared)
