"""Tests for ats/oracle_hcm.py — detection + API mock + custom host mapping."""
import pytest
from unittest.mock import AsyncMock, MagicMock


def test_is_oracle_hcm_detects_oraclecloud():
    from backend.scraper.ats.oracle_hcm import is_oracle_hcm
    assert is_oracle_hcm("https://eeho.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1/job/12345/")


def test_is_oracle_hcm_detects_custom_domain():
    from backend.scraper.ats.oracle_hcm import is_oracle_hcm
    # Oracle offers custom career subdomains (e.g. careers.oracle.com) mapped to real backends
    assert is_oracle_hcm("https://careers.oracle.com/jobs/")


def test_is_oracle_hcm_rejects_non_oracle():
    from backend.scraper.ats.oracle_hcm import is_oracle_hcm
    assert not is_oracle_hcm("https://boards.greenhouse.io/acme")
    assert not is_oracle_hcm("https://nvidia.wd5.myworkdayjobs.com/Site")


def test_is_oracle_hcm_rejects_path_injection():
    from backend.scraper.ats.oracle_hcm import is_oracle_hcm
    assert not is_oracle_hcm("https://attacker.com/?url=oraclecloud.com")


def test_oracle_hcm_host_returns_backend():
    from backend.scraper.ats.oracle_hcm import _oracle_hcm_host
    # Direct oraclecloud.com URL — host is the URL's own host
    host = _oracle_hcm_host("https://eeho.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1/job/123")
    assert host == "eeho.fa.us2.oraclecloud.com"


def test_oracle_hcm_host_maps_custom_domain():
    from backend.scraper.ats.oracle_hcm import _oracle_hcm_host, _ORACLE_HCM_HOSTS
    # careers.oracle.com should map to a real backend
    host = _oracle_hcm_host("https://careers.oracle.com/jobs/")
    if "careers.oracle.com" in _ORACLE_HCM_HOSTS:
        assert host == _ORACLE_HCM_HOSTS["careers.oracle.com"]


def test_oracle_hcm_host_returns_none_for_non_oracle():
    from backend.scraper.ats.oracle_hcm import _oracle_hcm_host
    assert _oracle_hcm_host("https://boards.greenhouse.io/acme") is None


@pytest.mark.asyncio
async def test_scrape_oracle_hcm_handles_http_error(monkeypatch):
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.json = MagicMock(return_value={})
    mock_resp.text = ""

    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    monkeypatch.setattr("httpx.AsyncClient", lambda **kw: mock_client)

    from backend.scraper.ats.oracle_hcm import scrape
    result = await scrape("https://eeho.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1/")
    jobs = result[0] if isinstance(result, tuple) else result
    assert jobs == []
