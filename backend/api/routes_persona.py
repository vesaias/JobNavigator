"""Persona endpoints — singleton record per applicant."""
import copy
import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from backend.models.db import get_db, Persona, Resume, utcnow

logger = logging.getLogger("jobnavigator.persona")

router = APIRouter(prefix="/persona", tags=["persona"])

# Allowed top-level node names. PATCH must use exactly these keys.
_NODES = {
    "contact",
    "work_auth",
    "demographics",
    "compensation",
    "preferences",
    "resume_content",
    "qa_bank",
}


def _to_dict(p: Persona) -> dict:
    return {
        "id": p.id,
        "contact": p.contact or {},
        "work_auth": p.work_auth or {},
        "demographics": p.demographics or {},
        "compensation": p.compensation or {},
        "preferences": p.preferences or {},
        "resume_content": p.resume_content or {},
        "qa_bank": p.qa_bank or [],
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


@router.get("")
def get_persona(db: Session = Depends(get_db)):
    """Return the singleton Persona (id=1)."""
    p = db.query(Persona).filter(Persona.id == 1).first()
    if not p:
        # Should never happen — seed_persona runs at startup. Guard anyway.
        raise HTTPException(status_code=500, detail="Persona singleton missing — restart app to re-seed")
    return _to_dict(p)


@router.patch("")
def update_persona(updates: dict, db: Session = Depends(get_db)):
    """Replace one or more node values atomically; callers must send the complete intended value of each node they update. Unknown top-level keys → 400."""
    unknown = set(updates.keys()) - _NODES
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown persona node(s): {sorted(unknown)}")

    p = db.query(Persona).filter(Persona.id == 1).first()
    if not p:
        raise HTTPException(status_code=500, detail="Persona singleton missing")

    for k, v in updates.items():
        setattr(p, k, v)
        # JSON columns compare by value, so an order-only change (e.g. reordering
        # resume_content.skills) produces no UPDATE unless the node is flagged explicitly.
        flag_modified(p, k)
    p.updated_at = utcnow()
    db.commit()
    db.refresh(p)
    return _to_dict(p)


# ── Import (résumé → persona) ────────────────────────────────────────────────
# Initial population: the imported document replaces `contact` and `resume_content`;
# the other five nodes are never touched since nothing in a résumé answers them.

# The header fills contact's name/email/phone/location/social keys; `current_company`
# comes from the latest role in `experience` (see _current_company_from below), and
# there's no title key (see autofill_schema.py ANSWER_SCHEMA), so `title` is dropped.
_EMAIL_RE = re.compile(r"[\w.+%-]+@[\w-]+\.[\w.-]+")
# a phone is digits with the usual separators — no letters, at least 7 digits
_PHONE_RE = re.compile(r"^\+?[\d][\d\s().+/-]{5,}$")
# deliberately no bare "site": it is a substring of real place names (Yosemite),
# and a location line is exactly what the fall-through below has to catch.
_LINK_WORDS = ("portfolio", "website", "web site", "homepage", "blog", "www.", "http")


def _digits(s: str) -> int:
    return sum(1 for c in s if c.isdigit())


def _split_location(text: str) -> dict:
    """Split a location line ('Boston, MA' / 'Berlin, Germany' / 'Austin, TX, USA') into city/state/country; a two-part location is a country when the second half names one (reusing the dial-code table), else a state."""
    parts = [x.strip() for x in text.split(",") if x.strip()]
    if not parts:
        return {}
    out = {"city": parts[0]}
    if len(parts) >= 3:
        out["state"], out["country"] = parts[1], parts[2]
    elif len(parts) == 2:
        from backend.autofill_schema import _DIAL_CODES
        second = parts[1]
        out["country" if second.lower() in _DIAL_CODES else "state"] = second
    return out


def _contact_from_header(header: dict) -> dict:
    """Map a résumé header {name, contact_items[{text,url}]} onto the persona's contact keys (first_name, last_name, email, phone, city, state, country, linkedin, github, portfolio); each item is classified by its text and url, first match wins, and the first item of a kind wins over later ones."""
    out = {}
    name = str((header or {}).get("name") or "").strip()
    if name:
        parts = name.split()
        out["first_name"] = parts[0]
        if len(parts) > 1:
            out["last_name"] = " ".join(parts[1:])

    for item in (header or {}).get("contact_items") or []:
        if not isinstance(item, dict):
            continue
        # the stored key is `text`; `label` is accepted for hand-written payloads
        text = str(item.get("text") or item.get("label") or "").strip()
        url = str(item.get("url") or "").strip()
        if not text and not url:
            continue
        low = f"{text} {url}".lower()

        if url.lower().startswith("mailto:"):
            out.setdefault("email", url[7:].strip())
            continue
        m = _EMAIL_RE.search(text) or _EMAIL_RE.search(url)
        if m:
            out.setdefault("email", m.group(0))
            continue
        if url.lower().startswith("tel:"):
            out.setdefault("phone", url[4:].strip())
            continue
        if not url and _PHONE_RE.match(text) and _digits(text) >= 7:
            out.setdefault("phone", text)
            continue
        if "linkedin" in low:
            out.setdefault("linkedin", url or text)
            continue
        if "github" in low:
            out.setdefault("github", url or text)
            continue
        if url or any(w in low for w in _LINK_WORDS):
            out.setdefault("portfolio", url or text)
            continue
        # no url, not an address, not a number → the location line
        if "city" not in out and any(c.isalpha() for c in text):
            out.update(_split_location(text))
    return out


# The résumé sections the Persona editor renders (ResumeSections.jsx SECTION_ORDER minus
# Header, which lives in `contact`); defaults keep the node's shape stable for the editor.
_CONTENT_DEFAULTS = (
    ("summary", ""), ("experience", []), ("skills", {}),
    ("education", []), ("projects", []), ("publications", []),
)


def _resume_content_from(json_data: dict) -> dict:
    """The résumé's own sections, copied verbatim — exactly what the Persona editor edits via ResumeSections."""
    src = json_data or {}
    return {k: copy.deepcopy(src[k]) if src.get(k) else copy.deepcopy(default)
            for k, default in _CONTENT_DEFAULTS}


# ── current employer ─────────────────────────────────────────────────────────
# The one contact key a résumé answers outside its header: the company of the
# latest role in `experience`. An open-ended role ("2021 – Present") outranks
# every dated one; ties keep the résumé's own order, which lists newest first.
_PRESENT_WORDS = ("present", "current", "now", "ongoing", "to date")
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
_MONTHS = {m: i for i, m in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), start=1)}
# en dash, em dash, minus, hyphen or the word "to" — the separators résumé date ranges use
_RANGE_SPLIT_RE = re.compile(r"\s*(?:[–—−-]|\bto\b)\s*")


