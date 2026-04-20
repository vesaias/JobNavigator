"""Tests for analyzer/h1b_checker — scan_jd, determine_verdict, refresh-preserves-cache."""
import pytest
from unittest.mock import AsyncMock


# ── scan_jd_for_h1b_flags ────────────────────────────────────────────────────

def test_scan_jd_for_h1b_flags_match():
    """JD contains an exclusion phrase → jd_flag=True + snippet populated."""
    from backend.analyzer.h1b_checker import scan_jd_for_h1b_flags

    description = (
        "Great role for an experienced PM. Unfortunately we do not sponsor "
        "visas for this position. Strong culture and benefits."
    )
    phrases = ["no visa sponsorship", "do not sponsor"]

    result = scan_jd_for_h1b_flags(description, phrases)

    assert result["jd_flag"] is True
    assert result["jd_snippet"] is not None
    assert "sponsor" in result["jd_snippet"].lower()


def test_scan_jd_for_h1b_flags_no_match():
    """JD with no exclusion phrases → jd_flag=False, snippet=None."""
    from backend.analyzer.h1b_checker import scan_jd_for_h1b_flags

    description = "Great role. We offer competitive benefits and equity."
    phrases = ["no visa sponsorship", "do not sponsor"]

    result = scan_jd_for_h1b_flags(description, phrases)

    assert result["jd_flag"] is False
    assert result["jd_snippet"] is None


def test_scan_jd_for_h1b_flags_empty_description():
    """Empty description → jd_flag=False."""
    from backend.analyzer.h1b_checker import scan_jd_for_h1b_flags

    result = scan_jd_for_h1b_flags("", ["no sponsorship"])
    assert result["jd_flag"] is False
    assert result["jd_snippet"] is None


def test_scan_jd_for_h1b_flags_case_insensitive():
    """Phrase match is case-insensitive."""
    from backend.analyzer.h1b_checker import scan_jd_for_h1b_flags

    description = "We DO NOT SPONSOR visas for this role."
    phrases = ["do not sponsor"]

    result = scan_jd_for_h1b_flags(description, phrases)
    assert result["jd_flag"] is True


# ── determine_h1b_verdict (5-branch logic) ───────────────────────────────────

def test_determine_h1b_verdict_likely():
    """lca_count > 50, no jd_flag → 'likely'."""
    from backend.analyzer.h1b_checker import determine_h1b_verdict
    assert determine_h1b_verdict(100, False) == "likely"
    assert determine_h1b_verdict(51, False) == "likely"


def test_determine_h1b_verdict_possible():
    """10 <= lca_count <= 50, no jd_flag → 'possible'."""
    from backend.analyzer.h1b_checker import determine_h1b_verdict
    assert determine_h1b_verdict(10, False) == "possible"
    assert determine_h1b_verdict(50, False) == "possible"


def test_determine_h1b_verdict_unlikely_low_count():
    """lca_count 1..9, no jd_flag → 'unlikely'."""
    from backend.analyzer.h1b_checker import determine_h1b_verdict
    assert determine_h1b_verdict(5, False) == "unlikely"
    assert determine_h1b_verdict(1, False) == "unlikely"


def test_determine_h1b_verdict_unknown_zero():
    """lca_count == 0, no jd_flag → 'unknown'."""
    from backend.analyzer.h1b_checker import determine_h1b_verdict
    assert determine_h1b_verdict(0, False) == "unknown"


def test_determine_h1b_verdict_jd_flag_wins():
    """JD flag overrides LCA count → always 'unlikely'."""
    from backend.analyzer.h1b_checker import determine_h1b_verdict
    # JD flag wins even with high LCA count
    assert determine_h1b_verdict(500, True) == "unlikely"
    assert determine_h1b_verdict(10, True) == "unlikely"
    assert determine_h1b_verdict(0, True) == "unlikely"


# ── refresh_all_h1b preserves cached data when fetch returns zeros ──────────

@pytest.mark.asyncio
async def test_refresh_all_h1b_preserves_cached_when_fetch_zero(test_db, monkeypatch):
    """When fetch returns 0 LCAs for a company with cached non-zero data, keep cached."""
    from backend.models.db import Company
    from sqlalchemy.orm import sessionmaker

    TestSession = sessionmaker(bind=test_db.get_bind())
    monkeypatch.setattr("backend.analyzer.h1b_checker.SessionLocal", TestSession)

    # Company with real cached LCA data (no h1b_last_checked → eligible for refresh)
    co = Company(
        name="CachedCo",
        scrape_urls=[],
        aliases=[],
        h1b_lca_count=250,
        h1b_approval_rate=95.5,
        h1b_median_salary=180000,
        h1b_last_checked=None,
    )
    test_db.add(co)
    test_db.commit()

    # Fetch returns zeros (simulating a MyVisaJobs redirect / slug lookup failure)
    async def fake_fetch(company_name, h1b_slug=None):
        return {"lca_count": 0, "approval_rate": 0, "median_salary": 0}

    monkeypatch.setattr(
        "backend.analyzer.h1b_checker.fetch_company_h1b_data",
        fake_fetch,
    )

    # Silence the activity logger (it hits a separate SessionLocal import)
    monkeypatch.setattr(
        "backend.activity.log_activity",
        lambda *a, **kw: None,
    )

    from backend.analyzer.h1b_checker import refresh_all_h1b
    await refresh_all_h1b()

    # Cached data should be preserved
    test_db.expire_all()
    refreshed = test_db.query(Company).filter(Company.name == "CachedCo").first()
    assert refreshed.h1b_lca_count == 250, (
        f"Expected cached count preserved; got {refreshed.h1b_lca_count}"
    )
    assert refreshed.h1b_approval_rate == 95.5
    assert refreshed.h1b_median_salary == 180000


@pytest.mark.asyncio
async def test_refresh_all_h1b_overwrites_when_fetch_nonzero(test_db, monkeypatch):
    """Sanity: when fetch returns non-zero, the new data DOES overwrite."""
    from backend.models.db import Company
    from sqlalchemy.orm import sessionmaker

    TestSession = sessionmaker(bind=test_db.get_bind())
    monkeypatch.setattr("backend.analyzer.h1b_checker.SessionLocal", TestSession)

    co = Company(
        name="UpdateCo",
        scrape_urls=[],
        aliases=[],
        h1b_lca_count=10,
        h1b_approval_rate=80.0,
        h1b_median_salary=120000,
        h1b_last_checked=None,
    )
    test_db.add(co)
    test_db.commit()

    async def fake_fetch(company_name, h1b_slug=None):
        return {"lca_count": 500, "approval_rate": 98.0, "median_salary": 200000}

    monkeypatch.setattr(
        "backend.analyzer.h1b_checker.fetch_company_h1b_data",
        fake_fetch,
    )
    monkeypatch.setattr(
        "backend.activity.log_activity",
        lambda *a, **kw: None,
    )

    from backend.analyzer.h1b_checker import refresh_all_h1b
    await refresh_all_h1b()

    test_db.expire_all()
    refreshed = test_db.query(Company).filter(Company.name == "UpdateCo").first()
    assert refreshed.h1b_lca_count == 500
    assert refreshed.h1b_median_salary == 200000
