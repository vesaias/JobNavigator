"""FastAPI entry point for JobNavigator."""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.models.db import create_tables, SessionLocal, Setting, JobRun
from backend.seed import run_seeds
from backend.config import INITIAL_API_KEY, TELEGRAM_BOT_TOKEN
from backend.job_monitor import launch_background, JobAlreadyRunningError, get_all_running, is_running, _get_running_by_job_type, cleanup_stale_runs

from backend.api.routes_settings import router as settings_router
from backend.api.routes_cvs import router as cvs_router
from backend.api.routes_jobs import router as jobs_router
from backend.api.routes_applications import router as applications_router
from backend.api.routes_companies import router as companies_router
from backend.api.routes_searches import router as searches_router
from backend.api.routes_resumes import router as resumes_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("jobnavigator")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create tables, seed data, start scheduler."""
    logger.info("Starting JobNavigator backend...")
    create_tables()
    run_seeds()

    # Set initial API key if dashboard_api_key is empty
    db = SessionLocal()
    try:
        setting = db.query(Setting).filter(Setting.key == "dashboard_api_key").first()
        if setting and not setting.value:
            setting.value = INITIAL_API_KEY
            db.commit()
    finally:
        db.close()

    # Clean up stale job runs from previous process
    cleanup_stale_runs()

    # Start scheduler
    from backend.scheduler import scheduler, configure_scheduler
    configure_scheduler()
    scheduler.start()
    logger.info("Database initialized, seeded, scheduler started.")

    yield

    scheduler.shutdown()
    logger.info("Shutting down JobNavigator backend...")


OPENAPI_TAGS = [
    {"name": "triggers", "description": "Manual trigger endpoints - run scrapes, analysis, email checks, etc. on demand"},
    {"name": "scheduler", "description": "View scheduled jobs and activity log"},
    {"name": "stats", "description": "Aggregate statistics and scrape history"},
    {"name": "settings", "description": "Global settings (key-value store)"},
    {"name": "searches", "description": "Search configurations for JobSpy board scraping"},
    {"name": "companies", "description": "Company management - scrape URLs, CV selection, H-1B data, filters"},
    {"name": "jobs", "description": "Job listings discovered by scrapers"},
    {"name": "applications", "description": "Job applications tracked by Chrome extension and email monitor"},
    {"name": "cvs", "description": "CV upload, extraction, and management (max 5)"},
    {"name": "telegram", "description": "Telegram bot webhook and test endpoints"},
    {"name": "monitor", "description": "Job execution monitoring — active runs, run history"},
    {"name": "system", "description": "Health check and system info"},
]

app = FastAPI(
    title="JobNavigator API",
    version="1.0.0",
    description=(
        "Personal job hunt automation system. Scrapes job boards and career pages, "
        "scores jobs against CVs using Claude API, monitors Gmail for responses, "
        "sends Telegram notifications.\n\n"
        "**Auth:** Pass `X-API-Key` header with dashboard API key. "
        "Health, docs, and OpenAPI endpoints skip auth."
    ),
    openapi_tags=OPENAPI_TAGS,
    lifespan=lifespan,
)

# CORS — allow dashboard frontend (configurable via ALLOWED_ORIGINS env var)
import os as _os_cors
_allowed_origins = _os_cors.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost,http://localhost:3000,http://localhost:80"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _allowed_origins if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── API Key auth middleware ──────────────────────────────────────────────────
import hmac as _hmac_mw

# Paths that NEVER require auth (exact or prefix match)
_PUBLIC_PREFIXES = ("/health", "/docs", "/openapi.json", "/redoc", "/cv/", "/api/telegram/webhook", "/api/auth/set-session", "/api/auth/verify", "/api/auth/logout")

@app.middleware("http")
async def api_key_auth(request: Request, call_next):
    path = request.url.path

    # Let CORS preflight requests pass through so CORSMiddleware can respond
    if request.method == "OPTIONS":
        return await call_next(request)

    # Public endpoints
    if any(path == p or path.startswith(p + "/") or path == p.rstrip("/") for p in _PUBLIC_PREFIXES):
        return await call_next(request)
    # docs subpaths
    if path.startswith("/docs"):
        return await call_next(request)

    # Accept either X-API-Key header (API clients, extension) OR jn_session cookie (browser)
    api_key = request.headers.get("X-API-Key", "") or request.cookies.get("jn_session", "")

    db = SessionLocal()
    try:
        setting = db.query(Setting).filter(Setting.key == "dashboard_api_key").first()
        expected = setting.value if setting else INITIAL_API_KEY
        # First-run: no key configured → allow everything
        if not expected:
            # WARNING-level so operators see this in logs when they shouldn't (e.g.,
            # dashboard_api_key setting cleared by a botched DB restore).
            logger.warning(
                "api key BYPASS (first-run mode): path=%s — dashboard_api_key setting is empty",
                request.url.path,
            )
            return await call_next(request)
        # Key configured → require match (timing-safe compare)
        if not api_key:
            return JSONResponse(status_code=401, content={"detail": "API key required"})
        if not _hmac_mw.compare_digest(api_key, expected):
            return JSONResponse(status_code=401, content={"detail": "Invalid API key"})
    finally:
        db.close()

    return await call_next(request)


# ── Auth endpoints (cookie session) ──────────────────────────────────────────
import hmac as _hmac
from fastapi import Response as _Response

@app.post("/api/auth/verify", tags=["auth"], summary="Verify an API key without setting a session")
async def verify_api_key(body: dict):
    """Validate API key. Returns 200 {ok: true} on match, 401 otherwise."""
    api_key = (body or {}).get("api_key", "")
    db = SessionLocal()
    try:
        setting = db.query(Setting).filter(Setting.key == "dashboard_api_key").first()
        expected = setting.value if setting else INITIAL_API_KEY
        if not expected:
            return {"ok": True, "first_run": True}
        if not api_key or not _hmac.compare_digest(api_key, expected):
            raise HTTPException(status_code=401, detail="Invalid API key")
        return {"ok": True, "first_run": False}
    finally:
        db.close()


@app.post("/api/auth/set-session", tags=["auth"], summary="Set session cookie from API key")
async def set_session(body: dict, response: _Response):
    """Verify API key and set httpOnly jn_session cookie. Cookie is sent on all
    same-origin requests (including iframe/download URLs)."""
    api_key = (body or {}).get("api_key", "")
    db = SessionLocal()
    try:
        setting = db.query(Setting).filter(Setting.key == "dashboard_api_key").first()
        expected = setting.value if setting else INITIAL_API_KEY
        if expected and (not api_key or not _hmac.compare_digest(api_key, expected)):
            raise HTTPException(status_code=401, detail="Invalid API key")
        # First-run (no key configured) is OK - set cookie to empty, middleware will allow
        cookie_value = api_key or ""
        response.set_cookie(
            key="jn_session",
            value=cookie_value,
            httponly=True,
            samesite="strict",
            max_age=60 * 60 * 24 * 30,  # 30 days
            secure=False,  # set True when deployed over HTTPS
        )
        return {"ok": True}
    finally:
        db.close()


@app.post("/api/auth/logout", tags=["auth"], summary="Clear session cookie")
async def logout(response: _Response):
    response.delete_cookie(key="jn_session", samesite="strict", httponly=True)
    return {"ok": True}


# ── Routes ───────────────────────────────────────────────────────────────────
app.include_router(settings_router, prefix="/api")
app.include_router(cvs_router, prefix="/api")
app.include_router(jobs_router, prefix="/api")
app.include_router(applications_router, prefix="/api")
app.include_router(companies_router, prefix="/api")
app.include_router(searches_router, prefix="/api")
app.include_router(resumes_router, prefix="/api")


@app.get("/health", tags=["system"], summary="Health check")
def health_check():
    """Returns OK if the backend is running."""
    return {"status": "ok", "service": "JobNavigator"}


@app.get("/cv/{token}", tags=["tracer"], summary="Tracer link redirect")
async def tracer_redirect(token: str, request: Request):
    """Public redirect endpoint for tracer links. Logs click, then 302 redirects."""
    import re
    import hashlib
    from backend.models.db import TracerLink, TracerClickEvent

    db = SessionLocal()
    try:
        link = db.query(TracerLink).filter(TracerLink.token == token, TracerLink.is_active == True).first()
        if not link:
            raise HTTPException(404, "Link not found")

        # Parse user-agent
        ua = (request.headers.get("user-agent") or "").lower()
        device_type = "mobile" if any(m in ua for m in ("mobile", "android", "iphone", "ipad")) else \
                      "tablet" if "tablet" in ua else "desktop"
        ua_family = "chrome" if "chrome" in ua and "edge" not in ua else \
                    "firefox" if "firefox" in ua else \
                    "safari" if "safari" in ua and "chrome" not in ua else \
                    "edge" if "edge" in ua else "unknown"
        os_family = "windows" if "windows" in ua else \
                    "macos" if "macintosh" in ua else \
                    "ios" if any(x in ua for x in ("iphone", "ipad")) else \
                    "android" if "android" in ua else \
                    "linux" if "linux" in ua else "unknown"

        # Bot detection
        bot_pattern = re.compile(
            r'\b(bot|crawler|spider|preview|scanner|headless|curl|wget|'
            r'slackbot|discordbot|facebookexternalhit|whatsapp|'
            r'skypeuripreview|linkedinbot|googleimageproxy)\b', re.I
        )
        is_bot = bool(bot_pattern.search(request.headers.get("user-agent") or ""))

        # Hash IP /24 prefix
        ip = request.client.host if request.client else None
        ip_hash = None
        if ip:
            parts = ip.split(".")
            if len(parts) == 4:
                prefix = f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
            else:
                prefix = ip
            ip_hash = hashlib.sha256(prefix.encode()).hexdigest()

        # Referrer hostname
        referrer = request.headers.get("referer")
        referrer_host = None
        if referrer:
            try:
                from urllib.parse import urlparse
                referrer_host = urlparse(referrer).hostname
            except Exception:
                pass

        # Capture destination BEFORE the click-log write so we can always redirect,
        # even if the click-log commit fails (e.g., constraint violation, transient
        # DB error). Click logging is best-effort.
        destination = link.destination_url

        # Log click — best-effort. Failures here must not break the redirect.
        try:
            event = TracerClickEvent(
                tracer_link_id=link.id,
                device_type=device_type,
                ua_family=ua_family,
                os_family=os_family,
                referrer_host=referrer_host,
                ip_hash=ip_hash,
                is_likely_bot=is_bot,
            )
            db.add(event)
            db.commit()
        except Exception as e:
            logger.exception("Tracer click log failed for token=%s: %s", token, e)
            # Rollback so the session isn't left in an error state.
            try:
                db.rollback()
            except Exception:
                pass
    finally:
        db.close()

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=destination, status_code=302)


# ── Trigger endpoints (non-blocking, return 202) ────────────────────────────
@app.post("/api/scrape/run-all", tags=["triggers"], summary="Run all scrapes", status_code=202)
async def trigger_all_scrapes():
    """Run all active JobSpy keyword searches + all active Playwright career page scrapes.
    Returns immediately with a run_id. Check progress via /api/monitor/active.
    """
    async def _do():
        from backend.scraper.orchestrator import run_all as run_all_searches
        await run_all_searches(force=True)
        from backend.analyzer.cv_scorer import analyze_unscored_jobs
        await analyze_unscored_jobs()

    try:
        run_id = launch_background("scrape_all", _do, trigger="manual")
        return {"run_id": run_id, "status": "running"}
    except JobAlreadyRunningError as e:
        logger.info("Duplicate trigger rejected for job_type=%s", e.job_type)
        return JSONResponse(
            status_code=409,
            content={"detail": f"{e.job_type} is already running"},
        )


@app.post("/api/email/check-now", tags=["triggers"], summary="Check Gmail now", status_code=202)
async def trigger_email_check():
    """Poll Gmail for new emails. Returns immediately with a run_id."""
    async def _do():
        from backend.email_monitor.gmail_client import check_emails
        await check_emails()

    try:
        run_id = launch_background("email_check", _do, trigger="manual")
        return {"run_id": run_id, "status": "running"}
    except JobAlreadyRunningError as e:
        logger.info("Duplicate trigger rejected for job_type=%s", e.job_type)
        return JSONResponse(
            status_code=409,
            content={"detail": f"{e.job_type} is already running"},
        )


@app.post("/api/h1b/refresh", tags=["triggers"], summary="Refresh H-1B data", status_code=202)
async def trigger_h1b_refresh():
    """Scrape MyVisaJobs.com for all active companies. Returns immediately with a run_id."""
    async def _do():
        from backend.analyzer.h1b_checker import refresh_all_h1b
        await refresh_all_h1b()

    try:
        run_id = launch_background("h1b_refresh", _do, trigger="manual")
        return {"run_id": run_id, "status": "running"}
    except JobAlreadyRunningError as e:
        logger.info("Duplicate trigger rejected for job_type=%s", e.job_type)
        return JSONResponse(
            status_code=409,
            content={"detail": f"{e.job_type} is already running"},
        )


@app.post("/api/analyze/{job_id}", tags=["triggers"], summary="Analyze a single job", status_code=202)
async def trigger_analysis(job_id: str, depth: str = "full", body: dict = None):
    """Re-run CV scoring for a specific job. depth: 'light' or 'full' (default)."""
    cv_ids = (body or {}).get("cv_ids")

    async def _do():
        from backend.analyzer.cv_scorer import score_single_job
        await score_single_job(job_id, cv_ids=cv_ids, depth=depth)

    # Include cv_ids in scope_key so scoring the same job with different CVs doesn't conflict
    scope = f"{job_id}:{','.join(sorted(cv_ids))}" if cv_ids else job_id
    try:
        run_id = launch_background("analyze_job", _do, trigger="manual", scope_key=scope)
        return {"run_id": run_id, "status": "running", "job_id": job_id}
    except JobAlreadyRunningError as e:
        logger.info("Duplicate trigger rejected for job_type=%s", e.job_type)
        return JSONResponse(
            status_code=409,
            content={"detail": f"{e.job_type} is already running"},
        )


@app.post("/api/db/cleanup", tags=["triggers"], summary="Database cleanup", status_code=202)
async def trigger_job_cleanup():
    """Delete old skipped/ignored jobs. Returns immediately with a run_id."""
    async def _do():
        from backend.models.db import Job
        from datetime import timedelta, timezone as tz
        from datetime import datetime as dt
        from backend.scheduler import get_setting
        db = SessionLocal()
        try:
            archive_days = int(get_setting(db, "job_archive_after_days", "0"))
            if archive_days <= 0:
                return
            cutoff = dt.now(tz.utc) - timedelta(days=archive_days)
            old_skipped = db.query(Job).filter(Job.status == "skip", Job.discovered_at < cutoff).all()
            count = len(old_skipped)
            for job in old_skipped:
                db.delete(job)
            db.commit()
            from backend.activity import log_activity
            log_activity("scrape", f"Job cleanup: deleted {count} old skipped jobs (>{archive_days} days)")
        finally:
            db.close()

    try:
        run_id = launch_background("job_cleanup", _do, trigger="manual")
        return {"run_id": run_id, "status": "running"}
    except JobAlreadyRunningError as e:
        logger.info("Duplicate trigger rejected for job_type=%s", e.job_type)
        return JSONResponse(
            status_code=409,
            content={"detail": f"{e.job_type} is already running"},
        )


@app.post("/api/auto-reject/run", tags=["triggers"], summary="Run auto-reject now", status_code=202)
async def trigger_auto_reject():
    """Run auto-reject on stale applications. Returns immediately with a run_id."""
    async def _do():
        from backend.models.db import Application, record_transition
        from backend.scheduler import get_setting
        from datetime import timedelta, timezone as tz
        from datetime import datetime as dt
        db = SessionLocal()
        try:
            days = int(get_setting(db, "auto_reject_after_days", "0"))
            if days <= 0:
                return
            cutoff = dt.now(tz.utc) - timedelta(days=days)
            keep = ["rejected", "offer"]
            stale = db.query(Application).filter(
                ~Application.status.in_(keep),
                Application.applied_at < cutoff,
            ).all()
            count = 0
            for app in stale:
                record_transition(app, "rejected", "scheduler")
                count += 1
            if count:
                db.commit()
        finally:
            db.close()

    try:
        run_id = launch_background("auto_reject", _do, trigger="manual")
        return {"run_id": run_id, "status": "running"}
    except JobAlreadyRunningError as e:
        logger.info("Duplicate trigger rejected for job_type=%s", e.job_type)
        return JSONResponse(
            status_code=409,
            content={"detail": f"{e.job_type} is already running"},
        )


@app.post("/api/jobs/backfill-descriptions", tags=["triggers"], summary="Fetch descriptions for jobs missing them", status_code=202)
async def trigger_backfill_descriptions():
    """Fetch job descriptions for saved/new jobs that have a URL but no description."""
    async def _do():
        from backend.models.db import Job
        from backend.scraper.ats._descriptions import _fetch_job_description
        from backend.analyzer.salary_extractor import apply_salary_to_job
        db = SessionLocal()
        try:
            jobs = db.query(Job).filter(
                Job.status.in_(["new", "saved"]),
                Job.url != None,
                (Job.description == None) | (Job.description == ""),
            ).order_by(Job.discovered_at.desc()).limit(50).all()

            logger.info(f"Backfill descriptions: {len(jobs)} jobs to process")
            import asyncio
            count = 0
            for job in jobs:
                try:
                    desc = await _fetch_job_description(job.url)
                    if desc and len(desc) > 50:
                        job.description = desc
                        apply_salary_to_job(job)
                        count += 1
                        db.commit()
                        logger.info(f"Backfilled description for '{job.title}' ({len(desc)} chars)")
                except Exception as e:
                    logger.warning(f"Failed to fetch description for '{job.title}': {e}")
                await asyncio.sleep(1)

            logger.info(f"Backfill descriptions: done, {count}/{len(jobs)} updated")
        finally:
            db.close()

    try:
        run_id = launch_background("backfill_descriptions", _do, trigger="manual")
        return {"run_id": run_id, "status": "running"}
    except JobAlreadyRunningError as e:
        logger.info("Duplicate trigger rejected for job_type=%s", e.job_type)
        return JSONResponse(
            status_code=409,
            content={"detail": f"{e.job_type} is already running"},
        )


@app.post("/api/db/backup", tags=["triggers"], summary="Run database backup", status_code=202)
async def trigger_db_backup():
    """Run a database backup immediately. Returns immediately with a run_id."""
    async def _do():
        import subprocess, glob, os
        from datetime import datetime
        from backend.config import DATABASE_URL
        from urllib.parse import urlparse

        backup_dir = "/app/backups"
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"{backup_dir}/jobnavigator_{timestamp}.sql"

        parsed = urlparse(DATABASE_URL)
        env = os.environ.copy()
        env["PGPASSWORD"] = parsed.password or ""

        result = subprocess.run(
            ["pg_dump", "-h", parsed.hostname, "-p", str(parsed.port or 5432),
             "-U", parsed.username, "-d", parsed.path.lstrip("/"),
             "-f", backup_file],
            env=env, capture_output=True, text=True, timeout=300
        )
        if result.returncode != 0:
            raise RuntimeError(f"pg_dump failed: {result.stderr}")

        # Keep only last 5 backups
        backups = sorted(glob.glob(f"{backup_dir}/jobnavigator_*.sql"))
        while len(backups) > 5:
            os.remove(backups.pop(0))

    try:
        run_id = launch_background("db_backup", _do, trigger="manual")
        return {"run_id": run_id, "status": "running"}
    except JobAlreadyRunningError as e:
        logger.info("Duplicate trigger rejected for job_type=%s", e.job_type)
        return JSONResponse(
            status_code=409,
            content={"detail": f"{e.job_type} is already running"},
        )


@app.post("/api/telegram/digest", tags=["triggers"], summary="Send Telegram digest", status_code=202)
async def trigger_digest():
    """Send the daily Telegram digest immediately. Returns immediately with a run_id."""
    async def _do():
        from backend.notifier.telegram import send_digest
        await send_digest()

    try:
        run_id = launch_background("daily_digest", _do, trigger="manual")
        return {"run_id": run_id, "status": "running"}
    except JobAlreadyRunningError as e:
        logger.info("Duplicate trigger rejected for job_type=%s", e.job_type)
        return JSONResponse(
            status_code=409,
            content={"detail": f"{e.job_type} is already running"},
        )


@app.post("/api/scrape/company/{company_id}", tags=["triggers"], summary="Scrape a single company", status_code=202)
async def trigger_company_scrape(company_id: str, auto_score: bool = None):
    """Run Playwright career page scrape for one company. Returns immediately with a run_id.
    auto_score: True/False override, null=use company.auto_scoring_depth setting.
    """
    from backend.models.db import Company
    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.id == company_id).first()
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        company_name = company.name
    finally:
        db.close()

    async def _do():
        from backend.models.db import Company as C
        from backend.scraper.sources.company_pages import scrape_single_career_page
        db2 = SessionLocal()
        try:
            c = db2.query(C).filter(C.id == company_id).first()
            if c:
                result = await scrape_single_career_page(c)
                should_score = auto_score if auto_score is not None else (c.auto_scoring_depth in ("light", "full"))
                if should_score and result and result.get("new_jobs", 0) > 0:
                    from backend.analyzer.cv_scorer import analyze_unscored_jobs
                    await analyze_unscored_jobs(status="new")
        finally:
            db2.close()

    try:
        run_id = launch_background("company_scrape", _do, trigger="manual", scope_key=company_id, meta={"company": company_name})
        return {"run_id": run_id, "status": "running", "company": company_name}
    except JobAlreadyRunningError as e:
        logger.info("Duplicate trigger rejected for job_type=%s", e.job_type)
        return JSONResponse(
            status_code=409,
            content={"detail": f"{e.job_type} is already running"},
        )


@app.post("/api/telegram/webhook", tags=["telegram"], summary="Telegram webhook")
async def telegram_webhook(update: dict):
    """Handle incoming Telegram bot updates (callback queries from inline buttons).
    This is called by Telegram's webhook system, not manually.

    **Payload:** Raw Telegram Update object (see Telegram Bot API docs).
    """
    from backend.notifier.telegram import handle_callback

    callback_query = update.get("callback_query")
    if callback_query:
        data = callback_query.get("data", "")
        message_id = callback_query.get("message", {}).get("message_id")
        result = await handle_callback(data, message_id)

        # Answer callback to remove loading state
        callback_id = callback_query.get("id")
        if callback_id and TELEGRAM_BOT_TOKEN:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery",
                    json={"callback_query_id": callback_id, "text": result},
                )

    return {"ok": True}


@app.post("/api/telegram/test", tags=["telegram"], summary="Send test message", status_code=202)
async def telegram_test():
    """Send a test message to the configured Telegram chat. Returns immediately with a run_id."""
    async def _do():
        from backend.notifier.telegram import send_test_message
        await send_test_message()

    try:
        run_id = launch_background("telegram_test", _do, trigger="manual")
        return {"run_id": run_id, "status": "running"}
    except JobAlreadyRunningError as e:
        logger.info("Duplicate trigger rejected for job_type=%s", e.job_type)
        return JSONResponse(
            status_code=409,
            content={"detail": f"{e.job_type} is already running"},
        )


@app.get("/api/scheduler/jobs", tags=["scheduler"], summary="List scheduled jobs")
def get_scheduler_jobs():
    """Return all scheduler jobs with their schedule, next run time (UTC), trigger URL, and running state."""
    from backend.scheduler import scheduler, get_setting
    from backend.models.db import Company

    # Map scheduler job IDs to (trigger_url, job_type for monitor)
    job_map = {
        "scrape_all": ("/scrape/run-all", "scrape_all"),
        "email_check": ("/email/check-now", "email_check"),
        "daily_digest": ("/telegram/digest", "daily_digest"),
        "h1b_refresh": ("/h1b/refresh", "h1b_refresh"),
        "db_backup": ("/db/backup", "db_backup"),
        "job_cleanup": ("/db/cleanup", "job_cleanup"),
        "auto_reject": ("/auto-reject/run", "auto_reject"),
    }

    jobs = scheduler.get_jobs()
    result = []
    for job in jobs:
        trigger = job.trigger
        if hasattr(trigger, 'interval'):
            schedule = f"Every {int(trigger.interval.total_seconds() / 60)} min"
        elif hasattr(trigger, 'fields'):
            fields = {f.name: str(f) for f in trigger.fields}
            minute = fields.get('minute', '*')
            hour = fields.get('hour', '*')
            day = fields.get('day', '*')
            month = fields.get('month', '*')
            dow = fields.get('day_of_week', '*')
            schedule = f"{minute} {hour} {day} {month} {dow}"
        else:
            schedule = str(trigger)

        trigger_url, job_type = job_map.get(job.id, (None, None))
        running_info = _get_running_by_job_type(job_type) if job_type else None

        result.append({
            "id": job.id,
            "name": job.name or job.id,
            "schedule": schedule,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "pending": job.pending,
            "trigger_url": trigger_url,
            "running": running_info,
        })

    # Per-search and per-company custom scrape intervals
    db = SessionLocal()
    try:
        from backend.models.db import Search
        searches = db.query(Search).filter(
            Search.active == True,
            Search.run_interval_minutes != None,
            Search.run_interval_minutes > 0,
        ).all()
        for s in searches:
            next_run = None
            if s.last_run_at:
                from datetime import timedelta
                next_run = (s.last_run_at + timedelta(minutes=s.run_interval_minutes)).isoformat()
            result.append({
                "id": f"search_{s.id}",
                "name": f"Search: {s.name}",
                "schedule": f"Every {s.run_interval_minutes} min (search override)",
                "next_run": next_run,
                "pending": False,
                "trigger_url": f"/scrape/search/{s.id}",
                "running": None,
            })

        companies = db.query(Company).filter(
            Company.active == True,
            Company.scrape_interval_minutes != None,
        ).all()
        for c in companies:
            next_run = None
            if c.last_scraped_at:
                from datetime import timedelta
                next_run = (c.last_scraped_at + timedelta(minutes=c.scrape_interval_minutes)).isoformat()
            company_running = is_running("company_scrape", str(c.id))
            running_info = None
            if company_running:
                from datetime import datetime, timezone
                elapsed = (datetime.now(timezone.utc) - company_running.started_at).total_seconds()
                running_info = {"run_id": str(company_running.run_id), "elapsed_seconds": round(elapsed, 1)}
            result.append({
                "id": f"company_{c.id}",
                "name": f"Scrape: {c.name}",
                "schedule": f"Every {c.scrape_interval_minutes} min (company override)",
                "next_run": next_run,
                "pending": False,
                "trigger_url": f"/scrape/company/{c.id}",
                "running": running_info,
            })
    finally:
        db.close()

    return result


# ── Monitor endpoints ────────────────────────────────────────────────────────
@app.get("/api/monitor/active", tags=["monitor"], summary="Currently running jobs")
def get_active_jobs():
    """Return all currently running jobs with elapsed time in seconds."""
    return get_all_running()


@app.get("/api/monitor/history", tags=["monitor"], summary="Run history")
def get_run_history(limit: int = 30, job_type: str = None, status: str = None):
    """Return recent job run history, newest first."""
    db = SessionLocal()
    try:
        q = db.query(JobRun)
        if job_type:
            q = q.filter(JobRun.job_type == job_type)
        if status:
            q = q.filter(JobRun.status == status)
        runs = q.order_by(JobRun.started_at.desc()).limit(limit).all()
        return [
            {
                "id": str(r.id),
                "job_type": r.job_type,
                "trigger": r.trigger,
                "status": r.status,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                "duration_seconds": r.duration_seconds,
                "result_summary": r.result_summary,
                "error": r.error,
                "meta": r.meta,
            }
            for r in runs
        ]
    finally:
        db.close()


@app.get("/api/monitor/run/{run_id}", tags=["monitor"], summary="Single run details")
def get_run_detail(run_id: str):
    """Return details for a single job run."""
    db = SessionLocal()
    try:
        r = db.query(JobRun).filter(JobRun.id == run_id).first()
        if not r:
            raise HTTPException(status_code=404, detail="Run not found")
        return {
            "id": str(r.id),
            "job_type": r.job_type,
            "trigger": r.trigger,
            "status": r.status,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "duration_seconds": r.duration_seconds,
            "result_summary": r.result_summary,
            "error": r.error,
            "meta": r.meta,
        }
    finally:
        db.close()


@app.get("/api/activity-log", tags=["scheduler"], summary="Activity log")
def get_activity_log(
    limit: int = 50,
    type: str = None,
    company: str = None,
):
    """Recent activity log entries across all subsystems.

    **Types:** `scrape`, `h1b`, `cv_score`, `email`, `telegram`

    **Filters:**
    - `type` — exact match on activity type
    - `company` — case-insensitive substring match on company name
    - `limit` — max entries to return (default 50)
    """
    from backend.models.db import ActivityLog
    db = SessionLocal()
    try:
        q = db.query(ActivityLog)
        if type:
            q = q.filter(ActivityLog.type == type)
        if company:
            q = q.filter(ActivityLog.company.ilike(f"%{company}%"))
        logs = q.order_by(ActivityLog.created_at.desc()).limit(limit).all()
        return [
            {
                "id": str(log.id),
                "type": log.type,
                "message": log.message,
                "company": log.company,
                "details": log.details,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ]
    finally:
        db.close()


@app.get("/api/scrape-log", tags=["stats"], summary="Scrape log history")
def get_scrape_log(
    limit: int = 50,
    errors_only: bool = False,
    warnings_only: bool = False,
):
    """Raw scrape run history with per-search/company details.

    Each entry includes: source, jobs_found, new_jobs, error, duration.

    **Filters:**
    - `errors_only` — only show runs that had errors
    - `warnings_only` — only show runs with 0 results (warnings)
    """
    from backend.models.db import ScrapeLog
    db = SessionLocal()
    try:
        q = db.query(ScrapeLog)
        if errors_only:
            q = q.filter(ScrapeLog.error != None)
        elif warnings_only:
            q = q.filter(ScrapeLog.is_warning == True)
        logs = q.order_by(ScrapeLog.ran_at.desc()).limit(limit).all()
        return [
            {
                "id": str(log.id),
                "search_id": str(log.search_id) if log.search_id else None,
                "company_id": str(log.company_id) if log.company_id else None,
                "source": log.source,
                "jobs_found": log.jobs_found,
                "new_jobs": log.new_jobs,
                "error": log.error,
                "is_warning": log.is_warning,
                "duration_seconds": log.duration_seconds,
                "ran_at": log.ran_at.isoformat() if log.ran_at else None,
            }
            for log in logs
        ]
    finally:
        db.close()


@app.get("/api/stats/timeline", tags=["stats"], summary="Job discovery timeline")
def get_stats_timeline(days: int = 30):
    """Daily job counts for the last N days."""
    from backend.models.db import Job
    from sqlalchemy import func, cast, Date
    from datetime import datetime, timedelta, timezone

    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        rows = db.query(
            cast(Job.discovered_at, Date).label("date"),
            func.count().label("total"),
            func.count().filter(Job.status == "saved").label("saved"),
            func.count().filter(Job.status == "applied").label("applied"),
        ).filter(Job.discovered_at >= cutoff).group_by(
            cast(Job.discovered_at, Date)
        ).order_by(cast(Job.discovered_at, Date)).all()
        return [{"date": str(r.date), "total": r.total, "saved": r.saved, "applied": r.applied} for r in rows]
    finally:
        db.close()


@app.get("/api/stats/score-distribution", tags=["stats"], summary="CV score distribution")
def get_score_distribution():
    """Distribution of best CV scores across all scored jobs."""
    from backend.models.db import Job

    db = SessionLocal()
    try:
        jobs = db.query(Job).filter(Job.cv_scores != None).all()
        buckets = {"0-20": 0, "21-40": 0, "41-60": 0, "61-80": 0, "81-100": 0}
        for job in jobs:
            scores = job.cv_scores or {}
            if not isinstance(scores, dict):
                continue
            numeric = [v for v in scores.values() if isinstance(v, (int, float))]
            if not numeric:
                continue
            best = max(numeric)
            if best <= 20:
                buckets["0-20"] += 1
            elif best <= 40:
                buckets["21-40"] += 1
            elif best <= 60:
                buckets["41-60"] += 1
            elif best <= 80:
                buckets["61-80"] += 1
            else:
                buckets["81-100"] += 1
        return [{"range": k, "count": v} for k, v in buckets.items()]
    finally:
        db.close()


@app.get("/api/stats/sankey", tags=["stats"], summary="Application flow data for Sankey diagram")
def get_stats_sankey():
    """Return status transition flows aggregated across all applications."""
    from backend.models.db import Application
    db = SessionLocal()
    try:
        apps = db.query(Application).filter(Application.status_transitions != None).all()
        flows = {}  # (from, to) -> count
        for app in apps:
            transitions = app.status_transitions or []
            for t in transitions:
                fr = t.get("from") or "new"
                to = t.get("to", "")
                if to:
                    key = (fr, to)
                    flows[key] = flows.get(key, 0) + 1
        return [{"source": k[0], "target": k[1], "value": v} for k, v in flows.items()]
    finally:
        db.close()


# ── LLM cost stats ───────────────────────────────────────────────────────────

def _llm_costs_stats(days: int = 7) -> dict:
    """Aggregate llm_call_log rows within the last `days` days."""
    from datetime import datetime, timedelta, timezone
    from backend.models.db import LlmCallLog

    since = datetime.now(timezone.utc) - timedelta(days=days)
    db = SessionLocal()
    try:
        q = db.query(LlmCallLog).filter(LlmCallLog.created_at >= since)
        rows = q.all()

        total_cost = sum(r.cost_usd or 0 for r in rows)
        total_calls = len(rows)

        # Group by (purpose, provider, model)
        groups = {}
        for r in rows:
            key = (r.purpose, r.provider, r.model)
            g = groups.setdefault(key, {
                "purpose": r.purpose,
                "provider": r.provider or "",
                "model": r.model,
                "calls": 0,
                "cost_usd": 0.0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_read_tokens": 0,
                "cache_write_tokens": 0,
                "cache_involving": 0,
                "cache_hits": 0,
            })
            g["calls"] += 1
            g["cost_usd"] += r.cost_usd or 0
            g["input_tokens"] += r.input_tokens or 0
            g["output_tokens"] += r.output_tokens or 0
            g["cache_read_tokens"] += r.cache_read_tokens or 0
            g["cache_write_tokens"] += r.cache_write_tokens or 0
            if (r.cache_read_tokens or 0) > 0 or (r.cache_write_tokens or 0) > 0:
                g["cache_involving"] += 1
            if (r.cache_read_tokens or 0) > 0:
                g["cache_hits"] += 1

        by_purpose = []
        for g in groups.values():
            g["cache_hit_ratio"] = (
                g["cache_hits"] / g["cache_involving"] if g["cache_involving"] > 0 else 0.0
            )
            by_purpose.append(g)

        return {
            "window_days": days,
            "total_calls": total_calls,
            "total_cost_usd": round(total_cost, 6),
            "by_purpose": sorted(by_purpose, key=lambda x: -x["cost_usd"]),
        }
    finally:
        db.close()


@app.get("/api/stats/llm-costs", tags=["stats"], summary="LLM cost + cache hit stats")
async def llm_costs(days: int = 7):
    """Returns spend and cache hit rate aggregated by (purpose, model) for the last N days."""
    return _llm_costs_stats(days=days)


@app.get("/api/stats", tags=["stats"], summary="Dashboard statistics")
def get_stats():
    """Aggregate counts: total jobs, new jobs, saved jobs, total applications,
    application status breakdown, and response rate percentage.
    """
    from backend.models.db import Job, Application
    from sqlalchemy import func
    db = SessionLocal()
    try:
        total_jobs = db.query(Job).count()
        new_jobs = db.query(Job).filter(Job.status == "new").count()
        saved_jobs = db.query(Job).filter(Job.status == "saved").count()
        total_apps = db.query(Application).count()

        status_counts = {}
        for status, count in db.query(Application.status, func.count()).group_by(Application.status).all():
            status_counts[status] = count

        return {
            "total_jobs": total_jobs,
            "new_jobs": new_jobs,
            "saved_jobs": saved_jobs,
            "total_applications": total_apps,
            "application_statuses": status_counts,
            "response_rate": (
                round((status_counts.get("screening", 0) + status_counts.get("phone_screen", 0) +
                       status_counts.get("interview", 0) + status_counts.get("final_round", 0) +
                       status_counts.get("offer", 0) + status_counts.get("rejected", 0)) /
                      total_apps * 100, 1) if total_apps > 0 else 0
            ),
        }
    finally:
        db.close()
