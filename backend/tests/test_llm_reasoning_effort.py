"""Reasoning effort: which setting a call reads, what each provider receives, and the output cap it gets."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.analyzer import llm_client as L
from backend.cli_runner import runtime as R
from backend.analyzer.llm_client import NonRetryableLLMError, REASONING_HEADROOM
from backend.models.db import Setting


def _settings(db, **values):
    for k, v in values.items():
        db.add(Setting(key=k, value=v))
    db.commit()


# ── resolve_llm_config ───────────────────────────────────────────────────────

def test_primary_effort_is_resolved(test_db):
    _settings(test_db, llm_provider="claude_api", llm_model="claude-opus-5-5", llm_effort="high")
    assert L.resolve_llm_config("")["effort"] == "high"


def test_feature_on_the_primary_provider_inherits_the_primary_effort(test_db):
    _settings(test_db, llm_provider="claude_api", llm_effort="high",
              scoring_llm_provider="claude_api", scoring_llm_model="claude-haiku-4-5")
    assert L.resolve_llm_config("scoring")["effort"] == "high"


def test_feature_on_another_provider_does_not_inherit_the_primary_effort(test_db):
    """claude_api has no "none" and openai has no "max" — an effort is only meaningful on its own provider."""
    _settings(test_db, llm_provider="claude_api", llm_effort="max",
              email_llm_provider="openai", email_llm_model="gpt-6-luna")
    assert L.resolve_llm_config("email")["effort"] == ""


def test_feature_effort_wins_over_the_primary_effort(test_db):
    _settings(test_db, llm_provider="openai", llm_effort="high", cv_tailor_llm_effort="low")
    assert L.resolve_llm_config("cv_tailor")["effort"] == "low"


# ── _dispatch: filter + cap ──────────────────────────────────────────────────

def _capture(monkeypatch, name):
    seen = {}

    async def fake(*args, **kwargs):
        seen["args"], seen["kwargs"] = args, kwargs
        return {"text": "ok", "usage": {}}

    monkeypatch.setattr(L, name, fake)
    return seen


@pytest.mark.asyncio
async def test_an_effort_the_provider_lacks_is_dropped(monkeypatch):
    seen = _capture(monkeypatch, "_call_claude_api")
    await L._dispatch("claude_api", "claude-opus-5-5", "k", "p", "s", 600, effort="none")
    assert seen["kwargs"]["effort"] == ""


@pytest.mark.asyncio
@pytest.mark.parametrize("provider,fn", [("claude_api", "_call_claude_api"), ("openai", "_call_openai"),
                                         ("openrouter", "_call_openai")])
async def test_api_providers_get_headroom_for_reasoning(monkeypatch, provider, fn):
    seen = _capture(monkeypatch, fn)
    await L._dispatch(provider, "m", "k", "p", "s", 600, effort="high")
    assert seen["args"][4] == 600 + REASONING_HEADROOM
    assert seen["kwargs"]["effort"] == "high"


@pytest.mark.asyncio
@pytest.mark.parametrize("provider,fn", [("openai", "_call_openai"), ("openrouter", "_call_openai")])
async def test_openai_style_providers_keep_the_cap_until_an_effort_is_set(monkeypatch, provider, fn):
    """gpt-4o and the small-cap OpenRouter models refuse a 16,600 cap; with no effort chosen nothing reasons."""
    seen = _capture(monkeypatch, fn)
    await L._dispatch(provider, "gpt-4o", "k", "p", "s", 600, effort="")
    assert seen["args"][4] == 600


@pytest.mark.asyncio
async def test_claude_api_gets_headroom_by_default(monkeypatch):
    """Claude 5 models reason unasked, so the headroom applies with the empty default too."""
    seen = _capture(monkeypatch, "_call_claude_api")
    await L._dispatch("claude_api", "claude-sonnet-5", "k", "p", "s", 600, effort="")
    assert seen["args"][4] == 600 + REASONING_HEADROOM


@pytest.mark.asyncio
async def test_effort_none_keeps_the_callers_cap(monkeypatch):
    seen = _capture(monkeypatch, "_call_openai")
    await L._dispatch("openai", "gpt-6-sol", "k", "p", "s", 600, effort="none")
    assert seen["args"][4] == 600


@pytest.mark.asyncio
async def test_cli_providers_keep_the_callers_cap(monkeypatch):
    seen = _capture(monkeypatch, "_call_codex_cli")
    await L._dispatch("codex_cli", "gpt-6-sol", "", "p", "s", 600, effort="xhigh")
    assert seen["args"][3] == 600
    assert seen["kwargs"]["effort"] == "xhigh"


# ── what each provider receives ──────────────────────────────────────────────

def _claude_client(monkeypatch, content, stop_reason="end_turn"):
    resp = MagicMock(content=content, stop_reason=stop_reason)
    resp.usage = MagicMock(input_tokens=1, output_tokens=1, cache_read_input_tokens=0,
                           cache_creation_input_tokens=0)
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=resp)
    import anthropic
    monkeypatch.setattr(anthropic, "AsyncAnthropic", lambda **kw: client)
    return client


@pytest.mark.asyncio
async def test_claude_api_sends_effort_in_output_config_and_skips_the_thinking_block(monkeypatch):
    """The pinned SDK reads a thinking block as a TextBlock with text=None; it must not become the answer."""
    client = _claude_client(monkeypatch, [MagicMock(type="thinking", text=None),
                                          MagicMock(type="text", text=" answer ")])
    res = await L._call_claude_api("p", "s", "claude-opus-5-5", "k", 100, effort="high")
    assert res["text"] == "answer"
    assert client.messages.create.call_args.kwargs["extra_body"] == {"output_config": {"effort": "high"}}


@pytest.mark.asyncio
async def test_claude_api_without_effort_sends_no_output_config(monkeypatch):
    client = _claude_client(monkeypatch, [MagicMock(type="text", text="ok")])
    await L._call_claude_api("p", "s", "claude-sonnet-5", "k", 100)
    assert "extra_body" not in client.messages.create.call_args.kwargs


@pytest.mark.asyncio
async def test_claude_api_reasoning_that_fills_the_cap_is_not_retried(monkeypatch):
    _claude_client(monkeypatch, [MagicMock(type="thinking", text=None)], stop_reason="max_tokens")
    with pytest.raises(NonRetryableLLMError, match="lower the reasoning effort"):
        await L._call_claude_api("p", "s", "claude-opus-5-5", "k", 100, effort="max")


def _openai_client(monkeypatch, content="ok", finish_reason="stop"):
    resp = MagicMock()
    resp.choices = [MagicMock(message=MagicMock(content=content), finish_reason=finish_reason)]
    resp.usage = MagicMock(prompt_tokens=1, completion_tokens=1)
    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=resp)
    import openai
    monkeypatch.setattr(openai, "AsyncOpenAI", lambda **kw: client)
    return client


@pytest.mark.asyncio
async def test_openai_takes_max_completion_tokens_and_reasoning_effort(monkeypatch):
    """OpenAI's reasoning models reject max_tokens."""
    client = _openai_client(monkeypatch)
    await L._call_openai("p", "s", "gpt-6-sol", "k", 700, effort="low")
    kw = client.chat.completions.create.call_args.kwargs
    assert kw["max_completion_tokens"] == 700 and "max_tokens" not in kw
    assert kw["reasoning_effort"] == "low"


