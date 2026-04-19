"""Tests for sources/linkedin_extension.py — Voyager-API enrichment."""
import pytest
import asyncio


def test_exposes_enrich():
    from backend.scraper.sources import linkedin_extension
    assert hasattr(linkedin_extension, "enrich")


def test_enrich_is_async():
    from backend.scraper.sources import linkedin_extension
    assert asyncio.iscoroutinefunction(linkedin_extension.enrich)


@pytest.mark.asyncio
async def test_enrich_handles_empty_list():
    """Passing [] returns without raising and without any API calls."""
    from backend.scraper.sources.linkedin_extension import enrich
    result = await enrich([])
    # Result may be a dict with counts, or None — just verify no raise
    assert result is None or isinstance(result, dict)
