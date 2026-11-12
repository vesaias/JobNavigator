"""FastAPI entry point for JobNavigator."""
import logging
from contextlib import asynccontextmanager
from typing import Annotated, Optional

from fastapi import Depends, FastAPI, Query, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from backend.models.db import create_tables, SessionLocal, JobRun
from backend.accounts.settings import get_install_setting, install_row, put_setting
from backend.seed import run_seeds
from backend.config import INITIAL_API_KEY, TELEGRAM_BOT_TOKEN
from backend.job_monitor import launch_background, JobAlreadyRunningError, get_all_running, is_running, _get_running_by_job_type, cleanup_stale_runs, sanitize_run_error

from backend.api.routes_settings import router as settings_router
from backend.api.routes_jobs import router as jobs_router
from backend.api.routes_applications import router as applications_router
from backend.api.routes_companies import router as companies_router
from backend.api.routes_searches import router as searches_router
from backend.api.routes_resumes import router as resumes_router
from backend.api.routes_persona import router as persona_router
from backend.api.routes_cover_letters import router as cover_letters_router
from backend.api.routes_linkedin import router as linkedin_router
from backend.api.routes_telemetry import router as telemetry_router
from backend.api.routes_updates import router as updates_router
from backend.api.routes_autofill import router as autofill_router
from backend.api.routes_llm import router as llm_router
from backend.api.routes_accounts import router as accounts_router
from backend.api.routes_gmail import router as gmail_router
from backend.scraper._shared.link_kinds import job_link

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("jobnavigator")

