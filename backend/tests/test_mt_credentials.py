"""MT-15 · Per-account credentials: API keys and subscription-CLI logins.

A is the owner (its values are the install values), B a member. Every LLM entry point
must dispatch with B's own provider/model/key when B's models section is 'own', and with
the owner's when it is 'inherit' (the default). The three CLIs get per-account logins:
Claude Code a token setting, Codex a CODEX_HOME, Antigravity a HOME (its state dir).
No subprocess runs: `_run_cli` / `create_subprocess_exec` are fakes that record the env.
"""
import json
import os

import pytest

from backend.accounts import credentials as C
from backend.accounts.context import use_account
from backend.analyzer import llm_client as L
from backend.cli_runner import runtime as R, paths as runner_paths
from backend.models.db import Account, SectionPolicy, Setting
from backend.tests.r4_support import client, set_setting  # noqa: F401 (fixture)

FEATURES = ("scoring", "cv_tailor", "cover_letter", "autofill", "email")


@pytest.fixture
def accounts(test_db):
    a = test_db.query(Account).filter(Account.role == "owner").one()
    b = Account(name="Partner", role="member")
    test_db.add(b)
    test_db.commit()
    return a.id, b.id


def _own(db, account_id, key, value):
    row = db.query(Setting).filter(Setting.key == key, Setting.account_id == account_id).first()
    if row is None:
        db.add(Setting(key=key, value=value, account_id=account_id))
    else:
        row.value = value
    db.commit()


def _models_own(db, account_id):
    db.add(SectionPolicy(account_id=account_id, section="models", mode="own"))
    db.commit()


@pytest.fixture
def two_configs(test_db, accounts):
    """Owner: claude_api / owner-model / sk-owner (+ an OpenRouter fallback). B: openai /
    member-model / sk-member (+ an OpenAI fallback, so the same key), stored as B's rows but only
    read once B owns 'models'. Keys are per provider (3.1)."""
    a, b = accounts
    for k, v in {"llm_provider": "claude_api", "llm_model": "owner-model", "anthropic_api_key": "sk-owner",
                 "llm_fallback_provider": "openrouter", "llm_fallback_model": "owner-fb",
                 "openrouter_api_key": "or-owner"}.items():
        set_setting(test_db, k, v)
    for k, v in {"llm_provider": "openai", "llm_model": "member-model", "openai_api_key": "sk-member",
                 "llm_fallback_provider": "openai", "llm_fallback_model": "member-fb"}.items():
        _own(test_db, b, k, v)
    return a, b


OWNER = ("claude_api", "owner-model", "sk-owner")
MEMBER = ("openai", "member-model", "sk-member")


def _capture_dispatch(monkeypatch, fail_primary=False):
    calls = []

    async def fake_dispatch(provider, model, api_key, prompt, system, max_tokens, cached_prefix=None, effort=""):
        calls.append((provider, model, api_key))
        if fail_primary and len(calls) == 1:
            raise L.NonRetryableLLMError("primary down")
        return {"text": "ok", "usage": {}}

    monkeypatch.setattr(L, "_dispatch", fake_dispatch)
    return calls


async def _every_entry_point():
    """The six dispatching entry points, in order: scoring (call_llm), tailoring, letters,
    autofill, email, and the résumé PDF / generic path (call_llm with no override)."""
    await L.call_llm("p", "s", 10, **{k: v for k, v in zip(
        ("provider", "model", "api_key"), _scoring_pair())})
    await L.call_cv_tailor_llm("p", "s")
    await L.call_cover_letter_llm("p", "s")
    await L.call_autofill_llm("p", "s")
    await L.call_email_llm("p", "s")
    await L.call_llm("p", "s", 10)


def _scoring_pair():
    cfg = L.resolve_llm_config("scoring")
    return cfg["provider"], cfg["model"], cfg["api_key"]


# ── API keys: every entry point ──────────────────────────────────────────────

