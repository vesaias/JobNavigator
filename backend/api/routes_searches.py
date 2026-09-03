"""Search config CRUD endpoints."""
import asyncio
import logging
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from backend.models.db import get_db, Search, Setting, ScrapeLog, Job

logger = logging.getLogger("jobnavigator.routes_searches")

# The two seeded browser-extension searches ("Extension" / "Extension LI") have
# no scraper and must not be deleted — jobs arrive by push from the extension.
# PATCH stays open (the editor saves their filters through it).
EXTENSION_MODES = ("extension", "linkedin_extension")

router = APIRouter(prefix="/searches", tags=["searches"])

# In-memory store for async test results
_test_results: dict[str, dict] = {}  # run_id -> {"status": "running"|"done", "result": ...}


class SearchCreate(BaseModel):
    name: str
    active: bool = True
    sources: list = ["linkedin", "indeed", "zip_recruiter", "google"]
    search_mode: str = "keyword"
    search_term: Optional[str] = None
    direct_url: Optional[str] = None
    location: str = "United States"
    is_remote: Optional[bool] = None
    job_type: str = "fulltime"
    # Optional so the editor can clear the field: an explicit null falls back to
    # the column default on insert (SQLAlchemy applies it for a None value).
    hours_old: Optional[int] = 24
    results_wanted: Optional[int] = 50
    title_include_keywords: list = []
    title_exclude_keywords: list = ["intern", "junior", "associate"]
    company_filter: list = []
    company_exclude: list = []
    exclude_active_companies: bool = False
    max_pages: int = 50
    min_fit_score: int = 0
    require_salary: bool = False
    run_interval_minutes: int = 0
    auto_scoring_depth: str = "off"


@router.get("")
def list_searches(db: Session = Depends(get_db)):
    searches = db.query(Search).order_by(Search.created_at).all()
    # Latest ScrapeLog per search → surface the most recent run's outcome so the
    # UI can show a live summary/health line (mirrors what /companies does).
    from sqlalchemy import func, and_
    from backend.models.db import ScrapeLog
    latest_sub = (
        db.query(ScrapeLog.search_id, func.max(ScrapeLog.ran_at).label("mx"))
        .filter(ScrapeLog.search_id.isnot(None))
        .group_by(ScrapeLog.search_id).subquery()
    )
    last_log = {
        str(l.search_id): l
        for l in db.query(ScrapeLog).join(
            latest_sub, and_(ScrapeLog.search_id == latest_sub.c.search_id,
                             ScrapeLog.ran_at == latest_sub.c.mx)).all()
    }
    return [_search_to_dict(s, last_log.get(str(s.id))) for s in searches]


@router.post("")
def create_search(data: SearchCreate, db: Session = Depends(get_db)):
    search = Search(**data.model_dump())
    db.add(search)
    db.commit()
    return _search_to_dict(search)


@router.patch("/{search_id}")
def update_search(search_id: str, updates: dict, db: Session = Depends(get_db)):
    search = db.query(Search).filter(Search.id == search_id).first()
    if not search:
        raise HTTPException(status_code=404, detail="Search not found")

    allowed = {
        "name", "active", "sources", "search_mode", "search_term", "direct_url",
        "location", "is_remote", "job_type", "hours_old", "results_wanted",
        "title_include_keywords", "title_exclude_keywords", "company_filter",
        "company_exclude", "exclude_active_companies", "max_pages", "min_fit_score",
        "require_salary", "auto_scoring_depth", "run_interval_minutes",
    }
    for key, value in updates.items():
        if key in allowed:
            setattr(search, key, value)
    db.commit()
    return _search_to_dict(search)