def _role_end(entry: dict):
    """(year, month) the role ended, as a sort key; (9999, 12) for an open-ended one and (0, 0) when the date names no year."""
    text = str((entry or {}).get("date") or "")
    tail = _RANGE_SPLIT_RE.split(text)[-1].strip().lower()
    if any(w in tail for w in _PRESENT_WORDS):
        return (9999, 12)
    years = _YEAR_RE.findall(tail) or _YEAR_RE.findall(text)
    if not years:
        return (0, 0)
    month = next((n for m, n in _MONTHS.items() if m in tail), 0)
    return (int(years[-1]), month)


def _current_company_from(content: dict) -> str:
    """The employer of the most recent role in `resume_content`, for contact.current_company; empty when no role names a company."""
    rows = [e for e in (content or {}).get("experience") or []
            if isinstance(e, dict) and str(e.get("company") or "").strip()]
    if not rows:
        return ""
    # -i breaks a tie toward the earlier row, i.e. the one the résumé lists first
    best = max(range(len(rows)), key=lambda i: (_role_end(rows[i]), -i))
    return str(rows[best]["company"]).strip()


def _import_summary(contact: dict, content: dict, source: str) -> dict:
    exp = content.get("experience") or []
    bullets = sum(len(e.get("bullets") or []) for e in exp if isinstance(e, dict))
    return {
        "roles": len(exp),
        "bullets": bullets,
        "skill_groups": len(content.get("skills") or {}),
        "education": len(content.get("education") or []),
        "projects": len(content.get("projects") or []),
        "contact_items": len(contact),
        "source": source,
    }


