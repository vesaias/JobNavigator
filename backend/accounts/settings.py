"""Account-scoped settings and section policies (MT-9).

A setting has an install value (`settings.account_id IS NULL`, what the owner edits; the
owner's values ARE the install values) and, per member, optionally an own value (a row
with that member's account_id). Which one a member reads depends on the key's section:

- scope 'owner_only': always the install value; members cannot write it.
- scope 'own_always': always the member's own row; with no row yet the seeded default,
  never the owner's value (a chat id, a mailbox, a résumé id are personal).
- scope 'policy': the owner picks per member 'inherit' (install value, read-only) or
  'own' (the member's row when one exists, else the seeded default). No
  `section_policies` row = the section's default.

QA F5 (R3-01/R3-02/T3-06): 'own' never falls back to the owner's install value. A member
on 'own' with no row of its own reads the seeded default, exactly like own_always: empty
for credentials, emails, sessions and API keys; the seeded lists for the global excludes
(a new member starts from the defaults, not the owner's personal lists, unless copy-from
"excludes" copied them); the seeded prompts/models elsewhere. Sharing the owner's value is
what 'inherit' is for.

Every settings read in the backend goes through `get_setting()` (or a module-local
wrapper that calls it), so this file is the one place that knows the rules. The owner,
system code (`unscoped()`) and code with no account context read install values exactly
as before MT-9.

`SETTING_SECTIONS` is served to the UI at GET /api/settings/sections; the ids of the
sections with a `ui` entry match the anchor ids of the Settings screen
(frontend/src/screens/Settings.jsx). Appearance/theme are per browser and not here.
"""
import uuid
from typing import Optional

from backend.accounts.context import current_account, is_unscoped, owner_id_for_session

POLICY = "policy"
OWN_ALWAYS = "own_always"
OWNER_ONLY = "owner_only"
INHERIT = "inherit"
OWN = "own"
POLICY_MODES = (INHERIT, OWN)

_LLM_FEATURES = ("", "llm_fallback_", "scoring_", "cv_tailor_", "cover_letter_", "autofill_", "email_")


# One API key per provider (3.1): every model slot on a provider uses its key, so switching a
# slot's provider back and forth never loses or mis-sends a key. Setting = env var in lower case.
PROVIDER_KEY_SETTINGS = {"claude_api": "anthropic_api_key", "openai": "openai_api_key",
                         "openrouter": "openrouter_api_key", "opencode_go": "opencode_api_key"}
# The per-slot keys they replace: migrated once (seed.migrate_llm_provider_keys), then neither
# served nor writable nor read; the rows stay one release for a downgrade.
LEGACY_LLM_KEY_SETTINGS = ("llm_api_key", "llm_fallback_api_key", "scoring_llm_api_key",
                           "cv_tailor_llm_api_key", "cover_letter_llm_api_key",
                           "autofill_llm_api_key", "email_llm_api_key")


def _llm_keys() -> list:
    keys = []
    for f in _LLM_FEATURES:
        base = "llm_fallback" if f == "llm_fallback_" else f"{f}llm"
        for part in ("provider", "model", "effort"):
            keys.append(f"{base}_{part}")
    return keys + list(PROVIDER_KEY_SETTINGS.values())


