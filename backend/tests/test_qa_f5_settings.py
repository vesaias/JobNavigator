"""QA F5 · 'own' never falls back to the owner; owner values hidden from members.

R3-01 / R6-02 / T3-06: a member section on 'own' with no row of its own reads the seeded
default, never the owner's install value (credentials, sessions, excludes).
R3-02: a member on its own Models section uses only its own API keys (no owner key, no
`.env` key), and the model catalog never resolves the owner's key for it.
R5-01: LinkedIn session files follow the linkedin section policy; R5-02: per-account
LinkedIn import progress. R3-03: proxy credentials and owner personal values masked for
members. R3-04: startup migrations reach members' own rows. R3-05: default_resume_id
validated. R3-06: the settings PK swap looks the constraint name up. T7-11: copied
LinkedIn / Jobright searches of a member with nothing set fail clearly.
"""
import json
import os

import pytest
from fastapi import HTTPException

from backend.accounts import credentials as C
from backend.accounts import settings as S
from backend.accounts.context import owner_unlocked, use_account
from backend.api import routes_settings as R
from backend.models.db import Account, Resume, SectionPolicy, Setting
from backend.tests.r4_support import client, set_setting  # noqa: F401 (fixture)


@pytest.fixture
def accounts(test_db):
    a = test_db.query(Account).filter(Account.role == "owner").one()
    b = Account(name="Partner", role="member")
    test_db.add(b)
    test_db.commit()
    return a.id, b.id


@pytest.fixture
def roots(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "LI_ACCOUNTS_ROOT", str(tmp_path / "li" / "accounts"))
    monkeypatch.setattr(C, "LI_EXTENSION_OWNER", str(tmp_path / "li" / "li_cookies.json"))
    monkeypatch.setattr(C, "LI_PERSONAL_OWNER", str(tmp_path / "tmp" / "linkedin_cookies.json"))
    monkeypatch.setattr(C, "LI_PIN_OWNER", str(tmp_path / "tmp" / "li_pin.txt"))
    return tmp_path


def _own(db, account_id, key, value):
    db.add(Setting(key=key, value=value, account_id=account_id))
    db.commit()


def _policy(db, account_id, section, mode):
    row = db.query(SectionPolicy).filter_by(account_id=account_id, section=section).first()
    if row is None:
        db.add(SectionPolicy(account_id=account_id, section=section, mode=mode))
    else:
        row.mode = mode
    db.commit()


OWNER_CREDS = {
    "linkedin_email": "owner@li.example", "linkedin_password": "li-pass",
    "linkedin_mock_email": "mock@li.example", "linkedin_mock_password": "mock-pass",
    "jobright_email": "owner@jr.example", "jobright_password": "jr-pass",
    "jobright_session_id": "owner-session", "jobright_session_obtained_at": "2026-10-01T00:00:00+00:00",
}


@pytest.fixture
def owner_creds(test_db, accounts):
    for k, v in OWNER_CREDS.items():
        set_setting(test_db, k, v)
    return accounts


# ── R3-01 / T3-06: the resolve rule ──────────────────────────────────────────

def test_member_own_with_no_rows_never_reads_the_owner_credentials(test_db, owner_creds):
    a, b = owner_creds
    with use_account(b):
        for key in OWNER_CREDS:
            value, source = S.resolve_setting(test_db, key)
            assert value in ("", None), key
            assert source in ("default", None), key
        assert S.get_setting(test_db, "linkedin_email") == ""
        assert S.get_setting(test_db, "jobright_session_id", "") == ""
    with use_account(a):
        assert S.get_setting(test_db, "linkedin_email") == "owner@li.example"


