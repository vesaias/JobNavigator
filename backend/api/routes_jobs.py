"""Job listing and management endpoints."""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, text, func
from backend.models.db import get_db, Job, find_company_by_name
from backend.scraper._shared.dedup import make_external_id, make_content_hash
from backend.analyzer.salary_extractor import apply_salary_to_job
from backend.job_monitor import launch_background, JobAlreadyRunningError
# LinkedIn extension enrichment — see sources/linkedin_extension.py
from backend.scraper.sources.linkedin_extension import (
    enrich as _scrape_linkedin_ids,  # noqa: F401
    _linkedin_import_progress,
)

logger = logging.getLogger("jobnavigator.jobs")

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/linkedin-import")
async def linkedin_import(request: Request, db: Session = Depends(get_db)):
    """Accept LinkedIn job IDs from the Chrome Extension, scrape via Voyager API in background."""
    data = await request.json()
    linkedin_ids = [str(lid).strip() for lid in data.get("linkedin_ids", []) if lid]

    if not linkedin_ids:
        return {"accepted": 0, "message": "No IDs provided"}

    # Quick pre-check: how many are already in DB (for immediate feedback to extension)
    existing_li_ids = {
        r[0] for r in db.query(Job.linkedin_job_id).filter(Job.linkedin_job_id != None).all()
    }
    new_count = sum(1 for lid in linkedin_ids if lid not in existing_li_ids)

    _linkedin_import_progress.clear()

    async def _do():
        await _scrape_linkedin_ids(linkedin_ids)

    try:
        run_id = launch_background("linkedin_import", _do, trigger="manual")
    except JobAlreadyRunningError as e:
        logger.info("Duplicate linkedin_import trigger rejected (%s)", e)
        raise HTTPException(
            status_code=409,
            detail=f"{e.job_type} is already running",
        )

    return {
        "accepted": len(linkedin_ids),
        "new": new_count,
        "already_imported": len(linkedin_ids) - new_count,
        "run_id": run_id,
        "message": f"Processing {new_count} new jobs ({len(linkedin_ids) - new_count} already imported)",
    }


@router.get("/linkedin-import/progress")
def linkedin_import_progress():
    """Poll LinkedIn import progress."""
    if not _linkedin_import_progress:
        return {"status": "idle"}
    return _linkedin_import_progress


