"""Cover-letter CRUD, PDF export, and background AI generation.

Mirrors routes_resumes.py. Reuses the warm Playwright browser singleton
(_get_browser) and the font-embedding render pattern. Tracer-link rewriting is
NOT applied here (TracerLink is FK-bound to resumes); cover-letter header links
render as-is.
"""
import json
import logging
import uuid as _uuid
from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response, JSONResponse
from sqlalchemy.orm import Session

from backend.models.db import get_db, CoverLetter, Resume, Job, Setting, Persona, SessionLocal
from backend.job_monitor import launch_background, JobAlreadyRunningError
from backend.api.routes_resumes import _get_browser  # shared warm browser

logger = logging.getLogger("jobnavigator.cover_letters")

router = APIRouter(prefix="/cover-letters", tags=["cover-letters"])

TEMPLATES_DIR = Path(__file__).parent.parent / "cover_letter_templates"


# ── Templates ─────────────────────────────────────────────────────────────────

def _discover_templates() -> list[dict]:
    templates = []
    if not TEMPLATES_DIR.exists():
        return templates
    for d in sorted(TEMPLATES_DIR.iterdir()):
        if d.is_dir() and (d / "template.html.j2").exists():
            meta = {"id": d.name, "name": d.name.replace("_", " ").title(), "description": ""}
            meta_file = d / "meta.json"
            if meta_file.exists():
                try:
                    with open(meta_file) as f:
                        meta.update(json.load(f))
                        meta["id"] = d.name
                except Exception:
                    pass
            templates.append(meta)
    return templates


def _default_template_id() -> str:
    templates = _discover_templates()
    return templates[0]["id"] if templates else "garamond"


def _render_html(json_data: dict, template_name: str, page_format: str) -> str:
    """Render a cover letter to HTML via its Jinja2 template (fonts base64-embedded)."""
    import base64
    import re as _re
    from jinja2 import Environment, FileSystemLoader
    from markupsafe import Markup

    template_dir = TEMPLATES_DIR / template_name
    if not template_dir.exists():
        raise HTTPException(status_code=400, detail=f"Template '{template_name}' not found")

    env = Environment(loader=FileSystemLoader(str(template_dir)))
    env.filters['bold'] = lambda text: Markup(
        _re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>',
                _re.sub(r'[<>&]', lambda m: {'<': '&lt;', '>': '&gt;', '&': '&amp;'}[m.group()], text or ''))
    )
    template = env.get_template("template.html.j2")

    fonts = {}
    fonts_dir = template_dir / "fonts"
    if fonts_dir.exists():
        for pattern in ("*.TTF", "*.ttf"):
            for font_file in fonts_dir.glob(pattern):
                with open(font_file, "rb") as f:
                    fonts[font_file.name] = "data:font/truetype;base64," + base64.b64encode(f.read()).decode()

    return template.render(**json_data, page_format=page_format, fonts=fonts)


@router.get("/templates")
def list_templates():
    return _discover_templates()


# ── Serialization ─────────────────────────────────────────────────────────────

def _to_dict(cl: CoverLetter, include_json_data: bool = False) -> dict:
    d = {
        "id": str(cl.id),
        "name": cl.name,
        "job_id": str(cl.job_id) if cl.job_id else None,
        "resume_id": str(cl.resume_id) if cl.resume_id else None,
        "parent_id": str(cl.parent_id) if cl.parent_id else None,
        "template": cl.template,
        "page_format": cl.page_format,
        "created_at": cl.created_at.isoformat() if cl.created_at else None,
        "updated_at": cl.updated_at.isoformat() if cl.updated_at else None,
    }
    if include_json_data:
        d["json_data"] = cl.json_data or {}
    return d


# ── CRUD ──────────────────────────────────────────────────────────────────────

