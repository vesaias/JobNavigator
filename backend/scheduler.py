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


def _int_setting(db, key: str) -> int:
    """A minutes-interval setting, or 0 (= disabled) if the stored value is junk.

    OPEN-01: PATCH /settings now rejects non-integer intervals, but a row written
    before that guard existed (or edited straight in the DB) must not take the
    process down — configure_scheduler() runs inside the app's lifespan, so an
    int() raising here meant the backend could not start at all. Log it loudly
    and leave that one job unscheduled instead.
    """
    raw = get_setting(db, key, "0")
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        logger.error(f"Setting '{key}' is not a whole number: {raw!r} — job disabled until it is fixed")
        return 0
    if value < 0:
        logger.error(f"Setting '{key}' is negative: {raw!r} — job disabled until it is fixed")
        return 0
    return value


def configure_scheduler():
    """Read all intervals from settings table and configure scheduler jobs.
    Called at startup and after any settings update.

    Every value is read defensively: a bad interval or cron skips its own job and
    logs an error, so one unparseable row can never stop the rest of the schedule
    (or the app) from coming up.
    """
    db = SessionLocal()
    try:
        scrape_interval = _int_setting(db, "scrape_interval_minutes")
        email_interval = _int_setting(db, "email_check_interval_minutes")
        backup_cron = str(get_setting(db, "backup_cron", "") or "").strip()
        digest_cron = str(get_setting(db, "digest_cron", "") or "").strip()
        h1b_cron = str(get_setting(db, "h1b_cron", "") or "").strip()
        cleanup_cron = str(get_setting(db, "cleanup_cron", "") or "").strip()
        reject_cron = str(get_setting(db, "reject_cron", "") or "").strip()
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
                logger.error(f"Invalid cron for {job_id}: '{cron_expr}' (need 5 fields) — job disabled until it is fixed")
        except Exception as e:
            logger.error(f"Invalid cron for {job_id}: '{cron_expr}': {e} — job disabled until it is fixed")

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


# ── Run summaries ───────────────────────────────────────────────────────────
# JobRun.result_summary is what Stats > Run history shows next to a run. These
# read back rows the run itself just wrote rather than threading counts up
# through every subsystem, so a summary can never disagree with the log.


def _scrape_summary(since) -> str:
    from backend.models.db import ScrapeLog
    db = SessionLocal()
    try:
        from backend.scraper.orchestrator import source_errors
        rows = db.query(ScrapeLog).filter(ScrapeLog.ran_at >= since).all()
        if not rows:
            return "No sources ran"
        found = sum(r.new_jobs or 0 for r in rows)
        failed = sum(1 for r in rows if r.error)
        # R3-A-03: a run where one configured board refused the request now sets
        # is_warning, but it is not "empty" — say which it is.
        bad_source = {r.id for r in rows if not r.error and source_errors(r.source_breakdown)}
        warned = sum(1 for r in rows if r.is_warning and not r.error and r.id not in bad_source)
        parts = [f"{len(rows)} source{'' if len(rows) == 1 else 's'}", f"+{found} new"]
        if failed:
            parts.append(f"{failed} failed")
        if bad_source:
            parts.append(f"{len(bad_source)} with a failed board")
        if warned:
            parts.append(f"{warned} empty")
        return " - ".join(parts)
    finally:
        db.close()


def _activity_summary(since, log_type: str, noun: str, plural: str = None) -> str:
    """Count the activity-log rows a run produced, e.g. "1 reply" / "3 replies".

    R3-A-07: the "+s" rule alone made the email summary read "1 repl" / "2 repls",
    because the only way to get "replies" out of it was to pass the stem. Pass an
    explicit `plural` whenever the plural is not just the noun plus an s.
    """
    from backend.models.db import ActivityLog
    db = SessionLocal()
    try:
        n = db.query(ActivityLog).filter(
            ActivityLog.created_at >= since, ActivityLog.type == log_type
        ).count()
        if not n:
            return ""
        return f"{n} {noun}" if n == 1 else f"{n} {plural or noun + 's'}"
    finally:
        db.close()


