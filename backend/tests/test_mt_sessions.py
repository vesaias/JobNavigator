"""MT-16 · Per-account scraper sessions and the Claude Code no-fallback rule.

The owner keeps today's exact paths; a member gets `<LI_ACCOUNTS_ROOT>/<id>/…`. Everything
runs against tmp dirs and fakes: no browser, no login.
"""
import asyncio
import json
import os

import pytest

from backend.accounts import credentials as C
from backend.accounts.context import use_account
from backend.models.db import Account, SectionPolicy, Setting
from backend.tests.r4_support import set_setting

pytestmark = pytest.mark.asyncio


@pytest.fixture
def accounts(test_db):
    a = test_db.query(Account).filter(Account.role == "owner").one()
    b = Account(name="Partner", role="member")
    test_db.add(b)
    test_db.commit()
    return a.id, b.id


@pytest.fixture
def roots(tmp_path, monkeypatch):
    """Point every session path at tmp, owner paths included."""
    monkeypatch.setattr(C, "LI_ACCOUNTS_ROOT", str(tmp_path / "li" / "accounts"))
    monkeypatch.setattr(C, "LI_EXTENSION_OWNER", str(tmp_path / "li" / "li_cookies.json"))
    monkeypatch.setattr(C, "LI_PERSONAL_OWNER", str(tmp_path / "tmp" / "linkedin_cookies.json"))
    monkeypatch.setattr(C, "LI_PIN_OWNER", str(tmp_path / "tmp" / "li_pin.txt"))
    monkeypatch.setattr(C, "CODEX_ACCOUNTS_ROOT", str(tmp_path / "codex" / "accounts"))
    monkeypatch.setattr(C, "AGY_ACCOUNTS_ROOT", str(tmp_path / "gemini" / "accounts"))
    monkeypatch.setattr(C, "CLAUDE_ACCOUNTS_ROOT", str(tmp_path / "claude" / "accounts"))
    return tmp_path


# ── path rules ───────────────────────────────────────────────────────────────

async def test_owner_paths_are_todays_exact_paths():
    assert C.LI_EXTENSION_OWNER == "/root/.linkedin_api/li_cookies.json"
    # 3.2: the main session persists next to the mock one (/tmp was wiped on every rebuild)
    assert C.LI_PERSONAL_OWNER == "/root/.linkedin_api/linkedin_cookies.json"
    assert C.LI_PIN_OWNER == "/tmp/li_pin.txt"


async def test_the_owners_main_jar_moves_out_of_tmp(tmp_path, monkeypatch):
    old, new = tmp_path / "tmp" / "linkedin_cookies.json", tmp_path / "li" / "linkedin_cookies.json"
    old.parent.mkdir()
    old.write_text('[{"name": "li_at"}]')
    monkeypatch.setattr(C, "LI_PERSONAL_LEGACY", str(old))
    monkeypatch.setattr(C, "LI_PERSONAL_OWNER", str(new))
    assert C.linkedin_personal_cookies() == str(new)
    assert new.read_text() == '[{"name": "li_at"}]' and not old.exists()


async def test_owner_no_context_and_unscoped_resolve_to_the_owner_paths(test_db, accounts):
    a, b = accounts
    from backend.accounts.context import unscoped
    for ctx in (use_account(a), unscoped()):
        with ctx:
            assert C.linkedin_extension_cookies(test_db) == C.LI_EXTENSION_OWNER
            assert C.linkedin_personal_cookies(test_db) == C.LI_PERSONAL_OWNER
            assert C.linkedin_pin_file(test_db) == C.LI_PIN_OWNER
    assert C.linkedin_extension_cookies(test_db) == C.LI_EXTENSION_OWNER   # no context at all


async def test_member_paths_are_per_account(test_db, accounts, roots):
    a, b = accounts
    d = roots / "li" / "accounts" / str(b)
    with use_account(b):
        assert C.linkedin_extension_cookies(test_db) == str(d / "li_cookies.json")
        assert C.linkedin_personal_cookies(test_db) == str(d / "linkedin_cookies.json")
        assert C.linkedin_pin_file(test_db) == str(roots / "tmp" / f"li_pin_{b}.txt")
    with use_account(a):
        assert C.linkedin_extension_cookies(test_db) == str(roots / "li" / "li_cookies.json")


