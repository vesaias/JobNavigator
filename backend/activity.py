"""Activity log helper — logs system events to the activity_log_v2 table."""
import logging
from backend.models.db import SessionLocal, ActivityLog

logger = logging.getLogger("jobnavigator.activity")


def log_activity(type: str, message: str, company: str = None, details: dict = None, db=None):
    """Log an activity event. Creates own session if db not provided."""
    own_session = db is None
    if own_session:
        db = SessionLocal()
    try:
        entry = ActivityLog(
            type=type,
            message=message,
            company=company,
            details=details,
        )
        db.add(entry)
        if own_session:
            db.commit()
        else:
            db.flush()
    except Exception as e:
        logger.warning(f"Failed to log activity: {e}")
        if own_session:
            db.rollback()
    finally:
        if own_session:
            db.close()