# (id, label, scope, default mode, Settings-screen sections it appears in, keys)
_SECTIONS = [
    # shown under Display on the Settings screen, with the browser-only look rows
    ("feed", "Feed", POLICY, OWN, ["appearance"], ["feed_zoom_floater"]),
    # claude_code_oauth_token: the Claude Code subscription login per account (MT-15).
    ("models", "Models", POLICY, INHERIT, ["models"], _llm_keys() + ["llm_models_list", "claude_code_oauth_token"]),
    # The host's local model servers: one address per install, so a member cannot point the
    # backend at an arbitrary internal URL. Shown in Settings › Models.
    ("llm_local", "Local model servers", OWNER_ONLY, INHERIT, ["models"], ["lmstudio_base_url", "ollama_base_url"]),
    ("scoring", "Scoring behavior", POLICY, INHERIT, ["scoring"], [
        "scoring_default_depth", "on_save_action", "prompt_caching_enabled",
        "scoring_rubric", "scoring_output_light", "scoring_output_full"]),
    # A résumé id belongs to one account: never inherited (MT-4 leftover).
    ("default_resume", "Default résumé", OWN_ALWAYS, OWN, ["scoring"], ["default_resume_id"]),
    # Process-wide semaphores: one value for the install.
    ("limits", "Parallel limits", OWNER_ONLY, INHERIT, ["scoring", "tailoring", "scheduler"], [
        "scoring_max_concurrent", "tailoring_max_concurrent", "scrape_max_concurrent"]),
    ("tailoring", "Tailoring", POLICY, INHERIT, ["tailoring"], [
        "cv_tailor_prompt", "persona_tailor_prompt", "tailor_auto_quick_score"]),
    ("letters", "Cover letters", POLICY, INHERIT, ["letters"], [
        "cover_letter_default_voice", "cover_letter_voice_presets", "cover_letter_prompt",
        "cover_letter_template"]),
    ("autofill", "Autofill", POLICY, INHERIT, ["autofill"], [
        "autofill_default_length", "autofill_prompt", "autofill_field_patterns",
        "autofill_option_synonyms"]),
    ("prep", "Interview prep", POLICY, INHERIT, ["prep"], ["prep_ask", "prep_include"]),
    ("emailclass", "Email classification", POLICY, INHERIT, ["emailclass"], [
        "email_llm_enabled", "email_llm_confidence_threshold", "email_llm_prompt",
        "email_gmail_query_subjects", "email_gmail_query_senders", "email_gmail_query_exclusions"]),
    ("scheduler", "Scheduler", POLICY, INHERIT, ["scheduler"], [
        "scrape_interval_minutes", "email_check_interval_minutes", "job_archive_after_days",
        "auto_reject_after_days", "reject_cron", "digest_cron", "cleanup_cron"]),
    ("backups", "Backups", OWNER_ONLY, INHERIT, ["scheduler", "advanced"], ["backup_cron"]),
    ("h1b", "H-1B", OWNER_ONLY, INHERIT, ["scheduler"], ["h1b_cron"]),
    ("exclude", "Global exclude", POLICY, OWN, ["exclude"], [
        "body_exclusion_phrases", "title_exclude_global", "company_exclude_global"]),
    ("dedup", "Dedup tracking params", OWNER_ONLY, INHERIT, ["dedup"], ["dedup_tracking_params"]),
    # where each kind of copy goes (posting_links.py): ignored (default) or new
    ("copies", "Copies of a posting", POLICY, INHERIT, ["copies"], [
        "dedup_copy_link", "dedup_copy_city", "dedup_copy_repost"]),
    # MT-17: telegram_bot_mode / telegram_bot_token pick a member's own bot (the owner always
    # uses the household bot); telegram_own_webhook_secret signs that bot's webhook (never served).
    ("notifications", "Notifications", OWN_ALWAYS, OWN, ["notifications"], [
        "telegram_enabled", "telegram_chat_id", "fit_score_threshold",
        "telegram_bot_mode", "telegram_bot_token", "telegram_own_webhook_secret"]),
    # The household bot's webhook secret: one per bot, the bot is the install's (owner's).
    ("telegram_bot", "Telegram bot", OWNER_ONLY, INHERIT, ["notifications"], ["telegram_webhook_secret"]),
    ("tracer", "Tracked links", OWNER_ONLY, INHERIT, ["tracer"], [
        "tracer_links_enabled", "tracer_links_base_url", "tracer_links_url_style"]),
    ("jobright", "Jobright.ai", POLICY, OWN, ["jobright"], [
        "jobright_email", "jobright_password", "jobright_session_id", "jobright_session_obtained_at"]),
    # PR #28: a paid credential. 'own' (default) = the member's own token or none, never the
    # owner's; 'inherit' = the member's Apify searches bill the owner's Apify account.
    ("apify", "Apify", POLICY, OWN, ["apify"], ["apify_api_key"]),
    ("linkedin", "LinkedIn", POLICY, OWN, ["linkedin"], [
        "linkedin_email", "linkedin_password", "linkedin_mock_email", "linkedin_mock_password"]),
    ("advanced", "Advanced", OWNER_ONLY, INHERIT, ["advanced"], ["proxy_url", "dashboard_api_key"]),
    # telemetry/level.py: one choice per install, the owner's (JN_TELEMETRY overrides it)
    ("telemetry", "Telemetry", OWNER_ONLY, INHERIT, ["telemetry"], ["telemetry_level"]),
    # Not a section of the Settings screen. MT-19: the token is connected from a row in Email
    # classification (GET /api/gmail/connect); gmail_token_status = the "expired" marker after
    # an invalid_grant (never served).
    ("gmail", "Gmail", OWN_ALWAYS, OWN, [], ["gmail_processed_ids", "gmail_refresh_token", "gmail_token_status"]),
    # account_cookie_secret: HMAC key of the jn_account cookie (MT-10); never served.
    # telemetry_install_id / telemetry_last_sent_at: telemetry state, never served.
    ("system", "System", OWNER_ONLY, INHERIT, [], ["llm_seeded_models", "llm_local_seed_cleared", "account_cookie_secret",
                                                   "telemetry_install_id", "telemetry_last_sent_at"]),
]

