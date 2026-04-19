"""Tests for ats/workday.py — detection + API mock."""
import pytest
from unittest.mock import AsyncMock, MagicMock


def test_is_workday_detects_myworkdayjobs():
    from backend.scraper.ats.workday import is_workday
    assert is_workday("https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite")


def test_is_workday_detects_locale_prefix():
    from backend.scraper.ats.workday import is_workday
    assert is_workday("https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite")


def test_is_workday_rejects_non_workday():
    from backend.scraper.ats.workday import is_workday
    assert not is_workday("https://boards.greenhouse.io/acme")
    assert not is_workday("https://jobs.lever.co/acme")
    assert not is_workday("https://example.com/careers")


def test_is_workday_rejects_path_injection():
    from backend.scraper.ats.workday import is_workday
    assert not is_workday("https://evil.com/?x=myworkdayjobs.com")


def test_parse_workday_url_extracts_components():
    from backend.scraper.ats.workday import _parse_workday_url
    url = "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite"
    origin, company, site, facets = _parse_workday_url(url)
    assert origin == "https://nvidia.wd5.myworkdayjobs.com"
    assert company == "nvidia"
    assert site == "NVIDIAExternalCareerSite"
    assert facets == {}


def test_parse_workday_url_skips_locale_prefix():
    from backend.scraper.ats.workday import _parse_workday_url
    url = "https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite"
    origin, company, site, facets = _parse_workday_url(url)
    assert site == "NVIDIAExternalCareerSite"  # NOT "en-US"


def test_parse_workday_url_captures_facets():
    from backend.scraper.ats.workday import _parse_workday_url
    url = "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite?locations=abc123&timeType=def456"
    origin, company, site, facets = _parse_workday_url(url)
    assert "locations" in facets
    assert "timeType" in facets


@pytest.mark.asyncio
async def test_scrape_workday_calls_api(monkeypatch):
    """scrape() POSTs to /wday/cxs/{company}/{site}/jobs and parses jobPostings."""
    api_response_body = (
        '{"total": 2, "jobPostings": ['
        '{"title": "Senior Product Manager", "externalPath": "/job/123", "locationsText": "San Francisco"},'
        '{"title": "Staff Software Engineer", "externalPath": "/job/456", "locationsText": "Remote"}'
        ']}'
    )

    mock_resp = MagicMock()
    mock_resp.text = api_response_body
    mock_resp.status_code = 200

    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    monkeypatch.setattr("httpx.AsyncClient", lambda **kw: mock_client)

    from backend.scraper.ats.workday import scrape
    jobs = await scrape("https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite")

    assert isinstance(jobs, list)
    assert len(jobs) == 2
    assert jobs[0]["title"] == "Senior Product Manager"
    assert "url" in jobs[0]
    assert "/job/123" in jobs[0]["url"]


@pytest.mark.asyncio
async def test_scrape_workday_handles_http_error(monkeypatch):
    """scrape() returns empty list on HTTP error, doesn't raise."""
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = ""

    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    monkeypatch.setattr("httpx.AsyncClient", lambda **kw: mock_client)

    from backend.scraper.ats.workday import scrape
    jobs = await scrape("https://nvidia.wd5.myworkdayjobs.com/Site")
    assert jobs == []


@pytest.mark.asyncio
async def test_scrape_workday_bad_url(monkeypatch):
    """scrape() returns empty for unparseable URL."""
    from backend.scraper.ats.workday import scrape
    # URL with no site segment
    jobs = await scrape("https://nvidia.wd5.myworkdayjobs.com/")
    assert jobs == []
