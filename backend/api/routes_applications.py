"""Application management endpoints."""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc
from backend.models.db import get_db, Application, Job, Company, Setting, utcnow, SessionLocal

logger = logging.getLogger("jobnavigator.applications")

router = APIRouter(prefix="/applications", tags=["applications"])


class ApplicationCreate(BaseModel):
    title: str
    company: str
    url: str
    cv_version_used: Optional[str] = None
    notes: Optional[str] = None


def _extract_clean_content(raw_html: str) -> tuple:
    """Extract clean, readable HTML from raw page. Returns (clean_html, plain_text)."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(raw_html, "html.parser")

    # Remove non-content elements
    for tag in soup.find_all([
        "script", "style", "nav", "footer", "header", "noscript",
        "iframe", "svg", "img", "video", "audio", "picture", "source",
        "form", "input", "button", "select", "textarea", "label",
        "figure", "figcaption", "canvas", "map", "area",
    ]):
        tag.decompose()

    # Remove hidden elements
    for tag in soup.find_all(True, attrs={"aria-hidden": "true"}):
        tag.decompose()
    for tag in soup.find_all(True, style=lambda s: s and "display:none" in s.replace(" ", "").lower()):
        tag.decompose()

    # Tags we keep (structural content)
    KEEP_TAGS = {
        "h1", "h2", "h3", "h4", "h5", "h6",
        "p", "ul", "ol", "li", "dl", "dt", "dd",
        "strong", "b", "em", "i", "a", "br",
        "div", "span", "section", "article", "main",
        "table", "tr", "td", "th", "thead", "tbody",
        "blockquote", "pre", "code", "hr",
    }

    # Strip all attributes except href on <a> tags
    for tag in soup.find_all(True):
        if tag.name not in KEEP_TAGS:
            tag.unwrap()  # Replace tag with its contents
        elif tag.name == "a":
            href = tag.get("href", "")
            tag.attrs = {"href": href, "target": "_blank"} if href else {}
        else:
            tag.attrs = {}

    # Get the body content
    body = soup.body if soup.body else soup
    clean_html = str(body)

    # Collapse excessive whitespace / empty divs
    import re
    clean_html = re.sub(r'(<br\s*/?>[\s]*){3,}', '<br><br>', clean_html)
    clean_html = re.sub(r'(<div>\s*</div>\s*){2,}', '', clean_html)
    clean_html = re.sub(r'\n{3,}', '\n\n', clean_html)

    # Plain text for search/analysis
    text = soup.get_text(separator="\n", strip=True)[:50_000]

    return clean_html[:500_000], text


async def _fetch_with_playwright(url: str) -> str:
    """Fetch a page using Playwright for SPA/JS-rendered sites. Returns raw HTML."""
    from backend.scraper.playwright_scraper import _get_browser, _new_page, _close_page
    pw, browser = await _get_browser()
    try:
        page = await _new_page(browser)
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(2000)  # Extra time for JS rendering
            return await page.content()
        finally:
            await _close_page(page)
    finally:
        await browser.close()
        await pw.stop()


async def _cache_job_page(job_id: str, url: str):
    """Fetch and cache the job page as clean readable HTML."""
    import httpx
    from datetime import datetime, timezone

    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job or not url:
            return

        try:
            # Try httpx first (fast, works for most sites)
            html = None
            try:
                async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                    resp = await client.get(url, headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    })
                    resp.raise_for_status()
                    html = resp.text[:1_000_000]
            except Exception as e:
                logger.info(f"httpx failed for job {job_id}, will try Playwright: {e}")

            clean_html, text = _extract_clean_content(html) if html else ("", "")

            # If too little content, fall back to Playwright (handles SPAs like Meta, Apple)
            if len(text) < 200:
                logger.info(f"Thin content ({len(text)} chars) for job {job_id}, trying Playwright")
                try:
                    pw_html = await _fetch_with_playwright(url)
                    if pw_html:
                        clean_html, text = _extract_clean_content(pw_html)
                        logger.info(f"Playwright got {len(text)} text chars for job {job_id}")
                except Exception as e:
                    logger.warning(f"Playwright fallback failed for job {job_id}: {e}")

            if len(text) > 50:
                job.cached_page_html = clean_html
                job.cached_page_text = text
                job.page_cached_at = datetime.now(timezone.utc)
                db.commit()
                logger.info(f"Cached page for job {job_id}: {len(clean_html)} clean HTML, {len(text)} text chars")
            else:
                logger.warning(f"No usable content for job {job_id} ({url})")

        except Exception as e:
            logger.warning(f"Failed to cache page for job {job_id}: {e}")

    finally:
        db.close()


@router.post("")
def create_application(
    data: ApplicationCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Create application (used by Chrome extension). Also creates job record if needed."""
    # Generate external_id for dedup (use same normalization as scrapers)
    from backend.scraper.deduplicator import make_external_id
    external_id = make_external_id(data.company, data.title, data.url)

    # Find or create job
    job = db.query(Job).filter(Job.external_id == external_id).first()
    if not job:
        job = Job(
            external_id=external_id,
            company=data.company,
            title=data.title,
            url=data.url,
            source="direct",
            status="applied",
            seen=True,
        )
        db.add(job)
        db.flush()
    else:
        job.status = "applied"

    # Upsert application — overwrite if one already exists for this job
    app = db.query(Application).filter(Application.job_id == job.id).first()
    if app:
        app.status = "applied"
        if data.cv_version_used is not None:
            app.cv_version_used = data.cv_version_used
        if data.notes is not None:
            app.notes = data.notes
        app.updated_at = utcnow()
    else:
        app = Application(
            job_id=job.id,
            status="applied",
            cv_version_used=data.cv_version_used,
            notes=data.notes,
        )
        db.add(app)
    db.commit()

    # Auto-create company if it doesn't exist (only on application, not during scraping)
    if data.company and data.company.strip():
        company_name = data.company.strip()
        from backend.models.db import find_company_by_name
        existing_co = find_company_by_name(db, company_name)
        if not existing_co:
            default_cv_row = db.query(Setting).filter(Setting.key == "default_cv_id").first()
            default_cv_ids = [default_cv_row.value] if default_cv_row and default_cv_row.value else []
            new_co = Company(
                name=company_name, tier=None, active=False, playwright_enabled=False,
                selected_cv_ids=default_cv_ids,
            )
            db.add(new_co)
            db.flush()
            db.commit()
            logger.info(f"Auto-created company '{company_name}' from application")
            # Fire H-1B lookup in background
            from backend.analyzer.h1b_checker import fetch_h1b_for_company_id
            background_tasks.add_task(fetch_h1b_for_company_id, str(new_co.id))

    # Cache job page in background if not already cached
    if data.url and not job.cached_page_html:
        background_tasks.add_task(_cache_job_page, str(job.id), data.url)

    return {
        "id": str(app.id),
        "job_id": str(job.id),
        "status": app.status,
        "company": job.company,
        "title": job.title,
    }


