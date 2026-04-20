"""Integration test: _cache_job_page refuses SSRF-style URLs (#4)."""
import pytest


@pytest.mark.asyncio
async def test_cache_job_page_rejects_aws_metadata_url(monkeypatch, test_db):
    """URL pointing at 169.254.169.254 must be refused before any fetch,
    and the reason must land in job.cache_error for the UI to surface."""
    from backend.models.db import Job
    job = Job(
        external_id="ssrf-1",
        content_hash="cssrf1",
        company="Acme",
        title="Senior PM",
        url="http://169.254.169.254/latest/meta-data/",
    )
    test_db.add(job)
    test_db.commit()

    from sqlalchemy.orm import sessionmaker
    TestSession = sessionmaker(bind=test_db.get_bind())
    monkeypatch.setattr(
        "backend.api.routes_applications.SessionLocal", TestSession, raising=False,
    )

    # Ensure neither httpx nor Playwright is ever touched
    import httpx as _httpx
    from unittest.mock import MagicMock
    forbidden = MagicMock(
        side_effect=AssertionError("httpx must not be called for unsafe URL"),
    )
    monkeypatch.setattr(_httpx, "AsyncClient", forbidden)

    from backend.api.routes_applications import _cache_job_page
    await _cache_job_page(str(job.id), job.url)

    test_db.expire_all()
    back = test_db.query(Job).filter(Job.id == job.id).first()
    assert back.cached_page_html is None
    assert back.cached_page_text is None
    assert back.cache_error and "unsafe" in back.cache_error.lower()


@pytest.mark.asyncio
async def test_cache_job_page_rejects_private_ip(monkeypatch, test_db):
    """http://10.0.0.5/ must be rejected — protects internal LAN + Tailscale."""
    from backend.models.db import Job
    job = Job(
        external_id="ssrf-2",
        content_hash="cssrf2",
        company="Acme",
        title="PM",
        url="http://10.0.0.5:8000/admin",
    )
    test_db.add(job)
    test_db.commit()

    from sqlalchemy.orm import sessionmaker
    TestSession = sessionmaker(bind=test_db.get_bind())
    monkeypatch.setattr(
        "backend.api.routes_applications.SessionLocal", TestSession, raising=False,
    )

    from backend.api.routes_applications import _cache_job_page
    await _cache_job_page(str(job.id), job.url)

    test_db.expire_all()
    back = test_db.query(Job).filter(Job.id == job.id).first()
    assert back.cache_error and "unsafe" in back.cache_error.lower()