# httpx logs every request URL at INFO, and the Telegram API carries the bot token in
# the path — so each alert wrote the token into the container log in cleartext
# (R4-T5-03). The app logs its own outcomes for every outbound call it cares about.
for _noisy in ("httpx", "httpcore"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create tables, seed data, start scheduler."""
    logger.info("Starting JobNavigator backend...")
    # First, so the line is in the log even if the migration below fails: code
    # pulled without pulling or rebuilding the image runs in the old image.
    from backend.image_check import log_image_status
    log_image_status()
    # Before ANY migration: a release change backs the database up first, and a
    # failed backup stops startup here (upgrade_backup.py; JN_SKIP_UPGRADE_BACKUP=1 skips).
    from backend.upgrade_backup import prepare_upgrade, mark_booted
    prepare_upgrade()
    # Boot DDL waits for locks without the app's lock_timeout (S2-01): a restart during
    # a long pg_dump must wait for it, not fail.
    from backend.models.db import lock_timeout_exempt
    with lock_timeout_exempt():
        create_tables()
        run_seeds()

    # Set initial API key if dashboard_api_key is empty
    db = SessionLocal()
    try:
        setting = install_row(db, "dashboard_api_key")
        if setting and not setting.value:
            setting.value = INITIAL_API_KEY
            db.commit()
    finally:
        db.close()

    # Clean up stale job runs from previous process (every account's: system code)
    from backend.accounts.context import unscoped
    with unscoped():
        cleanup_stale_runs()

    # Start scheduler
    from backend.scheduler import scheduler, configure_scheduler, scheduler_disabled
    if scheduler_disabled():
        # QA F9 / T2-01: JN_SCHEDULER_DISABLED=1 for throwaway/staging copies of real data.
        logger.warning("JN_SCHEDULER_DISABLED is set: the scheduler is NOT started "
                       "(no scrapes, email checks, digests or backups run).")
    else:
        configure_scheduler()
        # The LinkedIn employer-link lookup runs after every scrape, not on a clock.
        from backend.job_monitor import on_scrape_finished
        from backend.scheduler import lookup_after_scrape
        on_scrape_finished(lookup_after_scrape)
        # QA F4 / R1-01: the scheduler's timers capture the context of whoever wakes it.
        from backend.accounts.context import run_in_clean_context
        run_in_clean_context(scheduler.start)
        # Telemetry's start event (sends nothing unless the owner allowed it); kept on
        # app.state so the task is not garbage-collected mid-send.
        from backend.telemetry.umami import send_start
        import asyncio as _asyncio
        app.state.telemetry_start = run_in_clean_context(lambda: _asyncio.ensure_future(send_start()))
        logger.info("Database initialized, seeded, scheduler started.")

    # Warm the OpenRouter live-pricing cache used for LLM cost logging (non-fatal).
    try:
        from backend.analyzer.llm_cost import refresh_openrouter_prices
        await refresh_openrouter_prices(force=True)
    except Exception as e:
        logger.warning(f"OpenRouter price warmup failed: {e}")

    # Booted: the database is on this release now (install-level marker, see upgrade_backup.py).
    try:
        mark_booted()
    except Exception as e:  # the next boot then backs up once more; not worth failing over
        logger.warning(f"Could not record the release marker: {e}")

    from backend.runner_management import coordinator, enabled as runner_management_enabled
    if runner_management_enabled():
        coordinator.start()
    try:
        yield
    finally:
        await coordinator.stop()

    if scheduler.running:
        scheduler.shutdown()
    logger.info("Shutting down JobNavigator backend...")


OPENAPI_TAGS = [
    {"name": "triggers", "description": "Manual trigger endpoints - run scrapes, analysis, email checks, etc. on demand"},
    {"name": "scheduler", "description": "View scheduled jobs and activity log"},
    {"name": "stats", "description": "Aggregate statistics and scrape history"},
    {"name": "settings", "description": "Global settings (key-value store)"},
    {"name": "searches", "description": "Search configurations for JobSpy board scraping"},
    {"name": "companies", "description": "Company management - scrape URLs, Resume selection, H-1B data, filters"},
    {"name": "jobs", "description": "Job listings discovered by scrapers"},
    {"name": "applications", "description": "Job applications tracked by Chrome extension and email monitor"},
    {"name": "telegram", "description": "Telegram bot webhook and test endpoints"},
    {"name": "monitor", "description": "Job execution monitoring — active runs, run history"},
    {"name": "system", "description": "Health check and system info"},
]

from backend.version import APP_VERSION  # noqa: E402 — released version (major.minor); Settings and /health

app = FastAPI(
    title="JobNavigator API",
    version=APP_VERSION,
    description=(
        "Personal job hunt automation system. Scrapes job boards and career pages, "
        "scores jobs against resumes using Claude API, monitors Gmail for responses, "
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


# ── DB pool saturation → 503, fast ───────────────────────────────────────────
# The engine's pool_timeout is short (5 s) so a drained pool fails instead of
# hanging. Both surfaces of that failure answer the same way: a 503 with
# Retry-After, never a 30 s stall or a stack trace.
from sqlalchemy.exc import TimeoutError as _PoolTimeout


def _pool_busy_response() -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"detail": "Database is busy, retry shortly"},
        headers={"Retry-After": "5"},
    )


# ── API Key auth middleware ──────────────────────────────────────────────────
# MT-10: install password (X-API-Key header or jn_session cookie), then the account
# (signed X-Account-Token header, else the signed jn_account cookie, else the owner when
# the install has one account, else 401 account_required; a bad token is 401
# invalid_account_token). The rules, the cookie and the token format are documented in
# backend/accounts/auth.py.
import hmac as _hmac_mw
from backend.accounts.context import owner_context, owner_unlocked, use_account, is_unscoped
from backend.accounts import auth as acct_auth

# Paths that NEVER require auth (exact or prefix match)
_PUBLIC_PREFIXES = ("/health", "/docs", "/openapi.json", "/redoc", "/cv", "/api/telegram/webhook", "/api/auth/set-session", "/api/auth/verify", "/api/auth/logout",
                    "/api/gmail/callback")  # Google redirects the browser there (MT-19; signed state)
# Need the install password but no account (the picker reads and calls these).
_ACCOUNT_OPTIONAL = ("/api/auth/accounts", "/api/auth/switch", "/api/auth/verify-pin")


def _account_required_response(detail: str, clear_cookie: bool = False) -> JSONResponse:
    headers = {acct_auth.AUTH_HEADER: "account"} if detail == acct_auth.ACCOUNT_REQUIRED else None
    resp = JSONResponse(status_code=401, content={"detail": detail}, headers=headers)
    if clear_cookie:
        # QA F3 / R2-03: a stale jn_account (removed account, changed PIN) is dropped.
        acct_auth.clear_account_cookie(resp)
    return resp


def _secret_eq(given, expected) -> bool:
    """Constant-time compare that never raises: `hmac.compare_digest(str, str)` raises
    TypeError on non-ASCII text (a latin-1 header or cookie byte, QA F3 / R2-07), so both
    sides are compared as UTF-8 bytes; anything that is not a string is not the secret."""
    if not isinstance(given, str) or not isinstance(expected, str):
        return False
    return _hmac_mw.compare_digest(given.encode("utf-8", "surrogatepass"),
                                   expected.encode("utf-8", "surrogatepass"))


@app.middleware("http")
async def api_key_auth(request: Request, call_next):
    return await _api_key_auth(request, call_next)


async def _as_owner(request: Request, call_next):
    with owner_context():
        return await call_next(request)


async def _api_key_auth(request: Request, call_next):
    path = request.url.path

    # Let CORS preflight requests pass through so CORSMiddleware can respond
    if request.method == "OPTIONS":
        return await _as_owner(request, call_next)

    # Public endpoints (they resolve their own rows: tracer tokens are looked up unscoped)
    if any(path == p or path.startswith(p + "/") or path == p.rstrip("/") for p in _PUBLIC_PREFIXES):
        return await _as_owner(request, call_next)
    # docs subpaths
    if path.startswith("/docs"):
        return await _as_owner(request, call_next)
    # Param-style tracer links (?cv=token on root) are public, same as /cv/{token}.
    if path == "/" and request.query_params.get("cv"):
        return await _as_owner(request, call_next)

    # Accept either X-API-Key header (API clients, extension) OR jn_session cookie (browser)
    header_key = request.headers.get("X-API-Key", "")
    api_key = header_key or request.cookies.get("jn_session", "")

    # QA F4 / R1-11: the key check, the account lookup and the last-active write are
    # blocking DB calls; they run in the threadpool (which copies the context), so a
    # slow DB or a pool wait stalls this request only, not the event loop.
    early, res = await run_in_threadpool(
        _authenticate_sync, path, api_key,
        request.headers.get(acct_auth.TOKEN_HEADER, ""),
        request.cookies.get(acct_auth.COOKIE_NAME, ""))
    if early is not None:
        return early

    optional = path in _ACCOUNT_OPTIONAL
    if res is not None and res.error and not (optional and res.error == acct_auth.ACCOUNT_REQUIRED):
        return _account_required_response(res.error, clear_cookie=res.clear_cookie)
    if res is None or res.account is None:
        request.state.account_id = None
        request.state.owner_unlocked_until = 0
        request.state.owner_unlock_id = None
        return await _as_owner(request, call_next)
    request.state.account_id = res.account["id"]
    request.state.owner_unlocked_until = res.unlocked_until
    request.state.owner_unlock_id = res.unlock_id
    acc_id = str(res.account["id"])
    changed = _account_changed_response(request, path, res.account, acc_id)
    if changed is not None:
        return changed
    unlocked = bool(res.unlocked_until) and res.unlocked_until > acct_auth._now()
    with use_account(res.account["id"]), owner_unlocked(unlocked):
        resp = await call_next(request)
    resp.headers[acct_auth.ACCOUNT_HEADER] = acc_id
    return resp


# QA F7 / R6-01: writes from a tab that still shows another account. The switch itself
# (and the PIN check before it) is how a tab changes account, so it is never refused.
_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_EXPECT_EXEMPT = ("/api/auth/switch", "/api/auth/verify-pin", "/api/auth/logout")


def _account_changed_response(request: Request, path: str, account: dict, acc_id: str):
    """409 `account_changed` when a write names an expected account that is not the one
    this request resolved to; None otherwise (no header, a read, or the switch)."""
    if request.method not in _WRITE_METHODS or path in _EXPECT_EXEMPT:
        return None
    expected = request.headers.get(acct_auth.EXPECTED_ACCOUNT_HEADER, "").strip().lower()
    if not expected or expected == acc_id.lower():
        return None
    logger.info("refused a %s %s from a tab loaded for another account", request.method, path)
    return JSONResponse(
        status_code=409,
        content={"detail": acct_auth.ACCOUNT_CHANGED,
                 "account": {"id": acc_id, "name": account.get("name") or ""}},
        headers={acct_auth.ACCOUNT_HEADER: acc_id})


def _authenticate_sync(path: str, api_key: str, token: str, cookie: str):
    """(early response or None, account resolution or None). Runs in the threadpool."""
    # A middleware runs outside FastAPI's exception handlers, so a pool timeout
    # here would surface as a bare connection error, not a status code. The
    # connection is acquired lazily by the query, not by SessionLocal().
    db = SessionLocal()
    try:
        try:
            expected = get_install_setting(db, "dashboard_api_key", INITIAL_API_KEY)
        except _PoolTimeout:
            logger.warning("DB pool exhausted while authenticating %s", path)
            return _pool_busy_response(), None
        # First-run: no key configured → allow everything
        if not expected:
            # WARNING-level so operators see this in logs when they shouldn't (e.g.,
            # dashboard_api_key setting cleared by a botched DB restore).
            logger.warning(
                "api key BYPASS (first-run mode): path=%s — dashboard_api_key setting is empty",
                path,
            )
        else:
            # Key configured → require match (timing-safe compare)
            if not api_key:
                return JSONResponse(status_code=401, content={"detail": "API key required"}), None
            if not _secret_eq(api_key, expected):
                return JSONResponse(status_code=401, content={"detail": "Invalid API key"}), None

        # Tests that drive the app on their own throwaway engine run unscoped (system
        # context); production requests never arrive unscoped.
        if is_unscoped():
            return None, None
        try:
            # QA F1 (R2-01): the signed X-Account-Token, else the jn_account cookie,
            # else the one-account owner. A bare X-Account header is never read.
            res = acct_auth.resolve_request(db, token, cookie)
        except _PoolTimeout:
            logger.warning("DB pool exhausted while resolving the account for %s", path)
            return _pool_busy_response(), None
        if res is not None and res.account is not None:
            # MT-11: at most one UPDATE per account per minute (in-memory throttle).
            acct_auth.touch_last_active(db, res.account["id"])
        return None, res
    finally:
        db.close()


# ── Auth endpoints (cookie session) ──────────────────────────────────────────
import hmac as _hmac
import time as _time
from fastapi import Response as _Response

# ── Brute-force throttle for the two unauthenticated auth endpoints ──────────
# They answered 401 at ~276 req/s with no delay and no lockout (R4-T5-06). In-memory
# per-IP failure counter: N failures inside the window → 429 + Retry-After; a
# successful verify clears the bucket. Process-local by design (single-user app,
# one backend process) — a restart forgives everything, which is fine.
_AUTH_FAIL_LIMIT = 10
_AUTH_FAIL_WINDOW = 60.0
_auth_failures: dict[str, list[float]] = {}


def _auth_client_ip(request: Request) -> str:
    """Caller IP. Through Caddy every browser request has the proxy's IP as the peer,
    so prefer the forwarded client address — otherwise one LAN attacker would lock
    out the dashboard itself."""
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        first = fwd.split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client else "unknown"


def _auth_throttle(request: Request) -> None:
    """Raise 429 with Retry-After while this IP is over the failure budget."""
    ip = _auth_client_ip(request)
    now = _time.monotonic()
    hits = [t for t in _auth_failures.get(ip, []) if now - t < _AUTH_FAIL_WINDOW]
    if hits:
        _auth_failures[ip] = hits
    else:
        _auth_failures.pop(ip, None)
    if len(hits) >= _AUTH_FAIL_LIMIT:
        retry_after = max(1, int(_AUTH_FAIL_WINDOW - (now - hits[0])) + 1)
        logger.warning("auth throttle: %s locked out for %ss", ip, retry_after)
        raise HTTPException(
            status_code=429, detail="Too many failed attempts",
            headers={"Retry-After": str(retry_after)},
        )


def _auth_record_failure(request: Request) -> None:
    _auth_failures.setdefault(_auth_client_ip(request), []).append(_time.monotonic())


def _auth_clear_failures(request: Request) -> None:
    _auth_failures.pop(_auth_client_ip(request), None)


def _reset_auth_throttle() -> None:
    """Drop every bucket (tests, and a manual unlock)."""
    _auth_failures.clear()


@app.post("/api/auth/verify", tags=["auth"], summary="Verify an API key without setting a session")
async def verify_api_key(body: dict, request: Request):
    """Validate API key. Returns 200 {ok: true} on match, 401 otherwise, 429 after too many failures from one IP."""
    _auth_throttle(request)
    # hmac.compare_digest() raises TypeError on a non-string, and this endpoint is
    # unauthenticated — anything that is not a string is simply not the key
    # (R4-T1-24).
    api_key = (body or {}).get("api_key", "")
    if not isinstance(api_key, str):
        api_key = ""
    db = SessionLocal()
    try:
        expected = get_install_setting(db, "dashboard_api_key", INITIAL_API_KEY)
        if not expected:
            return {"ok": True, "first_run": True}
        if not api_key or not _secret_eq(api_key, expected):
            _auth_record_failure(request)
            raise HTTPException(status_code=401, detail="Invalid API key")
        _auth_clear_failures(request)
        return {"ok": True, "first_run": False}
    finally:
        db.close()


@app.post("/api/auth/set-session", tags=["auth"], summary="Set session cookie from API key")
async def set_session(body: dict, response: _Response, request: Request):
    """Verify API key and set httpOnly jn_session cookie (also sent on iframe/download requests); 429 after too many failures from one IP."""
    _auth_throttle(request)
    # hmac.compare_digest() raises TypeError on a non-string, and this endpoint is
    # unauthenticated — anything that is not a string is simply not the key
    # (R4-T1-24).
    api_key = (body or {}).get("api_key", "")
    if not isinstance(api_key, str):
        api_key = ""
    db = SessionLocal()
    try:
        expected = get_install_setting(db, "dashboard_api_key", INITIAL_API_KEY)
        if expected and (not api_key or not _secret_eq(api_key, expected)):
            _auth_record_failure(request)
            raise HTTPException(status_code=401, detail="Invalid API key")
        _auth_clear_failures(request)
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
async def logout(request: Request, response: _Response):
    """Clear the install session cookie and this browser's account cookie (ending its owner unlock)."""
    _revoke_cookie_unlock(request)
    response.delete_cookie(key="jn_session", samesite="strict", httponly=True)
    acct_auth.clear_account_cookie(response)
    return {"ok": True}


# ── Accounts: picker, switch, owner unlock (MT-10) ───────────────────────────
from datetime import datetime as _dt_auth, timezone as _tz_auth


def _switch_denied(e: "acct_auth.SwitchDenied") -> JSONResponse:
    content = {"detail": e.detail}
    if e.tries_left is not None:
        content["tries_left"] = e.tries_left
    headers = {"Retry-After": str(e.retry_after)} if e.retry_after else None
    return JSONResponse(status_code=e.status, content=content, headers=headers)


def _epoch_iso(ts) -> Optional[str]:
    return _dt_auth.fromtimestamp(ts, _tz_auth.utc).isoformat() if ts else None


def _revoke_cookie_unlock(request: Request) -> None:
    """QA F3 / R2-06: end the owner unlock carried by this browser's jn_account cookie
    (Lock, switching away, logout), so a copy of the old value no longer unlocks."""
    value = request.cookies.get(acct_auth.COOKIE_NAME)
    if not value:
        return
    db = SessionLocal()
    try:
        acct_auth.revoke_cookie_unlock(db, value)
    finally:
        db.close()


@app.get("/api/auth/accounts", tags=["auth"], summary="Accounts for the picker")
def auth_accounts():
    """Every account as {id, name, color, role, has_pin}, owner first; nothing else. Needs the install password but no account."""
    db = SessionLocal()
    try:
        return [acct_auth.public_account(a) for a in acct_auth.load_accounts(db)]
    finally:
        db.close()


@app.post("/api/auth/switch", tags=["auth"], summary="Switch this browser to an account")
def auth_switch(body: dict, request: Request, response: _Response):
    """Body {account_id, pin?}. Sets the signed httpOnly `jn_account` cookie for this browser only (ending any owner unlock of the previous one). The owner's PIN is required once it has one; a member's PIN is optional, and the owner's PIN also opens a PIN'd member. Errors: 404 unknown account, 401 `pin_required` / `wrong_pin` (+ `tries_left`), 429 `pin_cooldown` (+ Retry-After) after 5 wrong tries for that account from this client (30 s, doubling for repeated cooldowns up to 15 min), or while the account's global ceiling is cooling."""
    body = body or {}
    pin = body.get("pin")
    if pin is not None and not isinstance(pin, str):
        pin = str(pin)
    db = SessionLocal()
    try:
        accounts = acct_auth.load_accounts(db)
        target = acct_auth._find(accounts, body.get("account_id"))
        if target is None:
            raise HTTPException(status_code=404, detail="Account not found")
        try:
            how = acct_auth.check_switch(accounts, target, pin, client=_auth_client_ip(request))
        except acct_auth.SwitchDenied as e:
            logger.info("account switch denied: account=%s reason=%s", target["id"], e.detail)
            return _switch_denied(e)
        acct_auth.revoke_cookie_unlock(db, request.cookies.get(acct_auth.COOKIE_NAME))
        acct_auth.touch_last_active(db, target["id"], force=True)
        acct_auth.set_account_cookie(response, db, target)
        return {"ok": True, "via": how, "account": acct_auth.public_account(target)}
    finally:
        db.close()


@app.post("/api/auth/verify-pin", tags=["auth"], summary="Check an account PIN and issue its API token")
def auth_verify_pin(body: dict, request: Request):
    """Body {account_id, pin?}. Same PIN rules, cooldown counters and owner-covers-member as /api/auth/switch (an account without a PIN needs none), but sets no cookie and changes nothing. Returns {ok, via, account, token}: `token` is the account's signed API token, sent back as the `X-Account-Token` header (the extension stores it; valid 1 year, dies with a PIN change or the account). Errors: 404 unknown account, 401 `pin_required` / `wrong_pin` (+ `tries_left`), 429 `pin_cooldown`. Needs the install key; no account needed."""
    body = body or {}
    pin = body.get("pin")
    if pin is not None and not isinstance(pin, str):
        pin = str(pin)
    db = SessionLocal()
    try:
        accounts = acct_auth.load_accounts(db)
        target = acct_auth._find(accounts, body.get("account_id"))
        if target is None:
            raise HTTPException(status_code=404, detail="Account not found")
        try:
            how = acct_auth.check_switch(accounts, target, pin, client=_auth_client_ip(request))
        except acct_auth.SwitchDenied as e:
            logger.info("pin check denied: account=%s reason=%s", target["id"], e.detail)
            return _switch_denied(e)
        return {"ok": True, "via": how, "account": acct_auth.public_account(target),
                "token": acct_auth.make_api_token(db, target)}
    finally:
        db.close()


@app.get("/api/auth/me", tags=["auth"], summary="The account this browser acts as")
def auth_me(request: Request):
    """{account: {id, name, color, role, has_pin}, accounts_count, owner_has_pin, owner_unlocked_until (ISO or null)}. `owner_has_pin` (public: the picker lists has_pin too) tells a member's lock card whether the owner unlock needs a PIN or is a plain Unlock (QA F2 / D3). 401 `account_required` when the install has several accounts and this browser picked none."""
    from backend.accounts.context import current_account
    db = SessionLocal()
    try:
        accounts = acct_auth.load_accounts(db)
        acc = acct_auth._find(accounts, current_account.get()) or acct_auth._owner_of(accounts)
        if acc is None:
            raise HTTPException(status_code=404, detail="No account")
        until = getattr(request.state, "owner_unlocked_until", 0) or 0
        owner = acct_auth._owner_of(accounts)
        return {"account": acct_auth.public_account(acc), "accounts_count": len(accounts),
                "owner_has_pin": bool(owner and owner["pin_hash"]),
                "owner_unlocked_until": _epoch_iso(until) if until > acct_auth._now() else None}
    finally:
        db.close()


@app.post("/api/auth/verify-owner-pin", tags=["auth"], summary="Unlock owner-only settings for 15 minutes")
def auth_verify_owner_pin(body: dict, request: Request, response: _Response):
    """Body {pin}. On the owner's PIN (or when the owner has none yet) re-issues this browser's `jn_account` cookie for the current account with `u` = now + 15 min, exposed to routes as `request.state.owner_unlocked_until`. Returns {ok, unlocked_until}. Same 401/429 contract and owner cooldown as /api/auth/switch."""
    from backend.accounts.context import current_account
    pin = (body or {}).get("pin")
    if pin is not None and not isinstance(pin, str):
        pin = str(pin)
    db = SessionLocal()
    try:
        accounts = acct_auth.load_accounts(db)
        try:
            acct_auth.check_owner_pin(accounts, pin, client=_auth_client_ip(request))
        except acct_auth.SwitchDenied as e:
            return _switch_denied(e)
        acc = acct_auth._find(accounts, current_account.get()) or acct_auth._owner_of(accounts)
        until = int(acct_auth._now() + acct_auth.OWNER_UNLOCK_SECONDS)
        # QA F3 / R2-06: the unlock lives in the server allowlist; a previous one of this
        # browser is replaced.
        acct_auth.revoke_unlock(getattr(request.state, "owner_unlock_id", None))
        acct_auth.set_account_cookie(response, db, acc, unlocked_until=until,
                                     unlock_id=acct_auth.grant_unlock(until))
        return {"ok": True, "unlocked_until": _epoch_iso(until)}
    finally:
        db.close()


@app.post("/api/auth/owner-lock", tags=["auth"], summary="End the owner unlock in this browser")
def auth_owner_lock(request: Request, response: _Response):
    """MT-14 "Lock": re-issues this browser's `jn_account` cookie for the same account with no owner unlock, and drops the unlock from the server allowlist so a copied cookie value stops unlocking too (QA F3 / R2-06). Returns {ok, locked}. A browser with no account cookie (one account, or the API path) has nothing to lock: {ok, locked: false}."""
    from backend.accounts.context import current_account
    if not request.cookies.get(acct_auth.COOKIE_NAME):
        return {"ok": True, "locked": False}
    acct_auth.revoke_unlock(getattr(request.state, "owner_unlock_id", None))
    db = SessionLocal()
    try:
        accounts = acct_auth.load_accounts(db)
        acc = acct_auth._find(accounts, current_account.get())
        if acc is None:
            return {"ok": True, "locked": False}
        acct_auth.set_account_cookie(response, db, acc, unlocked_until=0)
        return {"ok": True, "locked": True}
    finally:
        db.close()


# ── Routes ───────────────────────────────────────────────────────────────────
app.include_router(settings_router, prefix="/api")
app.include_router(jobs_router, prefix="/api")
app.include_router(applications_router, prefix="/api")
app.include_router(companies_router, prefix="/api")
app.include_router(searches_router, prefix="/api")
app.include_router(resumes_router, prefix="/api")
app.include_router(persona_router, prefix="/api")
app.include_router(cover_letters_router, prefix="/api")
app.include_router(linkedin_router, prefix="/api")
app.include_router(telemetry_router, prefix="/api")
app.include_router(updates_router, prefix="/api")
app.include_router(autofill_router, prefix="/api")
app.include_router(llm_router, prefix="/api")
app.include_router(accounts_router, prefix="/api")
app.include_router(gmail_router, prefix="/api")


# A malformed UUID in a path (/api/jobs/abc) makes Postgres raise DataError deep in
# the query; without this every id route answers 500 instead of 404.
from sqlalchemy.exc import DataError as _SADataError


@app.exception_handler(_SADataError)
async def _bad_uuid_to_404(request: Request, exc: _SADataError):
    if "invalid input syntax for type uuid" in str(exc.orig or exc):
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    logger.exception("Database DataError on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.exception_handler(_PoolTimeout)
async def _pool_timeout_to_503(request: Request, exc: _PoolTimeout):
    """A handler that could not get a connection answers 503, not 500."""
    logger.warning("DB pool exhausted on %s %s", request.method, request.url.path)
    return _pool_busy_response()


@app.get("/health", tags=["system"], summary="Health check")
def health_check():
    """Returns OK if the backend is running.

    Deliberately touches no database: it is the one endpoint that must answer
    while the pool is drained, and it is in _PUBLIC_PREFIXES so the auth
    middleware's settings read is skipped too.

    `image_outdated` is true when the image's packages (or build stamp) do not
    match the mounted code; `image_message` then says what differs and how to fix
    it. Computed once per process (image_check.py).
    """
    from backend.image_check import image_status
    status = image_status()
    return {
        "status": "ok", "service": "JobNavigator", "version": APP_VERSION,
        "image_outdated": status["image_outdated"],
        "image_message": status["image_message"],
        "image_details": status["image_details"],
    }


async def _tracer_click_and_redirect(token: str, request: Request):
    """Log the click (best-effort) and 302 to the link's destination; shared by both link shapes (path /cv/{token} and param /?cv={token})."""
    import re
    import hashlib
    from backend.models.db import TracerLink, TracerClickEvent

    from backend.accounts.context import use_account

    db = SessionLocal()
    try:
        # Public route, no session: the token is unique install-wide, so resolve it
        # across every account (MT-6) and record the click under the link's account.
        link = (db.query(TracerLink).execution_options(jn_unscoped=True)
                .filter(TracerLink.token == token, TracerLink.is_active == True).first())
        if not link:
            raise HTTPException(404, "Link not found")
        link_account = link.account_id

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

        bot_pattern = re.compile(
            r'\b(bot|crawler|spider|preview|scanner|headless|curl|wget|'
            r'slackbot|discordbot|facebookexternalhit|whatsapp|'
            r'skypeuripreview|linkedinbot|googleimageproxy)\b', re.I
        )
        is_bot = bool(bot_pattern.search(request.headers.get("user-agent") or ""))

        ip = request.client.host if request.client else None
        ip_hash = None
        if ip:
            parts = ip.split(".")
            if len(parts) == 4:
                prefix = f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
            else:
                prefix = ip
            ip_hash = hashlib.sha256(prefix.encode()).hexdigest()

        referrer = request.headers.get("referer")
        referrer_host = None
        if referrer:
            try:
                from urllib.parse import urlparse
                referrer_host = urlparse(referrer).hostname
            except Exception:
                pass

        # Capture destination before the click-log write so redirect still happens
        # even if the click-log commit fails (best-effort logging).
        destination = link.destination_url

        try:
            with use_account(link_account):
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


@app.get("/cv/{token}", tags=["tracer"], summary="Tracer link redirect (path style)")
async def tracer_redirect(token: str, request: Request):
    """Path-style tracer link: /cv/{token}. Logs click, then 302 redirects."""
    return await _tracer_click_and_redirect(token, request)


@app.get("/", include_in_schema=False)
async def tracer_redirect_param(request: Request):
    """Param-style tracer link: /?cv={token}. Only tracer requests reach the backend
    root (Caddy routes bare / to the frontend); without ?cv it's a 404."""
    token = request.query_params.get("cv")
    if not token:
        raise HTTPException(404, "Not found")
    return await _tracer_click_and_redirect(token, request)


# ── Trigger endpoints (non-blocking, return 202) ────────────────────────────
@app.post("/api/scrape/run-all", tags=["triggers"], summary="Run all scrapes", status_code=202)
async def trigger_all_scrapes():
    """Run all active JobSpy keyword searches + all active Playwright career page scrapes.
    Returns immediately with a run_id. Check progress via /api/monitor/active.
    """
    async def _do():
        from datetime import datetime as _dt, timezone as _tz
        from backend.scheduler import _scrape_summary
        started = _dt.now(_tz.utc)
        from backend.scraper.orchestrator import run_all as run_all_searches
        from backend.accounts.context import current_account
        # A manual run-all covers the caller's searches and companies only (MT-8); the
        # scheduled one covers every account. None = owner fallback (caller's context).
        outcome = await run_all_searches(force=True, account_ids=[current_account.get()]) or {}
        from backend.analyzer.cv_scorer import analyze_unscored_jobs
        await analyze_unscored_jobs()
        summary = _scrape_summary(started)
        # Name what did not run, so a company missing from the sweep is visible in
        # the run history instead of only in the container log.
        skipped = ((outcome.get("companies") or {}).get("skipped")) or []
        if skipped:
            shown = ", ".join(f"{s['name']} ({s['reason']})" for s in skipped[:4])
            if len(skipped) > 4:
                shown += f", +{len(skipped) - 4} more"
            summary += f" - {len(skipped)} skipped: {shown}"
        return summary

    try:
        run_id = launch_background("scrape_all", _do, trigger="manual")
        return {"run_id": run_id, "status": "running"}
    except JobAlreadyRunningError as e:
        logger.info("Duplicate trigger rejected for job_type=%s: %s", e.job_type, e)
        # QA F6 / R4-01: refused while the scheduled scrape is live (`scheduled_scrape_running`).
        from backend.job_monitor import scheduled_scrape_conflict_response
        return scheduled_scrape_conflict_response(e)


@app.post("/api/email/check-now", tags=["triggers"], summary="Check Gmail now", status_code=202)
async def trigger_email_check():
    """Poll Gmail for new emails. Returns immediately with a run_id."""
    async def _do():
        from datetime import datetime as _dt, timezone as _tz
        from backend.scheduler import _activity_summary
        started = _dt.now(_tz.utc)
        from backend.email_monitor.gmail_client import check_emails
        await check_emails()
        return _activity_summary(started, "email", "reply", "replies") or "No new replies"

    try:
        run_id = launch_background("email_check", _do, trigger="manual")
        return {"run_id": run_id, "status": "running"}
    except JobAlreadyRunningError as e:
        logger.info("Duplicate trigger rejected for job_type=%s", e.job_type)
        return JSONResponse(
            status_code=409,
            content={"detail": f"{e.job_type} is already running"},
        )


@app.post("/api/h1b/refresh", tags=["triggers"], summary="Refresh H-1B data", status_code=202,
          dependencies=[Depends(acct_auth.require_owner)])
async def trigger_h1b_refresh():
    """Scrape MyVisaJobs.com for all active companies. Returns immediately with a run_id. Install-level: 403 for a member."""
    async def _do():
        from datetime import datetime as _dt, timezone as _tz
        from backend.models.db import VisaCache
        started = _dt.now(_tz.utc)
        from backend.analyzer.h1b_checker import refresh_all_h1b
        await refresh_all_h1b()
        db = SessionLocal()
        try:
            n = db.query(VisaCache).filter(VisaCache.fetched_at >= started).count()
            return f"{n} compan{'y' if n == 1 else 'ies'} refreshed"
        finally:
            db.close()

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
    """Re-run resume scoring for a specific job. depth: 'light' or 'full' (default)."""
    import uuid as _uuid
    # uuid.UUID(job_id) used to be evaluated inside the launch_background(...)
    # call, so a malformed id raised ValueError instead of answering the way
    # every other id route does (R4-T1-23).
    try:
        target_job_uuid = _uuid.UUID(job_id)
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(status_code=404, detail="Not found")

    # JobRun.target_job_id is a FK to jobs.id, so a well-formed id for a job that does
    # not exist raised ForeignKeyViolation inside launch_background — a bare 500 plus a
    # full INSERT traceback in the log (R4-T5-09). Look it up first, like
    # /api/scrape/company/{id} does.
    from backend.models.db import Job as _Job
    cv_ids = (body or {}).get("cv_ids")
    db = SessionLocal()
    try:
        job_row = db.query(_Job).filter(_Job.id == target_job_uuid).first()
        if not job_row:
            raise HTTPException(status_code=404, detail="Job not found")
        # cv_ids is a filter, not a reference: _cv_texts_for_ids loads them through the
        # scoped session, so an id that is unknown or another account's scores nothing.
        # Names the run will write into cv_scores, resolved while the session is open.
        try:
            from backend.analyzer.cv_scorer import resolve_score_resume_names
            resume_names = resolve_score_resume_names(db, job=job_row, cv_ids=cv_ids)
        except Exception:
            resume_names = []
    finally:
        db.close()

    async def _do():
        from backend.analyzer.cv_scorer import score_single_job
        # Forwarded so the run's summary reaches JobRun.result_summary.
        return await score_single_job(job_id, cv_ids=cv_ids, depth=depth)

    # Include cv_ids in scope_key so scoring the same job with different CVs doesn't conflict
    scope = f"{job_id}:{','.join(sorted(cv_ids))}" if cv_ids else job_id
    try:
        run_id = launch_background(
            "analyze_job", _do, trigger="manual", scope_key=scope,
            target_job_id=target_job_uuid,
            meta={"resume_names": resume_names, "depth": depth},
        )
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
                return "Disabled (job_archive_after_days = 0)"
            cutoff = dt.now(tz.utc) - timedelta(days=archive_days)
            old_skipped = db.query(Job).filter(Job.status == "skip", Job.discovered_at < cutoff).all()
            count = len(old_skipped)
            for job in old_skipped:
                db.delete(job)
            db.commit()
            from backend.activity import log_activity
            log_activity("scrape", f"Job cleanup: deleted {count} old skipped jobs (>{archive_days} days)")
            return f"{count} skipped job{'' if count == 1 else 's'} deleted (>{archive_days}d old)"
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
                return "Disabled (auto_reject_after_days = 0)"
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
            return f"{count} application{'' if count == 1 else 's'} auto-rejected (>{days}d silent)"
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
    """Fetch job descriptions for new/saved/applied jobs that have a URL but no description."""
    async def _do():
        from backend.models.db import Job
        from backend.scraper.ats._descriptions import _fetch_job_description
        from backend.analyzer.salary_extractor import apply_salary_to_job
        db = SessionLocal()
        try:
            jobs = db.query(Job).filter(
                # "applied" is in the set because a hand-logged job (Log application)
                # lands there directly and needs the same repair.
                Job.status.in_(["new", "saved", "applied"]),
                Job.url != None,
                (Job.description == None) | (Job.description == ""),
            ).order_by(Job.discovered_at.desc()).limit(50).all()

            logger.info(f"Backfill descriptions: {len(jobs)} jobs to process")
            import asyncio
            count = 0
            for job in jobs:
                try:
                    desc = await _fetch_job_description(job_link(job))
                    if desc and len(desc) > 50:
                        job.description = desc
                        apply_salary_to_job(job)
                        from backend.analyzer.work_arrangement import apply_arrangement_to_job
                        apply_arrangement_to_job(job)
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


@app.post("/api/db/backup", tags=["triggers"], summary="Run database backup", status_code=202,
          dependencies=[Depends(acct_auth.require_owner)])
async def trigger_db_backup():
    """Run a database backup immediately. Returns immediately with a run_id. Install-level: 403 for a member."""
    async def _do():
        from backend.db_backup import run_pg_dump
        # Keeps only the last 5 rotation backups
        b = run_pg_dump()
        return f"Snapshot {b['size_mb']:.0f} MB -> {b['file']}" + (f" - {b['pruned']} old pruned" if b['pruned'] else "")

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
        from datetime import datetime as _dt, timezone as _tz
        from backend.scheduler import _activity_summary
        started = _dt.now(_tz.utc)
        from backend.notifier.telegram import send_digest
        sent = await send_digest()
        if sent is False:      # QA F9 / T3-02
            from backend.scheduler import DIGEST_SKIPPED_SUMMARY
            return DIGEST_SKIPPED_SUMMARY
        return _activity_summary(started, "telegram", "alert") or "Digest sent"

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
        from backend.scraper.sources.company_pages import (
            scrape_single_career_page, record_company_scrape_log,
        )
        db2 = SessionLocal()
        try:
            c = db2.query(C).filter(C.id == company_id).first()
            if c:
                result = await scrape_single_career_page(c)
                if result and result.get("deleted"):   # QA F6 / T5-04
                    return f"{company_name} - deleted during the run, nothing saved"
                # Same audit row the batch path writes, so a manual run also shows
                # up in /api/scrape-log, is_warning and /health/entities.
                # A manual run feeds only this account (MT-8): its own run_id, no fan-out.
                import uuid as _uuid
                should_score = auto_score if auto_score is not None else (c.auto_scoring_depth in ("light", "full"))
                record_company_scrape_log(c.id, c.name, result or {}, db=db2, run_id=_uuid.uuid4())
                if should_score and result and result.get("new_jobs", 0) > 0:
                    from backend.analyzer.cv_scorer import analyze_unscored_jobs
                    await analyze_unscored_jobs(status="new")
                if result:
                    return f"{company_name} - {result.get('jobs_found', 0)} seen, +{result.get('new_jobs', 0)} new"
        finally:
            db2.close()

    try:
        run_id = launch_background(
            "company_scrape", _do, trigger="manual",
            scope_key=company_id, company_id=company_id,
            meta={"company": company_name},
        )
        return {"run_id": run_id, "status": "running", "company": company_name}
    except JobAlreadyRunningError as e:
        logger.info("Duplicate trigger rejected for job_type=%s: %s", e.job_type, e)
        from backend.job_monitor import scheduled_scrape_conflict_response
        return scheduled_scrape_conflict_response(e)


@app.post("/api/telegram/webhook", tags=["telegram"], summary="Telegram webhook")
async def telegram_webhook(update: dict, request: Request):
    """Handle a Telegram webhook update of the household bot (callback queries from inline buttons, link codes); validates X-Telegram-Bot-Api-Secret-Token against the telegram_webhook_secret setting.
    The chat names the account (MT-17): buttons act only on that account's jobs, an unlinked chat acts on nothing."""
    db = SessionLocal()
    try:
        expected = (get_install_setting(db, "telegram_webhook_secret") or "").strip()
    finally:
        db.close()
    if not expected:
        # Misconfigured — never accept anonymous webhook traffic. The seed step
        # populates this on first run; an empty value means someone cleared it.
        logger.warning("telegram_webhook rejected: webhook secret not configured")
        raise HTTPException(status_code=503, detail="Telegram webhook secret not configured")
    received = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not received or not _secret_eq(received, expected):   # QA F8 / R5-07: never a 500
        logger.warning("telegram_webhook rejected: invalid secret token")
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    import backend.notifier.telegram as tg
    await _telegram_update(update, tg.household_chat_account, TELEGRAM_BOT_TOKEN)
    return {"ok": True}


async def _telegram_update(update: dict, chat_account, answer_token: str, bot_account=None):
    """One webhook update (MT-17). Inline buttons act only for the account the chat is
    linked to (`chat_account(chat_id)`, NOT_LINKED = none); text messages carry link codes.
    `bot_account` = the member whose own bot posted (None = the household bot)."""
    import backend.notifier.telegram as tg
    if not isinstance(update, dict):
        return
    callback_query = update.get("callback_query")
    if callback_query and isinstance(callback_query, dict):
        data = callback_query.get("data", "")
        message = callback_query.get("message")
        message_id = message.get("message_id") if isinstance(message, dict) else None
        with tg.acting_for_chat(chat_account(tg.update_chat_id(callback_query))):
            result = await tg.handle_callback(data, message_id)

        # Answer callback to remove loading state
        callback_id = callback_query.get("id")
        if callback_id and answer_token:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"https://api.telegram.org/bot{answer_token}/answerCallbackQuery",
                    json={"callback_query_id": callback_id, "text": result},
                )
    message = update.get("message")
    if isinstance(message, dict):
        own_token = answer_token if bot_account is not None else None
        await tg.handle_message(message, bot_account=bot_account, token=own_token)


@app.post("/api/telegram/webhook/{bot_account_id}", tags=["telegram"], summary="Telegram webhook (a member's own bot)")
async def telegram_member_webhook(bot_account_id: str, update: dict, request: Request):
    """Webhook of a member's own bot (MT-17): validates X-Telegram-Bot-Api-Secret-Token
    against that member's own webhook secret; buttons act only when pressed in the
    member's own chat, on the member's jobs; text messages carry link codes."""
    import uuid as _uuid
    import backend.notifier.telegram as tg
    try:
        acc = _uuid.UUID(bot_account_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Unknown bot")
    db = SessionLocal()
    try:
        own = tg.member_own_bot(db, acc)
    finally:
        db.close()
    if own is None:
        raise HTTPException(status_code=404, detail="Unknown bot")
    token, expected = own
    if not expected:
        raise HTTPException(status_code=503, detail="Telegram webhook secret not configured")
    received = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not received or not _secret_eq(received, expected):   # QA F8 / R5-07: never a 500
        logger.warning("telegram_member_webhook rejected: invalid secret token")
        raise HTTPException(status_code=401, detail="Invalid webhook secret")
    await _telegram_update(update, lambda chat: tg.own_bot_chat_account(acc, chat), token, bot_account=acc)
    return {"ok": True}


@app.post("/api/telegram/link-code", tags=["telegram"], summary="Code to link a Telegram chat")
def telegram_link_code():
    """A 6-digit code (10 minutes) for the caller's account. Sending `/start <code>` (or
    just the code) to the bot links that chat as the account's chat id (MT-17)."""
    from backend.accounts.context import current_account
    from backend.models.db import Account, get_owner_id
    import backend.notifier.telegram as tg
    db = SessionLocal()
    try:
        acc_id = current_account.get() or get_owner_id(db)
        acc = db.query(Account).filter(Account.id == acc_id).first() if acc_id else None
        if acc is None:
            raise HTTPException(status_code=409, detail="No account to link")
        own = tg.member_own_bot(db, acc.id) is not None
        name = acc.name
    finally:
        db.close()
    out = tg.create_link_code(acc_id)
    out.update({"account": name, "bot": "own" if own else "household"})
    return out


def _telegram_owner_check(db):
    from backend.accounts.settings import acts_as_owner
    if not acts_as_owner(db):
        raise HTTPException(status_code=403, detail="owner_only")


@app.post("/api/telegram/register-webhook", tags=["telegram"], summary="Register Telegram webhook")
async def telegram_register_webhook(body: dict):
    """Register {public_url}/api/telegram/webhook with Telegram, signed with telegram_webhook_secret; public_url must be HTTPS.
    A member on its own bot registers that bot at {public_url}/api/telegram/webhook/<account id> with a fresh
    secret of its own; the household bot is the owner's (403 for a member)."""
    import secrets as _secrets
    import backend.notifier.telegram as tg
    from backend.accounts.settings import member_account
    public_url = (body.get("public_url") or "").strip().rstrip("/")
    if not public_url.startswith("https://"):
        raise HTTPException(status_code=400, detail="public_url must start with https://")
    db = SessionLocal()
    try:
        member = member_account(db)
        own = tg.member_own_bot(db, member) if member is not None else None
        if own is None:
            _telegram_owner_check(db)
    finally:
        db.close()
    if own is not None:
        # QA F8 / R5-05: the fresh secret is stored only once Telegram accepted the webhook
        # that carries it; on any failure the old secret (and the old webhook) keep working.
        secret = _secrets.token_urlsafe(32)
        result = await tg.register_webhook(f"{public_url}/api/telegram/webhook/{member}", token=own[0], secret=secret)
        if isinstance(result, dict) and result.get("ok") is True:
            db = SessionLocal()
            try:
                put_setting(db, tg.OWN_WEBHOOK_SECRET_KEY, secret, account_id=member,
                            description="Secret of this account's own Telegram bot webhook.")
                db.commit()
            finally:
                db.close()
        return result
    full_url = f"{public_url}/api/telegram/webhook"
    result = await tg.register_webhook(full_url)
    return result


@app.post("/api/telegram/rotate-webhook-secret", tags=["telegram"], summary="Rotate Telegram webhook secret")
async def telegram_rotate_webhook_secret():
    """Regenerate `telegram_webhook_secret` and return the new value. After
    rotating, call POST /api/telegram/register-webhook to re-register with
    Telegram so the next callback carries the new header value. The household bot is the
    owner's: a member gets 403 (its own bot gets a fresh secret on every registration).
    """
    from backend.notifier.telegram import rotate_webhook_secret
    db = SessionLocal()
    try:
        _telegram_owner_check(db)
    finally:
        db.close()
    new_value = rotate_webhook_secret()
    return {"ok": True, "webhook_secret": new_value}


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


_OWNER_ONLY_SCHEDULES = frozenset({"h1b_refresh", "db_backup", "telemetry_daily"})   # install-level / require_owner

# The schedules list shows these names; every id scheduler.py registers needs one
# (test_schedule_names.py).
SCHEDULE_NAMES = {
    "scrape_all": "Scrape all searches & companies",
    "email_check": "Check Gmail for replies",
    "daily_digest": "Send daily Telegram digest",
    "h1b_refresh": "Refresh H-1B / LCA data",
    "db_backup": "Back up database (pg_dump)",
    "job_cleanup": "Clean up stale skipped jobs",
    "auto_reject": "Auto-reject stale applications",
    "telemetry_daily": "Send telemetry (what Settings › Telemetry allows)",
}


@app.get("/api/scheduler/jobs", tags=["scheduler"], summary="List scheduled jobs")
def get_scheduler_jobs():
    """Return all scheduler jobs with their schedule, next run time (UTC), trigger URL, and running state."""
    from backend.scheduler import scheduler
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
            "name": SCHEDULE_NAMES.get(job.id, job.name or job.id),
            "schedule": schedule,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "pending": job.pending,
            "trigger_url": trigger_url,
            "running": running_info,
            # QA F7 / T7-02: the trigger is `require_owner` (403 for a member that has
            # not unlocked the owner sections); the Stats table hides Run now then
            "owner_only": job.id in _OWNER_ONLY_SCHEDULES,
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
                "trigger_url": f"/searches/{s.id}/run",
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
                running_info = {"run_id": str(company_running.run_id), "elapsed_seconds": round(elapsed, 1),
                                "waiting": company_running.waiting}
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
    """Return the current account's running jobs with elapsed time in seconds (MT-6;
    get_all_running(all_accounts=True) is the hook for an owner "every account" view)."""
    return get_all_running()


@app.get("/api/monitor/in-flight", tags=["monitor"], summary="Per-job active operations")
def get_in_flight(job_ids: str = None, detail: bool = False):
    """Return {job_id: [job_types]} for running ops tagged with target_job_id (scheduler-level ops like scrape_all have none, so are omitted); optional job_ids filters by comma-separated UUIDs, and detail=1 returns [{job_type, meta}] entries instead of bare job types."""
    import backend.job_monitor as mon

    wanted: set[str] | None = None
    if job_ids:
        wanted = {s.strip() for s in job_ids.split(",") if s.strip()}

    result: dict[str, list] = {}
    for r in mon.visible_running():   # the current account's runs only (MT-6)
        if r.target_job_id is None:
            continue
        key = str(r.target_job_id)
        if wanted is not None and key not in wanted:
            continue
        entry = {"job_type": r.job_type, "meta": r.meta} if detail else r.job_type
        result.setdefault(key, []).append(entry)

    return result


@app.get("/api/monitor/finished", tags=["monitor"], summary="Recently finished per-job runs")
def get_finished(job_ids: str = None, since: str = None,
                 limit: Annotated[int, Query(ge=0, le=1000)] = 200):
    """Return recently finished (completed/failed) runs for the given jobs, so the dashboard can resolve OK/NOK for an op that just left /monitor/in-flight from the run's actual status rather than job fields."""
    import uuid as _uuid
    from datetime import datetime as _dt, timezone as _tz

    wanted = None
    if job_ids:
        wanted = []
        for s in job_ids.split(","):
            s = s.strip()
            if not s:
                continue
            try:
                wanted.append(_uuid.UUID(s))
            except ValueError:
                continue
        if not wanted:
            return []

    # `since` is epoch milliseconds (URL-safe; avoids the '+' in ISO offsets
    # decoding to a space in a query string). Runs finished at/after it are kept.
    since_dt = None
    if since:
        try:
            since_dt = _dt.fromtimestamp(int(since) / 1000, tz=_tz.utc)
        except (ValueError, TypeError, OverflowError):
            since_dt = None

    def _aware(dt):
        # Normalize so naive (SQLite) and aware (Postgres) values compare cleanly.
        return dt.replace(tzinfo=_tz.utc) if dt.tzinfo is None else dt

    db = SessionLocal()
    try:
        q = db.query(JobRun).filter(
            JobRun.status.in_(("completed", "failed")),
            JobRun.target_job_id.isnot(None),
        )
        if wanted is not None:
            q = q.filter(JobRun.target_job_id.in_(wanted))
        runs = q.order_by(JobRun.finished_at.desc()).limit(limit).all()
        return [
            {
                "target_job_id": str(r.target_job_id),
                "job_type": r.job_type,
                "status": r.status,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            }
            for r in runs
            if since_dt is None or (r.finished_at is not None and _aware(r.finished_at) >= since_dt)
        ]
    finally:
        db.close()


@app.get("/api/monitor/history", tags=["monitor"], summary="Run history")
def get_run_history(limit: Annotated[int, Query(ge=0, le=1000)] = 30, offset: int = 0,
                    job_type: str = None, status: str = None):
    """Return recent job run history, newest first.

    `offset` skips that many rows so the dashboard can page ("Load more").
    """
    db = SessionLocal()
    try:
        q = db.query(JobRun)
        if job_type:
            q = q.filter(JobRun.job_type == job_type)
        if status:
            q = q.filter(JobRun.status == status)
        q = q.order_by(JobRun.started_at.desc())
        member = _member_viewer(db)
        if member is None or (job_type and job_type != "scrape_all"):
            runs = q.offset(max(0, offset)).limit(limit).all()
            return [_run_dict(r) for r in runs]
        # QA V-03: a member also sees the install-level scheduled scrape_all runs (the
        # owner's rows), which ingest into every account — merged by start time.
        upto = max(0, offset) + limit
        own = q.limit(upto).all()
        shared = _install_scrape_runs(db, member, status=status, limit=upto)
        runs = sorted(own + shared, key=lambda r: _utc_ts(r.started_at), reverse=True)
        runs = runs[max(0, offset):upto]
        shared_ids = {r.id for r in shared}
        views = _member_views(db, [r for r in runs if r.id in shared_ids])
        return [views.get(r.id) or _run_dict(r) for r in runs]
    finally:
        db.close()


def _run_dict(r) -> dict:
    return {
        "id": str(r.id),
        "job_type": r.job_type,
        "trigger": r.trigger,
        "status": r.status,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        "duration_seconds": r.duration_seconds,
        "result_summary": r.result_summary,
        "error": sanitize_run_error(r.error),
        "meta": r.meta,
    }


def _utc_ts(ts):
    from datetime import datetime as _d, timezone as _tz
    if ts is None:
        return _d.min.replace(tzinfo=_tz.utc)
    return ts.replace(tzinfo=_tz.utc) if ts.tzinfo is None else ts


def _member_viewer(db):
    """The caller's account when it is a member (None for the owner / no accounts)."""
    from backend.accounts.settings import member_account
    try:
        return member_account(db)
    except Exception:
        return None


# Message a member sees instead of a failed scheduled run's error, which may name
# other accounts (the owner sees the full text).
INSTALL_RUN_FAILED = "The scheduled scrape failed — details are in the owner's Run history"


def _install_scrape_runs(db, member, status=None, limit=30, run_id=None) -> list:
    """The owner's scheduled scrape_all runs (install-level since MT-8: one fetch, ingest
    into every subscribing account) started after `member` was created, newest first.
    Read unscoped; the caller turns each into the member's view (_member_views)."""
    from backend.accounts.context import unscoped, owner_account_id
    from backend.models.db import Account
    owner = owner_account_id()
    if owner is None:
        return []
    with unscoped():
        acc = db.query(Account).filter(Account.id == member).first()
        q = db.query(JobRun).filter(JobRun.account_id == owner,
                                    JobRun.job_type == "scrape_all",
                                    JobRun.trigger == "scheduler")
        if acc is not None and acc.created_at is not None:
            q = q.filter(JobRun.started_at >= acc.created_at)
        if status:
            q = q.filter(JobRun.status == status)
        if run_id is not None:
            q = q.filter(JobRun.id == run_id)
        runs = q.order_by(JobRun.started_at.desc()).limit(limit).all()
        for r in runs:
            db.expunge(r)   # read-only snapshots: never flushed back under the member
    return runs


def _member_views(db, runs) -> dict:
    """id → the member's view of install-level scheduled runs: timing and status kept,
    the summary rebuilt from the member's OWN ScrapeLog rows in the run's window, the
    error replaced by a generic line, meta dropped. Nothing of another account."""
    from backend.scheduler import own_scrape_summaries
    if not runs:
        return {}
    try:
        lines = own_scrape_summaries(db, [(r.started_at, r.finished_at) for r in runs])
    except Exception:
        logger.exception("member run summary failed")
        lines = ["Summary unavailable"] * len(runs)
    out = {}
    for r, line in zip(runs, lines):
        d = _run_dict(r)
        d["result_summary"] = None if r.status == "running" else line
        d["error"] = INSTALL_RUN_FAILED if (r.status == "failed" or r.error) else None
        d["meta"] = {"install_run": True}
        out[r.id] = d
    return out


@app.get("/api/monitor/run/{run_id}", tags=["monitor"], summary="Single run details")
def get_run_detail(run_id: str):
    """Return details for a single job run."""
    db = SessionLocal()
    try:
        r = db.query(JobRun).filter(JobRun.id == run_id).first()
        if r:
            return _run_dict(r)
        member = _member_viewer(db)
        if member is not None:
            # QA V-03: a member may open an install-level scheduled run (its own part).
            shared = _install_scrape_runs(db, member, limit=1, run_id=run_id)
            if shared:
                return _member_views(db, shared)[shared[0].id]
        raise HTTPException(status_code=404, detail="Run not found")
    finally:
        db.close()


@app.get("/api/activity-log", tags=["scheduler"], summary="Activity log")
def get_activity_log(
    limit: Annotated[int, Query(ge=0, le=1000)] = 50,
    offset: int = 0,
    type: str = None,
    company: str = None,
):
    """Recent activity log entries, optionally filtered by exact `type` and case-insensitive `company` substring, paginated with limit/offset."""
    from backend.models.db import ActivityLog
    db = SessionLocal()
    try:
        q = db.query(ActivityLog)
        if type:
            q = q.filter(ActivityLog.type == type)
        if company:
            q = q.filter(ActivityLog.company.ilike(f"%{company}%"))
        logs = q.order_by(ActivityLog.created_at.desc()).offset(max(0, offset)).limit(limit).all()
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
    limit: Annotated[int, Query(ge=0, le=1000)] = 50,
    errors_only: bool = False,
    warnings_only: bool = False,
):
    """Raw scrape run history with per-search/company details, including per-board `source_breakdown`; optionally filtered to errored or 0-result (warning) runs."""
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
                # Per-board {seen, new, error?} — without it a run whose ZipRecruiter
                # leg 403'd is indistinguishable here from a clean one.
                "source_breakdown": log.source_breakdown or None,
                "ran_at": log.ran_at.isoformat() if log.ran_at else None,
            }
            for log in logs
        ]
    finally:
        db.close()


