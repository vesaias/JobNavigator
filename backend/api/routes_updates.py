"""Update check (update_check.py): is a newer release, or a newer commit on main, available?

Every account may read the result; only the owner may skip the cache ("Check now"),
because each skip spends the install's anonymous GitHub quota. Nothing here updates
the install."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.models.db import get_db

router = APIRouter(prefix="/updates", tags=["system"])


@router.get("", summary="Update check result")
async def update_check(force: bool = False, db: Session = Depends(get_db)):
    from backend.accounts.settings import is_owner_caller
    from backend.update_check import settings_of, update_status
    owner = is_owner_caller(db)
    if force and not owner:
        raise HTTPException(403, "Only the owner can run the update check now.")
    mode, repo = settings_of(db)
    return {**await update_status(mode, repo, force=force), "owner": owner}