SETTING_SECTIONS = {
    sid: {"id": sid, "label": label, "scope": scope, "default": default, "ui": list(ui), "keys": list(keys)}
    for sid, label, scope, default, ui, keys in _SECTIONS
}
KEY_SECTION = {k: sid for sid, *_rest, keys in _SECTIONS for k in keys}
FALLBACK_SECTION = "system"  # a key no section lists is install-only


class SettingNotWritable(Exception):
    """A member tried to write keys whose section they do not own."""

    def __init__(self, keys):
        self.keys = sorted(keys)
        super().__init__(", ".join(self.keys))


def section_of(key: str) -> str:
    return KEY_SECTION.get(key, FALLBACK_SECTION)


def sections_payload() -> list:
    """GET /api/settings/sections: the table, in Settings-screen order."""
    return [dict(SETTING_SECTIONS[sid]) for sid, *_ in _SECTIONS]


# ── Who is reading ───────────────────────────────────────────────────────────

def member_account(db) -> Optional[uuid.UUID]:
    """The current account when it is a member, else None (owner, system code, no
    context, or no accounts table): None means "read and write install values"."""
    if is_unscoped():
        return None
    acc = current_account.get()
    if acc is None:
        return None
    owner = owner_id_for_session(db)
    if owner is None or acc == owner:
        return None
    return acc


def section_mode(db, account_id, section_id: str) -> str:
    """'inherit' | 'own' | 'own_always' | 'owner_only' for `account_id` (a member)."""
    from backend.models.db import SectionPolicy
    sec = SETTING_SECTIONS.get(section_id) or SETTING_SECTIONS[FALLBACK_SECTION]
    if sec["scope"] != POLICY:
        return sec["scope"]
    row = (db.query(SectionPolicy.mode)
           .filter(SectionPolicy.account_id == account_id, SectionPolicy.section == sec["id"])
           .first())
    return row[0] if row and row[0] in POLICY_MODES else sec["default"]


def _owns(mode: str) -> bool:
    return mode in (OWN, OWN_ALWAYS)


# ── Reads ────────────────────────────────────────────────────────────────────

def install_row(db, key: str):
    from backend.models.db import Setting
    return db.query(Setting).filter(Setting.key == key, Setting.account_id.is_(None)).first()


def _account_row(db, account_id, key: str):
    from backend.models.db import Setting
    return db.query(Setting).filter(Setting.key == key, Setting.account_id == account_id).first()


def _seeded(key: str) -> Optional[str]:
    from backend.seed import DEFAULT_SETTINGS
    entry = DEFAULT_SETTINGS.get(key)
    return entry[0] if entry else None


def resolve_for(db, account_id, key: str):
    """(value, source) `account_id` (a member) reads for `key`: its own row in a section it
    owns ('account'), else the seeded default ('default'; None when the key has no seeded
    value) — never the install value; in an inherited / owner-only section the install
    value ('install'). See the module docstring (QA F5)."""
    if _owns(section_mode(db, account_id, section_of(key))):
        row = _account_row(db, account_id, key)
        if row is not None:
            return row.value, "account"
        seeded = _seeded(key)
        return (seeded, "default") if seeded is not None else (None, None)
    row = install_row(db, key)
    return (row.value, "install") if row is not None else (None, None)


def resolve_setting(db, key: str):
    """(value, source) for the current account: source 'install' | 'account' | 'default'
    (seeded default: a member section it owns with no row yet) | None (no value anywhere)."""
    member = member_account(db)
    if member is not None:
        return resolve_for(db, member, key)
    row = install_row(db, key)
    return (row.value, "install") if row is not None else (None, None)


def get_setting(db, key: str, default=None):
    """The value the current account sees for `key` (the stored string, as `row.value`
    was), or `default` when no row applies. The one settings read in the backend."""
    value, _source = resolve_setting(db, key)
    return default if value is None else value


