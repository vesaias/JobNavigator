"""Update check: a newer GitHub release, or new commits on main, against this install.

GitHub is replaced by httpx.MockTransport; nothing here leaves the machine."""
import httpx
import pytest

from backend import update_check as U
from backend.models.db import Account
from backend.seed import invalid_setting_values
from backend.tests.r4_support import ACT_AS, client, set_setting  # noqa: F401 (fixture)
from backend.version import APP_VERSION

OLD = "a" * 40
NEW = "b" * 40
REPO = "vesaias/JobNavigator"


@pytest.fixture(autouse=True)
def _fresh_cache():
    U._cache.update(key=None, result=None, expires=0.0, fetched=0.0)
    yield
    U._cache.update(key=None, result=None, expires=0.0, fetched=0.0)


def _github(routes, calls=None):
    """A client whose transport answers `routes` {path: (status, json)}; other paths are 404."""
    def handler(request):
        if calls is not None:
            calls.append(request.url.path)
        status, body = routes.get(request.url.path, (404, {"message": "Not Found"}))
        return httpx.Response(status, json=body)
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _bump(v):
    major, minor, *_ = U.version_tuple(v)
    return f"{major}.{minor + 1}"


# ── the running commit ──────────────────────────────────────────────────────

def test_commit_from_a_loose_branch_ref(tmp_path):
    (tmp_path / "refs/heads").mkdir(parents=True)
    (tmp_path / "HEAD").write_text("ref: refs/heads/main\n")
    (tmp_path / "refs/heads/main").write_text(OLD + "\n")
    assert U.read_local_commit(tmp_path) == OLD


def test_commit_from_packed_refs(tmp_path):
    (tmp_path / "HEAD").write_text("ref: refs/heads/main\n")
    (tmp_path / "packed-refs").write_text(f"# pack-refs with: peeled\n{NEW} refs/heads/other\n{OLD} refs/heads/main\n")
    assert U.read_local_commit(tmp_path) == OLD


def test_commit_from_a_detached_head(tmp_path):
    (tmp_path / "HEAD").write_text(NEW + "\n")
    assert U.read_local_commit(tmp_path) == NEW


def test_commit_from_a_worktree(tmp_path):
    common = tmp_path / "repo/.git"
    wt = common / "worktrees/w1"
    wt.mkdir(parents=True)
    (common / "refs/heads").mkdir(parents=True)
    (common / "refs/heads/feature").write_text(OLD)
    (wt / "HEAD").write_text("ref: refs/heads/feature")
    (wt / "commondir").write_text("../..")
    checkout = tmp_path / "w1"
    checkout.mkdir()
    (checkout / ".git").write_text(f"gitdir: {wt}")
    assert U.read_local_commit(checkout / ".git") == OLD


@pytest.mark.parametrize("head", [None, "", "ref: refs/heads/missing", "not a sha"])
def test_unknown_commit_is_none(tmp_path, head):
    if head is not None:
        (tmp_path / "HEAD").write_text(head)
    assert U.read_local_commit(tmp_path) is None
    assert U.read_local_commit(tmp_path / "absent") is None


def test_version_tuple():
    assert U.version_tuple("v3.1") == (3, 1, 0)
    assert U.version_tuple("3.1.2") == (3, 1, 2)
    assert U.version_tuple("v3.10") > U.version_tuple("3.9")
    assert U.version_tuple("") == (0, 0, 0)


# ── release mode ────────────────────────────────────────────────────────────

async def test_newer_release_is_reported():
    newer = _bump(APP_VERSION)
    routes = {f"/repos/{REPO}/releases/latest": (200, {"tag_name": f"v{newer}", "html_url": "https://x/rel"})}
    async with _github(routes) as c:
        r = await U.check_release(c, REPO, None)
    assert r["update_available"] is True
    assert r["latest"]["version"] == newer
    assert r["url"] == "https://x/rel"


async def test_same_or_older_release_is_not_an_update():
    for tag in (f"v{APP_VERSION}", "v1.0.0"):
        async with _github({f"/repos/{REPO}/releases/latest": (200, {"tag_name": tag})}) as c:
            assert (await U.check_release(c, REPO, None))["update_available"] is False


async def test_repository_without_releases():
    async with _github({}) as c:
        r = await U.check_release(c, REPO, None)
    assert r["update_available"] is False
    assert "no published release" in r["message"]


# ── commit mode ─────────────────────────────────────────────────────────────

HEAD_ROUTE = {f"/repos/{REPO}/commits/main": (200, {"sha": NEW, "html_url": "https://x/c", "commit": {"committer": {"date": "2026-11-06T14:44:13Z"}}})}