@app.get("/api/stats/timeline", tags=["stats"], summary="Job discovery timeline")
def get_stats_timeline(days: Annotated[int, Query(le=3650)] = 30):
    """Daily job counts for the last N days.

    Only the upper bound is enforced: `days <= 0` is a legal "everything from now
    on" window that returns an empty series, while an absurd value overflowed
    `timedelta` and escaped as a bare 500 (R4-T1-08).
    """
    from backend.models.db import Job
    from sqlalchemy import func
    from datetime import datetime, timedelta, timezone

    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        # date() instead of CAST(... AS DATE): the same day on Postgres, and SQLite
        # (tests) answers it too, so the leak harness can judge this route (MT-6).
        day = func.date(Job.discovered_at)
        rows = db.query(
            day.label("date"),
            func.count().label("total"),
            func.count().filter(Job.status == "new").label("new"),
            func.count().filter(Job.status == "saved").label("saved"),
            func.count().filter(Job.status == "applied").label("applied"),
            func.count().filter(Job.status == "skip").label("skipped"),
            # 'ignored' = auto-filtered (title/body/H-1B), saved only for dedup — never shown in the feed.
            func.count().filter(Job.status == "ignored").label("filtered"),
        ).filter(Job.discovered_at >= cutoff).group_by(day).order_by(day).all()
        return [{
            "date": str(r.date), "total": r.total,
            "new": r.new, "saved": r.saved, "applied": r.applied,
            "skipped": r.skipped, "filtered": r.filtered,
        } for r in rows]
    finally:
        db.close()


