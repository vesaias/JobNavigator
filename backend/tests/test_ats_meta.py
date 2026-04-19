"""Tests for ats/meta.py — detection only (scrape requires real browser)."""
import pytest


def test_is_meta_detects_metacareers():
    from backend.scraper.ats.meta import is_meta
    assert is_meta("https://metacareers.com/jobs/")


def test_is_meta_detects_subdomain():
    from backend.scraper.ats.meta import is_meta
    assert is_meta("https://www.metacareers.com/jobs/12345")


def test_is_meta_rejects_non_meta():
    from backend.scraper.ats.meta import is_meta
    assert not is_meta("https://boards.greenhouse.io/acme")


def test_is_meta_rejects_path_injection():
    from backend.scraper.ats.meta import is_meta
    assert not is_meta("https://evil.com/?url=metacareers.com")