@router.get("")
def list_cover_letters(job_id: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(CoverLetter).order_by(CoverLetter.updated_at.desc())
    if job_id:
        q = q.filter(CoverLetter.job_id == job_id)
    return [_to_dict(cl) for cl in q.all()]


@router.post("", status_code=201)
def create_cover_letter(body: dict, db: Session = Depends(get_db)):
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    cl = CoverLetter(
        name=name,
        job_id=body.get("job_id"),
        resume_id=body.get("resume_id"),
        parent_id=body.get("parent_id"),
        template=body.get("template", _default_template_id()),
        page_format=body.get("page_format", "letter"),
        json_data=body.get("json_data", {}),
    )
    db.add(cl)
    db.commit()
    db.refresh(cl)
    return _to_dict(cl, include_json_data=True)


@router.get("/{cl_id}")
def get_cover_letter(cl_id: str, db: Session = Depends(get_db)):
    cl = db.query(CoverLetter).filter(CoverLetter.id == cl_id).first()
    if not cl:
        raise HTTPException(404, "Cover letter not found")
    return _to_dict(cl, include_json_data=True)


@router.patch("/{cl_id}")
def update_cover_letter(cl_id: str, body: dict, db: Session = Depends(get_db)):
    cl = db.query(CoverLetter).filter(CoverLetter.id == cl_id).first()
    if not cl:
        raise HTTPException(404, "Cover letter not found")
    allowed = {"name", "template", "page_format", "json_data", "job_id", "resume_id"}
    for k, v in body.items():
        if k in allowed:
            setattr(cl, k, v)
    db.commit()
    db.refresh(cl)
    return _to_dict(cl, include_json_data=True)


@router.delete("/{cl_id}")
def delete_cover_letter(cl_id: str, db: Session = Depends(get_db)):
    cl = db.query(CoverLetter).filter(CoverLetter.id == cl_id).first()
    if not cl:
        raise HTTPException(404, "Cover letter not found")
    db.delete(cl)
    db.commit()
    return {"deleted": cl_id}


# ── PDF export ────────────────────────────────────────────────────────────────

@router.get("/{cl_id}/pdf")
async def export_pdf(cl_id: str, db: Session = Depends(get_db)):
    cl = db.query(CoverLetter).filter(CoverLetter.id == cl_id).first()
    if not cl:
        raise HTTPException(404, "Cover letter not found")

    html = _render_html(cl.json_data or {}, cl.template, cl.page_format)
    fmt = cl.page_format or "letter"
    paper_format = "A4" if fmt.lower() == "a4" else "Letter"

    try:
        browser = await _get_browser()
        page = await browser.new_page()
        await page.set_content(html, wait_until="networkidle")
        pdf_bytes = await page.pdf(
            format=paper_format, print_background=True,
            margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
        )
        await page.close()
    except Exception as e:
        logger.error(f"Cover-letter PDF generation failed: {e}")
        raise HTTPException(500, f"PDF generation failed: {str(e)}")

    # Filename: {Name}_{Type}_CoverLetter_{number}.pdf
    header_name = (cl.json_data or {}).get("header", {}).get("name", "CoverLetter").replace(" ", "")
    base_type = (cl.name.split(" → ")[0] if " → " in (cl.name or "") else (cl.name or "Cover")).replace(" ", "")
    number = ""
    if cl.job_id:
        job = db.query(Job).filter(Job.id == cl.job_id).first()
        if job and job.short_id:
            number = f"_{job.short_id}"
    filename = f"{header_name}_{base_type}_CoverLetter{number}".encode("ascii", "replace").decode()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}.pdf"'},
    )


# ── AI generation ─────────────────────────────────────────────────────────────

