"""Company management endpoints."""
import base64
import logging
import re
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.models.db import get_db, Company, Job, Application, Setting

logger = logging.getLogger("jobnavigator.companies")

router = APIRouter(prefix="/companies", tags=["companies"])


async def _fire_h1b_async(company_id: str):
    """Run H-1B lookup (used as BackgroundTasks target)."""
    from backend.analyzer.h1b_checker import fetch_h1b_for_company_id
    await fetch_h1b_for_company_id(company_id)


def detect_scrape_type(url: str) -> str:
    """Detect the ATS/scraper type from a URL via string matching. No network calls."""
    from backend.scraper.playwright_scraper import (
        _is_workday, _is_oracle_hcm, _is_lever, _is_phenom_post,
        _is_talentbrew_ajax, _is_ashby, _is_greenhouse, _is_rippling,
        _is_meta_careers, _is_google_careers,
    )
    if _is_workday(url):
        return "Workday API"
    if _is_oracle_hcm(url):
        return "Oracle HCM API"
    if _is_lever(url):
        return "Lever API"
    if _is_phenom_post(url):
        return "Phenom API"
    if _is_talentbrew_ajax(url):
        return "TalentBrew AJAX"
    if _is_ashby(url):
        return "Ashby API"
    if _is_greenhouse(url):
        return "Greenhouse API"
    if _is_rippling(url):
        return "Rippling API"
    if _is_meta_careers(url):
        return "Meta Careers (Playwright)"
    if _is_google_careers(url):
        return "Google Careers (Playwright)"
    return "Generic (Playwright)"


class CompanyCreate(BaseModel):
    name: str
    tier: Optional[int] = 2
    scrape_urls: List[str] = []
    selected_cv_ids: List[str] = []
    scrape_interval_minutes: Optional[int] = None
    title_include_expr: Optional[str] = None
    title_exclude_keywords: list = []
    wait_for_selector: Optional[str] = None
    max_pages: int = 5
    h1b_slug: Optional[str] = None
    notes: Optional[str] = None
    auto_scoring_depth: str = "off"


class BulkActivate(BaseModel):
    active: bool
    tiers: Optional[List[str]] = None


@router.get("")
def list_companies(
    active: Optional[bool] = None,
    tier: Optional[int] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Company)
    if active is not None:
        q = q.filter(Company.active == active)
    if tier is not None:
        q = q.filter(Company.tier == tier)
    companies = q.order_by(Company.tier.asc().nullslast(), Company.name).all()

    # Count applications: Application records + jobs with status='applied' (no double-counting)
    # Uses UNION of job IDs from both sources, then groups by company name
    from sqlalchemy import union, select
    app_job_ids = select(Application.job_id.label("jid")).distinct()
    applied_job_ids = select(Job.id.label("jid")).where(Job.status == "applied")
    all_applied = union(app_job_ids, applied_job_ids).subquery()
    raw_counts = (
        db.query(Job.company, func.count(all_applied.c.jid))
        .join(all_applied, Job.id == all_applied.c.jid)
        .group_by(Job.company)
        .all()
    )
    app_counts = {}
    for name, count in raw_counts:
        key = (name or "").lower().replace(" ", "")
        app_counts[key] = app_counts.get(key, 0) + count

    return [
        _company_to_dict(c, application_count=app_counts.get(c.name.lower().replace(" ", ""), 0))
        for c in companies
    ]


