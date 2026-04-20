"""Tests for notifier/telegram._send_message — bool return on success/failure."""
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_send_message_returns_true_on_success(monkeypatch, mock_telegram):
    """Successful HTTP 200 + ok:true → returns True."""
    # Ensure Telegram is treated as enabled + token available
    monkeypatch.setattr("backend.notifier.telegram._is_enabled", lambda: True, raising=False)
    monkeypatch.setattr("backend.notifier.telegram.TELEGRAM_BOT_TOKEN", "fake-bot-token", raising=False)
    monkeypatch.setattr("backend.notifier.telegram.BASE_URL",
                        "https://api.telegram.org/botfake-bot-token", raising=False)

    from backend.notifier.telegram import _send_message
    result = await _send_message(chat_id="123", text="hello", parse_mode="HTML")
    assert result is True


@pytest.mark.asyncio
async def test_send_message_returns_false_on_network_error(monkeypatch):
    """When httpx raises (network down, timeout), _send_message returns False."""
    import httpx

    async def broken_post(*a, **kw):
        raise httpx.RequestError("network down")

    client = MagicMock()
    client.post = AsyncMock(side_effect=broken_post)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: client)

    monkeypatch.setattr("backend.notifier.telegram._is_enabled", lambda: True, raising=False)
    monkeypatch.setattr("backend.notifier.telegram.TELEGRAM_BOT_TOKEN", "fake-bot-token", raising=False)
    monkeypatch.setattr("backend.notifier.telegram.BASE_URL",
                        "https://api.telegram.org/botfake-bot-token", raising=False)

    from backend.notifier.telegram import _send_message
    result = await _send_message(chat_id="123", text="hello", parse_mode="HTML")
    assert result is False


@pytest.mark.asyncio
async def test_send_message_returns_false_when_missing_token(monkeypatch):
    """When no bot token is configured, returns False (not None)."""
    monkeypatch.setattr("backend.notifier.telegram.TELEGRAM_BOT_TOKEN", "", raising=False)

    from backend.notifier.telegram import _send_message
    result = await _send_message(chat_id="123", text="hi", parse_mode="HTML")
    assert result is False
