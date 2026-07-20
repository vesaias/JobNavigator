"""Idempotent two-stage email notifications for aggregate feed jobs."""
from __future__ import annotations

import asyncio
import html
import logging
import uuid

from backend.models.db import (
    ApplicationQueueItem,
    Job,
    JobFeedPosting,
    Persona,
    SessionLocal,
    Setting,
    utcnow,
)

logger = logging.getLogger("jobnavigator.notifier.email")
_TERMINAL = {"ready", "needs_review", "ineligible", "failed"}
_dispatch_lock = asyncio.Lock()


def _setting(db, key: str, default: str = "") -> str:
    row = db.query(Setting).filter(Setting.key == key).first()
    return row.value if row else default


def _enabled(db) -> bool:
    return _setting(db, "job_feeds_email_enabled", "true").strip().lower() in {"1", "true", "yes", "on"}


def _recipient(db) -> str:
    configured = _setting(db, "job_feeds_notification_email", "").strip()
    if configured:
        return configured
    persona = db.query(Persona).filter(Persona.id == 1).first()
    return str(((persona.contact if persona else {}) or {}).get("email") or "").strip()


def _job_sources(job: Job) -> list[str]:
    return sorted({posting.source_id for posting in job.feed_postings})


async def send_detected_notification(item_id: str) -> bool:
    db = SessionLocal()
    try:
        item = db.query(ApplicationQueueItem).filter(
            ApplicationQueueItem.id == uuid.UUID(str(item_id))
        ).first()
        if not item or item.detected_notified_at or not _enabled(db):
            return bool(item and item.detected_notified_at)
        job = db.query(Job).filter(Job.id == item.job_id).first()
        recipient = _recipient(db)
        if not job or not job.feed_postings or not recipient:
            return False
        sources = _job_sources(job)
        warnings = list(item.eligibility_warnings or [])
        subject = f"[New Job] {job.company or 'Unknown'} - {job.title or 'Unknown role'}"
        application_url = item.application_url or job.url or ""
        text = (
            f"New aggregate-feed job detected.\n\n"
            f"Company: {job.company or 'Unknown'}\nRole: {job.title or 'Unknown'}\n"
            f"Location: {job.location or 'Unknown'}\nSources: {', '.join(sources)}\n"
            f"Application: {application_url}\n"
            f"Status: {item.status}\n"
        )
        if warnings:
            text += "Review notes: " + "; ".join(warnings) + "\n"
        body = (
            f"<h2>{html.escape(job.company or 'Unknown')} - {html.escape(job.title or 'Unknown role')}</h2>"
            f"<p><b>Location:</b> {html.escape(job.location or 'Unknown')}<br>"
            f"<b>Sources:</b> {html.escape(', '.join(sources))}<br>"
            f"<b>Status:</b> {html.escape(item.status)}</p>"
            f"<p><a href=\"{html.escape(application_url, quote=True)}\">Open application</a></p>"
        )
        if warnings:
            body += "<p><b>Review notes:</b> " + html.escape("; ".join(warnings)) + "</p>"
    finally:
        db.close()

    from backend.email_monitor.gmail_client import send_gmail_message
    sent = await send_gmail_message(recipient, subject, text, body)
    if sent:
        db = SessionLocal()
        try:
            item = db.query(ApplicationQueueItem).filter(
                ApplicationQueueItem.id == uuid.UUID(str(item_id)),
                ApplicationQueueItem.detected_notified_at.is_(None),
            ).first()
            if item:
                item.detected_notified_at = utcnow()
                db.commit()
        finally:
            db.close()
    return sent


async def send_terminal_notification(item_id: str) -> bool:
    db = SessionLocal()
    try:
        item = db.query(ApplicationQueueItem).filter(
            ApplicationQueueItem.id == uuid.UUID(str(item_id))
        ).first()
        if not item or item.status not in _TERMINAL or item.terminal_notified_at or not _enabled(db):
            return bool(item and item.terminal_notified_at)
        if item.status == "failed" and (item.attempts or 0) < 3:
            return False
        job = db.query(Job).filter(Job.id == item.job_id).first()
        recipient = _recipient(db)
        if not job or not job.feed_postings or not recipient:
            return False
        application_url = item.application_url or job.url or ""
        label = {
            "ready": "Resume Ready",
            "needs_review": "Resume Needs Review",
            "ineligible": "Job Skipped",
            "failed": "Preparation Failed",
        }[item.status]
        subject = f"[{label}] {job.company or 'Unknown'} - {job.title or 'Unknown role'}"
        notes = list(item.eligibility_warnings or [])
        if item.error:
            notes.append(item.error)
        packet = item.artifact_dir or "Not generated"
        text = (
            f"{label}\n\nCompany: {job.company or 'Unknown'}\nRole: {job.title or 'Unknown'}\n"
            f"Status: {item.status}\nApplication: {application_url}\nPacket: {packet}\n"
        )
        if notes:
            text += "Notes: " + "; ".join(notes) + "\n"
        body = (
            f"<h2>{html.escape(label)}</h2>"
            f"<p><b>{html.escape(job.company or 'Unknown')}</b> - {html.escape(job.title or 'Unknown role')}<br>"
            f"<b>Status:</b> {html.escape(item.status)}<br>"
            f"<b>Local packet:</b> <code>{html.escape(packet)}</code></p>"
            f"<p><a href=\"{html.escape(application_url, quote=True)}\">Open application</a></p>"
        )
        if notes:
            body += "<p><b>Notes:</b> " + html.escape("; ".join(notes)) + "</p>"
    finally:
        db.close()

    from backend.email_monitor.gmail_client import send_gmail_message
    sent = await send_gmail_message(recipient, subject, text, body)
    if sent:
        db = SessionLocal()
        try:
            item = db.query(ApplicationQueueItem).filter(
                ApplicationQueueItem.id == uuid.UUID(str(item_id)),
                ApplicationQueueItem.terminal_notified_at.is_(None),
            ).first()
            if item:
                item.terminal_notified_at = utcnow()
                db.commit()
        finally:
            db.close()
    return sent


async def dispatch_pending_notifications() -> dict:
    # Poll and packet-worker schedules can overlap. Serialize dispatch within the
    # backend process so both stages cannot send the same timestamp-null alert.
    async with _dispatch_lock:
        db = SessionLocal()
        try:
            feed_posting_exists = db.query(JobFeedPosting.id).filter(
                JobFeedPosting.job_id == ApplicationQueueItem.job_id
            ).exists()
            detected_ids = [
                str(row[0]) for row in db.query(ApplicationQueueItem.id).filter(
                    ApplicationQueueItem.detected_notified_at.is_(None),
                    feed_posting_exists,
                ).order_by(ApplicationQueueItem.created_at.asc()).all()
            ]
            terminal_ids = [
                str(row[0]) for row in db.query(ApplicationQueueItem.id).filter(
                    ApplicationQueueItem.status.in_(_TERMINAL),
                    ApplicationQueueItem.terminal_notified_at.is_(None),
                    feed_posting_exists,
                ).order_by(ApplicationQueueItem.updated_at.asc()).all()
            ]
        finally:
            db.close()
        detected = 0
        for item_id in detected_ids:
            if await send_detected_notification(item_id):
                detected += 1
        terminal = 0
        for item_id in terminal_ids:
            if await send_terminal_notification(item_id):
                terminal += 1
        return {"detected": detected, "terminal": terminal}
