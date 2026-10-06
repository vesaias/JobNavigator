"""Tests for _shared/analysis.py — inline-analysis wrapper."""
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_analyze_inline_calls_both_h1b_and_salary(monkeypatch):
    """analyze_inline(job) calls both check_job_h1b and apply_salary_to_job."""
    called = {}

    async def fake_h1b(job, db=None):
        called["h1b"] = getattr(job, "id", None)

    def fake_salary(job, h1b_median=None):
        called["salary"] = getattr(job, "id", None)

    monkeypatch.setattr("backend.scraper._shared.analysis.check_job_h1b", fake_h1b)
    monkeypatch.setattr("backend.scraper._shared.analysis.apply_salary_to_job", fake_salary)

    from backend.scraper._shared.analysis import analyze_inline

    class FakeJob:
        id = "job-1"
        description = "software engineer role"
        company = "Acme"

    await analyze_inline(FakeJob())
    assert called.get("h1b") == "job-1"
    assert called.get("salary") == "job-1"


@pytest.mark.asyncio
async def test_analyze_inline_tolerates_h1b_exception(monkeypatch):
    """If h1b raises, salary still runs and analyze_inline doesn't bubble up."""
    salary_called = []

    async def broken_h1b(job, db=None):
        raise RuntimeError("h1b boom")

    def ok_salary(job, h1b_median=None):
        salary_called.append(True)

    monkeypatch.setattr("backend.scraper._shared.analysis.check_job_h1b", broken_h1b)
    monkeypatch.setattr("backend.scraper._shared.analysis.apply_salary_to_job", ok_salary)

    from backend.scraper._shared.analysis import analyze_inline

    class FakeJob:
        id = "job-1"
    # Must not raise
    await analyze_inline(FakeJob())
    # Salary still ran despite h1b failure
    assert salary_called == [True]


@pytest.mark.asyncio
async def test_analyze_inline_tolerates_salary_exception(monkeypatch):
    """If salary raises, analyze_inline doesn't bubble up."""
    async def ok_h1b(job, db=None):
        pass

    def broken_salary(job, h1b_median=None):
        raise RuntimeError("salary broken")

    monkeypatch.setattr("backend.scraper._shared.analysis.check_job_h1b", ok_h1b)
    monkeypatch.setattr("backend.scraper._shared.analysis.apply_salary_to_job", broken_salary)

    from backend.scraper._shared.analysis import analyze_inline

    class FakeJob:
        id = "job-1"
    # Must not raise
    await analyze_inline(FakeJob())


@pytest.mark.asyncio
async def test_analyze_inline_forwards_db_and_h1b_median(monkeypatch):
    """db and h1b_median args are forwarded to the callees."""
    captured = {}

    async def fake_h1b(job, db=None):
        captured["h1b_db"] = db

    def fake_salary(job, h1b_median=None):
        captured["salary_median"] = h1b_median

    monkeypatch.setattr("backend.scraper._shared.analysis.check_job_h1b", fake_h1b)
    monkeypatch.setattr("backend.scraper._shared.analysis.apply_salary_to_job", fake_salary)

    from backend.scraper._shared.analysis import analyze_inline

    class FakeJob:
        id = "job-1"

    fake_db = MagicMock()
    await analyze_inline(FakeJob(), db=fake_db, h1b_median=120000)
    assert captured["h1b_db"] is fake_db
    assert captured["salary_median"] == 120000


@pytest.mark.asyncio
async def test_analyze_inline_extracts_salary_with_the_real_extractor(monkeypatch):
    """No fake salary function here: a fake with the wrong keyword is how a TypeError hid in this call."""
    async def no_h1b(job, db=None):
        job._h1b_median = None
    monkeypatch.setattr("backend.scraper._shared.analysis.check_job_h1b", no_h1b)

    from backend.scraper._shared.analysis import analyze_inline
    from backend.models.db import Job

    job = Job(title="Site Reliability Engineer", company="Acme", location="Vancouver, BC",
              description="Pay: $120,000 - $150,000 a year. Hybrid.")
    await analyze_inline(job, h1b_median=None)
    assert (job.salary_min, job.salary_max, job.salary_source) == (120000, 150000, "posting")

    lca = Job(title="Engineer", company="Acme", description="No pay listed.")
    await analyze_inline(lca, h1b_median=99000)
    assert (lca.salary_min, lca.salary_source) == (99000, "lca_estimate")
