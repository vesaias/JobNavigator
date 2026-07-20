"""Atomic, project-local application packet export."""
from __future__ import annotations

import csv
import io
import json
import os
import re
import shutil
import threading
import uuid
from pathlib import Path

import pdfplumber

from backend.models.db import ApplicationQueueItem, Job, Persona, Resume, SessionLocal, Setting, utcnow

_INDEX_LOCK = threading.Lock()
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _setting(db, key: str, default: str = "") -> str:
    row = db.query(Setting).filter(Setting.key == key).first()
    return row.value if row else default


def resolve_packet_root(db=None) -> Path:
    owns_db = db is None
    db = db or SessionLocal()
    try:
        configured = (_setting(db, "job_feeds_artifact_dir", "application-packets") or "application-packets").strip()
    finally:
        if owns_db:
            db.close()
    root = Path(configured)
    if not root.is_absolute():
        root = _PROJECT_ROOT / root
    return root.resolve()


def _safe_slug(value: str, limit: int = 48) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return (slug or "unknown")[:limit].rstrip("-")


def _number_tokens(value) -> set[str]:
    text = json.dumps(value or {}, ensure_ascii=False)
    return set(re.findall(r"(?<![A-Za-z])\d+(?:\.\d+)?%?", text))


def validate_tailored_resume(persona_data: dict, tailored_data: dict) -> list[str]:
    """Cheap deterministic guardrails; this is validation, not ATS scoring."""
    issues: list[str] = []
    base_exp = list((persona_data or {}).get("experience") or [])
    tailored_exp = list((tailored_data or {}).get("experience") or [])
    immutable = ("company", "title", "location", "date")
    if len(base_exp) != len(tailored_exp):
        issues.append("experience entries changed count or order")
    for index, base_entry in enumerate(base_exp):
        if index >= len(tailored_exp):
            break
        for key in immutable:
            if (base_entry.get(key) or "") != (tailored_exp[index].get(key) or ""):
                issues.append(f"experience {index + 1} changed immutable field {key}")
        if tailored_exp[index].get("suggested_bullets"):
            issues.append(f"experience {index + 1} contains speculative suggested bullets")

    if (persona_data or {}).get("education") != (tailored_data or {}).get("education"):
        issues.append("education changed")

    extra_numbers = _number_tokens(tailored_data) - _number_tokens(persona_data)
    if extra_numbers:
        issues.append("new numeric claims: " + ", ".join(sorted(extra_numbers)))

    persona_text = json.dumps(persona_data or {}, ensure_ascii=False).lower()
    for value in ((tailored_data or {}).get("skills") or {}).values():
        for skill in re.split(r"[,;|]", str(value)):
            normalized = skill.strip().lower()
            if normalized and normalized not in persona_text:
                issues.append(f"new or unsupported skill: {skill.strip()}")
    return issues


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        return "\n".join((page.extract_text() or "") for page in pdf.pages).strip()


def _packet_relative_path(path: Path) -> str:
    try:
        return path.relative_to(_PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path)


def _rebuild_index(root: Path) -> None:
    rows = []
    db = SessionLocal()
    try:
        records = db.query(ApplicationQueueItem, Job, Resume).join(
            Job, Job.id == ApplicationQueueItem.job_id
        ).join(
            Resume, Resume.id == ApplicationQueueItem.resume_id
        ).filter(
            ApplicationQueueItem.artifact_dir.isnot(None)
        ).order_by(ApplicationQueueItem.created_at.asc()).all()
        for item, job, resume in records:
            rows.append({
                "queue_item_id": str(item.id),
                "job_id": str(job.id),
                "resume_id": str(resume.id),
                "company": job.company or "",
                "title": job.title or "",
                "location": job.location or "",
                "status": item.status,
                "application_url": item.application_url or job.url or "",
                "source_feed": item.source_feed or "",
                "source_posted_at": item.source_posted_at.isoformat() if item.source_posted_at else "",
                "packet_dir": item.artifact_dir or "",
                "resume_file": f"{item.artifact_dir}/resume.pdf" if item.artifact_dir else "",
            })
    finally:
        db.close()

    root.mkdir(parents=True, exist_ok=True)
    target = root / "index.csv"
    temp = root / f".index-{uuid.uuid4().hex}.tmp"
    fieldnames = [
        "queue_item_id", "job_id", "resume_id", "company", "title", "location",
        "status", "application_url", "source_feed", "source_posted_at", "packet_dir", "resume_file",
    ]
    with temp.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temp, target)


