"""Account administration (MT-11): counts, create with copy-from, remove, export.

Every function here reads and writes rows of an account that is usually NOT the caller's
(the owner creating, copying into, removing or exporting another account), so all of it
runs inside `unscoped()` with an explicit `account_id` filter or stamp — never rely on the
MT-2 listener in this file.

Storage note: résumé and cover-letter PDFs are rendered on demand (Playwright) and
streamed, never written to disk, so there are no per-account files to delete or export
today. `account_dirs()` is the hook for per-account directories that later batches add
(MT-15 CLI logins, MT-16 LinkedIn sessions).
"""
import copy
import io
import json
import logging
import os
import shutil
import tempfile
import uuid
import zipfile
from datetime import date, datetime, timezone
from typing import Iterable, Optional

from sqlalchemy import func, select

from backend.accounts import settings as acct_settings
from backend.accounts.context import unscoped

logger = logging.getLogger("jobnavigator.accounts")

MAX_ACCOUNTS = 5

COPY_ITEMS = ("persona", "qa", "resumes", "companies", "searches", "settings", "voices", "excludes")

# copy_from "voices" / "excludes" are settings: the keys they carry and their section.
VOICE_KEYS = ("cover_letter_voice_presets", "cover_letter_default_voice")
EXCLUDE_KEYS = ("body_exclusion_phrases", "title_exclude_global", "company_exclude_global")

# Never copied from one person to another: credentials, sessions, mailboxes, chats.
_PERSONAL_SECTIONS = {"gmail", "jobright", "linkedin"}
_PERSONAL_KEYS = {"telegram_chat_id"}


def _is_personal(key: str) -> bool:
    from backend.api.routes_settings import _HIDDEN_KEYS, _is_secret
    return (key in _PERSONAL_KEYS or key in _HIDDEN_KEYS or _is_secret(key)
            or acct_settings.section_of(key) in _PERSONAL_SECTIONS)


# ── Counts ───────────────────────────────────────────────────────────────────

def _count_models():
    from backend.models.db import Application, Company, CoverLetter, Job, Resume, Search
    return {"jobs": Job, "applications": Application, "resumes": Resume,
            "cover_letters": CoverLetter, "searches": Search, "companies": Company}


def account_counts(db) -> dict:
    """{account_id: {jobs, applications, resumes, cover_letters, searches, companies}} for
    every account (one GROUP BY per table)."""
    out: dict = {}
    with unscoped():
        for label, model in _count_models().items():
            for acc_id, n in db.query(model.account_id, func.count()).group_by(model.account_id).all():
                if acc_id is not None:
                    out.setdefault(acc_id, {})[label] = int(n)
    return out


def empty_counts() -> dict:
    return {k: 0 for k in _count_models()}


# ── Create ───────────────────────────────────────────────────────────────────

def _columns(model, skip=()):
    skip = set(skip) | {"id", "account_id"}
    return [c.key for c in model.__mapper__.column_attrs if c.key not in skip]


def _clone(row, model, account_id, skip=(), **overrides):
    data = {k: copy.deepcopy(getattr(row, k)) for k in _columns(model, skip)}
    data.update(overrides)
    return model(account_id=account_id, **data)


def _company_copy(c, model, account_id, selected_resume_ids, **overrides):
    """One company row for `account_id`. last_scraped_at cleared (MT-12 decision): the copy
    is due at once, so the next scheduled pass scrapes it, and a due target's one shared
    fetch (MT-8) feeds every subscriber, the source company included."""
    return _clone(c, model, account_id, skip=("warning_acknowledged_at",),
                  selected_resume_ids=selected_resume_ids, last_scraped_at=None, **overrides)


def _search_copy(s, model, account_id, **overrides):
    """One search row for `account_id`, due at once (last_run_at cleared). An Apify search
    is copied paused: it bills the new account's Apify token (or the owner's, on inherit),
    so its owner resumes it on purpose, the same rule as a new Apify search."""
    from backend.scraper.search_modes import get_mode
    mode = get_mode(s.search_mode)
    if mode is not None and mode.paid:
        overrides.setdefault("active", False)
    return _clone(s, model, account_id, skip=("created_at", "warning_acknowledged_at"),
                  last_run_at=None, **overrides)


