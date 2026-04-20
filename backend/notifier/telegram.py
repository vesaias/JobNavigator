"""Telegram bot — alerts, inline buttons, daily digest, email response alerts."""
import json
import logging
from datetime import datetime, timezone, timedelta

import httpx

from backend.config import TELEGRAM_BOT_TOKEN
from backend.models.db import SessionLocal, Setting, Job, Application

logger = logging.getLogger("jobnavigator.telegram")

BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def _get_chat_id() -> str:
    """Read chat_id from settings table."""
    db = SessionLocal()
    try:
        row = db.query(Setting).filter(Setting.key == "telegram_chat_id").first()
        return row.value if row and row.value else ""
    finally:
        db.close()


def _is_enabled() -> bool:
    """Check if Telegram is enabled in settings."""
    db = SessionLocal()
    try:
        row = db.query(Setting).filter(Setting.key == "telegram_enabled").first()
        return row.value.lower() == "true" if row else True
    finally:
        db.close()


async def _send_message(chat_id: str, text: str, reply_markup: dict = None, parse_mode: str = "HTML") -> bool:
    """Send a Telegram message.

    Returns True on HTTP 200, False on any failure (missing config, network error,
    non-200 response). Callers that care about delivery can check the return value.
    """
    if not TELEGRAM_BOT_TOKEN or not chat_id:
        logger.warning("Telegram not configured (missing token or chat_id)")
        return False

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(f"{BASE_URL}/sendMessage", json=payload)
            if resp.status_code != 200:
                logger.error(f"Telegram send failed: {resp.text}")
                return False
            return True
    except Exception as e:
        logger.error(f"Telegram send error: {e}")
        return False


def _get_webhook_secret() -> str:
    """Read the webhook secret from settings. Returns empty string if missing."""
    db = SessionLocal()
    try:
        row = db.query(Setting).filter(Setting.key == "telegram_webhook_secret").first()
        return (row.value or "").strip() if row else ""
    finally:
        db.close()


async def register_webhook(public_url: str) -> dict:
    """Register the Telegram webhook with Telegram's API, passing `secret_token`.

    `public_url` must be the externally reachable URL that ends at
    `/api/telegram/webhook` (https only — Telegram refuses http).
    Returns the Telegram API response dict.
    """
    if not TELEGRAM_BOT_TOKEN:
        return {"ok": False, "error": "TELEGRAM_BOT_TOKEN not set"}
    secret = _get_webhook_secret()
    if not secret:
        return {"ok": False, "error": "telegram_webhook_secret not configured"}
    payload = {
        "url": public_url,
        "secret_token": secret,
        "allowed_updates": ["callback_query", "message"],
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(f"{BASE_URL}/setWebhook", json=payload)
            return resp.json()
    except Exception as e:
        logger.error(f"setWebhook failed: {e}")
        return {"ok": False, "error": str(e)}


def rotate_webhook_secret() -> str:
    """Regenerate the webhook secret. Returns the new value.

    Callers should re-register the webhook with Telegram after rotation so the
    next callback carries the new header value.
    """
    import secrets as _secrets
    new_value = _secrets.token_urlsafe(32)
    db = SessionLocal()
    try:
        row = db.query(Setting).filter(Setting.key == "telegram_webhook_secret").first()
        if row is None:
            row = Setting(
                key="telegram_webhook_secret",
                value=new_value,
                description="Auto-generated secret token validated on every /api/telegram/webhook call.",
            )
            db.add(row)
        else:
            row.value = new_value
        db.commit()
    finally:
        db.close()
    return new_value


def _format_salary(salary_min, salary_max):
    """Format salary range for display."""
    if not salary_min and not salary_max:
        return "Not listed"
    if salary_min and salary_max and salary_min != salary_max:
        return f"${salary_min:,}–${salary_max:,}"
    if salary_min:
        return f"${salary_min:,}"
    return f"${salary_max:,}"


def _format_h1b(verdict, lca_count=None, approval_rate=None):
    """Format H-1B verdict for display."""
    icons = {"likely": "✅", "possible": "⚠️", "unlikely": "🚫", "unknown": "❓"}
    icon = icons.get(verdict, "❓")
    parts = [f"{icon} H-1B: {(verdict or 'Unknown').title()}"]
    if lca_count:
        parts.append(f"({lca_count} LCAs")
        if approval_rate:
            parts.append(f", {approval_rate:.0f}% approval)")
        else:
            parts.append(")")
    return " ".join(parts)


async def send_job_alert(data: dict):
    """Send new job alert with inline buttons."""
    if not _is_enabled():
        return

    chat_id = _get_chat_id()
    if not chat_id:
        return

    job = data.get("job")
    if not job:
        return

    best_score = data.get("best_score", 0)

    # Build message
    salary_str = _format_salary(job.salary_min, job.salary_max)
    h1b_str = _format_h1b(
        job.h1b_verdict,
        job.h1b_company_lca_count,
        job.h1b_company_approval_rate,
    )
    jd_flag_str = f"🚫 JD Flag: {job.h1b_jd_snippet[:60]}" if job.h1b_jd_flag else ""

    location_str = job.location or "Unknown"
    if job.remote:
        location_str += " (Remote)"

    scores = job.cv_scores or {}
    scores_str = "  ".join(f"{k}:{v}" for k, v in scores.items()) if scores else "N/A"

    text = (
        f"🆕 <b>New Job — {best_score}% fit</b>\n\n"
        f"🏢 {job.company} · {job.title}\n"
        f"📍 {location_str}\n"
        f"💰 {salary_str}\n"
        f"{h1b_str}\n"
        f"📋 CVs: {scores_str}\n"
    )

    if jd_flag_str:
        text += f"{jd_flag_str}\n"

    # Inline keyboard buttons
    job_id = str(job.id)
    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "🔗 Open", "url": job.url or "https://example.com"},
                {"text": "💾 Save", "callback_data": f"save_{job_id}"},
                {"text": "❌ Skip", "callback_data": f"skip_{job_id}"},
                {"text": "✅ Applied", "callback_data": f"applied_{job_id}"},
            ]
        ]
    }

    await _send_message(chat_id, text, reply_markup)