async def export_application_packet(item_id: str) -> dict:
    """Render and atomically save one queue item's mapped packet."""
    item_uuid = uuid.UUID(str(item_id))
    db = SessionLocal()
    try:
        item = db.query(ApplicationQueueItem).filter(ApplicationQueueItem.id == item_uuid).first()
        if not item or not item.resume_id:
            raise RuntimeError("Queue item has no tailored resume to export")
        job = db.query(Job).filter(Job.id == item.job_id).first()
        resume = db.query(Resume).filter(Resume.id == item.resume_id).first()
        persona = db.query(Persona).filter(Persona.id == 1).first()
        if not job or not resume:
            raise RuntimeError("Queue item job or resume no longer exists")

        root = resolve_packet_root(db)
        day = (item.created_at or utcnow()).date().isoformat()
        stable_id = str(job.short_id) if job.short_id else str(job.id).split("-")[0]
        directory_name = f"{stable_id}_{_safe_slug(job.company)}_{_safe_slug(job.title)}"
        final_dir = (root / day / directory_name).resolve()
        if root not in final_dir.parents:
            raise RuntimeError("Unsafe application packet path")

        existing_meta = final_dir / "metadata.json"
        if existing_meta.exists():
            try:
                existing = json.loads(existing_meta.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                existing = {}
            if existing.get("queue_item_id") == str(item.id):
                item.artifact_dir = _packet_relative_path(final_dir)
                if item.status == "exporting":
                    item.status = existing.get("status") or "ready"
                db.commit()
                with _INDEX_LOCK:
                    _rebuild_index(root)
                return existing

        from backend.api.routes_resumes import render_resume_pdf_bytes

        pdf_bytes, page_count, _ = await render_resume_pdf_bytes(resume, db)
        try:
            pdf_text = _extract_pdf_text(pdf_bytes)
        except Exception as exc:
            pdf_text = ""
            pdf_extract_error = str(exc)
        else:
            pdf_extract_error = ""

        issues = validate_tailored_resume(
            (persona.resume_content if persona else {}) or {},
            resume.json_data or {},
        )
        if page_count != 1:
            issues.append(f"resume PDF has {page_count} pages")
        if len(pdf_text) < 100:
            issues.append("resume PDF text extraction is empty or too short")
        if pdf_extract_error:
            issues.append(f"resume PDF extraction failed: {pdf_extract_error}")
        packet_status = "ready" if not issues else "needs_review"

        metadata = {
            "queue_item_id": str(item.id),
            "job_id": str(job.id),
            "resume_id": str(resume.id),
            "company": job.company,
            "title": job.title,
            "location": job.location,
            "application_url": item.application_url or job.url,
            "source_feeds": sorted({posting.source_id for posting in job.feed_postings}),
            "source_posted_at": item.source_posted_at.isoformat() if item.source_posted_at else None,
            "detected_at": item.created_at.isoformat() if item.created_at else None,
            "generated_at": utcnow().isoformat(),
            "status": packet_status,
            "validation_issues": issues,
            "resume_file": "resume.pdf",
            "job_file": "job.md",
        }
        job_markdown = (
            f"# {job.company or 'Unknown company'} - {job.title or 'Unknown role'}\n\n"
            f"- Location: {job.location or 'Unknown'}\n"
            f"- Application: {item.application_url or job.url or ''}\n"
            f"- Sources: {', '.join(metadata['source_feeds'])}\n"
            f"- Detected: {metadata['detected_at'] or ''}\n\n"
            f"## Job description\n\n{job.description or 'Job description unavailable.'}\n"
        )

        final_dir.parent.mkdir(parents=True, exist_ok=True)
        temp_dir = final_dir.parent / f".{directory_name}-{uuid.uuid4().hex}.tmp"
        temp_dir.mkdir(parents=False, exist_ok=False)
        try:
            (temp_dir / "resume.pdf").write_bytes(pdf_bytes)
            (temp_dir / "resume.json").write_text(
                json.dumps(resume.json_data or {}, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            (temp_dir / "job.md").write_text(job_markdown, encoding="utf-8")
            (temp_dir / "metadata.json").write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            if final_dir.exists():
                raise RuntimeError(f"Application packet path already exists: {final_dir}")
            os.replace(temp_dir, final_dir)
        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

        item.artifact_dir = _packet_relative_path(final_dir)
        item.status = packet_status
        if issues:
            item.eligibility_warnings = list(item.eligibility_warnings or []) + issues
        item.error = None
        db.commit()
    finally:
        db.close()

    with _INDEX_LOCK:
        _rebuild_index(root)
    return metadata
