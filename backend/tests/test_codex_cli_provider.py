"""Contract tests for the ChatGPT-subscription Codex CLI provider."""
import json
from pathlib import Path

import pytest

from backend.analyzer import llm_client
from backend.analyzer.llm_client import NonRetryableLLMError


class FakeProcess:
    def __init__(self, stdout=b"", stderr=b"", returncode=0):
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode
        self.input = None

    async def communicate(self, input=None):
        self.input = input
        return self._stdout, self._stderr


def _jsonl(events):
    return ("\n".join(json.dumps(e) for e in events) + "\n").encode()


def _install(monkeypatch, exec_process, login_rc=0):
    """`codex login status` answers login_rc; `codex exec` returns exec_process. Records every argv."""
    calls = []

    async def fake_exec(*args, **kwargs):
        calls.append((args, kwargs))
        if args[:3] == ("codex", "login", "status"):
            return FakeProcess(returncode=login_rc)
        return exec_process

    monkeypatch.setattr(llm_client.asyncio, "create_subprocess_exec", fake_exec)
    return calls


@pytest.mark.asyncio
async def test_codex_cli_runs_ephemeral_read_only_and_parses_jsonl(monkeypatch):
    events = [
        # emitted even on success (Code Mode unavailable); must not be mistaken for the answer or a failure
        {"type": "item.completed", "item": {"type": "error", "message": "Falling back from WebSockets to HTTPS"}},
        {"type": "item.completed", "item": {"type": "agent_message", "text": "  matched  "}},
        {"type": "turn.completed", "usage": {"input_tokens": 81, "cached_input_tokens": 20, "output_tokens": 12}},
    ]
    process = FakeProcess(stdout=_jsonl(events))
    calls = _install(monkeypatch, process)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-should-not-reach-codex")

    result = await llm_client._call_codex_cli("job description", "score against the resume", "gpt-5.6-sol", 600)

    assert calls[0][0][:3] == ("codex", "login", "status")
    args, kwargs = calls[1]
    assert args[:2] == ("codex", "exec")
    for flag in ("--ephemeral", "--ignore-user-config", "--ignore-rules", "--skip-git-repo-check", "--json"):
        assert flag in args
    assert args[args.index("--sandbox") + 1] == "read-only"
    assert args[args.index("--model") + 1] == "gpt-5.6-sol"
    assert args[-1] == "-"
    assert Path(args[args.index("-C") + 1]).name.startswith("jobnavigator-codex-")
    assert "OPENAI_API_KEY" not in kwargs["env"]
    assert process.input == b"score against the resume\n\njob description"
    assert result == {
        "text": "matched",
        "usage": {"input_tokens": 81, "output_tokens": 12, "cache_read_tokens": 20, "cache_write_tokens": 0},
    }


@pytest.mark.asyncio
async def test_codex_cli_not_logged_in_fails_fast_without_running_exec(monkeypatch):
    calls = _install(monkeypatch, FakeProcess(), login_rc=1)
    with pytest.raises(NonRetryableLLMError, match="not logged in.*codex login --device-auth"):
        await llm_client._call_codex_cli("prompt", "system", "", 10)
    assert all(c[0][:3] == ("codex", "login", "status") for c in calls)


@pytest.mark.asyncio
async def test_codex_cli_turn_failed_is_the_error_even_with_rc_zero(monkeypatch):
    events = [
        {"type": "error", "message": "failed to connect to websocket: HTTP error: 500"},
        {"type": "turn.failed", "error": {"message": "model gpt-9 is unknown"}},
    ]
    _install(monkeypatch, FakeProcess(stdout=_jsonl(events), returncode=0))
    with pytest.raises(RuntimeError, match=r"codex exec failed.*model gpt-9 is unknown"):
        await llm_client._call_codex_cli("prompt", "system", "gpt-9", 10)


@pytest.mark.asyncio
async def test_codex_cli_usage_limit_is_not_retryable(monkeypatch):
    events = [{"type": "turn.failed", "error": {"message": "You have hit your usage limit. Try again in 3 hours."}}]
    _install(monkeypatch, FakeProcess(stdout=_jsonl(events), returncode=1))
    with pytest.raises(NonRetryableLLMError, match="usage limit"):
        await llm_client._call_codex_cli("prompt", "system", "", 10)


@pytest.mark.asyncio
async def test_codex_cli_401_after_login_check_reads_as_not_logged_in(monkeypatch):
    events = [{"type": "turn.failed", "error": {"message": "unexpected status 401 Unauthorized: Missing bearer"}}]
    _install(monkeypatch, FakeProcess(stdout=_jsonl(events), returncode=1))
    with pytest.raises(NonRetryableLLMError, match="not logged in"):
        await llm_client._call_codex_cli("prompt", "system", "", 10)


@pytest.mark.asyncio
async def test_codex_cli_reports_subprocess_failure_from_stderr(monkeypatch):
    _install(monkeypatch, FakeProcess(stderr=b"first line\nsomething broke", returncode=1))
    with pytest.raises(RuntimeError, match=r"codex exec failed \(rc=1\): something broke"):
        await llm_client._call_codex_cli("prompt", "system", "", 10)


@pytest.mark.asyncio
async def test_cli_runner_kills_on_timeout(monkeypatch):
    import asyncio

    class Hung(FakeProcess):
        def __init__(self):
            super().__init__()
            self.killed = False

        async def communicate(self, input=None):
            await asyncio.sleep(10)

        def kill(self):
            self.killed = True

        async def wait(self):
            return 0

    hung = Hung()

    async def fake_exec(*args, **kwargs):
        return hung

    monkeypatch.setattr(llm_client.asyncio, "create_subprocess_exec", fake_exec)
    with pytest.raises(RuntimeError, match="timed out after 0s"):
        await llm_client._run_cli(["codex", "exec"], b"", timeout=0.01)
    assert hung.killed


@pytest.mark.asyncio
async def test_call_llm_skips_retries_and_goes_to_fallback_on_non_retryable(monkeypatch):
    attempts = []

    async def fake_dispatch(provider, model, api_key, prompt, system, max_tokens, cached_prefix=None):
        attempts.append(provider)
        if provider == "codex_cli":
            raise NonRetryableLLMError("Codex usage limit reached")
        return {"text": "ok", "usage": {"input_tokens": 1, "output_tokens": 1, "cache_read_tokens": 0, "cache_write_tokens": 0}}

    async def no_sleep(_):
        return None

    monkeypatch.setattr(llm_client, "_dispatch", fake_dispatch)
    monkeypatch.setattr(llm_client.asyncio, "sleep", no_sleep)
    monkeypatch.setattr(llm_client, "_get_setting", lambda db, key, default="": {
        "llm_fallback_provider": "openai", "llm_fallback_model": "gpt-5.4-mini", "llm_fallback_api_key": "k",
    }.get(key, default))
    monkeypatch.setattr(llm_client, "resolve_llm_config", lambda feature="", db=None: {"provider": "codex_cli", "model": "gpt-5.6-sol", "api_key": ""})

    res = await llm_client.call_llm("p", "s", 100)
    assert res["provider"] == "openai"
    assert attempts == ["codex_cli", "openai"]
