"""Tests for ats/google.py — detection only (scrape requires real browser)."""
import pytest


def test_is_google_detects_about_careers():
    from backend.scraper.ats.google import is_google
    assert is_google("https://www.google.com/about/careers/applications/jobs/results")


def test_is_google_rejects_non_google():
    from backend.scraper.ats.google import is_google
    assert not is_google("https://boards.greenhouse.io/acme")


def test_is_google_rejects_path_injection():
    from backend.scraper.ats.google import is_google
    # is_google uses a plain substring check, so ?url=google.com/about/careers would false-positive.
    assert not is_google("https://evil.com/?dest=some-other-careers")
