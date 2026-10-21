"""Contract tests for the Google-subscription Antigravity CLI provider."""
import json
import os
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


def _events(*events):
    return ("\n".join(json.dumps(e) for e in events) + "\n").encode()


def _result(**fields):
    base = {"conversation_id": "c-1", "status": "SUCCESS", "response": "  matched  ",
            "usage": {"input_tokens": 81, "output_tokens": 12, "cache_read_tokens": 20}}
    base.update(fields)
    return {"event": "result", "result": base}


def _install(monkeypatch, process):
    """`agy` returns process. Records every argv and kwargs."""
    calls = []

    async def fake_exec(*args, **kwargs):
        calls.append((args, kwargs))
        return process

    monkeypatch.setattr(llm_client.asyncio, "create_subprocess_exec", fake_exec)
    monkeypatch.setattr(llm_client, "_agy_discard", lambda cid: None)
    monkeypatch.setattr(llm_client, "_agy_install_settings", lambda: ["command(*)"])
    monkeypatch.setattr(llm_client, "_agy_assert_denied", lambda path, rules: None)
    return calls


@pytest.mark.asyncio
async def test_antigravity_sends_one_ndjson_line_and_parses_the_result_event(monkeypatch):
    process = FakeProcess(stdout=_events(
        {"event": "init", "init": {"model": "gemini-3.8-flash-medium"}},
        {"event": "step_update", "step_update": {"state": "ACTIVE"}},
        _result(),
    ))
    calls = _install(monkeypatch, process)
    monkeypatch.setenv("GEMINI_API_KEY", "should-not-reach-agy")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/tmp/adc.json")

    result = await llm_client._call_antigravity_cli(
        "job description", "score against the resume", "gemini-3.8-flash-medium", 600)

    args, kwargs = calls[0]
    assert args[0] == "agy"
    assert args[args.index("--input-format") + 1] == "stream-json"
    assert args[args.index("--output-format") + 1] == "stream-json"
    assert args[args.index("--model") + 1] == "gemini-3.8-flash-medium"
    # `-p` swallows the next token, so it must stay last with an attached empty value.
    assert args[-1] == "-p="
    assert "GEMINI_API_KEY" not in kwargs["env"]
    assert "GOOGLE_APPLICATION_CREDENTIALS" not in kwargs["env"]
    assert Path(kwargs["cwd"]).name.startswith("jobnavigator-agy-")

    sent = json.loads(process.input.decode())
    assert sent == {"event": "user",
                    "message": {"role": "user",
                                "content": "score against the resume\n\njob description"}}
    assert result == {
        "text": "matched",
        "usage": {"input_tokens": 81, "output_tokens": 12,
                  "cache_read_tokens": 20, "cache_write_tokens": 0},
    }


@pytest.mark.asyncio
async def test_antigravity_not_logged_in_is_not_retryable(monkeypatch):
    _install(monkeypatch, FakeProcess(
        stdout=_events(_result(status="ERROR", response="",
                               error="authentication failed or timed out")),
        returncode=1))
    with pytest.raises(NonRetryableLLMError, match="not logged in.*docker compose exec"):
        await llm_client._call_antigravity_cli("prompt", "system", "", 10)


@pytest.mark.asyncio
async def test_antigravity_expired_login_is_not_retryable(monkeypatch):
    """agy 1.3.3+ words an expired or revoked token this way; a retry cannot fix it."""
    _install(monkeypatch, FakeProcess(
        stdout=_events(_result(status="ERROR", response="",
                               error="Authentication expired. Please log back in.")),
        returncode=1))
    with pytest.raises(NonRetryableLLMError, match="not logged in.*docker compose exec"):
        await llm_client._call_antigravity_cli("prompt", "system", "", 10)


@pytest.mark.asyncio
async def test_antigravity_usage_limit_is_not_retryable(monkeypatch):
    _install(monkeypatch, FakeProcess(
        stdout=_events(_result(status="ERROR", error="You have hit your usage limit.")),
        returncode=1))
    with pytest.raises(NonRetryableLLMError, match="usage limit"):
        await llm_client._call_antigravity_cli("prompt", "system", "", 10)


@pytest.mark.asyncio
async def test_antigravity_error_status_wins_even_with_rc_zero(monkeypatch):
    _install(monkeypatch, FakeProcess(
        stdout=_events(_result(status="ERROR", error='invalid model selection (--model "gemini-9")')),
        returncode=0))
    with pytest.raises(RuntimeError, match="agy failed.*invalid model selection"):
        await llm_client._call_antigravity_cli("prompt", "system", "gemini-9", 10)


