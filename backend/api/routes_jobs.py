"""Job listing and management endpoints."""
import asyncio
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, text, func
from backend.models.db import (
    get_db, Job, SessionLocal, find_company_by_name,
    build_company_lookup, get_existing_external_ids,
)
from backend.scraper.deduplicator import make_external_id, make_content_hash
from backend.analyzer.salary_extractor import apply_salary_to_job
from backend.analyzer.h1b_checker import check_job_h1b, determine_h1b_verdict

logger = logging.getLogger("jobnavigator.jobs")

router = APIRouter(prefix="/jobs", tags=["jobs"])

# In-memory LinkedIn import progress tracker
_linkedin_import_progress: dict = {}


async def _scrape_linkedin_ids(linkedin_ids: list[str]):
    """Background: fetch LinkedIn job data via Voyager API, extract apply URLs, create jobs."""
    import re
    from linkedin_api import Linkedin as LinkedinAPI
    from backend.models.db import Setting, Search

    logger.info(f"LinkedIn import: fetching {len(linkedin_ids)} jobs via Voyager API")

    db = SessionLocal()
    try:
        # Pre-check: skip LinkedIn IDs already in the DB (avoid unnecessary Voyager API calls)
        existing_li_ids = {
            r[0] for r in db.query(Job.linkedin_job_id).filter(Job.linkedin_job_id != None).all()
        }
        pre_dedup = [lid for lid in linkedin_ids if lid not in existing_li_ids]
        pre_skipped = len(linkedin_ids) - len(pre_dedup)
        if pre_skipped:
            logger.info(f"LinkedIn import: {pre_skipped}/{len(linkedin_ids)} already in DB, skipping Voyager calls")

        # Init progress tracker
        _linkedin_import_progress.update({
            "total": len(linkedin_ids),
            "pre_skipped": pre_skipped,
            "processed": 0,
            "imported": 0,
            "skipped": pre_skipped,
            "status": "running",
        })

        if not pre_dedup:
            _linkedin_import_progress["status"] = "done"
            logger.info("LinkedIn import: all IDs already exist, nothing to fetch")
            return

        # Get mock account credentials from settings
        li_email = db.query(Setting).filter(Setting.key == "linkedin_mock_email").first()
        li_pass = db.query(Setting).filter(Setting.key == "linkedin_mock_password").first()
        if not li_email or not li_email.value or not li_pass or not li_pass.value:
            logger.error("LinkedIn import: linkedin_mock_email / linkedin_mock_password not set")
            _linkedin_import_progress["status"] = "error"
            return

        # Load the LinkedIn Extension search for filters + linking
        ext_search = db.query(Search).filter(Search.search_mode == "linkedin_extension").first()

        # Login via Voyager API (sync — offload to thread)
        try:
            api = await asyncio.to_thread(LinkedinAPI, li_email.value, li_pass.value)
        except Exception as e:
            logger.error(f"LinkedIn import: login failed: {e}")
            _linkedin_import_progress["status"] = "error"
            return

        existing_ext_ids = get_existing_external_ids(db)
        company_lookup = build_company_lookup(db)
        imported = 0
        skipped = pre_skipped

        for lid in pre_dedup:
            linkedin_url = f"https://www.linkedin.com/jobs/view/{lid}"
            try:
                # Voyager API call (sync — offload to thread)
                job_data = await asyncio.to_thread(api.get_job, lid)
                if not job_data or not job_data.get("title"):
                    logger.warning(f"LinkedIn {lid}: no data returned, skipping")
                    skipped += 1
                    continue

                title = (job_data.get("title") or "").strip()

                # Company — nested in companyDetails
                company = ""
                for v in (job_data.get("companyDetails") or {}).values():
                    if isinstance(v, dict) and "companyResolutionResult" in v:
                        company = (v["companyResolutionResult"].get("name") or "").strip()
                        break

                if not title or not company:
                    logger.warning(f"LinkedIn {lid}: missing title/company, skipping")
                    skipped += 1
                    continue

                # Apply search filters (title include/exclude, company exclude)
                if ext_search:
                    title_lower = title.lower()
                    # Title include filter
                    include_kw = ext_search.title_include_keywords or []
                    if include_kw and not any(kw.lower() in title_lower for kw in include_kw):
                        logger.info(f"LinkedIn {lid}: title '{title}' doesn't match include filter, skipping")
                        skipped += 1
                        continue
                    # Title exclude filter (merge global)
                    from backend.models.db import get_global_title_exclude
                    _global_te = get_global_title_exclude(db)
                    exclude_kw = list(set((ext_search.title_exclude_keywords or []) + _global_te))
                    if exclude_kw:
                        pattern = "|".join(r'\b' + re.escape(kw) + r'\b' for kw in exclude_kw)
                        if re.search(pattern, title, re.IGNORECASE):
                            logger.info(f"LinkedIn {lid}: title '{title}' matches exclude filter, skipping")
                            skipped += 1
                            continue
                    # Company exclude filter
                    company_excl = ext_search.company_exclude or []
                    if company_excl and company.lower().strip() in {c.lower().strip() for c in company_excl}:
                        logger.info(f"LinkedIn {lid}: company '{company}' excluded, skipping")
                        skipped += 1
                        continue

                # Location
                location = (job_data.get("formattedLocation") or "").strip()

                # Description
                description = (job_data.get("description", {}).get("text") or "").strip()

                # Apply URL from applyMethod
                apply_url = ""
                for v in (job_data.get("applyMethod") or {}).values():
                    if isinstance(v, dict):
                        apply_url = (v.get("companyApplyUrl") or "").strip()
                        break

                # Use apply_url for dedup + display, fall back to linkedin URL
                job_url = apply_url if apply_url else linkedin_url

                ext_id = make_external_id(company, title, job_url)
                c_hash = make_content_hash(company, title)
                alt_ext_id = make_external_id(company, title, linkedin_url) if apply_url else None

                if ext_id in existing_ext_ids:
                    skipped += 1
                    continue
                if alt_ext_id and alt_ext_id in existing_ext_ids:
                    skipped += 1
                    continue

                job = Job(
                    external_id=ext_id,
                    content_hash=c_hash,
                    company=company,
                    title=title,
                    url=job_url,
                    source="linkedin_extension",
                    linkedin_job_id=lid,
                    search_id=ext_search.id if ext_search else None,
                    location=location,
                    description=description,
                    status="new",
                )

                # Salary extraction from description
                comp_obj = find_company_by_name(db, company) or company_lookup.get(company.lower().strip())
                h1b_median = comp_obj.h1b_median_salary if comp_obj else None
                apply_salary_to_job(job, h1b_median)

                # H-1B + language check
                try:
                    await check_job_h1b(job, db)
                    job.h1b_verdict = determine_h1b_verdict(
                        job.h1b_company_lca_count, job.h1b_jd_flag
                    )
                except Exception as e:
                    logger.warning(f"LinkedIn {lid}: analysis error: {e}")

                # Skip flagged jobs (same as other scrapers)
                if job.h1b_jd_flag:
                    logger.info(f"LinkedIn {lid}: skipping (H-1B exclusion) — {job.h1b_jd_snippet}")
                    skipped += 1
                    continue

                db.add(job)
                db.commit()
                imported += 1
                existing_ext_ids.add(ext_id)
                logger.info(f"LinkedIn {lid}: imported '{title}' at '{company}' -> {job_url[:80]}")

            except Exception as e:
                logger.warning(f"LinkedIn {lid}: failed: {e}")
                db.rollback()
                skipped += 1

            # Update progress tracker
            _linkedin_import_progress.update({
                "processed": _linkedin_import_progress["processed"] + 1,
                "imported": imported,
                "skipped": skipped,
            })

            await asyncio.sleep(1)  # Rate limit

        _linkedin_import_progress["status"] = "done"
        logger.info(f"LinkedIn import: done — imported {imported}, skipped {skipped}/{len(linkedin_ids)}")

        # Trigger auto CV scoring if enabled on the extension search
        if imported > 0 and ext_search and ext_search.auto_scoring_depth in ("light", "full"):
            try:
                from backend.analyzer.cv_scorer import analyze_unscored_jobs
                await analyze_unscored_jobs(status="new")
                logger.info("LinkedIn import: auto-scoring triggered")
            except Exception as e:
                logger.warning(f"LinkedIn import: auto-scoring failed: {e}")
    finally:
        db.close()


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
    asyncio.create_task(_scrape_linkedin_ids(linkedin_ids))

    return {
        "accepted": len(linkedin_ids),
        "new": new_count,
        "already_imported": len(linkedin_ids) - new_count,
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
        vals = [c.strip() for c in company.split(",") if c.strip()]
        if len(vals) > 1:
            q = q.filter(func.lower(Job.company).in_([v.lower() for v in vals]))
        else:
            q = q.filter(Job.company.ilike(f"%{vals[0]}%"))
    if min_score is not None:
        q = q.filter(text(
            "(SELECT COALESCE(MAX(v::numeric), 0) FROM jsonb_each_text(CASE WHEN jsonb_typeof(COALESCE(cv_scores, '{}'::jsonb)) = 'object' THEN cv_scores ELSE '{}'::jsonb END) AS t(k, v)"
            " WHERE v ~ '^[0-9]+(\\.[0-9]+)?$') >= :min_score"
        ).bindparams(min_score=min_score))
    if max_score is not None:
        q = q.filter(text(
            "(SELECT COALESCE(MAX(v::numeric), 0) FROM jsonb_each_text(CASE WHEN jsonb_typeof(COALESCE(cv_scores, '{}'::jsonb)) = 'object' THEN cv_scores ELSE '{}'::jsonb END) AS t(k, v)"
            " WHERE v ~ '^[0-9]+(\\.[0-9]+)?$') <= :max_score"
        ).bindparams(max_score=max_score))
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
        q = q.order_by(text(
            "(SELECT COALESCE(MAX(v::numeric), 0) FROM jsonb_each_text("
            "CASE WHEN jsonb_typeof(COALESCE(cv_scores, '{}'::jsonb)) = 'object' "
            "THEN cv_scores ELSE '{}'::jsonb END) AS t(k, v) "
            "WHERE v ~ '^[0-9]+(\\.[0-9]+)?$') DESC"
        ))
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

    return {
        "total": total,
        "jobs": [_job_to_dict(j, tailored_resume_id=tailored_map.get(j.id)) for j in jobs],
    }


def _apply_common_filters(q, status=None, company=None, source=None, h1b_verdict=None,
                          min_score=None, saved=None, title_search=None, remote=None,
                          min_salary=None, max_salary=None, search_id=None):
    """Apply shared filter logic for job list and filter-list endpoints."""
    if status:
        vals = [s.strip() for s in status.split(",") if s.strip()]
        q = q.filter(Job.status.in_(vals)) if len(vals) > 1 else q.filter(Job.status == vals[0])
    if company:
        vals = [c.strip() for c in company.split(",") if c.strip()]
        if len(vals) > 1:
            q = q.filter(func.lower(Job.company).in_([v.lower() for v in vals]))
        else:
            q = q.filter(Job.company.ilike(f"%{vals[0]}%"))
    if source:
        vals = [s.strip() for s in source.split(",") if s.strip()]
        q = q.filter(Job.source.in_(vals)) if len(vals) > 1 else q.filter(Job.source == vals[0])
    if h1b_verdict:
        vals = [v.strip() for v in h1b_verdict.split(",") if v.strip()]
        q = q.filter(Job.h1b_verdict.in_(vals)) if len(vals) > 1 else q.filter(Job.h1b_verdict == vals[0])
    if min_score is not None:
        q = q.filter(text(
            "(SELECT COALESCE(MAX(v::numeric), 0) FROM jsonb_each_text(CASE WHEN jsonb_typeof(COALESCE(cv_scores, '{}'::jsonb)) = 'object' THEN cv_scores ELSE '{}'::jsonb END) AS t(k, v)"
            " WHERE v ~ '^[0-9]+(\\.[0-9]+)?$') >= :min_score"
        ).bindparams(min_score=min_score))
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
    db: Session = Depends(get_db),
):
    """Return distinct company names from jobs matching current filters, sorted."""
    q = db.query(Job.company).distinct().filter(Job.company.isnot(None), Job.company != "")
    q = _apply_common_filters(q, status=status, source=source, h1b_verdict=h1b_verdict,
                              min_score=min_score, saved=saved, title_search=title_search,
                              remote=remote, min_salary=min_salary, max_salary=max_salary,
                              search_id=search_id)
    rows = q.order_by(Job.company).all()
    return [r[0] for r in rows]


