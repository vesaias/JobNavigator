"""Contract tests for the ChatGPT-subscription Codex CLI provider."""
import json
from pathlib import Path

import pytest


class FakeProcess:
    def __init__(self, stdout=b"", stderr=b"", returncode=0):
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode
        self.input = None

    async def communicate(self, input=None):
        self.input = input
        return self._stdout, self._stderr


@pytest.mark.asyncio
async def test_codex_cli_runs_ephemeral_read_only_and_parses_jsonl(monkeypatch):
    from backend.analyzer import llm_client

    events = [
        {"type": "item.completed", "item": {"type": "agent_message", "text": "  matched  "}},
        {"type": "turn.completed", "usage": {
            "input_tokens": 81, "cached_input_tokens": 20, "output_tokens": 12,
        }},
    ]
    process = FakeProcess(stdout=("\n".join(json.dumps(e) for e in events) + "\n").encode())
    captured = {}

    async def fake_exec(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return process

    monkeypatch.setattr(llm_client.asyncio, "create_subprocess_exec", fake_exec)
    result = await llm_client._call_codex_cli(
        "job description", "score against the resume", "gpt-5.6-sol", 600,
    )

    args = captured["args"]
    assert args[:2] == ("codex", "exec")
    assert "--ephemeral" in args
    assert "--ignore-user-config" in args
    assert "--ignore-rules" in args
    assert "--skip-git-repo-check" in args
    assert args[args.index("--sandbox") + 1] == "read-only"
    assert args[args.index("--model") + 1] == "gpt-5.6-sol"
    assert args[-1] == "-"
    assert Path(args[args.index("-C") + 1]).name.startswith("jobnavigator-codex-")
    assert process.input == b"score against the resume\n\njob description"
    assert result == {
        "text": "matched",
        "usage": {"input_tokens": 81, "output_tokens": 12,
                  "cache_read_tokens": 20, "cache_write_tokens": 0},
    }


@pytest.mark.asyncio
async def test_codex_cli_reports_subprocess_failure(monkeypatch):
    from backend.analyzer import llm_client

    async def fake_exec(*args, **kwargs):
        return FakeProcess(stderr=b"login required", returncode=1)

    monkeypatch.setattr(llm_client.asyncio, "create_subprocess_exec", fake_exec)
    with pytest.raises(RuntimeError, match=r"codex subprocess failed.*login required"):
        await llm_client._call_codex_cli("prompt", "system", "", 10)
