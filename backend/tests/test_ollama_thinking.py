"""Contract tests for the Ollama provider and thinking models: `think` on the
request, the reasoning effort, and a reply the reasoning used up."""
import pytest

from backend.analyzer import llm_client
from backend.analyzer.llm_client import NonRetryableLLMError, REASONING_HEADROOM
from backend.tests.r4_support import client  # noqa: F401  (fixture)

_ANSWER = {"response": ' {"score": 80} ', "done_reason": "stop", "prompt_eval_count": 1, "eval_count": 1}
# What Ollama returns when the reasoning fills num_predict before the answer begins.
_REASONING_ONLY = {"response": "", "thinking": "Let me compare the résumé with...", "done_reason": "length",
                   "prompt_eval_count": 1, "eval_count": 600}


def _ollama_answers(monkeypatch, payload):
    """Route _call_ollama's real httpx client at a mock transport that answers every request with
    `payload`; returns the requests, so a test reads the body and the timeout that were sent."""
    import httpx
    calls = []
    real = httpx.AsyncClient

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=payload)

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setattr(llm_client, "local_base_url", lambda provider: "http://ollama:11434")
    return calls


def _sent(request) -> dict:
    import json
    return json.loads(request.content)


@pytest.mark.asyncio
@pytest.mark.parametrize("effort", ["", "none"])
async def test_thinking_is_off_without_a_reasoning_effort(monkeypatch, effort):
    """Thinking models reason by default and the reasoning counts against num_predict, so a
    scoring call returned an empty or cut-off reply. Without a level, `think` is false, the choice
    the LM Studio branch makes with reasoning_effort="none"."""
    calls = _ollama_answers(monkeypatch, _ANSWER)
    res = await llm_client._call_ollama("p", "s", "thinking-model:8b", 600, effort=effort)

    assert res["text"] == '{"score": 80}'
    assert _sent(calls[0])["think"] is False
    assert _sent(calls[0])["options"] == {"num_predict": 600}
    assert calls[0].extensions["timeout"]["read"] == 120


@pytest.mark.asyncio
@pytest.mark.parametrize("effort", ["low", "medium", "high"])
async def test_a_reasoning_effort_turns_thinking_on_with_the_long_timeout(monkeypatch, effort):
    """Ollama's `think` is an on/off switch for most models, so every level sends true; a local
    GPU can reason for minutes, so the call waits OLLAMA_THINKING_TIMEOUT instead of 120 s."""
    calls = _ollama_answers(monkeypatch, _ANSWER)
    await llm_client._call_ollama("p", "s", "thinking-model:8b", 600, effort=effort)

    assert _sent(calls[0])["think"] is True
    assert calls[0].extensions["timeout"]["read"] == llm_client.OLLAMA_THINKING_TIMEOUT


def test_output_cap_gives_ollama_headroom_only_with_a_level():
    """The reasoning room the API providers get, but only when thinking is on: with it off, a
    larger cap would only let a model that ignores it run longer."""
    from backend.analyzer.llm_client import _output_cap
    assert _output_cap("ollama", 600, "") == 600
    assert _output_cap("ollama", 600, "none") == 600
    for level in ("low", "medium", "high"):
        assert _output_cap("ollama", 600, level) == 600 + REASONING_HEADROOM


@pytest.mark.asyncio
@pytest.mark.parametrize("effort,expected", [
    ("high", {"max_tokens": 600 + REASONING_HEADROOM, "effort": "high"}),
    ("", {"max_tokens": 600, "effort": ""}),
    ("xhigh", {"max_tokens": 600, "effort": ""}),     # not an Ollama value: dropped, thinking stays off
])
async def test_dispatch_sends_the_effort_and_the_cap_to_ollama(monkeypatch, effort, expected):
    """_dispatch keeps an Ollama level, drops a left-over effort from another provider, and pads the
    cap only for a level."""
    captured = {}

    async def fake_ollama(prompt, system, model, max_tokens, effort=""):
        captured.update(max_tokens=max_tokens, effort=effort)
        return {"text": "ok", "usage": {}}

    monkeypatch.setattr(llm_client, "_call_ollama", fake_ollama)
    await llm_client._dispatch(provider="ollama", model="thinking-model:8b", api_key="",
                               prompt="p", system="s", max_tokens=600, effort=effort)
    assert captured == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("effort,hint", [
    ("", "pick a reasoning effort for it in Settings › Models"),   # gpt-oss reasons with think=false
    ("high", "lower the reasoning effort"),                        # the level's reasoning outgrew the room
])
async def test_a_reply_the_reasoning_used_up_is_named_and_not_retried(monkeypatch, effort, hint):
    """Before, the empty reply reached the JSON check and failed as "not valid JSON"; a retry ends
    the same way, so the message names the model and the fix instead."""
    _ollama_answers(monkeypatch, _REASONING_ONLY)
    with pytest.raises(NonRetryableLLMError, match=hint) as e:
        await llm_client._call_ollama("p", "s", "gpt-oss:20b", 600, effort=effort)
    assert "gpt-oss:20b used the whole output cap on reasoning" in str(e.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("payload,text", [
    ({"response": "", "done_reason": "stop"}, ""),                         # ended normally
    ({"response": '{"score": ', "done_reason": "length"}, '{"score":'),    # cut off, but has text
])
async def test_other_replies_take_the_normal_path(monkeypatch, payload, text):
    """Only an empty reply that hit the cap is an error here; anything else is returned as before,
    and the caller's JSON check decides, as for every provider."""
    _ollama_answers(monkeypatch, payload)
    res = await llm_client._call_ollama("p", "s", "thinking-model:8b", 600)
    assert res["text"] == text


@pytest.mark.asyncio
async def test_call_llm_skips_the_retries_when_the_reasoning_used_up_the_reply(monkeypatch):
    """End to end: the primary is tried once, not four times; each try is a full reasoning run on
    the local GPU."""
    calls = _ollama_answers(monkeypatch, _REASONING_ONLY)
    settings = {"llm_provider": "ollama", "llm_model": "gpt-oss:20b",
                "llm_fallback_provider": "", "llm_fallback_model": ""}
    monkeypatch.setattr(llm_client, "_get_setting", lambda db, k, d="": settings.get(k, d))
    monkeypatch.setattr(llm_client, "SessionLocal", lambda: type("S", (), {"close": lambda self: None})())
    with pytest.raises(NonRetryableLLMError, match="used the whole output cap on reasoning"):
        await llm_client.call_llm("p", "s", 10)
    assert len(calls) == 1


def test_efforts_endpoint_lists_the_ollama_levels(client):
    """The Settings effort picker is built from this list, so Ollama gets one with no frontend code."""
    r = client.get("/api/llm/efforts")   # the keyed client: an install with a dashboard key answers 401 without it
    assert r.status_code == 200
    assert r.json()["efforts"]["ollama"] == ["none", "low", "medium", "high"]