@pytest.mark.asyncio
async def test_openrouter_takes_max_tokens_and_a_reasoning_object(monkeypatch):
    client = _openai_client(monkeypatch)
    await L._call_openai("p", "s", "openai/gpt-6-sol", "k", 700, base_url=L.OPENROUTER_BASE_URL, effort="xhigh")
    kw = client.chat.completions.create.call_args.kwargs
    assert kw["max_tokens"] == 700 and "max_completion_tokens" not in kw
    assert kw["extra_body"] == {"reasoning": {"effort": "xhigh"}}
    assert "reasoning_effort" not in kw


@pytest.mark.asyncio
async def test_openai_reasoning_that_fills_the_cap_is_not_retried(monkeypatch):
    _openai_client(monkeypatch, content=None, finish_reason="length")
    with pytest.raises(NonRetryableLLMError, match="lower the reasoning effort"):
        await L._call_openai("p", "s", "gpt-6-sol", "k", 100, effort="max")


@pytest.mark.asyncio
async def test_claude_code_passes_effort_flag(test_db, monkeypatch):
    seen = {}

    async def fake_run_cli(cmd, stdin, env=None, timeout=None, cwd=None):
        seen["cmd"] = cmd
        return 0, b'{"result": "ok", "is_error": false, "subtype": "success"}', b""

    monkeypatch.setattr(R, "_run_cli", fake_run_cli)
    await R._call_claude_code("p", "s", "claude-opus-5-5", 100, effort="xhigh")
    assert seen["cmd"][seen["cmd"].index("--effort") + 1] == "xhigh"


@pytest.mark.asyncio
async def test_codex_passes_effort_as_a_toml_string(monkeypatch):
    seen = {}

    async def fake_run_cli(cmd, stdin, env=None, timeout=None, cwd=None):
        seen.setdefault("cmds", []).append(cmd)
        if cmd[:3] == ["codex", "login", "status"]:
            return 0, b"", b""
        return 0, b'{"type": "item.completed", "item": {"type": "agent_message", "text": "ok"}}\n', b""

    monkeypatch.setattr(R, "_run_cli", fake_run_cli)
    await R._call_codex_cli("p", "s", "gpt-6-sol", 100, effort="high")
    cmd = seen["cmds"][-1]
    assert cmd[cmd.index("-c", cmd.index("--model")) + 1] == 'model_reasoning_effort="high"'


# ── call_llm fallback + settings API ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_the_fallback_uses_its_own_effort(test_db, monkeypatch):
    _settings(test_db, llm_provider="claude_api", llm_model="a", llm_effort="max",
              llm_fallback_provider="openai", llm_fallback_model="b", llm_fallback_effort="none")
    efforts = []

    async def fake_dispatch(provider, model, *a, cached_prefix=None, effort=""):
        efforts.append(effort)
        if provider == "claude_api":
            raise NonRetryableLLMError("down")
        return {"text": "ok", "usage": {}}

    monkeypatch.setattr(L, "_dispatch", fake_dispatch)
    await L.call_llm("p", "s", 100)
    assert efforts == ["max", "none"]


def _seed_first_run(test_db):
    """Open access for the API client: with INITIAL_API_KEY set in the environment the
    middleware wants a key unless the dashboard_api_key row exists and is empty."""
    from backend.models.db import Setting
    test_db.add(Setting(key="dashboard_api_key", value=""))
    test_db.commit()


def test_settings_api_lists_efforts_and_rejects_an_unknown_one(api_client, test_db):
    _seed_first_run(test_db)
    efforts = api_client.get("/api/llm/efforts").json()["efforts"]
    assert efforts["claude_code"] == ["low", "medium", "high", "xhigh", "max"]
    assert "antigravity_cli" not in efforts

    assert api_client.patch("/api/settings", json={"llm_effort": "xhigh"}).status_code == 200
    assert api_client.patch("/api/settings", json={"llm_effort": "turbo"}).status_code == 400