@router.post("/generate", status_code=202)
async def generate_cover_letter(body: dict, db: Session = Depends(get_db)):
    """Generate a cover letter for a (resume, job) pair in the background.

    Body: {resume_id, job_id, voice?, length?, template?, page_format?}
    Returns 202 + run_id; the CoverLetter row appears when the job finishes.
    """
    resume_id = body.get("resume_id")
    job_id = body.get("job_id")
    if not resume_id or not job_id:
        raise HTTPException(400, "resume_id and job_id are required")

    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(404, "Resume not found")
    if not (resume.json_data or {}):
        raise HTTPException(400, "Resume has no content")

    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")
    if not (job.description or "").strip():
        raise HTTPException(400, "Job has no description")

    prompt_row = db.query(Setting).filter(Setting.key == "cover_letter_prompt").first()
    if not prompt_row or not (prompt_row.value or "").strip():
        raise HTTPException(500, "cover_letter_prompt setting is empty — configure it in Settings")

    scope = f"cl:{resume_id}:{job_id}"
    try:
        run_id = launch_background(
            "generate_cover_letter",
            _generate_impl,
            trigger="manual",
            scope_key=scope,
            target_job_id=_uuid.UUID(job_id) if isinstance(job_id, str) else job_id,
            func_kwargs={
                "resume_id": resume_id,
                "job_id": job_id,
                "voice": body.get("voice"),
                "length": body.get("length", "standard"),
                "template": body.get("template"),
                "page_format": body.get("page_format"),
            },
        )
        return {"run_id": run_id, "status": "running"}
    except JobAlreadyRunningError as e:
        return JSONResponse(status_code=409, content={"detail": f"{e.job_type} is already running for this pair"})


async def _generate_impl(resume_id: str, job_id: str, voice: str | None, length: str,
                         template: str | None, page_format: str | None):
    """Background worker: generate the letter and persist a CoverLetter row."""
    from backend.analyzer.cover_letter_generator import (
        resolve_voice_instruction, generate_cover_letter_body,
    )
    from backend.analyzer.llm_logger import track_llm_call

    db = SessionLocal()
    try:
        resume = db.query(Resume).filter(Resume.id == resume_id).first()
        job = db.query(Job).filter(Job.id == job_id).first()
        persona = db.query(Persona).filter(Persona.id == 1).first()
        if not resume or not job:
            raise RuntimeError("resume or job missing at execution time")

        prompt_template = db.query(Setting).filter(Setting.key == "cover_letter_prompt").first().value
        voice_id, voice_instruction = resolve_voice_instruction(db, voice)
        preferences = (persona.preferences if persona else {}) or {}

        _m = db.query(Setting).filter(Setting.key == "cover_letter_llm_model").first()
        _model = (_m.value if _m and _m.value else None) or "claude-sonnet-4-6"
        _p = db.query(Setting).filter(Setting.key == "cover_letter_llm_provider").first()
        _provider = (_p.value if _p and _p.value else None) or "claude_api"

        async with track_llm_call("cover_letter", _provider, _model, job_id=job_id) as _tracker:
            body = await generate_cover_letter_body(
                resume.json_data or {}, preferences, job.description or "",
                voice_instruction, length, prompt_template,
            )
            _tracker.usage = body.pop("_usage", _tracker.usage)

        # Assemble json_data: header from resume, recipient/date from job/company
        header = (resume.json_data or {}).get("header", {})
        today = date.today().strftime("%B %d, %Y")
        json_data = {
            "header": {"name": header.get("name", ""), "contact_items": header.get("contact_items", [])},
            "recipient": {"company": job.company or "", "manager": "", "address": ""},
            "date": today,
            "greeting": body["greeting"],
            "body_paragraphs": body["body_paragraphs"],
            "closing": body["closing"],
            "signature": body["signature"] or header.get("name", ""),
        }

        cl = CoverLetter(
            name=f"{resume.name} → {job.company} — {job.title}",
            job_id=job_id,
            resume_id=resume_id,
            template=template or resume.template or _default_template_id(),
            page_format=page_format or resume.page_format or "letter",
            json_data=json_data,
        )
        db.add(cl)
        db.commit()
        db.refresh(cl)
        logger.info(f"Cover letter {cl.id} generated for job {job_id} (voice={voice_id})")
    finally:
        db.close()
