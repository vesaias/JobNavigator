"""Persona endpoints — singleton record per applicant."""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.models.db import get_db, Persona, utcnow

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
    "writing_samples",
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
        "writing_samples": p.writing_samples or [],
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
    """Replace one or more node values. PATCH replaces a whole node atomically;
    callers must send the complete intended value of each node they update.

    Unknown top-level keys → 400.
    """
    unknown = set(updates.keys()) - _NODES
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown persona node(s): {sorted(unknown)}")

    p = db.query(Persona).filter(Persona.id == 1).first()
    if not p:
        raise HTTPException(status_code=500, detail="Persona singleton missing")

    for k, v in updates.items():
        setattr(p, k, v)
    p.updated_at = utcnow()
    db.commit()
    db.refresh(p)
    return _to_dict(p)