async def test_two_members_never_share_a_path(test_db, accounts, roots):
    a, b = accounts
    c = Account(name="Third", role="member")
    test_db.add(c)
    test_db.commit()
    seen = set()
    for acc in (a, b, c.id):
        with use_account(acc):
            seen |= {C.linkedin_extension_cookies(test_db), C.linkedin_personal_cookies(test_db),
                     C.linkedin_pin_file(test_db)}
    assert len(seen) == 9


async def test_a_member_path_follows_the_linkedin_policy_not_the_models_one(test_db, accounts, roots):
    # QA F5 (R5-01): 'inherit' LinkedIn = the owner's session paths
    a, b = accounts
    test_db.add(SectionPolicy(account_id=b, section="models", mode="inherit"))
    test_db.commit()
    with use_account(b):
        assert str(b) in C.linkedin_extension_cookies(test_db)       # linkedin 'own' (default)
    test_db.add(SectionPolicy(account_id=b, section="linkedin", mode="inherit"))
    test_db.commit()
    with use_account(b):
        assert C.linkedin_extension_cookies(test_db) == C.LI_EXTENSION_OWNER


# ── LinkedIn Personal + extension import ─────────────────────────────────────

class _Ctx:
    def __init__(self, cookies):
        self._cookies = cookies
        self.added = None

    async def cookies(self):
        return self._cookies

    async def add_cookies(self, c):
        self.added = c

    async def add_init_script(self, s):
        pass

    async def new_page(self):
        return object()


async def test_personal_scraper_saves_and_loads_the_accounts_own_jar(test_db, accounts, roots, monkeypatch):
    from backend.scraper.sources import linkedin_personal as lp
    a, b = accounts
    with use_account(a):
        await lp._save_cookies(_Ctx([{"name": "li_at", "value": "owner"}]))
    with use_account(b):
        await lp._save_cookies(_Ctx([{"name": "li_at", "value": "member"}]))
    owner_file = roots / "tmp" / "linkedin_cookies.json"
    member_file = roots / "li" / "accounts" / str(b) / "linkedin_cookies.json"
    assert json.loads(owner_file.read_text())[0]["value"] == "owner"
    assert json.loads(member_file.read_text())[0]["value"] == "member"

    ctx = _Ctx([])

    class _Browser:
        async def new_context(self, **k):
            return ctx

    class _PW:
        class chromium:
            @staticmethod
            async def launch(**k):
                return _Browser()

    class _Starter:
        async def start(self):
            return _PW()

    import playwright.async_api as pa
    monkeypatch.setattr(pa, "async_playwright", lambda: _Starter())
    with use_account(b):
        await lp._get_linkedin_browser()
    assert ctx.added[0]["value"] == "member"
    with use_account(a):
        await lp._get_linkedin_browser()
    assert ctx.added[0]["value"] == "owner"


async def test_extension_import_reads_the_accounts_own_session(test_db, accounts, roots):
    from backend.scraper.sources import linkedin_extension as ext
    a, b = accounts
    # the import reads the mock session of an account that has a mock account set (Task 8)
    from backend.accounts.context import unscoped
    with unscoped():   # the owner reads the install row, the member (LinkedIn 'own') its own
        test_db.add_all([Setting(key="linkedin_mock_email", value="mock@x.io", account_id=None),
                         Setting(key="linkedin_mock_email", value="mock@x.io", account_id=b)])
        test_db.commit()
    (roots / "li").mkdir(parents=True)
    (roots / "li" / "li_cookies.json").write_text(json.dumps([{"name": "li_at", "value": "owner"}]))
    with use_account(a):
        assert ext._load_session_cookies()[0]["value"] == "owner"
    with use_account(b):
        assert ext._load_session_cookies() is None          # no session of its own yet
    d = roots / "li" / "accounts" / str(b)
    d.mkdir(parents=True)
    (d / "li_cookies.json").write_text(json.dumps([{"name": "li_at", "value": "member"}]))
    with use_account(b):
        assert ext._load_session_cookies()[0]["value"] == "member"
    with use_account(a):
        assert ext._load_session_cookies()[0]["value"] == "owner"


