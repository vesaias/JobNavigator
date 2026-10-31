"""GET /settings and PATCH /settings endpoints, plus the MT-9 section table and policies."""
import json
import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from backend.models.db import get_db, Account, SectionPolicy
from backend.scheduler import configure_scheduler
from backend.analyzer.cv_scorer import reset_scoring_semaphore
from backend.scraper._shared.dedup import reload_tracking_params
from backend.accounts import settings as acct_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])


_REDACT_SUFFIXES = ("_password", "_api_key", "_session_id", "_secret")
_REDACT_KEYS = {"dashboard_api_key", "gmail_refresh_token", "claude_code_oauth_token",
                "telegram_bot_token"}
# Server-side only, never listed (not even redacted) and not writable (not a known key).
_HIDDEN_KEYS = {"account_cookie_secret", "telegram_own_webhook_secret", "gmail_token_status",
                "llm_local_seed_cleared", "llm_provider_keys_migrated", "cv_score_keys_migrated", "posting_keys_migrated",
                "telemetry_install_id", "telemetry_last_sent_at",
                # the per-slot API keys replaced by one key per provider (kept one release for a downgrade)
                *acct_settings.LEGACY_LLM_KEY_SETTINGS}


def _is_secret(key: str) -> bool:
    return key in _REDACT_KEYS or any(key.endswith(s) for s in _REDACT_SUFFIXES)


# QA F5 (R3-03 / R6-02): the owner's personal values a member reads through an inherited or
# owner-only section are never served in clear: addresses and chat ids come back "" with
# `_meta.set_by_owner`, secrets keep the "••••••" placeholder and get the same flag, and
# the proxy URL keeps its host but masks the credentials in it.
_OWNER_PERSONAL_SUFFIXES = ("_email", "_chat_id")
_MASKED_URL_KEYS = {"proxy_url", "lmstudio_base_url", "ollama_base_url"}


def _is_owner_personal(key: str) -> bool:
    return any(key.endswith(s) for s in _OWNER_PERSONAL_SUFFIXES)


def mask_url_credentials(value: str) -> str:
    """`scheme://user:pass@host:port/…` → `scheme://••••@host:port/…`; a URL with no
    credentials is returned as it is."""
    from urllib.parse import urlsplit, urlunsplit
    v = (value or "").strip()
    if "@" not in v:
        return v
    try:
        parts = urlsplit(v)
        if parts.netloc and "@" in parts.netloc:
            host = parts.netloc.rsplit("@", 1)[1]
            return urlunsplit(parts._replace(netloc="••••@" + host))
    except ValueError:
        pass
    # not a parseable URL: hide everything up to the last "@"
    head, _, tail = v.rpartition("@")
    scheme = head.split("://", 1)[0] + "://" if "://" in head else ""
    return f"{scheme}••••@{tail}"


def _check_default_resume(db, value) -> None:
    """R3-05: `default_resume_id` is "", "persona" or the id of one of the caller's own base
    résumés (the Resume query is account-scoped); anything else is a 422."""
    v = value.strip() if isinstance(value, str) else value
    if v in ("", "persona"):
        return
    from backend.models.db import Resume
    try:
        rid = uuid.UUID(str(v))
    except (ValueError, TypeError, AttributeError):
        rid = None
    found = rid is not None and db.query(Resume.id).filter(
        Resume.id == rid, Resume.is_base == True).first() is not None  # noqa: E712 (scoped)
    if not found:
        raise HTTPException(status_code=422, detail="default_resume_id must be \"\", \"persona\" or the id of one of your base résumés")


def _check_cover_letter_template(value) -> None:
    """`cover_letter_template` is "" (Garamond Modern) or a folder under
    cover_letter_templates/ on this install; anything else is a 422."""
    from backend.api.routes_cover_letters import TEMPLATES_DIR
    from backend.api.routes_resumes import template_paths
    v = value.strip() if isinstance(value, str) else value
    if v != "" and v not in template_paths(TEMPLATES_DIR):
        raise HTTPException(status_code=422, detail="cover_letter_template must be \"\" or the id of a cover-letter template")


