"""Aggregate feed health and manual controls."""
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.job_monitor import JobAlreadyRunningError, launch_background
from backend.models.db import ApplicationQueueItem, JobFeedCheckpoint, Setting, get_db

router = APIRouter(prefix="/job-feeds", tags=["job-feeds"])


@router.get("/status")
def get_status(db: Session = Depends(get_db)):
    settings = {
        row.key: row.value
        for row in db.query(Setting).filter(Setting.key.in_([
            "job_feeds_enabled", "job_feeds_interval_minutes",
            "job_feeds_worker_interval_minutes", "job_feeds_artifact_dir",
        ])).all()
    }
    queue_counts = {
        status: count
        for status, count in db.query(
            ApplicationQueueItem.status, func.count(ApplicationQueueItem.id)
        ).group_by(ApplicationQueueItem.status).all()
    }
    sources = []
    for row in db.query(JobFeedCheckpoint).order_by(JobFeedCheckpoint.repository_id).all():
        sources.append({
            "repository_id": row.repository_id,
            "last_commit_sha": row.last_commit_sha,
            "last_checked_at": row.last_checked_at.isoformat() if row.last_checked_at else None,
            "last_changed_at": row.last_changed_at.isoformat() if row.last_changed_at else None,
            "last_success_at": row.last_success_at.isoformat() if row.last_success_at else None,
            "upstream_updated_at": row.upstream_updated_at.isoformat() if row.upstream_updated_at else None,
            "consecutive_errors": row.consecutive_errors or 0,
            "last_error": row.last_error,
        })
    return {"settings": settings, "queue": queue_counts, "sources": sources}


@router.post("/run", status_code=202)
async def run_now():
    from backend.automation.speedyapply_pipeline import run_job_feed_poll

    try:
        run_id = launch_background(
            "job_feed_poll",
            run_job_feed_poll,
            trigger="manual",
            func_kwargs={"trigger": "manual", "force": True},
        )
        return {"run_id": run_id, "status": "running"}
    except JobAlreadyRunningError as exc:
        return {"status": "already_running", "detail": str(exc)}
