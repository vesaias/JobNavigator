"""APScheduler — reads all timing config from settings DB table. No hardcoded schedules."""
import logging
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from backend.models.db import SessionLocal, Setting

logger = logging.getLogger("jobnavigator.scheduler")

scheduler = AsyncIOScheduler()


def get_setting(db, key, default=None):
    """Read a setting value from DB."""
    row = db.query(Setting).filter(Setting.key == key).first()
    if row:
        return row.value
    return default


def configure_scheduler():
    """Read all intervals from settings table and configure scheduler jobs.
    Called at startup and after any settings update.
    """
    db = SessionLocal()
    try:
        scrape_interval = int(get_setting(db, "scrape_interval_minutes", "0"))
        email_interval = int(get_setting(db, "email_check_interval_minutes", "0"))
        backup_cron = get_setting(db, "backup_cron", "").strip()
        digest_cron = get_setting(db, "digest_cron", "").strip()
        h1b_cron = get_setting(db, "h1b_cron", "").strip()
        cleanup_cron = get_setting(db, "cleanup_cron", "").strip()
        reject_cron = get_setting(db, "reject_cron", "").strip()
    finally:
        db.close()

    def _add_cron_job(func, job_id, cron_expr):
        """Parse a 5-field cron expression and add to scheduler. Empty = skip."""
        if not cron_expr:
            return
        try:
            parts = cron_expr.split()
            if len(parts) == 5:
                scheduler.add_job(
                    func,
                    CronTrigger(minute=parts[0], hour=parts[1], day=parts[2], month=parts[3], day_of_week=parts[4]),
                    id=job_id,
                    replace_existing=True,
                )
            else:
                logger.warning(f"Invalid cron for {job_id}: '{cron_expr}' (need 5 fields)")
        except Exception as e:
            logger.warning(f"Invalid cron for {job_id}: '{cron_expr}': {e}")

    # Remove existing jobs before reconfiguring
    scheduler.remove_all_jobs()

    # Interval-based jobs (0 = disabled)
    if scrape_interval > 0:
        scheduler.add_job(
            run_all_scrapes,
            IntervalTrigger(minutes=scrape_interval),
            id="scrape_all",
            replace_existing=True,
        )

    if email_interval > 0:
        scheduler.add_job(
            run_email_check,
            IntervalTrigger(minutes=email_interval),
            id="email_check",
            replace_existing=True,
        )

    # Cron-based jobs (empty = disabled)
    _add_cron_job(run_db_backup, "db_backup", backup_cron)
    _add_cron_job(send_daily_digest, "daily_digest", digest_cron)
    _add_cron_job(refresh_h1b_data, "h1b_refresh", h1b_cron)
    _add_cron_job(run_job_cleanup_auto, "job_cleanup", cleanup_cron)
    _add_cron_job(run_auto_reject, "auto_reject", reject_cron)

    logger.info(
        f"Scheduler configured: scrape every {scrape_interval}m, "
        f"email every {email_interval}m, {len(scheduler.get_jobs())} total jobs"
    )


# ── Job stubs (implementations added in later phases) ────────────────────────
async def run_all_scrapes():
    from backend.job_monitor import tracked_run, JobAlreadyRunningError
    try:
        async with tracked_run("scrape_all", "scheduler"):
            logger.info("Running all scrapes...")
            from backend.scraper.orchestrator import run_all
            await run_all()
            # CV scoring happens per-search/company based on their auto_scoring_depth setting
            # Also score any saved-but-unscored jobs (from manual saves)
            from backend.analyzer.cv_scorer import analyze_unscored_jobs
            await analyze_unscored_jobs(status="saved")
            # Check for repeated scrape failures
            await check_scrape_health()
    except JobAlreadyRunningError as e:
        logger.warning(f"Scheduler skipped: {e}")


async def run_email_check():
    from backend.job_monitor import tracked_run, JobAlreadyRunningError
    try:
        async with tracked_run("email_check", "scheduler"):
            logger.info("Running email check...")
            from backend.email_monitor.gmail_client import check_emails
            await check_emails()
    except JobAlreadyRunningError as e:
        logger.warning(f"Scheduler skipped: {e}")


async def send_daily_digest():
    from backend.job_monitor import tracked_run, JobAlreadyRunningError
    try:
        async with tracked_run("daily_digest", "scheduler"):
            logger.info("Sending daily digest...")
            from backend.notifier.telegram import send_digest
            await send_digest()
    except JobAlreadyRunningError as e:
        logger.warning(f"Scheduler skipped: {e}")