@router.get("")
def list_applications(
    status: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    q = db.query(Application)
    if status:
        q = q.filter(Application.status == status)

    total = q.count()
    apps = q.order_by(desc(Application.updated_at)).offset(offset).limit(limit).all()

    return {
        "total": total,
        "applications": [_app_to_dict(a) for a in apps],
    }


@router.patch("/{app_id}")
def update_application(app_id: str, updates: dict, db: Session = Depends(get_db)):
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    allowed = {"status", "notes", "next_action", "next_action_date", "cv_version_used"}
    # Track status transitions
    if "status" in updates and updates["status"] != app.status:
        from backend.models.db import record_transition
        record_transition(app, updates["status"], "ui")
        del updates["status"]  # already set by record_transition
    for key, value in updates.items():
        if key in allowed:
            setattr(app, key, value)
    app.updated_at = utcnow()
    db.commit()
    return _app_to_dict(app)


@router.delete("/{app_id}")
def delete_application(app_id: str, db: Session = Depends(get_db)):
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    db.delete(app)
    db.commit()
    return {"deleted": True}


def _app_to_dict(a: Application) -> dict:
    job = a.job
    return {
        "id": str(a.id),
        "job_id": str(a.job_id),
        "status": a.status,
        "applied_at": a.applied_at.isoformat() if a.applied_at else None,
        "cv_version_used": a.cv_version_used,
        "notes": a.notes,
        "next_action": a.next_action,
        "next_action_date": a.next_action_date.isoformat() if a.next_action_date else None,
        "last_email_received": a.last_email_received.isoformat() if a.last_email_received else None,
        "last_email_snippet": a.last_email_snippet,
        "status_transitions": a.status_transitions or [],
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
        "company": job.company if job else None,
        "title": job.title if job else None,
        "url": job.url if job else None,
        "best_cv": job.best_cv if job else None,
        "short_id": job.short_id if job else None,
    }