# ── Clone one company / search from another account (MT-20) ──────────────────

class CloneError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def caller_account_id(db):
    """The account the request acts for (the owner when no context is set)."""
    from backend.accounts import auth as acct_auth
    from backend.accounts.context import current_account
    accounts = acct_auth.load_accounts(db)
    acc = acct_auth._find(accounts, current_account.get()) or acct_auth._owner_of(accounts)
    return (acc["id"] if acc else None), accounts


def _other_accounts(db) -> tuple:
    """(caller id, [other accounts as dicts]) — empty list unless there are >= 2 accounts."""
    caller, accounts = caller_account_id(db)
    if caller is None or len(accounts) < 2:
        return caller, []
    return caller, [a for a in accounts if a["id"] != caller]


def _require_two(db):
    caller, others = _other_accounts(db)
    if not others:
        raise CloneError(409, "needs_two_accounts", "Copying needs a second account.")
    return caller


def company_clone_sources(db) -> dict:
    """Other accounts' companies, only the fields a picker needs (no notes, no jobs, no
    counts). `exists` = the caller already has a company of that name (a clone would 409)."""
    from backend.models.db import Company
    caller, others = _other_accounts(db)
    out = []
    with unscoped():
        mine = {(n or "").strip().lower() for (n,) in db.query(Company.name).filter(Company.account_id == caller)}
        for acc in others:
            rows = (db.query(Company).filter(Company.account_id == acc["id"])
                    .order_by(Company.tier.asc().nullslast(), Company.name).all())
            out.append({"id": str(acc["id"]), "name": acc["name"], "color": acc["color"],
                        "role": acc["role"],
                        "items": [{"id": str(c.id), "name": c.name, "tier": c.tier, "active": bool(c.active),
                                   "scrape_urls": list(c.scrape_urls or []),
                                   "exists": (c.name or "").strip().lower() in mine} for c in rows]})
    return {"accounts": out}


def search_clone_sources(db) -> dict:
    """Other accounts' searches (built-in extension searches left out), picker fields only."""
    from backend.models.db import Search
    from backend.seed import EXTENSION_SEARCH_MODES
    _caller, others = _other_accounts(db)
    out = []
    with unscoped():
        for acc in others:
            rows = (db.query(Search).filter(Search.account_id == acc["id"],
                                            Search.search_mode.notin_(EXTENSION_SEARCH_MODES))
                    .order_by(Search.created_at).all())
            out.append({"id": str(acc["id"]), "name": acc["name"], "color": acc["color"],
                        "role": acc["role"],
                        "items": [{"id": str(s.id), "name": s.name, "search_mode": s.search_mode,
                                   "search_term": s.search_term, "direct_url": s.direct_url,
                                   "location": s.location, "country": s.country,
                                   "active": bool(s.active)} for s in rows]})
    return {"accounts": out}


def _source_row(db, model, source_id, caller):
    try:
        sid = source_id if isinstance(source_id, uuid.UUID) else uuid.UUID(str(source_id))
    except (ValueError, TypeError, AttributeError):
        sid = None
    row = None
    if sid is not None:
        with unscoped():
            row = db.query(model).filter(model.id == sid, model.account_id != caller).first()
    if row is None:
        raise CloneError(404, "source_not_found", "That item is not in another account.")
    return row


def clone_company(db, source_id):
    """Copy one company of another account into the caller's (settings only: no jobs, no
    notes; résumé choices dropped, the cloner picks later; due now). Name clash with the
    caller's own company -> 409 `name_taken` (a company is matched to jobs by its name, so
    a renamed twin would never match anything). Adds + commits; returns the new row."""
    from backend.models.db import Company
    caller = _require_two(db)
    src = _source_row(db, Company, source_id, caller)
    with unscoped():
        clash = (db.query(Company.id).filter(Company.account_id == caller,
                                             func.lower(Company.name) == (src.name or "").strip().lower()).first())
        if clash is not None:
            raise CloneError(409, "name_taken", f"You already have a company named {src.name}.")
        new = _company_copy(src, Company, caller, [], notes=None)
        db.add(new)
        db.commit()
        new_id = new.id
    return new_id


