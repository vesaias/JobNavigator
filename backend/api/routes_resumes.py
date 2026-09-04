"""Resume builder CRUD, preview, PDF export, and PDF import endpoints."""
import functools as _functools
import io
import json
import logging
import re
import uuid as _uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, Response, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from backend.models.db import get_db, Resume, TracerLink, TracerClickEvent, Setting, Job, Application, SessionLocal, utcnow, Persona
from backend.job_monitor import launch_background, JobAlreadyRunningError


# ── Persona experience merge helpers ─────────────────────────────────────────
# Used by _tailor_impl when merging Persona.resume_content's experience entries
# into a base Resume's experience. Two-stage:
#   1. Match entries by normalized company name (case-insensitive, suffix-stripped) +
#      coarse title-root (Project|Product|Program Manager → "manager")
#   2. For matched entries, merge bullets — drop persona bullets that duplicate base
#      bullets via combined Jaccard + numeric-anchor heuristic.
# Thresholds tuned against real-world data (see analyze_bullet_dupes.py): J >= 0.40
# with shared numeric anchor catches all 27 true dups in the corpus zero false
# positives; J >= 0.50 lexical-only catches the rare paraphrase pair.

_COMPANY_SUFFIX_RE = re.compile(r'\b(inc|corp|corporation|ltd|llc|gmbh|ag|sa|plc|co)\.?$', re.IGNORECASE)
_NUMERIC_RE = re.compile(r'\$?\d+(?:[.,]\d+)?[KMB%+]*')
_WORD_RE = re.compile(r'[a-zA-Z]+')

_BULLET_STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "at",
    "by", "for", "with", "from", "as", "is", "was", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did",
    "this", "that", "these", "those", "it", "its", "i", "we", "our",
    "you", "your", "into", "via", "across", "per",
}

_TITLE_ROOTS = (
    "manager", "engineer", "analyst", "developer", "designer",
    "lead", "director", "vp", "chief", "intern", "consultant",
    "scientist", "researcher", "specialist", "architect", "owner",
)


def _normalize_company(s: str) -> str:
    """Lowercase + strip common suffixes (Inc., Corp., LLC, GmbH, AG, ...)."""
    if not s:
        return ""
    s = s.strip().lower().rstrip(",.")
    return _COMPANY_SUFFIX_RE.sub("", s).strip().rstrip(",.")


def _normalize_title_root(s: str) -> str:
    """Collapse role variants to a single root, e.g.
       'Senior Project Manager' / 'Senior Product Manager' / 'Senior Program Manager' → 'manager'.
       Falls back to the lowercased title if no known root matches."""
    s = (s or "").strip().lower()
    if not s:
        return ""
    for root in _TITLE_ROOTS:
        if root in s:
            return root
    return s


def _bullet_stem(w: str) -> str:
    for suf in ("ings", "ing", "edly", "ed", "ly", "es", "s"):
        if len(w) > len(suf) + 2 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def _bullet_tokens(s: str) -> set:
    return {_bullet_stem(w.lower()) for w in _WORD_RE.findall(s or "") if w.lower() not in _BULLET_STOPWORDS}


def _bullet_jaccard(a: str, b: str) -> float:
    ta, tb = _bullet_tokens(a), _bullet_tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _numeric_anchors(s: str) -> set:
    return set(_NUMERIC_RE.findall(s or ""))


def _is_duplicate_bullet(a: str, b: str) -> bool:
    """Two bullets are duplicates if:
       - they share a numeric anchor AND have Jaccard ≥ 0.40, OR
       - they have Jaccard ≥ 0.50 (no shared numeric anchor required)."""
    if _numeric_anchors(a) & _numeric_anchors(b):
        return _bullet_jaccard(a, b) >= 0.40
    return _bullet_jaccard(a, b) >= 0.50


def _merge_persona_experience(base_exp: list, persona_exp: list) -> list:
    """Merge persona experience entries into base experience, returning a new list.

    For each persona entry: find the base entry with the same normalized company AND
    matching title-root; if found, append persona bullets that don't duplicate any
    base bullet (via Jaccard + numeric-anchor). If no entry matches, append the
    persona entry wholesale (it's a role the base resume doesn't list)."""
    if not persona_exp:
        return [dict(e) for e in (base_exp or [])]
    if not base_exp:
        return [dict(e) for e in persona_exp]

    # Deep-clone base entries so we don't mutate the caller's data
    merged = [{**e, "bullets": list(e.get("bullets", []) or [])} for e in base_exp]

    # Index merged entries by normalized company → list of indices
    by_company = {}
    for i, e in enumerate(merged):
        cn = _normalize_company(e.get("company", ""))
        if cn:
            by_company.setdefault(cn, []).append(i)

    for p_exp in persona_exp:
        p_company = _normalize_company(p_exp.get("company", ""))
        candidates = by_company.get(p_company, [])
        chosen = None
        if candidates:
            p_root = _normalize_title_root(p_exp.get("title", ""))
            for i in candidates:
                if _normalize_title_root(merged[i].get("title", "")) == p_root:
                    chosen = i
                    break
            if chosen is None:
                chosen = candidates[0]  # fallback — same company, different role flavor

        if chosen is not None:
            existing = merged[chosen]["bullets"]
            for p_bullet in (p_exp.get("bullets") or []):
                if not any(_is_duplicate_bullet(p_bullet, eb) for eb in existing):
                    existing.append(p_bullet)
        else:
            new_entry = {**p_exp, "bullets": list(p_exp.get("bullets", []) or [])}
            merged.append(new_entry)
            cn = _normalize_company(p_exp.get("company", ""))
            if cn:
                by_company.setdefault(cn, []).append(len(merged) - 1)

    return merged
# ─────────────────────────────────────────────────────────────────────────────

logger = logging.getLogger("jobnavigator.resumes")

