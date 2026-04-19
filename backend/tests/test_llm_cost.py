"""Tests for llm_cost.py — pricing calculations."""
import pytest
from backend.analyzer.llm_cost import calc_cost, get_pricing


def test_sonnet_pricing_no_cache():
    """Sonnet 4.6: $3/MTok input, $15/MTok output."""
    cost = calc_cost("claude-sonnet-4-6",
                     input_tokens=1000, output_tokens=200,
                     cache_read_tokens=0, cache_write_tokens=0)
    # 1000 * 3/1M + 200 * 15/1M = 0.003 + 0.003 = 0.006
    assert cost == pytest.approx(0.006, rel=0.01)


def test_sonnet_pricing_with_cache_read():
    """Cache read is 10x cheaper: $0.30/MTok."""
    cost = calc_cost("claude-sonnet-4-6",
                     input_tokens=500, output_tokens=100,
                     cache_read_tokens=2000, cache_write_tokens=0)
    # 500 * 3/1M + 100 * 15/1M + 2000 * 0.30/1M = 0.0015 + 0.0015 + 0.0006 = 0.0036
    assert cost == pytest.approx(0.0036, rel=0.01)


def test_sonnet_pricing_with_cache_write():
    """Cache write is 1.25x more: $3.75/MTok."""
    cost = calc_cost("claude-sonnet-4-6",
                     input_tokens=500, output_tokens=100,
                     cache_read_tokens=0, cache_write_tokens=2000)
    # 500 * 3/1M + 100 * 15/1M + 2000 * 3.75/1M = 0.0015 + 0.0015 + 0.0075 = 0.0105
    assert cost == pytest.approx(0.0105, rel=0.01)


def test_haiku_pricing():
    """Haiku 4.5: $1/MTok input, $5/MTok output."""
    cost = calc_cost("claude-haiku-4-5-20251001",
                     input_tokens=1000, output_tokens=200,
                     cache_read_tokens=0, cache_write_tokens=0)
    # 1000 * 1/1M + 200 * 5/1M = 0.001 + 0.001 = 0.002
    assert cost == pytest.approx(0.002, rel=0.01)


def test_unknown_model_returns_zero():
    """Unknown models should return 0.0, not raise."""
    cost = calc_cost("some-random-model",
                     input_tokens=1000, output_tokens=200)
    assert cost == 0.0


def test_get_pricing_known():
    pricing = get_pricing("claude-sonnet-4-6")
    assert pricing["input_per_mtok"] == 3.0
    assert pricing["output_per_mtok"] == 15.0
    assert pricing["cache_read_per_mtok"] == 0.30
    assert pricing["cache_write_per_mtok"] == 3.75


def test_get_pricing_unknown():
    pricing = get_pricing("unknown-model")
    assert pricing is None