def test_member_own_reads_its_row_and_inherit_reads_the_owner(test_db, owner_creds):
    a, b = owner_creds
    _own(test_db, b, "jobright_email", "me@jr.example")
    with use_account(b):
        assert S.resolve_setting(test_db, "jobright_email") == ("me@jr.example", "account")
    _policy(test_db, b, "jobright", "inherit")
    with use_account(b):
        assert S.resolve_setting(test_db, "jobright_email") == ("owner@jr.example", "install")
        assert S.get_setting(test_db, "jobright_session_id") == "owner-session"


def test_new_member_excludes_start_from_the_seeded_defaults(test_db, accounts):
    """T3-06: the owner's personal exclude lists are not the member's until copied."""
    from backend.models.db import get_global_title_exclude
    a, b = accounts
    set_setting(test_db, "title_exclude_global", '["intern", "sales"]')
    set_setting(test_db, "body_exclusion_phrases", '["no sponsorship"]')
    with use_account(b):
        assert get_global_title_exclude(test_db) == []
        assert S.resolve_setting(test_db, "body_exclusion_phrases") == ("[]", "default")
    with use_account(a):
        assert get_global_title_exclude(test_db) == ["intern", "sales"]


def test_copy_from_excludes_still_copies_the_owner_lists(test_db, accounts):
    from backend.accounts.admin import copy_from
    a, b = accounts
    set_setting(test_db, "title_exclude_global", '["intern"]')
    copy_from(test_db, a, b, ["excludes"], a)
    test_db.commit()
    with use_account(b):
        assert S.resolve_setting(test_db, "title_exclude_global") == ('["intern"]', "account")


def test_copy_from_a_member_on_own_without_rows_copies_the_defaults(test_db, accounts):
    """_effective_value follows the same rule: a member source with no own row gives the
    seeded default, not the owner's list."""
    from backend.accounts.admin import copy_from
    a, b = accounts
    c = Account(name="Third", role="member")
    test_db.add(c)
    test_db.commit()
    set_setting(test_db, "title_exclude_global", '["owner-only"]')
    copy_from(test_db, b, c.id, ["excludes"], a)
    test_db.commit()
    with use_account(c.id):
        assert S.get_setting(test_db, "title_exclude_global") == "[]"


def test_effective_rows_matches_resolve_setting_for_a_member(test_db, owner_creds):
    a, b = owner_creds
    _own(test_db, b, "linkedin_email", "me@li.example")
    _policy(test_db, b, "models", "own")
    set_setting(test_db, "anthropic_api_key", "sk-owner")
    for k, v in (("title_exclude_global", '["x"]'), ("scoring_rubric", "r"), ("telegram_chat_id", "1")):
        set_setting(test_db, k, v)    # every seeded key has an install row in a real DB
    with use_account(b):
        rows = {k: (v, src) for k, v, src in S.effective_rows(test_db)}
        for key in ("linkedin_email", "linkedin_password", "jobright_email", "anthropic_api_key",
                    "title_exclude_global", "scoring_rubric", "telegram_chat_id"):
            assert rows[key] == S.resolve_setting(test_db, key), key
    assert rows["anthropic_api_key"] == ("", "default")


# ── R3-01 / R6-02 / R3-03: what a member's GET /api/settings shows ───────────

def test_member_get_never_shows_owner_addresses_or_secrets(test_db, owner_creds):
    a, b = owner_creds
    with use_account(b):
        body = R.get_settings(meta=False, db=test_db)
    meta = body.pop("_meta")
    blob = json.dumps(body)
    for v in ("owner@li.example", "mock@li.example", "owner@jr.example", "owner-session"):
        assert v not in blob
    assert body["linkedin_email"] == "" and meta["linkedin_email"]["source"] == "default"
    assert body["jobright_password"] == "" and "set_by_owner" not in meta["jobright_password"]