@router.delete("/{search_id}")
def delete_search(search_id: str, db: Session = Depends(get_db)):
    search = db.query(Search).filter(Search.id == search_id).first()
    if not search:
        raise HTTPException(status_code=404, detail="Search not found")
    if search.search_mode in EXTENSION_MODES:
        raise HTTPException(
            status_code=409,
            detail="Built-in extension searches cannot be deleted — "
                   "pause it instead to stop importing captured jobs",
        )
    # R3-A-08: same trap as delete_company — ScrapeLog.search_id (every run this
    # search ever did) and Job.search_id (every job it stored) are plain FKs with
    # no ON DELETE in the live schema, so a search that had ever run could not be
    # deleted and the endpoint returned a bare 500. Orphan both: the jobs are kept
    # on purpose (they carry their own company/title), and the audit rows stay
    # readable in the run history.
    db.query(ScrapeLog).filter(ScrapeLog.search_id == search.id).update(
        {"search_id": None}, synchronize_session=False)
    db.query(Job).filter(Job.search_id == search.id).update(
        {"search_id": None}, synchronize_session=False)
    db.delete(search)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        logger.error(f"delete_search({search_id}) blocked by a foreign key: {e}")
        raise HTTPException(
            status_code=409,
            detail="Could not delete this search — another record still references it",
        ) from e
    return {"deleted": True}


@router.post("/{search_id}/run", status_code=202)
async def trigger_search(search_id: str, auto_score: bool = None, db: Session = Depends(get_db)):
    """Trigger a single search. Returns immediately with a run_id — the run continues
    in the background and is pollable via /api/monitor/active (scope_key = search id).
    auto_score: True/False override, null=use the search's auto_scoring_depth."""
    search = db.query(Search).filter(Search.id == search_id).first()
    if not search:
        raise HTTPException(status_code=404, detail="Search not found")
    if search.search_mode in EXTENSION_MODES:
        raise HTTPException(
            status_code=409,
            detail="Extension searches have no scraper to run — "
                   "jobs arrive from the browser extension",
        )
    search_name = search.name

    async def _do():
        from backend.scraper.orchestrator import _run_search_by_id as run_single_search
        result = await run_single_search(search_id, auto_score=auto_score)
        # Never forward scraper exception strings to the client (py/stack-trace-exposure);
        # the real text is already persisted on the ScrapeLog row and logged here.
        if isinstance(result, dict) and result.get("error"):
            logger.warning("Search %s finished with scrape error: %s", search_id, result.get("error"))
        # Returned string becomes JobRun.result_summary (Stats -> Run history).
        if isinstance(result, dict):
            summary = (f"{search_name} - {result.get('jobs_found', 0)} seen, "
                       f"+{result.get('new_jobs', 0)} new")
            # R3-A-03: name the boards that hard-failed, so "9 seen, +0 new"
            # can't be mistaken for a quiet day on every configured source.
            from backend.scraper.orchestrator import describe_source_errors
            failed = describe_source_errors(result.get("source_breakdown"))
            return f"{summary} · {failed}" if failed else summary
        return f"{search_name} - nothing ran"

    from backend.job_monitor import launch_background, JobAlreadyRunningError
    try:
        run_id = launch_background("search_run", _do, trigger="manual",
                                   scope_key=search_id, meta={"search": search_name})
        return {"run_id": run_id, "status": "running", "search_id": search_id, "search": search_name}
    except JobAlreadyRunningError as e:
        logger.info("Duplicate search run rejected for %s", search_id)
        return JSONResponse(status_code=409, content={"detail": f"{e.job_type} is already running"})


