"""GET /api/health/entities — flag active companies/searches with failing scrapes."""
from datetime import datetime, timezone, timedelta

from backend.models.db import Company, Search, ScrapeLog


def _log(company_id=None, search_id=None, error=None, is_warning=False, ago_min=0):
    return ScrapeLog(
        company_id=company_id, search_id=search_id, source="test",
        jobs_found=0, new_jobs=0, error=error, is_warning=is_warning,
        duration_seconds=0.0,
        ran_at=datetime.now(timezone.utc) - timedelta(minutes=ago_min),
    )


def _run():
    from backend.main import get_failing_entities
    return get_failing_entities()


def test_company_flagged_on_three_empty(test_db):
    c = Company(name="EmptyCo", active=True)
    test_db.add(c)
    test_db.commit()
    for i in range(3):
        test_db.add(_log(company_id=c.id, is_warning=True, ago_min=i))
    test_db.commit()

    r = _run()
    row = next((x for x in r["companies"] if x["name"] == "EmptyCo"), None)
    assert row is not None
    assert "No results" in row["reason"]


def test_company_flagged_on_three_errors_uses_latest_error(test_db):
    c = Company(name="BrokenCo", active=True)
    test_db.add(c)
    test_db.commit()
    test_db.add(_log(company_id=c.id, error="old error", ago_min=5))
    test_db.add(_log(company_id=c.id, error="mid error", ago_min=3))
    test_db.add(_log(company_id=c.id, error="latest 404", ago_min=0))
    test_db.commit()

    r = _run()
    row = next((x for x in r["companies"] if x["name"] == "BrokenCo"), None)
    assert row is not None
    assert row["reason"] == "latest 404"  # most recent actual error


def test_not_flagged_when_a_recent_scrape_succeeded(test_db):
    c = Company(name="OkCo", active=True)
    test_db.add(c)
    test_db.commit()
    test_db.add(_log(company_id=c.id, is_warning=True, ago_min=2))
    test_db.add(_log(company_id=c.id, is_warning=True, ago_min=1))
    test_db.add(_log(company_id=c.id, is_warning=False, error=None, ago_min=0))  # success
    test_db.commit()

    r = _run()
    assert all(x["name"] != "OkCo" for x in r["companies"])


def test_not_flagged_with_fewer_than_window_logs(test_db):
    c = Company(name="NewCo", active=True)
    test_db.add(c)
    test_db.commit()
    test_db.add(_log(company_id=c.id, is_warning=True, ago_min=1))
    test_db.add(_log(company_id=c.id, is_warning=True, ago_min=0))  # only 2
    test_db.commit()

    r = _run()
    assert all(x["name"] != "NewCo" for x in r["companies"])


def test_inactive_company_not_flagged(test_db):
    c = Company(name="OffCo", active=False)
    test_db.add(c)
    test_db.commit()
    for i in range(3):
        test_db.add(_log(company_id=c.id, error="boom", ago_min=i))
    test_db.commit()

    r = _run()
    assert all(x["name"] != "OffCo" for x in r["companies"])


def test_search_flagged_and_count(test_db):
    s = Search(name="DeadSearch", search_mode="keyword", active=True)
    test_db.add(s)
    test_db.commit()
    for i in range(3):
        test_db.add(_log(search_id=s.id, error="429", ago_min=i))
    test_db.commit()

    r = _run()
    assert any(x["name"] == "DeadSearch" for x in r["searches"])
    assert r["count"] == len(r["companies"]) + len(r["searches"])


def test_inactive_search_not_flagged(test_db):
    """A paused search is not an open problem — it was switched off deliberately,
    so its failed history must stop driving the rail dot and the header count."""
    s = Search(name="OffSearch", search_mode="keyword", active=False)
    test_db.add(s)
    test_db.commit()
    for i in range(3):
        test_db.add(_log(search_id=s.id, error="boom", ago_min=i))
    test_db.commit()

    r = _run()
    assert all(x["name"] != "OffSearch" for x in r["searches"])
    assert r["count"] == 0


# ── acknowledgement ──────────────────────────────────────────────────────────

def test_acknowledged_company_not_flagged(test_db):
    c = Company(name="AckCo", active=True)
    test_db.add(c)
    test_db.commit()
    for i in range(3):
        test_db.add(_log(company_id=c.id, error="404", ago_min=i + 1))
    test_db.commit()
    # acknowledged after the newest of those runs
    c.warning_acknowledged_at = datetime.now(timezone.utc)
    test_db.commit()

    r = _run()
    assert all(x["name"] != "AckCo" for x in r["companies"])


def test_acknowledged_search_not_flagged(test_db):
    s = Search(name="AckSearch", search_mode="keyword", active=True)
    test_db.add(s)
    test_db.commit()
    for i in range(3):
        test_db.add(_log(search_id=s.id, error="429", ago_min=i + 1))
    test_db.commit()
    s.warning_acknowledged_at = datetime.now(timezone.utc)
    test_db.commit()

    r = _run()
    assert all(x["name"] != "AckSearch" for x in r["searches"])


def test_failed_run_after_acknowledge_flags_again(test_db):
    """No expiry timer: the warning comes back the moment a run *newer* than the
    acknowledgement fails."""
    c = Company(name="ReAckCo", active=True)
    test_db.add(c)
    test_db.commit()
    for i in range(3):
        test_db.add(_log(company_id=c.id, error="404", ago_min=i + 10))
    test_db.commit()
    c.warning_acknowledged_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    test_db.commit()
    assert all(x["name"] != "ReAckCo" for x in _run()["companies"]), "acknowledged, so quiet"

    test_db.add(_log(company_id=c.id, error="still 404", ago_min=0))   # newer than the ack
    test_db.commit()

    row = next((x for x in _run()["companies"] if x["name"] == "ReAckCo"), None)
    assert row is not None
    assert row["reason"] == "still 404"


def test_acknowledge_also_covers_a_failed_board_on_the_last_run(test_db):
    """The R3-A-03 single-board branch honours the acknowledgement too — otherwise
    "ZipRecruiter failed" would stay amber forever with no way to clear it."""
    s = Search(name="BoardSearch", search_mode="keyword", active=True)
    test_db.add(s)
    test_db.commit()
    log = _log(search_id=s.id, ago_min=1)
    log.source_breakdown = {"zip_recruiter": {"error": "403"}}
    test_db.add(log)
    test_db.commit()
    assert any(x["name"] == "BoardSearch" for x in _run()["searches"])

    s.warning_acknowledged_at = datetime.now(timezone.utc)
    test_db.commit()
    assert all(x["name"] != "BoardSearch" for x in _run()["searches"])
