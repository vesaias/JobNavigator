"""Resume builder CRUD, preview, PDF export, and PDF import endpoints."""
import io
import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from backend.models.db import get_db, Resume, TracerLink, TracerClickEvent, Setting, Job, utcnow

logger = logging.getLogger("jobnavigator.resumes")

router = APIRouter(prefix="/resumes", tags=["resumes"])

TEMPLATES_DIR = Path(__file__).parent.parent / "resume_templates"

# Warm Playwright browser singleton for fast PDF generation (~3-13ms warm vs ~500ms cold)
_pw_instance = None
_pw_browser = None

async def _get_browser():
    """Get or create a warm Playwright browser instance."""
    global _pw_instance, _pw_browser
    if _pw_browser and _pw_browser.is_connected():
        return _pw_browser
    from playwright.async_api import async_playwright
    _pw_instance = await async_playwright().start()
    _pw_browser = await _pw_instance.chromium.launch(headless=True, args=['--font-render-hinting=none'])
    logger.info("Warm Playwright browser started for PDF generation")
    return _pw_browser

def _default_template_id() -> str:
    """Return the first available template ID, or 'garamond' as last resort."""
    templates = _discover_templates()
    return templates[0]["id"] if templates else "garamond"


def _discover_templates() -> list[dict]:
    """Scan resume_templates/ for folders containing template.html.j2.
    Each folder can optionally include meta.json with 'name' and 'description'."""
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
                        meta["id"] = d.name  # folder name is always the ID
                except Exception:
                    pass
            templates.append(meta)
    return templates


# ── Helpers ─────────────────────────────────────────────────────────────────

