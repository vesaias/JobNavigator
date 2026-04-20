"""JobSpy-backed keyword search source.

Uses the `jobspy` pip library to search LinkedIn, Indeed, ZipRecruiter, Google Jobs
via a single multi-board request. Returns a dict with jobs_found, new_jobs, error, duration.
"""
import asyncio
import json
import logging
import re
import time
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.models.db import SessionLocal, Search, Job, Setting, get_existing_external_ids
from backend.scraper._shared.dedup import make_external_id, make_content_hash

logger = logging.getLogger("jobnavigator.scraper.sources.jobspy")


def _apply_h1b_inline(job, db=None) -> None:
    """Sync-safe H-1B JD scan.

    Runs the async check_job_h1b inside a fresh event loop so this is safe to call
    from inside asyncio.to_thread() workers (which are sync contexts that may or may not
    have an event loop attached depending on Python config).
    """
    import asyncio as _asyncio
    from backend.analyzer.h1b_checker import check_job_h1b

    try:
        loop = _asyncio.new_event_loop()
        try:
            loop.run_until_complete(check_job_h1b(job, db=db))
        finally:
            loop.close()
    except Exception as e:
        logger.warning(f"_apply_h1b_inline failed for job {getattr(job, 'id', '?')}: {e}")


def get_setting_value(db: Session, key: str, default: str = "") -> str:
    """Read a single Setting row's value by key, returning ``default`` if not set."""
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


def _run_sync(search, proxy_url: str = None) -> dict:
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

                # Run H-1B check + language check + salary extraction inline.
                # _apply_h1b_inline uses a fresh event loop so it's safe in asyncio.to_thread workers.
                _apply_h1b_inline(job, db)
                try:
                    from backend.analyzer.salary_extractor import apply_salary_to_job
                    from backend.models.db import find_company_by_name
                    company_obj = find_company_by_name(db, company)
                    h1b_median = company_obj.h1b_median_salary if company_obj else None
                    apply_salary_to_job(job, h1b_median)
                except Exception as analysis_err:
                    logger.warning(f"Inline salary analysis failed for {title}: {analysis_err}")

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


async def run(search, proxy_url: str = None) -> dict:
    """Async entry point — offloads the synchronous JobSpy call to a thread."""
    return await asyncio.to_thread(_run_sync, search, proxy_url)
