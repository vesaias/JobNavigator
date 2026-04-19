"""Tests for sources/linkedin_personal.py — LinkedIn /jobs/collections/ scraper."""
import pytest


def test_sources_linkedin_personal_exposes_entry_points():
    from backend.scraper.sources import linkedin_personal
    assert hasattr(linkedin_personal, "run")
    assert hasattr(linkedin_personal, "preview")


def test_run_is_async():
    import asyncio
    from backend.scraper.sources import linkedin_personal
    assert asyncio.iscoroutinefunction(linkedin_personal.run)


def test_preview_is_async():
    import asyncio
    from backend.scraper.sources import linkedin_personal
    assert asyncio.iscoroutinefunction(linkedin_personal.preview)
