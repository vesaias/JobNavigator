"""Per-account subscription-CLI logins (MT-15).

API keys need nothing here: they are settings in the 'models' section, so `get_setting`
already gives a member on 'own' its own key/provider/model (empty when unset, never the
owner's, QA F5) and a member on 'inherit' the owner's (MT-9). `llm_client` refuses an
empty key for such a member instead of using the `.env` key. The three subscription CLIs keep their login outside the settings table,
so they get per-account homes by the same rule:

- Claude Code: the `claude_code_oauth_token` setting (models section, a secret). The
  owner's install value when set, else today's `CLAUDE_CODE_OAUTH_TOKEN` env var; a member
  on 'own' with its own token uses that. The CLI is handed it as CLAUDE_CODE_OAUTH_TOKEN.
  A member on 'own' also runs it with `HOME=~/.claude-accounts/<account id>` and
  `CLAUDE_CONFIG_DIR=<that>/.claude`, so its transcripts stay out of the owner's ~/.claude.
- Codex CLI: `CODEX_HOME=~/.codex/accounts/<account id>` (in the codex_auth volume) for a
  member whose models section is 'own'; owner and 'inherit' keep the default ~/.codex.
- Antigravity CLI: `HOME=~/.gemini/accounts/<account id>` (in the antigravity_auth
  volume) for the same members, so its state dir is `<that>/.gemini/antigravity-cli`;
  owner and 'inherit' keep HOME (state ~/.gemini/antigravity-cli).

Removing an account deletes its CLI dirs (`admin.account_dirs`); export leaves them out.
`backend/scripts/cli_login.py` prints the login command for one account.
"""
import os
import uuid
from typing import Optional

from backend.accounts import settings as acct_settings

CLAUDE_TOKEN_KEY = "claude_code_oauth_token"
CLAUDE_TOKEN_ENV = "CLAUDE_CODE_OAUTH_TOKEN"
MODELS_SECTION = "models"

# Roots of the per-account homes; both sit inside the Docker volumes that already hold the
# owner's logins, so a member's login survives a rebuild too. Tests point them at tmp.
CODEX_ACCOUNTS_ROOT = "~/.codex/accounts"
AGY_ACCOUNTS_ROOT = "~/.gemini/accounts"
# QA F8 / R5-08: `claude -p` keeps a transcript of every prompt under its config dir; a
# member on its own models section runs with HOME and CLAUDE_CONFIG_DIR of its own here,
# so its résumé/JD prompts never land in the owner's ~/.claude. The token stays a setting,
# Claude tokens stay in settings; the shared claude_accounts volume lets the
# backend remove member transcripts even when the Claude runner is stopped.
CLAUDE_ACCOUNTS_ROOT = "~/.claude-accounts"
CLAUDE_CONFIG_SUBDIR = ".claude"
AGY_STATE_SUBDIR = os.path.join(".gemini", "antigravity-cli")


def _expand(path: str) -> str:
    return os.path.expanduser(path)


def cli_account_roots() -> list:
    """Auth/transcript roots shared with the independent runners."""
    return [_expand(CODEX_ACCOUNTS_ROOT), _expand(AGY_ACCOUNTS_ROOT), _expand(CLAUDE_ACCOUNTS_ROOT)]


def account_roots() -> list:
    """Every per-account root; removal deletes `<root>/<account id>` in each."""
    return cli_account_roots() + [LI_ACCOUNTS_ROOT]


def codex_home(account_id) -> str:
    return os.path.join(_expand(CODEX_ACCOUNTS_ROOT), str(account_id))


def claude_home(account_id) -> str:
    """HOME for an account's `claude -p` (config dir `<this>/.claude`, R5-08)."""
    return os.path.join(_expand(CLAUDE_ACCOUNTS_ROOT), str(account_id))


def claude_config_dir(account_id) -> str:
    return os.path.join(claude_home(account_id), CLAUDE_CONFIG_SUBDIR)


def agy_home(account_id) -> str:
    """HOME for an account's agy process (its state dir is `<this>/.gemini/antigravity-cli`)."""
    return os.path.join(_expand(AGY_ACCOUNTS_ROOT), str(account_id))


def agy_state_dir(account_id) -> str:
    return os.path.join(agy_home(account_id), AGY_STATE_SUBDIR)


def uses_own_logins(db, account_id) -> bool:
    """True when `account_id` is a member whose models section is 'own' (owner: False)."""
    mode = acct_settings.section_mode(db, account_id, MODELS_SECTION)
    return mode == acct_settings.OWN


def own_login_account(db) -> Optional[uuid.UUID]:
    """The current account when it is a member on its own models section, else None
    (owner, 'inherit', system code, no context): None = the install's default CLI homes."""
    member = acct_settings.member_account(db)
    if member is None:
        return None
    return member if uses_own_logins(db, member) else None


def claude_code_token(db) -> str:
    """The token the current account's Claude Code calls use, or "" to keep the
    process env (the owner's CLAUDE_CODE_OAUTH_TOKEN from .env).

    A member on its own models section never falls back to the owner's token (MT-16, same
    rule as Codex/agy): with no token of its own the call fails with a NonRetryable
    "not logged in" error that names Settings › Models."""
    member = own_login_account(db)
    if member is not None:
        row = acct_settings._account_row(db, member, CLAUDE_TOKEN_KEY)
        own = (row.value if row is not None else "") or ""
        if not own.strip():
            from backend.analyzer.llm_client import NonRetryableLLMError
            raise NonRetryableLLMError(
                "Claude Code is not logged in for this account: paste your Claude Code token "
                "(from `claude setup-token`) in Settings › Models")
        return own.strip()
    return (acct_settings.get_setting(db, CLAUDE_TOKEN_KEY) or "").strip()


