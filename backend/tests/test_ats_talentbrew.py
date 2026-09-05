"""Tests for ats/talentbrew.py — detection."""
import pytest


def test_is_talentbrew_positive():
    """Checks for the '/search-jobs/results?' substring (case-insensitive); used by BlackRock, Intuit, and other TalentBrew career pages."""
    from backend.scraper.ats.talentbrew import is_talentbrew
    assert is_talentbrew("https://careers.blackrock.com/search-jobs/results?keywords=engineer")


def test_is_talentbrew_rejects_non_talentbrew():
    from backend.scraper.ats.talentbrew import is_talentbrew
    assert not is_talentbrew("https://boards.greenhouse.io/acme")


def test_is_talentbrew_rejects_empty():
    from backend.scraper.ats.talentbrew import is_talentbrew
    assert not is_talentbrew("")