@app.get("/api/health/entities", tags=["stats"], summary="Companies/searches needing attention")
def get_failing_entities(window: Annotated[int, Query(ge=1, le=100)] = 3):
    """Active companies/searches whose last `window` scrapes all errored or returned 0 results (a likely broken/moved ATS or dead URL); acknowledged warnings drop out until a newer run fails again.

    `window` must be at least 1: `window=0` made `all([])` true and reported every
    active company and search as broken, and a negative one reached `LIMIT -1`
    (R4-T1-10).
    """
    from backend.models.db import ScrapeLog, Company, Search, is_acknowledged
    from backend.scraper.orchestrator import empty_sources, source_errors, source_label
    db = SessionLocal()
    try:
        def _reason(entity_col, entity_id, acknowledged_at=None):
            recent = (db.query(ScrapeLog).filter(entity_col == entity_id)
                      .order_by(ScrapeLog.ran_at.desc()).limit(window).all())
            # Acknowledging reads healthy until something *newer* than the
            # acknowledgement goes wrong (compared against the newest run, not "now").
            if recent and is_acknowledged(recent[0].ran_at, acknowledged_at):
                return None
            # One configured board refusing the request is worth flagging on its
            # own, since the other boards can mask it entirely.
            if recent:
                failed = source_errors(recent[0].source_breakdown)
                if failed:
                    return " · ".join(
                        f"{source_label(k)} failed ({e})" for k, e in failed
                    ) + " on the last run"
            if len(recent) < window or not all(r.error or r.is_warning for r in recent):
                return None
            err = next((r.error for r in recent if r.error), None)
            if err:
                return err[:160]
            # is_warning also covers "one board returned nothing while the others
            # worked". Two outcomes:
            #  - a board quiet on every run in the window: name it;
            #  - every other case: the original sentence. It can be false about
            #    a run that found jobs while a board stayed quiet on some runs
            #    only. The user accepts that cost and keeps this wording.
            per_run = [set(empty_sources(r.source_breakdown)) for r in recent]
            always_quiet = sorted(set.intersection(*per_run)) if per_run else []
            if always_quiet:
                return " · ".join(f"{source_label(k)} returned nothing" for k in always_quiet) \
                       + f" in the last {window} scrapes"
            return f"No results in the last {window} scrapes"

        # Paused/inactive entities are excluded on purpose (their last-run state
        # is history, not an open problem) but still show up muted in the row.
        companies = []
        for c in db.query(Company).filter(Company.active == True).all():
            reason = _reason(ScrapeLog.company_id, c.id, c.warning_acknowledged_at)
            if reason:
                companies.append({"id": str(c.id), "name": c.name, "reason": reason})

        searches = []
        for s in db.query(Search).filter(Search.active == True).all():
            reason = _reason(ScrapeLog.search_id, s.id, s.warning_acknowledged_at)
            if reason:
                searches.append({"id": str(s.id), "name": s.name, "reason": reason})

        return {"companies": companies, "searches": searches,
                "count": len(companies) + len(searches)}
    finally:
        db.close()