@router.post("")
def create_company(data: CompanyCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    existing = db.query(Company).filter(func.lower(Company.name) == data.name.lower()).first()
    if existing:
        raise HTTPException(status_code=409, detail="Company already exists")
    company = Company(
        name=data.name,
        tier=data.tier,
        scrape_urls=[u for u in data.scrape_urls if u.strip()],
        selected_cv_ids=data.selected_cv_ids,
        scrape_interval_minutes=data.scrape_interval_minutes,
        title_include_expr=data.title_include_expr,
        title_exclude_keywords=data.title_exclude_keywords,
        wait_for_selector=data.wait_for_selector,
        max_pages=data.max_pages,
        notes=data.notes,
        active=True,
        playwright_enabled=True,
    )
    db.add(company)
    db.commit()

    # Fire H-1B lookup in background
    company_id = str(company.id)
    background_tasks.add_task(_fire_h1b_async, company_id)

    return _company_to_dict(company)


@router.patch("/{company_id}")
def update_company(company_id: str, updates: dict, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    old_slug = company.h1b_slug
    old_name = company.name

    allowed = {
        "name", "active", "scrape_urls", "tier", "selected_cv_ids",
        "playwright_enabled", "jobspy_search_term", "scrape_interval_minutes",
        "title_include_expr", "title_exclude_keywords",
        "wait_for_selector", "max_pages", "h1b_slug", "notes", "aliases", "auto_scoring_depth",
    }
    for key, value in updates.items():
        if key in allowed:
            setattr(company, key, value)
    db.commit()

    # Re-fetch H-1B if slug or name changed
    if updates.get("h1b_slug") != old_slug or updates.get("name") != old_name:
        if "h1b_slug" in updates or "name" in updates:
            background_tasks.add_task(_fire_h1b_async, company_id)

    return _company_to_dict(company)


@router.post("/auto-create-from-jobs")
def auto_create_from_jobs(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Scan all Job.company distinct values and create inactive Company records for unmatched names."""
    default_cv_row = db.query(Setting).filter(Setting.key == "default_cv_id").first()
    default_cv_ids = [default_cv_row.value] if default_cv_row and default_cv_row.value else []

    from backend.models.db import get_company_all_names
    existing = set(get_company_all_names(db).keys())
    distinct_companies = db.query(Job.company).distinct().all()
    new_ids = []
    created = 0
    for (name,) in distinct_companies:
        if not name or name.strip().lower() in existing:
            continue
        name = name.strip()
        company = Company(
            name=name, tier=None, active=False, playwright_enabled=False,
            selected_cv_ids=default_cv_ids,
        )
        db.add(company)
        db.flush()
        new_ids.append(str(company.id))
        existing.add(name.lower())
        created += 1
    db.commit()

    # Fire H-1B lookups for all newly created companies
    for cid in new_ids:
        background_tasks.add_task(_fire_h1b_async, cid)

    return {"created": created}


@router.post("/bulk-activate")
def bulk_activate(data: BulkActivate, db: Session = Depends(get_db)):
    """Set companies active or inactive, optionally filtered by tiers."""
    q = db.query(Company)
    if data.tiers:
        tier_ints = [int(t) for t in data.tiers if t != 'none']
        has_none = 'none' in data.tiers
        if tier_ints and has_none:
            q = q.filter((Company.tier.in_(tier_ints)) | (Company.tier.is_(None)))
        elif tier_ints:
            q = q.filter(Company.tier.in_(tier_ints))
        elif has_none:
            q = q.filter(Company.tier.is_(None))
    count = q.update({Company.active: data.active}, synchronize_session='fetch')
    db.commit()
    return {"updated": count, "active": data.active}


@router.post("/refresh-h1b")
async def refresh_h1b_all(db: Session = Depends(get_db)):
    """Fetch H-1B data for all companies that haven't been checked yet, or re-check all."""
    from backend.analyzer.h1b_checker import fetch_company_h1b_data
    companies = db.query(Company).all()
    updated = 0
    for company in companies:
        try:
            data = await fetch_company_h1b_data(company.name, h1b_slug=company.h1b_slug)
            # Only update if new data has LCAs or existing data is already zero
            if data["lca_count"] > 0 or (company.h1b_lca_count or 0) == 0:
                company.h1b_lca_count = data["lca_count"]
                company.h1b_approval_rate = data["approval_rate"]
                company.h1b_median_salary = data["median_salary"]
                company.h1b_last_checked = datetime.now(timezone.utc)
                updated += 1
        except Exception as e:
            logger.error(f"H-1B refresh failed for {company.name}: {e}")
            continue
    db.commit()
    logger.info(f"H-1B refresh complete: {updated} companies updated")
    return {"updated": updated}


@router.post("/backfill-h1b-jobs")
async def backfill_h1b_jobs(db: Session = Depends(get_db)):
    """Re-run check_job_h1b on all jobs with NULL h1b_verdict."""
    from backend.analyzer.h1b_checker import check_job_h1b
    jobs = db.query(Job).filter(Job.h1b_verdict.is_(None)).all()
    updated = 0
    for job in jobs:
        await check_job_h1b(job, db)
        updated += 1
    db.commit()
    logger.info(f"H-1B backfill complete: {updated} jobs updated")
    return {"updated": updated}


@router.post("/{company_id}/test-scrape")
async def test_scrape_company(company_id: str, db: Session = Depends(get_db)):
    """Run Playwright scrape for a company and return results WITHOUT saving to DB."""
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    from backend.scraper.playwright_scraper import (
        _get_browser, _new_page, _close_page, _extract_all_pages, _wait_for_content,
        _setup_route_blocks, match_title_expr,
        _is_talentbrew_ajax, _scrape_talentbrew_ajax,
        _is_oracle_hcm, _scrape_oracle_hcm,
        _is_phenom_post, _scrape_phenom,
        _is_lever, _scrape_lever,
        _is_workday, _scrape_workday,
        _is_ashby, _scrape_ashby,
        _is_greenhouse, _scrape_greenhouse,
        _is_rippling, _scrape_rippling,
        _is_meta_careers, _scrape_meta_careers,
        _is_google_careers, _scrape_google_careers,
    )

    urls = company.scrape_urls or []
    if not urls:
        raise HTTPException(status_code=400, detail="No scrape URLs configured")

    include_expr = company.title_include_expr
    exclude_kws = [kw.lower() for kw in (company.title_exclude_keywords or [])]

    all_jobs = []
    urls_scraped = []
    pw = None
    browser = None
    try:
        pw, browser = await _get_browser()
        max_pages = company.max_pages or 5

        all_rejected = []
        all_pagination_debug = []
        screenshots = []
        for target_url in urls:
            target_url = target_url.strip()
            if not target_url:
                continue
            page = None
            try:
                # HTTP-based scrapers (no Playwright needed)
                if _is_phenom_post(target_url):
                    jobs, rejected = await _scrape_phenom(target_url, debug=True)
                    all_jobs.extend(jobs)
                    all_rejected.extend(rejected)
                    urls_scraped.append(f"Phenom POST API ({len(jobs)} found)")
                    continue
                if _is_talentbrew_ajax(target_url):
                    jobs, rejected = await _scrape_talentbrew_ajax(target_url, debug=True)
                    all_jobs.extend(jobs)
                    all_rejected.extend(rejected)
                    urls_scraped.append(f"{target_url[:80]}... ({len(jobs)} found via HTTP)")
                    continue
                if _is_oracle_hcm(target_url):
                    jobs, rejected = await _scrape_oracle_hcm(target_url, debug=True)
                    all_jobs.extend(jobs)
                    all_rejected.extend(rejected)
                    urls_scraped.append(f"{target_url[:80]}... ({len(jobs)} found via Oracle HCM API)")
                    continue
                if _is_lever(target_url):
                    jobs, rejected = await _scrape_lever(target_url, debug=True)
                    all_jobs.extend(jobs)
                    all_rejected.extend(rejected)
                    urls_scraped.append(f"{target_url[:80]}... ({len(jobs)} found via Lever API)")
                    continue
                if _is_workday(target_url):
                    jobs, rejected = await _scrape_workday(target_url, debug=True)
                    all_jobs.extend(jobs)
                    all_rejected.extend(rejected)
                    urls_scraped.append(f"{target_url[:80]}... ({len(jobs)} found via Workday API)")
                    continue
                if _is_ashby(target_url):
                    jobs, rejected = await _scrape_ashby(target_url, debug=True)
                    all_jobs.extend(jobs)
                    all_rejected.extend(rejected)
                    urls_scraped.append(f"{target_url[:80]}... ({len(jobs)} found via Ashby API)")
                    continue
                if _is_greenhouse(target_url):
                    jobs, rejected = await _scrape_greenhouse(target_url, debug=True)
                    all_jobs.extend(jobs)
                    all_rejected.extend(rejected)
                    urls_scraped.append(f"{target_url[:80]}... ({len(jobs)} found via Greenhouse API)")
                    continue
                if _is_rippling(target_url):
                    jobs, rejected = await _scrape_rippling(target_url, debug=True)
                    all_jobs.extend(jobs)
                    all_rejected.extend(rejected)
                    urls_scraped.append(f"{target_url[:80]}... ({len(jobs)} found via Rippling API)")
                    continue
                if _is_meta_careers(target_url):
                    jobs, rejected = await _scrape_meta_careers(target_url, browser=browser, debug=True)
                    all_jobs.extend(jobs)
                    all_rejected.extend(rejected)
                    urls_scraped.append(f"{target_url[:80]}... ({len(jobs)} found via Meta Careers)")
                    continue
                if _is_google_careers(target_url):
                    jobs, rejected = await _scrape_google_careers(target_url, browser=browser, debug=True)
                    all_jobs.extend(jobs)
                    all_rejected.extend(rejected)
                    urls_scraped.append(f"{target_url[:80]}... ({len(jobs)} found via Google Careers)")
                    continue

                page = await _new_page(browser)
                await _setup_route_blocks(page)
                await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
                await _wait_for_content(page, company.wait_for_selector)
                # Capture viewport screenshot before extraction
                png_bytes = await page.screenshot(full_page=True)
                screenshots.append({
                    "url": target_url,
                    "data": base64.b64encode(png_bytes).decode(),
                })
                jobs, rejected, pag_debug = await _extract_all_pages(page, target_url, max_pages, debug=True, wait_for_selector=company.wait_for_selector)
                all_jobs.extend(jobs)
                all_rejected.extend(rejected)
                all_pagination_debug.extend(pag_debug)
                urls_scraped.append(f"{target_url} ({len(jobs)} found, {len(rejected)} rejected)")
            except Exception as e:
                urls_scraped.append(f"{target_url[:80]}... (error: {e})")
            finally:
                if page:
                    await _close_page(page)

        # Classify valid jobs with keyword filter reasons
        results = []
        kept_count = 0
        for j in all_jobs:
            title_lower = j["title"].lower()
            reason = None

            matched_exclude = [kw for kw in exclude_kws if re.search(r'\b' + re.escape(kw) + r'\b', title_lower)]
            if matched_exclude:
                reason = f"Excluded by: {', '.join(matched_exclude)}"
            elif include_expr and include_expr.strip():
                    if not match_title_expr(include_expr, j["title"]):
                        reason = f"No match for: {include_expr}"

            kept = reason is None
            if kept:
                kept_count += 1

            results.append({
                "title": j["title"],
                "url": j["url"],
                "kept": kept,
                "reason": reason,
            })

        # Append rejected entries at the end so user can see what was dropped
        for r in all_rejected:
            results.append({
                "title": r["title"],
                "url": r["url"],
                "kept": False,
                "reason": f"[Validation] {r['reason']} (via {r['selector']})",
            })

        return {
            "company": company.name,
            "urls_scraped": urls_scraped,
            "screenshots": screenshots,
            "pagination_debug": all_pagination_debug,
            "include_expr": include_expr,
            "exclude_keywords": exclude_kws,
            "total_found": len(all_jobs),
            "total_rejected": len(all_rejected),
            "after_filter": kept_count,
            "jobs": results,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if browser:
            await browser.close()
        if pw:
            await pw.stop()


def _company_to_dict(c: Company, application_count: int = 0) -> dict:
    urls = c.scrape_urls or []
    detected_types = {url: detect_scrape_type(url) for url in urls if url.strip()}
    return {
        "id": str(c.id),
        "name": c.name,
        "aliases": c.aliases or [],
        "auto_scoring_depth": c.auto_scoring_depth,
        "active": c.active,
        "scrape_urls": urls,
        "tier": c.tier,
        "selected_cv_ids": c.selected_cv_ids or [],
        "playwright_enabled": c.playwright_enabled,
        "scrape_interval_minutes": c.scrape_interval_minutes,
        "title_include_expr": c.title_include_expr,
        "title_exclude_keywords": c.title_exclude_keywords or [],
        "wait_for_selector": c.wait_for_selector,
        "max_pages": c.max_pages or 5,
        "jobspy_search_term": c.jobspy_search_term,
        "h1b_slug": c.h1b_slug,
        "detected_scrape_types": detected_types,
        "application_count": application_count,
        "h1b_lca_count": c.h1b_lca_count,
        "h1b_approval_rate": c.h1b_approval_rate,
        "h1b_median_salary": c.h1b_median_salary,
        "h1b_last_checked": c.h1b_last_checked.isoformat() if c.h1b_last_checked else None,
        "last_scraped_at": c.last_scraped_at.isoformat() if c.last_scraped_at else None,
        "notes": c.notes,
    }
