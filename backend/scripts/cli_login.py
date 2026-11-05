"""Print the command that logs one account into a subscription CLI (MT-15).

Run inside the backend container (it reads the accounts table):

    docker compose exec backend python -m backend.scripts.cli_login codex "Partner"
    docker compose exec backend python -m backend.scripts.cli_login agy <account id>
    docker compose exec backend python -m backend.scripts.cli_login claude Owner

Providers: codex, agy (antigravity), claude. The account is a name (case-insensitive) or
an id. It prints the `docker compose run --rm -it <runner> …` command to run on the host:

- codex / agy: the owner logs into the default home (~/.codex, ~/.gemini); a member gets
  its own (`CODEX_HOME=~/.codex/accounts/<id>`, agy `HOME=~/.gemini/accounts/<id>`), which
  is used only while its Models section is set to Own (Settings › Accounts policies).
- claude: `claude setup-token` prints a token; paste it into Settings › Models ›
  Claude Code token (a member: with its own Models section). The owner may keep it in .env
  as CLAUDE_CODE_OAUTH_TOKEN instead.

Nothing is logged in here; the per-account directory is created so the command works.
"""
import argparse
import os
import sys
import uuid

PROVIDERS = {"codex": "codex", "agy": "agy", "antigravity": "agy", "claude": "claude",
             "claude_code": "claude", "codex_cli": "codex", "antigravity_cli": "agy"}


def find_account(db, ref: str):
    from backend.accounts.context import unscoped
    from backend.models.db import Account
    with unscoped():
        try:
            acc = db.query(Account).filter(Account.id == uuid.UUID(ref)).first()
            if acc is not None:
                return acc
        except ValueError:
            pass
        matches = [a for a in db.query(Account).all() if (a.name or "").strip().lower() == ref.strip().lower()]
    return matches[0] if len(matches) == 1 else None


def login_lines(provider: str, account, own_logins: bool, make_dirs: bool = True) -> list:
    """The lines to print for `account` (an Account row). `own_logins`: a member whose
    Models section is Own (the per-account home is in use)."""
    from backend.accounts import credentials as C
    is_owner = account.role == "owner"
    lines = []
    if provider == "claude":
        lines.append("docker compose run --rm -it claude-runner claude setup-token")
        if is_owner:
            lines.append("# Paste the printed token into Settings › Models › Claude Code token, "
                         "or put it in .env as CLAUDE_CODE_OAUTH_TOKEN and run `docker compose up -d backend`.")
        else:
            lines.append(f"# Switch to {account.name}, then paste the printed token into "
                         "Settings › Models › Claude Code token.")
    elif provider == "codex":
        if is_owner:
            lines.append("docker compose run --rm -it codex-runner codex login --device-auth")
            lines.append("docker compose run --rm codex-runner codex login status")
        else:
            home = C.codex_home(account.id)
            if make_dirs:
                os.makedirs(home, exist_ok=True)
            lines.append(f"docker compose run --rm -it -e CODEX_HOME={home} codex-runner codex login --device-auth")
            lines.append(f"docker compose run --rm -e CODEX_HOME={home} codex-runner codex login status")
    elif provider == "agy":
        if is_owner:
            lines.append("docker compose run --rm -it antigravity-runner agy")
        else:
            home = C.agy_home(account.id)
            if make_dirs:
                os.makedirs(home, exist_ok=True)
            lines.append(f"docker compose run --rm -it -e HOME={home} antigravity-runner agy")
        lines.append("# Sign in when agy asks, then quit it (/quit).")
    if not is_owner and not own_logins:
        lines.append(f"# Note: {account.name}'s Models section inherits the owner's, so the owner's "
                     "login is used until the owner sets it to Own.")
    return lines


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("provider", help="codex | agy | claude")
    parser.add_argument("account", help="account name or id")
    args = parser.parse_args(argv)
    provider = PROVIDERS.get(args.provider.strip().lower())
    if provider is None:
        print(f"Unknown provider {args.provider!r}; use codex, agy or claude.", file=sys.stderr)
        return 2
    from backend.accounts.credentials import uses_own_logins
    from backend.models.db import SessionLocal
    db = SessionLocal()
    try:
        account = find_account(db, args.account)
        if account is None:
            print(f"No single account named or with id {args.account!r}.", file=sys.stderr)
            return 1
        own = account.role != "owner" and uses_own_logins(db, account.id)
        for line in login_lines(provider, account, own):
            print(line)
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
