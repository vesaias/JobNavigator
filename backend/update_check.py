"""Is a newer JobNavigator available? Read-only: it reports, it never updates.

The owner picks one mode (install setting `update_check_mode`):

- `release` (default): GitHub's latest release of `update_check_repo` against APP_VERSION.
- `commit`: the head of `main` in that repository against the commit this install runs.
  The commit comes from the clone's `.git` (docker-compose.yml mounts it read-only):
  Compose bind-mounts ./backend, so the clone, not the image, is the code that runs.
- `off`: no request leaves the install.

Only api.github.com is called, without a token and without any data about the install.
The anonymous limit is 60 requests an hour per address, so a result is cached for
CACHE_SECONDS (a failure for ERROR_SECONDS), and "Check now" is limited to one
request each FORCE_SECONDS. Never raises: a network or API failure is a result
with `error` set.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx

from backend.version import APP_VERSION

logger = logging.getLogger("jobnavigator.update_check")

DEFAULT_REPO = "vesaias/JobNavigator"
BRANCH = "main"
MODES = ("release", "commit", "off")
DEFAULT_MODE = "release"
API = "https://api.github.com"
TIMEOUT = 10
CACHE_SECONDS = 6 * 3600
ERROR_SECONDS = 15 * 60
FORCE_SECONDS = 60
# No token, no install data: the User-Agent names the app, not the install.
_HEADERS = {"Accept": "application/vnd.github+json", "User-Agent": "JobNavigator-update-check",
            "X-GitHub-Api-Version": "2022-11-28"}

REPO_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/[A-Za-z0-9._-]{1,100}$")
_SHA = re.compile(r"^[0-9a-f]{40}$")
GIT_DIR = Path(os.getenv("JN_GIT_DIR") or Path(__file__).resolve().parents[1] / ".git")


# ── the running commit ──────────────────────────────────────────────────────

def _read(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def read_local_commit(git_dir: Path = GIT_DIR) -> Optional[str]:
    """The commit HEAD points to, read from the files (no git binary), or None.

    Handles a branch HEAD (loose ref, then packed-refs), a detached HEAD, and a
    worktree (`.git` is a file with `gitdir:`; refs live in the common dir)."""
    pointer = _read(git_dir) if git_dir.is_file() else None
    if pointer is not None:
        if not pointer.startswith("gitdir:"):
            return None
        git_dir = (git_dir.parent / pointer[len("gitdir:"):].strip()).resolve()
    head = _read(git_dir / "HEAD")
    if not head:
        return None
    if _SHA.match(head):
        return head
    if not head.startswith("ref:"):
        return None
    ref = head[len("ref:"):].strip()
    common = _read(git_dir / "commondir")
    roots = [git_dir] + ([(git_dir / common).resolve()] if common else [])
    for root in roots:
        sha = _read(root / ref)
        if sha and _SHA.match(sha):
            return sha
    for root in roots:
        for line in (_read(root / "packed-refs") or "").splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[1] == ref and _SHA.match(parts[0]):
                return parts[0]
    return None


# ── comparison ──────────────────────────────────────────────────────────────

def version_tuple(v: str) -> tuple:
    """'v3.1' / '3.1.0' -> (3, 1, 0); anything non-numeric counts as 0."""
    parts = re.split(r"[.\-+]", (v or "").strip().lstrip("vV"))[:3]
    nums = [int(p) if p.isdigit() else 0 for p in parts]
    return tuple(nums + [0] * (3 - len(nums)))


def _result(mode: str, repo: str, commit: Optional[str], **fields) -> dict:
    base = {
        "mode": mode, "repo": repo, "branch": BRANCH,
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "current": {"version": APP_VERSION, "commit": commit},
        "latest": None, "update_available": False, "behind_by": None,
        "url": None, "message": "", "error": None,
    }
    base.update(fields)
    return base


async def _get(client: httpx.AsyncClient, path: str) -> Optional[dict]:
    """GET one API path. None on 404/422 (an unknown release, ref or commit);
    other failures raise httpx.HTTPError."""
    r = await client.get(f"{API}{path}")
    if r.status_code in (404, 422):
        return None
    r.raise_for_status()
    return r.json()


async def check_release(client: httpx.AsyncClient, repo: str, commit: Optional[str]) -> dict:
    data = await _get(client, f"/repos/{repo}/releases/latest")
    if not data or not data.get("tag_name"):
        return _result("release", repo, commit, message=f"{repo} has no published release.")
    tag = str(data["tag_name"])
    latest = tag.lstrip("vV")
    newer = version_tuple(latest) > version_tuple(APP_VERSION)
    return _result(
        "release", repo, commit, update_available=newer, url=data.get("html_url"),
        latest={"version": latest, "commit": None, "date": data.get("published_at"), "url": data.get("html_url")},
        message=(f"JobNavigator {latest} is available (this install runs {APP_VERSION})." if newer
                 else f"JobNavigator {APP_VERSION} is the latest release."),
    )


async def check_commit(client: httpx.AsyncClient, repo: str, commit: Optional[str]) -> dict:
    data = await _get(client, f"/repos/{repo}/commits/{BRANCH}")
    if not data or not data.get("sha"):
        return _result("commit", repo, commit, message=f"{repo} has no branch {BRANCH}.")
    head = str(data["sha"])
    date = ((data.get("commit") or {}).get("committer") or {}).get("date")
    url = data.get("html_url")
    latest = {"version": None, "commit": head, "date": date, "url": url}
    if not commit:
        return _result("commit", repo, None, latest=latest, url=url, update_available=None,
                       message="The running commit is unknown: the backend cannot read the clone's .git.")
    if commit == head:
        return _result("commit", repo, commit, latest=latest,
                       message=f"This install runs the head of {repo} {BRANCH} ({head[:7]}).")
    diff = await _get(client, f"/repos/{repo}/compare/{commit}...{head}")
    if diff is None:
        return _result("commit", repo, commit, latest=latest, url=url, update_available=None,
                       message=f"The running commit {commit[:7]} is not in {repo}; {BRANCH} is at {head[:7]}.")
    status, ahead = diff.get("status"), int(diff.get("ahead_by") or 0)
    if status in ("ahead", "diverged") and ahead:
        return _result(
            "commit", repo, commit, latest=latest, update_available=True, behind_by=ahead,
            url=diff.get("html_url") or url,
            message=f"{repo} {BRANCH} has {ahead} new commit{'s' if ahead != 1 else ''} ({commit[:7]} → {head[:7]}).",
        )
    return _result("commit", repo, commit, latest=latest,
                   message=f"The running commit {commit[:7]} already contains {repo} {BRANCH} ({head[:7]}).")


# ── cached entry point ──────────────────────────────────────────────────────

_cache: dict = {"key": None, "result": None, "expires": 0.0, "fetched": 0.0}
_lock = asyncio.Lock()


def settings_of(db) -> tuple[str, str]:
    """(mode, repo) from the install settings; a bad or empty value falls back to the default."""
    from backend.accounts.settings import get_install_setting
    mode = str(get_install_setting(db, "update_check_mode") or "").strip().lower()
    repo = str(get_install_setting(db, "update_check_repo") or "").strip()
    return (mode if mode in MODES else DEFAULT_MODE), (repo if REPO_RE.match(repo) else DEFAULT_REPO)


async def update_status(mode: str, repo: str, force: bool = False, client: Optional[httpx.AsyncClient] = None) -> dict:
    """The check for (mode, repo), from the cache while it is fresh.

    `force` skips the cache, but never more than once each FORCE_SECONDS."""
    commit = read_local_commit()
    if mode == "off":
        return _result("off", repo, commit, message="Update check is off.")
    key = (mode, repo, commit)
    async with _lock:
        now = time.monotonic()
        fresh = _cache["key"] == key and now < _cache["expires"]
        recent = _cache["key"] == key and now - _cache["fetched"] < FORCE_SECONDS
        if _cache["result"] is not None and (recent or (fresh and not force)):
            return _cache["result"]
        try:
            if client is None:
                async with httpx.AsyncClient(timeout=TIMEOUT, headers=_HEADERS) as own:
                    result = await (check_commit if mode == "commit" else check_release)(own, repo, commit)
            else:
                result = await (check_commit if mode == "commit" else check_release)(client, repo, commit)
            ttl = CACHE_SECONDS
        except (httpx.HTTPError, ValueError) as error:
            logger.warning("Update check (%s, %s) failed: %s", mode, repo, error)
            result = _result(mode, repo, commit, update_available=None,
                             error=str(error) or error.__class__.__name__,
                             message="The update check could not reach GitHub.")
            ttl = ERROR_SECONDS
        _cache.update(key=key, result=result, expires=now + ttl, fetched=now)
        return result