def test_member_on_inherit_sees_set_by_owner_placeholders(test_db, owner_creds):
    a, b = owner_creds
    _policy(test_db, b, "linkedin", "inherit")
    _policy(test_db, b, "jobright", "inherit")
    with use_account(b):
        body = R.get_settings(meta=False, db=test_db)
    meta = body.pop("_meta")
    assert "owner@li.example" not in json.dumps(body)
    for key in ("linkedin_email", "linkedin_mock_email", "jobright_email"):
        assert body[key] == "", key
        assert meta[key]["set_by_owner"] is True and meta[key]["source"] == "install"
    for key in ("linkedin_password", "jobright_password", "jobright_session_id"):
        assert body[key] == "•" * 6
        assert meta[key]["set_by_owner"] is True


def test_owner_unset_values_carry_no_set_by_owner_flag(test_db, accounts):
    a, b = accounts
    set_setting(test_db, "linkedin_email", "")
    _policy(test_db, b, "linkedin", "inherit")
    with use_account(b):
        body = R.get_settings(meta=False, db=test_db)
    assert body["linkedin_email"] == ""
    assert "set_by_owner" not in body["_meta"]["linkedin_email"]


@pytest.mark.parametrize("raw,shown", [
    ("http://user:pa55@proxy.example:8080", "http://••••@proxy.example:8080"),
    ("socks5://u@10.0.0.1:1080/x", "socks5://••••@10.0.0.1:1080/x"),
    ("socks5://127.0.0.1:9050", "socks5://127.0.0.1:9050"),
    ("", ""),
    ("user:pass@host:1", "••••@host:1"),
])
def test_mask_url_credentials(raw, shown):
    assert R.mask_url_credentials(raw) == shown


def test_proxy_url_credentials_masked_for_members_only(client, test_db, accounts):
    a, b = accounts
    set_setting(test_db, "proxy_url", "http://alice:s3cret@proxy.example:3128")
    with use_account(b):
        body = R.get_settings(meta=False, db=test_db)
    assert body["proxy_url"] == "http://••••@proxy.example:3128"
    assert "s3cret" not in json.dumps(body)
    # the owner's own response is untouched
    assert client.get("/api/settings").json()["proxy_url"] == "http://alice:s3cret@proxy.example:3128"


def test_owner_response_has_no_set_by_owner_flags(client, test_db, owner_creds):
    body = client.get("/api/settings").json()
    assert "_meta" not in body
    assert body["linkedin_email"] == "owner@li.example"
    meta = client.get("/api/settings?meta=1").json()["_meta"]
    assert not any("set_by_owner" in m for m in meta.values())


# ── R3-02: API keys on own Models ────────────────────────────────────────────

@pytest.fixture
def owner_key(test_db, accounts, monkeypatch):
    set_setting(test_db, "llm_provider", "claude_api")
    set_setting(test_db, "anthropic_api_key", "sk-owner")
    set_setting(test_db, "llm_fallback_provider", "")
    set_setting(test_db, "llm_fallback_model", "")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-env-owner")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env-openai")
    return accounts


def test_member_own_models_without_a_key_resolves_empty(test_db, owner_key):
    from backend.analyzer.llm_client import resolve_llm_config
    a, b = owner_key
    _policy(test_db, b, "models", "own")
    _own(test_db, b, "llm_provider", "openrouter")
    with use_account(b):
        for f in ("", "scoring", "cv_tailor", "cover_letter", "autofill", "email"):
            assert resolve_llm_config(f, db=test_db)["api_key"] == "", f
    with use_account(a):
        assert resolve_llm_config("", db=test_db)["api_key"] == "sk-owner"


@pytest.mark.asyncio
@pytest.mark.parametrize("provider,label", [("claude_api", "Claude API"), ("openai", "OpenAI"),
                                            ("openrouter", "OpenRouter"), ("opencode_go", "OpenCode Go"),
                                            ("cheaper_inference", "Cheaper Inference")])
