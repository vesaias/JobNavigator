"""R2-H-02: a manual company scrape must write the same ScrapeLog row as the batch.

Only the batch path (scrape_career_pages) used to build the ScrapeLog row, so
POST /api/scrape/company/{id} left no audit trail — /api/scrape-log, is_warning
and /health/entities never saw manual runs. Both paths now call
record_company_scrape_log().
"""
import asyncio

import pytest

from backend.models.db import Company, ScrapeLog


def test_record_company_scrape_log_writes_row(test_db):
    from backend.scraper.sources.company_pages import record_company_scrape_log

    c = Company(name="Acme", active=True, playwright_enabled=True,
                scrape_urls=["https://jobs.lever.co/acme"])
    test_db.add(c)
    test_db.commit()

    record_company_scrape_log(
        c.id, c.name,
        {"jobs_found": 7, "new_jobs": 3, "error": None, "duration": 1.25},
        db=test_db,
    )

    row = test_db.query(ScrapeLog).one()
    assert row.company_id == c.id
    assert row.source == "playwright_Acme"
    assert row.jobs_found == 7
    assert row.new_jobs == 3
    assert row.is_warning is False
    assert row.error is None
    assert row.duration_seconds == pytest.approx(1.25)


def test_record_company_scrape_log_flags_empty_run_as_warning(test_db):
    from backend.scraper.sources.company_pages import record_company_scrape_log

    c = Company(name="Empty Co", active=True, playwright_enabled=True, scrape_urls=[])
    test_db.add(c)
    test_db.commit()

    record_company_scrape_log(c.id, c.name, {"jobs_found": 0, "new_jobs": 0}, db=test_db)
    record_company_scrape_log(
        c.id, c.name,
        {"jobs_found": 0, "new_jobs": 0, "error": "boom"},
        db=test_db,
    )

    # ScrapeLog.id is a UUID, so order by content rather than insertion order.
    rows = test_db.query(ScrapeLog).all()
    assert len(rows) == 2
    clean = [r for r in rows if not r.error]
    failed = [r for r in rows if r.error]
    assert [r.is_warning for r in clean] == [True]
    assert [r.is_warning for r in failed] == [False]
    assert failed[0].error == "boom"


def test_record_company_scrape_log_opens_own_session(test_db):
    """No db= passed: the helper opens/closes its own SessionLocal."""
    from backend.scraper.sources.company_pages import record_company_scrape_log

    c = Company(name="Solo", active=True, playwright_enabled=True, scrape_urls=[])
    test_db.add(c)
    test_db.commit()

    record_company_scrape_log(c.id, c.name, {"jobs_found": 2, "new_jobs": 1, "duration": 0.5})

    row = test_db.query(ScrapeLog).one()
    assert row.company_id == c.id and row.new_jobs == 1


@pytest.mark.asyncio
async def test_manual_company_trigger_writes_scrape_log(test_db, monkeypatch):
    """POST /api/scrape/company/{id} background worker writes the audit row.

    Needs the container (imports backend.main → apscheduler).
    """
    pytest.importorskip("apscheduler")
    import backend.main as main_mod
    import backend.scraper.sources.company_pages as cp

    c = Company(name="Manual Co", active=True, playwright_enabled=True,
                scrape_urls=["https://jobs.lever.co/manual"], auto_scoring_depth="off")
    test_db.add(c)
    test_db.commit()
    company_id = str(c.id)

    async def fake_scrape(company, **kw):
        return {"jobs_found": 0, "new_jobs": 0, "error": None, "duration": 0.4}

    monkeypatch.setattr(cp, "scrape_single_career_page", fake_scrape)

    resp = await main_mod.trigger_company_scrape(company_id)
    assert resp["status"] == "running"

    # Let the background task finish.
    import backend.job_monitor as jm
    for _ in range(100):
        if not jm._running:
            break
        await asyncio.sleep(0.02)

    row = test_db.query(ScrapeLog).filter(ScrapeLog.company_id == c.id).one()
    assert row.source == "playwright_Manual Co"
    assert row.jobs_found == 0 and row.new_jobs == 0
    assert row.is_warning is True
