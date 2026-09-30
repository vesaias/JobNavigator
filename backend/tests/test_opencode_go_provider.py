"""Contract tests for the OpenCode Go provider — an OpenAI-compatible endpoint, no CLI/binary."""
import pytest

from backend.analyzer import llm_client
from backend.analyzer.llm_client import NonRetryableLLMError, OPENCODE_GO_BASE_URL


class _StatusError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status_code = status


@pytest.mark.asyncio
async def test_dispatch_routes_opencode_go_to_its_base_url(monkeypatch):
    """opencode_go is OpenAI-API-compatible: same client, Go base URL, key passed through."""
    captured = {}

    async def fake_openai(prompt, system, model, api_key, max_tokens, base_url=None, extra_body=None, effort=""):
        captured.update(prompt=prompt, model=model, api_key=api_key, base_url=base_url)
        return {"text": "ok", "usage": {"input_tokens": 1, "output_tokens": 1,
                                        "cache_read_tokens": 0, "cache_write_tokens": 0}}

    monkeypatch.setattr(llm_client, "_call_openai", fake_openai)
    await llm_client._dispatch(provider="opencode_go", model="deepseek-v4.1-flash", api_key="sk-go",
                               prompt="the question", system="s", max_tokens=10, cached_prefix="the resume")

    assert captured["base_url"] == OPENCODE_GO_BASE_URL
    assert captured["api_key"] == "sk-go"
    assert captured["model"] == "deepseek-v4.1-flash"
    # Non-Anthropic provider: the prefix is concatenated, not sent as a cache block.
    assert captured["prompt"] == "the resume\n\nthe question"


@pytest.mark.asyncio
async def test_missing_key_is_not_retryable(monkeypatch):
    """A Go key is required; a 401 must not retry into the fallback as a transient error."""
    async def boom(*_a, **_k):
        raise _StatusError(401, "Error code: 401 - {'error': {'message': 'Missing API key.'}}")

    monkeypatch.setattr(llm_client, "_call_openai", boom)
    with pytest.raises(NonRetryableLLMError, match="needs an API key"):
        await llm_client._call_opencode_go("p", "s", "deepseek-v4.1-flash", "", 10)


@pytest.mark.asyncio
async def test_autofill_streaming_uses_the_go_base_url(monkeypatch):
    """opencode_go streams natively (like openai/openrouter), so autofill animation works."""
    captured = {}

    async def fake_stream(prompt, system, model, api_key, max_tokens, base_url=None, effort=""):
        captured.update(base_url=base_url, model=model, max_tokens=max_tokens)
        yield "ok"

    monkeypatch.setattr(llm_client, "_stream_openai", fake_stream)
    monkeypatch.setattr(llm_client, "resolve_llm_config", lambda feature="", db=None: {
        "provider": "opencode_go", "model": "glm-5.3", "api_key": "sk-go", "effort": ""})

    chunks = [c async for c in llm_client.call_autofill_llm_stream("q", "s", 100)]
    assert chunks == ["ok"]
    assert captured["base_url"] == OPENCODE_GO_BASE_URL


@pytest.mark.asyncio
async def test_other_errors_still_retry(monkeypatch):
    async def boom(*_a, **_k):
        raise _StatusError(500, "server error")

    monkeypatch.setattr(llm_client, "_call_openai", boom)
    with pytest.raises(_StatusError):
        await llm_client._call_opencode_go("p", "s", "x", "sk", 10)


def test_output_cap_gives_opencode_go_reasoning_headroom():
    """OpenCode Go's models reason by default and the picker has no effort to lower, so without
    headroom the whole cap went to reasoning and returned no text."""
    from backend.analyzer.llm_client import _output_cap, REASONING_HEADROOM
    assert _output_cap("opencode_go", 600, "") == 600 + REASONING_HEADROOM
    assert _output_cap("opencode_go", 600, "none") == 600
    assert _output_cap("openai", 600, "") == 600   # OpenAI still requires an effort for headroom


def test_client_sends_identity_and_session_headers(monkeypatch):
    """Go asks clients to identify themselves and send a stable x-opencode-session; the SDK's
    generic user agent and a missing session header are what the docs warn against."""
    import openai
    captured = {}

    class Fake:
        def __init__(self, **kw):
            captured.update(kw)

    monkeypatch.setattr(openai, "AsyncOpenAI", Fake)
    from backend.analyzer.llm_client import _openai_client, OPENCODE_USER_AGENT, _OPENCODE_SESSION

    _openai_client("sk-go", OPENCODE_GO_BASE_URL)
    assert captured["default_headers"]["User-Agent"] == OPENCODE_USER_AGENT
    assert captured["default_headers"]["x-opencode-session"] == _OPENCODE_SESSION

    captured.clear()
    _openai_client("sk", None)          # plain OpenAI keeps the SDK defaults
    assert captured["default_headers"] is None


@pytest.mark.asyncio
async def test_a_model_on_another_endpoint_is_named(monkeypatch):
    """GPT/Grok use /responses and MiniMax/Qwen use /messages; a chat/completions 404 should
    point the user at a supported model rather than retry."""
    async def boom(*_a, **_k):
        raise _StatusError(404, "Error code: 404 - {'error': {'message': 'The model grok-4.7 does not exist'}}")

    monkeypatch.setattr(llm_client, "_call_openai", boom)
    with pytest.raises(NonRetryableLLMError, match="chat/completions"):
        await llm_client._call_opencode_go("p", "s", "grok-4.7", "sk", 10)


@pytest.mark.asyncio
async def test_catalog_reads_models_from_the_go_base_url(monkeypatch):
    import backend.api.routes_llm as rl
    seen = {}

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"data": [{"id": "deepseek-v4.1-flash"}, {"id": "glm-5.3"}]}

    class _Client:
        def __init__(self, *_a, **_k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_a):
            return False

        async def get(self, url, headers=None):
            seen["url"] = url
            seen["headers"] = headers
            return _Resp()

    monkeypatch.setattr(rl.httpx, "AsyncClient", _Client)
    models = await rl._fetch_opencode_go("sk-go")

    assert seen["url"] == OPENCODE_GO_BASE_URL + "/models"
    assert seen["headers"] == {"Authorization": "Bearer sk-go"}
    assert [m["id"] for m in models] == ["deepseek-v4.1-flash", "glm-5.3"]
