"""Tests for ats/phenom.py — detection + POST API format parsing."""
import pytest


def test_is_phenom_detects_post_format():
    """Phenom URLs are formatted as 'POST|api_url|json_payload' strings."""
    from backend.scraper.ats.phenom import is_phenom
    # Must read original _is_phenom_post logic — likely checks string starts with "POST|"
    assert is_phenom('POST|https://jobs.example.com/api/search|{"query":"..."}')


def test_is_phenom_rejects_plain_url():
    from backend.scraper.ats.phenom import is_phenom
    assert not is_phenom("https://jobs.example.com/careers")


def test_is_phenom_rejects_empty():
    from backend.scraper.ats.phenom import is_phenom
    assert not is_phenom("")


def test_parse_phenom_url_extracts_api_and_payload():
    from backend.scraper.ats.phenom import _parse_phenom_url
    raw = 'POST|https://jobs.example.com/api/search|{"query":"software"}'
    api_url, payload = _parse_phenom_url(raw)
    assert "jobs.example.com" in api_url
    assert isinstance(payload, dict)
    assert payload.get("query") == "software"
