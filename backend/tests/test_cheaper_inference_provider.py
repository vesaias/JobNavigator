"""Contract tests for the Cheaper Inference provider — an OpenAI-compatible gateway, pay per token."""
import pytest

from backend.analyzer import llm_client
from backend.analyzer.llm_client import CHEAPER_INFERENCE_BASE_URL, NonRetryableLLMError


class _StatusError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status_code = status


@pytest.mark.asyncio
async def test_dispatch_routes_cheaper_inference_to_its_base_url(monkeypatch):
    """cheaper_inference is OpenAI-API-compatible: same client, its base URL, key passed through."""
    captured = {}

    async def fake_openai(prompt, system, model, api_key, max_tokens, base_url=None, extra_body=None, effort=""):
        captured.update(prompt=prompt, model=model, api_key=api_key, base_url=base_url)
        return {"text": "ok", "usage": {"input_tokens": 1, "output_tokens": 1,
                                        "cache_read_tokens": 0, "cache_write_tokens": 0}}

    monkeypatch.setattr(llm_client, "_call_openai", fake_openai)
    await llm_client._dispatch(provider="cheaper_inference", model="gpt-5.4-mini", api_key="ci-key",
                               prompt="the question", system="s", max_tokens=10, cached_prefix="the resume")

    assert captured["base_url"] == CHEAPER_INFERENCE_BASE_URL
    assert captured["api_key"] == "ci-key"
    assert captured["model"] == "gpt-5.4-mini"
    # Non-Anthropic provider: the prefix is concatenated, not sent as a cache block.
    assert captured["prompt"] == "the resume\n\nthe question"


@pytest.mark.asyncio
async def test_missing_key_is_not_retryable(monkeypatch):
    """No key at all stops before anything is sent."""
    monkeypatch.delenv("CHEAPER_INFERENCE_API_KEY", raising=False)
    monkeypatch.setattr(llm_client, "_own_login_account", lambda: None)
    sent = []

    async def fake_openai(*a, **k):
        sent.append(a)
        return {"text": "ok", "usage": {}}

    monkeypatch.setattr(llm_client, "_call_openai", fake_openai)
    with pytest.raises(NonRetryableLLMError, match="No API key for Cheaper Inference"):
        await llm_client._call_cheaper_inference("p", "s", "gpt-5.4-mini", "", 10)
    assert sent == []


@pytest.mark.asyncio
async def test_env_key_is_used_when_the_setting_is_empty(monkeypatch):
    monkeypatch.setenv("CHEAPER_INFERENCE_API_KEY", "ci-env")
    monkeypatch.setattr(llm_client, "_own_login_account", lambda: None)
    captured = {}

    async def fake_openai(prompt, system, model, api_key, max_tokens, base_url=None, extra_body=None, effort=""):
        captured["api_key"] = api_key
        return {"text": "ok", "usage": {}}

    monkeypatch.setattr(llm_client, "_call_openai", fake_openai)
    await llm_client._call_cheaper_inference("p", "s", "gpt-5.4-mini", "", 10)
    assert captured["api_key"] == "ci-env"


@pytest.mark.asyncio
async def test_rejected_key_is_not_retryable(monkeypatch):
    """A 401 cannot succeed on a retry, so the fallback runs at once."""
    async def boom(*_a, **_k):
        raise _StatusError(401, "Error code: 401 - invalid api key")

    monkeypatch.setattr(llm_client, "_call_openai", boom)
    with pytest.raises(NonRetryableLLMError, match="rejected the API key"):
        await llm_client._call_cheaper_inference("p", "s", "gpt-5.4-mini", "ci-key", 10)


@pytest.mark.asyncio
async def test_other_errors_still_retry(monkeypatch):
    async def boom(*_a, **_k):
        raise _StatusError(500, "server error")

    monkeypatch.setattr(llm_client, "_call_openai", boom)
    with pytest.raises(_StatusError):
        await llm_client._call_cheaper_inference("p", "s", "gpt-5.4-mini", "ci-key", 10)


@pytest.mark.asyncio
async def test_autofill_streaming_uses_the_cheaper_inference_base_url(monkeypatch):
    """cheaper_inference streams natively (like openai/openrouter), so autofill animation works."""
    captured = {}

    async def fake_stream(prompt, system, model, api_key, max_tokens, base_url=None, effort="", feature=""):
        captured.update(base_url=base_url, model=model, api_key=api_key)
        yield "ok"

    monkeypatch.setattr(llm_client, "_stream_openai", fake_stream)
    monkeypatch.setattr(llm_client, "resolve_llm_config", lambda feature="", db=None: {
        "provider": "cheaper_inference", "model": "claude-sonnet-5", "api_key": "ci-key", "effort": ""})

    chunks = [c async for c in llm_client.call_autofill_llm_stream("q", "s", 100)]
    assert chunks == ["ok"]
    assert captured == {"base_url": CHEAPER_INFERENCE_BASE_URL, "model": "claude-sonnet-5", "api_key": "ci-key"}


def test_output_cap_always_gives_cheaper_inference_headroom():
    """No effort values to lower and models that reason by default, so the cap always gets the room."""
    from backend.analyzer.llm_client import _output_cap, REASONING_HEADROOM
    assert _output_cap("cheaper_inference", 600, "") == 600 + REASONING_HEADROOM
    assert _output_cap("cheaper_inference", 600, "none") == 600


def test_request_uses_max_completion_tokens():
    """It serves OpenAI's reasoning models, which reject `max_tokens`."""
    kwargs = llm_client._openai_kwargs(600, "", CHEAPER_INFERENCE_BASE_URL)
    assert kwargs == {"max_completion_tokens": 600}
    assert llm_client._openai_kwargs(600, "", llm_client.OPENROUTER_BASE_URL) == {"max_tokens": 600}


def test_client_sends_no_extra_headers_and_never_none(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-env")
    client = llm_client._openai_client(None, CHEAPER_INFERENCE_BASE_URL)
    assert client.api_key == ""
    assert str(client.base_url).rstrip("/") == CHEAPER_INFERENCE_BASE_URL


@pytest.mark.asyncio
async def test_catalog_lists_only_chat_text_models_from_the_public_list(monkeypatch):
    import backend.api.routes_llm as rl
    seen = {}

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"models": [
                {"id": "gpt-5.4-mini", "model_type": "text", "context_length": 400000,
                 "supported_endpoints": ["/v1/chat/completions", "/v1/responses"]},
                {"id": "a-responses-only", "model_type": "text", "supported_endpoints": ["/v1/responses"]},
                {"id": "text-embedding-3-small", "model_type": "embedding",
                 "supported_endpoints": ["/v1/embeddings"]},
                {"id": "no-metadata"},
            ]}

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
    models = await rl._fetch_cheaper_inference()

    assert seen["url"] == "https://api.cheaperinference.com/public/models"
    assert seen["headers"] is None   # public list: no key is sent
    assert models == [{"id": "gpt-5.4-mini", "name": "gpt-5.4-mini", "context_length": 400000}]