_CHAT_KEYS = ("telegram_chat_id", "telegram_bot_mode", "telegram_bot_token")


def _check_telegram_chat(db, updates: dict, targets: dict) -> None:
    """R5-03: a chat on the household bot belongs to one account, whether it was linked
    with a code or typed into Settings. A write that would leave the account's chat id
    (new or current) on the household bot while another account already has it there is a
    409 `chat_in_use` (nothing written). Clearing the chat id is always allowed."""
    if not any(k in updates for k in _CHAT_KEYS):
        return
    from backend.models.db import get_owner_id
    import backend.notifier.telegram as tg
    # Every key of the notifications section has the same target: the owner's (install,
    # also for a member with the owner unlock writing install values) or the member's own.
    target = next((targets.get(k) for k in _CHAT_KEYS if k in updates), None)
    account = target if target is not None else get_owner_id(db)
    if account is None:
        return

    def current(key):
        if target is None:
            return (acct_settings.get_install_setting(db, key) or "").strip()
        row = acct_settings._account_row(db, target, key)
        return (row.value or "").strip() if row is not None else ""

    def after(key):
        if key in updates:
            v = updates[key]
            return "" if v is None else str(v).strip()
        return current(key)

    chat = after("telegram_chat_id")
    if not chat:
        return
    on_own_bot = (target is not None and after("telegram_bot_mode").lower() == tg.OWN_BOT
                  and bool(after("telegram_bot_token")))
    other = tg.chat_in_use_by(db, account, chat, on_own_bot)
    if other:
        raise HTTPException(status_code=409, detail="chat_in_use")


@router.get("")
def get_settings(meta: bool = Query(False, description="Add `_meta` (per-key section, source, editable); always on for members"),
                 db: Session = Depends(get_db)):
    """Return the settings the current account sees as a key-value map. Sensitive values are redacted. For the owner these are the install values plus `_effective` {lmstudio_base_url, ollama_base_url: the address in use} (`_meta` only with `?meta=1`); a member gets inherited install values plus its own rows, and a `_meta` key with `{key: {section, source, editable}}`. A member never receives the owner's addresses, chat ids or secrets: those come back empty (secrets as "••••••") with `set_by_owner: true` in `_meta`, and `proxy_url` with its credentials masked."""
    rows = [r for r in acct_settings.effective_rows(db) if r[0] not in _HIDDEN_KEYS]
    member_caller = not acct_settings.is_owner_caller(db)
    result = {}
    owner_set = set()
    for key, value, source in rows:
        from_owner = member_caller and source == "install"
        # Redact secrets — return empty string if not set, "••••••" if set
        if _is_secret(key):
            result[key] = "" if not value else "•" * 6
            if from_owner and value:
                owner_set.add(key)
            continue
        if from_owner and _is_owner_personal(key):
            result[key] = ""
            if value:
                owner_set.add(key)
            continue
        if from_owner and key in _MASKED_URL_KEYS:
            result[key] = mask_url_credentials(value)
            continue
        try:
            result[key] = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            result[key] = value
    if not member_caller:
        # L-03: the address each local model server uses now (setting, else env, else default),
        # which Settings › Models shows as the placeholder of an empty box. Owner only: it can
        # carry the owner's env address, which a member never receives in clear.
        from backend.analyzer.llm_client import LOCAL_LLM_URLS, local_base_url
        result["_effective"] = {key: local_base_url(provider, db=db)
                                for provider, (key, _env, _default) in LOCAL_LLM_URLS.items()}
    if meta or member_caller:
        info = acct_settings.key_meta(db, [k for k, _v, _s in rows])
        for key, _value, source in rows:
            info[key]["source"] = source
            if key in owner_set:
                info[key]["set_by_owner"] = True
        result["_meta"] = info
    return result


