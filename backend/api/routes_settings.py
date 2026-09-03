"""GET /settings and PATCH /settings endpoints."""
import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.models.db import get_db, Setting
from backend.scheduler import configure_scheduler
from backend.analyzer.cv_scorer import reset_scoring_semaphore
from backend.scraper._shared.dedup import reload_tracking_params

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])


_REDACT_SUFFIXES = ("_password", "_api_key", "_session_id", "_secret")
_REDACT_KEYS = {"dashboard_api_key", "gmail_refresh_token"}


@router.get("")
def get_settings(db: Session = Depends(get_db)):
    """Return all settings as a key-value map. Sensitive values are redacted."""
    rows = db.query(Setting).all()
    result = {}
    for row in rows:
        # Redact secrets — return empty string if not set, "••••••" if set
        if row.key in _REDACT_KEYS or any(row.key.endswith(s) for s in _REDACT_SUFFIXES):
            result[row.key] = "" if not row.value else "\u2022" * 6
            continue
        # Try to parse JSON values
        try:
            result[row.key] = json.loads(row.value)
        except (json.JSONDecodeError, TypeError):
            result[row.key] = row.value
    return result


@router.patch("")
def update_settings(updates: dict, db: Session = Depends(get_db)):
    """Update one or more settings.

    Only keys the app actually reads are writable: the seeded defaults plus the
    handful written at runtime (seed.RUNTIME_SETTING_KEYS). A typo used to create
    a brand-new Setting row nothing ever reads (SET-28), so unknown keys are now
    rejected as a group with 400.

    Values are checked too (OPEN-01): integer keys must be whole and non-negative,
    `*_cron` keys must be empty or a 5-field expression APScheduler can parse, and
    enum keys must name a value their reader understands. A bad interval used to
    be written happily and then raise inside configure_scheduler() — after which
    the backend could not start.
    """
    from backend.seed import invalid_setting_values, unknown_setting_keys

    unknown = unknown_setting_keys(updates.keys())
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown setting: {', '.join(sorted(unknown))}",
        )

    # The redacted placeholder is never a real value — it is skipped below too.
    checkable = {k: v for k, v in updates.items()
                 if not (isinstance(v, str) and v == "•" * 6)}
    problems = invalid_setting_values(checkable)
    if problems:
        raise HTTPException(
            status_code=400,
            detail="Invalid setting value — " + "; ".join(problems),
        )

    warnings: list[str] = []
    updated = []
    for key, value in updates.items():
        # Skip redacted placeholder values (don't overwrite real secrets with bullets)
        if isinstance(value, str) and value == "\u2022" * 6:
            continue
        setting = db.query(Setting).filter(Setting.key == key).first()
        if setting:
            setting.value = json.dumps(value) if isinstance(value, (list, dict, bool)) else str(value)
            updated.append(key)
        else:
            # Create new setting if it doesn't exist
            db.add(Setting(key=key, value=json.dumps(value) if isinstance(value, (list, dict, bool)) else str(value)))
            updated.append(key)
    db.commit()

    # Reconfigure scheduler if timing settings changed
    timing_keys = {
        "scrape_interval_minutes", "email_check_interval_minutes",
        "backup_cron", "digest_cron", "h1b_cron", "cleanup_cron", "reject_cron",
    }
    if timing_keys & set(updated):
        try:
            configure_scheduler()
        except Exception as _e:
            warnings.append(f"configure_scheduler failed: {_e}")
            logger.exception("configure_scheduler failed after settings update")

    # Reset scoring semaphore if concurrency limit changed
    if "scoring_max_concurrent" in updated:
        try:
            reset_scoring_semaphore()
        except Exception as _e:
            warnings.append(f"reset_scoring_semaphore failed: {_e}")
            logger.exception("reset_scoring_semaphore failed after settings update")

    # Reset tailoring semaphore if its limit changed
    if "tailoring_max_concurrent" in updated:
        try:
            from backend.api.routes_resumes import reset_tailoring_semaphore
            reset_tailoring_semaphore()
        except Exception as _e:
            warnings.append(f"reset_tailoring_semaphore failed: {_e}")
            logger.exception("reset_tailoring_semaphore failed after settings update")

    # Reload dedup params cache if changed
    if "dedup_tracking_params" in updated:
        try:
            reload_tracking_params()
        except Exception as _e:
            warnings.append(f"reload_tracking_params failed: {_e}")
            logger.exception("reload_tracking_params failed after settings update")

    return {"updated": updated, "warnings": warnings}


@router.get("/defaults")
def get_defaults():
    """Seeded defaults, so an editor can offer "Reset to default" without
    hardcoding a second copy of every prompt in the frontend."""
    from backend.seed import DEFAULT_SETTINGS
    return {k: v[0] for k, v in DEFAULT_SETTINGS.items()}
