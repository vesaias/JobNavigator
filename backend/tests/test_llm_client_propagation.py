"""Tests that call_llm/call_email_llm/call_cv_tailor_llm return dicts and pass cached_prefix through."""
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_call_llm_returns_dict(monkeypatch, mock_anthropic_client, mock_anthropic_response):
    """call_llm returns {text, usage}."""
    # Mock the settings reads
    def fake_get_setting(db, key, default=""):
        return {
            "llm_provider": "claude_api",
            "llm_model": "claude-sonnet-4-6",
            "llm_api_key": "sk-test",
        }.get(key, default)

    monkeypatch.setattr("backend.analyzer.llm_client._get_setting", fake_get_setting)
    mock_anthropic_client.messages.create.return_value = mock_anthropic_response(
        text="ok", input_tokens=100, output_tokens=10,
    )

    from backend.analyzer.llm_client import call_llm
    result = await call_llm("prompt", "system", 100)

    assert isinstance(result, dict)
    assert result["text"] == "ok"
    assert result["usage"]["input_tokens"] == 100


@pytest.mark.asyncio
async def test_call_llm_passes_cached_prefix(monkeypatch, mock_anthropic_client, mock_anthropic_response):
    """call_llm forwards cached_prefix through _dispatch."""
    def fake_get_setting(db, key, default=""):
        return {
            "llm_provider": "claude_api",
            "llm_model": "claude-sonnet-4-6",
            "llm_api_key": "sk-test",
        }.get(key, default)

    monkeypatch.setattr("backend.analyzer.llm_client._get_setting", fake_get_setting)
    mock_anthropic_client.messages.create.return_value = mock_anthropic_response()

    from backend.analyzer.llm_client import call_llm
    await call_llm("JD text", "system", 100, cached_prefix="CACHED RUBRIC")

    # Verify the prefix made it to the anthropic call
    call_args = mock_anthropic_client.messages.create.call_args
    user_content = call_args.kwargs["messages"][0]["content"]
    assert isinstance(user_content, list)
    assert user_content[0]["text"] == "CACHED RUBRIC"


@pytest.mark.asyncio
async def test_openai_provider_returns_dict(monkeypatch):
    """Non-Anthropic providers also return {text, usage} for consistency."""
    from unittest.mock import MagicMock

    fake_resp = MagicMock()
    fake_resp.choices = [MagicMock(message=MagicMock(content="openai result"))]
    fake_resp.usage = MagicMock(prompt_tokens=50, completion_tokens=20)

    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(return_value=fake_resp)

    def fake_ctor(**kwargs):
        return fake_client

    import openai
    monkeypatch.setattr(openai, "AsyncOpenAI", fake_ctor)

    from backend.analyzer.llm_client import _call_openai
    result = await _call_openai("prompt", "system", "gpt-4o", "sk-test", 100)
    assert isinstance(result, dict)
    assert result["text"] == "openai result"
    assert result["usage"]["input_tokens"] == 50
    assert result["usage"]["output_tokens"] == 20
    # OpenAI doesn't have cache_read/write — they should be 0
    assert result["usage"]["cache_read_tokens"] == 0
    assert result["usage"]["cache_write_tokens"] == 0