def clone_search(db, source_id):
    """Copy one search of another account into the caller's (due now). Name clash ->
    " (copy)", " (copy 2)", ... (search names are free labels, so renaming beats refusing).
    Built-in extension searches -> 409 `builtin_search`. Adds + commits; returns the new id."""
    from backend.models.db import Search
    from backend.seed import EXTENSION_SEARCH_MODES
    caller = _require_two(db)
    src = _source_row(db, Search, source_id, caller)
    if src.search_mode in EXTENSION_SEARCH_MODES:
        raise CloneError(409, "builtin_search", "Built-in extension searches exist in every account.")
    with unscoped():
        taken = {(n or "").strip().lower() for (n,) in db.query(Search.name).filter(Search.account_id == caller)}
        name, n = src.name, 1
        while name.strip().lower() in taken:
            n += 1
            name = f"{src.name} (copy)" if n == 2 else f"{src.name} (copy {n - 1})"
        new = _search_copy(src, Search, caller, name=name)
        db.add(new)
        db.commit()
        new_id = new.id
    return new_id


def seed_new_account(db, account_id) -> None:
    """The rows every account starts with: an empty Persona and the two built-in
    extension searches. No commit."""
    from backend.accounts.owned import _empty_persona_fields
    from backend.models.db import Persona
    from backend.seed import ensure_extension_searches
    with unscoped():
        if db.query(Persona.id).filter(Persona.account_id == account_id).first() is None:
            db.add(Persona(account_id=account_id, **_empty_persona_fields()))
        ensure_extension_searches(db, account_id)


def _source_values(db, source_id, owner_id) -> dict:
    """{key: stored value} the source holds as its own: the owner's are the install values;
    a member's are its own rows in sections it owns."""
    from backend.models.db import Setting
    if source_id == owner_id:
        return {r.key: r.value for r in db.query(Setting).filter(Setting.account_id.is_(None)).all()}
    out = {}
    for r in db.query(Setting).filter(Setting.account_id == source_id).all():
        mode = acct_settings.section_mode(db, source_id, acct_settings.section_of(r.key))
        if mode in (acct_settings.OWN, acct_settings.OWN_ALWAYS):
            out[r.key] = r.value
    return out


def _effective_value(db, source_id, owner_id, key: str) -> Optional[str]:
    """What the source account reads for `key` (the owner: the install value; a member:
    `resolve_for`, so an 'own' section with no row gives the seeded default, QA F5)."""
    if source_id != owner_id:
        return acct_settings.resolve_for(db, source_id, key)[0]
    row = acct_settings.install_row(db, key)
    return row.value if row is not None else None


def _set_policy(db, account_id, section: str, mode: str) -> None:
    from backend.models.db import SectionPolicy
    row = (db.query(SectionPolicy)
           .filter(SectionPolicy.account_id == account_id, SectionPolicy.section == section).first())
    if row is None:
        db.add(SectionPolicy(account_id=account_id, section=section, mode=mode))
    else:
        row.mode = mode


def _owns(db, account_id, key: str) -> bool:
    mode = acct_settings.section_mode(db, account_id, acct_settings.section_of(key))
    return mode in (acct_settings.OWN, acct_settings.OWN_ALWAYS)


def _remap_resume_value(value: str, resume_map: dict) -> Optional[str]:
    """default_resume_id: 'persona' stays; a copied résumé id becomes the copy's id; any
    other id is dropped (None)."""
    v = (value or "").strip()
    if not v:
        return v
    if v == "persona":
        return v
    return resume_map.get(v)


