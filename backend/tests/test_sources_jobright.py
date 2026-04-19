"""Tests for sources/jobright.py."""
import asyncio


def test_sources_jobright_exposes_run_and_preview():
    from backend.scraper.sources import jobright
    assert hasattr(jobright, "run")
    assert hasattr(jobright, "preview")


def test_run_is_async():
    from backend.scraper.sources import jobright
    assert asyncio.iscoroutinefunction(jobright.run)


def test_preview_is_async():
    from backend.scraper.sources import jobright
    assert asyncio.iscoroutinefunction(jobright.preview)