async def test_member_own_models_call_fails_clearly_without_a_key(test_db, owner_key, monkeypatch, provider, label):
    from backend.analyzer import llm_client as L
    a, b = owner_key
    _policy(test_db, b, "models", "own")
    _own(test_db, b, "llm_provider", provider)
    sent = []

    async def no_network(*args, **kwargs):
        sent.append(args)
        return {"text": "x", "usage": {}}

    monkeypatch.setattr(L, "_call_claude_api", no_network)
    monkeypatch.setattr(L, "_call_openai", no_network)
    with use_account(b):
        with pytest.raises(L.NonRetryableLLMError) as e:
            await L.call_llm("p", "s", 10)
    assert str(e.value) == f"No API key for {label} — set it in Settings › Models"
    assert sent == []


@pytest.mark.asyncio
async def test_member_own_streaming_autofill_fails_clearly_without_a_key(test_db, owner_key, monkeypatch):
    from backend.analyzer import llm_client as L
    a, b = owner_key
    _policy(test_db, b, "models", "own")

    async def boom(*a, **k):
        raise AssertionError("must not stream with the env key")
        yield  # pragma: no cover

    monkeypatch.setattr(L, "_stream_claude", boom)
    with use_account(b):
        with pytest.raises(L.NonRetryableLLMError):
            async for _ in L.call_autofill_llm_stream("p", "s"):
                pass


@pytest.mark.asyncio
async def test_owner_and_inherit_keep_the_env_key_fallback(test_db, owner_key, monkeypatch):
    from backend.analyzer import llm_client as L
    a, b = owner_key
    seen = []

    async def fake(prompt, system, model, api_key, max_tokens, cached_prefix=None, effort=""):
        seen.append(api_key)
        return {"text": "ok", "usage": {}}

    monkeypatch.setattr(L, "_call_claude_api", fake)
    set_setting(test_db, "anthropic_api_key", "")
    with use_account(a):
        await L.call_llm("p", "s", 10)
    with use_account(b):                          # inherit: the owner's (empty) key, env fallback allowed
        await L.call_llm("p", "s", 10)
    assert seen == ["", ""]
    L._require_own_key("claude_api", "")          # no context: allowed


@pytest.mark.asyncio
async def test_member_own_models_with_its_key_dispatches_it(test_db, owner_key, monkeypatch):
    from backend.analyzer import llm_client as L
    a, b = owner_key
    _policy(test_db, b, "models", "own")
    _own(test_db, b, "llm_provider", "claude_api")
    _own(test_db, b, "anthropic_api_key", "sk-member")
    seen = []

    async def fake(prompt, system, model, api_key, max_tokens, cached_prefix=None, effort=""):
        seen.append(api_key)
        return {"text": "ok", "usage": {}}

    monkeypatch.setattr(L, "_call_claude_api", fake)
    with use_account(b):
        await L.call_llm("p", "s", 10)
    assert seen == ["sk-member"]