def _render_html(json_data: dict, template_name: str, page_format: str) -> str:
    """Render a resume to HTML using its Jinja2 template."""
    from jinja2 import Environment, FileSystemLoader

    template_dir = TEMPLATES_DIR / template_name
    if not template_dir.exists():
        raise HTTPException(status_code=400, detail=f"Template '{template_name}' not found")

    import re as _re
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    from markupsafe import Markup
    env.filters['bold'] = lambda text: Markup(_re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', _re.sub(r'[<>&]', lambda m: {'<':'&lt;','>':'&gt;','&':'&amp;'}[m.group()], text or '')))
    template = env.get_template("template.html.j2")

    # Embed fonts as base64 data URIs (file:// blocked by Chromium in set_content)
    import base64
    fonts_dir = template_dir / "fonts"
    fonts = {}
    if fonts_dir.exists():
        for font_file in fonts_dir.glob("*.TTF"):
            with open(font_file, "rb") as f:
                fonts[font_file.name] = "data:font/truetype;base64," + base64.b64encode(f.read()).decode()
        for font_file in fonts_dir.glob("*.ttf"):
            with open(font_file, "rb") as f:
                fonts[font_file.name] = "data:font/truetype;base64," + base64.b64encode(f.read()).decode()

    html = template.render(
        **json_data,
        page_format=page_format,
        fonts_base="",
        fonts=fonts,
    )
    return html


def _rewrite_urls_with_tracers(json_data: dict, resume_id: str, db) -> dict:
    """Replace URLs in json_data with tracer redirect URLs. Returns modified copy."""
    import string, random, json as _json


    enabled_row = db.query(Setting).filter(Setting.key == "tracer_links_enabled").first()
    if not enabled_row or enabled_row.value != "true":
        return json_data

    base_url_row = db.query(Setting).filter(Setting.key == "tracer_links_base_url").first()
    base_url = (base_url_row.value if base_url_row else "").rstrip("/")
    if not base_url:
        return json_data

    style_row = db.query(Setting).filter(Setting.key == "tracer_links_url_style").first()
    url_style = style_row.value if style_row else "path"

    data = _json.loads(_json.dumps(json_data))  # deep copy
    header = data.get("header", {})

    items = header.get("contact_items", [])
    for i, item in enumerate(items):
        url = item.get("url")
        if not url or not url.strip() or url.startswith("mailto:"):
            continue

        label = item.get("text", f"Link {i+1}")

        # Ensure it's a full URL for the destination
        dest_url = url if url.startswith("http") else f"https://{url}"

        # Suffix for per-link distinction in job_id modes (user-defined stub or fallback to first 3 chars)
        label_suffix = item.get("stub") or label.lower()[:3]

        token = None
        # Determine token based on style
        if url_style in ("path_jobid", "param_jobid"):

            resume_obj = db.query(Resume).filter(Resume.id == resume_id).first()
            if resume_obj and resume_obj.job_id:
                job_obj = db.query(Job).filter(Job.id == resume_obj.job_id).first()
                if job_obj and job_obj.short_id:
                    token = f"{job_obj.short_id}{label_suffix}"

        # Find or create tracer link
        existing = db.query(TracerLink).filter(
            TracerLink.resume_id == resume_id,
            TracerLink.destination_url == dest_url,
        ).first()

        if existing:
            # Update token if style changed
            if token and existing.token != token:
                existing.token = token
                db.commit()
            if not token:
                token = existing.token
        else:
            # For job_id-based tokens, reuse existing token from a previous resume for the same job
            if token:
                existing_by_token = db.query(TracerLink).filter(TracerLink.token == token).first()
                if existing_by_token:
                    # Point the existing token to this new resume
                    existing_by_token.resume_id = resume_id
                    existing_by_token.destination_url = dest_url
                    existing_by_token.source_label = label
                    db.commit()
                else:
                    db.add(TracerLink(token=token, resume_id=resume_id, destination_url=dest_url, source_label=label))
                    db.commit()
            else:
                # Generate unique random token
                chars = string.ascii_lowercase + string.digits
                for _ in range(100):
                    token = ''.join(random.choices(chars, k=6))
                    if not db.query(TracerLink).filter(TracerLink.token == token).first():
                        break
                db.add(TracerLink(token=token, resume_id=resume_id, destination_url=dest_url, source_label=label))
                db.commit()

        if url_style in ("param", "param_jobid"):
            tracer_url = f"{base_url}?cv={token}"
        else:
            tracer_url = f"{base_url}/cv/{token}"

        items[i]["url"] = tracer_url

    data["header"] = header
    return data


def _resume_to_dict(r: Resume, include_json_data: bool = False) -> dict:
    """Serialize a Resume row to a dict."""
    d = {
        "id": str(r.id),
        "name": r.name,
        "is_base": r.is_base,
        "parent_id": str(r.parent_id) if r.parent_id else None,
        "job_id": str(r.job_id) if r.job_id else None,
        "template": r.template,
        "page_format": r.page_format,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }
    if include_json_data:
        d["json_data"] = r.json_data or {}
    return d


# ── Template listing ────────────────────────────────────────────────────────

@router.get("/templates")
def list_templates():
    """Return available resume templates (auto-discovered from filesystem)."""
    return _discover_templates()


# ── CRUD ────────────────────────────────────────────────────────────────────

@router.get("")
def list_resumes(is_base: Optional[bool] = None, db: Session = Depends(get_db)):
    """List all resumes. Optional filter: is_base=true for base resumes only."""
    q = db.query(Resume).order_by(Resume.updated_at.desc())
    if is_base is not None:
        q = q.filter(Resume.is_base == is_base)
    resumes = q.all()
    return [_resume_to_dict(r) for r in resumes]


@router.post("", status_code=201)
def create_resume(body: dict, db: Session = Depends(get_db)):
    """Create a new resume.

    Body: {name, is_base?, parent_id?, job_id?, template?, page_format?, json_data?}
    """
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    resume = Resume(
        name=name,
        is_base=body.get("is_base", True),
        parent_id=body.get("parent_id"),
        job_id=body.get("job_id"),
        template=body.get("template", _default_template_id()),
        page_format=body.get("page_format", "letter"),
        json_data=body.get("json_data", {}),
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return _resume_to_dict(resume, include_json_data=True)


@router.post("/copy")
def copy_resume_for_job(body: dict, db: Session = Depends(get_db)):
    """Copy a base resume for a job — no LLM, just exact copy with tracer links."""
    import json as _json
    base_resume_id = body.get("base_resume_id")
    job_id = body.get("job_id")
    if not base_resume_id or not job_id:
        raise HTTPException(400, "base_resume_id and job_id are required")

    base = db.query(Resume).filter(Resume.id == base_resume_id).first()
    if not base:
        raise HTTPException(404, "Base resume not found")


    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")

    job_name = f"{job.company} \u2014 {job.title}" if job.company else job.title or ""
    copy = Resume(
        name=f"{base.name} \u2192 {job_name}",
        is_base=False,
        parent_id=base.id,
        job_id=job_id,
        template=base.template,
        page_format=base.page_format,
        json_data=_json.loads(_json.dumps(base.json_data or {})),
    )
    db.add(copy)
    db.commit()
    db.refresh(copy)
    return _resume_to_dict(copy, include_json_data=True)


@router.post("/tailor")
async def tailor_resume(body: dict, db: Session = Depends(get_db)):
    """Tailor a base resume for a specific job description using LLM."""
    import re as _re

    base_resume_id = body.get("base_resume_id")
    job_id = body.get("job_id")
    job_description = body.get("job_description")

    if not base_resume_id:
        raise HTTPException(400, "base_resume_id is required")
    if not job_id and not job_description:
        raise HTTPException(400, "Either job_id or job_description is required")

    # Load base resume
    base = db.query(Resume).filter(Resume.id == base_resume_id).first()
    if not base:
        raise HTTPException(404, "Base resume not found")
    base_data = base.json_data or {}

    # Load job description
    jd_text = job_description or ""
    job_name = ""
    if job_id:
    
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise HTTPException(404, "Job not found")
        jd_text = job.description or ""
        job_name = f"{job.company} \u2014 {job.title}" if job.company else job.title or ""
        if not jd_text:
            raise HTTPException(400, "Job has no description")

    # Load prompt template from settings
    prompt_row = db.query(Setting).filter(Setting.key == "cv_tailor_prompt").first()
    if not prompt_row or not prompt_row.value:
        raise HTTPException(500, "cv_tailor_prompt setting is empty")
    prompt_template = prompt_row.value

    # Build prompt — send only tailorable sections as JSON
    import json as _json
    resume_sections = {
        "summary": base_data.get("summary", ""),
        "experience": base_data.get("experience", []),
        "skills": base_data.get("skills", {}),
    }
    prompt = prompt_template.replace("{resume_json}", _json.dumps(resume_sections, indent=2))
    prompt = prompt.replace("{job_description}", jd_text[:6000])

    system = "You are an expert resume tailor. Rewrite the resume to align with the job description using the JD's exact vocabulary. Do NOT invent experience, skills, or facts not present in the original resume. Only reformulate, reframe, and reorder existing content. If something is missing, map to the closest truthful concept."

    # Call LLM
    from backend.analyzer.llm_client import call_cv_tailor_llm
    try:
        _resp = await call_cv_tailor_llm(prompt, system, max_tokens=3000)
        raw = _resp["text"]
    except Exception as e:
        logger.error(f"CV tailoring LLM failed: {e}")
        raise HTTPException(500, f"LLM tailoring failed: {e}")

    # Parse JSON response
    try:
        text = raw.strip()
        match = _re.search(r'\{[\s\S]*\}', text)
        if match:
            text = match.group(0)
        llm_result = _json.loads(text)
    except _json.JSONDecodeError as e:
        logger.error(f"CV tailoring JSON parse failed: {e}. Raw: {raw[:500]}")
        raise HTTPException(500, "Failed to parse LLM response as JSON")

    # Merge: base sections + LLM-tailored sections
    tailored_data = _json.loads(_json.dumps(base_data))  # deep copy
    if "summary" in llm_result:
        tailored_data["summary"] = llm_result["summary"]
    if "experience" in llm_result:
        llm_exp = llm_result["experience"]
        base_exp = tailored_data.get("experience", [])
        for i, llm_job in enumerate(llm_exp):
            if i < len(base_exp):
                base_exp[i]["bullets"] = llm_job.get("bullets", base_exp[i].get("bullets", []))
                if llm_job.get("suggested_bullets"):
                    base_exp[i]["suggested_bullets"] = llm_job["suggested_bullets"]
                if llm_job.get("description") is not None:
                    base_exp[i]["description"] = llm_job["description"]
        tailored_data["experience"] = base_exp
    if "skills" in llm_result:
        tailored_data["skills"] = llm_result["skills"]

    # Create tailored resume
    name = f"{base.name} \u2192 {job_name}" if job_name else f"{base.name} (tailored)"
    tailored = Resume(
        name=name,
        is_base=False,
        parent_id=base.id,
        job_id=job_id,
        template=base.template,
        page_format=base.page_format,
        json_data=tailored_data,
    )
    db.add(tailored)
    db.commit()
    db.refresh(tailored)

    return _resume_to_dict(tailored, include_json_data=True)


@router.get("/{resume_id}")
def get_resume(resume_id: str, db: Session = Depends(get_db)):
    """Get a single resume with its full json_data."""
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    return _resume_to_dict(resume, include_json_data=True)


@router.patch("/{resume_id}")
def update_resume(resume_id: str, body: dict, db: Session = Depends(get_db)):
    """Update resume fields. Supports partial updates.

    Body: any subset of {name, is_base, parent_id, job_id, template, page_format, json_data}
    """
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    allowed = {"name", "is_base", "parent_id", "job_id", "template", "page_format", "json_data"}
    for key, value in body.items():
        if key in allowed:
            setattr(resume, key, value)

    resume.updated_at = utcnow()
    db.commit()
    db.refresh(resume)
    return _resume_to_dict(resume, include_json_data=True)


@router.delete("/{resume_id}")
def delete_resume(resume_id: str, db: Session = Depends(get_db)):
    """Delete a resume and cascade-delete its tailored children."""
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    # Delete tracer links + tailored children first
    children = db.query(Resume).filter(Resume.parent_id == resume_id).all()
    child_ids = [c.id for c in children]
    all_ids = [resume.id] + child_ids
    # Delete tracer links for this resume and all children
    db.query(TracerLink).filter(TracerLink.resume_id.in_(all_ids)).delete(synchronize_session=False)
    for child in children:
        db.delete(child)

    db.delete(resume)
    db.commit()
    return {"deleted": True, "id": resume_id, "children_deleted": len(children)}


# ── Preview & PDF ───────────────────────────────────────────────────────────

@router.get("/{resume_id}/preview")
def preview_resume(resume_id: str, db: Session = Depends(get_db)):
    """Render resume as HTML and return it for preview."""
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    json_data = resume.json_data or {}
    html = _render_html(json_data, resume.template, resume.page_format)
    return HTMLResponse(content=html)


@router.get("/{resume_id}/pdf")
async def export_pdf(resume_id: str, db: Session = Depends(get_db)):
    """Render resume as PDF via Playwright and return the bytes."""
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    json_data = resume.json_data or {}
    # Rewrite URLs with tracer links if enabled
    pdf_data = _rewrite_urls_with_tracers(json_data, str(resume.id), db)
    html = _render_html(pdf_data, resume.template, resume.page_format)

    # Determine paper format
    fmt = resume.page_format or "letter"
    paper_format = "A4" if fmt.lower() == "a4" else "Letter"

    try:
        browser = await _get_browser()
        page = await browser.new_page()
        await page.set_content(html, wait_until="networkidle")
        pdf_bytes = await page.pdf(
            format=paper_format,
            print_background=True,
            margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
        )
        # Count pages (rough estimate from PDF byte boundaries)
        page_count = pdf_bytes.count(b"/Type /Page") - pdf_bytes.count(b"/Type /Pages")
        if page_count < 1:
            page_count = 1
        await page.close()
    except Exception as e:
        logger.error(f"PDF generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")

    # Build filename: CV_{name}_{base cv name}_{short_id}.pdf
    header_name = (resume.json_data or {}).get("header", {}).get("name", "Resume").replace(" ", "")
    base_name = resume.name.split(" \u2192 ")[0] if " \u2192 " in (resume.name or "") else resume.name
    short_id = ""
    if resume.job_id:
        job_for_name = db.query(Job).filter(Job.id == resume.job_id).first()
        if job_for_name and job_for_name.short_id:
            short_id = f"_{job_for_name.short_id}"
    filename = f"CV_{header_name}_{base_name}{short_id}".encode("ascii", "replace").decode()

    headers = {
        "Content-Disposition": f'attachment; filename="{filename}.pdf"',
        "X-Page-Count": str(page_count),
    }
    if page_count > 1:
        headers["X-Warning"] = f"Resume is {page_count} pages - consider trimming to 1 page"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers=headers,
    )


# ── PDF Import ──────────────────────────────────────────────────────────────

@router.post("/import-pdf", status_code=201)
async def import_pdf(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload a PDF resume, extract text with pdfplumber, use LLM to parse into structured json_data.

    Returns the created Resume with extracted json_data.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    pdf_bytes = await file.read()
    if len(pdf_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="PDF too large (max 10 MB)")

    # Extract text via pdfplumber
    extracted_text = ""
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    extracted_text += text + "\n"
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to process PDF: {str(e)}")

    if len(extracted_text.strip()) < 50:
        raise HTTPException(status_code=422, detail="Could not extract enough text from PDF. It may be image-based.")

    # Use LLM to parse extracted text into structured resume JSON
    schema_example = '{"header":{"name":"","contact_items":[{"text":"location"},{"text":"email","url":"mailto:email"},{"text":"LinkedIn","url":"linkedin.com/in/..."},{"text":"phone"}]},"summary":"","experience":[{"company":"","title":"","location":"","date":"","description":"","bullets":[]}],"skills":{},"education":[{"school":"","location":"","degree":""}],"projects":[],"publications":[]}'

    system_prompt = "You are a resume parser. Extract structured data from resume text. Return ONLY valid JSON, no markdown fences."
    user_prompt = (
        f"Parse this resume text into the following JSON structure. "
        f"Fill in all fields you can find. Use empty strings for missing fields, empty arrays for missing lists.\n\n"
        f"Target schema:\n{schema_example}\n\n"
        f"Resume text:\n{extracted_text}"
    )

    try:
        from backend.analyzer.llm_client import call_llm
        _resp = await call_llm(prompt=user_prompt, system=system_prompt, max_tokens=2000)
        raw_response = _resp["text"]

        # Strip markdown fences if present
        cleaned = raw_response.strip()
        if cleaned.startswith("```"):
            # Remove opening fence (with optional language tag)
            first_newline = cleaned.index("\n")
            cleaned = cleaned[first_newline + 1:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        json_data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error(f"LLM returned invalid JSON for PDF import: {e}\nRaw: {raw_response[:500]}")
        raise HTTPException(status_code=422, detail="LLM returned invalid JSON. Try again or enter data manually.")
    except Exception as e:
        logger.error(f"LLM call failed during PDF import: {e}")
        raise HTTPException(status_code=500, detail=f"LLM extraction failed: {str(e)}")

    # Create resume with extracted data
    name = file.filename.rsplit(".", 1)[0] if "." in file.filename else file.filename
    resume = Resume(
        name=name,
        is_base=True,
        template=_default_template_id(),
        page_format="letter",
        json_data=json_data,
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)

    return _resume_to_dict(resume, include_json_data=True)


# ── Score Check ────────────────────────────────────────────────────────────

@router.post("/{resume_id}/score-check")
async def score_check(resume_id: str, request_body: dict = None, db: Session = Depends(get_db)):
    """Score a tailored resume against its linked job. Saves result to job as 'Tailored' CV score."""
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    if not resume.job_id:
        raise HTTPException(status_code=400, detail="Resume has no linked job")

    job = db.query(Job).filter(Job.id == resume.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Linked job not found")

    depth = (request_body or {}).get("depth", "light")
    if depth not in ("light", "full"):
        depth = "light"

    # Convert resume JSON to plain text for scoring
    json_data = resume.json_data or {}
    text_parts = []
    header = json_data.get("header", {})
    if header.get("name"):
        text_parts.append(header["name"])
    if header.get("title"):
        text_parts.append(header["title"])
    if json_data.get("summary"):
        text_parts.append(json_data["summary"])
    for exp in json_data.get("experience", []):
        text_parts.append(f"{exp.get('title', '')} at {exp.get('company', '')}")
        for b in exp.get("bullets", []):
            text_parts.append(f"- {b}")
    for edu in json_data.get("education", []):
        text_parts.append(f"{edu.get('degree', '')} — {edu.get('school', '')}")
    for sk in json_data.get("skills", []):
        if isinstance(sk, dict):
            text_parts.append(f"{sk.get('category', '')}: {sk.get('items', '')}")
        elif isinstance(sk, str):
            text_parts.append(sk)

    resume_text = "\n".join(text_parts)
    if len(resume_text) < 50:
        raise HTTPException(status_code=400, detail="Resume has insufficient text for scoring")

    # Get original best score from job.cv_scores (before tailored)
    existing_scores = dict(job.cv_scores or {})
    original_score = existing_scores.get("Tailored")  # previous tailored score if re-running
    if original_score is None:
        # Fall back to best non-tailored score
        numeric = {k: v for k, v in existing_scores.items() if k != "Tailored" and isinstance(v, (int, float))}
        original_score = max(numeric.values()) if numeric else None

    # Run LLM scoring with "Tailored" as the CV name
    from backend.analyzer.cv_scorer import score_job_sync
    cv_texts = {"Tailored": resume_text}
    result = await score_job_sync(job, cv_texts, db=db, depth=depth)

    if not result:
        raise HTTPException(status_code=500, detail="Scoring failed -- check LLM configuration")

    # Extract the tailored score
    tailored_score = None
    scores = result.get("scores", result)
    if isinstance(scores, dict):
        tailored_score = scores.get("Tailored")

    # Save score to job
    updated_scores = dict(job.cv_scores or {})
    if tailored_score is not None:
        updated_scores["Tailored"] = tailored_score
        job.cv_scores = updated_scores
        # Update best_cv if tailored is now highest
        numeric = {k: v for k, v in updated_scores.items() if isinstance(v, (int, float))}
        if numeric:
            best_name = max(numeric, key=numeric.get)
            job.best_cv = best_name

    # Save report per CV (nested dict)
    if depth == "full" and result.get("_scoring_report"):
        report = result["_scoring_report"]
        report["scored_with"] = "Tailored"
        existing = dict(job.scoring_report or {})
        # Migrate flat format to nested if needed
        if existing and "summary" in existing:
            old_cv = existing.pop("scored_with", job.best_cv or "Unknown")
            existing = {old_cv: existing}
        existing["Tailored"] = report
        job.scoring_report = existing

    db.commit()

    response = {
        "original_score": original_score,
        "tailored_score": tailored_score,
        "delta": (tailored_score - original_score) if tailored_score is not None and original_score is not None else None,
        "depth": depth,
        "job_title": job.title,
        "job_company": job.company,
    }
    if depth == "full" and result.get("_scoring_report"):
        response["report"] = result["_scoring_report"]

    return response


# ── Tracer Stats ───────────────────────────────────────────────────────────

@router.get("/{resume_id}/tracer-stats")
def get_tracer_stats(resume_id: str, db: Session = Depends(get_db)):
    """Get click stats per tracer link for a resume."""
    from sqlalchemy import func
    links = db.query(TracerLink).filter(TracerLink.resume_id == resume_id).all()
    result = []
    for link in links:
        total_clicks = db.query(func.count(TracerClickEvent.id)).filter(
            TracerClickEvent.tracer_link_id == link.id,
            TracerClickEvent.is_likely_bot == False,
        ).scalar()
        last_click = db.query(func.max(TracerClickEvent.clicked_at)).filter(
            TracerClickEvent.tracer_link_id == link.id,
            TracerClickEvent.is_likely_bot == False,
        ).scalar()
        result.append({
            "token": link.token,
            "source_label": link.source_label,
            "destination_url": link.destination_url,
            "clicks": total_clicks or 0,
            "last_clicked": last_click.isoformat() if last_click else None,
            "is_active": link.is_active,
        })
    return result