def copy_from(db, source_id, new_id, items: Iterable[str], owner_id) -> dict:
    """Deep-copy the chosen items of `source_id` into `new_id` (new ids, foreign keys and
    JSON id lists remapped, ids that were not copied dropped). No jobs, applications,
    letters or tracer links. No commit. Returns {item: rows copied}."""
    from backend.models.db import Company, Persona, Resume, Search, SectionPolicy
    from backend.seed import EXTENSION_SEARCH_MODES
    items = set(items)
    done: dict = {}
    resume_map: dict = {}   # str(old id) -> str(new id)
    with unscoped():
        db.flush()   # the new account's seeded Persona must be visible below
        if items & {"persona", "qa"}:
            src = db.query(Persona).filter(Persona.account_id == source_id).first()
            dst = db.query(Persona).filter(Persona.account_id == new_id).first()
            if src is not None and dst is not None:
                nodes = (["contact", "work_auth", "demographics", "compensation", "preferences",
                          "resume_content", "qa_bank"] if "persona" in items else ["qa_bank"])
                for node in nodes:
                    setattr(dst, node, copy.deepcopy(getattr(src, node)))
                if "persona" in items:
                    done["persona"] = 1
                done["qa"] = len(src.qa_bank or [])   # Q&A entries (persona includes them)

        if "resumes" in items:
            n = 0
            for r in (db.query(Resume).filter(Resume.account_id == source_id, Resume.is_base == True)  # noqa: E712
                      .order_by(Resume.created_at).all()):
                new = _clone(r, Resume, new_id, skip=("created_at", "updated_at"),
                             parent_id=None, job_id=None, id=uuid.uuid4())
                db.add(new)
                resume_map[str(r.id)] = str(new.id)
                n += 1
            done["resumes"] = n

        if "companies" in items:
            n = 0
            for c in db.query(Company).filter(Company.account_id == source_id).order_by(Company.name).all():
                selected = []
                for rid in (c.selected_resume_ids or []):
                    if str(rid) == "persona":
                        selected.append("persona")
                    elif str(rid) in resume_map:
                        selected.append(resume_map[str(rid)])
                db.add(_company_copy(c, Company, new_id, selected))
                n += 1
            done["companies"] = n

        if "searches" in items:
            n = 0
            for s in (db.query(Search).filter(Search.account_id == source_id,
                                              Search.search_mode.notin_(EXTENSION_SEARCH_MODES))
                      .order_by(Search.created_at).all()):
                db.add(_search_copy(s, Search, new_id))   # due at once, like the companies above
                n += 1
            done["searches"] = n

        if "settings" in items:
            n = 0
            if source_id != owner_id:
                for p in db.query(SectionPolicy).filter(SectionPolicy.account_id == source_id).all():
                    _set_policy(db, new_id, p.section, p.mode)
                    n += 1
                db.flush()
            for key, value in _source_values(db, source_id, owner_id).items():
                sec = acct_settings.SETTING_SECTIONS.get(acct_settings.section_of(key))
                if sec is None or sec["scope"] == acct_settings.OWNER_ONLY:
                    continue
                if key in VOICE_KEYS or key in EXCLUDE_KEYS or _is_personal(key):
                    continue
                if not _owns(db, new_id, key):
                    continue
                if key == "default_resume_id":
                    value = _remap_resume_value(value, resume_map)
                    if value is None:
                        continue
                acct_settings.put_setting(db, key, value, account_id=new_id)
                n += 1
            done["settings"] = n

        for item, keys in (("voices", VOICE_KEYS), ("excludes", EXCLUDE_KEYS)):
            if item not in items:
                continue
            n = 0
            section = acct_settings.section_of(keys[0])
            if acct_settings.SETTING_SECTIONS[section]["scope"] == acct_settings.POLICY:
                _set_policy(db, new_id, section, acct_settings.OWN)
                db.flush()
            for key in keys:
                value = _effective_value(db, source_id, owner_id, key)
                if value is not None:
                    acct_settings.put_setting(db, key, value, account_id=new_id)
                    n += 1
            done[item] = n
    return done


# ── Remove ───────────────────────────────────────────────────────────────────

def account_dirs(account_id) -> list:
    """Per-account directories on disk to remove with the account: MT-15's CLI homes
    (CODEX_HOME, agy HOME; the Claude Code token is a setting row) and, from MT-16, the
    LinkedIn / Jobright / Levels sessions under …/accounts/<id>/. Never exported."""
    from backend.accounts.credentials import account_roots
    roots: list = list(account_roots())
    return [os.path.join(r, str(account_id)) for r in roots]