import asyncio as _asyncio

_tailoring_semaphore: _asyncio.Semaphore | None = None


def _get_tailoring_semaphore() -> _asyncio.Semaphore:
    """Lazy-init tailoring semaphore from DB setting. Created on first use."""
    global _tailoring_semaphore
    if _tailoring_semaphore is None:
        db = SessionLocal()
        try:
            row = db.query(Setting).filter(Setting.key == "tailoring_max_concurrent").first()
            try:
                limit = max(1, int(row.value)) if row and row.value else 2
            except (ValueError, TypeError):
                limit = 2
        finally:
            db.close()
        _tailoring_semaphore = _asyncio.Semaphore(limit)
        logger.info(f"Tailoring semaphore initialized: max {limit} concurrent jobs")
    return _tailoring_semaphore


def reset_tailoring_semaphore():
    """Reset semaphore so next call re-reads the limit from DB."""
    global _tailoring_semaphore
    _tailoring_semaphore = None


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

@_functools.lru_cache(maxsize=32)
def _load_template_fonts(fonts_dir_str: str) -> dict:
    """Read + base64-encode a template's fonts once per process.

    Fonts never change at runtime (~0.75 MB raw per serif template), but this was
    being re-read and re-encoded on every PDF preview/render. Keyed by directory
    path string so the resume and cover-letter template trees share the cache.
    """
    import base64
    from pathlib import Path as _Path
    fonts = {}
    fonts_dir = _Path(fonts_dir_str)
    if fonts_dir.exists():
        for pattern in ("*.TTF", "*.ttf"):
            for font_file in fonts_dir.glob(pattern):
                with open(font_file, "rb") as f:
                    fonts[font_file.name] = "data:font/truetype;base64," + base64.b64encode(f.read()).decode()
    return fonts


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
    fonts = _load_template_fonts(str(template_dir / "fonts"))

    # RES-20: json_data may carry internal metadata under keys prefixed with "_"
    # (_tailor_context, _score). Those are never résumé content — keep them out of
    # the template namespace so they can never render, and so a future key can't
    # collide with a template global.
    content = {k: v for k, v in (json_data or {}).items() if not str(k).startswith("_")}
    html = template.render(
        **content,
        page_format=page_format,
        fonts_base="",
        fonts=fonts,
    )
    return html


def _rewrite_urls_with_tracers(json_data: dict, resume_id: str, db,
                               cover_letter_id: str = None, job_id=None) -> dict:
    """Replace header contact URLs with tracer redirect URLs. Returns modified copy.

    Owner is exactly one of a resume (resume_id) or a cover letter
    (cover_letter_id). For job_id token styles, the owning job's short_id is
    resolved from the Resume's job_id, or from the passed `job_id` for cover
    letters.
    """
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

    owner_is_cl = cover_letter_id is not None
    owner_filter = (TracerLink.cover_letter_id == cover_letter_id) if owner_is_cl \
        else (TracerLink.resume_id == resume_id)

    def _new_link(token, dest_url, label):
        kwargs = {"token": token, "destination_url": dest_url, "source_label": label}
        if owner_is_cl:
            kwargs["cover_letter_id"] = cover_letter_id
        else:
            kwargs["resume_id"] = resume_id
        return TracerLink(**kwargs)

    def _repoint(link, dest_url, label):
        # R3-B-03: claim this token for the current owner *without* releasing the
        # other one. A résumé and the cover letter written for the same job derive
        # the same {short_id}{stub} token by design (one job, one tracked link), so
        # the row has to be able to belong to both at once. Nulling the other side
        # — what this used to do — meant whichever document rendered second owned
        # the link and the other one's /tracer-stats came back empty, flipping on
        # every render. Both FKs are nullable and the stats endpoints filter on
        # their own FK, so shared ownership makes both documents report the same
        # (shared) counter instead of one of them reporting nothing.
        if owner_is_cl:
            link.cover_letter_id = cover_letter_id
        else:
            link.resume_id = resume_id
        link.destination_url = dest_url
        link.source_label = label

    # Resolve the owning job's short_id once (for *_jobid token styles).
    job_short_id = None
    if url_style in ("path_jobid", "param_jobid"):
        resolved_job_id = job_id
        if not resolved_job_id and not owner_is_cl:
            resume_obj = db.query(Resume).filter(Resume.id == resume_id).first()
            resolved_job_id = resume_obj.job_id if resume_obj else None
        if resolved_job_id:
            job_obj = db.query(Job).filter(Job.id == resolved_job_id).first()
            job_short_id = job_obj.short_id if job_obj else None

    data = _json.loads(_json.dumps(json_data))  # deep copy
    header = data.get("header", {})

    items = header.get("contact_items", [])
    for i, item in enumerate(items):
        url = item.get("url")
        if not url or not url.strip() or url.startswith("mailto:"):
            continue

        label = item.get("text", f"Link {i+1}")
        dest_url = url if url.startswith("http") else f"https://{url}"
        # Suffix for per-link distinction in job_id modes (user stub or first 3 chars)
        stub = item.get("stub")
        label_suffix = stub or label.lower()[:3]

        jobid_style = url_style in ("path_jobid", "param_jobid")
        if job_short_id:
            token = f"{job_short_id}{label_suffix}"
        elif jobid_style and stub:
            # Base resume (no job → no short_id) with an explicit stub: reserve "0"
            # as the no-job prefix so the token is 0{stub} instead of random.
            token = f"0{stub}"
        else:
            token = None

        # Find or create tracer link for this owner + destination
        from sqlalchemy.exc import IntegrityError
        existing = db.query(TracerLink).filter(
            owner_filter, TracerLink.destination_url == dest_url,
        ).first()

        # The deterministic token is a preference, never a guarantee. Only a
        # job-derived {short_id}{stub} is unique by construction; the job-less
        # 0{stub} fallback is not — every job-less owner with a stub of "l"
        # wants "0l" — so it may only be taken when nothing else holds it.
        def _taken_by_other(tok):
            q = db.query(TracerLink).filter(TracerLink.token == tok)
            if existing is not None:
                q = q.filter(TracerLink.id != existing.id)
            return q.first()

        if existing:
            if token and existing.token != token and _taken_by_other(token) is None:
                try:
                    existing.token = token
                    db.commit()
                except IntegrityError:
                    db.rollback()   # lost a race for it; keep the token we have
            # whatever happened above, the row's own token is the truth
            token = existing.token
        else:
            holder = _taken_by_other(token) if token else None
            if holder is not None and not job_short_id:
                # 0{stub} already belongs to a different job-less owner — taking
                # it would break their links, so fall back to a random token.
                token = None
            if token:
                if holder is not None:
                    # Same job → a resume and its cover letter intentionally share
                    # this token; hand it to whoever is rendering now.
                    _repoint(holder, dest_url, label)
                    db.commit()
                else:
                    # concurrent PDF renders can race here (same deterministic token);
                    # on the unique-violation, recover the row the other request inserted.
                    try:
                        db.add(_new_link(token, dest_url, label))
                        db.commit()
                    except IntegrityError:
                        db.rollback()
                        winner = db.query(TracerLink).filter(TracerLink.token == token).first()
                        if winner:
                            _repoint(winner, dest_url, label)
                            db.commit()
            if not token:
                chars = string.ascii_lowercase + string.digits
                for _ in range(100):
                    token = ''.join(random.choices(chars, k=6))
                    if db.query(TracerLink).filter(TracerLink.token == token).first():
                        continue
                    try:
                        db.add(_new_link(token, dest_url, label))
                        db.commit()
                        break
                    except IntegrityError:
                        db.rollback()
                        continue

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