# ── Scraper sessions (MT-16) ─────────────────────────────────────────────────
#
# The LinkedIn browser sessions are files; Jobright's session is a setting (section
# 'jobright': on 'own' the member's row, on 'inherit' the install row, so one Jobright
# account keeps one session) and Levels.fyi keeps none. The LinkedIn files follow the
# 'linkedin' section the same way (QA F5, R5-01): 'own' → the member's directory below,
# 'inherit' → the owner's paths.
# The OWNER keeps today's exact paths; a member gets a directory of its own that holds both
# LinkedIn cookie jars, inside the bind-mounted ~/.linkedin_api so it survives a rebuild.
#
#   extension import session   owner /root/.linkedin_api/li_cookies.json
#                              member /root/.linkedin_api/accounts/<id>/li_cookies.json
#   LinkedIn Personal scraper  owner /tmp/linkedin_cookies.json
#                              member /root/.linkedin_api/accounts/<id>/linkedin_cookies.json
#   session-refresh PIN drop   owner /tmp/li_pin.txt     member /tmp/li_pin_<id>.txt
#
# Removing an account deletes its directory (`admin.account_dirs`); export leaves it out.
# Tests point the constants at tmp dirs.
LI_ACCOUNTS_ROOT = "/root/.linkedin_api/accounts"
LI_EXTENSION_OWNER = "/root/.linkedin_api/li_cookies.json"
LI_PERSONAL_OWNER = "/root/.linkedin_api/linkedin_cookies.json"
# Where the owner's main jar lived until 3.2: /tmp is wiped on every rebuild, so each one signed the
# main account out; a jar still there moves to LI_PERSONAL_OWNER on first use.
LI_PERSONAL_LEGACY = "/tmp/linkedin_cookies.json"
LI_PIN_OWNER = "/tmp/li_pin.txt"
LI_EXTENSION_FILE = "li_cookies.json"
LI_PERSONAL_FILE = "linkedin_cookies.json"


LINKEDIN_SECTION = "linkedin"


def _linkedin_member(db) -> Optional[uuid.UUID]:
    member = acct_settings.member_account(db)
    if member is None:
        return None
    mode = acct_settings.section_mode(db, member, LINKEDIN_SECTION)
    return member if mode == acct_settings.OWN else None


def session_member(db=None) -> Optional[uuid.UUID]:
    """The current account when it is a member whose LinkedIn section is 'own' (QA F5,
    R5-01); None = the owner's paths: owner, system code, no context, and a member on
    'inherit' (it uses the owner's LinkedIn, so the owner's one session jar, PIN drop and
    refresh state, never a second login into the owner's account). Opens its own session
    when none is passed."""
    if db is not None:
        return _linkedin_member(db)
    from backend.models.db import SessionLocal
    own = SessionLocal()
    try:
        return _linkedin_member(own)
    finally:
        own.close()


def linkedin_shared_from_owner(db=None) -> bool:
    """True for a member whose LinkedIn section is 'inherit': its LinkedIn runs use the
    owner's session; refreshing that session is the owner's job (R5-01)."""
    def _check(d):
        member = acct_settings.member_account(d)
        return member is not None and _linkedin_member(d) is None
    if db is not None:
        return _check(db)
    from backend.models.db import SessionLocal
    own = SessionLocal()
    try:
        return _check(own)
    finally:
        own.close()


def linkedin_session_dir(account_id) -> str:
    return os.path.join(LI_ACCOUNTS_ROOT, str(account_id))


def linkedin_extension_cookies(db=None) -> str:
    """Cookie jar of the logged-in browser the extension import (Voyager) uses."""
    member = session_member(db)
    if member is None:
        return LI_EXTENSION_OWNER
    return os.path.join(linkedin_session_dir(member), LI_EXTENSION_FILE)


def linkedin_personal_cookies(db=None) -> str:
    """Cookie jar of the LinkedIn Personal scraper (also loaded by the session refresh)."""
    member = session_member(db)
    if member is None:
        if not os.path.exists(LI_PERSONAL_OWNER) and os.path.exists(LI_PERSONAL_LEGACY):
            try:
                import shutil
                os.makedirs(os.path.dirname(LI_PERSONAL_OWNER), exist_ok=True)
                shutil.move(LI_PERSONAL_LEGACY, LI_PERSONAL_OWNER)
            except OSError:
                return LI_PERSONAL_LEGACY
        return LI_PERSONAL_OWNER
    return os.path.join(linkedin_session_dir(member), LI_PERSONAL_FILE)


def linkedin_pin_file(db=None) -> str:
    """Where the emailed LinkedIn checkpoint PIN is dropped for the account's refresh."""
    member = session_member(db)
    if member is None:
        return LI_PIN_OWNER
    return member_pin_file(member)


def member_pin_file(account_id) -> str:
    """A member's PIN drop file (/tmp/li_pin_<id>.txt); removal deletes it (R5-10)."""
    root, ext = os.path.splitext(LI_PIN_OWNER)
    return f"{root}_{account_id}{ext}"