def get_install_setting(db, key: str, default=None):
    """The install value regardless of the account (auth key, webhook secret)."""
    row = install_row(db, key)
    return default if row is None else row.value


def default_resume_ids(db) -> list:
    """`selected_resume_ids` for a company created on the fly (apply, save, auto-create):
    the current account's default résumé, or [] when it has none or the stored id is not
    one of its base résumés (a member never gets another account's résumé id)."""
    from backend.models.db import Resume
    value = (get_setting(db, "default_resume_id") or "").strip()
    if not value:
        return []
    if value == "persona":
        return [value]
    try:
        rid = uuid.UUID(value)
    except ValueError:
        return []
    found = db.query(Resume.id).filter(Resume.id == rid, Resume.is_base == True).first()  # noqa: E712 (scoped)
    return [value] if found else []


# ── Writes ───────────────────────────────────────────────────────────────────

def write_targets(db, keys) -> dict:
    """{key: account id or None (install)} for a PATCH, all-or-nothing (MT-14).

    Owner / system: every key → install. Member: keys of sections it owns → its own rows;
    the rest → install when the browser holds a live owner unlock (the owner entered their
    PIN, `is_owner_unlocked()`), else SettingNotWritable naming them."""
    from backend.accounts.context import is_owner_unlocked
    member = member_account(db)
    if member is None:
        return {k: None for k in keys}
    modes = {}
    out, denied = {}, []
    for k in keys:
        sid = section_of(k)
        if sid not in modes:
            modes[sid] = section_mode(db, member, sid)
        if _owns(modes[sid]):
            out[k] = member
        elif is_owner_unlocked():
            out[k] = None
        else:
            denied.append(k)
    if denied:
        raise SettingNotWritable(denied)
    return out


def acts_as_owner(db) -> bool:
    """Owner, system code, or a member with a live owner unlock (MT-14)."""
    from backend.accounts.context import is_owner_unlocked
    return member_account(db) is None or is_owner_unlocked()


def put_setting(db, key: str, value: str, account_id=None, description=None):
    """Upsert the row for (key, account_id) — None = install. No commit."""
    from backend.models.db import Setting
    row = install_row(db, key) if account_id is None else _account_row(db, account_id, key)
    if row is not None:
        row.value = value
        return row
    row = Setting(key=key, value=value, account_id=account_id, description=description)
    db.add(row)
    return row


def set_setting(db, key: str, value: str, description=None):
    """Write `key` where the current account reads it from: a member's own row when the
    member owns the section, else the install row (runtime state such as a scraper
    session or processed-mail ids). No commit."""
    member = member_account(db)
    target = None
    if member is not None and _owns(section_mode(db, member, section_of(key))):
        target = member
    return put_setting(db, key, value, account_id=target, description=description)


# ── The whole map (GET /api/settings) ────────────────────────────────────────

def effective_rows(db):
    """[(key, value, source)] the current account sees. For the owner: the install rows in
    the order the database returns them (the pre-MT-9 response, unchanged)."""
    from backend.models.db import Setting
    install = db.query(Setting).filter(Setting.account_id.is_(None)).all()
    member = member_account(db)
    if member is None:
        return [(r.key, r.value, "install") for r in install]
    own = {r.key: r.value for r in db.query(Setting).filter(Setting.account_id == member).all()}
    modes = {}
    out = []
    seen = set()
    keys = [r.key for r in install] + [k for k in own if k not in {r.key for r in install}]
    install_values = {r.key: r.value for r in install}
    for key in keys:
        if key in seen:
            continue
        seen.add(key)
        sid = section_of(key)
        if sid not in modes:
            modes[sid] = section_mode(db, member, sid)
        mode = modes[sid]
        if _owns(mode) and key in own:
            out.append((key, own[key], "account"))
        elif _owns(mode):
            seeded = _seeded(key)
            if seeded is not None:
                out.append((key, seeded, "default"))
        elif key in install_values:
            out.append((key, install_values[key], "install"))
    return out


def key_meta(db, keys) -> dict:
    """{key: {section, editable}} for the current account (source is added by the caller)."""
    member = member_account(db)
    modes = {}
    meta = {}
    for key in keys:
        sid = section_of(key)
        if member is None:
            editable = True
        else:
            if sid not in modes:
                modes[sid] = section_mode(db, member, sid)
            editable = _owns(modes[sid])
        meta[key] = {"section": sid, "editable": editable}
    return meta


def is_owner_caller(db) -> bool:
    return member_account(db) is None