async def test_running_the_head_is_not_an_update():
    async with _github(HEAD_ROUTE) as c:
        r = await U.check_commit(c, REPO, NEW)
    assert r["update_available"] is False
    assert r["latest"]["commit"] == NEW


@pytest.mark.parametrize("status", ["ahead", "diverged"])
async def test_new_commits_on_main_are_counted(status):
    routes = {**HEAD_ROUTE, f"/repos/{REPO}/compare/{OLD}...{NEW}": (200, {"status": status, "ahead_by": 5, "behind_by": 1, "html_url": "https://x/cmp"})}
    async with _github(routes) as c:
        r = await U.check_commit(c, REPO, OLD)
    assert (r["update_available"], r["behind_by"], r["url"]) == (True, 5, "https://x/cmp")


async def test_running_code_newer_than_main_is_not_an_update():
    routes = {**HEAD_ROUTE, f"/repos/{REPO}/compare/{OLD}...{NEW}": (200, {"status": "behind", "ahead_by": 0, "behind_by": 3})}
    async with _github(routes) as c:
        assert (await U.check_commit(c, REPO, OLD))["update_available"] is False


async def test_commit_unknown_upstream_or_locally_is_undecided():
    async with _github(HEAD_ROUTE) as c:
        assert (await U.check_commit(c, REPO, OLD))["update_available"] is None   # compare 404
        r = await U.check_commit(c, REPO, None)
    assert r["update_available"] is None
    assert ".git" in r["message"]


# ── cache and failures ──────────────────────────────────────────────────────

async def test_off_sends_nothing(monkeypatch):
    calls = []
    async with _github({}, calls) as c:
        r = await U.update_status("off", REPO, client=c)
    assert r["mode"] == "off" and calls == []


async def test_result_is_cached_and_force_is_rate_limited(monkeypatch):
    monkeypatch.setattr(U, "read_local_commit", lambda: None)
    calls = []
    routes = {f"/repos/{REPO}/releases/latest": (200, {"tag_name": "v1.0"})}
    async with _github(routes, calls) as c:
        await U.update_status("release", REPO, client=c)
        await U.update_status("release", REPO, client=c)
        await U.update_status("release", REPO, force=True, client=c)   # within FORCE_SECONDS
        assert len(calls) == 1
        U._cache["fetched"] -= U.FORCE_SECONDS + 1
        await U.update_status("release", REPO, force=True, client=c)
        assert len(calls) == 2
        await U.update_status("commit", REPO, client=c)                # another key, another request
        assert len(calls) == 3


async def test_github_failure_is_a_result_not_an_exception(monkeypatch):
    monkeypatch.setattr(U, "read_local_commit", lambda: None)
    async with _github({f"/repos/{REPO}/releases/latest": (403, {"message": "rate limit"})}) as c:
        r = await U.update_status("release", REPO, client=c)
    assert r["update_available"] is None
    assert r["error"]
    assert U._cache["expires"] - U._cache["fetched"] == U.ERROR_SECONDS


# ── settings and the endpoint ───────────────────────────────────────────────

def test_setting_values_are_validated():
    assert invalid_setting_values({"update_check_mode": "commit", "update_check_repo": "volkotyk/JobNavigator"}) == []
    assert invalid_setting_values({"update_check_repo": ""}) == []
    assert len(invalid_setting_values({"update_check_mode": "nightly"})) == 1
    for bad in ("https://github.com/a/b", "a/b/c", "a b/c", "../x"):
        assert len(invalid_setting_values({"update_check_repo": bad})) == 1, bad


def test_settings_fall_back_to_defaults(test_db):
    assert U.settings_of(test_db) == (U.DEFAULT_MODE, U.DEFAULT_REPO)
    set_setting(test_db, "update_check_mode", "commit")
    set_setting(test_db, "update_check_repo", "volkotyk/JobNavigator")
    assert U.settings_of(test_db) == ("commit", "volkotyk/JobNavigator")


def test_endpoint_reads_the_settings_and_only_the_owner_forces(client, test_db, monkeypatch):
    seen = []

    async def fake(mode, repo, force=False):
        seen.append((mode, repo, force))
        return {"mode": mode, "update_available": False}
    monkeypatch.setattr(U, "update_status", fake)
    set_setting(test_db, "update_check_mode", "off")
    r = client.get("/api/updates", params={"force": "true"})
    assert r.status_code == 200 and r.json()["owner"] is True
    assert seen == [("off", U.DEFAULT_REPO, True)]

    member = Account(name="Partner", role="member")
    test_db.add(member)
    test_db.commit()
    client.headers[ACT_AS] = str(member.id)
    assert client.get("/api/updates", params={"force": "true"}).status_code == 403
    r = client.get("/api/updates")
    assert r.status_code == 200 and r.json()["owner"] is False
