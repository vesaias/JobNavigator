"""Tests for llm_cost.py — pricing calculations keyed by (provider, model)."""
import pytest
from backend.analyzer.llm_cost import calc_cost, get_pricing, FREE_PROVIDERS, PRICING


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


def test_sonnet_5_is_2_10_distinct_from_4_6():
    """Sonnet 5 is now $2/$10 (standard); Sonnet 4.6 stays $3/$15."""
    p5 = get_pricing("claude_api", "claude-sonnet-5")
    assert p5["input_per_mtok"] == 2.0 and p5["output_per_mtok"] == 10.0
    p46 = get_pricing("claude_api", "claude-sonnet-4-6")
    assert p46["input_per_mtok"] == 3.0 and p46["output_per_mtok"] == 15.0


@pytest.mark.parametrize("model", ["claude-opus-5", "claude-opus-4-8", "claude-opus-4-7", "claude-opus-4-6"])
def test_opus_pricing(model):
    """All current Opus models: $5/MTok input, $25/MTok output (NOT the old $15/$75)."""
    cost = calc_cost("claude_api", model, input_tokens=1000, output_tokens=200)
    assert cost == pytest.approx(0.010, rel=0.01)
    p = get_pricing("claude_api", model)
    assert p["cache_read_per_mtok"] == pytest.approx(0.50)
    assert p["cache_write_per_mtok"] == pytest.approx(6.25)


def test_fable_5_pricing():
    """Fable 5: $10/MTok input, $50/MTok output."""
    cost = calc_cost("claude_api", "claude-fable-5",
                     input_tokens=1000, output_tokens=200)
    assert cost == pytest.approx(0.020, rel=0.01)


def test_haiku_pricing_alias_and_dated_id():
    """Haiku 4.5: $1/$5 — both the alias and legacy dated ID price identically."""
    for model in ("claude-haiku-4-5", "claude-haiku-4-5-20251001"):
        cost = calc_cost("claude_api", model, input_tokens=1000, output_tokens=200)
        assert cost == pytest.approx(0.002, rel=0.01), model


def test_claude_code_is_free():
    """claude_code is subscription — always $0 regardless of token counts."""
    cost = calc_cost("claude_code", "claude-sonnet-5",
                     input_tokens=10000, output_tokens=5000,
                     cache_read_tokens=2000, cache_write_tokens=3000)
    assert cost == 0.0


def test_codex_cli_is_free():
    """codex_cli uses a ChatGPT subscription — always $0 in API-cost stats."""
    cost = calc_cost("codex_cli", "gpt-5.6-sol",
                     input_tokens=10000, output_tokens=5000,
                     cache_read_tokens=2000, cache_write_tokens=0)
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


def test_openai_compat_provider_removed():
    """openai_compat was removed 2026-07 — no pricing, costs $0 (unknown provider)."""
    assert "openai_compat" not in PRICING
    assert get_pricing("openai_compat", "gpt-4o") is None
    assert calc_cost("openai_compat", "gpt-4o", input_tokens=1000) == 0.0


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
    assert "codex_cli" in FREE_PROVIDERS
    assert "ollama" in FREE_PROVIDERS