@app.get("/api/stats/score-distribution", tags=["stats"], summary="Resume score distribution")
def get_score_distribution(detail: bool = False):
    """Distribution of best resume scores across all scored jobs; `detail=true` adds scored_count/avg/tailored_count/tailored_avg on top of the bare bucket list."""
    from backend.models.db import Job

    db = SessionLocal()
    try:
        # Only the scores column: loading whole Job rows to read one JSON field
        # cost ~800ms on a few thousand jobs and was the single thing Stats waited on.
        rows = db.query(Job.cv_scores).filter(Job.cv_scores != None).all()
        buckets = {"0-20": 0, "21-40": 0, "41-60": 0, "61-80": 0, "81-100": 0}
        bests: list[float] = []
        tailored: list[float] = []
        for (scores,) in rows:
            scores = scores or {}
            if not isinstance(scores, dict):
                continue
            numeric = [v for v in scores.values() if isinstance(v, (int, float))]
            if not numeric:
                continue
            best = max(numeric)
            bests.append(best)
            t = scores.get("Tailored")
            if isinstance(t, (int, float)):
                tailored.append(t)
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
        rows = [{"range": k, "count": v} for k, v in buckets.items()]
        if not detail:
            return rows
        return {
            "buckets": rows,
            "scored_count": len(bests),
            "avg": round(sum(bests) / len(bests), 1) if bests else None,
            "tailored_count": len(tailored),
            "tailored_avg": round(sum(tailored) / len(tailored), 1) if tailored else None,
        }
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

