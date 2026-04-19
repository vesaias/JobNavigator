"""Tests for ats/talentbrew.py — detection."""
import pytest


def test_is_talentbrew_positive():
    """Original _is_talentbrew_ajax checks for '/search-jobs/results?' substring
    in the URL (case-insensitive). Used by BlackRock, Intuit, and other legacy
    TalentBrew-hosted career pages.
    """
    from backend.scraper.ats.talentbrew import is_talentbrew
    assert is_talentbrew("https://careers.blackrock.com/search-jobs/results?keywords=engineer")


def test_is_talentbrew_rejects_non_talentbrew():
    from backend.scraper.ats.talentbrew import is_talentbrew
    assert not is_talentbrew("https://boards.greenhouse.io/acme")


def test_is_talentbrew_rejects_empty():
    from backend.scraper.ats.talentbrew import is_talentbrew
    assert not is_talentbrew("")