@router.get("")
def list_jobs(
    status: Optional[str] = None,
    company: Optional[str] = None,
    min_score: Optional[int] = None,
    max_score: Optional[int] = None,
    search_id: Optional[str] = None,
    h1b_verdict: Optional[str] = None,
    remote: Optional[bool] = None,
    source: Optional[str] = None,
    saved: Optional[bool] = None,
    title_search: Optional[str] = None,
    min_salary: Optional[int] = None,
    max_salary: Optional[int] = None,
    sort_by: Optional[str] = Query("date", pattern="^(date|score|salary|company)$"),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    q = db.query(Job)

    if status:
        vals = [s.strip() for s in status.split(",") if s.strip()]
        q = q.filter(Job.status.in_(vals)) if len(vals) > 1 else q.filter(Job.status == vals[0])
    if company:
        company = _expand_company_filter(db, company)
        vals = [c.strip() for c in company.split(",") if c.strip()]
        q = q.filter(func.lower(Job.company).in_([v.lower() for v in vals]))
    if min_score is not None:
        q = q.filter(Job.best_cv_score >= float(min_score))
    if max_score is not None:
        q = q.filter(Job.best_cv_score <= float(max_score))
    if search_id:
        q = q.filter(Job.search_id == search_id)
    if h1b_verdict:
        vals = [v.strip() for v in h1b_verdict.split(",") if v.strip()]
        q = q.filter(Job.h1b_verdict.in_(vals)) if len(vals) > 1 else q.filter(Job.h1b_verdict == vals[0])
    if remote is not None:
        q = q.filter(Job.remote == remote)
    if source:
        vals = [s.strip() for s in source.split(",") if s.strip()]
        q = q.filter(Job.source.in_(vals)) if len(vals) > 1 else q.filter(Job.source == vals[0])
    if saved is not None:
        q = q.filter(Job.saved == saved)
    if title_search:
        q = q.filter(Job.title.ilike(f"%{title_search}%"))
    if min_salary is not None:
        q = q.filter(Job.salary_max >= min_salary)
    if max_salary is not None:
        q = q.filter(Job.salary_min <= max_salary)

    total = q.count()

    # Sort
    if sort_by == "score":
        q = q.order_by(desc(Job.best_cv_score).nullslast())
    elif sort_by == "salary":
        q = q.order_by(desc(Job.salary_max).nullslast())
    elif sort_by == "company":
        q = q.order_by(asc(Job.company))
    else:  # "date" (default)
        q = q.order_by(desc(Job.discovered_at))

    jobs = q.offset(offset).limit(limit).all()

    # Batch-check which jobs have tailored resumes (most recent per job)
    from backend.models.db import Resume
    job_ids = [j.id for j in jobs]
    tailored_map = {}
    if job_ids:
        rows = db.query(Resume.job_id, Resume.id).filter(
            Resume.job_id.in_(job_ids), Resume.is_base == False
        ).order_by(Resume.updated_at.desc()).all()
        for jid, rid in rows:
            if jid not in tailored_map:
                tailored_map[jid] = rid

    # Batch per-job in-flight op lookup (O(N running jobs) once, O(1) per row)
    import backend.job_monitor as _mon
    in_flight_map: dict[str, list[str]] = {}
    for r in _mon._running.values():
        if r.target_job_id is None:
            continue
        in_flight_map.setdefault(str(r.target_job_id), []).append(r.job_type)

    return {
        "total": total,
        "jobs": [
            _job_to_dict(
                j,
                tailored_resume_id=tailored_map.get(j.id),
                in_flight=in_flight_map.get(str(j.id), []),
            )
            for j in jobs
        ],
    }


def _expand_company_filter(db, company):
    """Expand a comma-separated list of company names to include all aliases
    of each. Picking 'Amazon' will match jobs whose Job.company is 'Audible',
    'AWS', or 'Prime Video & Amazon MGM Studios'. Returns a comma-separated
    string of names + aliases. Empty input returns None. Orphan names (no
    matching Company record) pass through unchanged."""
    if not company:
        return None
    vals = [c.strip() for c in company.split(",") if c.strip()]
    expanded = set()
    for v in vals:
        co = find_company_by_name(db, v)
        if co:
            expanded.add(co.name)
            for a in (co.aliases or []):
                expanded.add(a)
        else:
            expanded.add(v)
    return ",".join(sorted(expanded))


def _apply_common_filters(q, status=None, company=None, source=None, h1b_verdict=None,
                          min_score=None, saved=None, title_search=None, remote=None,
                          min_salary=None, max_salary=None, search_id=None):
    """Apply shared filter logic for job list and filter-list endpoints."""
    if status:
        vals = [s.strip() for s in status.split(",") if s.strip()]
        q = q.filter(Job.status.in_(vals)) if len(vals) > 1 else q.filter(Job.status == vals[0])
    if company:
        vals = [c.strip() for c in company.split(",") if c.strip()]
        # Caller is expected to pre-expand aliases via _expand_company_filter
        q = q.filter(func.lower(Job.company).in_([v.lower() for v in vals]))
    if source:
        vals = [s.strip() for s in source.split(",") if s.strip()]
        q = q.filter(Job.source.in_(vals)) if len(vals) > 1 else q.filter(Job.source == vals[0])
    if h1b_verdict:
        vals = [v.strip() for v in h1b_verdict.split(",") if v.strip()]
        q = q.filter(Job.h1b_verdict.in_(vals)) if len(vals) > 1 else q.filter(Job.h1b_verdict == vals[0])
    if min_score is not None:
        q = q.filter(Job.best_cv_score >= float(min_score))
    if saved is not None:
        q = q.filter(Job.saved == saved)
    if title_search:
        q = q.filter(Job.title.ilike(f"%{title_search}%"))
    if remote is not None:
        q = q.filter(Job.remote == remote)
    if min_salary is not None:
        q = q.filter(Job.salary_max >= min_salary)
    if max_salary is not None:
        q = q.filter(Job.salary_min <= max_salary)
    if search_id:
        q = q.filter(Job.search_id == search_id)
    return q


@router.get("/feed-stats")
def feed_stats(db: Session = Depends(get_db)):
    """Global counts for the v2 feed header — arrived today + not-yet-scored.
    (The paged /jobs response only sees the current page.)"""
    from datetime import datetime, timezone
    from sqlalchemy import func, text
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    arrived_today = db.query(func.count(Job.id)).filter(Job.discovered_at >= start).scalar() or 0
    unscored = db.execute(text(
        "select count(*) from jobs where status in ('new','saved') "
        "and (cv_scores is null or cv_scores::text = '{}')"
    )).scalar() or 0
    return {"arrived_today": int(arrived_today), "unscored": int(unscored)}


@router.get("/unscored-ids")
def unscored_ids(limit: int = 500, db: Session = Depends(get_db)):
    """IDs of not-yet-scored new/saved jobs — the header 'Score N unscored'
    action scores exactly these (they sort to the bottom by score, so the feed
    page won't contain them)."""
    from sqlalchemy import text
    rows = db.execute(text(
        "select id from jobs where status in ('new','saved') "
        "and (cv_scores is null or cv_scores::text = '{}') "
        "order by discovered_at desc limit :lim"
    ), {"lim": limit}).fetchall()
    return {"ids": [str(r[0]) for r in rows]}


@router.get("/companies/list")
def list_job_companies(
    status: Optional[str] = None,
    source: Optional[str] = None,
    h1b_verdict: Optional[str] = None,
    min_score: Optional[int] = None,
    saved: Optional[bool] = None,
    title_search: Optional[str] = None,
    remote: Optional[bool] = None,
    min_salary: Optional[int] = None,
    max_salary: Optional[int] = None,
    search_id: Optional[str] = None,
    counts: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    """Return distinct CANONICAL company names from jobs matching current filters,
    sorted. Aliases collapse to their parent (e.g. 'Audible' and 'Prime Video &
    Amazon MGM Studios' both surface as 'Amazon'). With ?counts=1, returns
    [{name, count}] sorted by open-role count (for the v2 Company filter)."""
    from backend.models.db import build_company_lookup
    if counts:
        from sqlalchemy import func
        cq = db.query(Job.company, func.count(Job.id)).filter(Job.company.isnot(None), Job.company != "")
        cq = _apply_common_filters(cq, status=status, source=source, h1b_verdict=h1b_verdict,
                                   min_score=min_score, saved=saved, title_search=title_search,
                                   remote=remote, min_salary=min_salary, max_salary=max_salary,
                                   search_id=search_id).group_by(Job.company)
        lookup = build_company_lookup(db)
        agg = {}
        for name, cnt in cq.all():
            co = lookup.get((name or "").lower())
            cname = co.name if co else name
            agg[cname] = agg.get(cname, 0) + cnt
        return [{"name": n, "count": c} for n, c in sorted(agg.items(), key=lambda x: (-x[1], x[0].lower()))]
    q = db.query(Job.company).distinct().filter(Job.company.isnot(None), Job.company != "")
    q = _apply_common_filters(q, status=status, source=source, h1b_verdict=h1b_verdict,
                              min_score=min_score, saved=saved, title_search=title_search,
                              remote=remote, min_salary=min_salary, max_salary=max_salary,
                              search_id=search_id)
    raw_names = [r[0] for r in q.all()]
    lookup = build_company_lookup(db)
    canonical = set()
    for raw in raw_names:
        co = lookup.get((raw or "").lower())
        canonical.add(co.name if co else raw)
    return sorted(canonical, key=str.lower)


@router.get("/sources/list")
def list_job_sources(
    counts: Optional[bool] = None,
    status: Optional[str] = None,
    company: Optional[str] = None,
    h1b_verdict: Optional[str] = None,
    min_score: Optional[int] = None,
    saved: Optional[bool] = None,
    title_search: Optional[str] = None,
    remote: Optional[bool] = None,
    min_salary: Optional[int] = None,
    max_salary: Optional[int] = None,
    search_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Return distinct source values from jobs matching current filters, sorted."""
    company = _expand_company_filter(db, company)
    # FEED-26: ?counts=1 returns [{name, count}] so the dropdown can show how many jobs each value has
    q = (db.query(Job.source, func.count(Job.id)) if counts else db.query(Job.source).distinct()).filter(Job.source.isnot(None), Job.source != "")
    q = _apply_common_filters(q, status=status, company=company, h1b_verdict=h1b_verdict,
                              min_score=min_score, saved=saved, title_search=title_search,
                              remote=remote, min_salary=min_salary, max_salary=max_salary,
                              search_id=search_id)
    if counts:
        return [{"name": r[0], "count": r[1]} for r in q.group_by(Job.source).order_by(Job.source).all()]
    rows = q.order_by(Job.source).all()
    return [r[0] for r in rows]


@router.get("/verdicts/list")
def list_job_verdicts(
    counts: Optional[bool] = None,
    status: Optional[str] = None,
    company: Optional[str] = None,
    source: Optional[str] = None,
    min_score: Optional[int] = None,
    saved: Optional[bool] = None,
    title_search: Optional[str] = None,
    remote: Optional[bool] = None,
    min_salary: Optional[int] = None,
    max_salary: Optional[int] = None,
    search_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Return distinct h1b_verdict values from jobs matching current filters."""
    company = _expand_company_filter(db, company)
    # FEED-26: ?counts=1 returns [{name, count}] so the dropdown can show how many jobs each value has
    q = (db.query(Job.h1b_verdict, func.count(Job.id)) if counts else db.query(Job.h1b_verdict).distinct()).filter(Job.h1b_verdict.isnot(None), Job.h1b_verdict != "")
    q = _apply_common_filters(q, status=status, company=company, source=source,
                              min_score=min_score, saved=saved, title_search=title_search,
                              remote=remote, min_salary=min_salary, max_salary=max_salary,
                              search_id=search_id)
    if counts:
        return [{"name": r[0], "count": r[1]} for r in q.group_by(Job.h1b_verdict).order_by(Job.h1b_verdict).all()]
    rows = q.order_by(Job.h1b_verdict).all()
    return [r[0] for r in rows]


@router.post("/save-from-extension")
async def save_from_extension(body: dict, db: Session = Depends(get_db)):
    """Save a job from the Chrome Extension to the Job Feed (no application created).

    Runs the same enrichment pipeline as LinkedIn passive capture:
      • title-include / title-exclude / company-exclude filters from the linked
        'Extension' search (matches linkedin_extension.py behavior)
      • salary extraction
      • H-1B / body-exclusion scan (flagged jobs go to status='ignored')
      • auto-score chain when the 'Extension' search has auto_scoring_depth set
    """
    from backend.analyzer.h1b_checker import check_job_h1b
    from backend.models.db import Search
    import uuid as _uuid
    import re as _re

    title = (body.get("title") or "").strip()
    company = (body.get("company") or "").strip()
    url = (body.get("url") or "").strip()
    description = (body.get("description") or "").strip() or None
    if not title or not company or not url:
        raise HTTPException(status_code=400, detail="title, company, and url are required")

    # Pull the per-company H-1B median (used by salary fallback) if we know the company.
    comp_obj = find_company_by_name(db, company)

    external_id = make_external_id(company, title, url)
    content_hash = make_content_hash(company, title)

    # Two-layer dedup: check external_id (URL-based) first, fall back to content_hash
    # (company+title) for cross-source catches where the same job was saved via a
    # different URL shape.
    existing = db.query(Job).filter(
        (Job.external_id == external_id) | (Job.content_hash == content_hash)
    ).first()
    if existing:
        if existing.status == "skip":
            existing.status = "new"
        # Backfill description if missing — share salary fallback shape with insert path.
        if description and not existing.description:
            existing.description = description
            from backend.analyzer.h1b_checker import resolve_company_h1b
            _hd = await resolve_company_h1b(db, existing.company or "", allow_live=False)
            apply_salary_to_job(existing, (_hd or {}).get("median_salary"))
        db.commit()
        # OPEN-12: `saved` is the field the extension reads — a row sitting at
        # `ignored` never reaches the feed, and re-saving it will not change that.
        out = {"id": str(existing.id), "company": existing.company, "title": existing.title,
               "new": False, "saved": existing.status != "ignored", "status": existing.status}
        if existing.status == "ignored":
            out["reason"] = "already saved earlier and filtered out then — it stays out of the feed"
        return out

    # Link to the hardcoded "Extension" search (manual Save-to-Job-Feed flow).
    # The "Extension LI" search (search_mode=linkedin_extension) is reserved for the
    # passive LinkedIn-collections capture path so the two flows can have independent
    # auto-score / title-filter configs.
    ext_search = db.query(Search).filter(Search.search_mode == "extension").first()

    # Apply per-search title + company filters (full parity with linkedin_extension flow):
    # title-exclude matched case-insensitively, AND merged with global title-exclude phrases.
    # Rejected jobs are still saved as 'ignored' so the dedup keys stick — this prevents
    # the user from re-saving the same rejected job over and over.
    # OPEN-12: the filters used to run silently — the job was stored `ignored`,
    # never appeared in the feed, and the person who saved it was told nothing.
    # `reject_message` is the sentence the extension shows; `filter_reject_reason`
    # stays the operator-facing log line.
    filter_reject_reason = None
    reject_message = None
    if ext_search is not None:
        from backend.models.db import get_global_title_exclude
        title_lower = title.lower()
        include_kw = ext_search.title_include_keywords or []
        exclude_kw = list(set((ext_search.title_exclude_keywords or []) + get_global_title_exclude(db)))
        if include_kw and not any(kw.lower() in title_lower for kw in include_kw):
            filter_reject_reason = f"title-include miss: needed any of {include_kw}"
            reject_message = ("title matches none of the required keywords ("
                              + ", ".join(include_kw) + ")")
        if not filter_reject_reason and exclude_kw:
            matched = [kw for kw in exclude_kw if _re.search(r'\b' + _re.escape(kw) + r'\b', title, _re.IGNORECASE)]
            if matched:
                filter_reject_reason = f"title-exclude hit: {', '.join(matched)}"
                reject_message = "title excluded by " + ", ".join(f"'{kw}'" for kw in matched)
        if not filter_reject_reason:
            company_lower = company.lower()
            for excl in (ext_search.company_exclude or []):
                if excl and excl.lower() == company_lower:
                    filter_reject_reason = f"company-exclude: {excl}"
                    reject_message = f"company excluded by '{excl}'"
                    break

    job = Job(
        external_id=external_id,
        content_hash=content_hash,
        company=company,
        title=title,
        url=url,
        description=description,
        source="extension",
        search_id=ext_search.id if ext_search else None,
        status="new",
    )

    # H-1B + body-exclusion scan, then salary (reuses the cache median that
    # check_job_h1b stashes). `check_job_h1b` already sets job.h1b_verdict.
    try:
        await check_job_h1b(job, db)
    except Exception as e:
        logger.warning(f"save-from-extension: analysis failed for '{title}' @ '{company}': {e}")

    if description:
        apply_salary_to_job(job, getattr(job, "_h1b_median", None))

    # Skip flagged jobs OR jobs that hit the search-filter set.
    if filter_reject_reason:
        logger.info(f"save-from-extension: filtered — '{title}' @ '{company}' — {filter_reject_reason}")
        job.status = "ignored"
    elif job.h1b_jd_flag:
        _phrase = getattr(job, "_h1b_matched_phrase", None) or "?"
        logger.info(f"save-from-extension: skipping (body exclusion) — '{title}' @ '{company}' — phrase: {_phrase!r}")
        job.status = "ignored"
        reject_message = f"description matched the excluded phrase '{_phrase}'"

    db.add(job)
    db.commit()
    db.refresh(job)

    # Auto-score chain — fire only for kept jobs and only when the extension search
    # opted in via auto_scoring_depth. Same pattern as the LinkedIn import endpoint.
    if (
        job.status == "new"
        and ext_search is not None
        and ext_search.auto_scoring_depth in ("light", "full")
    ):
        try:
            from backend.analyzer.cv_scorer import score_single_job
            launch_background(
                "analyze_job",
                score_single_job,
                trigger="manual",
                scope_key=f"{job.id}:extension",
                target_job_id=_uuid.UUID(str(job.id)),
                func_kwargs={"job_id": str(job.id), "depth": ext_search.auto_scoring_depth},
            )
        except JobAlreadyRunningError:
            pass
        except Exception as e:
            logger.warning(f"save-from-extension: auto-score launch failed for {job.id}: {e}")

    out = {
        "id": str(job.id),
        "company": job.company,
        "title": job.title,
        "new": True,
        # OPEN-12: the row is always written (the dedup keys have to stick), but
        # `saved` says whether it actually reached the feed.
        "saved": job.status == "new",
        "status": job.status,
        "h1b_jd_flag": bool(job.h1b_jd_flag),
    }
    if job.status == "ignored":
        out["reason"] = reject_message or "filtered out by your Extension search rules"
    return out


@router.post("/bulk-update")
def bulk_update_jobs(body: dict, db: Session = Depends(get_db)):
    """Bulk update multiple jobs at once. Allowed fields: status, seen, saved.

    Returns {"updated": count, "not_found": [<ids>]} so the frontend can
    reconcile IDs that failed to resolve (e.g. stale client-side selections).
    """
    job_ids = body.get("job_ids", [])
    updates = body.get("updates", {})
    allowed = {"status", "seen", "saved"}
    count = 0
    not_found: list[str] = []
    for job_id in job_ids:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            for k, v in updates.items():
                if k in allowed:
                    setattr(job, k, v)
            count += 1
        else:
            not_found.append(str(job_id))
    db.commit()
    return {"updated": count, "not_found": not_found}


@router.get("/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db)):
    from backend.models.db import Resume
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    tailored = db.query(Resume.id).filter(
        Resume.job_id == job.id, Resume.is_base == False
    ).order_by(Resume.updated_at.desc()).first()
    import backend.job_monitor as _mon
    in_flight = [r.job_type for r in _mon._running.values() if r.target_job_id == job.id]
    return _job_to_dict(job, tailored_resume_id=tailored[0] if tailored else None, in_flight=in_flight)


@router.patch("/{job_id}")
async def update_job(job_id: str, updates: dict, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    # NOTE: must be async — launch_background() below uses asyncio.create_task(), which
    # needs a running event loop. A sync endpoint runs in a threadpool with no loop, so
    # the task would silently fail to start (JobRun row created but never registered in
    # _running → invisible to /monitor/in-flight → no scoring toast).
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    allowed = {"seen", "saved", "status"}
    for key, value in updates.items():
        if key in allowed:
            setattr(job, key, value)
    db.commit()

    # Trigger CV scoring when job is saved (respects on_save_action setting). Launched
    # as a TRACKED op so it shows in /monitor/in-flight + /monitor/finished — that's
    # what drives the dashboard's scoring badge and start/OK-NOK toasts.
    if updates.get("saved") is True and not job.cv_scores:
        from backend.models.db import Setting
        on_save_row = db.query(Setting).filter(Setting.key == "on_save_action").first()
        on_save = on_save_row.value if on_save_row and on_save_row.value else "off"
        if on_save != "off":
            try:
                from backend.analyzer.cv_scorer import score_single_job
                launch_background(
                    "analyze_job",
                    score_single_job,
                    trigger="manual",
                    scope_key=f"{job.id}:on-save",
                    target_job_id=job.id,
                    func_kwargs={"job_id": str(job.id), "depth": on_save},
                )
            except JobAlreadyRunningError:
                pass  # already scoring this job — the save itself still succeeds
            except Exception as e:
                logger.warning(f"on-save auto-score launch failed for {job.id}: {e}")

    # R2-H-05: "Applied" is a compound action — it can create an Application and a
    # Company alongside the status change. Report what it created so the Feed's
    # Undo can reverse all of it instead of leaving orphans behind.
    created_application_id = None
    created_company_id = None

    # Auto-cache page and create Application when status changes to applied
    if updates.get("status") == "applied":
        if job.url and not job.has_cached_page:
            from backend.api.routes_applications import _cache_job_page
            background_tasks.add_task(_cache_job_page, str(job.id), job.url)

        # Auto-create Application record if none exists
        from backend.models.db import Application
        from datetime import datetime, timezone
        existing_app = db.query(Application).filter(Application.job_id == job.id).first()
        if not existing_app:
            app = Application(job_id=job.id, status="applied",
                              status_transitions=[{"from": None, "to": "applied", "at": datetime.now(timezone.utc).isoformat(), "source": "ui"}])
            db.add(app)
            db.commit()
            created_application_id = str(app.id)

        # Auto-create company if it doesn't exist
        if job.company and job.company.strip():
            from backend.models.db import Company, Setting
            from backend.models.db import find_company_by_name
            existing_co = find_company_by_name(db, job.company.strip())
            if not existing_co:
                default_resume_row = db.query(Setting).filter(Setting.key == "default_resume_id").first()
                default_resume_ids = [default_resume_row.value] if default_resume_row and default_resume_row.value else []
                new_co = Company(
                    name=job.company.strip(), tier=None, active=False, playwright_enabled=False,
                    selected_resume_ids=default_resume_ids,
                )
                db.add(new_co)
                db.commit()
                created_company_id = str(new_co.id)
                from backend.analyzer.h1b_checker import fetch_h1b_for_company_id
                background_tasks.add_task(fetch_h1b_for_company_id, str(new_co.id))

    result = _job_to_dict(job)
    result["created_application_id"] = created_application_id
    result["created_company_id"] = created_company_id
    return result


@router.post("/cache-applied")
def cache_applied_jobs(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Cache pages for all applied jobs that don't have a cached page yet."""
    jobs = db.query(Job).filter(
        Job.status == "applied",
        Job.url.isnot(None),
        Job.cached_page_html.is_(None),
    ).all()

    for job in jobs:
        from backend.api.routes_applications import _cache_job_page
        background_tasks.add_task(_cache_job_page, str(job.id), job.url)

    return {"queued": len(jobs)}


def _reader_html(body_html: str, meta: str) -> str:
    """Wrap cleaned posting HTML in the shared reader shell (used by the cached-page
    and live-page endpoints)."""
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         max-width: 800px; margin: 0 auto; padding: 24px 32px; line-height: 1.7; color: #1a1a1a;
         font-size: 15px; }}
  h1 {{ font-size: 1.5em; margin-top: 1.5em; margin-bottom: 0.5em; color: #111; }}
  h2 {{ font-size: 1.3em; margin-top: 1.4em; margin-bottom: 0.4em; color: #222; }}
  h3, h4, h5, h6 {{ font-size: 1.1em; margin-top: 1.2em; margin-bottom: 0.3em; color: #333; }}
  p {{ margin: 0.6em 0; }}
  ul, ol {{ padding-left: 1.5em; margin: 0.5em 0; }}
  li {{ margin-bottom: 0.4em; }}
  a {{ color: #2563eb; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1em 0; }}
  td, th {{ border: 1px solid #e5e7eb; padding: 8px 12px; text-align: left; }}
  th {{ background: #f9fafb; font-weight: 600; }}
  blockquote {{ border-left: 3px solid #d1d5db; padding-left: 1em; color: #4b5563; margin: 1em 0; }}
  pre, code {{ background: #f3f4f6; padding: 2px 6px; border-radius: 3px; font-size: 0.9em; }}
  hr {{ border: none; border-top: 1px solid #e5e7eb; margin: 1.5em 0; }}
  .cache-meta {{ color: #9ca3af; font-size: 12px; border-bottom: 1px solid #f3f4f6; padding-bottom: 12px; margin-bottom: 16px; }}
</style></head><body>
<div class="cache-meta">{meta}</div>
{body_html}
</body></html>"""


_READER_CSP = {"Content-Security-Policy": "sandbox; default-src 'unsafe-inline'; style-src 'unsafe-inline'"}


@router.get("/{job_id}/cached-page")
def get_cached_page(job_id: str, db: Session = Depends(get_db)):
    """Return the cached page as clean, readable HTML."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.cached_page_html:
        raise HTTPException(status_code=404, detail="No cached page available")
    cached_at = job.page_cached_at.strftime("%b %d, %Y") if job.page_cached_at else "Unknown"
    return HTMLResponse(content=_reader_html(job.cached_page_html, f"Cached on {cached_at}"), headers=_READER_CSP)


@router.get("/{job_id}/frame-check")
async def frame_check(job_id: str, db: Session = Depends(get_db)):
    """Report whether the posting can be embedded in an iframe without the extension.
    Blocks only when we CONFIDENTLY see a framing block (X-Frame-Options, or a CSP
    frame-ancestors directive) on a successful fetch; any fetch error → embeddable
    True so the feed still tries the live preview."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.url:
        return {"embeddable": False}
    from backend.scraper._shared.url_safety import safe_get, UnsafeURLError
    try:
        resp = await safe_get(job.url, timeout=12, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        })
        xfo = (resp.headers.get("x-frame-options") or "").strip()
        csp = (resp.headers.get("content-security-policy") or "").lower()
        blocked = bool(xfo) or ("frame-ancestors" in csp)
        return {"embeddable": not blocked}
    except UnsafeURLError:
        return {"embeddable": False}
    except Exception:
        return {"embeddable": True}   # unknown — let the browser try the live frame


def _inject_base(raw_html: str, url: str) -> str:
    """Return the page's own HTML with a <base href> so its relative CSS/images/links
    resolve against the source, and its embedded CSP <meta> stripped (would otherwise
    block the inlined render). Scripts are neutered by the iframe sandbox, not here."""
    import re
    import html as _html
    raw_html = re.sub(
        r'<meta[^>]+http-equiv=["\']?content-security-policy["\']?[^>]*>',
        '', raw_html, flags=re.IGNORECASE)
    base_tag = f'<base href="{_html.escape(url, quote=True)}">'
    m = re.search(r'<head[^>]*>', raw_html, flags=re.IGNORECASE)
    if m:
        return raw_html[:m.end()] + base_tag + raw_html[m.end():]
    return base_tag + raw_html


@router.get("/{job_id}/live-page")
async def get_live_page(job_id: str, db: Session = Depends(get_db)):
    """Fetch the posting from the backend (SSRF-guarded) and return its OWN HTML so the
    feed can show the real page — not a reader extraction — even when the browser
    extension isn't stripping X-Frame-Options. Warms the cached_page_* columns as a
    side effect (cleaned text, for scoring)."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.url:
        raise HTTPException(status_code=404, detail="No posting URL captured for this job")

    from backend.scraper._shared.url_safety import safe_get, UnsafeURLError
    from backend.api.routes_applications import _extract_clean_content
    try:
        resp = await safe_get(job.url, timeout=20, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })
        resp.raise_for_status()
        raw = resp.text[:2_000_000]
    except UnsafeURLError:
        raise HTTPException(status_code=400, detail="URL not allowed")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not fetch posting: {e}")
    if not (raw or "").strip():
        raise HTTPException(status_code=502, detail="Posting returned no content")
    # Probe: is there real server-rendered content, or just a client-side app shell?
    # JS-rendered postings (Workday, Jobright, …) come back as a near-empty shell that
    # would only show a spinner without scripts — treat those as a failure so the feed
    # falls back to the extension message instead of a blank/spinning frame.
    clean_html, text = _extract_clean_content(raw)
    if len((text or "").strip()) < 200:
        raise HTTPException(status_code=502, detail="Posting is rendered client-side — needs the extension")
    # warm the cache with cleaned text for scoring; never overwrite an existing snapshot
    if not job.cached_page_html and clean_html:
        try:
            job.cached_page_html = clean_html
            job.cached_page_text = text
            db.commit()
        except Exception:
            db.rollback()
    return HTMLResponse(content=_inject_base(raw, str(resp.url)), headers=_READER_CSP)


def _normalize_report(report, best_cv):
    """Ensure scoring_report is always in nested {cv_name: report} format."""
    if not report:
        return None
    # Already nested format: check if any value is a dict with 'summary'
    if isinstance(report, dict) and "summary" not in report:
        return report
    # Flat format: wrap in {cv_name: report}
    if isinstance(report, dict) and "summary" in report:
        report = dict(report)
        cv_name = report.pop("scored_with", best_cv or "Unknown")
        return {cv_name: report}
    return report


def _job_to_dict(j: Job, tailored_resume_id=None, in_flight: list[str] | None = None) -> dict:
    scores = j.cv_scores or {}
    numeric_scores = [v for v in scores.values() if isinstance(v, (int, float))]
    best_score = max(numeric_scores) if numeric_scores else 0
    return {
        "id": str(j.id),
        "external_id": j.external_id,
        "company": j.company,
        "title": j.title,
        "url": j.url,
        "source": j.source,
        "search_id": str(j.search_id) if j.search_id else None,
        "description": j.description,
        "location": j.location,
        "remote": j.remote,
        "salary_min": j.salary_min,
        "salary_max": j.salary_max,
        "salary_source": j.salary_source,
        "h1b_company_lca_count": j.h1b_company_lca_count,
        "h1b_company_approval_rate": j.h1b_company_approval_rate,
        "h1b_jd_flag": j.h1b_jd_flag,
        "h1b_jd_snippet": j.h1b_jd_snippet,
        "h1b_verdict": j.h1b_verdict,
        "cv_scores": scores,
        "best_cv": j.best_cv,
        "scoring_report": _normalize_report(j.scoring_report, j.best_cv),
        "best_score": best_score,
        "has_cached_page": bool(j.has_cached_page),
        "page_cached_at": j.page_cached_at.isoformat() if j.page_cached_at else None,
        "seen": j.seen,
        "saved": j.saved,
        "status": j.status,
        "discovered_at": j.discovered_at.isoformat() if j.discovered_at else None,
        "has_tailored_resume": tailored_resume_id is not None,
        "tailored_resume_id": str(tailored_resume_id) if tailored_resume_id else None,
        "in_flight": in_flight or [],
    }
