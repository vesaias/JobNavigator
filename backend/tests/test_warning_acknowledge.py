"""Acknowledging a scrape warning, and keeping switched-off entities (paused searches, inactive companies) out of the rail health dot and attention counts."""
from datetime import datetime, timezone, timedelta

import pytest
from fastapi import HTTPException

from backend.api.routes_companies import acknowledge_company_warning
from backend.api.routes_searches import acknowledge_search_warning
from backend.models.db import Company, Search, ScrapeLog, is_acknowledged

MISSING_ID = "d4dddddd-ddd4-4dd4-8ddd-dddddddddddd"


def _now():
    return datetime.now(timezone.utc)


# ── POST /api/companies/{id}/acknowledge ─────────────────────────────────────

def test_acknowledge_company_stamps_now(test_db):
    c = Company(name="AckEndpointCo", active=True)
    test_db.add(c)
    test_db.commit()

    before = _now()
    out = acknowledge_company_warning(str(c.id), db=test_db)

    assert out["name"] == "AckEndpointCo"
    assert out["warning_acknowledged_at"]
    stamp = c.warning_acknowledged_at
    assert stamp is not None
    # SQLite drops the offset on read-back, so normalise before comparing
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    assert before - timedelta(seconds=5) <= stamp <= _now() + timedelta(seconds=5)


def test_acknowledge_company_404_on_unknown_id(test_db):
    with pytest.raises(HTTPException) as e:
        acknowledge_company_warning(MISSING_ID, db=test_db)
    assert e.value.status_code == 404


# ── POST /api/searches/{id}/acknowledge ──────────────────────────────────────

def test_acknowledge_search_stamps_now(test_db):
    s = Search(name="AckEndpointSearch", search_mode="keyword", active=True)
    test_db.add(s)
    test_db.commit()

    out = acknowledge_search_warning(str(s.id), db=test_db)

    assert out["name"] == "AckEndpointSearch"
    assert s.warning_acknowledged_at is not None
    assert out["warning_acknowledged_at"] == s.warning_acknowledged_at.isoformat()


def test_acknowledge_search_404_on_unknown_id(test_db):
    with pytest.raises(HTTPException) as e:
        acknowledge_search_warning(MISSING_ID, db=test_db)
    assert e.value.status_code == 404


@pytest.mark.parametrize("mode", ["extension", "linkedin_extension"])
def test_acknowledge_search_409_on_builtin_extension_searches(test_db, mode):
    """The seeded extension searches never scrape, so there is no scrape health to acknowledge — same guard /run and DELETE use."""
    s = Search(name=f"Extension {mode}", search_mode=mode, active=True)
    test_db.add(s)
    test_db.commit()

    with pytest.raises(HTTPException) as e:
        acknowledge_search_warning(str(s.id), db=test_db)
    assert e.value.status_code == 409
    assert s.warning_acknowledged_at is None


# ── is_acknowledged() ────────────────────────────────────────────────────────

def test_is_acknowledged_compares_against_the_newest_run():
    ack = _now()
    assert is_acknowledged(ack - timedelta(minutes=1), ack) is True
    assert is_acknowledged(ack + timedelta(minutes=1), ack) is False
    assert is_acknowledged(ack, None) is False
    assert is_acknowledged(None, ack) is False


def test_is_acknowledged_tolerates_naive_datetimes():
    """SQLite (and any row written before the column was tz-aware) hands back a naive datetime; comparing it with an aware one would raise TypeError."""
    ack = _now()
    naive_run = (ack - timedelta(minutes=1)).replace(tzinfo=None)
    assert is_acknowledged(naive_run, ack) is True
    assert is_acknowledged(ack.replace(tzinfo=None), ack) is True


# ── scheduler run summary ────────────────────────────────────────────────────

def test_scrape_summary_ignores_switched_off_entities(test_db):
    from backend.scheduler import _scrape_summary
    live = Search(name="Live", search_mode="keyword", active=True)
    paused = Search(name="Paused", search_mode="keyword", active=False)
    off_co = Company(name="OffCo", active=False)
    test_db.add_all([live, paused, off_co])
    test_db.commit()

    test_db.add(ScrapeLog(search_id=live.id, source="linkedin", jobs_found=4, new_jobs=2))
    test_db.add(ScrapeLog(search_id=paused.id, source="indeed", jobs_found=0, error="403"))
    test_db.add(ScrapeLog(company_id=off_co.id, source="playwright_url", jobs_found=0, is_warning=True))
    bad_board = ScrapeLog(search_id=paused.id, source="jobspy", jobs_found=1, new_jobs=0)
    bad_board.source_breakdown = {"zip_recruiter": {"error": "403"}}
    test_db.add(bad_board)
    test_db.commit()

    out = _scrape_summary(_now() - timedelta(hours=1))

    # every row still counts as a source that ran, and new jobs are new jobs…
    assert out.startswith("4 sources - +2 new")
    # …but nothing that was switched off is reported as needing attention
    assert "failed" not in out
    assert "empty" not in out


def test_scrape_summary_still_reports_active_entities(test_db):
    from backend.scheduler import _scrape_summary
    live = Search(name="Live", search_mode="keyword", active=True)
    test_db.add(live)
    test_db.commit()
    test_db.add(ScrapeLog(search_id=live.id, source="indeed", jobs_found=0, error="403"))
    test_db.commit()

    assert "1 failed" in _scrape_summary(_now() - timedelta(hours=1))