@pytest.mark.asyncio
async def test_opencode_go_env_key_reaches_owner_and_inherit_never_a_member_on_own(test_db, owner_key, monkeypatch):
    """#25: OPENCODE_API_KEY is the owner's. Owner and 'inherit' fall back to it; a member on its
    own Models uses only its own Go key (call and streaming autofill), else a clear error."""
    from backend.analyzer import llm_client as L
    from backend.api import routes_llm as rl
    a, b = owner_key
    monkeypatch.setenv("OPENCODE_API_KEY", "sk-env-go")
    set_setting(test_db, "llm_provider", "opencode_go")
    set_setting(test_db, "llm_model", "glm-5.3")
    set_setting(test_db, "opencode_api_key", "")
    set_setting(test_db, "autofill_llm_provider", "")
    seen = []

    async def fake_call(prompt, system, model, api_key, max_tokens, base_url=None, extra_body=None, effort=""):
        seen.append((api_key, base_url))
        return {"text": "ok", "usage": {}}

    async def fake_stream(prompt, system, model, api_key, max_tokens, base_url=None, effort="", feature=""):
        seen.append((api_key, base_url))
        yield "ok"

    monkeypatch.setattr(L, "_call_openai", fake_call)
    monkeypatch.setattr(L, "_stream_openai", fake_stream)
    with use_account(a):
        await L.call_llm("p", "s", 10)
        assert [c async for c in L.call_autofill_llm_stream("p", "s")] == ["ok"]
    with use_account(b):                          # inherit: the owner's config, env included
        await L.call_llm("p", "s", 10)
    assert seen == [("sk-env-go", L.OPENCODE_GO_BASE_URL)] * 3

    seen.clear()
    _policy(test_db, b, "models", "own")
    _own(test_db, b, "llm_provider", "opencode_go")
    with use_account(b):
        with pytest.raises(L.NonRetryableLLMError, match="No API key for OpenCode Go"):
            await L.call_llm("p", "s", 10)
        with pytest.raises(L.NonRetryableLLMError, match="No API key for OpenCode Go"):
            async for _ in L.call_autofill_llm_stream("p", "s"):
                pass
        assert L._opencode_go_key("") == ""       # never the env key
        assert rl._resolve_key(test_db, "opencode_go") == ""     # catalog: public list, no owner key
    with use_account(a):
        assert rl._resolve_key(test_db, "opencode_go") == "sk-env-go"
    assert seen == []

    _own(test_db, b, "opencode_api_key", "sk-member-go")
    with use_account(b):
        await L.call_llm("p", "s", 10)
    assert seen == [("sk-member-go", L.OPENCODE_GO_BASE_URL)]


def test_model_catalog_never_uses_the_owner_key_for_a_member_on_own(test_db, owner_key):
    from backend.api import routes_llm as rl
    a, b = owner_key
    with use_account(b):                          # inherit: owner's key
        assert rl._resolve_key(test_db, "claude_api") == "sk-owner"
    _policy(test_db, b, "models", "own")
    with use_account(b):
        assert rl._resolve_key(test_db, "claude_api") == ""          # not sk-owner, not the env
        assert rl._resolve_key(test_db, "openai") == ""
    _own(test_db, b, "llm_provider", "openai")
    _own(test_db, b, "openai_api_key", "sk-member-oa")
    with use_account(b):
        assert rl._resolve_key(test_db, "openai") == "sk-member-oa"
    with use_account(a):
        assert rl._resolve_key(test_db, "claude_api") == "sk-owner"
        assert rl._resolve_key(test_db, "openai") == "sk-env-openai"   # owner keeps the env


@pytest.mark.asyncio
async def test_model_catalog_route_400s_for_a_member_without_a_key(test_db, owner_key, monkeypatch):
    from backend.api import routes_llm as rl
    a, b = owner_key
    _policy(test_db, b, "models", "own")

    async def boom(key):
        raise AssertionError("no fetch with anyone's key")

    monkeypatch.setattr(rl, "_fetch_anthropic", boom)
    with use_account(b):
        with pytest.raises(HTTPException) as e:
            await rl.list_models(provider="claude_api")
    assert e.value.status_code == 400


# ── R5-01: LinkedIn session paths follow the section policy ─────────────────

def test_linkedin_inherit_uses_the_owner_paths(test_db, accounts, roots):
    a, b = accounts
    with use_account(b):                          # default own: the member's dir
        assert C.linkedin_extension_cookies(test_db).startswith(str(roots / "li" / "accounts" / str(b)))
        assert C.linkedin_shared_from_owner(test_db) is False
    _policy(test_db, b, "linkedin", "inherit")
    with use_account(b):
        assert C.linkedin_extension_cookies(test_db) == C.LI_EXTENSION_OWNER
        assert C.linkedin_personal_cookies(test_db) == C.LI_PERSONAL_OWNER
        assert C.linkedin_pin_file(test_db) == C.LI_PIN_OWNER
        assert C.linkedin_extension_cookies() == C.LI_EXTENSION_OWNER    # own session too
        assert C.linkedin_shared_from_owner(test_db) is True
    with use_account(a):
        assert C.linkedin_shared_from_owner(test_db) is False


