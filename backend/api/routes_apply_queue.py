"""Ready-to-apply queue and SpeedyApply workflow controls."""
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from backend.job_monitor import JobAlreadyRunningError, launch_background
from backend.models.db import ApplicationQueueItem, Job, Resume, get_db

router = APIRouter(prefix="/apply-queue", tags=["apply-queue"])


def _serialize(item: ApplicationQueueItem, job: Job, resume: Resume) -> dict:
    resume_id = str(resume.id)
    return {
        "id": str(item.id),
        "status": item.status,
        "source_feed": item.source_feed,
        "attempts": item.attempts or 0,
        "error": item.error,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "acknowledged_at": item.acknowledged_at.isoformat() if item.acknowledged_at else None,
        "source_posted_at": item.source_posted_at.isoformat() if item.source_posted_at else None,
        "artifact_path": item.artifact_dir,
        "eligibility_warnings": item.eligibility_warnings or [],
        "detected_notified_at": item.detected_notified_at.isoformat() if item.detected_notified_at else None,
        "terminal_notified_at": item.terminal_notified_at.isoformat() if item.terminal_notified_at else None,
        "job_id": str(job.id),
        "company": job.company,
        "title": job.title,
        "location": job.location,
        "application_url": item.application_url or job.url,
        "resume_id": resume_id,
        "resume_name": resume.name,
        "resume_pdf_url": f"/api/resumes/{resume_id}/pdf",
        "packet_pdf_url": f"/api/apply-queue/{item.id}/packet-pdf" if item.artifact_dir else None,
        "resume_editor_url": f"/resumes?resume={resume_id}",
    }


@router.get("/ready")
def list_ready(unseen_only: bool = True, db: Session = Depends(get_db)):
    query = db.query(ApplicationQueueItem, Job, Resume).join(
        Job, Job.id == ApplicationQueueItem.job_id
    ).join(
        Resume, Resume.id == ApplicationQueueItem.resume_id
    ).filter(ApplicationQueueItem.status.in_(["ready", "needs_review"]))
    if unseen_only:
        query = query.filter(ApplicationQueueItem.acknowledged_at.is_(None))
    rows = query.order_by(ApplicationQueueItem.created_at.asc()).all()
    return {"total": len(rows), "items": [_serialize(item, job, resume) for item, job, resume in rows]}


@router.get("/{item_id}/packet-pdf")
def packet_pdf(item_id: str, db: Session = Depends(get_db)):
    """Serve the exact locally prepared PDF packet shown in the apply modal."""
    try:
        item_uuid = uuid.UUID(item_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid queue item ID")

    item = db.query(ApplicationQueueItem).filter(ApplicationQueueItem.id == item_uuid).first()
    if not item or not item.artifact_dir:
        raise HTTPException(status_code=404, detail="Application packet not found")

    project_root = Path(__file__).resolve().parents[2]
    packet_dir = Path(item.artifact_dir)
    if not packet_dir.is_absolute():
        packet_dir = project_root / packet_dir
    packet_dir = packet_dir.resolve()
    if project_root.resolve() not in packet_dir.parents:
        raise HTTPException(status_code=400, detail="Unsafe application packet path")

    pdf_path = packet_dir / "resume.pdf"
    if not pdf_path.is_file():
        raise HTTPException(status_code=404, detail="Application packet PDF not found")
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename="Yang_Yu_Generic_Software_Engineer_Resume.pdf",
    )


@router.post("/{item_id}/acknowledge")
def acknowledge(item_id: str, db: Session = Depends(get_db)):
    try:
        item_uuid = uuid.UUID(item_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid queue item ID")
    item = db.query(ApplicationQueueItem).filter(ApplicationQueueItem.id == item_uuid).first()
    if not item:
        raise HTTPException(status_code=404, detail="Application queue item not found")
    item.acknowledged_at = datetime.now(timezone.utc)
    db.commit()
    return {"acknowledged": True, "id": str(item.id)}


@router.post("/{item_id}/retry", status_code=202)
async def retry_item(item_id: str, db: Session = Depends(get_db)):
    try:
        item_uuid = uuid.UUID(item_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid queue item ID")
    item = db.query(ApplicationQueueItem).filter(ApplicationQueueItem.id == item_uuid).first()
    if not item:
        raise HTTPException(status_code=404, detail="Application queue item not found")

    from backend.automation.speedyapply_pipeline import prepare_queue_item
    try:
        run_id = launch_background(
            "speedyapply_prepare",
            prepare_queue_item,
            trigger="manual",
            scope_key=str(item.id),
            target_job_id=item.job_id,
            func_args=(str(item.id),),
            meta={"queue_item_id": str(item.id)},
        )
        return {"run_id": run_id, "status": "running"}
    except JobAlreadyRunningError as exc:
        return JSONResponse(status_code=409, content={"detail": str(exc)})


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
        return JSONResponse(status_code=409, content={"detail": str(exc)})
