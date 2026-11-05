"""_call_claude_code must name what went wrong instead of handing back "".

`claude -p --output-format json` reports a refusal, an overload or a spent quota
as an rc=0 envelope with `is_error` set; its `result` can also be empty. Both
used to leave the caller parsing an empty string.
"""
import json as _json

import pytest

from backend.cli_runner.runtime import NonRetryableLLMError, _call_claude_code

def _cli_printing(monkeypatch, payload, rc=0, stderr=b""):
    out = payload if isinstance(payload, bytes) else _json.dumps(payload).encode()

    async def fake_run_cli(cmd, stdin, env=None, timeout=None, cwd=None):
        return rc, out, stderr

    monkeypatch.setattr("backend.cli_runner.runtime._run_cli", fake_run_cli)


async def _call():
    return await _call_claude_code("p", "s", "claude-sonnet-5", 3000)


@pytest.mark.asyncio
async def test_a_normal_envelope_yields_its_result(monkeypatch):
    _cli_printing(monkeypatch, {"result": '{"summary": "x"}', "is_error": False,
                                "subtype": "success"})
    assert (await _call())["text"] == '{"summary": "x"}'


@pytest.mark.asyncio
async def test_plain_stdout_still_passes_through(monkeypatch):
    """Not every build prints an envelope; a bare answer is still an answer."""
    _cli_printing(monkeypatch, b'{"summary": "x"}')
    assert (await _call())["text"] == '{"summary": "x"}'


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [
    {"result": "", "is_error": False, "subtype": "success"},
    {"result": "   \n ", "is_error": False},
    b"",
])
async def test_an_empty_reply_raises_instead_of_returning_nothing(monkeypatch, payload):
    _cli_printing(monkeypatch, payload)
    with pytest.raises(RuntimeError) as exc:
        await _call()
    assert "empty reply" in str(exc.value)
    # Retryable on purpose: call_llm's loop should get another go at it.
    assert not isinstance(exc.value, NonRetryableLLMError)


@pytest.mark.asyncio
async def test_an_error_envelope_carries_the_cli_text(monkeypatch):
    _cli_printing(monkeypatch, {"result": "API Error: 500 Internal Server Error",
                                "is_error": True, "subtype": "error_during_execution"})
    with pytest.raises(RuntimeError) as exc:
        await _call()
    assert "500 Internal Server Error" in str(exc.value)


@pytest.mark.asyncio
async def test_an_error_envelope_without_text_still_names_its_subtype(monkeypatch):
    _cli_printing(monkeypatch, {"result": "", "is_error": True,
                                "subtype": "error_max_turns"})
    with pytest.raises(RuntimeError) as exc:
        await _call()
    assert "error_max_turns" in str(exc.value)


@pytest.mark.asyncio
async def test_a_spent_quota_is_not_retried(monkeypatch):
    _cli_printing(monkeypatch, {"result": "Claude usage limit reached — resets at 5pm",
                                "is_error": True, "subtype": "error"})
    with pytest.raises(NonRetryableLLMError) as exc:
        await _call()
    assert "usage limit" in str(exc.value)


@pytest.mark.asyncio
async def test_a_failed_subprocess_still_reports_stderr(monkeypatch):
    _cli_printing(monkeypatch, b"", rc=1, stderr=b"not logged in")
    with pytest.raises(RuntimeError) as exc:
        await _call()
    assert "not logged in" in str(exc.value)