# ── refresh_linkedin_session ─────────────────────────────────────────────────

class _Page:
    url = "https://www.linkedin.com/feed/"

    async def goto(self, *a, **k):
        pass


class _RCtx:
    async def cookies(self):
        return [{"name": "li_at", "value": "fresh", "domain": ".linkedin.com"},
                {"name": "x", "value": "1", "domain": ".other.com"}]

    async def clear_cookies(self):
        pass


class _Browser2:
    async def close(self):
        pass


class _PW2:
    async def stop(self):
        pass


@pytest.fixture
def fake_browser(monkeypatch):
    from backend.scraper.sources import linkedin_personal as lp

    async def fake_get():
        return _PW2(), _Browser2(), _RCtx(), _Page()

    async def me(page):
        return 200

    monkeypatch.setattr(lp, "_get_linkedin_browser", fake_get)
    monkeypatch.setattr(lp, "_voyager_me_status", me)


async def test_refresh_writes_the_current_accounts_jar_only(test_db, accounts, roots, fake_browser):
    from backend import refresh_linkedin_session as rls
    a, b = accounts
    with use_account(b):
        assert await rls._login_and_save("e", "p") == 0
    member_jar = roots / "li" / "accounts" / str(b) / "li_cookies.json"
    assert [c["name"] for c in json.loads(member_jar.read_text())] == ["li_at"]   # non-linkedin cookie dropped
    assert not (roots / "li" / "li_cookies.json").exists()
    with use_account(a):
        assert await rls._login_and_save("e", "p") == 0
    assert (roots / "li" / "li_cookies.json").exists()


async def test_refresh_state_and_pin_drop_are_per_account(test_db, accounts, roots):
    from backend import refresh_linkedin_session as rls
    a, b = accounts
    rls.STATES["mock"].update(phase="idle", detail="")
    rls._MEMBER_STATES.clear()
    with use_account(b):
        rls._phase("awaiting_pin", "mail")
        assert rls.state()["phase"] == "awaiting_pin"
        assert rls.pin_file() == str(roots / "tmp" / f"li_pin_{b}.txt")
    assert rls.STATES["mock"]["phase"] == "idle"
    with use_account(a):
        assert rls.state() is rls.STATES["mock"]
        assert rls.pin_file() == str(roots / "tmp" / "li_pin.txt")


async def test_a_mock_jar_saved_before_the_split_asks_for_a_new_sign_in(test_db, accounts, roots):
    """A mock jar without the sign-in record (saved before 3.2) cannot be used by the employer-link
    lookup; the Mock session row says so instead of looking signed in."""
    from backend.api import routes_linkedin as rl
    from backend import refresh_linkedin_session as rls
    a, _ = accounts
    (roots / "li").mkdir(parents=True)
    (roots / "li" / "li_cookies.json").write_text("[]")
    with use_account(a):
        from backend.models.db import Setting
        test_db.add(Setting(key="linkedin_mock_email", value="mock@example.com"))
        test_db.commit()
        st = rl.session_status("mock")
        assert st["status"] == "stale" and "sign in again" in st["summary"].lower()
        rls.record_sign_in(rls.MOCK, "mock@example.com")
        assert rl.session_status("mock")["status"] == "ok"
        # the mock email changed after the sign-in: the lookup will not use it
        rls.record_sign_in(rls.MOCK, "old@example.com")
        st = rl.session_status("mock")
        assert st["status"] == "stale" and "another email" in st["summary"]


async def test_session_routes_follow_the_callers_account(test_db, accounts, roots):
    from backend.api import routes_linkedin as rl
    from backend import refresh_linkedin_session as rls
    a, b = accounts
    rls._MEMBER_STATES.clear()
    (roots / "li").mkdir(parents=True)
    (roots / "li" / "li_cookies.json").write_text("[]")
    with use_account(a):
        assert rl.session_status()["exists"] is True
    with use_account(b):
        assert rl.session_status()["exists"] is False
        os.makedirs(roots / "tmp", exist_ok=True)
        assert rl.session_pin(rl.PinIn(pin="12 34 56")) == {"ok": True}
    assert (roots / "tmp" / f"li_pin_{b}.txt").read_text() == "123456"
    assert not (roots / "tmp" / "li_pin.txt").exists()