def _delete_plan():
    """(label, model) in child-first order; job_locations and tracer clicks follow their
    parents' account."""
    from backend.models import db as m
    return [
        ("tracer_clicks", m.TracerClickEvent), ("tracer_links", m.TracerLink),
        ("interviews", m.Interview), ("applications", m.Application),
        ("cover_letters", m.CoverLetter), ("resumes", m.Resume),
        ("job_locations", m.JobLocation), ("llm_calls", m.LlmCallLog),
        ("job_runs", m.JobRun), ("scrape_log", m.ScrapeLog), ("activity_log", m.ActivityLog),
        ("jobs", m.Job), ("searches", m.Search), ("companies", m.Company),
        ("persona", m.Persona), ("settings", m.Setting), ("section_policies", m.SectionPolicy),
    ]


def _rows_of(db, model, account_id):
    from backend.models import db as m
    if model is m.TracerClickEvent:
        sub = select(m.TracerLink.id).where(m.TracerLink.account_id == account_id)
        return db.query(model).filter(model.tracer_link_id.in_(sub))
    if model is m.JobLocation:
        sub = select(m.Job.id).where(m.Job.account_id == account_id)
        return db.query(model).filter(model.job_id.in_(sub))
    return db.query(model).filter(model.account_id == account_id)


def delete_account_rows(db, account_id) -> dict:
    """Delete every row the account owns and the account itself, explicitly table by
    table (the FKs cascade on Postgres too; SQLite does not enforce them). Commits.
    Returns {label: rows deleted}."""
    from backend.models.db import Account
    counts = {}
    with unscoped():
        for label, model in _delete_plan():
            counts[label] = _rows_of(db, model, account_id).delete(synchronize_session=False)
        db.query(Account).filter(Account.id == account_id).delete(synchronize_session=False)
        db.commit()
    from backend.accounts import auth as _acct_auth
    _acct_auth.invalidate_accounts_cache()   # QA F9 / T6-02
    # Runners share these volumes, including when stopped. Tombstones prevent a
    # queued/stale request from restoring a removed login; in-flight calls clean
    # up again on exit. Never mark the owner's default home or another account.
    from pathlib import Path
    from backend.accounts.credentials import cli_account_roots
    from backend.cli_runner.paths import deletion_marker
    for root in cli_account_roots():
        marker = deletion_marker(Path(root) / str(account_id))
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch()
    removed_dirs = []
    for path in account_dirs(account_id):
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
            removed_dirs.append(path)
    counts["dirs"] = len(removed_dirs)
    counts["files"] = 0   # PDFs are never stored (rendered on demand)
    forget_account_memory(account_id)
    return counts


def forget_account_memory(account_id) -> None:
    """QA F8 / R5-10: everything in memory or /tmp keyed by a removed account goes with it:
    its LinkedIn PIN drop file, refresh phase and import progress, a live Telegram link code,
    PIN cooldown buckets and the last-active throttle. Modules that were never imported hold
    nothing, so they are looked up in sys.modules instead of being imported here."""
    import sys
    from backend.accounts import auth as acct_auth
    from backend.accounts.credentials import member_pin_file
    key = str(account_id)
    for pin in (member_pin_file(account_id), member_pin_file(account_id) + ".main"):   # mock, main
        try:
            os.remove(pin)
        except OSError:
            pass
    acct_auth._clear(account_id)
    acct_auth._touched.pop(key, None)
    refresh = sys.modules.get("backend.refresh_linkedin_session")
    if refresh is not None:
        # keyed (account id, session) since the two LinkedIn sessions split
        for k in [k for k in refresh._MEMBER_STATES if str(k[0] if isinstance(k, tuple) else k) == key]:
            refresh._MEMBER_STATES.pop(k, None)
    li = sys.modules.get("backend.scraper.sources.linkedin_extension")
    if li is not None:
        li._linkedin_import_progress.forget(account_id)
    tg = sys.modules.get("backend.notifier.telegram")
    if tg is not None:
        tg.forget_link_codes(account_id)


# ── Export ───────────────────────────────────────────────────────────────────

def _jsonable(v):
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, uuid.UUID):
        return str(v)
    if isinstance(v, bytes):
        return v.decode("utf-8", "replace")
    raise TypeError(f"not serialisable: {type(v).__name__}")


def _row(obj, skip=()):
    return {c.key: getattr(obj, c.key) for c in obj.__mapper__.column_attrs if c.key not in skip}