@router.get("/shelf")
def resume_shelf(db: Session = Depends(get_db)):
    """Assembled résumé shelf for the v2 UI: base résumés with their tailored
    copies grouped underneath, each copy carrying its job's company/role and fit
    score, plus a per-base average fit. One pass over resumes + a single jobs
    query — avoids the client fetching every copy's job (N+1)."""
    resumes = db.query(Resume).order_by(Resume.updated_at.desc()).all()
    bases = [r for r in resumes if r.is_base]
    copies = [r for r in resumes if not r.is_base]

    job_ids = {c.job_id for c in copies if c.job_id}
    jobs = {}
    app_status = {}
    app_updated = {}   # RES-29: when the application last moved — the archive date for a rejection
    if job_ids:
        for j in db.query(Job).filter(Job.id.in_(job_ids)).all():
            jobs[j.id] = j
        # application status per job (rejected → archived); most-recent wins
        for a in db.query(Application).filter(Application.job_id.in_(job_ids)).order_by(Application.updated_at.asc()).all():
            app_status[a.job_id] = a.status
            app_updated[a.job_id] = a.updated_at

    STALE_DAYS = 45
    now = utcnow()

    def _fresh(c):
        # unreviewed tailoring changes ≈ LLM suggested_bullets still pending accept/decline
        try:
            return any((e or {}).get("suggested_bullets") for e in (c.json_data or {}).get("experience", []))
        except Exception:
            return False

    def _archived_at(c, reason):
        # RES-29: a rejection is archived when the application was last moved; a
        # stale copy is archived by its own last edit (that's what STALE_DAYS
        # measures). Falls back to the copy's timestamp so the sort is total.
        ts = app_updated.get(c.job_id) if reason == "rejected" else None
        ts = ts or c.updated_at
        return ts.isoformat() if ts else None

    def _archive_reason(c):
        if app_status.get(c.job_id) == "rejected":
            return "rejected"
        ts = c.updated_at
        if ts is not None:
            ref = ts if ts.tzinfo else ts.replace(tzinfo=now.tzinfo)
            days = (now - ref).days
            if days > STALE_DAYS:
                return f"stale {days}d"
        return None

    def _copy_score(job, name):
        # Score lives on the copy's job cv_scores, keyed by the copy name or the
        # generic "Tailored" label; fall back to the best numeric score present.
        if not job:
            return None
        cs = job.cv_scores or {}
        for key in (name, "Tailored"):
            v = cs.get(key)
            if isinstance(v, (int, float)):
                return int(round(v))
        nums = [v for v in cs.values() if isinstance(v, (int, float))]
        return int(round(max(nums))) if nums else None

    by_parent = {}
    for c in copies:
        by_parent.setdefault(c.parent_id, []).append(c)

    archived = []
    out = []
    for b in bases:
        clist = sorted(by_parent.get(b.id, []),
                       key=lambda c: c.updated_at or b.updated_at, reverse=True)
        copies_out, scores = [], []
        for c in clist:
            job = jobs.get(c.job_id)
            sc = _copy_score(job, c.name)
            # avg_fit counts every scored copy, archived (rejected/stale) ones included
            if sc is not None:
                scores.append(sc)
            reason = _archive_reason(c)
            if reason:
                archived.append({
                    "id": str(c.id),
                    "name": c.name,
                    "base_id": str(b.id),
                    "job_id": str(c.job_id) if c.job_id else None,
                    "company": (job.company if job else None),
                    "role": (job.title if job else None),
                    "why": reason,
                    "archived_at": _archived_at(c, reason),
                })
                continue
            copies_out.append({
                "id": str(c.id),
                "name": c.name,
                "job_id": str(c.job_id) if c.job_id else None,
                "company": (job.company if job else None),
                "role": (job.title if job else None),
                "score": sc,
                "status": app_status.get(c.job_id) or (job.status if job else None),
                "fresh": _fresh(c),
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            })
        out.append({
            "id": str(b.id),
            "name": b.name,
            "updated_at": b.updated_at.isoformat() if b.updated_at else None,
            "copy_count": len(copies_out),
            "archived_count": len(clist) - len(copies_out),
            "avg_fit": int(round(sum(scores) / len(scores))) if scores else None,
            "copies": copies_out,
        })
    # Persona group: tailored copies with no base parent (base_resume_id == "persona")
    persona_copies_out, persona_scores = [], []
    for c in sorted(by_parent.get(None, []), key=lambda c: c.updated_at or now, reverse=True):
        job = jobs.get(c.job_id)
        sc = _copy_score(job, c.name)
        # avg_fit counts every scored copy, archived ones included
        if sc is not None:
            persona_scores.append(sc)
        reason = _archive_reason(c)
        if reason:
            archived.append({"id": str(c.id), "name": c.name, "base_id": None,
                             "job_id": str(c.job_id) if c.job_id else None,
                             "company": (job.company if job else None),
                             "role": (job.title if job else None), "why": reason,
                             "archived_at": _archived_at(c, reason)})
            continue
        persona_copies_out.append({
            "id": str(c.id), "name": c.name,
            "job_id": str(c.job_id) if c.job_id else None,
            "company": (job.company if job else None),
            "role": (job.title if job else None),
            "score": sc, "status": app_status.get(c.job_id) or (job.status if job else None),
            "fresh": _fresh(c), "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        })
    persona = {
        "copy_count": len(persona_copies_out),
        "archived_count": len(by_parent.get(None, [])) - len(persona_copies_out),
        "avg_fit": int(round(sum(persona_scores) / len(persona_scores))) if persona_scores else None,
        "copies": persona_copies_out,
        # newest copy's timestamp powers the "edited X ago" meta on the shelf card
        "updated_at": persona_copies_out[0]["updated_at"] if persona_copies_out else None,
    }

    # RES-29: this said "newest archived first" but sorted rejected-before-stale
    # with no date involved. Sort by the archive date, newest first (undated last).
    archived.sort(key=lambda a: (a["archived_at"] or ""), reverse=True)
    return {"bases": out, "total_copies": len(copies) - len(archived),
            "persona": persona, "archived": archived, "archived_count": len(archived)}


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


def _resolve_chain_score_depth(db) -> str | None:
    """Depth of the score chained after a job-linked tailor, or None for no chain.

    Setting `tailor_auto_quick_score` (seeded default 'light') accepts:
      'off' / 'false' / 'no' / '0'        → no chain
      'light' / 'true' / 'yes' / '1' / '' → light chain (default)
      'full'                              → full chain (richer report, slower/costlier)
    """
    chain_row = db.query(Setting).filter(Setting.key == "tailor_auto_quick_score").first()
    raw_chain = (chain_row.value if chain_row else "light").strip().lower()
    depth_map = {
        "off": None, "false": None, "no": None, "0": None,
        "true": "light", "light": "light", "yes": "light", "1": "light", "": "light",
        "full": "full",
    }
    return depth_map.get(raw_chain, "light")


@router.post("/tailor", status_code=202)
async def tailor_resume(body: dict, db: Session = Depends(get_db)):
    """Tailor a base resume for a specific job in the background.

    Returns immediately with a run_id. Progress is trackable via
    GET /api/monitor/in-flight?job_ids=<job_id>. The resulting Resume
    row appears when the job finishes (fetch via list_resumes).

    The response also reports `chain_score` — the depth of the scoring run the
    worker will launch on the new copy ('light' | 'full'), or 'off' when nothing
    follows — so the UI can say up front that a second LLM call is coming
    (R2-H-09). Only job-linked tailors chain; a freeform one always reports 'off'.
    """
    base_resume_id = body.get("base_resume_id")
    job_id = body.get("job_id")
    job_description = body.get("job_description")

    if not base_resume_id:
        raise HTTPException(400, "base_resume_id is required")
    if not job_id and not job_description:
        raise HTTPException(400, "Either job_id or job_description is required")

    # Fast-fail: base resume must exist. Reserved id 'persona' resolves to the
    # singleton Persona's resume_content — must be non-empty.
    if base_resume_id == "persona":
        persona = db.query(Persona).filter(Persona.id == 1).first()
        if not persona or not (persona.resume_content or {}):
            raise HTTPException(400, "Persona has no resume_content — fill it in /persona first")
    else:
        base = db.query(Resume).filter(Resume.id == base_resume_id).first()
        if not base:
            raise HTTPException(404, "Base resume not found")

    # Fast-fail: job must exist (if job_id given) and have *some* JD source. The worker
    # resolves the actual text (description → live fetch → cached page); here we only
    # confirm there's something to work from, without doing the (slow) fetch.
    if job_id:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise HTTPException(404, "Job not found")
        if not ((job.description or "").strip() or (job.url or "").strip() or (job.cached_page_text or "").strip()):
            raise HTTPException(400, "Job has no description, URL, or cached page to tailor from")

    # Fast-fail: the prompt template must exist
    prompt_row = db.query(Setting).filter(Setting.key == "cv_tailor_prompt").first()
    if not prompt_row or not (prompt_row.value or "").strip():
        raise HTTPException(500, "cv_tailor_prompt setting is empty — configure it in Settings")

    target_uuid = _uuid.UUID(job_id) if job_id else None
    scope = f"{base_resume_id}:{job_id or 'freeform'}"

    try:
        run_id = launch_background(
            "tailor_resume",
            _tailor_impl,
            trigger="manual",
            scope_key=scope,
            target_job_id=target_uuid,
            func_kwargs={
                "base_resume_id": base_resume_id,
                "job_id": job_id,
                "job_description_override": job_description,
            },
        )
        chain_depth = _resolve_chain_score_depth(db) if job_id else None
        return {"run_id": run_id, "status": "running", "chain_score": chain_depth or "off"}
    except JobAlreadyRunningError as e:
        return JSONResponse(
            status_code=409,
            content={"detail": f"{e.job_type} is already running for this pair"},
        )


async def _resolve_tailoring_jd(job, db) -> str:
    """Resolve the JD text to tailor against, best-quality first:

    1. ``job.description`` — clean, already stored.
    3. live ``_fetch_job_description(job.url)`` — a fresh ATS-parsed description;
       persisted back to ``job.description`` so scoring and future tailors reuse it.
    2. ``job.cached_page_text`` — raw page text captured on apply; noisy, so it's the
       last resort and is NOT persisted as the description.

    Returns "" when nothing usable exists (the caller then hard-fails).
    """
    if (job.description or "").strip():
        return job.description
    if (job.url or "").strip():
        from backend.scraper.ats._descriptions import _fetch_job_description
        fetched = await _fetch_job_description(job.url)
        if fetched and fetched.strip():
            job.description = fetched
            db.commit()
            return fetched
    return job.cached_page_text or ""


async def _tailor_impl(base_resume_id: str, job_id: str | None, job_description_override: str | None):
    """Background worker: does the actual LLM tailoring work.

    Opens its own DB session (no request-scoped session available outside an HTTP
    handler). Semaphore-guarded so concurrent tailors don't exceed
    tailoring_max_concurrent.
    """
    import re as _re
    import json as _json

    async with _get_tailoring_semaphore():
        db = SessionLocal()
        try:
            # Reserved id 'persona' uses the singleton Persona's resume_content as
            # the base. The output Resume has parent_id=None since Persona isn't a
            # Resume row.
            persona_as_base = (base_resume_id == "persona")
            if persona_as_base:
                persona_row = db.query(Persona).filter(Persona.id == 1).first()
                if not persona_row or not (persona_row.resume_content or {}):
                    logger.error("Tailor: persona has no resume_content at execution time")
                    raise RuntimeError("Tailor: persona has no resume_content at execution time")
                base = None
                base_data = persona_row.resume_content or {}
                base_name = "Persona"
                base_template = None
                base_page_format = None
                base_id_for_parent = None
            else:
                base = db.query(Resume).filter(Resume.id == base_resume_id).first()
                if not base:
                    logger.error(f"Tailor: base resume {base_resume_id} missing at execution time")
                    raise RuntimeError(f"Tailor: base resume {base_resume_id} missing at execution time")
                base_data = base.json_data or {}
                base_name = base.name
                base_template = base.template
                base_page_format = base.page_format
                base_id_for_parent = base.id

            jd_text = job_description_override or ""
            job_name = ""
            if job_id:
                job = db.query(Job).filter(Job.id == job_id).first()
                if not job:
                    logger.error(f"Tailor: job {job_id} missing at execution time")
                    raise RuntimeError(f"Tailor: job {job_id} missing at execution time")
                jd_text = await _resolve_tailoring_jd(job, db)
                job_name = f"{job.company} \u2014 {job.title}" if job.company else (job.title or "")
                if not jd_text:
                    logger.error(f"Tailor: job {job_id} has no usable description")
                    raise RuntimeError(f"Tailor: job {job_id} has no usable description")

            # Persona-as-base uses a constrained prompt (select 3-5 bullets per role
            # from the rich pool); falls back to the standard cv_tailor_prompt if the
            # persona-specific one isn't configured.
            prompt_template = None
            if persona_as_base:
                p_row = db.query(Setting).filter(Setting.key == "persona_tailor_prompt").first()
                if p_row and (p_row.value or "").strip():
                    prompt_template = p_row.value
            if not prompt_template:
                prompt_row = db.query(Setting).filter(Setting.key == "cv_tailor_prompt").first()
                if not prompt_row or not prompt_row.value:
                    logger.error("Tailor: cv_tailor_prompt setting is empty")
                    raise RuntimeError("Tailor: cv_tailor_prompt setting is empty")
                prompt_template = prompt_row.value

            resume_sections = {
                "summary": base_data.get("summary", ""),
                "experience": list(base_data.get("experience", []) or []),
                "skills": dict(base_data.get("skills", {}) or {}),
            }

            # Note: Persona is NOT auto-merged into Resume-as-base tailoring. Two clean
            # modes — Resume-as-base uses ONLY the base resume's bullets (predictable
            # output length); Persona-as-base uses persona's full pool with the
            # constrained persona_tailor_prompt that selects 3-5 best bullets per role.

            prompt = prompt_template.replace("{resume_json}", _json.dumps(resume_sections, indent=2))
            prompt = prompt.replace("{job_description}", jd_text[:6000])

            system = (
                "You are an expert resume tailor. Rewrite the resume to align with the "
                "job description using the JD's exact vocabulary. Do NOT invent experience, "
                "skills, or facts not present in the original resume. Only reformulate, "
                "reframe, and reorder existing content. If something is missing, map to "
                "the closest truthful concept."
            )

            from backend.analyzer.llm_client import call_cv_tailor_llm
            from backend.analyzer.llm_logger import track_llm_call

            # Same resolver call_cv_tailor_llm dispatches with, so the log row
            # can never name a model that was not called (R2-H-15).
            from backend.analyzer.llm_client import resolve_llm_config
            _cfg = resolve_llm_config("cv_tailor", db=db)
            _provider, _model = _cfg["provider"], _cfg["model"]

            try:
                async with track_llm_call("tailor", _provider, _model, job_id=job_id) as _tracker:
                    _resp = await call_cv_tailor_llm(prompt, system, max_tokens=3000)
                    _tracker.record(_resp)
                    raw = _resp["text"]
            except Exception as e:
                logger.error(f"Tailor LLM failed for base={base_resume_id} job={job_id}: {e}")
                raise

            try:
                text = raw.strip()
                match = _re.search(r'\{[\s\S]*\}', text)
                if match:
                    text = match.group(0)
                llm_result = _json.loads(text)
            except _json.JSONDecodeError as e:
                logger.error(f"Tailor JSON parse failed: {e}. Raw: {raw[:500]}")
                raise

            tailored_data = _json.loads(_json.dumps(base_data))
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

            # RES-20: a copy tailored from a pasted description has no Job row, so the
            # text it was written against would be lost — and with it any chance of
            # scoring the copy. Keep it on the copy under an "_"-prefixed key, which
            # _render_html and the section editors both ignore.
            if not job_id and jd_text:
                tailored_data["_tailor_context"] = {"job_description": jd_text[:6000], "source": "freeform"}

            name = f"{base_name} \u2192 {job_name}" if job_name else f"{base_name} (tailored)"
            tailored = Resume(
                name=name,
                is_base=False,
                parent_id=base_id_for_parent,
                job_id=job_id,
                template=base_template,
                page_format=base_page_format,
                json_data=tailored_data,
            )
            db.add(tailored)
            db.commit()
            db.refresh(tailored)
            # Optional: chain a score against the newly tailored CV.
            chain_depth = _resolve_chain_score_depth(db)
            if chain_depth and job_id:
                try:
                    from backend.analyzer.cv_scorer import score_single_job
                    launch_background(
                        "analyze_job",
                        score_single_job,
                        trigger="manual",
                        scope_key=f"{job_id}:tailored:{tailored.id}",
                        target_job_id=_uuid.UUID(job_id) if isinstance(job_id, str) else job_id,
                        func_kwargs={
                            "job_id": job_id,
                            "cv_ids": [str(tailored.id)],
                            "depth": chain_depth,
                        },
                    )
                except Exception as _e:
                    # Non-fatal — tailor succeeded, chain is a nice-to-have
                    logger.warning(f"Tailor chain score failed to launch: {_e}")
            logger.info(f"Tailor: created resume {tailored.id} for job {job_id}")
            # Returned string becomes JobRun.result_summary (Stats → Run history).
            return (f"Created '{name}'"
                    + (f" - {chain_depth} score chained" if chain_depth and job_id else ""))
        finally:
            db.close()


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
            # SQLAlchemy decides whether to emit an UPDATE by comparing old == new.
            # Two dicts with the same pairs in a different order compare equal, so a
            # pure reorder (e.g. moving a skills row with the editor's ▲▼) was silently
            # dropped. Force the column dirty for the JSON payload.
            if key == "json_data":
                flag_modified(resume, "json_data")

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
    # Delete tracer links for this resume and all children. R3-B-03: a link can
    # be shared with a cover letter (same job → same token). The letter outlives
    # the résumé (CoverLetter.resume_id is ON DELETE SET NULL), so release our
    # side of a shared row instead of deleting it and taking the letter's link —
    # and its click history — with it.
    shared = db.query(TracerLink).filter(
        TracerLink.resume_id.in_(all_ids), TracerLink.cover_letter_id.isnot(None),
    ).all()
    for link in shared:
        link.resume_id = None
    db.query(TracerLink).filter(
        TracerLink.resume_id.in_(all_ids), TracerLink.cover_letter_id.is_(None),
    ).delete(synchronize_session=False)
    # R3-B-05: the "Tailored" entries a tailored copy wrote onto its job outlive
    # the copy. `tailored_resume_id` is derived from the surviving Resume rows so
    # it disappears on its own, but `cv_scores["Tailored"]`, the report keyed
    # "Tailored" and a `best_cv` pointing at it do not — leaving the Feed with a
    # score (and a report tab) attributed to a document that no longer exists,
    # which can still win best_cv. Drop them once the job has no tailored copy
    # left, and recompute the best from whatever remains.
    job_ids = {r.job_id for r in [resume, *children] if r.job_id and not r.is_base}
    for child in children:
        db.delete(child)

    db.delete(resume)
    db.flush()   # so the "any tailored copy left?" query can't see the deleted rows
    for jid in job_ids:
        _clear_orphan_tailored_score(db, jid)
    db.commit()
    return {"deleted": True, "id": resume_id, "children_deleted": len(children)}


def _clear_orphan_tailored_score(db: Session, job_id) -> bool:
    """Strip a job's `Tailored` score/report once its last tailored copy is gone.

    No-op while another tailored copy still points at the job — the score belongs
    to whichever copy is current, not to the one being deleted. Returns True when
    something was cleared (used by the tests; callers commit).
    """
    still_tailored = db.query(Resume.id).filter(
        Resume.job_id == job_id, Resume.is_base == False,
    ).first()
    if still_tailored:
        return False
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        return False

    changed = False
    scores = dict(job.cv_scores or {})
    if "Tailored" in scores:
        scores.pop("Tailored")
        job.cv_scores = scores
        flag_modified(job, "cv_scores")
        changed = True

    report = dict(job.scoring_report or {})
    if "Tailored" in report:
        report.pop("Tailored")
        # A single-CV report is stored flat (`{summary, ..., scored_with}`) and only
        # nested per-CV once a second one arrives. Unwrap back to the flat shape so
        # the Feed doesn't have to special-case a one-key wrapper.
        if len(report) == 1:
            only_cv, only_report = next(iter(report.items()))
            if isinstance(only_report, dict) and "summary" in only_report:
                report = {**only_report, "scored_with": only_cv}
        job.scoring_report = report or None
        flag_modified(job, "scoring_report")
        changed = True

    if changed:
        numeric = {k: v for k, v in scores.items() if isinstance(v, (int, float))}
        if numeric:
            job.best_cv = max(numeric, key=numeric.get)
            job.best_cv_score = float(max(numeric.values()))
        else:
            job.best_cv = None
            job.best_cv_score = None
    return changed


# ── Preview & PDF ───────────────────────────────────────────────────────────

@router.get("/{resume_id}/preview")
def preview_resume(resume_id: str, db: Session = Depends(get_db)):
    """Render resume as HTML and return it for preview.

    OPEN-13: this used to hand back the *un-rewritten* document while /pdf
    rewrote the contact links into tracked ones, so the two endpoints disagreed
    about what the résumé says. `_rewrite_urls_with_tracers` reuses an existing
    link per (owner, destination) and only mints one when there is none, so
    previewing costs nothing extra and the PDF rendered afterwards carries the
    same tokens.
    """
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    json_data = _rewrite_urls_with_tracers(resume.json_data or {}, str(resume.id), db)
    html = _render_html(json_data, resume.template, resume.page_format)
    return HTMLResponse(content=html)


@router.get("/{resume_id}/pdf")
async def export_pdf(resume_id: str, template: Optional[str] = None, format: Optional[str] = None, db: Session = Depends(get_db)):
    """Render resume as PDF via Playwright and return the bytes. `template`/`format`
    query params override the stored values (used by the live editor preview so a
    rapid template switch doesn't race the debounced PATCH)."""
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    tpl = template or resume.template
    fmt = (format or resume.page_format or "letter")
    json_data = resume.json_data or {}
    # Rewrite URLs with tracer links if enabled
    pdf_data = _rewrite_urls_with_tracers(json_data, str(resume.id), db)
    html = _render_html(pdf_data, tpl, fmt)

    # Determine paper format
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

    # Build filename: {Name}_{Type}_Resume_{number}.pdf
    # Name = candidate header name; Type = base resume name (PM/PjM/\u2026);
    # number = linked job short_id (omitted for base resumes with no job).
    header_name = (resume.json_data or {}).get("header", {}).get("name", "Resume").replace(" ", "")
    base_name = (resume.name.split(" \u2192 ")[0] if " \u2192 " in (resume.name or "") else resume.name) or "Resume"
    base_name = base_name.replace(" ", "")
    number = ""
    if resume.job_id:
        job_for_name = db.query(Job).filter(Job.id == resume.job_id).first()
        if job_for_name and job_for_name.short_id:
            number = f"_{job_for_name.short_id}"
    filename = f"{header_name}_{base_name}_Resume{number}".encode("ascii", "replace").decode()

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

# One place for the upload ceiling, so every endpoint that accepts a résumé PDF
# (this one and POST /api/persona/import) enforces the same 10 MB.
PDF_MAX_BYTES = 10 * 1024 * 1024


def check_pdf_name(filename: str) -> None:
    """Reject anything that isn't a .pdf before its bytes are read. 400."""
    if not (filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")


def check_pdf_size(pdf_bytes: bytes) -> None:
    """The shared 10 MB ceiling for a résumé PDF upload. 400."""
    if len(pdf_bytes) > PDF_MAX_BYTES:
        raise HTTPException(status_code=400, detail="PDF too large (max 10 MB)")


async def parse_resume_pdf(pdf_bytes: bytes, db: Session) -> dict:
    """PDF bytes → structured résumé ``json_data``, via pdfplumber + one LLM call.

    The single parser for every "a PDF becomes résumé content" path: the résumé
    shelf import below and POST /api/persona/import both call it, so they share
    the schema, the prompt, the fence-stripping and the llm_logger tracking.

    Raises HTTPException — 422 when the PDF yields no usable text or the model
    returns invalid JSON, 500 when the LLM call itself fails.
    """
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

    raw_response = ""
    try:
        from backend.analyzer.llm_client import call_llm
        from backend.analyzer.llm_logger import track_llm_call
        # Determine model for logging — the same resolver call_llm dispatches with.
        from backend.analyzer.llm_client import resolve_llm_config
        _cfg = resolve_llm_config("", db=db)
        _provider, _model = _cfg["provider"], _cfg["model"]
        async with track_llm_call("pdf", _provider, _model) as _tracker:
            _resp = await call_llm(prompt=user_prompt, system=system_prompt, max_tokens=2000)
            _tracker.record(_resp)
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

        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error(f"LLM returned invalid JSON for PDF import: {e}\nRaw: {raw_response[:500]}")
        raise HTTPException(status_code=422, detail="LLM returned invalid JSON. Try again or enter data manually.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"LLM call failed during PDF import: {e}")
        raise HTTPException(status_code=500, detail=f"LLM extraction failed: {str(e)}")


@router.post("/import-pdf", status_code=201)
async def import_pdf(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload a PDF resume, extract text with pdfplumber, use LLM to parse into structured json_data.

    Returns the created Resume with extracted json_data.
    """
    check_pdf_name(file.filename)
    pdf_bytes = await file.read()
    check_pdf_size(pdf_bytes)

    json_data = await parse_resume_pdf(pdf_bytes, db)

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

def _tailor_context_jd(json_data: dict) -> str:
    """RES-20: the job description a freeform tailor was run against.

    A copy tailored from a pasted JD has no Job row, so _tailor_impl stores the
    text on the copy itself under json_data["_tailor_context"]. That is what makes
    such a copy scoreable. Returns "" when there is none.
    """
    ctx = (json_data or {}).get("_tailor_context") or {}
    return str(ctx.get("job_description") or "").strip()


def _resume_to_score_text(json_data: dict) -> str:
    """Flatten a Resume.json_data into the plaintext form passed to the scorer.

    Thin wrapper around analyzer.cv_scorer._flatten_resume so the score-check pre-check
    and the LLM payload always agree on the canonical flatten (skills is a dict, not a list).
    """
    from backend.analyzer.cv_scorer import _flatten_resume
    return _flatten_resume(json_data or {})


async def _score_resume_impl(resume_id: str, depth: str):
    """Background worker: score a tailored resume against its linked job.

    RES-20: a copy tailored from a pasted description has no linked job. It is
    scored against the JD kept on the copy (json_data["_tailor_context"]) and the
    result is stored on the copy under json_data["_score"] — the Job path below is
    unchanged.

    Runs under launch_background → progress visible via /monitor/active so the
    spinner survives navigation away from /resumes.

    Returns a one-line summary — launch_background stores it as
    JobRun.result_summary for Stats → Run history (R2-H-13).
    """
    from backend.analyzer.cv_scorer import score_job_sync

    db = SessionLocal()
    try:
        resume = db.query(Resume).filter(Resume.id == resume_id).first()
        if not resume:
            logger.error(f"Score: resume {resume_id} missing at execution time")
            return "Resume not found"

        job = None
        jd_text = ""
        if resume.job_id:
            job = db.query(Job).filter(Job.id == resume.job_id).first()
            if not job:
                logger.error(f"Score: linked job {resume.job_id} not found")
                return "Linked job not found"
        else:
            jd_text = _tailor_context_jd(resume.json_data or {})
            if not jd_text:
                logger.error(f"Score: resume {resume_id} has no linked job and no saved job description")
                return "No linked job or saved job description"

        resume_text = _resume_to_score_text(resume.json_data or {})
        if len(resume_text) < 50:
            logger.warning(f"Score: resume {resume_id} has insufficient text ({len(resume_text)} chars)")
            return "Resume has insufficient text"

        cv_texts = {"Tailored": resume_text}
        if job is not None:
            result = await score_job_sync(job, cv_texts, db=db, depth=depth)
        else:
            # score_job_sync only reads `job` for its id (logging / LLM-cost rows)
            # once the JD text is supplied, so a stand-in is enough here.
            from types import SimpleNamespace
            stand_in = SimpleNamespace(id=None, company=None, title=None, description=jd_text)
            result = await score_job_sync(stand_in, cv_texts, db=db, depth=depth, preloaded_text=jd_text)
        if not result:
            logger.error(f"Score: scoring failed for resume {resume_id}")
            return "Scoring failed"

        tailored_score = None
        scores = result.get("scores", result)
        if isinstance(scores, dict):
            tailored_score = scores.get("Tailored")

        if job is None:
            data = dict(resume.json_data or {})
            entry = {"Tailored": tailored_score, "scored_at": utcnow().isoformat()}
            if depth == "full" and result.get("_scoring_report"):
                report = dict(result["_scoring_report"])
                report["scored_with"] = "Tailored"
                entry["report"] = report
            data["_score"] = entry
            resume.json_data = data
            flag_modified(resume, "json_data")
            db.commit()
            logger.info(f"Score: resume {resume_id} (freeform JD) = {tailored_score} (depth={depth})")
            return f"{resume.name} (pasted JD) - Tailored {tailored_score}, {depth}"

        updated_scores = dict(job.cv_scores or {})
        if tailored_score is not None:
            updated_scores["Tailored"] = tailored_score
            job.cv_scores = updated_scores
            numeric = {k: v for k, v in updated_scores.items() if isinstance(v, (int, float))}
            if numeric:
                job.best_cv = max(numeric, key=numeric.get)
                try:
                    job.best_cv_score = float(max(numeric.values()))
                except (ValueError, TypeError):
                    job.best_cv_score = None

        if depth == "full" and result.get("_scoring_report"):
            report = result["_scoring_report"]
            report["scored_with"] = "Tailored"
            existing = dict(job.scoring_report or {})
            if existing and "summary" in existing:
                old_cv = existing.pop("scored_with", job.best_cv or "Unknown")
                existing = {old_cv: existing}
            existing["Tailored"] = report
            job.scoring_report = existing

        db.commit()
        logger.info(f"Score: resume {resume_id} → job {resume.job_id} = {tailored_score} (depth={depth})")
        return f"{job.title} - Tailored {tailored_score}, {depth}"
    finally:
        db.close()


@router.post("/{resume_id}/score-check", status_code=202)
async def score_check(resume_id: str, request_body: dict = None, db: Session = Depends(get_db)):
    """Score a tailored resume against its linked job in the background.

    Returns 202 + run_id immediately. Progress trackable via GET /api/monitor/active
    (job_type=score_resume). Result lands in the job's cv_scores under 'Tailored'.
    """
    import uuid as _uuid

    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    if resume.job_id:
        job = db.query(Job).filter(Job.id == resume.job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Linked job not found")
        # Pre-check matches the worker's text-resolution: cv_scorer._get_job_text() falls
        # back to cached_page_text (and even live page-fetch) when description is empty.
        # Don't 400 jobs that scored fine via cache alone.
        if not (job.description or "").strip() and not (job.cached_page_text or "").strip():
            raise HTTPException(status_code=400, detail="Linked job has no description or cached page text")
    # RES-20: no Job row is fine as long as the copy kept the description it was
    # tailored from; only a copy with neither can't be scored.
    elif not _tailor_context_jd(resume.json_data or {}):
        raise HTTPException(status_code=400, detail="Resume has no linked job or saved job description")

    if len(_resume_to_score_text(resume.json_data or {})) < 50:
        raise HTTPException(status_code=400, detail="Resume has insufficient text for scoring")

    depth = (request_body or {}).get("depth", "light")
    if depth not in ("light", "full"):
        depth = "light"

    scope = f"{resume.job_id}:resume:{resume_id}" if resume.job_id else f"resume:{resume_id}"
    try:
        run_id = launch_background(
            "score_resume",
            _score_resume_impl,
            trigger="manual",
            scope_key=scope,
            target_job_id=_uuid.UUID(str(resume.job_id)) if resume.job_id else None,
            func_kwargs={"resume_id": resume_id, "depth": depth},
        )
        return {"run_id": run_id, "status": "running", "depth": depth, "resume_id": resume_id}
    except JobAlreadyRunningError as e:
        return JSONResponse(
            status_code=409,
            content={"detail": f"{e.job_type} is already running for this resume"},
        )


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
