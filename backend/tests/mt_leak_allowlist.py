"""Routes the MT-3 leak harness (test_mt_leaks.py) does not call, because they are
install-wide by design or act on install-level state outside the database.

Key: (METHOD, path template exactly as FastAPI registers it). Value: one-line reason.
A stale entry (route renamed or removed) fails `test_allowlist_entries_exist`.
Do not park a route here because it leaks: mark it in KNOWN_LEAKS in test_mt_leaks.py.
"""

ALLOWLIST: dict[tuple[str, str], str] = {
    # Install password and liveness
    ("POST", "/api/auth/verify"): "install password check (no account involved)",
    ("POST", "/api/auth/set-session"): "install password session cookie (no account involved)",
    ("POST", "/api/auth/logout"): "clears this browser's session + account cookies",
    # MT-10 account selection: covered by test_mt_auth.py
    ("GET", "/api/auth/accounts"): "the picker lists every account (id, name, colour, role, has_pin) by design",
    ("POST", "/api/auth/switch"): "switches this browser's own cookie; PIN rules in test_mt_auth.py",
    ("POST", "/api/auth/verify-pin"): "checks a PIN, sets no cookie, changes nothing, returns that account's API token (MT-18, QA F1); test_mt_extension.py",
    ("GET", "/api/auth/me"): "the caller's own account; test_mt_auth.py",
    ("POST", "/api/auth/verify-owner-pin"): "re-signs the caller's own cookie; test_mt_auth.py",
    ("GET", "/health"): "liveness probe, no user data",
    # MT-11 account administration: the owner acts on other accounts by design (list with
    # counts, rename/PIN reset, remove, export), so "A sees/changes B" is the feature, not a
    # leak. test_mt_accounts_api.py covers the member side (other accounts reduced to
    # name/colour/role; PATCH/export on another account 403; DELETE owner-only).
    # POST /api/accounts stays in the harness (member 403; owner without PIN 409).
    ("GET", "/api/accounts"): "lists every account by design (member: names/colours only); test_mt_accounts_api.py",
    ("PATCH", "/api/accounts/{account_id}"): "owner renames / resets PINs of other accounts by design; member->other 403 in test_mt_accounts_api.py",
    ("DELETE", "/api/accounts/{account_id}"): "owner removes a member by design (typed name, backup first); member 403 in test_mt_accounts_api.py",
    ("GET", "/api/accounts/{account_id}/export"): "owner exports any account by design; member->other 403 in test_mt_accounts_api.py",
    ("POST", "/api/accounts/{account_id}/api-token"): "the caller's own account only (owner->member and member->owner 403); test_mt_auth.py, test_qa_r2_01.py",

    # MT-20 "Copy from…": the pickers intentionally list OTHER accounts' company/search rows
    # (picker fields only: no notes, jobs or counts). test_mt_clone.py covers the visibility rules.
    ("GET", "/api/companies/clone-sources"): "lists other accounts' company names/URLs by design (copy-from picker); test_mt_clone.py",
    ("GET", "/api/searches/clone-sources"): "lists other accounts' search names/terms by design (copy-from picker); test_mt_clone.py",

    # Settings (MT-9): A is the owner, whose view IS the install values; members' own rows
    # are not AccountScoped (Setting is read explicitly), so the harness seeds none.
    # test_mt_settings.py covers member reads/writes and that the owner never sees a
    # member's own values. /settings/sections and /settings/policies go through the harness.
    ("GET", "/api/settings"): "owner = install values; member/own-row isolation in test_mt_settings.py",
    ("PATCH", "/api/settings"): "owner writes install values + reconfigures the scheduler; member writes in test_mt_settings.py",
    ("GET", "/api/settings/defaults"): "static seed defaults",

    # Static catalogs
    ("GET", "/api/resumes/templates"): "template files on disk, shared by every account",
    ("GET", "/api/cover-letters/templates"): "template files on disk, shared by every account",
    ("GET", "/api/llm/efforts"): "static reasoning-effort catalog",
    ("GET", "/api/llm/models"): "provider model catalog fetched over the network",
    ("GET", "/api/searches/countries"): "static country list",
    ("GET", "/api/updates"): "install-wide update check fetched over the network, no account data; test_update_check.py",

    # Install-level sessions and bots (per-account in MT-16 / MT-17)
    ("GET", "/api/linkedin/session"): "the caller's own LinkedIn cookie jar (MT-16; owner = today's path)",
    ("POST", "/api/linkedin/session/refresh"): "acts on the caller's own session files (MT-16)",
    ("POST", "/api/linkedin/session/pin"): "acts on the caller's own session files (MT-16)",
    # Telegram (MT-17): routing and per-account sends covered by test_mt_telegram.py.
    ("POST", "/api/telegram/webhook"): "public household-bot webhook; chat id -> account routing in test_mt_telegram.py",
    ("POST", "/api/telegram/webhook/{bot_account_id}"): "public webhook of a member's own bot (its own secret); test_mt_telegram.py",
    ("POST", "/api/telegram/register-webhook"): "household bot = owner only, a member's own bot = its own; test_mt_telegram.py",
    ("POST", "/api/telegram/rotate-webhook-secret"): "household bot secret, owner only (member 403 in test_mt_telegram.py)",
    ("POST", "/api/telegram/test"): "sends to the caller's own chat on its own bot (Telegram, not the DB); test_mt_telegram.py",

    # Install-level system work (stays install-level per MT-7)
    ("GET", "/api/scheduler/jobs"): "the one process-wide APScheduler",
    ("POST", "/api/db/backup"): "pg_dump of the whole install (owner/system)",
    ("POST", "/api/h1b/refresh"): "install-wide visa cache refresh",

    # Public tracer redirects: resolve any account's token by design; MT-6 looks the
    # token up unscoped and records the click under the link's own account.
    ("GET", "/cv/{token}"): "public tracer redirect, resolves any account's token by design",
    ("GET", "/"): "public ?cv= tracer redirect, resolves any account's token by design",
}