async def refresh_h1b_data():
    from backend.job_monitor import tracked_run, JobAlreadyRunningError
    try:
        async with tracked_run("h1b_refresh", "scheduler"):
            logger.info("Refreshing H-1B data...")
            from backend.analyzer.h1b_checker import refresh_all_h1b
            await refresh_all_h1b()
    except JobAlreadyRunningError as e:
        logger.warning(f"Scheduler skipped: {e}")


async def run_auto_reject():
    """Move old non-rejected/non-offer applications to rejected after X days."""
    from backend.job_monitor import tracked_run, JobAlreadyRunningError
    try:
        async with tracked_run("auto_reject", "scheduler"):
            db = SessionLocal()
            try:
                setting = db.query(Setting).filter(Setting.key == "auto_reject_after_days").first()
                days = int(setting.value) if setting and setting.value else 0
                if days <= 0:
                    return

                from backend.models.db import Application, record_transition
                cutoff = datetime.now(timezone.utc) - timedelta(days=days)
                keep_statuses = ["rejected", "offer"]
                stale = db.query(Application).filter(
                    ~Application.status.in_(keep_statuses),
                    Application.applied_at < cutoff,
                ).all()

                count = 0
                for app in stale:
                    record_transition(app, "rejected", "scheduler")
                    count += 1

                if count:
                    db.commit()
                    logger.info(f"Auto-rejected {count} applications (>{days} days)")
            finally:
                db.close()
    except JobAlreadyRunningError as e:
        logger.warning(f"Scheduler skipped: {e}")


async def run_job_cleanup_auto():
    """Auto-delete old skipped jobs if job_archive_after_days > 0."""
    from backend.job_monitor import tracked_run, JobAlreadyRunningError
    try:
        async with tracked_run("job_cleanup", "scheduler"):
            db = SessionLocal()
            try:
                setting = db.query(Setting).filter(Setting.key == "job_archive_after_days").first()
                days = int(setting.value) if setting and setting.value else 0
                if days <= 0:
                    return

                from backend.models.db import Job
                cutoff = datetime.now(timezone.utc) - timedelta(days=days)
                old_jobs = db.query(Job).filter(Job.status == "skip", Job.discovered_at < cutoff).all()
                count = len(old_jobs)
                for j in old_jobs:
                    db.delete(j)
                if count:
                    db.commit()
                    logger.info(f"Job cleanup: deleted {count} skipped jobs (>{days} days)")
            finally:
                db.close()
    except JobAlreadyRunningError as e:
        logger.warning(f"Scheduler skipped: {e}")
    finally:
        db.close()


async def check_scrape_health():
    """Alert via Telegram if any scraper has failed 3+ times consecutively."""
    from backend.models.db import ScrapeLog
    db = SessionLocal()
    try:
        sources = db.query(ScrapeLog.source).distinct().all()
        alerts = []
        for (source,) in sources:
            recent = db.query(ScrapeLog).filter(
                ScrapeLog.source == source
            ).order_by(ScrapeLog.ran_at.desc()).limit(3).all()
            if len(recent) >= 3 and all(r.error or r.is_warning for r in recent):
                alerts.append(source)

        if alerts:
            try:
                from backend.notifier.telegram import _send_message, _is_enabled, _get_chat_id
                if _is_enabled():
                    chat_id = _get_chat_id()
                    if chat_id:
                        msg = "\u26a0\ufe0f Scrape health alert:\n" + "\n".join(f"\u2022 {s}: 3 consecutive failures/empty results" for s in alerts)
                        await _send_message(chat_id, msg)
            except Exception as e:
                logger.error(f"Failed to send scrape health alert: {e}")
    finally:
        db.close()


async def run_db_backup():
    """Run pg_dump and keep max 5 backup files."""
    from backend.job_monitor import tracked_run, JobAlreadyRunningError
    try:
        async with tracked_run("db_backup", "scheduler"):
            import subprocess
            import glob
            import os
            from backend.config import DATABASE_URL
            from urllib.parse import urlparse

            backup_dir = "/app/backups"
            os.makedirs(backup_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = f"{backup_dir}/jobnavigator_{timestamp}.sql"

            # Parse DATABASE_URL for pg_dump
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
                logger.error(f"pg_dump failed: {result.stderr}")
                return

            logger.info(f"Database backup created: {backup_file}")

            # Keep only last 5 backups
            backups = sorted(glob.glob(f"{backup_dir}/jobnavigator_*.sql"))
            while len(backups) > 5:
                oldest = backups.pop(0)
                os.remove(oldest)
                logger.info(f"Removed old backup: {oldest}")
    except JobAlreadyRunningError as e:
        logger.warning(f"Scheduler skipped: {e}")