@router.get("/sources/list")
def list_job_sources(
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
    q = db.query(Job.source).distinct().filter(Job.source.isnot(None), Job.source != "")
    q = _apply_common_filters(q, status=status, company=company, h1b_verdict=h1b_verdict,
                              min_score=min_score, saved=saved, title_search=title_search,
                              remote=remote, min_salary=min_salary, max_salary=max_salary,
                              search_id=search_id)
    rows = q.order_by(Job.source).all()
    return [r[0] for r in rows]


@router.get("/verdicts/list")
def list_job_verdicts(
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
    q = db.query(Job.h1b_verdict).distinct().filter(Job.h1b_verdict.isnot(None), Job.h1b_verdict != "")
    q = _apply_common_filters(q, status=status, company=company, source=source,
                              min_score=min_score, saved=saved, title_search=title_search,
                              remote=remote, min_salary=min_salary, max_salary=max_salary,
                              search_id=search_id)
    rows = q.order_by(Job.h1b_verdict).all()
    return [r[0] for r in rows]


@router.post("/save-from-extension")
def save_from_extension(body: dict, db: Session = Depends(get_db)):
    """Save a job from the Chrome Extension to the Job Feed (no application created)."""
    title = (body.get("title") or "").strip()
    company = (body.get("company") or "").strip()
    url = (body.get("url") or "").strip()
    description = (body.get("description") or "").strip() or None
    if not title or not company or not url:
        raise HTTPException(status_code=400, detail="title, company, and url are required")

    from backend.scraper.deduplicator import make_external_id, make_content_hash
    external_id = make_external_id(company, title, url)

    existing = db.query(Job).filter(Job.external_id == external_id).first()
    if existing:
        if existing.status == "skip":
            existing.status = "new"
        # Backfill description if missing
        if description and not existing.description:
            existing.description = description
            apply_salary_to_job(existing)
        db.commit()
        return {"id": str(existing.id), "company": existing.company, "title": existing.title, "new": False}

    job = Job(
        external_id=external_id,
        content_hash=make_content_hash(company, title),
        company=company,
        title=title,
        url=url,
        description=description,
        source="extension",
        status="new",
    )
    # Parse salary from description
    if description:
        apply_salary_to_job(job)
    db.add(job)
    db.commit()
    return {"id": str(job.id), "company": job.company, "title": job.title, "new": True}


@router.post("/bulk-update")
def bulk_update_jobs(body: dict, db: Session = Depends(get_db)):
    """Bulk update multiple jobs at once. Allowed fields: status, seen, saved."""
    job_ids = body.get("job_ids", [])
    updates = body.get("updates", {})
    allowed = {"status", "seen", "saved"}
    count = 0
    for job_id in job_ids:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            for k, v in updates.items():
                if k in allowed:
                    setattr(job, k, v)
            count += 1
    db.commit()
    return {"updated": count}


@router.get("/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db)):
    from backend.models.db import Resume
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    tailored = db.query(Resume.id).filter(
        Resume.job_id == job.id, Resume.is_base == False
    ).order_by(Resume.updated_at.desc()).first()
    return _job_to_dict(job, tailored_resume_id=tailored[0] if tailored else None)


@router.patch("/{job_id}")
def update_job(job_id: str, updates: dict, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    allowed = {"seen", "saved", "status"}
    for key, value in updates.items():
        if key in allowed:
            setattr(job, key, value)
    db.commit()

    # Trigger CV scoring when job is saved (respects on_save_action setting)
    if updates.get("saved") is True and not job.cv_scores:
        from backend.models.db import Setting
        on_save_row = db.query(Setting).filter(Setting.key == "on_save_action").first()
        on_save = on_save_row.value if on_save_row and on_save_row.value else "off"
        if on_save != "off":
            from backend.analyzer.cv_scorer import score_single_job
            background_tasks.add_task(score_single_job, str(job.id), None, on_save)

    # Auto-cache page and create Application when status changes to applied
    if updates.get("status") == "applied":
        if job.url and not job.cached_page_html:
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

        # Auto-create company if it doesn't exist
        if job.company and job.company.strip():
            from backend.models.db import Company, Setting
            from backend.models.db import find_company_by_name
            existing_co = find_company_by_name(db, job.company.strip())
            if not existing_co:
                default_cv_row = db.query(Setting).filter(Setting.key == "default_cv_id").first()
                default_cv_ids = [default_cv_row.value] if default_cv_row and default_cv_row.value else []
                new_co = Company(
                    name=job.company.strip(), tier=None, active=False, playwright_enabled=False,
                    selected_cv_ids=default_cv_ids,
                )
                db.add(new_co)
                db.commit()
                from backend.analyzer.h1b_checker import fetch_h1b_for_company_id
                background_tasks.add_task(fetch_h1b_for_company_id, str(new_co.id))

    return _job_to_dict(job)


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


@router.get("/{job_id}/cached-page")
def get_cached_page(job_id: str, db: Session = Depends(get_db)):
    """Return the cached page as clean, readable HTML."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.cached_page_html:
        raise HTTPException(status_code=404, detail="No cached page available")

    cached_at = job.page_cached_at.strftime("%b %d, %Y") if job.page_cached_at else "Unknown"
    reader_html = f"""<!DOCTYPE html>
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
<div class="cache-meta">Cached on {cached_at}</div>
{job.cached_page_html}
</body></html>"""
    return HTMLResponse(
        content=reader_html,
        headers={"Content-Security-Policy": "sandbox; default-src 'unsafe-inline'; style-src 'unsafe-inline'"},
    )


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


def _job_to_dict(j: Job, tailored_resume_id=None) -> dict:
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
        "has_cached_page": bool(j.cached_page_html),
        "page_cached_at": j.page_cached_at.isoformat() if j.page_cached_at else None,
        "seen": j.seen,
        "saved": j.saved,
        "status": j.status,
        "discovered_at": j.discovered_at.isoformat() if j.discovered_at else None,
        "has_tailored_resume": tailored_resume_id is not None,
        "tailored_resume_id": str(tailored_resume_id) if tailored_resume_id else None,
    }
