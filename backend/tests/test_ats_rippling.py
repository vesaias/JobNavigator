"""Tests for ats/rippling.py — detection + parse + API mock."""
import pytest
from unittest.mock import AsyncMock, MagicMock


def test_is_rippling_detects_ats():
    """Per CLAUDE.md: Rippling URLs look like ats.rippling.com/<slug>/jobs."""
    from backend.scraper.ats.rippling import is_rippling
    # Check both ats.rippling.com and the `careers` variant
    assert is_rippling("https://ats.rippling.com/acme/jobs")


def test_is_rippling_detects_careers():
    from backend.scraper.ats.rippling import is_rippling
    # Per CLAUDE.md, rippling.com/careers also auto-detects
    assert is_rippling("https://rippling.com/careers")


def test_is_rippling_rejects_non_rippling():
    from backend.scraper.ats.rippling import is_rippling
    assert not is_rippling("https://boards.greenhouse.io/acme")


def test_is_rippling_rejects_path_injection():
    from backend.scraper.ats.rippling import is_rippling
    assert not is_rippling("https://evil.com/?url=rippling.com")


def test_parse_rippling_url_extracts_slug():
    from backend.scraper.ats.rippling import _parse_rippling_url
    url = "https://ats.rippling.com/acme/jobs"
    slug, filters = _parse_rippling_url(url)
    assert slug == "acme"


@pytest.mark.asyncio
async def test_scrape_rippling_handles_http_error(monkeypatch):
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.json = MagicMock(return_value=[])
    mock_resp.raise_for_status = MagicMock(side_effect=Exception("HTTP 500"))

    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    monkeypatch.setattr("httpx.AsyncClient", lambda **kw: mock_client)

    from backend.scraper.ats.rippling import scrape
    result = await scrape("https://ats.rippling.com/acme/jobs")
    jobs = result[0] if isinstance(result, tuple) else result
    assert jobs == []
