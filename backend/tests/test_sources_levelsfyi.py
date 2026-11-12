"""Tests for sources/levelsfyi.py."""
import asyncio

import pytest


def test_exposes_run_and_scrape():
    from backend.scraper.sources import levelsfyi
    assert hasattr(levelsfyi, "run")
    # _scrape_levelsfyi is used externally by routes_searches.py:409 — keep as-is
    assert hasattr(levelsfyi, "_scrape_levelsfyi")


def test_run_is_async():
    from backend.scraper.sources import levelsfyi
    assert asyncio.iscoroutinefunction(levelsfyi.run)


def test_is_levelsfyi_detects_levels():
    from backend.scraper.sources.levelsfyi import _is_levelsfyi
    assert _is_levelsfyi("https://www.levels.fyi/jobs")


def test_is_levelsfyi_rejects_non_levels():
    from backend.scraper.sources.levelsfyi import _is_levelsfyi
    assert not _is_levelsfyi("https://boards.greenhouse.io/acme")


def test_levelsfyi_job_id_keeps_the_whole_alphanumeric_id():
    """Since 2026-10-09 levels.fyi ids are base-36 ("2ci7r6weraiqb"); reading only the leading
    digits stored "jobId=2", a 404 page that scoring could never parse."""
    from backend.scraper.sources.levelsfyi import _levelsfyi_job_id
    assert _levelsfyi_job_id("/jobs?jobId=2ci7r6weraiqb") == "2ci7r6weraiqb"
    assert _levelsfyi_job_id("/jobs?jobId=0748ffyywjm40&utm=x") == "0748ffyywjm40"
    assert _levelsfyi_job_id("https://www.levels.fyi/jobs?jobId=113365928120328902") == "113365928120328902"
    assert _levelsfyi_job_id("/jobs?standardJobId=abc") is None
    assert _levelsfyi_job_id("/jobs?jobId=") is None


def test_parse_levelsfyi_salary_parses_range():
    from backend.scraper.sources.levelsfyi import _parse_levelsfyi_salary
    # Return shape: (location, work_arrangement, salary_min, salary_max)
    result = _parse_levelsfyi_salary("San Francisco \u00b7 Remote \u00b7 $100K - $150K")
    assert isinstance(result, tuple)
    assert len(result) == 4
    location, work_arrangement, salary_min, salary_max = result
    assert location == "San Francisco"
    assert work_arrangement == "Remote"
    assert salary_min == 100000
    assert salary_max == 150000


@pytest.mark.parametrize("url, expected", [
    ("https://www.levels.fyi/jobs/location/vancouver-can?locationSlug=canada&searchText=sre"
     "&standardLevels=mid_staff%2Cprincipal%2Cmanager&jobId=130827934242874054",
     "https://www.levels.fyi/jobs/location/vancouver-can?locationSlug=canada&searchText=sre"
     "&standardLevels=mid_staff%2Cprincipal%2Cmanager"),
    ("https://www.levels.fyi/jobs?jobId=3bzayjo8smjym", "https://www.levels.fyi/jobs"),
    ("https://www.levels.fyi/jobs?searchText=sre", "https://www.levels.fyi/jobs?searchText=sre"),
])
def test_listing_url_drops_the_job_id(url, expected):
    """A stale jobId in the saved URL made Levels.fyi answer 404: 0 jobs for 6 weeks."""
    from backend.scraper.sources.levelsfyi import _listing_url
    assert _listing_url(url) == expected


@pytest.mark.parametrize("status, title, refused", [
    (200, "735 Jobs in Vancouver (November 2026) | Levels.fyi", False),
    (None, "Browse Jobs | Levels.fyi", False),
    (404, "Levels.fyi - 404 Page Not Found", True),
    (202, "Let's confirm you are human", True),
])
def test_check_listing_raises_when_the_page_is_not_a_listing(status, title, refused):
    from backend.scraper.sources import levelsfyi
    if refused:
        with pytest.raises(levelsfyi.LevelsFyiRefusedError):
            levelsfyi._check_listing(status, title)
    else:
        levelsfyi._check_listing(status, title)


@pytest.mark.asyncio
async def test_a_refused_listing_is_an_error_and_not_zero_jobs():
    """The scraper logs other errors and returns []; a refusal must reach the run result."""
    from backend.scraper.sources import levelsfyi

    class _Response:
        status = 404

    class _Page:
        opened = None

        async def goto(self, url, **_kw):
            _Page.opened = url
            return _Response()

        async def title(self):
            return "Levels.fyi - 404 Page Not Found"

        async def close(self):
            return None

    class _Context:
        async def close(self):
            return None

    class _Browser:
        async def new_context(self, **_kw):
            return _Context()

    import unittest.mock as mock
    with mock.patch.object(levelsfyi, "_new_page", mock.AsyncMock(return_value=_Page())),             mock.patch.object(levelsfyi, "_close_page", mock.AsyncMock()):
        with pytest.raises(levelsfyi.LevelsFyiRefusedError, match="HTTP 404"):
            await levelsfyi._scrape_levelsfyi("https://www.levels.fyi/jobs?searchText=sre&jobId=1", browser=_Browser())
    assert _Page.opened == "https://www.levels.fyi/jobs?searchText=sre"