def test_resolve_llm_config_every_feature_inherit_then_own(test_db, two_configs):
    a, b = two_configs
    with use_account(b):
        for f in ("",) + FEATURES:
            cfg = L.resolve_llm_config(f, db=test_db)
            assert (cfg["provider"], cfg["model"], cfg["api_key"]) == OWNER, f
    _models_own(test_db, b)
    with use_account(b):
        for f in ("",) + FEATURES:
            cfg = L.resolve_llm_config(f, db=test_db)
            assert (cfg["provider"], cfg["model"], cfg["api_key"]) == MEMBER, f
    with use_account(a):
        for f in ("",) + FEATURES:
            cfg = L.resolve_llm_config(f, db=test_db)
            assert (cfg["provider"], cfg["model"], cfg["api_key"]) == OWNER, f


@pytest.mark.asyncio
async def test_every_entry_point_dispatches_with_the_member_own_key(test_db, two_configs, monkeypatch):
    a, b = two_configs
    _models_own(test_db, b)
    calls = _capture_dispatch(monkeypatch)
    with use_account(b):
        await _every_entry_point()
    assert calls == [MEMBER] * 6


@pytest.mark.asyncio
async def test_every_entry_point_dispatches_with_the_owner_key_on_inherit(test_db, two_configs, monkeypatch):
    a, b = two_configs
    calls = _capture_dispatch(monkeypatch)
    with use_account(b):
        await _every_entry_point()
    assert calls == [OWNER] * 6


@pytest.mark.asyncio
async def test_owner_entry_points_unchanged_by_a_member_own_config(test_db, two_configs, monkeypatch):
    a, b = two_configs
    _models_own(test_db, b)
    calls = _capture_dispatch(monkeypatch)
    with use_account(a):
        await _every_entry_point()
    assert calls == [OWNER] * 6


@pytest.mark.asyncio
@pytest.mark.parametrize("own,expected", [
    (True, ("openai", "member-fb", "sk-member")),
    (False, ("openrouter", "owner-fb", "or-owner")),
])
async def test_fallback_follows_the_member_policy(test_db, two_configs, monkeypatch, own, expected):
    a, b = two_configs
    if own:
        _models_own(test_db, b)
    calls = _capture_dispatch(monkeypatch, fail_primary=True)
    with use_account(b):
        res = await L.call_llm("p", "s", 10)
    assert calls[1] == expected
    assert (res["provider"], res["model"]) == expected[:2]


@pytest.mark.asyncio
@pytest.mark.parametrize("own", [True, False])
async def test_streaming_autofill_uses_the_member_policy(test_db, two_configs, monkeypatch, own):
    a, b = two_configs
    set_setting(test_db, "llm_provider", "claude_api")
    _own(test_db, b, "autofill_llm_provider", "claude_api")   # stream natively in both cases
    _own(test_db, b, "autofill_llm_model", "member-claude")   # its own model: not the OpenAI Primary's (L-05)
    _own(test_db, b, "anthropic_api_key", "sk-member-autofill")
    if own:
        _models_own(test_db, b)
    seen = []

    async def fake_stream(prompt, system, model, api_key, max_tokens, cached_prefix, effort=""):
        seen.append((model, api_key))
        yield "hi"

    monkeypatch.setattr(L, "_stream_claude", fake_stream)
    with use_account(b):
        out = [c async for c in L.call_autofill_llm_stream("p", "s")]
    assert out == ["hi"]
    assert seen == [("member-claude", "sk-member-autofill") if own else ("owner-model", "sk-owner")]


def test_streaming_route_over_http_runs_as_the_member(client, test_db, two_configs, monkeypatch):
    """The SSE body runs after the middleware returned: the account context must still be B's."""
    a, b = two_configs
    _models_own(test_db, b)
    _own(test_db, b, "llm_provider", "claude_api")
    _own(test_db, b, "anthropic_api_key", "sk-member-ant")   # its key for the provider it now uses
    set_setting(test_db, "autofill_prompt", "Answer {question} for {company} as {persona}")
    seen = []

    async def fake_stream(prompt, system, model, api_key, max_tokens, cached_prefix, effort=""):
        seen.append((model, api_key))
        yield "drafted"

    monkeypatch.setattr(L, "_stream_claude", fake_stream)
    client.headers["X-Test-Act-As"] = str(b)
    r = client.post("/api/autofill/answer/stream", json={"question": "Why us?", "company": "Acme"})
    assert r.status_code == 200, r.text
    assert "drafted" in r.text
    assert seen == [("member-model", "sk-member-ant")]


