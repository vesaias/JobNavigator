"""Tailoring JD resolution order, quality-first: description → live fetch (persisted) → cached page → none."""
import asyncio
from unittest.mock import MagicMock


def _job(description=None, url=None, cached=None):
    j = MagicMock()
    j.description = description
    j.url = url
    j.cached_page_text = cached
    return j


def test_description_used_first_no_fetch(monkeypatch):
    from backend.api.routes_resumes import _resolve_tailoring_jd
    calls = {"n": 0}

    async def fake_fetch(url):
        calls["n"] += 1
        return "SHOULD NOT BE USED"

    monkeypatch.setattr("backend.scraper.ats._descriptions._fetch_job_description", fake_fetch)
    job = _job(description="Clean stored JD", url="https://x.com/j", cached="noise")
    db = MagicMock()
    out = asyncio.run(_resolve_tailoring_jd(job, db))
    assert out == "Clean stored JD"
    assert calls["n"] == 0
    db.commit.assert_not_called()


def test_live_fetch_preferred_over_cached_and_persisted(monkeypatch):
    """description empty → live fetch wins over cached page text, and is persisted."""
    from backend.api.routes_resumes import _resolve_tailoring_jd

    async def fake_fetch(url):
        return "Freshly fetched clean JD"

    monkeypatch.setattr("backend.scraper.ats._descriptions._fetch_job_description", fake_fetch)
    job = _job(description="", url="https://x.com/j", cached="noisy cached page text")
    db = MagicMock()
    out = asyncio.run(_resolve_tailoring_jd(job, db))
    assert out == "Freshly fetched clean JD"
    assert job.description == "Freshly fetched clean JD"  # persisted back
    db.commit.assert_called_once()


def test_cached_fallback_when_fetch_fails_not_persisted(monkeypatch):
    from backend.api.routes_resumes import _resolve_tailoring_jd

    async def fake_fetch(url):
        return None

    monkeypatch.setattr("backend.scraper.ats._descriptions._fetch_job_description", fake_fetch)
    job = _job(description="", url="https://x.com/j", cached="noisy cached page text")
    db = MagicMock()
    out = asyncio.run(_resolve_tailoring_jd(job, db))
    assert out == "noisy cached page text"
    assert job.description == ""  # noisy text must NOT be persisted as the description
    db.commit.assert_not_called()


def test_no_url_skips_fetch_uses_cached(monkeypatch):
    from backend.api.routes_resumes import _resolve_tailoring_jd
    calls = {"n": 0}

    async def fake_fetch(url):
        calls["n"] += 1
        return "x"

    monkeypatch.setattr("backend.scraper.ats._descriptions._fetch_job_description", fake_fetch)
    job = _job(description="", url=None, cached="cached only")
    out = asyncio.run(_resolve_tailoring_jd(job, MagicMock()))
    assert out == "cached only"
    assert calls["n"] == 0


def test_all_empty_returns_empty(monkeypatch):
    from backend.api.routes_resumes import _resolve_tailoring_jd

    async def fake_fetch(url):
        return None

    monkeypatch.setattr("backend.scraper.ats._descriptions._fetch_job_description", fake_fetch)
    job = _job(description="", url=None, cached=None)
    out = asyncio.run(_resolve_tailoring_jd(job, MagicMock()))
    assert out == ""
