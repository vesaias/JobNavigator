"""Tests for sources/jobspy.py — JobSpy multi-board keyword scrape entry point."""
import pytest
from unittest.mock import AsyncMock, MagicMock


def test_sources_jobspy_exposes_run():
    """Module has a `run` function as its public entry point."""
    from backend.scraper.sources import jobspy
    assert hasattr(jobspy, "run")


@pytest.mark.asyncio
async def test_run_handles_empty_sources():
    """Search with no `sources` configured returns an error dict without raising."""
    from backend.scraper.sources.jobspy import run

    class FakeSearch:
        id = "s-1"
        name = "Empty Search"
        sources = []
        title_include_keywords = []
        title_exclude_keywords = []
        company_exclude = []
        location = None
        distance = None
        max_results = 50
        hours_old = 168
        require_salary = False

    # Should not raise; may return an empty/error result dict
    result = await run(FakeSearch())
    assert isinstance(result, dict)
    # Common keys in the result
    assert "jobs_found" in result or "error" in result