# ── Claude Code: token per account ───────────────────────────────────────────

def _capture_run_cli(monkeypatch, handler=None):
    calls = []

    async def fake_run_cli(cmd, stdin, env=None, timeout=None, cwd=None):
        calls.append({"cmd": list(cmd), "env": dict(env or {}), "cwd": cwd})
        if handler:
            return handler(cmd)
        return 0, json.dumps({"result": "ok", "is_error": False, "subtype": "success"}).encode(), b""

    monkeypatch.setattr(R, "_run_cli", fake_run_cli)

    async def in_process(provider, prompt, system, model, max_tokens, **kwargs):
        return await R.execute(provider, prompt, system, model, max_tokens, **kwargs)

    monkeypatch.setattr(L.runner_client, "complete", in_process)
    return calls


@pytest.mark.asyncio
async def test_claude_code_owner_without_a_setting_keeps_the_env_token(test_db, accounts, monkeypatch):
    a, b = accounts
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "env-owner-token")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-must-not-pass")
    calls = _capture_run_cli(monkeypatch)
    with use_account(a):
        await L._call_claude_code("p", "s", "claude-sonnet-5", 100)
    assert calls[0]["env"]["CLAUDE_CODE_OAUTH_TOKEN"] == "env-owner-token"
    assert "ANTHROPIC_API_KEY" not in calls[0]["env"]


@pytest.mark.asyncio
async def test_claude_code_owner_setting_beats_the_env(test_db, accounts, monkeypatch):
    a, b = accounts
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "env-owner-token")
    set_setting(test_db, "claude_code_oauth_token", "  install-token  ")
    calls = _capture_run_cli(monkeypatch)
    with use_account(a):
        await L._call_claude_code("p", "s", "", 100)
    assert calls[0]["env"]["CLAUDE_CODE_OAUTH_TOKEN"] == "install-token"


@pytest.mark.asyncio
async def test_claude_code_member_inherit_uses_the_owner_token(test_db, accounts, monkeypatch):
    a, b = accounts
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "env-owner-token")
    _own(test_db, b, "claude_code_oauth_token", "member-token")   # ignored while inheriting
    calls = _capture_run_cli(monkeypatch)
    with use_account(b):
        await L._call_claude_code("p", "s", "", 100)
    assert calls[0]["env"]["CLAUDE_CODE_OAUTH_TOKEN"] == "env-owner-token"
    set_setting(test_db, "claude_code_oauth_token", "install-token")
    with use_account(b):
        await L._call_claude_code("p", "s", "", 100)
    assert calls[1]["env"]["CLAUDE_CODE_OAUTH_TOKEN"] == "install-token"


@pytest.mark.asyncio
async def test_claude_code_member_own_uses_its_token(test_db, accounts, cli_roots, monkeypatch):
    a, b = accounts
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "env-owner-token")
    set_setting(test_db, "claude_code_oauth_token", "install-token")
    _models_own(test_db, b)
    _own(test_db, b, "claude_code_oauth_token", "member-token")
    calls = _capture_run_cli(monkeypatch)
    with use_account(b):
        await L._call_claude_code("p", "s", "", 100)
    with use_account(a):
        await L._call_claude_code("p", "s", "", 100)
    assert calls[0]["env"]["CLAUDE_CODE_OAUTH_TOKEN"] == "member-token"
    assert calls[1]["env"]["CLAUDE_CODE_OAUTH_TOKEN"] == "install-token"


def test_claude_code_token_is_a_redacted_models_secret(client, test_db, accounts):
    from backend.accounts.settings import section_of
    from backend.seed import DEFAULT_SETTINGS
    assert section_of("claude_code_oauth_token") == "models"
    assert "claude_code_oauth_token" in DEFAULT_SETTINGS
    set_setting(test_db, "claude_code_oauth_token", "sk-ant-oat-secret")
    body = client.get("/api/settings").json()
    assert body["claude_code_oauth_token"] == "•" * 6
    # the mask PATCHed back never overwrites the stored token
    assert client.patch("/api/settings", json={"claude_code_oauth_token": "•" * 6}).status_code == 200
    test_db.expire_all()
    row = test_db.query(Setting).filter(Setting.key == "claude_code_oauth_token",
                                        Setting.account_id.is_(None)).one()
    assert row.value == "sk-ant-oat-secret"


