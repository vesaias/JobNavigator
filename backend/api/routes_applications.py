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


def _parse_dt(value):
    """Lenient ISO parse for calendar inputs ('2026-09-09T14:00' has no zone)."""
    if not value:
        return None
    from datetime import datetime, timezone
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


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
    when_at: Optional[str] = None      # ISO datetime from the calendar picker
    where_text: Optional[str] = None
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
            source="manual",   # APPS-15: hand-logged via the Log modal / extension, not a scrape
            status="applied",
            seen=True,
        )
        db.add(job)
        db.flush()
    else:
        job.status = "applied"

    # One application per job — a duplicate log is refused with 409 (APPS-04)
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
        # APPS-04: a second log for the same posting used to silently overwrite the
        # notes and reset the stage (interview -> applied, with a bogus funnel edge).
        # Refuse and point the caller at the existing record instead.
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={"message": "An application already exists for this job", "application_id": str(app.id)},
        )
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

    from backend.models.db import build_company_lookup, Resume, CoverLetter
    lookup = build_company_lookup(db)
    job_ids = [a.job_id for a in apps]
    with_letter = set()
    if job_ids:
        with_letter = {str(r[0]) for r in db.query(CoverLetter.job_id)
                       .filter(CoverLetter.job_id.in_(job_ids)).distinct().all()}
    tailored = {}
    if job_ids:
        for r in (db.query(Resume)
                  .filter(Resume.job_id.in_(job_ids), Resume.is_base == False)  # noqa: E712
                  .order_by(Resume.updated_at.asc()).all()):
            tailored[str(r.job_id)] = r      # asc → last write wins = most recent
    return {
        "total": total,
        "applications": [_app_to_dict(a, lookup, tailored.get(str(a.job_id)),
                                      str(a.job_id) in with_letter) for a in apps],
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
    changed = False
    if "status" in updates:
        if updates["status"] != app.status:
            from backend.models.db import record_transition
            record_transition(app, updates["status"], "ui")
            changed = True
        # Same status = a click on the already-active stage. record_transition()
        # already declines to log it, so treat it as a no-op here too: bumping
        # updated_at would reset the ageing signal ("Nd" cell, "N waiting >7d")
        # for something the user did not actually change (APPS-07).
        del updates["status"]
    for key, value in updates.items():
        if key in allowed:
            setattr(app, key, value)
            changed = True
    if changed:
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


# ── Employer detection for the posting-URL reader (R3-A-05) ──────────────────
# The reader used to fall back to og:site_name / hostname, which on an ATS-hosted
# board is the *board's* brand ("Greenhouse", "Lever", "Linkedin"), not the
# employer. That value lands in the Company field the user is about to save and
# becomes Job.company plus the Application grouping key, and the modal's
# "only fill empty fields" rule makes a wrong value sticky. So: derive the
# employer from the board slug for known ATS hosts, and drop any brand-looking
# fallback instead of guessing — an empty field the user types into beats a
# confidently wrong one.

# Squashed (lowercase, alphanumeric-only) names of job boards / aggregators that
# must never be returned as an employer.
_ATS_BRAND_KEYS = {
    "greenhouse", "lever", "ashby", "ashbyhq", "workday", "myworkdayjobs",
    "smartrecruiters", "rippling", "phenom", "talentbrew", "icims", "taleo",
    "eightfold", "jobvite", "workable", "breezy", "breezyhr", "bamboohr",
    "teamtailor", "recruitee", "linkedin", "indeed", "ziprecruiter",
    "glassdoor", "monster", "dice", "wellfound", "angellist", "builtin",
    "levelsfyi", "jobright", "jobspy",
}

# Path segments that are board chrome rather than a company slug.
_SLUG_NOISE = {
    "jobs", "job", "careers", "career", "embed", "api", "search", "postings",
    "posting", "job_board", "job_app", "users", "self", "login", "signin",
    "sessions", "en-us", "en",
}


def _title_slug(slug: str) -> str:
    """'clear-street' -> 'Clear Street'. Only the first letter of each word is
    forced, so already-cased slugs ('BoschGroup') survive intact."""
    import re
    words = [w for w in re.split(r"[-_+.\s]+", (slug or "").strip()) if w]
    return " ".join(w[0].upper() + w[1:] for w in words)


def _is_ats_brand(name) -> bool:
    """True if a detected 'company' is really the job board's own brand (or pure
    board chrome like 'Careers'). Used to suppress the og:site_name / hostname
    fallbacks — see R3-A-05."""
    import re
    raw = (name or "").strip()
    if not raw:
        return False
    n = re.sub(r"\b(jobs?|boards?|careers?|site|com|io|inc|ltd|llc|software)\b", " ", raw.lower())
    n = re.sub(r"[^a-z0-9]+", "", n)
    if not n:
        return True  # "Jobs", "Careers", "Job Board" — chrome, not an employer
    return n in _ATS_BRAND_KEYS


def _company_from_url(url: str):
    """Derive the employer from a known ATS board URL (slug in the path, or the
    tenant subdomain); None for anything unrecognised so the caller can fall
    back to page metadata. Reuses the scraper's is_* host predicates so the two
    stay in sync rather than growing a second copy of the ATS matrix (R3-A-05)."""
    from urllib.parse import parse_qs, urlparse
    from backend.scraper.ats.ashby import is_ashby
    from backend.scraper.ats.greenhouse import is_greenhouse
    from backend.scraper.ats.lever import is_lever
    from backend.scraper.ats.rippling import is_rippling, _parse_rippling_url
    from backend.scraper.ats.smartrecruiters import is_smartrecruiters, _extract_company_slug
    from backend.scraper.ats.workday import is_workday

    if not url:
        return None
    try:
        parsed = urlparse(url)
    except Exception:
        return None
    host = (parsed.hostname or "").lower()
    parts = [p for p in (parsed.path or "").strip("/").split("/") if p]

    def _first_slug():
        for part in parts:
            if part.lower() not in _SLUG_NOISE:
                return part
        return None

    slug = None
    try:
        if is_greenhouse(url):
            # boards.greenhouse.io/<slug>/jobs/<id>, job-boards.greenhouse.io/<slug>/...,
            # and the embed form boards.greenhouse.io/embed/job_board?for=<slug>.
            slug = (parse_qs(parsed.query).get("for") or [None])[0] or _first_slug()
        elif is_lever(url):            # jobs.lever.co/<slug>/<id>
            slug = _first_slug()
        elif is_ashby(url):            # jobs.ashbyhq.com/<slug>/<id>
            slug = _first_slug()
        elif is_smartrecruiters(url):  # jobs|careers|api.smartrecruiters.com/<slug>/...
            slug = _extract_company_slug(url)
        elif is_workday(url):          # <company>.wd5.myworkdayjobs.com/<site>/...
            sub = host.split(".")[0]
            slug = sub if sub not in ("www", "jobs", "careers") else None
        elif is_rippling(url):         # ats.rippling.com/<slug>/jobs
            slug, _ = _parse_rippling_url(url)
    except Exception:  # a malformed board URL must never break the reader
        return None

    if not slug or slug.lower() in _SLUG_NOISE:
        return None
    return _title_slug(slug) or None


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
            # R3-A-05: ATS boards set og:site_name to their own brand, so a
            # brand-looking value is dropped and the slug layer below wins.
            if og and og.get("content") and not _is_ats_brand(og["content"]):
                company = og["content"]
        # 3. <title>, minus the trailing " | Company" / " at Company" tail
        if not title and soup.title and soup.title.string:
            title = re.split(r"\s+[|–—-]\s+", soup.title.string.strip())[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.info("extract failed for %s: %s", url, e)

    # R3-A-05: known ATS board URLs carry the employer in the path/subdomain —
    # read it there before falling back to the hostname, which on those hosts is
    # the ATS brand.
    if not company:
        company = _company_from_url(url)

    if not company:
        host = (urlparse(url).hostname or "").replace("www.", "")
        parts = [p for p in host.split(".") if p not in ("com", "io", "co", "org", "net", "ai", "jobs", "careers")]
        candidate = parts[-1].title() if parts else None
        # Leave it empty rather than fill the Company field with a board name.
        company = candidate if candidate and not _is_ats_brand(candidate) else None

    return {"title": (title or "").strip() or None, "company": (company or "").strip() or None}


@router.post("/{app_id}/interviews", status_code=201)
def add_interview(app_id: str, data: InterviewCreate, db: Session = Depends(get_db)):
    from backend.models.db import Interview
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    iv = Interview(application_id=app.id, what=data.what, where_text=data.where_text,
                   when_at=_parse_dt(data.when_at), status=data.status or "scheduled", prep=data.prep)
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
    for key in ("what", "where_text", "status", "prep"):
        if key in updates:
            setattr(iv, key, updates[key])
    if "when_at" in updates:
        iv.when_at = _parse_dt(updates["when_at"])
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
    """Assemble the interview prep handover — four plain sections in the order a
    model reads best: the role, my résumé, the posting, and what I want back.
    The closing ask is the editable `prep_ask` setting. No LLM call here — this
    is the context, not the answer."""
    from backend.models.db import Resume
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    job = app.job

    def money(lo, hi):
        def k(v):
            return "$" + str(round(v / 1000)) + "K"
        if lo and hi and lo != hi:
            return k(lo) + "–" + k(hi)
        return k(lo or hi) if (lo or hi) else None

    # Which optional sections to include (Settings -> Interview prep).
    inc_row = db.query(Setting).filter(Setting.key == "prep_include").first()
    inc = {x.strip() for x in ((inc_row.value if inc_row else None) or "resume,posting,notes").split(",") if x.strip()}

    L = []
    add = L.append
    title = (job.title if job else None) or "Unknown Role"
    company = (job.company if job else None) or "Unknown Company"

    # ── 1. the role ──────────────────────────────────────────────────────────
    add("# " + title + " at " + company)
    add("")
    add("## The role")
    add("- Company: " + company)
    add("- Title: " + title)
    if job:
        if job.location:
            add("- Location: " + job.location + (" (remote)" if job.remote else ""))
        sal = money(job.salary_min, job.salary_max)
        if sal:
            add("- Listed salary: " + sal)
        if job.url:
            add("- Posting: " + job.url)
    add("- Stage: " + (app.status or "applied").capitalize())
    if app.interviews:
        add("- Interviews booked:")
        for iv in app.interviews:
            when = iv.when_at.strftime("%a %d %b %Y, %H:%M") if iv.when_at else "unscheduled"
            where = (" · " + iv.where_text) if iv.where_text else ""
            row = "  - " + iv.what + " — " + when + where + " (" + (iv.status or "scheduled") + ")"
            if iv.prep:
                row += "\n    prep note: " + iv.prep
            add(row)
    if app.notes and "notes" in inc:
        add("- My notes on this application: " + " ".join(app.notes.split()))

    # ── 2. my résumé, flattened to plain text ────────────────────────────────
    tailored = None
    if app.job_id:
        tailored = (db.query(Resume)
                    .filter(Resume.job_id == app.job_id, Resume.is_base == False)  # noqa: E712
                    .order_by(Resume.updated_at.desc()).first())
    cv_name = (tailored.name if tailored else None) or app.cv_version_used or (job.best_cv if job else None)
    src = tailored
    if not src and cv_name:
        src = db.query(Resume).filter(Resume.name == cv_name).first()
    resume_text = ""
    if src and src.json_data:
        try:
            from backend.analyzer.cv_scorer import _flatten_resume
            resume_text = _flatten_resume(src.json_data)
        except Exception as e:
            logger.info("prep: could not flatten résumé %s: %s", cv_name, e)
    if "resume" in inc:
        add("")
        add("## My résumé" + (" — " + cv_name if cv_name else ""))
    # _flatten_resume emits its own "## Summary"/"## Experience" headings — demote
    # them so they read as parts of the résumé, not siblings of "The posting".
        body = resume_text.strip() or "[résumé content unavailable]"
        add("\n".join(("#" + ln) if ln.startswith("##") else ln for ln in body.splitlines()))

    # ── 3. the posting, plain text ───────────────────────────────────────────
    if "posting" in inc:
        posting = ((job.cached_page_text or job.description) if job else "") or ""
        add("")
        add("## The posting")
        add(posting.strip() or "[no posting text was captured]")

    # ── 4. the ask — editable in Settings → AI ───────────────────────────────
    ask = db.query(Setting).filter(Setting.key == "prep_ask").first()
    add("")
    add("## What I need from you")
    add((ask.value.strip() if ask and ask.value else "") or "Prepare me for this interview.")
    return {"text": "\n".join(L)}


def _app_to_dict(a: Application, lookup=None, tailored=None, has_cover_letter=False) -> dict:
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
        "has_cover_letter": has_cover_letter,
        "interviews": [_interview_to_dict(i) for i in (a.interviews or [])],
    }


def _interview_to_dict(i) -> dict:
    return {
        "id": str(i.id),
        "what": i.what,
        "when_at": i.when_at.isoformat() if i.when_at else None,
        "where_text": i.where_text,
        "status": i.status or "scheduled",
        "prep": i.prep,
        "created_at": i.created_at.isoformat() if i.created_at else None,
    }
