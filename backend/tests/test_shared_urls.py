"""Tests for _shared/urls.py — URL helpers."""
import pytest


def test_host_matches_exact():
    from backend.scraper._shared.urls import host_matches
    assert host_matches("https://metacareers.com/jobs/123", "metacareers.com")


def test_host_matches_subdomain():
    from backend.scraper._shared.urls import host_matches
    assert host_matches("https://www.metacareers.com/jobs/123", "metacareers.com")


def test_host_matches_blocks_lookalike():
    from backend.scraper._shared.urls import host_matches
    assert not host_matches("https://evil-metacareers.com/", "metacareers.com")


def test_host_matches_blocks_path_injection():
    from backend.scraper._shared.urls import host_matches
    assert not host_matches("https://attacker.com/?url=metacareers.com", "metacareers.com")


def test_host_matches_multiple_domains():
    from backend.scraper._shared.urls import host_matches
    assert host_matches("https://boards.greenhouse.io/acme", "greenhouse.io", "boards.greenhouse.io")


def test_host_matches_invalid_url():
    from backend.scraper._shared.urls import host_matches
    assert not host_matches("not-a-url", "anything.com")


def test_host_matches_trailing_slash_in_domain():
    from backend.scraper._shared.urls import host_matches
    assert host_matches("https://metacareers.com/", "metacareers.com/")


def test_host_matches_empty_url():
    from backend.scraper._shared.urls import host_matches
    assert not host_matches("", "anything.com")


def test_path_contains_simple():
    from backend.scraper._shared.urls import path_contains
    assert path_contains("https://example.com/jobs/view/123", "/jobs/")


def test_path_contains_case_insensitive():
    from backend.scraper._shared.urls import path_contains
    assert path_contains("https://example.com/Careers", "/careers")


def test_path_contains_no_match():
    from backend.scraper._shared.urls import path_contains
    assert not path_contains("https://example.com/about", "/jobs")


def test_clean_application_url_strips_utm(monkeypatch):
    # Stub the setting getter to return a known tracking set
    monkeypatch.setattr(
        "backend.scraper._shared.urls._get_url_tracking_params",
        lambda: {"utm_source", "utm_campaign", "utm_medium"}
    )
    from backend.scraper._shared.urls import _clean_application_url
    url = "https://company.com/jobs/123?utm_source=linkedin&utm_campaign=x&gh_jid=456"
    result = _clean_application_url(url)
    assert "utm_source" not in result
    assert "utm_campaign" not in result
    assert "gh_jid=456" in result  # functional param preserved