def test_new_account_settings_copy_never_carries_the_token(test_db, accounts):
    from backend.accounts.admin import _is_personal
    assert _is_personal("claude_code_oauth_token")


# ── Codex: CODEX_HOME per account ────────────────────────────────────────────

@pytest.fixture
def cli_roots(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "CODEX_ACCOUNTS_ROOT", str(tmp_path / "codex" / "accounts"))
    monkeypatch.setattr(C, "AGY_ACCOUNTS_ROOT", str(tmp_path / "gemini" / "accounts"))
    monkeypatch.setattr(C, "CLAUDE_ACCOUNTS_ROOT", str(tmp_path / "claude" / "accounts"))
    monkeypatch.setattr(C, "LI_ACCOUNTS_ROOT", str(tmp_path / "li" / "accounts"))
    for name in ("CODEX_ACCOUNTS_ROOT", "AGY_ACCOUNTS_ROOT", "CLAUDE_ACCOUNTS_ROOT"):
        monkeypatch.setattr(runner_paths, name, getattr(C, name))
    return tmp_path


def _codex_handler(login_rc=0):
    def handler(cmd):
        if cmd[:3] == ["codex", "login", "status"]:
            return login_rc, b"", b""
        events = [{"type": "item.completed", "item": {"type": "agent_message", "text": "ok"}}]
        return 0, ("\n".join(json.dumps(e) for e in events) + "\n").encode(), b""
    return handler


@pytest.mark.asyncio
async def test_codex_member_own_gets_its_own_home_for_status_and_exec(test_db, accounts, cli_roots, monkeypatch):
    a, b = accounts
    _models_own(test_db, b)
    monkeypatch.delenv("CODEX_HOME", raising=False)
    calls = _capture_run_cli(monkeypatch, _codex_handler())
    with use_account(b):
        res = await L._call_codex_cli("p", "s", "", 10)
    home = str(cli_roots / "codex" / "accounts" / str(b))
    assert res["text"] == "ok"
    assert [c["cmd"][:2] for c in calls] == [["codex", "login"], ["codex", "exec"]]
    assert all(c["env"]["CODEX_HOME"] == home for c in calls)
    assert os.path.isdir(home)


@pytest.mark.asyncio
@pytest.mark.parametrize("who", ["owner", "inherit"])
async def test_codex_owner_and_inherit_keep_the_default_home(test_db, accounts, cli_roots, monkeypatch, who):
    a, b = accounts
    monkeypatch.delenv("CODEX_HOME", raising=False)
    calls = _capture_run_cli(monkeypatch, _codex_handler())
    with use_account(a if who == "owner" else b):
        await L._call_codex_cli("p", "s", "", 10)
    assert all("CODEX_HOME" not in c["env"] for c in calls)
    assert not (cli_roots / "codex").exists()


@pytest.mark.asyncio
async def test_codex_member_not_logged_in_names_its_own_login_command(test_db, accounts, cli_roots, monkeypatch):
    a, b = accounts
    _models_own(test_db, b)
    calls = _capture_run_cli(monkeypatch, _codex_handler(login_rc=1))
    with use_account(b):
        with pytest.raises(L.NonRetryableLLMError) as e:
            await L._call_codex_cli("p", "s", "", 10)
    home = str(cli_roots / "codex" / "accounts" / str(b))
    assert f"-e CODEX_HOME={home} codex-runner codex login --device-auth" in str(e.value)
    assert len(calls) == 1


# ── Antigravity: HOME (state dir) per account ────────────────────────────────

def _agy_setup(tmp_path, monkeypatch):
    source = tmp_path / "shipped.json"
    source.write_text(json.dumps({"permissions": {"deny": ["command(*)", "read_file(/)"]}}))
    monkeypatch.setattr(R, "_AGY_SETTINGS_SOURCE", str(source))
    default_state = tmp_path / "default-home" / ".gemini" / "antigravity-cli"
    monkeypatch.setattr(R, "_AGY_STATE", str(default_state))
    asserted = []
    monkeypatch.setattr(R, "_agy_assert_denied", lambda path, rules: asserted.append(rules))

    def handler(cmd):
        out = [{"event": "init", "conversation_id": "c-9"},
               {"event": "result", "result": {"conversation_id": "c-9", "status": "SUCCESS", "response": "ok"}}]
        return 0, ("\n".join(json.dumps(e) for e in out) + "\n").encode(), b""
    return default_state, asserted, handler