@router.get("/sections")
def get_sections(db: Session = Depends(get_db)):
    """The settings sections: id (matches the Settings screen anchors where `ui` lists them), label, scope ('policy' | 'own_always' | 'owner_only'), default mode for 'policy' sections ('inherit' | 'own'), and the keys each holds. For a member each section also carries `mode`: that member's effective mode ('inherit' | 'own' | 'own_always' | 'owner_only')."""
    out = acct_settings.sections_payload()
    member = acct_settings.member_account(db)
    if member is not None:
        for sec in out:
            sec["mode"] = acct_settings.section_mode(db, member, sec["id"])
    return out


@router.patch("")
def update_settings(updates: dict, db: Session = Depends(get_db)):
    """Update one or more settings; only keys the app reads are writable (unknown -> 400 as a group), and values are validated (integers non-negative, `*_cron` a parseable 5-field expression, enums known) since a bad one could crash configure_scheduler() and prevent the backend from starting. The owner writes install values; a member writes its own values, and only in sections it owns (else 403, nothing written)."""
    from backend.seed import invalid_setting_values, unknown_setting_keys

    unknown = unknown_setting_keys(updates.keys())
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown setting: {', '.join(sorted(unknown))}",
        )

    # The redacted placeholder is never a real value — it is skipped below too.
    checkable = {k: v for k, v in updates.items()
                 if not (isinstance(v, str) and v == "•" * 6)}
    problems = invalid_setting_values(checkable)
    if problems:
        raise HTTPException(
            status_code=400,
            detail="Invalid setting value — " + "; ".join(problems),
        )

    try:
        targets = acct_settings.write_targets(db, checkable.keys())
    except acct_settings.SettingNotWritable as e:
        raise HTTPException(
            status_code=403,
            detail="These settings are managed by the account owner: " + ", ".join(e.keys),
        )

    if "default_resume_id" in checkable:
        _check_default_resume(db, checkable["default_resume_id"])
    if "cover_letter_template" in checkable:
        _check_cover_letter_template(checkable["cover_letter_template"])
    _check_telegram_chat(db, checkable, targets)

    warnings: list[str] = []
    updated = []
    install_updated = []
    for key, value in updates.items():
        if isinstance(value, str) and value == "•" * 6:
            continue
        stored = json.dumps(value) if isinstance(value, (list, dict, bool)) else str(value)
        target = targets.get(key)
        acct_settings.put_setting(db, key, stored, account_id=target)
        updated.append(key)
        if target is None:
            install_updated.append(key)
    db.commit()

    if not install_updated:
        # A member's own values touch no process-wide state (scheduler timing, semaphores
        # and dedup params are read from install values).
        return {"updated": updated, "warnings": warnings}

    # A member writing install values through the owner unlock (MT-14): the reconfigure
    # steps below must read the install values, not that member's own.
    from contextlib import nullcontext
    from backend.accounts.context import unscoped
    member_caller = not acct_settings.is_owner_caller(db)

    def _reconfigure(name: str, fn) -> None:
        """Run one post-update reconfigure; a failure becomes a warning naming the step.

        The exception text stays in the server log: it can carry file paths, connection
        strings and stack detail, and the response is not the place for it.
        """
        try:
            with (unscoped() if member_caller else nullcontext()):
                fn()
        except Exception:
            warnings.append(f"{name} failed — see server logs")
            logger.exception("%s failed after settings update", name)

    timing_keys = {
        "scrape_interval_minutes", "email_check_interval_minutes", "telemetry_level",
        "backup_cron", "digest_cron", "h1b_cron", "cleanup_cron", "reject_cron",
    }
    if timing_keys & set(install_updated):
        _reconfigure("configure_scheduler", configure_scheduler)

    if "scoring_max_concurrent" in install_updated:
        _reconfigure("reset_scoring_semaphore", reset_scoring_semaphore)

    if "scrape_max_concurrent" in install_updated:
        def _reset_scraping():
            from backend.job_monitor import reset_limiter
            reset_limiter("scraping")
        _reconfigure("reset_scrape_gate", _reset_scraping)

    if "tailoring_max_concurrent" in install_updated:
        def _reset_tailoring():
            from backend.api.routes_resumes import reset_tailoring_semaphore
            reset_tailoring_semaphore()
        _reconfigure("reset_tailoring_semaphore", _reset_tailoring)

    if "dedup_tracking_params" in install_updated:
        _reconfigure("reload_tracking_params", reload_tracking_params)

    return {"updated": updated, "warnings": warnings}