@router.post("/{search_id}/test")
async def test_search(search_id: str, db: Session = Depends(get_db)):
    """Launch a search test in the background. Returns run_id to poll for results.

    For fast modes (keyword), runs synchronously and returns results directly.
    For slow modes (levels_fyi, linkedin_personal), launches async and returns 202.
    """
    search = db.query(Search).filter(Search.id == search_id).first()
    if not search:
        raise HTTPException(status_code=404, detail="Search not found")

    # Slow modes: launch in background, return run_id for polling
    if search.search_mode in ("levels_fyi", "linkedin_personal", "jobright", "freehire"):
        run_id = str(uuid.uuid4())[:8]
        _test_results[run_id] = {"status": "running", "result": None}

        # Snapshot search fields needed by the test functions (DB session won't survive across await)
        from backend.models.db import SessionLocal
        async def _run_test():
            test_db = SessionLocal()
            try:
                test_search_obj = test_db.query(Search).filter(Search.id == search_id).first()
                if not test_search_obj:
                    _test_results[run_id] = {"status": "done", "result": {"error": "Search not found"}}
                    return
                if search.search_mode == "levels_fyi":
                    result = await _test_levelsfyi_search(test_search_obj, test_db)
                elif search.search_mode == "jobright":
                    from backend.scraper.sources.jobright import preview as test_jobright
                    result = await test_jobright(test_search_obj, test_db)
                elif search.search_mode == "freehire":
                    from backend.scraper.sources.freehire import preview as test_freehire
                    result = await test_freehire(test_search_obj, test_db)
                else:
                    from backend.scraper.sources.linkedin_personal import preview as test_linkedin_personal
                    result = await test_linkedin_personal(test_search_obj, test_db)
                _test_results[run_id] = {"status": "done", "result": result}
            except Exception as e:
                logger.error(f"Test run {run_id} failed: {e}")
                _test_results[run_id] = {"status": "done", "result": {"error": str(e)}}
            finally:
                test_db.close()

        asyncio.create_task(_run_test())
        return JSONResponse(status_code=202, content={"run_id": run_id, "status": "running"})

    if search.search_mode != "keyword":
        raise HTTPException(status_code=400, detail="Test only supports keyword, levels_fyi, linkedin_personal, jobright, and freehire searches")

    # ── Keyword (JobSpy) test — runs synchronously ──
    import re
    import time
    import pandas as pd
    from jobspy import scrape_jobs

    sources = [s for s in (search.sources or []) if s != "direct"]
    if not sources:
        raise HTTPException(status_code=400, detail="No JobSpy sources configured")

    proxy_row = db.query(Setting).filter(Setting.key == "proxy_url").first()
    proxy_url = proxy_row.value if proxy_row and proxy_row.value else None

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

    start = time.time()
    try:
        jobs_df = await asyncio.to_thread(scrape_jobs, **kwargs)
    except Exception:
        logger.exception("JobSpy scrape_jobs failed during test for search %s", search.name)
        return {
            "search_name": search.name,
            "error": "Scrape failed; see server logs for details.",
            "config": {
                "sources": sources,
                "search_term": kwargs["search_term"],
                "location": kwargs["location"],
                "results_wanted": kwargs["results_wanted"],
                "hours_old": kwargs["hours_old"],
                "job_type": kwargs["job_type"],
                "is_remote": search.is_remote,
                "proxy": bool(proxy_url),
            },
        }

    duration = round(time.time() - start, 1)

    if jobs_df is None or jobs_df.empty:
        return {
            "search_name": search.name,
            "duration": duration,
            "raw_count": 0,
            "after_filter": 0,
            "body_excluded_count": 0,
            "body_unchecked_count": 0,
            "body_phrase_count": 0,
            "source_breakdown": {},
            "company_breakdown": {},
            "include_keywords": search.title_include_keywords or [],
            "exclude_keywords": search.title_exclude_keywords or [],
            "company_filter": search.company_filter or [],
            "company_exclude": search.company_exclude or [],
            "jobs": [],
            "config": {
                "sources": sources,
                "search_term": kwargs["search_term"],
                "location": kwargs["location"],
                "results_wanted": kwargs["results_wanted"],
                "hours_old": kwargs["hours_old"],
                "job_type": kwargs["job_type"],
                "is_remote": search.is_remote,
                "proxy": bool(proxy_url),
            },
        }

    raw_count = len(jobs_df)

    # Apply title filters
    include_kw = search.title_include_keywords or []
    exclude_kw = search.title_exclude_keywords or []

    mask = pd.Series(True, index=jobs_df.index)
    if include_kw:
        pattern = "|".join(include_kw)
        mask &= jobs_df["title"].str.contains(pattern, case=False, na=False)
    if exclude_kw:
        pattern = "|".join(r'\b' + re.escape(kw) + r'\b' for kw in exclude_kw)
        mask &= ~jobs_df["title"].str.contains(pattern, case=False, na=False, regex=True)

    # Company filter (exact match, case-insensitive)
    company_filter = search.company_filter or []
    if company_filter:
        cf_set = {cf.lower() for cf in company_filter}
        mask &= jobs_df["company"].str.lower().isin(cf_set)

    # Company exclude (global + per-search + active companies if flag on)
    import json
    from backend.scraper._shared.filters import build_search_exclude_sets
    global_exclude_set, search_exclude_set = build_search_exclude_sets(db, search)
    all_exclude = list(global_exclude_set | search_exclude_set)
    if global_exclude_set or search_exclude_set:
        def _kw_excl(name):
            nl = str(name).lower()
            if nl in global_exclude_set:
                return True
            return nl in search_exclude_set
        excl_mask = jobs_df["company"].apply(_kw_excl)
        mask &= ~excl_mask

    # Body exclusion description check (H-1B + language phrases)
    body_row = db.query(Setting).filter(Setting.key == "body_exclusion_phrases").first()
    body_phrases = []
    if body_row and body_row.value:
        try:
            body_phrases = json.loads(body_row.value)
        except json.JSONDecodeError:
            pass
    # R3-A-01: the preview used to fold a body-exclusion drop into the same
    # anonymous "filtered" bucket as a title miss, so a job the run would store
    # as `ignored` looked kept. Record which phrase hit (and which rows could
    # not be checked at all) so each row can say so inline.
    body_hits = {}          # df index -> the exclusion phrase that matched
    body_unchecked = set()  # df index -> passed the title layers, but had no description
    if body_phrases:
        from backend.analyzer.h1b_checker import scan_jd_for_h1b_flags
        for idx in jobs_df.index:
            if mask[idx]:
                desc = str(jobs_df.at[idx, "description"]) if "description" in jobs_df.columns else ""
                if desc and desc != "nan":
                    result = scan_jd_for_h1b_flags(desc, body_phrases)
                    if result["jd_flag"]:
                        body_hits[idx] = result["matched_phrase"] or "matched"
                        mask[idx] = False
                else:
                    body_unchecked.add(idx)

    # Source breakdown
    source_breakdown = {}
    if "site" in jobs_df.columns:
        source_breakdown = jobs_df["site"].value_counts().to_dict()

    # Company breakdown (top 20)
    company_breakdown = {}
    if "company" in jobs_df.columns:
        company_breakdown = jobs_df["company"].value_counts().head(20).to_dict()

    # Build per-job results
    results = []
    for idx, row in jobs_df.iterrows():
        kept = bool(mask[idx])
        company = str(row.get("company", ""))
        title = str(row.get("title", ""))
        url = str(row.get("job_url", ""))
        site = str(row.get("site", ""))
        location = str(row.get("location", ""))
        desc = str(row.get("description", ""))
        min_sal = row.get("min_amount")
        max_sal = row.get("max_amount")

        # Figure out rejection reason
        reason = None
        if not kept:
            title_lower = title.lower()
            if include_kw and not any(kw.lower() in title_lower for kw in include_kw):
                reason = f"No match for: {', '.join(include_kw)}"
            elif exclude_kw:
                matched = [kw for kw in exclude_kw if re.search(r'\b' + re.escape(kw) + r'\b', title_lower)]
                if matched:
                    reason = f"Excluded by: {', '.join(matched)}"
            if not reason and company_filter:
                company_lower = company.lower()
                if company_lower not in {cf.lower() for cf in company_filter}:
                    reason = f"Company filter: {', '.join(company_filter)}"
            if not reason and (global_exclude_set or search_exclude_set):
                company_lower = company.lower()
                if company_lower in global_exclude_set:
                    reason = f"Company excluded (global): {company_lower}"
                elif company_lower in search_exclude_set:
                    reason = f"Company excluded: {company_lower}"
            if not reason and idx in body_hits:
                reason = f"Body exclusion: {body_hits[idx]}"
            if not reason:
                reason = "Filtered"

        salary = None
        try:
            if min_sal and str(min_sal) != "nan":
                salary = f"${int(float(min_sal)):,}"
                if max_sal and str(max_sal) != "nan":
                    salary += f" – ${int(float(max_sal)):,}"
        except (ValueError, TypeError):
            pass

        has_desc = bool(desc and desc != "nan" and len(desc) > 50)

        results.append({
            "title": title,
            "company": company,
            "url": url,
            "source": site,
            "location": location if location != "nan" else "",
            "salary": salary,
            "has_description": has_desc,
            "desc_length": len(desc) if has_desc else 0,
            "kept": kept,
            "reason": reason,
            # R3-A-01: the phrase that would make the run store this row as
            # `ignored`, or null. `body_checked` is false when there was no
            # description to scan, so the preview says "needs the description"
            # rather than quietly implying the row passed.
            "body_excluded_by": body_hits.get(idx),
            "body_checked": bool(body_phrases) and idx not in body_unchecked,
        })

    after_filter = sum(1 for j in results if j["kept"])
    body_excluded_count = len(body_hits)
    body_unchecked_count = len(body_unchecked)

    return {
        "search_name": search.name,
        "duration": duration,
        "raw_count": raw_count,
        "after_filter": after_filter,
        # R3-A-01 footer arithmetic: kept · title/company-filtered · would-be-ignored
        "body_excluded_count": body_excluded_count,
        "body_unchecked_count": body_unchecked_count,
        "body_phrase_count": len(body_phrases),
        "source_breakdown": source_breakdown,
        "company_breakdown": company_breakdown,
        "include_keywords": include_kw,
        "exclude_keywords": exclude_kw,
        "company_filter": company_filter,
        "company_exclude": all_exclude,
        "jobs": results,
        "config": {
            "sources": sources,
            "search_term": kwargs["search_term"],
            "location": kwargs["location"],
            "results_wanted": kwargs["results_wanted"],
            "hours_old": kwargs["hours_old"],
            "job_type": kwargs["job_type"],
            "is_remote": search.is_remote,
            "proxy": bool(proxy_url),
        },
    }