def test_linkedin_inherit_refresh_state_and_creds_are_the_owners(test_db, owner_creds, roots):
    from backend import refresh_linkedin_session as rls
    a, b = owner_creds
    rls.STATES["main"].update(phase="idle", detail="")
    rls._MEMBER_STATES.clear()
    with use_account(b):                          # own, nothing set: empty creds
        email, password, missing = rls._creds(rls.MAIN)
        assert (email, password) == ("", "")
    _policy(test_db, b, "linkedin", "inherit")
    with use_account(b):
        assert rls.state(rls.MAIN) is rls.STATES["main"]
        assert rls._creds(rls.MAIN)[:2] == ("owner@li.example", "li-pass")


@pytest.mark.asyncio
async def test_linkedin_inherit_refresh_and_pin_are_owner_only(test_db, accounts, roots, monkeypatch):
    from backend.api import routes_linkedin as rl
    a, b = accounts
    _policy(test_db, b, "linkedin", "inherit")
    (roots / "li").mkdir(parents=True)
    (roots / "li" / "li_cookies.json").write_text("[]")
    started = []
    monkeypatch.setattr(rl, "launch_background", lambda *a, **k: started.append(a) or "run-1")
    with use_account(b):
        st = rl.session_status()
        assert st["shared"] is True and st["exists"] is True
        assert st["summary"].startswith("The owner's session")
        with pytest.raises(HTTPException) as e:
            await rl.session_refresh()
        assert e.value.status_code == 403
        with pytest.raises(HTTPException) as e:
            rl.session_pin(rl.PinIn(pin="123456"))
        assert e.value.status_code == 403
        with owner_unlocked(True):
            assert (await rl.session_refresh())["status"] == "running"
    assert len(started) == 1
    with use_account(a):
        assert rl.session_status()["shared"] is False


# ── T7-11: copied LinkedIn / Jobright searches with nothing set ──────────────

@pytest.mark.asyncio
async def test_member_linkedin_personal_search_without_creds_fails_clearly(test_db, owner_creds, roots, monkeypatch):
    from backend.scraper.sources import linkedin_personal as lp
    from backend.models.db import Search
    a, b = owner_creds

    async def no_browser():
        raise AssertionError("no browser for an account that is not set up")

    monkeypatch.setattr(lp, "_get_linkedin_browser", no_browser)
    with use_account(b):
        s = Search(name="LI copy", search_mode="linkedin_personal", sources=["recommended"])
        test_db.add(s)
        test_db.commit()
        out = await lp.run(s)
        assert out["error"] == lp.NOT_SET_UP
        prev = await lp.preview(s, test_db)
        assert prev["error"] == lp.NOT_SET_UP


@pytest.mark.asyncio
async def test_member_jobright_without_creds_fails_clearly(test_db, owner_creds, monkeypatch):
    from backend.scraper.sources import jobright as jr
    a, b = owner_creds

    async def no_login(email, password):
        raise AssertionError(f"logged in as {email}")

    monkeypatch.setattr(jr, "_login", no_login)
    with use_account(b):
        with pytest.raises(RuntimeError) as e:
            await jr._ensure_session()
    assert "not set up for this account" in str(e.value)
    assert "Settings › Jobright.ai" in str(e.value)
    # nothing was written for the owner or the member
    rows = test_db.query(Setting).filter(Setting.key == "jobright_session_id").all()
    assert [(r.account_id, r.value) for r in rows] == [(None, "owner-session")]


# ── R5-02: per-account LinkedIn import progress ─────────────────────────────

