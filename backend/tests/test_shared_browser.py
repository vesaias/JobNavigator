"""Tests for _shared/browser.py — Playwright lifecycle + constants."""
import pytest
from unittest.mock import AsyncMock, MagicMock


def test_stealth_args_defined():
    from backend.scraper._shared.browser import _STEALTH_ARGS
    assert isinstance(_STEALTH_ARGS, list)
    assert any("blink-features" in arg for arg in _STEALTH_ARGS)


def test_user_agent_defined():
    from backend.scraper._shared.browser import _USER_AGENT
    assert isinstance(_USER_AGENT, str)
    assert "Chrome" in _USER_AGENT
    assert "Mozilla" in _USER_AGENT


@pytest.mark.asyncio
async def test_close_page_handles_exceptions():
    """_close_page swallows errors — it's best-effort cleanup."""
    mock_page = MagicMock()
    mock_page.close = AsyncMock(side_effect=Exception("already closed"))
    mock_page._stealth_ctx = None

    from backend.scraper._shared.browser import _close_page
    await _close_page(mock_page)  # Should not raise


@pytest.mark.asyncio
async def test_close_page_also_closes_context():
    """_close_page closes _stealth_ctx if present."""
    ctx = MagicMock()
    ctx.close = AsyncMock()
    mock_page = MagicMock()
    mock_page.close = AsyncMock()
    mock_page._stealth_ctx = ctx

    from backend.scraper._shared.browser import _close_page
    await _close_page(mock_page)

    mock_page.close.assert_called_once()
    ctx.close.assert_called_once()
