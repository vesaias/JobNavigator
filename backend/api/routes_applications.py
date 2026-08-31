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


VALID_STATUSES = {"applied", "interview", "offer", "rejected"}


class ApplicationCreate(BaseModel):
    title: str
    company: str
    url: str
    cv_version_used: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None          # applied|interview|offer (Log-application modal)
    applied_at: Optional[str] = None      # ISO date/datetime for back-dated entries


class InterviewCreate(BaseModel):
    what: str
    when_text: Optional[str] = None
    status: Optional[str] = "scheduled"
    prep: Optional[str] = None


class ExtractRequest(BaseModel):
    url: str


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
    from backend.scraper._shared.browser import _get_browser, _new_page, _close_page
    from backend.scraper._shared.url_safety import assert_public_http_url
    # Revalidate even though callers already gate on the plain-httpx path —
    # this function is also reachable directly and a single missed caller is
    # enough to reopen the SSRF hole.
    assert_public_http_url(url)
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
    from datetime import datetime, timezone
    from backend.scraper._shared.url_safety import safe_get, assert_public_http_url, UnsafeURLError

    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job or not url:
            return

        # SSRF gate — reject before any fetch. User-submitted job URLs from the
        # Chrome extension land here; without this check an attacker could cache
        # http://169.254.169.254/ or http://db:5432/ and read it from the UI.
        try:
            assert_public_http_url(url)
        except UnsafeURLError as e:
            logger.warning(f"Rejected unsafe job URL for {job_id}: {e}")
            try:
                job.cache_error = f"unsafe URL: {e}"[:500]
                db.commit()
            except Exception:
                db.rollback()
            return

        # Track the last error so it can be surfaced to the UI via job.cache_error
        last_error: str | None = None

        try:
            # Try httpx first (fast, works for most sites)
            html = None
            try:
                resp = await safe_get(url, timeout=20, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                })
                resp.raise_for_status()
                html = resp.text[:1_000_000]
            except UnsafeURLError as e:
                # Caught mid-redirect — don't fall back to Playwright for unsafe URLs.
                logger.warning(f"Unsafe redirect target for job {job_id}: {e}")
                try:
                    job.cache_error = f"unsafe redirect: {e}"[:500]
                    db.commit()
                except Exception:
                    db.rollback()
                return
            except Exception as e:
                logger.info(f"httpx failed for job {job_id}, will try Playwright: {e}")
                last_error = f"httpx: {e}"

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
                    last_error = f"playwright: {e}"

            if len(text) > 50:
                job.cached_page_html = clean_html
                job.cached_page_text = text
                job.page_cached_at = datetime.now(timezone.utc)
                job.cache_error = None  # Clear any previous error on success
                db.commit()
                logger.info(f"Cached page for job {job_id}: {len(clean_html)} clean HTML, {len(text)} text chars")
            else:
                msg = last_error or f"no usable content ({len(text)} chars)"
                logger.warning(f"No usable content for job {job_id} ({url}): {msg}")
                try:
                    job.cache_error = msg[:500]
                    db.commit()
                except Exception:
                    db.rollback()

        except Exception as e:
            logger.warning(f"Failed to cache page for job {job_id}: {e}")
            try:
                job.cache_error = str(e)[:500]
                db.commit()
            except Exception:
                db.rollback()

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
    from backend.scraper._shared.dedup import make_external_id
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
    from backend.models.db import record_transition
    new_status = data.status if data.status in VALID_STATUSES else "applied"
    applied_at = None
    if data.applied_at:
        from datetime import datetime
        try:
            applied_at = datetime.fromisoformat(data.applied_at.replace("Z", "+00:00"))
        except ValueError:
            logger.info("ignoring unparseable applied_at %r", data.applied_at)

    app = db.query(Application).filter(Application.job_id == job.id).first()
    if app:
        # go through record_transition so the move shows up in the Stats funnel
        record_transition(app, new_status, "ui")
        if data.cv_version_used is not None:
            app.cv_version_used = data.cv_version_used
        if data.notes is not None:
            app.notes = data.notes
        if applied_at:
            app.applied_at = applied_at
        app.updated_at = utcnow()
    else:
        app = Application(
            job_id=job.id,
            status=new_status,
            cv_version_used=data.cv_version_used,
            notes=data.notes,
            # seed the funnel edge — extension-created rows used to have an empty
            # history, so they never showed as an "-> applied" edge in the Sankey
            status_transitions=[{
                "from": None, "to": new_status,
                "at": utcnow().isoformat(), "source": "ui",
            }],
        )
        if applied_at:
            app.applied_at = applied_at
        db.add(app)
    db.commit()

    # Auto-create company if it doesn't exist (only on application, not during scraping)
    if data.company and data.company.strip():
        company_name = data.company.strip()
        from backend.models.db import find_company_by_name
        existing_co = find_company_by_name(db, company_name)
        if not existing_co:
            default_resume_row = db.query(Setting).filter(Setting.key == "default_resume_id").first()
            default_resume_ids = [default_resume_row.value] if default_resume_row and default_resume_row.value else []
            new_co = Company(
                name=company_name, tier=None, active=False, playwright_enabled=False,
                selected_resume_ids=default_resume_ids,
            )
            db.add(new_co)
            db.flush()
            db.commit()
            logger.info(f"Auto-created company '{company_name}' from application")
            # Fire H-1B lookup in background
            from backend.analyzer.h1b_checker import fetch_h1b_for_company_id
            background_tasks.add_task(fetch_h1b_for_company_id, str(new_co.id))

    # Cache job page in background if not already cached
    if data.url and not job.has_cached_page:
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
    limit: int = Query(200, le=2000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    from sqlalchemy.orm import selectinload
    q = db.query(Application).options(selectinload(Application.interviews))
    if status:
        q = q.filter(Application.status == status)

    total = q.count()
    apps = q.order_by(desc(Application.updated_at)).offset(offset).limit(limit).all()

    from backend.models.db import build_company_lookup, Resume
    lookup = build_company_lookup(db)
    job_ids = [a.job_id for a in apps]
    tailored = {}
    if job_ids:
        for r in (db.query(Resume)
                  .filter(Resume.job_id.in_(job_ids), Resume.is_base == False)  # noqa: E712
                  .order_by(Resume.updated_at.asc()).all()):
            tailored[str(r.job_id)] = r      # asc → last write wins = most recent
    return {
        "total": total,
        "applications": [_app_to_dict(a, lookup, tailored.get(str(a.job_id))) for a in apps],
    }


@router.patch("/{app_id}")
def update_application(app_id: str, updates: dict, db: Session = Depends(get_db)):
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    allowed = {"status", "notes", "next_action", "next_action_date", "cv_version_used", "applied_at"}
    if "status" in updates and updates["status"] not in VALID_STATUSES:
        raise HTTPException(status_code=400,
                            detail=f"status must be one of {sorted(VALID_STATUSES)}")
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
    from backend.models.db import build_company_lookup
    lookup = build_company_lookup(db)
    return _app_to_dict(app, lookup)


@router.delete("/{app_id}")
def delete_application(app_id: str, db: Session = Depends(get_db)):
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    # Deleting the application must also release the job, otherwise it stays
    # status='applied' forever and keeps counting in the Companies "Apps" column.
    job = app.job
    if job is not None and job.status == "applied":
        job.status = "saved"
    db.delete(app)
    db.commit()
    return {"deleted": True}


@router.post("/extract")
async def extract_posting(payload: ExtractRequest):
    """Read title + company off a posting URL for the Log-application modal.
    JSON-LD JobPosting first, then OpenGraph, then <title>/hostname. Always
    returns 200 with whatever it found — the form fields stay editable."""
    import json
    import re
    from urllib.parse import urlparse
    from bs4 import BeautifulSoup
    from backend.scraper._shared.url_safety import safe_get, assert_public_http_url, UnsafeURLError

    url = (payload.url or "").strip()
    try:
        assert_public_http_url(url)
    except UnsafeURLError as e:
        raise HTTPException(status_code=400, detail=f"Unsafe URL: {e}")

    title = company = None
    try:
        resp = await safe_get(url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text[:1_000_000], "html.parser")

        # 1. JSON-LD JobPosting (most ATS emit this)
        for tag in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(tag.string or "{}")
            except Exception:
                continue
            for node in (data if isinstance(data, list) else [data]):
                if not isinstance(node, dict):
                    continue
                if node.get("@type") == "JobPosting":
                    title = title or node.get("title")
                    org = node.get("hiringOrganization")
                    if isinstance(org, dict):
                        company = company or org.get("name")
                    elif isinstance(org, str):
                        company = company or org
        # 2. OpenGraph
        if not title:
            og = soup.find("meta", property="og:title")
            if og and og.get("content"):
                title = og["content"]
        if not company:
            og = soup.find("meta", property="og:site_name")
            if og and og.get("content"):
                company = og["content"]
        # 3. <title>, minus the trailing " | Company" / " at Company" tail
        if not title and soup.title and soup.title.string:
            title = re.split(r"\s+[|–—-]\s+", soup.title.string.strip())[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.info("extract failed for %s: %s", url, e)

    if not company:
        host = (urlparse(url).hostname or "").replace("www.", "")
        parts = [p for p in host.split(".") if p not in ("com", "io", "co", "org", "net", "ai", "jobs", "careers")]
        company = parts[-1].title() if parts else None

    return {"title": (title or "").strip() or None, "company": (company or "").strip() or None}


@router.post("/{app_id}/interviews", status_code=201)
def add_interview(app_id: str, data: InterviewCreate, db: Session = Depends(get_db)):
    from backend.models.db import Interview
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    iv = Interview(application_id=app.id, what=data.what,
                   when_text=data.when_text, status=data.status or "scheduled", prep=data.prep)
    db.add(iv)
    app.updated_at = utcnow()
    db.commit()
    return _interview_to_dict(iv)


@router.patch("/interviews/{interview_id}")
def update_interview(interview_id: str, updates: dict, db: Session = Depends(get_db)):
    from backend.models.db import Interview
    iv = db.query(Interview).filter(Interview.id == interview_id).first()
    if not iv:
        raise HTTPException(status_code=404, detail="Interview not found")
    for key in ("what", "when_text", "status", "prep"):
        if key in updates:
            setattr(iv, key, updates[key])
    db.commit()
    return _interview_to_dict(iv)


@router.delete("/interviews/{interview_id}")
def delete_interview(interview_id: str, db: Session = Depends(get_db)):
    from backend.models.db import Interview
    iv = db.query(Interview).filter(Interview.id == interview_id).first()
    if not iv:
        raise HTTPException(status_code=404, detail="Interview not found")
    db.delete(iv)
    db.commit()
    return {"deleted": True}


@router.get("/{app_id}/prep")
def prep_bundle(app_id: str, db: Session = Depends(get_db)):
    """Assemble the 'Prep for LLM' bundle: role, posting, résumé, notes, email
    and interviews as one pasteable block. Built here so the full cached posting
    text and flattened résumé never have to round-trip through the client."""
    from backend.models.db import Resume
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    job = app.job
    stage = (app.status or "applied").capitalize()
    days = (utcnow() - app.updated_at).days if app.updated_at else 0
    cv_name = app.cv_version_used or (job.best_cv if job else None) or "unknown résumé"

    posting_bits = []
    if job:
        lo, hi = job.salary_min, job.salary_max
        if lo or hi:
            k = lambda v: f"${round(v / 1000)}K"
            posting_bits.append(k(lo) if lo == hi or not hi else
                                (f"{k(lo)}–{k(hi)}" if lo else k(hi)))
        if job.location:
            posting_bits.append(job.location)

    lines = [
        f"# Interview prep — {(job.title if job else 'Unknown Role')} @ {(job.company if job else 'Unknown Company')}",
        "",
        f"Stage: {stage} · applied {days}d ago with {cv_name}",
    ]
    if posting_bits:
        lines.append("Posting: " + " · ".join(posting_bits))
    if app.notes:
        lines.append(f"My notes: {app.notes}")
    if app.last_email_snippet:
        lines.append(f"Last email from them: “{app.last_email_snippet}”")

    if app.interviews:
        lines += ["", "Interviews:"]
        for iv in app.interviews:
            row = f"- {iv.what} ({iv.when_text or 'Unscheduled'}, {iv.status or 'scheduled'})"
            if iv.prep:
                row += f" — {iv.prep}"
            lines.append(row)

    posting_text = (job.cached_page_text or job.description or "") if job else ""
    lines += ["", "## Cached job posting", posting_text.strip() or "[no posting text captured]"]

    resume_text = ""
    if app.cv_version_used:
        r = db.query(Resume).filter(Resume.name == app.cv_version_used).first()
        if r and r.json_data:
            try:
                from backend.analyzer.cv_scorer import _flatten_resume
                resume_text = _flatten_resume(r.json_data)
            except Exception as e:
                logger.info("prep: could not flatten résumé %s: %s", app.cv_version_used, e)
    lines += ["", f"## My résumé (as submitted) — {cv_name}", resume_text.strip() or "[résumé content unavailable]"]
    lines += ["", "Help me prepare: likely questions, what to emphasise from my background, "
                  "and questions I should ask them."]
    return {"text": "\n".join(lines)}


def _app_to_dict(a: Application, lookup=None, tailored=None) -> dict:
    """Serialize an Application. Pass lookup={lowercase: Company} (from
    build_company_lookup) to populate company_canonical for alias-aware
    grouping in the UI. When omitted, company_canonical falls back to the
    raw company name."""
    job = a.job
    raw = job.company if job else None
    canonical_co = (lookup or {}).get((raw or "").lower())
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
        "company": raw,
        "company_canonical": canonical_co.name if canonical_co else raw,
        "title": job.title if job else None,
        "url": job.url if job else None,
        "best_cv": job.best_cv if job else None,
        "short_id": job.short_id if job else None,
        # posting details the detail pane shows, so it never has to re-fetch the job
        "location": job.location if job else None,
        "salary_min": job.salary_min if job else None,
        "salary_max": job.salary_max if job else None,
        "source": job.source if job else None,
        "has_cached_page": bool(job.cached_page_html) if job else False,
        "discovered_at": job.discovered_at.isoformat() if (job and job.discovered_at) else None,
        "tailored_resume_id": str(tailored.id) if tailored else None,
        "tailored_resume_name": tailored.name if tailored else None,
        "interviews": [_interview_to_dict(i) for i in (a.interviews or [])],
    }


def _interview_to_dict(i) -> dict:
    return {
        "id": str(i.id),
        "what": i.what,
        "when_text": i.when_text,
        "status": i.status or "scheduled",
        "prep": i.prep,
        "created_at": i.created_at.isoformat() if i.created_at else None,
    }
