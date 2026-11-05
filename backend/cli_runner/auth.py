"""Private service credential, generated once by the backend on a shared volume."""
import os
import secrets
from pathlib import Path


def token_path():
    return Path(os.getenv("JN_RUNNER_TOKEN_FILE", "/run/jobnavigator-runner/token"))


def read_token():
    return token_path().read_text(encoding="ascii").strip()


def ensure_token():
    path = token_path()
    try:
        existing = read_token()
    except FileNotFoundError:
        pass
    else:
        if not existing:
            raise RuntimeError("Runner credential file is empty")
        return existing
    path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic publication: readers never see a partially written credential.
    temporary = path.with_name(f".token-{secrets.token_hex(8)}")
    try:
        with temporary.open("x", encoding="ascii") as output:
            os.chmod(temporary, 0o600)
            output.write(secrets.token_urlsafe(48))
        try:
            os.link(temporary, path)
        except FileExistsError:
            pass
        token = read_token()
        if not token:
            raise RuntimeError("Runner credential file is empty")
        return token
    finally:
        temporary.unlink(missing_ok=True)