def _transcript(state):
    (state / "conversations").mkdir(parents=True, exist_ok=True)
    (state / "conversations" / "c-9.db").write_text("resume text")
    return state / "conversations" / "c-9.db"


@pytest.mark.asyncio
async def test_agy_member_own_runs_with_its_own_home_and_state_dir(test_db, accounts, cli_roots, monkeypatch):
    a, b = accounts
    _models_own(test_db, b)
    default_state, asserted, handler = _agy_setup(cli_roots, monkeypatch)
    calls = _capture_run_cli(monkeypatch, handler)
    member_state = cli_roots / "gemini" / "accounts" / str(b) / ".gemini" / "antigravity-cli"
    stale = _transcript(member_state)
    with use_account(b):
        res = await L._call_antigravity_cli("p", "s", "", 10)
    assert res["text"] == "ok"
    assert calls[0]["env"]["HOME"] == str(cli_roots / "gemini" / "accounts" / str(b))
    # deny list installed in the member's state dir, checked against agy's log
    assert json.loads((member_state / "settings.json").read_text())["permissions"]["deny"] == ["command(*)", "read_file(/)"]
    assert asserted == [["command(*)", "read_file(/)"]]
    assert not (default_state / "settings.json").exists()
    # the transcript is cleared from the member's dir
    assert not stale.exists()
    # the override does not leak past the call
    assert R._agy_state() == str(default_state)


@pytest.mark.asyncio
@pytest.mark.parametrize("who", ["owner", "inherit"])
async def test_agy_owner_and_inherit_keep_home_and_the_default_state(test_db, accounts, cli_roots, monkeypatch, who):
    a, b = accounts
    default_state, asserted, handler = _agy_setup(cli_roots, monkeypatch)
    monkeypatch.setenv("HOME", "/root-ish")
    calls = _capture_run_cli(monkeypatch, handler)
    stale = _transcript(default_state)
    with use_account(a if who == "owner" else b):
        await L._call_antigravity_cli("p", "s", "", 10)
    assert calls[0]["env"]["HOME"] == "/root-ish"
    assert (default_state / "settings.json").exists()
    assert asserted and not stale.exists()
    assert not (cli_roots / "gemini").exists()


@pytest.mark.asyncio
async def test_agy_member_not_logged_in_names_its_own_home(test_db, accounts, cli_roots, monkeypatch):
    a, b = accounts
    _models_own(test_db, b)
    _default, _asserted, _h = _agy_setup(cli_roots, monkeypatch)

    def handler(cmd):
        out = [{"event": "result", "result": {"status": "ERROR", "error": "You are not logged into Antigravity."}}]
        return 1, ("\n".join(json.dumps(e) for e in out) + "\n").encode(), b""
    _capture_run_cli(monkeypatch, handler)
    with use_account(b):
        with pytest.raises(L.NonRetryableLLMError) as e:
            await L._call_antigravity_cli("p", "s", "", 10)
    assert f"-e HOME={cli_roots / 'gemini' / 'accounts' / str(b)} antigravity-runner agy" in str(e.value)


# ── Removal deletes the CLI homes ────────────────────────────────────────────

def test_account_dirs_lists_the_cli_homes_and_the_session_dir(cli_roots, accounts):
    from backend.accounts.admin import account_dirs
    a, b = accounts
    assert account_dirs(b) == [str(cli_roots / "codex" / "accounts" / str(b)),
                               str(cli_roots / "gemini" / "accounts" / str(b)),
                               str(cli_roots / "claude" / "accounts" / str(b)),
                               str(cli_roots / "li" / "accounts" / str(b))]


