"""Daily SpeedyApply import and resume-preparation workflow."""
from __future__ import annotations

import asyncio
import logging
import uuid

from backend.job_monitor import JobAlreadyRunningError, tracked_run
from backend.models.db import (
    ApplicationQueueItem,
    Job,
    Persona,
    Resume,
    SessionLocal,
    Setting,
    utcnow,
)

logger = logging.getLogger("jobnavigator.automation.speedyapply")


def _setting(db, key: str, default: str = "") -> str:
    row = db.query(Setting).filter(Setting.key == key).first()
    return row.value if row else default


def _as_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def resolve_base_resume_key(db) -> str | None:
    """Resolve the resume source for automatic tailoring.

    Order: feature-specific setting, global default, populated Persona, latest
    base Resume. Invalid configured IDs fall through instead of breaking every
    daily run after a resume is deleted.
    """
    candidates = [
        _setting(db, "job_feeds_resume_source", "").strip(),
        _setting(db, "speedyapply_resume_id", "").strip(),
        _setting(db, "default_resume_id", "").strip(),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        if candidate == "persona":
            persona = db.query(Persona).filter(Persona.id == 1).first()
            if persona and (persona.resume_content or {}):
                return "persona"
            continue
        try:
            resume_uuid = uuid.UUID(candidate)
        except (TypeError, ValueError):
            continue
        resume = db.query(Resume).filter(Resume.id == resume_uuid, Resume.is_base == True).first()
        if resume:
            return str(resume.id)

    persona = db.query(Persona).filter(Persona.id == 1).first()
    if persona and (persona.resume_content or {}):
        return "persona"

    resume = db.query(Resume).filter(Resume.is_base == True).order_by(Resume.updated_at.desc()).first()
    return str(resume.id) if resume else None


def enqueue_candidates(candidates: list[dict]) -> list[str]:
    """Create/reuse one durable queue item for each synced job."""
    db = SessionLocal()
    item_ids: list[str] = []
    try:
        base_key = resolve_base_resume_key(db)
        for candidate in candidates:
            try:
                job_uuid = uuid.UUID(str(candidate["job_id"]))
            except (KeyError, TypeError, ValueError):
                continue
            job = db.query(Job).filter(Job.id == job_uuid).first()
            if not job:
                continue
            item = db.query(ApplicationQueueItem).filter(ApplicationQueueItem.job_id == job.id).first()
            if not item:
                posted_at = candidate.get("source_posted_at")
                if isinstance(posted_at, str):
                    try:
                        from datetime import datetime
                        posted_at = datetime.fromisoformat(posted_at.replace("Z", "+00:00"))
                    except ValueError:
                        posted_at = None
                item = ApplicationQueueItem(
                    job_id=job.id,
                    base_resume_key=base_key,
                    source_feed=candidate.get("feed_id"),
                    application_url=candidate.get("application_url") or job.url,
                    status=candidate.get("status") or (
                        "pending_tailor" if (job.description or "").strip() else "pending_description"
                    ),
                    source_posted_at=posted_at,
                    priority=int(candidate.get("priority") or 10),
                    eligibility_warnings=candidate.get("eligibility_warnings") or [],
                )
                db.add(item)
                db.flush()
            else:
                if not item.base_resume_key and base_key:
                    item.base_resume_key = base_key
                if candidate.get("feed_id"):
                    item.source_feed = candidate["feed_id"]
                if candidate.get("application_url"):
                    item.application_url = candidate["application_url"]
                if candidate.get("source_posted_at") and not item.source_posted_at:
                    posted_at = candidate["source_posted_at"]
                    if isinstance(posted_at, str):
                        try:
                            from datetime import datetime
                            posted_at = datetime.fromisoformat(posted_at.replace("Z", "+00:00"))
                        except ValueError:
                            posted_at = None
                    item.source_posted_at = posted_at
                item.priority = max(item.priority or 10, int(candidate.get("priority") or 10))
                if candidate.get("eligibility_warnings"):
                    item.eligibility_warnings = candidate["eligibility_warnings"]
                if item.status == "pending_description" and (job.description or "").strip():
                    item.status = "pending_tailor"
                    item.error = None
            item_ids.append(str(item.id))
        db.commit()
    finally:
        db.close()
    return item_ids


async def run_job_feed_poll(trigger: str = "scheduler", *, force: bool = False) -> dict:
    """Fast monitor stage: poll changed repositories and enqueue candidates."""
    from backend.scraper.sources.job_feeds import sync_job_feeds

    sync_result = await sync_job_feeds(force=force)
    item_ids = enqueue_candidates(sync_result.get("queue_candidates", []))
    from backend.notifier.email import dispatch_pending_notifications
    notifications = await dispatch_pending_notifications()
    return {
        **sync_result,
        "queued": len(item_ids),
        "queue_item_ids": item_ids,
        "notifications": notifications,
    }


async def run_job_feed_worker(trigger: str = "scheduler") -> dict:
    """Prepare pending packets separately so LLM work never blocks polling."""
    db = SessionLocal()
    try:
        auto_tailor = _as_bool(_setting(db, "job_feeds_auto_tailor", "true"), default=True)
        try:
            limit = max(1, min(25, int(_setting(db, "job_feeds_max_jobs_per_poll", "25"))))
        except (TypeError, ValueError):
            limit = 25
        pending = db.query(ApplicationQueueItem).filter(
            ApplicationQueueItem.status.in_(["pending_description", "pending_tailor", "failed"]),
            ApplicationQueueItem.attempts < 3,
        ).order_by(
            ApplicationQueueItem.priority.desc(),
            ApplicationQueueItem.source_posted_at.desc(),
            ApplicationQueueItem.created_at.asc(),
        ).limit(limit).all()
        pending_ids = [str(item.id) for item in pending]
    finally:
        db.close()

    prepared = []
    if auto_tailor and pending_ids:
        prepared = await asyncio.gather(
            *[_prepare_tracked(item_id, trigger) for item_id in pending_ids]
        )
    from backend.notifier.email import dispatch_pending_notifications
    notifications = await dispatch_pending_notifications()
    return {
        "queued": len(pending_ids),
        "auto_tailor": auto_tailor,
        "prepared": prepared,
        "notifications": notifications,
    }


async def _fetch_description(url: str) -> str | None:
    from backend.scraper.ats._descriptions import _fetch_job_description

    return await _fetch_job_description(url)


async def _tailor_resume(base_resume_key: str, job_id: str) -> str:
    from backend.api.routes_resumes import _tailor_impl

    db = SessionLocal()
    try:
        prompt = _setting(db, "job_feeds_persona_prompt", "").strip() or None
    finally:
        db.close()
    resume_id = await _tailor_impl(
        base_resume_id=base_resume_key,
        job_id=job_id,
        job_description_override=None,
        score_depth_override="off",
        prompt_template_override=prompt if base_resume_key == "persona" else None,
        allow_suggested_bullets=False,
    )
    if not resume_id:
        raise RuntimeError("Resume tailoring completed without a resume ID")
    return str(resume_id)


def _mark_failed(item_id: str, exc: Exception) -> None:
    db = SessionLocal()
    try:
        item = db.query(ApplicationQueueItem).filter(ApplicationQueueItem.id == uuid.UUID(item_id)).first()
        if item:
            item.status = "failed"
            item.error = str(exc)[:2000]
            item.updated_at = utcnow()
            db.commit()
    finally:
        db.close()


async def _export_packet(item_id: str) -> dict:
    from backend.automation.application_packets import export_application_packet

    return await export_application_packet(item_id)


async def prepare_queue_item(item_id: str) -> str:
    """Prepare one queue item and return the tailored Resume ID."""
    db = SessionLocal()
    try:
        item = db.query(ApplicationQueueItem).filter(ApplicationQueueItem.id == uuid.UUID(item_id)).first()
        if not item:
            raise RuntimeError(f"Application queue item {item_id} no longer exists")
        job = db.query(Job).filter(Job.id == item.job_id).first()
        if not job:
            raise RuntimeError("Queued job no longer exists")

        if item.artifact_dir and item.status in {"ready", "needs_review"} and item.resume_id:
            return str(item.resume_id)

        resume_id: str | None = None
        if item.resume_id:
            existing = db.query(Resume).filter(Resume.id == item.resume_id).first()
            if existing:
                resume_id = str(existing.id)

        # Reuse any existing tailored resume for this job. This avoids spending
        # another LLM call when the user already tailored it manually.
        if not resume_id:
            existing = db.query(Resume).filter(
                Resume.job_id == job.id,
                Resume.is_base == False,
            ).order_by(Resume.updated_at.desc()).first()
            if existing:
                item.resume_id = existing.id
                resume_id = str(existing.id)

        base_key = item.base_resume_key or resolve_base_resume_key(db)
        if not resume_id and not base_key:
            item.status = "failed"
            item.attempts = (item.attempts or 0) + 1
            item.error = "No base resume or populated Persona is available for automatic tailoring"
            db.commit()
            raise RuntimeError(item.error)
        if base_key:
            item.base_resume_key = base_key
        item.attempts = (item.attempts or 0) + 1
        item.status = "exporting" if resume_id else "tailoring"
        item.error = None
        item.acknowledged_at = None
        job_id = str(job.id)
        job_url = job.url
        description_ready = bool((job.description or "").strip())
        db.commit()
    finally:
        db.close()

    try:
        if not resume_id and not description_ready:
            if not job_url:
                raise RuntimeError("Job has no application URL for description retrieval")
            description = await _fetch_description(job_url)
            if not (description or "").strip():
                raise RuntimeError("Could not retrieve a usable job description; will retry on the next run")
            update_db = SessionLocal()
            try:
                job = update_db.query(Job).filter(Job.id == uuid.UUID(job_id)).first()
                if not job:
                    raise RuntimeError("Queued job disappeared while fetching its description")
                job.description = description
                update_db.commit()
            finally:
                update_db.close()

        if not resume_id:
            resume_id = await _tailor_resume(base_key, job_id)
            finish_db = SessionLocal()
            try:
                item = finish_db.query(ApplicationQueueItem).filter(
                    ApplicationQueueItem.id == uuid.UUID(item_id)
                ).first()
                resume = finish_db.query(Resume).filter(Resume.id == uuid.UUID(resume_id)).first()
                if not item or not resume:
                    raise RuntimeError("Tailored resume could not be linked to the application queue")
                item.resume_id = resume.id
                item.status = "exporting"
                item.error = None
                item.acknowledged_at = None
                item.updated_at = utcnow()
                finish_db.commit()
            finally:
                finish_db.close()

        await _export_packet(item_id)
        return resume_id
    except Exception as exc:
        _mark_failed(item_id, exc)
        raise


async def _prepare_tracked(item_id: str, trigger: str) -> dict:
    lookup_db = SessionLocal()
    try:
        item = lookup_db.query(ApplicationQueueItem).filter(
            ApplicationQueueItem.id == uuid.UUID(item_id)
        ).first()
        target_job_id = item.job_id if item else None
    finally:
        lookup_db.close()

    try:
        async with tracked_run(
            "speedyapply_prepare",
            trigger=trigger,
            scope_key=item_id,
            meta={"queue_item_id": item_id},
            target_job_id=target_job_id,
        ):
            resume_id = await prepare_queue_item(item_id)
            status_db = SessionLocal()
            try:
                completed = status_db.query(ApplicationQueueItem).filter(
                    ApplicationQueueItem.id == uuid.UUID(item_id)
                ).first()
                status = completed.status if completed else "ready"
            finally:
                status_db.close()
            return {"item_id": item_id, "resume_id": resume_id, "status": status}
    except JobAlreadyRunningError as exc:
        return {"item_id": item_id, "status": "already_running", "error": str(exc)}
    except Exception as exc:
        logger.warning("SpeedyApply preparation failed for item %s: %s", item_id, exc)
        return {"item_id": item_id, "status": "failed", "error": str(exc)}


async def run_speedyapply_pipeline(trigger: str = "scheduler") -> dict:
    """Sync recent jobs and run bounded per-job resume workers."""
    from backend.scraper.sources.speedyapply import sync_speedyapply_jobs

    sync_result = await sync_speedyapply_jobs()
    enqueue_candidates(sync_result.get("queue_candidates", []))

    db = SessionLocal()
    try:
        auto_tailor = _as_bool(_setting(db, "speedyapply_auto_tailor", "true"), default=True)
        try:
            max_jobs = max(1, min(100, int(_setting(db, "speedyapply_max_jobs_per_run", "25"))))
        except (TypeError, ValueError):
            max_jobs = 25
        pending = db.query(ApplicationQueueItem).filter(
            ApplicationQueueItem.status.in_(["pending_description", "pending_tailor", "failed"])
        ).order_by(ApplicationQueueItem.created_at.asc()).limit(max_jobs).all()
        pending_ids = [str(item.id) for item in pending]
    finally:
        db.close()

    prepared = []
    if auto_tailor and pending_ids:
        prepared = await asyncio.gather(
            *[_prepare_tracked(item_id, trigger) for item_id in pending_ids]
        )

    return {
        **sync_result,
        "queued": len(pending_ids),
        "auto_tailor": auto_tailor,
        "prepared": prepared,
    }