def _require_owner(db):
    # MT-14: a member whose browser holds a live owner unlock acts as the owner here too.
    if not acct_settings.acts_as_owner(db):
        raise HTTPException(status_code=403, detail="Only the account owner can change section policies")


@router.get("/policies")
def get_policies(db: Session = Depends(get_db)):
    """Owner only: every member's effective mode per 'policy' section, `{account_id: {section: mode}}`."""
    _require_owner(db)
    from backend.accounts.context import unscoped
    with unscoped():
        members = db.query(Account.id).filter(Account.role != "owner").all()
    out = {}
    for (acc_id,) in members:
        out[str(acc_id)] = {
            sid: acct_settings.section_mode(db, acc_id, sid)
            for sid, sec in acct_settings.SETTING_SECTIONS.items()
            if sec["scope"] == acct_settings.POLICY
        }
    return out


@router.patch("/policies")
def update_policy(body: dict, db: Session = Depends(get_db)):
    """Owner only: set one member's mode for one 'policy' section. Body `{account_id, section, mode}` with mode 'inherit' | 'own'. A member's own values are kept when a section goes back to inherit (they apply again if it is flipped to own)."""
    _require_owner(db)
    body = body or {}
    section = body.get("section")
    mode = body.get("mode")
    sec = acct_settings.SETTING_SECTIONS.get(section) if isinstance(section, str) else None
    if sec is None:
        raise HTTPException(status_code=400, detail=f"Unknown section: {section!r}")
    if sec["scope"] != acct_settings.POLICY:
        raise HTTPException(status_code=400, detail=f"Section {section!r} is {sec['scope']}; it has no policy")
    if mode not in acct_settings.POLICY_MODES:
        raise HTTPException(status_code=400, detail="mode must be 'inherit' or 'own'")
    try:
        acc_id = uuid.UUID(str(body.get("account_id")))
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="account_id must be an account id")
    account = db.query(Account).filter(Account.id == acc_id).first()
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    if account.role == "owner":
        raise HTTPException(status_code=400, detail="The owner's values are the install values; policies apply to members")
    row = (db.query(SectionPolicy)
           .filter(SectionPolicy.account_id == acc_id, SectionPolicy.section == section).first())
    if row is None:
        db.add(SectionPolicy(account_id=acc_id, section=section, mode=mode))
    else:
        row.mode = mode
    db.commit()
    return {"account_id": str(acc_id), "section": section, "mode": mode}


@router.post("/apify/check")
async def check_apify_key(db: Session = Depends(get_db)):
    """Confirm the stored Apify key works, without running a paid actor.

    A member whose Apify section inherits the owner's key checks the owner's key: the
    answer then says only that it works (`inherited: true`), never the owner's Apify
    username, unless the caller holds a live owner unlock."""
    import httpx
    from backend.scraper.sources.apify import ApifyError, account_name
    member = acct_settings.member_account(db)
    inherited = (member is not None
                 and acct_settings.section_mode(db, member, "apify") == acct_settings.INHERIT
                 and not acct_settings.acts_as_owner(db))
    try:
        username = await account_name()
        if inherited:
            return {"ok": True, "username": None, "inherited": True}
        return {"ok": True, "username": username}
    except ApifyError as e:
        raise HTTPException(status_code=400, detail=f"Apify: {e}") from e
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Apify is unreachable ({type(e).__name__})") from e


@router.get("/defaults")
def get_defaults():
    """Seeded defaults, so an editor can offer "Reset to default" without hardcoding a second copy of every prompt in the frontend."""
    from backend.seed import DEFAULT_SETTINGS
    return {k: v[0] for k, v in DEFAULT_SETTINGS.items()}
