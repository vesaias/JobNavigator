"""Tests for _call_claude_api new dict return shape (includes usage)."""
import pytest


@pytest.mark.asyncio
async def test_call_claude_api_returns_dict_with_text_and_usage(mock_anthropic_client, mock_anthropic_response):
    """_call_claude_api returns {'text': str, 'usage': {...}}."""
    mock_anthropic_client.messages.create.return_value = mock_anthropic_response(
        text="hello world",
        input_tokens=500, output_tokens=20,
        cache_read=0, cache_write=0,
    )

    from backend.analyzer.llm_client import _call_claude_api
    result = await _call_claude_api(
        prompt="What is 2+2?",
        system="Be concise.",
        model="claude-sonnet-4-6",
        api_key="sk-test",
        max_tokens=100,
    )

    assert isinstance(result, dict)
    assert result["text"] == "hello world"
    assert result["usage"]["input_tokens"] == 500
    assert result["usage"]["output_tokens"] == 20
    assert result["usage"]["cache_read_tokens"] == 0
    assert result["usage"]["cache_write_tokens"] == 0


@pytest.mark.asyncio
async def test_call_claude_api_extracts_cache_metrics(mock_anthropic_client, mock_anthropic_response):
    """When cache is hit, cache_read_tokens is populated."""
    mock_anthropic_client.messages.create.return_value = mock_anthropic_response(
        text="cached hello",
        input_tokens=200, output_tokens=30,
        cache_read=2400, cache_write=0,
    )

    from backend.analyzer.llm_client import _call_claude_api
    result = await _call_claude_api(
        prompt="x", system="y",
        model="claude-sonnet-4-6", api_key="sk-test", max_tokens=50,
    )

    assert result["usage"]["cache_read_tokens"] == 2400
    assert result["usage"]["cache_write_tokens"] == 0


@pytest.mark.asyncio
async def test_call_claude_api_with_cached_prefix(mock_anthropic_client, mock_anthropic_response):
    """When cached_prefix is provided, the message structure uses cache_control blocks."""
    mock_anthropic_client.messages.create.return_value = mock_anthropic_response(
        text="ok", input_tokens=100, output_tokens=10,
        cache_read=0, cache_write=2400,
    )

    from backend.analyzer.llm_client import _call_claude_api
    await _call_claude_api(
        prompt="JD: software engineer role",
        system="Score candidate fit.",
        model="claude-sonnet-4-6",
        api_key="sk-test",
        max_tokens=200,
        cached_prefix="RUBRIC + CV CONTENT HERE (>1024 tokens)",
    )

    # Inspect how the mock was called — messages should have a list content with cache_control
    call_args = mock_anthropic_client.messages.create.call_args
    messages = call_args.kwargs["messages"]
    user_msg = messages[0]
    assert user_msg["role"] == "user"
    assert isinstance(user_msg["content"], list)
    assert len(user_msg["content"]) == 2
    # First block: cached prefix with cache_control
    assert user_msg["content"][0]["type"] == "text"
    assert user_msg["content"][0]["text"] == "RUBRIC + CV CONTENT HERE (>1024 tokens)"
    assert user_msg["content"][0]["cache_control"] == {"type": "ephemeral"}
    # Second block: per-call suffix, no cache_control
    assert user_msg["content"][1]["type"] == "text"
    assert user_msg["content"][1]["text"] == "JD: software engineer role"
    assert "cache_control" not in user_msg["content"][1]


@pytest.mark.asyncio
async def test_call_claude_api_without_cached_prefix_uses_string_content(mock_anthropic_client, mock_anthropic_response):
    """Back-compat: no cached_prefix → messages content is a plain string."""
    mock_anthropic_client.messages.create.return_value = mock_anthropic_response()

    from backend.analyzer.llm_client import _call_claude_api
    await _call_claude_api(
        prompt="simple prompt",
        system="sys",
        model="claude-sonnet-4-6",
        api_key="sk-test",
        max_tokens=50,
    )

    call_args = mock_anthropic_client.messages.create.call_args
    messages = call_args.kwargs["messages"]
    assert messages[0]["content"] == "simple prompt"  # plain string, not list


@pytest.mark.asyncio
async def test_call_claude_api_usage_defaults_when_cache_attrs_missing(mock_anthropic_client):
    """Back-compat: if the SDK response lacks cache_read/write attrs, default to 0."""
    from unittest.mock import MagicMock, AsyncMock

    resp = MagicMock()
    resp.content = [MagicMock(text="ok")]
    # usage WITHOUT cache_read_input_tokens / cache_creation_input_tokens attrs
    resp.usage = MagicMock(spec=["input_tokens", "output_tokens"])
    resp.usage.input_tokens = 100
    resp.usage.output_tokens = 20
    mock_anthropic_client.messages.create = AsyncMock(return_value=resp)

    from backend.analyzer.llm_client import _call_claude_api
    result = await _call_claude_api(
        prompt="p", system="s",
        model="claude-sonnet-4-6", api_key="sk", max_tokens=50,
    )
    assert result["usage"]["cache_read_tokens"] == 0
    assert result["usage"]["cache_write_tokens"] == 0
