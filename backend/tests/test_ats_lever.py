"""Tests for ats/lever.py — detection + API mock."""
import pytest
from unittest.mock import AsyncMock, MagicMock


def test_is_lever_detects_jobs_lever_co():
    from backend.scraper.ats.lever import is_lever
    assert is_lever("https://jobs.lever.co/acme")


def test_is_lever_detects_with_path():
    from backend.scraper.ats.lever import is_lever
    assert is_lever("https://jobs.lever.co/acme/team/engineering")


def test_is_lever_rejects_non_lever():
    from backend.scraper.ats.lever import is_lever
    assert not is_lever("https://boards.greenhouse.io/acme")
    assert not is_lever("https://nvidia.wd5.myworkdayjobs.com/Site")


def test_is_lever_rejects_path_injection():
    from backend.scraper.ats.lever import is_lever
    assert not is_lever("https://attacker.com/?url=lever.co")


@pytest.mark.asyncio
async def test_scrape_lever_parses_api(monkeypatch):
    """scrape() GETs api.lever.co/v0/postings/{company} and parses postings."""
    api_response_body = [
        {
            "id": "abc123",
            "text": "Senior Product Manager",
            "hostedUrl": "https://jobs.lever.co/acme/abc123",
            "categories": {"location": "San Francisco", "team": "Product"},
            "descriptionPlain": "Job description here...",
        },
        {
            "id": "def456",
            "text": "Staff Software Engineer",
            "hostedUrl": "https://jobs.lever.co/acme/def456",
            "categories": {"location": "Remote", "team": "Engineering"},
            "descriptionPlain": "Engineering role...",
        },
    ]
    import json as _json
    mock_resp = MagicMock()
    mock_resp.json = MagicMock(return_value=api_response_body)
    mock_resp.text = _json.dumps(api_response_body)
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    monkeypatch.setattr("httpx.AsyncClient", lambda **kw: mock_client)

    from backend.scraper.ats.lever import scrape
    result = await scrape("https://jobs.lever.co/acme")
    jobs = result[0] if isinstance(result, tuple) else result
    assert isinstance(jobs, list)
    assert len(jobs) >= 1
    assert any("Senior Product Manager" in j["title"] for j in jobs)


@pytest.mark.asyncio
async def test_scrape_lever_handles_http_error(monkeypatch):
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.json = MagicMock(return_value=[])
    mock_resp.text = "[]"

    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    monkeypatch.setattr("httpx.AsyncClient", lambda **kw: mock_client)

    from backend.scraper.ats.lever import scrape
    result = await scrape("https://jobs.lever.co/acme")
    jobs = result[0] if isinstance(result, tuple) else result
    assert jobs == []