def test_removing_an_account_deletes_its_cli_homes_only(test_db, accounts, cli_roots):
    from backend.accounts.admin import delete_account_rows
    a, b = accounts
    other = Account(name="Third", role="member")
    test_db.add(other)
    test_db.commit()
    for acc in (b, other.id):
        (cli_roots / "codex" / "accounts" / str(acc)).mkdir(parents=True)
        (cli_roots / "codex" / "accounts" / str(acc) / "auth.json").write_text("{}")
        (cli_roots / "gemini" / "accounts" / str(acc) / ".gemini").mkdir(parents=True)
    counts = delete_account_rows(test_db, b)
    assert counts["dirs"] == 2
    assert not (cli_roots / "codex" / "accounts" / str(b)).exists()
    assert not (cli_roots / "gemini" / "accounts" / str(b)).exists()
    assert (cli_roots / "codex" / "accounts" / str(other.id) / "auth.json").exists()
    assert (cli_roots / "gemini" / "accounts" / str(other.id)).exists()


def test_export_leaves_cli_homes_out(test_db, accounts, cli_roots):
    import zipfile
    from backend.accounts.admin import build_export
    a, b = accounts
    home = cli_roots / "codex" / "accounts" / str(b)
    home.mkdir(parents=True)
    (home / "auth.json").write_text('{"tokens": "secret"}')
    buf = build_export(test_db, b, a)
    with zipfile.ZipFile(buf) as zf:
        names = zf.namelist()
        assert not any("auth" in n or "codex" in n for n in names)
        assert "secret" not in zf.read("settings.json").decode()


# ── backend/scripts/cli_login.py ─────────────────────────────────────────────

def test_cli_login_prints_the_per_account_commands(test_db, accounts, cli_roots, capsys):
    from backend.scripts import cli_login
    a, b = accounts
    _models_own(test_db, b)
    assert cli_login.main(["codex", "partner"]) == 0
    home = cli_roots / "codex" / "accounts" / str(b)
    out = capsys.readouterr().out.splitlines()
    assert out[0] == f"docker compose run --rm -it -e CODEX_HOME={home} codex-runner codex login --device-auth"
    assert home.is_dir()
    assert cli_login.main(["agy", str(b)]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == f"docker compose run --rm -it -e HOME={cli_roots / 'gemini' / 'accounts' / str(b)} antigravity-runner agy"
    assert cli_login.main(["claude", "Partner"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("docker compose run --rm -it claude-runner claude setup-token")
    assert "Claude Code token" in out


def test_cli_login_owner_uses_the_default_homes_and_warns_inherit(test_db, accounts, cli_roots, capsys):
    from backend.scripts import cli_login
    a, b = accounts
    owner_name = test_db.query(Account).filter(Account.id == a).one().name
    assert cli_login.main(["codex_cli", owner_name]) == 0
    assert capsys.readouterr().out.splitlines()[0] == "docker compose run --rm -it codex-runner codex login --device-auth"
    assert cli_login.main(["codex", "Partner"]) == 0      # models inherit by default
    assert "inherits the owner's" in capsys.readouterr().out
    assert cli_login.main(["codex", "Nobody"]) == 1
    assert cli_login.main(["gemini", "Partner"]) == 2


# ── /api/llm/models: the catalog cache is per key ────────────────────────────

def test_model_catalog_cache_is_keyed_by_the_api_key(client, test_db, accounts, monkeypatch):
    import backend.api.routes_llm as rl
    a, b = accounts
    rl._cache.clear()
    set_setting(test_db, "llm_provider", "openai")
    set_setting(test_db, "openai_api_key", "sk-owner")
    _models_own(test_db, b)
    _own(test_db, b, "llm_provider", "openai")
    _own(test_db, b, "openai_api_key", "sk-member")
    fetched = []

    async def fake_fetch(key):
        fetched.append(key)
        return [{"id": f"gpt-{key}"}]

    monkeypatch.setattr(rl, "_fetch_openai", fake_fetch)
    assert client.get("/api/llm/models?provider=openai").json()["models"] == [{"id": "gpt-sk-owner"}]
    client.headers["X-Test-Act-As"] = str(b)
    assert client.get("/api/llm/models?provider=openai").json()["models"] == [{"id": "gpt-sk-member"}]
    assert client.get("/api/llm/models?provider=openai").json()["cached"] is True
    assert fetched == ["sk-owner", "sk-member"]
    rl._cache.clear()