@router.get("/test-result/{run_id}")
async def get_test_result(run_id: str):
    """Poll for async test results. Returns 200 with result when done, 202 while running."""
    entry = _test_results.get(run_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Test run not found")
    if entry["status"] == "running":
        return JSONResponse(status_code=202, content={"run_id": run_id, "status": "running"})
    result = entry["result"]
    if len(_test_results) > 20:
        oldest = list(_test_results.keys())[:len(_test_results) - 20]
        for k in oldest:
            _test_results.pop(k, None)
    return result


async def _test_levelsfyi_search(search, db):
    """Test a levels.fyi search — scrape via Playwright, return results without saving."""
    import re
    import time
    from backend.scraper.sources.levelsfyi import _scrape_levelsfyi
    from backend.scraper._shared.browser import _get_browser
    from backend.scraper._shared.filters import _apply_company_filters
    if not search.direct_url:
        raise HTTPException(status_code=400, detail="No levels.fyi URL configured")

    start = time.time()
    pw = None
    browser = None
    try:
        import asyncio
        pw, browser = await _get_browser()
        search_max_pages = search.max_pages or 50
        raw_jobs = await _scrape_levelsfyi(search.direct_url, browser=browser, max_pages=search_max_pages)

        # Retry up to 3 times if 0 results (levels.fyi rate-limiting / slow render)
        retry_delays = [10, 20, 30]
        for attempt, delay in enumerate(retry_delays, 1):
            if raw_jobs:
                break
            logger.info(f"levels.fyi test: 0 results, retry {attempt}/3 in {delay}s")
            await asyncio.sleep(delay)
            raw_jobs = await _scrape_levelsfyi(search.direct_url, browser=browser, max_pages=search_max_pages)
    except Exception as e:
        return {
            "search_name": search.name,
            "error": str(e),
            "config": {
                "mode": "levels_fyi",
                "url": search.direct_url,
            },
        }
    finally:
        if browser:
            await browser.close()
        if pw:
            await pw.stop()

    duration = round(time.time() - start, 1)

    if not raw_jobs:
        return {
            "search_name": search.name,
            "duration": duration,
            "raw_count": 0,
            "after_filter": 0,
            "source_breakdown": {"levels_fyi": 0},
            "company_breakdown": {},
            "include_keywords": search.title_include_keywords or [],
            "exclude_keywords": search.title_exclude_keywords or [],
            "company_filter": search.company_filter or [],
            "company_exclude": search.company_exclude or [],
            "jobs": [],
            "config": {"mode": "levels_fyi", "url": search.direct_url},
        }

    raw_count = len(raw_jobs)
    include_kw = search.title_include_keywords or []
    exclude_kw = search.title_exclude_keywords or []
    company_filter = search.company_filter or []

    # Company exclude (global + per-search + active companies if flag on)
    from backend.models.db import Setting
    import json
    from backend.scraper._shared.filters import build_search_exclude_sets
    global_exclude_set, search_exclude_set = build_search_exclude_sets(db, search)
    search_exclude = list(search_exclude_set)
    all_exclude = list(global_exclude_set | search_exclude_set)

    # Body exclusion phrases for desc check (H-1B + language)
    body_row = db.query(Setting).filter(Setting.key == "body_exclusion_phrases").first()
    body_phrases = []
    if body_row and body_row.value:
        try:
            body_phrases = json.loads(body_row.value)
        except json.JSONDecodeError:
            pass

    # Build per-company filter lookup
    company_filters = {}  # company_name_lower -> Company object
    company_names = {j.get("company", "") for j in raw_jobs if j.get("company")}
    for cn in company_names:
        from backend.models.db import find_company_by_name
        co = find_company_by_name(db, cn)
        if co and (co.title_exclude_keywords or (co.title_include_expr and co.title_include_expr.strip())):
            company_filters[cn.lower()] = co

    # Company breakdown
    from collections import Counter
    company_counts = Counter(j["company"] for j in raw_jobs if j.get("company"))
    company_breakdown = dict(company_counts.most_common(20))

    results = []
    for j in raw_jobs:
        title = j["title"]
        title_lower = title.lower()
        kept = True
        reason = None

        # Search-level title filters
        if include_kw and not any(kw.lower() in title_lower for kw in include_kw):
            kept = False
            reason = f"No match for: {', '.join(include_kw)}"
        if kept and exclude_kw:
            matched = [kw for kw in exclude_kw if re.search(r'\b' + re.escape(kw) + r'\b', title_lower)]
            if matched:
                kept = False
                reason = f"Excluded by: {', '.join(matched)}"
        if kept and company_filter:
            company_lower = (j.get("company") or "").lower()
            if company_lower not in {cf.lower() for cf in company_filter}:
                kept = False
                reason = f"Company filter: {', '.join(company_filter)}"

        # Company exclude (global=full match, per-search=full match)
        if kept and (global_exclude_set or search_exclude):
            company_lower = (j.get("company") or "").lower()
            if company_lower in global_exclude_set:
                kept = False
                reason = f"Company excluded (global): {company_lower}"
            elif company_lower in set(search_exclude):
                kept = False
                reason = f"Company excluded: {company_lower}"

        # Body exclusion description check (H-1B + language)
        if kept and body_phrases:
            desc = j.get("description") or ""
            if desc:
                from backend.analyzer.h1b_checker import scan_jd_for_h1b_flags
                body_result = scan_jd_for_h1b_flags(desc, body_phrases)
                if body_result["jd_flag"]:
                    kept = False
                    reason = f"Body exclusion: {body_result['jd_snippet'][:80] if body_result['jd_snippet'] else 'matched'}"

        # Per-company title filters
        if kept:
            co_name = (j.get("company") or "").lower()
            co_obj = company_filters.get(co_name)
            if co_obj:
                co_kept, co_rej = _apply_company_filters([j], co_obj)
                if not co_kept:
                    kept = False
                    # Build descriptive reason
                    if co_obj.title_exclude_keywords:
                        matched_kw = [kw for kw in co_obj.title_exclude_keywords if re.search(r'\b' + re.escape(kw.lower()) + r'\b', title_lower)]
                        if matched_kw:
                            reason = f"Company '{co_obj.name}' excludes: {', '.join(matched_kw)}"
                    if not reason and co_obj.title_include_expr:
                        reason = f"Company '{co_obj.name}' include expr: {co_obj.title_include_expr}"
                    if not reason:
                        reason = f"Company '{co_obj.name}' filter"

        salary = None
        if j.get("salary_min"):
            salary = f"${j['salary_min']:,}"
            if j.get("salary_max"):
                salary += f" – ${j['salary_max']:,}"

        # Show application_url if available, fallback to levels.fyi URL
        display_url = j.get("application_url") or j.get("url", "")
        desc = j.get("description") or ""
        has_desc = bool(desc and len(desc) > 50)

        results.append({
            "title": title,
            "company": j.get("company", ""),
            "url": display_url,
            "levelsfyi_url": j.get("url", ""),
            "source": "levels_fyi",
            "location": j.get("location", ""),
            "salary": salary,
            "has_description": has_desc,
            "desc_length": len(desc) if has_desc else 0,
            "kept": kept,
            "reason": reason,
            "date_posted": j.get("date_posted", ""),
        })

    after_filter = sum(1 for r in results if r["kept"])

    # Stats on enrichment
    with_apply_url = sum(1 for j in raw_jobs if j.get("application_url"))
    with_desc = sum(1 for j in raw_jobs if j.get("description") and len(j["description"]) > 50)
    with_salary = sum(1 for j in raw_jobs if j.get("salary_min"))

    return {
        "search_name": search.name,
        "duration": duration,
        "raw_count": raw_count,
        "after_filter": after_filter,
        "source_breakdown": {"levels_fyi": raw_count},
        "company_breakdown": company_breakdown,
        "enrichment": {
            "with_apply_url": with_apply_url,
            "with_description": with_desc,
            "with_salary": with_salary,
        },
        "include_keywords": include_kw,
        "exclude_keywords": exclude_kw,
        "company_filter": company_filter,
        "company_exclude": all_exclude,
        "company_filters_applied": list(company_filters.keys()),
        "jobs": results,
        "config": {"mode": "levels_fyi", "url": search.direct_url},
    }


def _last_source_errors(last_log) -> list:
    """Per-board failures from a search's most recent ScrapeLog row (R3-A-03)."""
    if last_log is None:
        return []
    from backend.scraper.orchestrator import source_errors, source_label
    return [
        {"source": key, "label": source_label(key), "error": err}
        for key, err in source_errors(getattr(last_log, "source_breakdown", None))
    ]


def _search_to_dict(s: Search, last_log=None) -> dict:
    return {
        "id": str(s.id),
        "name": s.name,
        "active": s.active,
        "sources": s.sources,
        "search_mode": s.search_mode,
        "search_term": s.search_term,
        "direct_url": s.direct_url,
        "location": s.location,
        "is_remote": s.is_remote,
        "job_type": s.job_type,
        "hours_old": s.hours_old,
        "results_wanted": s.results_wanted,
        "title_include_keywords": s.title_include_keywords,
        "title_exclude_keywords": s.title_exclude_keywords,
        "company_filter": s.company_filter,
        "company_exclude": s.company_exclude,
        "exclude_active_companies": bool(s.exclude_active_companies),
        "max_pages": s.max_pages,
        "min_fit_score": s.min_fit_score,
        "require_salary": s.require_salary,
        "auto_scoring_depth": s.auto_scoring_depth,
        "run_interval_minutes": s.run_interval_minutes,
        "last_run_at": s.last_run_at.isoformat() if s.last_run_at else None,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        # most recent ScrapeLog for this search (None until it has run once)
        "last_error": (last_log.error if last_log else None),
        "last_run_warning": (bool(last_log.is_warning) if last_log else False),
        # R3-A-03: boards that hard-failed on the last run, e.g.
        # [{"source": "zip_recruiter", "label": "ZipRecruiter", "error": "403"}]
        "last_source_errors": _last_source_errors(last_log),
        "last_jobs_found": (last_log.jobs_found if last_log else None),
        "last_new_jobs": (last_log.new_jobs if last_log else None),
        "last_duration": (last_log.duration_seconds if last_log else None),
    }