@router.post("/import")
async def import_persona(request: Request, file: Optional[UploadFile] = File(None), db: Session = Depends(get_db)):
    """Populate the persona from a base résumé (`{"resume_id": ...}`) or an uploaded résumé PDF (same parser as POST /api/resumes/import-pdf, stores nothing as a Resume row), replacing `contact` and `resume_content` wholesale while leaving the other nodes untouched."""
    p = db.query(Persona).filter(Persona.id == 1).first()
    if not p:
        raise HTTPException(status_code=500, detail="Persona singleton missing")

    if file is not None and getattr(file, "filename", None):
        from backend.api.routes_resumes import check_pdf_name, check_pdf_size, parse_resume_pdf
        filename = file.filename
        check_pdf_name(filename)
        pdf_bytes = await file.read()
        check_pdf_size(pdf_bytes)
        json_data = await parse_resume_pdf(pdf_bytes, db)
        source = f"pdf:{filename}"
    else:
        try:
            body = await request.json()
        except Exception:
            body = None
        resume_id = str((body or {}).get("resume_id") or "").strip() if isinstance(body, dict) else ""
        if not resume_id:
            raise HTTPException(status_code=400, detail="Send a resume_id, or upload a PDF file")
        r = db.query(Resume).filter(Resume.id == resume_id).first()
        if not r:
            raise HTTPException(status_code=404, detail="Resume not found")
        if not r.is_base:
            raise HTTPException(
                status_code=400,
                detail=f"'{r.name}' is a tailored copy — import from a base résumé",
            )
        json_data = r.json_data or {}
        source = f"resume:{r.name}"

    contact = _contact_from_header(json_data.get("header") or {})
    content = _resume_content_from(json_data)
    employer = _current_company_from(content)
    if employer:
        contact["current_company"] = employer

    p.contact = contact
    p.resume_content = content
    # JSON columns compare by value; flag both so an import that happens to match
    # the stored value still writes (same reason PATCH above flags every node).
    flag_modified(p, "contact")
    flag_modified(p, "resume_content")
    p.updated_at = utcnow()

    from backend.activity import log_activity
    log_activity("persona", f"Persona imported from {source}", db=db)

    db.commit()
    db.refresh(p)
    logger.info(f"Persona imported from {source}")
    return {"persona": _to_dict(p), "summary": _import_summary(contact, content, source)}


@router.post("/qa-bank")
def append_qa_bank(body: dict, db: Session = Depends(get_db)):
    """Append one {question, answer} entry to the singleton Persona's qa_bank, creating the Persona row if missing (empty question/answer -> 400); used by the extension's autofill review popover to save edited answers back into the bank."""
    question = (body.get("question") or "").strip()
    answer = (body.get("answer") or "").strip()
    if not question or not answer:
        raise HTTPException(status_code=400, detail="question and answer are required")

    p = db.query(Persona).filter(Persona.id == 1).first()
    if not p:
        p = Persona(id=1, qa_bank=[])
        db.add(p)

    bank = list(p.qa_bank or [])
    bank.append({"question": question, "answer": answer})
    p.qa_bank = bank
    # JSON columns need explicit change flagging so SQLAlchemy detects the mutation.
    flag_modified(p, "qa_bank")
    p.updated_at = utcnow()
    db.commit()
    return {"count": len(bank)}