def test_import_progress_is_per_account(test_db, accounts):
    from backend.scraper.sources.linkedin_extension import _linkedin_import_progress as P
    a, b = accounts
    P.reset_all()
    try:
        with use_account(a):
            P.update({"status": "running", "total": 300, "processed": 0})
        with use_account(b):
            P.clear()
            P.update({"status": "running", "total": 5, "processed": 0})
            P["processed"] = P["processed"] + 1
            P["status"] = "done"
        with use_account(a):
            assert dict(P) == {"status": "running", "total": 300, "processed": 0}
        with use_account(b):
            assert dict(P) == {"status": "done", "total": 5, "processed": 1}
    finally:
        P.reset_all()


@pytest.mark.asyncio
async def test_rejected_duplicate_import_keeps_the_running_progress(test_db, accounts, monkeypatch):
    from backend.api import routes_jobs as rj
    from backend.job_monitor import JobAlreadyRunningError
    from backend.scraper.sources.linkedin_extension import _linkedin_import_progress as P
    a, b = accounts

    class _Req:
        async def json(self):
            return {"linkedin_ids": ["1", "2"]}

    def dup(*args, **kwargs):
        raise JobAlreadyRunningError("linkedin_import", 3.0)

    monkeypatch.setattr(rj, "launch_background", dup)
    P.reset_all()
    try:
        with use_account(b):
            P.update({"status": "running", "total": 9, "processed": 4})
            with pytest.raises(HTTPException) as e:
                await rj.linkedin_import(_Req(), db=test_db)
            assert e.value.status_code == 409
            assert dict(P) == {"status": "running", "total": 9, "processed": 4}
        monkeypatch.setattr(rj, "launch_background", lambda *a, **k: "run-2")
        with use_account(b):
            await rj.linkedin_import(_Req(), db=test_db)
            assert dict(P) == {}                      # reset for the accepted import
        with use_account(a):
            assert rj.linkedin_import_progress() == {"status": "idle"}
    finally:
        P.reset_all()


# ── R3-04: startup migrations reach members' own rows ────────────────────────

def test_migrate_autofill_dicts_updates_member_rows(test_db, accounts):
    from backend.accounts.context import unscoped
    from backend.seed import DEFAULT_SETTINGS, migrate_autofill_dicts
    a, b = accounts
    defaults = json.loads(DEFAULT_SETTINGS["autofill_field_patterns"][0])
    some = sorted(defaults)[0]
    _own(test_db, b, "autofill_field_patterns", json.dumps({"custom_key": ["x"]}))
    with unscoped():
        migrate_autofill_dicts(test_db)
    row = test_db.query(Setting).filter_by(key="autofill_field_patterns", account_id=b).one()
    merged = json.loads(row.value)
    assert merged["custom_key"] == ["x"] and some in merged


def test_migrate_llm_settings_updates_member_rows(test_db, accounts):
    from backend.accounts.context import unscoped
    from backend.seed import DEFAULT_SETTINGS, migrate_llm_settings, install_row
    a, b = accounts
    default_list = json.loads(DEFAULT_SETTINGS["llm_models_list"][0])
    mkey = lambda m: f'{m.get("provider")}|{m.get("model")}'   # noqa: E731
    new_default, old_default = default_list[0], default_list[1]
    # the install has offered every default but the first; the member removed old_default
    seen = install_row(test_db, "llm_seeded_models")
    if seen is None:
        test_db.add(Setting(key="llm_seeded_models", value="[]"))
        test_db.commit()
        seen = install_row(test_db, "llm_seeded_models")
    seen.value = json.dumps(sorted(mkey(d) for d in default_list[1:]))
    set_setting(test_db, "llm_models_list", json.dumps(default_list[1:]))
    member_list = [m for m in default_list[2:]] + [{"provider": "openai_compat", "model": "x"}]
    _own(test_db, b, "llm_models_list", json.dumps(member_list))
    _own(test_db, b, "llm_provider", "openai_compat")
    _own(test_db, b, "llm_model", "claude-haiku-4-5-20251001")
    with unscoped():
        migrate_llm_settings(test_db)
    got = {r.key: r.value for r in test_db.query(Setting).filter(Setting.account_id == b)}
    keys = {mkey(m) for m in json.loads(got["llm_models_list"])}
    assert mkey(new_default) in keys                   # the release's new default arrives
    assert mkey(old_default) not in keys               # a default the member removed stays removed
    assert "openai_compat|x" not in keys
    assert got["llm_provider"] == "openai"
    assert got["llm_model"] == "claude-haiku-4-5"
    install_keys = {mkey(m) for m in json.loads(install_row(test_db, "llm_models_list").value)}
    assert mkey(new_default) in install_keys and mkey(old_default) in install_keys