async def send_email_alert(data: dict):
    """Send email response alert."""
    if not _is_enabled():
        return

    chat_id = _get_chat_id()
    if not chat_id:
        return

    company = data.get("company", "Unknown")
    response_type = data.get("type", "Unknown")
    role = data.get("role", "")
    snippet = data.get("snippet", "")

    type_icons = {
        "positive": "🟢 Positive",
        "rejection": "🔴 Rejection",
        "auto_reply": "⚪ Auto-reply",
        "ambiguous": "🟡 Ambiguous",
    }
    type_str = type_icons.get(response_type, f"❓ {response_type}")

    text = (
        f"📬 <b>Response — {company}</b>\n"
        f"Type: {type_str}  |  Role: {role}\n"
        f"<i>'{snippet[:200]}'</i>\n"
    )

    await _send_message(chat_id, text)


async def send_digest():
    """Send daily digest."""
    if not _is_enabled():
        return

    chat_id = _get_chat_id()
    if not chat_id:
        return

    db = SessionLocal()
    try:
        today = datetime.now(timezone.utc).date()
        yesterday = today - timedelta(days=1)
        yesterday_start = datetime.combine(yesterday, datetime.min.time()).replace(tzinfo=timezone.utc)

        # Count new jobs since yesterday
        new_jobs = db.query(Job).filter(Job.discovered_at >= yesterday_start).count()

        # Strong matches (score >= threshold)
        threshold_row = db.query(Setting).filter(Setting.key == "fit_score_threshold").first()
        threshold = int(threshold_row.value) if threshold_row else 60

        from sqlalchemy import text as sa_text
        strong = db.query(Job).filter(
            Job.discovered_at >= yesterday_start,
        ).filter(sa_text(
            "(SELECT COALESCE(MAX(v::numeric), 0) FROM jsonb_each_text(CASE WHEN jsonb_typeof(COALESCE(cv_scores, '{}'::jsonb)) = 'object' THEN cv_scores ELSE '{}'::jsonb END) AS t(k, v) WHERE v ~ '^[0-9]+(\\.[0-9]+)?$') >= :threshold"
        ).bindparams(threshold=threshold)).count()

        # Active applications
        active_statuses = ["applied", "screening", "phone_screen", "interview", "final_round"]
        active_apps = db.query(Application).filter(Application.status.in_(active_statuses)).count()

        # Responses (email updates) in last 24h
        responses = db.query(Application).filter(
            Application.last_email_received >= yesterday_start,
        ).count()

        text = (
            f"📊 <b>JobNavigator Daily — {today.strftime('%b %d')}</b>\n"
            f"🆕 New jobs: {new_jobs}  |  ⭐ Strong matches: {strong}\n"
            f"📬 Responses: {responses}  |  📋 Active apps: {active_apps}\n"
        )

        await _send_message(chat_id, text)

        from backend.activity import log_activity
        log_activity("telegram", f"Daily digest sent: {new_jobs} new jobs, {strong} strong matches", db=db)
        db.commit()

    finally:
        db.close()


async def send_test_message():
    """Send a test Telegram message."""
    chat_id = _get_chat_id()
    if not chat_id:
        return {"error": "No chat_id configured"}

    text = "🧪 <b>JobNavigator Test</b>\nTelegram integration is working!"
    await _send_message(chat_id, text)

    from backend.activity import log_activity
    log_activity("telegram", "Test message sent")

    return {"message": "Test sent"}


async def handle_callback(callback_data: str, message_id: int = None):
    """Handle inline button callbacks from Telegram."""
    db = SessionLocal()
    try:
        if callback_data.startswith("save_"):
            job_id = callback_data[5:]
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.saved = True
                job.status = "saved"
                db.commit()
                return "Job saved!"

        elif callback_data.startswith("skip_"):
            job_id = callback_data[5:]
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = "skip"
                db.commit()
                return "Job skipped."

        elif callback_data.startswith("applied_"):
            job_id = callback_data[8:]
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = "applied"
                # Create application record only if one doesn't already exist
                existing = db.query(Application).filter(Application.job_id == job.id).first()
                if not existing:
                    app = Application(job_id=job.id, status="applied",
                                     status_transitions=[{"from": None, "to": "applied", "at": datetime.now(timezone.utc).isoformat(), "source": "telegram"}])
                    db.add(app)
                db.commit()
                return "Marked as applied!"

        return "Unknown action"
    finally:
        db.close()
