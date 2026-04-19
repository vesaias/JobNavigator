"""Regression: _dispatch must concatenate cached_prefix into prompt for non-Anthropic providers.

Before the fix, providers other than claude_api silently dropped cached_prefix —
scoring broke because the rubric + CVs + schema never reached the model."""
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_dispatch_concatenates_prefix_for_claude_code(monkeypatch):
    """claude_code provider receives cached_prefix + prompt combined (subprocess can't cache)."""
    captured = {}

    async def fake_claude_code(prompt, system, model, max_tokens):
        captured["prompt"] = prompt
        return {"text": '{"ok": 1}',
                "usage": {"input_tokens": 0, "output_tokens": 0,
                          "cache_read_tokens": 0, "cache_write_tokens": 0}}

    monkeypatch.setattr("backend.analyzer.llm_client._call_claude_code", fake_claude_code)

    from backend.analyzer.llm_client import _dispatch
    await _dispatch(
        provider="claude_code", model="claude-sonnet-4-6",
        api_key="", base_url="",
        prompt="JOB DESCRIPTION: Senior PM role",
        system="rubric scorer",
        max_tokens=600,
        cached_prefix="RUBRIC + CVs + SCHEMA",
    )

    assert "RUBRIC + CVs + SCHEMA" in captured["prompt"]
    assert "JOB DESCRIPTION: Senior PM role" in captured["prompt"]
    # Prefix should appear before the suffix
    assert captured["prompt"].index("RUBRIC") < captured["prompt"].index("JOB DESCRIPTION")


@pytest.mark.asyncio
async def test_dispatch_concatenates_prefix_for_openai(monkeypatch):
    """openai provider receives cached_prefix + prompt combined."""
    captured = {}

    async def fake_openai(prompt, system, model, api_key, max_tokens, base_url=None):
        captured["prompt"] = prompt
        return {"text": "{}",
                "usage": {"input_tokens": 10, "output_tokens": 5,
                          "cache_read_tokens": 0, "cache_write_tokens": 0}}

    monkeypatch.setattr("backend.analyzer.llm_client._call_openai", fake_openai)

    from backend.analyzer.llm_client import _dispatch
    await _dispatch(
        provider="openai", model="gpt-4o",
        api_key="sk-test", base_url="",
        prompt="JD text",
        system="sys",
        max_tokens=600,
        cached_prefix="RUBRIC HERE",
    )

    assert "RUBRIC HERE" in captured["prompt"]
    assert "JD text" in captured["prompt"]


@pytest.mark.asyncio
async def test_dispatch_no_prefix_passes_prompt_unchanged(monkeypatch):
    """When cached_prefix is None, the prompt goes through without modification."""
    captured = {}

    async def fake_claude_code(prompt, system, model, max_tokens):
        captured["prompt"] = prompt
        return {"text": "ok",
                "usage": {"input_tokens": 0, "output_tokens": 0,
                          "cache_read_tokens": 0, "cache_write_tokens": 0}}

    monkeypatch.setattr("backend.analyzer.llm_client._call_claude_code", fake_claude_code)

    from backend.analyzer.llm_client import _dispatch
    await _dispatch(
        provider="claude_code", model="claude-sonnet-4-6",
        api_key="", base_url="",
        prompt="bare prompt",
        system="sys",
        max_tokens=50,
        cached_prefix=None,
    )

    assert captured["prompt"] == "bare prompt"


@pytest.mark.asyncio
async def test_dispatch_claude_api_still_uses_cache_control(monkeypatch):
    """claude_api branch passes cached_prefix through (NOT concatenated) so it uses cache_control."""
    captured = {}

    async def fake_claude_api(prompt, system, model, api_key, max_tokens, cached_prefix=None):
        captured["prompt"] = prompt
        captured["cached_prefix"] = cached_prefix
        return {"text": "ok",
                "usage": {"input_tokens": 0, "output_tokens": 0,
                          "cache_read_tokens": 0, "cache_write_tokens": 0}}

    monkeypatch.setattr("backend.analyzer.llm_client._call_claude_api", fake_claude_api)

    from backend.analyzer.llm_client import _dispatch
    await _dispatch(
        provider="claude_api", model="claude-sonnet-4-6",
        api_key="sk", base_url="",
        prompt="JD only",
        system="sys",
        max_tokens=50,
        cached_prefix="RUBRIC",
    )

    # For Anthropic, the prefix must stay separate (it becomes the cache_control block)
    assert captured["prompt"] == "JD only"
    assert captured["cached_prefix"] == "RUBRIC"