def test_migrate_cv_terminology_updates_member_rows(test_db, accounts):
    from backend.accounts.context import unscoped
    from backend.seed import migrate_cv_terminology
    a, b = accounts
    _own(test_db, b, "scoring_rubric", "Score each CV against CVs")
    with unscoped():
        migrate_cv_terminology(test_db)
    row = test_db.query(Setting).filter_by(key="scoring_rubric", account_id=b).one()
    assert row.value == "Score each Resume against Resumes"


# ── R3-05: default_resume_id ─────────────────────────────────────────────────

def _base(db, account_id, name):
    with use_account(account_id):
        r = Resume(name=name, is_base=True, json_data={"summary": "x"})
        db.add(r)
        db.commit()
        return str(r.id)


@pytest.mark.parametrize("bad", ["not-a-uuid", "12345", "00000000-0000-0000-0000-000000000000"])
def test_default_resume_id_garbage_is_422(test_db, accounts, bad):
    a, b = accounts
    for who in (a, b):
        with use_account(who):
            with pytest.raises(HTTPException) as e:
                R.update_settings({"default_resume_id": bad}, db=test_db)
            assert e.value.status_code == 422
    assert test_db.query(Setting).filter(Setting.key == "default_resume_id",
                                         Setting.value == bad).count() == 0


def test_default_resume_id_of_another_account_is_422(test_db, accounts):
    a, b = accounts
    owner_resume = _base(test_db, a, "Owner base")
    mine = _base(test_db, b, "Member base")
    with use_account(b):
        with pytest.raises(HTTPException) as e:
            R.update_settings({"default_resume_id": owner_resume}, db=test_db)
        assert e.value.status_code == 422
        for ok in (mine, "persona", ""):
            assert R.update_settings({"default_resume_id": ok}, db=test_db)["updated"] == ["default_resume_id"]
    with use_account(a):
        assert R.update_settings({"default_resume_id": owner_resume}, db=test_db)["updated"] == ["default_resume_id"]


def test_default_resume_id_over_http(client, test_db, accounts):
    a, b = accounts
    rid = _base(test_db, a, "Owner base")
    assert client.patch("/api/settings", json={"default_resume_id": "nope"}).status_code == 422
    assert client.patch("/api/settings", json={"default_resume_id": rid}).status_code == 200


def test_scoring_ignores_an_invalid_stored_default(test_db, accounts):
    from backend.analyzer.cv_scorer import _get_default_resume
    a, b = accounts
    set_setting(test_db, "default_resume_id", "not-a-uuid")
    with use_account(a):
        assert _get_default_resume(test_db) == {}
    rid = _base(test_db, a, "Owner base")
    set_setting(test_db, "default_resume_id", f" {rid} ")
    with use_account(a):
        assert list(_get_default_resume(test_db)) == ["Owner base"]


# ── R3-06: the settings PK swap ──────────────────────────────────────────────

def test_pk_swap_looks_up_the_constraint_name():
    from backend.seed import SETTINGS_SCOPING_STATEMENTS
    block = [s for s in SETTINGS_SCOPING_STATEMENTS if "DO $$" in s][0]
    assert "c.conname INTO pk_name" in block
    assert "format('ALTER TABLE settings DROP CONSTRAINT %I', pk_name)" in block
    assert "DROP CONSTRAINT settings_pkey" not in block