def _write_json_array(zf, name, rows) -> int:
    n = 0
    with zf.open(name, "w") as fh:
        fh.write(b"[")
        for r in rows:
            fh.write((b",\n" if n else b"\n") + json.dumps(r, default=_jsonable, ensure_ascii=False).encode())
            n += 1
        fh.write(b"\n]\n")
    return n


def _export_settings(db, account_id, owner_id) -> list:
    """The account's own settings rows (the owner's are the install values), secrets
    redacted as GET /api/settings does, server-only keys left out."""
    from backend.api.routes_settings import _HIDDEN_KEYS, _is_secret
    from backend.models.db import Setting
    q = (db.query(Setting).filter(Setting.account_id.is_(None)) if account_id == owner_id
         else db.query(Setting).filter(Setting.account_id == account_id))
    out = []
    for r in q.order_by(Setting.key).all():
        if r.key in _HIDDEN_KEYS:
            continue
        value = ("" if not r.value else "•" * 6) if _is_secret(r.key) else r.value
        out.append({"key": r.key, "value": value, "section": acct_settings.section_of(r.key)})
    return out


def build_export(db, account_id, owner_id) -> "tempfile.SpooledTemporaryFile":
    """A zip with one JSON file per table of the account's rows. Returned rewound; the
    caller streams and closes it."""
    from backend.models import db as m
    acc = None
    with unscoped():
        acc = db.query(m.Account).filter(m.Account.id == account_id).first()
    if acc is None:
        raise LookupError("account not found")
    tables = [
        ("persona", m.Persona), ("resumes", m.Resume), ("cover_letters", m.CoverLetter),
        ("searches", m.Search), ("companies", m.Company), ("jobs", m.Job),
        ("job_locations", m.JobLocation), ("applications", m.Application),
        ("interviews", m.Interview), ("tracer_links", m.TracerLink),
        ("tracer_click_events", m.TracerClickEvent), ("activity_log", m.ActivityLog),
        ("llm_call_log", m.LlmCallLog), ("job_runs", m.JobRun), ("scrape_log", m.ScrapeLog),
    ]
    buf = tempfile.SpooledTemporaryFile(max_size=32 * 1024 * 1024)
    counts = {}
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf, unscoped():
        account_row = _row(acc, skip=("pin_hash",))
        account_row["has_pin"] = bool(acc.pin_hash)
        zf.writestr("account.json", json.dumps(account_row, default=_jsonable, ensure_ascii=False, indent=1))
        for name, model in tables:
            q = _rows_of(db, model, account_id)
            if model is m.Job:
                from sqlalchemy.orm import undefer
                q = q.options(undefer(m.Job.cached_page_html), undefer(m.Job.cached_page_text))
            counts[name] = _write_json_array(zf, f"{name}.json", (_row(o) for o in q.yield_per(200)))
        settings_rows = _export_settings(db, account_id, owner_id)
        counts["settings"] = _write_json_array(zf, "settings.json", settings_rows)
        policies = []
        if account_id != owner_id:
            for sid, sec in acct_settings.SETTING_SECTIONS.items():
                policies.append({"section": sid, "scope": sec["scope"],
                                 "mode": acct_settings.section_mode(db, account_id, sid)})
        counts["section_policies"] = _write_json_array(zf, "section_policies.json", policies)
        manifest = {
            "format": "jobnavigator-account-export", "version": 1,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "account": {"id": str(acc.id), "name": acc.name, "role": acc.role},
            "counts": counts,
            "notes": [
                "One JSON array per table, rows exactly as stored (ids, timestamps in ISO 8601).",
                "Résumés and cover letters are included as JSON (json_data) only: their PDFs are "
                "rendered on demand and never stored, so there are no PDF files to include.",
                "Secret settings (API keys, passwords, tokens) are redacted as in the Settings "
                "screen; the owner's settings are the install values.",
                "CLI logins (Codex and Antigravity homes) are not included; the Claude Code "
                "token is a secret setting and is redacted.",
            ],
        }
        zf.writestr("manifest.json", json.dumps(manifest, indent=1, ensure_ascii=False))
    buf.seek(0)
    return buf