# ── Jobright / Levels ────────────────────────────────────────────────────────

async def test_jobright_session_is_a_setting_in_a_section_a_member_owns(test_db, accounts):
    from backend.accounts.settings import SETTING_SECTIONS, section_of
    assert section_of("jobright_session_id") == "jobright"
    assert SETTING_SECTIONS["jobright"]["default"] == "own"


# ── removal / export ─────────────────────────────────────────────────────────

async def test_removal_deletes_the_member_session_dir_only(test_db, accounts, roots):
    from backend.accounts.admin import delete_account_rows, account_dirs
    a, b = accounts
    other = Account(name="Third", role="member")
    test_db.add(other)
    test_db.commit()
    assert str(roots / "li" / "accounts" / str(b)) in account_dirs(b)
    for acc in (b, other.id):
        d = roots / "li" / "accounts" / str(acc)
        d.mkdir(parents=True)
        (d / "li_cookies.json").write_text("[]")
    (roots / "li" / "li_cookies.json").write_text("[]")
    counts = delete_account_rows(test_db, b)
    assert counts["dirs"] == 1
    assert not (roots / "li" / "accounts" / str(b)).exists()
    assert (roots / "li" / "accounts" / str(other.id) / "li_cookies.json").exists()
    assert (roots / "li" / "li_cookies.json").exists()      # the owner's jar is never touched


async def test_export_leaves_the_session_files_out(test_db, accounts, roots):
    import zipfile
    from backend.accounts.admin import build_export
    a, b = accounts
    d = roots / "li" / "accounts" / str(b)
    d.mkdir(parents=True)
    (d / "li_cookies.json").write_text('[{"name": "li_at", "value": "SECRETCOOKIE"}]')
    with zipfile.ZipFile(build_export(test_db, b, a)) as zf:
        blob = b"".join(zf.read(n) for n in zf.namelist())
    assert b"SECRETCOOKIE" not in blob


# ── Claude Code: a member on its own models never falls back to the owner ───

def _own(db, account_id, key, value):
    db.add(Setting(key=key, value=value, account_id=account_id))
    db.commit()


def _capture_cli(monkeypatch):
    from backend.tests.test_mt_credentials import _capture_run_cli
    return _capture_run_cli(monkeypatch)


async def test_member_on_own_models_without_a_token_fails_not_logged_in(test_db, accounts, monkeypatch):
    from backend.analyzer import llm_client as L
    a, b = accounts
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "env-owner-token")
    set_setting(test_db, "claude_code_oauth_token", "install-token")
    test_db.add(SectionPolicy(account_id=b, section="models", mode="own"))
    test_db.commit()
    calls = _capture_cli(monkeypatch)
    with use_account(b):
        with pytest.raises(L.NonRetryableLLMError) as e:
            await L._call_claude_code("p", "s", "", 100)
    assert "not logged in" in str(e.value) and "Settings › Models" in str(e.value)
    assert calls == []                                       # the CLI never ran
    # a blank own value is no token either
    _own(test_db, b, "claude_code_oauth_token", "   ")
    with use_account(b):
        with pytest.raises(L.NonRetryableLLMError):
            await L._call_claude_code("p", "s", "", 100)
    # the owner is unaffected
    with use_account(a):
        await L._call_claude_code("p", "s", "", 100)
    assert calls[0]["env"]["CLAUDE_CODE_OAUTH_TOKEN"] == "install-token"


async def test_member_on_inherit_still_uses_the_owner_token(test_db, accounts, monkeypatch):
    from backend.analyzer import llm_client as L
    a, b = accounts
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "env-owner-token")
    calls = _capture_cli(monkeypatch)
    with use_account(b):
        await L._call_claude_code("p", "s", "", 100)
    assert calls[0]["env"]["CLAUDE_CODE_OAUTH_TOKEN"] == "env-owner-token"