def _llm_costs_stats(days: int = 7, all_accounts: bool = False) -> dict:
    """Aggregate llm_call_log rows within the last `days` days. `all_accounts` (owner only,
    checked by the route) sums every account's rows and adds a per-account breakdown."""
    from datetime import datetime, timedelta, timezone
    from backend.accounts.context import unscoped
    from backend.models.db import Account, LlmCallLog

    db = SessionLocal()
    try:
        q = db.query(LlmCallLog)
        if days and days > 0:  # days <= 0 → all time (no date filter)
            since = datetime.now(timezone.utc) - timedelta(days=days)
            q = q.filter(LlmCallLog.created_at >= since)
        if all_accounts:
            with unscoped():
                rows = q.all()
                names = {a.id: a.name for a in db.query(Account).all()}
        else:
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

        out = {
            "window_days": days,
            "total_calls": total_calls,
            "total_cost_usd": round(total_cost, 6),
            "by_purpose": sorted(by_purpose, key=lambda x: -x["cost_usd"]),
        }
        if all_accounts:
            per: dict = {}
            for r in rows:
                g = per.setdefault(r.account_id, {"account_id": str(r.account_id) if r.account_id else None,
                                                  "name": names.get(r.account_id, "Unknown"),
                                                  "calls": 0, "cost_usd": 0.0})
                g["calls"] += 1
                g["cost_usd"] += r.cost_usd or 0
            by_account = sorted(per.values(), key=lambda x: -x["cost_usd"])
            for g in by_account:
                g["cost_usd"] = round(g["cost_usd"], 6)
            out["all_accounts"] = True
            out["by_account"] = by_account
        return out
    finally:
        db.close()


@app.get("/api/stats/llm-costs", tags=["stats"], summary="LLM cost + cache hit stats")
async def llm_costs(days: int = 7, all_accounts: bool = False):
    """Returns spend and cache hit rate aggregated by (purpose, provider, model) for the last N days, for the calling account. `all_accounts=1` (owner only, 403 for members) sums every account and adds `by_account`."""
    if all_accounts:
        from backend.accounts.settings import acts_as_owner
        db = SessionLocal()
        try:
            allowed = acts_as_owner(db)
        finally:
            db.close()
        if not allowed:
            raise HTTPException(status_code=403, detail="owner_only")
    return _llm_costs_stats(days=days, all_accounts=all_accounts)


@app.get("/api/stats", tags=["stats"], summary="Dashboard statistics")
def get_stats():
    """Aggregate counts: total jobs, new jobs, saved jobs, total applications, and application status breakdown."""
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
        }
    finally:
        db.close()
