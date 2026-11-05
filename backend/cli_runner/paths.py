"""Legacy auth paths shared by the backend and runners; existing volumes stay valid."""
import os
from pathlib import Path

CODEX_ACCOUNTS_ROOT = "~/.codex/accounts"
AGY_ACCOUNTS_ROOT = "~/.gemini/accounts"
CLAUDE_ACCOUNTS_ROOT = "~/.claude-accounts"
AGY_STATE_SUBDIR = os.path.join(".gemini", "antigravity-cli")


def codex_home(account_id):
    return os.path.join(os.path.expanduser(CODEX_ACCOUNTS_ROOT), str(account_id))


def agy_home(account_id):
    return os.path.join(os.path.expanduser(AGY_ACCOUNTS_ROOT), str(account_id))


def agy_state_dir(account_id):
    return os.path.join(agy_home(account_id), AGY_STATE_SUBDIR)


def claude_home(account_id):
    return os.path.join(os.path.expanduser(CLAUDE_ACCOUNTS_ROOT), str(account_id))


def claude_config_dir(account_id):
    return os.path.join(claude_home(account_id), ".claude")


def account_home(provider, account_id):
    return Path({"codex_cli": codex_home, "antigravity_cli": agy_home,
                 "claude_code": claude_home}[provider](account_id))


def deletion_marker(home):
    return Path(home).parent / ".deleted" / Path(home).name