@pytest.mark.asyncio
async def test_antigravity_reports_subprocess_failure_from_stderr(monkeypatch):
    _install(monkeypatch, FakeProcess(stderr=b"first line\nsomething broke", returncode=1))
    with pytest.raises(RuntimeError, match=r"agy failed \(rc=1\): something broke"):
        await llm_client._call_antigravity_cli("prompt", "system", "", 10)


@pytest.mark.asyncio
async def test_antigravity_empty_response_is_an_error(monkeypatch):
    _install(monkeypatch, FakeProcess(stdout=_events(_result(response="   "))))
    with pytest.raises(RuntimeError, match="without a response"):
        await llm_client._call_antigravity_cli("prompt", "system", "", 10)


@pytest.mark.asyncio
async def test_antigravity_discards_the_transcript_that_holds_the_prompt(monkeypatch, tmp_path):
    """The per-call transcript carries the whole resume. Nothing reads it back, so it goes."""
    state = tmp_path / "antigravity-cli"
    for sub in ("conversations", "presence", "annotations", "brain/c-1"):
        (state / sub).mkdir(parents=True, exist_ok=True)
    (state / "conversations/c-1.db").write_text("x")
    (state / "conversations/c-1.db-wal").write_text("x")
    (state / "presence/c-1.lock").write_text("x")
    (state / "annotations/c-1.pbtxt").write_text("x")
    (state / "brain/c-1/transcript.jsonl").write_text("resume text")
    (state / "conversations/keep-me.db").write_text("x")
    monkeypatch.setattr(llm_client, "_AGY_STATE", str(state))

    llm_client._agy_discard("c-1")

    assert not (state / "conversations/c-1.db").exists()
    assert not (state / "conversations/c-1.db-wal").exists()
    assert not (state / "presence/c-1.lock").exists()
    assert not (state / "annotations/c-1.pbtxt").exists()
    assert not (state / "brain/c-1").exists()
    assert (state / "conversations/keep-me.db").exists()


@pytest.mark.asyncio
async def test_antigravity_discards_the_transcript_when_the_call_times_out(monkeypatch):
    """The timeout path is the one that matters: a hung call still wrote the prompt to disk."""
    init = json.dumps({"event": "init", "conversation_id": "c-hung"}).encode() + b"\n"
    discarded = []

    async def fake_run_cli(cmd, stdin, env=None, timeout=None, cwd=None):
        raise llm_client.CLITimeoutError("agy timed out after 300s", init, b"")

    monkeypatch.setattr(llm_client, "_run_cli", fake_run_cli)
    monkeypatch.setattr(llm_client, "_agy_install_settings", lambda: [])
    monkeypatch.setattr(llm_client, "_agy_discard", discarded.append)

    with pytest.raises(llm_client.CLITimeoutError):
        await llm_client._call_antigravity_cli("prompt", "system", "", 10)
    assert discarded == ["c-hung"]


@pytest.mark.asyncio
async def test_antigravity_refuses_when_the_log_does_not_confirm_the_deny_rules(monkeypatch, tmp_path):
    """agy can fall back to its defaults; a call that cannot prove the deny list must not run."""
    log = tmp_path / "cli.log"
    log.write_text("I0916 cli_setting_manager.go:92] CLI settings initialized: "
                   "permissions=&{Allow:[] Deny:[] Ask:[]}\n")
    with pytest.raises(NonRetryableLLMError, match="without the deny rules"):
        llm_client._agy_assert_denied(str(log), ["command(*)", "read_file(/)"])


@pytest.mark.asyncio
async def test_antigravity_refuses_when_the_log_says_nothing_about_permissions(monkeypatch, tmp_path):
    with pytest.raises(NonRetryableLLMError, match="never reported its permissions"):
        llm_client._agy_assert_denied(str(tmp_path / "absent.log"), ["command(*)"])


def test_antigravity_settings_are_installed_where_agy_can_rewrite_them(monkeypatch, tmp_path):
    """A read-only copy makes agy's own start-up write fail, which is how it reaches its defaults."""
    source = tmp_path / "shipped.json"
    source.write_text(json.dumps({"permissions": {"deny": ["command(*)", "read_file(/)"]}}))
    state = tmp_path / "state"
    monkeypatch.setattr(llm_client, "_AGY_SETTINGS_SOURCE", str(source))
    monkeypatch.setattr(llm_client, "_AGY_STATE", str(state))

    rules = llm_client._agy_install_settings()

    assert rules == ["command(*)", "read_file(/)"]
    written = state / "settings.json"
    assert json.loads(written.read_text()) == json.loads(source.read_text())
    assert os.access(written, os.W_OK)


def test_antigravity_refuses_when_the_shipped_deny_list_is_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(llm_client, "_AGY_SETTINGS_SOURCE", str(tmp_path / "gone.json"))
    with pytest.raises(NonRetryableLLMError, match="deny list is missing"):
        llm_client._agy_install_settings()
