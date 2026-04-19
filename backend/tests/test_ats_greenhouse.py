"""Tests for ats/greenhouse.py — detection + API mock."""
import pytest
from unittest.mock import AsyncMock, MagicMock


def test_is_greenhouse_detects_boards():
    from backend.scraper.ats.greenhouse import is_greenhouse
    assert is_greenhouse("https://boards.greenhouse.io/acme")


def test_is_greenhouse_detects_job_boards():
    from backend.scraper.ats.greenhouse import is_greenhouse
    # job-boards.greenhouse.io is another Greenhouse subdomain
    assert is_greenhouse("https://job-boards.greenhouse.io/acme")


def test_is_greenhouse_rejects_non_greenhouse():
    from backend.scraper.ats.greenhouse import is_greenhouse
    assert not is_greenhouse("https://nvidia.wd5.myworkdayjobs.com/Site")
    assert not is_greenhouse("https://jobs.lever.co/acme")


def test_is_greenhouse_rejects_path_injection():
    from backend.scraper.ats.greenhouse import is_greenhouse
    assert not is_greenhouse("https://attacker.com/?url=greenhouse.io")


def test_parse_greenhouse_url_extracts_slug():
    from backend.scraper.ats.greenhouse import _parse_greenhouse_url
    slug, dept_ids, office_ids = _parse_greenhouse_url("https://boards.greenhouse.io/acme")
    assert slug == "acme"
    assert dept_ids == set()
    assert office_ids == set()


def test_parse_greenhouse_url_extracts_filters():
    from backend.scraper.ats.greenhouse import _parse_greenhouse_url
    url = "https://boards.greenhouse.io/acme?departments[]=1&offices[]=2"
    slug, dept_ids, office_ids = _parse_greenhouse_url(url)
    assert slug == "acme"
    assert 1 in dept_ids
    assert 2 in office_ids


@pytest.mark.asyncio
async def test_scrape_greenhouse_returns_parsed_jobs(monkeypatch):
    """scrape() GETs boards-api.greenhouse.io/v1/boards/{slug}/jobs and parses."""
    api_response_body = {
        "jobs": [
            {
                "id": 123,
                "title": "Senior Product Manager",
                "location": {"name": "San Francisco"},
                "departments": [{"id": 1, "name": "Product", "parent_id": None, "child_ids": []}],
                "offices": [{"id": 1, "name": "SF HQ", "parent_id": None, "child_ids": []}],
                "absolute_url": "https://boards.greenhouse.io/acme/jobs/123",
                "content": "<p>Description HTML</p>",
            },
        ],
    }
    mock_resp = MagicMock()
    mock_resp.json = MagicMock(return_value=api_response_body)
    mock_resp.text = '{"jobs": [{"id": 123, "title": "Senior Product Manager", "location": {"name": "San Francisco"}, "departments": [{"id": 1, "name": "Product", "parent_id": null, "child_ids": []}], "offices": [{"id": 1, "name": "SF HQ", "parent_id": null, "child_ids": []}], "absolute_url": "https://boards.greenhouse.io/acme/jobs/123", "content": "<p>Description HTML</p>"}]}'
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    monkeypatch.setattr("httpx.AsyncClient", lambda **kw: mock_client)

    from backend.scraper.ats.greenhouse import scrape
    result = await scrape("https://boards.greenhouse.io/acme")
    jobs = result[0] if isinstance(result, tuple) else result
    assert isinstance(jobs, list)
    assert len(jobs) >= 1
    assert jobs[0]["title"] == "Senior Product Manager"


@pytest.mark.asyncio
async def test_scrape_greenhouse_handles_http_error(monkeypatch):
    """scrape() returns empty on HTTP error, doesn't raise."""
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.json = MagicMock(return_value={})
    mock_resp.text = "{}"

    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    monkeypatch.setattr("httpx.AsyncClient", lambda **kw: mock_client)

    from backend.scraper.ats.greenhouse import scrape
    result = await scrape("https://boards.greenhouse.io/acme")
    jobs = result[0] if isinstance(result, tuple) else result
    assert jobs == []
