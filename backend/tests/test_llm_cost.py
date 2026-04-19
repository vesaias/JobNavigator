"""Tests for llm_cost.py — pricing calculations keyed by (provider, model)."""
import pytest
from backend.analyzer.llm_cost import calc_cost, get_pricing, FREE_PROVIDERS


def test_sonnet_pricing_no_cache():
    """Sonnet 4.6 via claude_api: $3/MTok input, $15/MTok output."""
    cost = calc_cost("claude_api", "claude-sonnet-4-6",
                     input_tokens=1000, output_tokens=200,
                     cache_read_tokens=0, cache_write_tokens=0)
    assert cost == pytest.approx(0.006, rel=0.01)


def test_sonnet_pricing_with_cache_read():
    """Cache read is 10x cheaper: $0.30/MTok."""
    cost = calc_cost("claude_api", "claude-sonnet-4-6",
                     input_tokens=500, output_tokens=100,
                     cache_read_tokens=2000, cache_write_tokens=0)
    assert cost == pytest.approx(0.0036, rel=0.01)


def test_sonnet_pricing_with_cache_write():
    """Cache write is 1.25x more: $3.75/MTok."""
    cost = calc_cost("claude_api", "claude-sonnet-4-6",
                     input_tokens=500, output_tokens=100,
                     cache_read_tokens=0, cache_write_tokens=2000)
    assert cost == pytest.approx(0.0105, rel=0.01)


def test_haiku_pricing():
    """Haiku 4.5 via claude_api: $1/MTok input, $5/MTok output."""
    cost = calc_cost("claude_api", "claude-haiku-4-5-20251001",
                     input_tokens=1000, output_tokens=200)
    assert cost == pytest.approx(0.002, rel=0.01)


def test_claude_code_is_free():
    """claude_code is subscription — always $0 regardless of token counts."""
    cost = calc_cost("claude_code", "claude-sonnet-4-6",
                     input_tokens=10000, output_tokens=5000,
                     cache_read_tokens=2000, cache_write_tokens=3000)
    assert cost == 0.0


def test_ollama_is_free():
    """ollama is local — always $0."""
    cost = calc_cost("ollama", "llama3",
                     input_tokens=10000, output_tokens=5000)
    assert cost == 0.0


def test_unknown_provider_returns_zero():
    cost = calc_cost("some-unknown-provider", "claude-sonnet-4-6",
                     input_tokens=1000, output_tokens=200)
    assert cost == 0.0


def test_unknown_model_for_known_provider_returns_zero():
    cost = calc_cost("claude_api", "claude-opus-99",
                     input_tokens=1000, output_tokens=200)
    assert cost == 0.0


def test_get_pricing_known():
    pricing = get_pricing("claude_api", "claude-sonnet-4-6")
    assert pricing["input_per_mtok"] == 3.0
    assert pricing["output_per_mtok"] == 15.0


def test_get_pricing_unknown_model():
    assert get_pricing("claude_api", "bogus-model") is None


def test_get_pricing_unknown_provider():
    assert get_pricing("bogus-provider", "claude-sonnet-4-6") is None


def test_free_providers_set():
    assert "claude_code" in FREE_PROVIDERS
    assert "ollama" in FREE_PROVIDERS