# ── Job stubs (implementations added in later phases) ────────────────────────
async def run_all_scrapes():
    from backend.job_monitor import tracked_run, JobAlreadyRunningError
    try:
        async with tracked_run("scrape_all", "scheduler") as run:
            logger.info("Running all scrapes...")
            started = datetime.now(timezone.utc)
            from backend.scraper.orchestrator import run_all
            await run_all()
            # CV scoring happens per-search/company based on their auto_scoring_depth setting
            # Also score any saved-but-unscored jobs (from manual saves)
            from backend.analyzer.cv_scorer import analyze_unscored_jobs
            await analyze_unscored_jobs(status="saved")
            # Check for repeated scrape failures
            await check_scrape_health()
            run.summary = _scrape_summary(started)
    except JobAlreadyRunningError as e:
        logger.warning(f"Scheduler skipped: {e}")


async def run_email_check():
    from backend.job_monitor import tracked_run, JobAlreadyRunningError
    try:
        async with tracked_run("email_check", "scheduler") as run:
            logger.info("Running email check...")
            started = datetime.now(timezone.utc)
            from backend.email_monitor.gmail_client import check_emails
            await check_emails()
            run.summary = _activity_summary(started, "email", "reply", "replies") or "No new replies"
    except JobAlreadyRunningError as e:
        logger.warning(f"Scheduler skipped: {e}")


async def send_daily_digest():
    from backend.job_monitor import tracked_run, JobAlreadyRunningError
    try:
        async with tracked_run("daily_digest", "scheduler") as run:
            logger.info("Sending daily digest...")
            started = datetime.now(timezone.utc)
            from backend.notifier.telegram import send_digest
            await send_digest()
            run.summary = _activity_summary(started, "telegram", "alert") or "Digest sent"
    except JobAlreadyRunningError as e:
        logger.warning(f"Scheduler skipped: {e}")


async def refresh_h1b_data():
    from backend.job_monitor import tracked_run, JobAlreadyRunningError
    try:
        async with tracked_run("h1b_refresh", "scheduler") as run:
            logger.info("Refreshing H-1B data...")
            from backend.models.db import VisaCache
            from backend.analyzer.h1b_checker import refresh_all_h1b
            started = datetime.now(timezone.utc)
            await refresh_all_h1b()
            _db = SessionLocal()
            try:
                # H-1B metrics live in VisaCache (keyed by company name), not on Company.
                refreshed = _db.query(VisaCache).filter(VisaCache.fetched_at >= started).count()
                with_data = _db.query(VisaCache).filter(VisaCache.has_data.is_(True)).count()
                run.summary = f"{refreshed} refreshed - {with_data} compan{'y' if with_data == 1 else 'ies'} with LCA data"
            finally:
                _db.close()
    except JobAlreadyRunningError as e:
        logger.warning(f"Scheduler skipped: {e}")


async def run_auto_reject():
    """Move old non-rejected/non-offer applications to rejected after X days."""
    from backend.job_monitor import tracked_run, JobAlreadyRunningError
    try:
        async with tracked_run("auto_reject", "scheduler") as run:
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
                run.summary = f"{count} application{'' if count == 1 else 's'} auto-rejected (>{days}d silent)"
            finally:
                db.close()
    except JobAlreadyRunningError as e:
        logger.warning(f"Scheduler skipped: {e}")


async def run_job_cleanup_auto():
    """Auto-delete old skipped jobs if job_archive_after_days > 0."""
    from backend.job_monitor import tracked_run, JobAlreadyRunningError
    try:
        async with tracked_run("job_cleanup", "scheduler") as run:
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
                run.summary = f"{count} skipped job{'' if count == 1 else 's'} deleted (>{days}d old)"
            finally:
                db.close()
    except JobAlreadyRunningError as e:
        logger.warning(f"Scheduler skipped: {e}")


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
        async with tracked_run("db_backup", "scheduler") as run:
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
            pruned = 0
            while len(backups) > 5:
                oldest = backups.pop(0)
                os.remove(oldest)
                pruned += 1
                logger.info(f"Removed old backup: {oldest}")

            size_mb = os.path.getsize(backup_file) / (1024 * 1024)
            run.summary = f"Snapshot {size_mb:.0f} MB -> {os.path.basename(backup_file)}"
            if pruned:
                run.summary += f" - {pruned} old pruned"
    except JobAlreadyRunningError as e:
        logger.warning(f"Scheduler skipped: {e}")


