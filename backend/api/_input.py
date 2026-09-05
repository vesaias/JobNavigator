"""Small guards for hand-rolled `body: dict` handlers.

Several endpoints take a raw dict rather than a Pydantic model (the Chrome
extension posts to some of them, and the shapes are loose by design). The idiom
`(body.get(k) or "").strip()` then raises `AttributeError` the moment a caller
sends a number, list or dict, which surfaces as an unexplained 500 (R4-T1-20).
These helpers turn every such shape into the 400 the handler already answers for
a blank value.
"""
import uuid as _uuid

from fastapi import HTTPException


def str_field(body: dict, key: str, *, required: bool = False, label: str = None) -> str:
    """Return `body[key]` as a stripped string.

    Missing/None/blank -> "" (or 400 when `required`). A non-string value is a
    400, never an `AttributeError` in the handler.
    """
    name = label or key
    value = (body or {}).get(key)
    if value is None:
        if required:
            raise HTTPException(status_code=400, detail=f"{name} is required")
        return ""
    if not isinstance(value, str):
        raise HTTPException(status_code=400, detail=f"{name} must be a string")
    value = value.strip()
    if required and not value:
        raise HTTPException(status_code=400, detail=f"{name} is required")
    return value


def uuid_filter(value, label: str):
    """Parse a query-string uuid *filter*, answering 422 when it is malformed.

    A bad id in a path segment is a missing resource (404, handled globally by
    `_bad_uuid_to_404`); a bad id in a filter is a malformed request. Without
    this the value reaches Postgres and the DataError handler reports the list
    endpoint as "Not found" (R4-T1-09).
    """
    if value is None or value == "":
        return None
    try:
        return _uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(status_code=422,
                            detail=f"{label} must be a UUID") from None
