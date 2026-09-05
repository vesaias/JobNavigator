"""The run summary must agree with the ScrapeLog row and with the rows the run actually stored: `_run_sync` counts title-filtered postings (still stored as `ignored`) into `ignored_jobs` and a per-board `filtered` entry, and the summary is built by reading the log row back so it cannot drift from the audit trail."""
import sys
import types

import pytest

from backend.models.db import Job, ScrapeLog, Search


def _fake_jobspy(rows):
    """Stand-in `jobspy` module whose scrape_jobs returns `rows`."""
    import pandas as pd

    mod = types.ModuleType("jobspy")
    mod.scrape_jobs = lambda **kwargs: pd.DataFrame(rows)
    sys.modules["jobspy"] = mod
    return mod


def _row(site, title, company, url):
    return {
        "site": site, "title": title, "company": company, "job_url": url,
        "description": "A perfectly ordinary job description. " * 5,
        "location": "Remote", "min_amount": None, "max_amount": None,
    }


def _search(db, sources, exclude=None):
    s = Search(name="ZZ Summary", search_mode="keyword", active=True, sources=sources,
               search_term="program manager", title_include_keywords=[],
               title_exclude_keywords=exclude or [], company_filter=[],
               company_exclude=[], auto_scoring_depth="off")
    db.add(s)
    db.commit()
    return s


# ── the counters ────────────────────────────────────────────────────────────

def test_every_stored_row_is_accounted_for(test_db):
    """new_jobs + ignored_jobs == the rows the run actually inserted; two of the five postings are rejected by the title filter and stored `ignored`."""
    from backend.scraper.sources.jobspy import _run_sync

    _fake_jobspy([
        _row("indeed", "Program Manager", "Acme", "https://indeed.test/a"),
        _row("indeed", "Delivery Manager", "Acme", "https://indeed.test/b"),
        _row("indeed", "Senior Program Manager", "Beta", "https://indeed.test/c"),
        _row("indeed", "Warehouse Intern", "Beta", "https://indeed.test/d"),
        _row("indeed", "Sales Intern", "Gamma", "https://indeed.test/e"),
    ])
    search = _search(test_db, ["indeed"], exclude=["intern"])

    result = _run_sync(search)

    stored = test_db.query(Job).filter(Job.search_id == search.id).all()
    kept = [j for j in stored if j.status != "ignored"]
    dropped = [j for j in stored if j.status == "ignored"]

    assert result["jobs_found"] == len(kept) == 3
    assert result["new_jobs"] == 3
    assert result["ignored_jobs"] == len(dropped) == 2
    # the whole stored set, with nothing left over
    assert result["new_jobs"] + result["ignored_jobs"] == len(stored) == 5


def test_filtered_rows_ride_into_the_per_board_breakdown(test_db):
    from backend.scraper.sources.jobspy import _run_sync
    from backend.scraper.orchestrator import filtered_count

    _fake_jobspy([
        _row("indeed", "Program Manager", "Acme", "https://indeed.test/a"),
        _row("indeed", "Sales Intern", "Gamma", "https://indeed.test/e"),
        _row("linkedin", "Product Intern", "Delta", "https://linkedin.test/f"),
    ])
    search = _search(test_db, ["indeed", "linkedin"], exclude=["intern"])

    result = _run_sync(search)

    bd = result["source_breakdown"]
    assert bd["indeed"]["seen"] == 1 and bd["indeed"]["new"] == 1
    assert bd["indeed"]["filtered"] == 1
    assert bd["linkedin"]["filtered"] == 1
    assert filtered_count(bd) == result["ignored_jobs"] == 2


def test_no_filtered_key_when_nothing_was_rejected(test_db):
    from backend.scraper.sources.jobspy import _run_sync
    from backend.scraper.orchestrator import filtered_count

    _fake_jobspy([_row("indeed", "Program Manager", "Acme", "https://indeed.test/a")])
    search = _search(test_db, ["indeed"])

    result = _run_sync(search)

    assert result["ignored_jobs"] == 0
    assert "filtered" not in result["source_breakdown"]["indeed"]
    assert filtered_count(result["source_breakdown"]) == 0


# ── summary vs the log row ──────────────────────────────────────────────────

async def _run_and_summarize(test_db, monkeypatch, search):
    """Drive the real _run_sync through _run_search_by_id, then build the Run-history line the way the trigger endpoint does."""
    import backend.scraper.orchestrator as orch
    from backend.scraper.sources.jobspy import _run_sync

    async def fake_run_search(s, proxy_url=None):
        return _run_sync(s)

    monkeypatch.setattr(orch, "run_search", fake_run_search)
    result = await orch._run_search_by_id(str(search.id), auto_score=False)
    return result, orch.summarize_search_run(search.name, result)


@pytest.mark.asyncio
async def test_summary_counts_equal_the_scrape_log_counts(test_db, monkeypatch):
    _fake_jobspy([
        _row("indeed", "Program Manager", "Acme", "https://indeed.test/a"),
        _row("indeed", "Delivery Manager", "Acme", "https://indeed.test/b"),
        _row("indeed", "Senior Program Manager", "Beta", "https://indeed.test/c"),
        _row("indeed", "Warehouse Intern", "Beta", "https://indeed.test/d"),
        _row("indeed", "Sales Intern", "Gamma", "https://indeed.test/e"),
    ])
    search = _search(test_db, ["indeed"], exclude=["intern"])

    result, summary = await _run_and_summarize(test_db, monkeypatch, search)

    log = test_db.query(ScrapeLog).filter(ScrapeLog.search_id == search.id).one()
    assert summary == f"ZZ Summary - {log.jobs_found} seen, +{log.new_jobs} new, 2 filtered out"
    assert (log.jobs_found, log.new_jobs) == (3, 3)
    # the summary was read back from that exact row, not from the result dict
    assert result["scrape_log_id"] == str(log.id)
    # and the row itself carries the filtered count
    from backend.scraper.orchestrator import filtered_count
    assert filtered_count(log.source_breakdown) == 2


@pytest.mark.asyncio
async def test_summary_says_nothing_about_filtering_when_there_was_none(test_db, monkeypatch):
    _fake_jobspy([
        _row("indeed", "Program Manager", "Acme", "https://indeed.test/a"),
        _row("indeed", "Delivery Manager", "Acme", "https://indeed.test/b"),
    ])
    search = _search(test_db, ["indeed"])

    _result, summary = await _run_and_summarize(test_db, monkeypatch, search)

    log = test_db.query(ScrapeLog).filter(ScrapeLog.search_id == search.id).one()
    assert summary == "ZZ Summary - 2 seen, +2 new"
    assert (log.jobs_found, log.new_jobs) == (2, 2)


@pytest.mark.asyncio
async def test_summary_prefers_the_log_row_over_a_stale_result_dict(test_db, monkeypatch):
    """Pins the mechanism: the numbers come from the ScrapeLog row, so a caller handing over a dict whose counts drifted cannot put a wrong number on screen."""
    import backend.scraper.orchestrator as orch

    async def fake_run_search(s, proxy_url=None):
        return {"jobs_found": 6, "new_jobs": 6, "ignored_jobs": 2, "error": None,
                "duration": 1.0,
                "source_breakdown": {"indeed": {"seen": 6, "new": 6, "filtered": 2}}}

    search = _search(test_db, ["indeed"])
    monkeypatch.setattr(orch, "run_search", fake_run_search)
    result = await orch._run_search_by_id(str(search.id), auto_score=False)

    result["jobs_found"] = 999          # whatever the caller thinks it saw
    result["new_jobs"] = 999
    summary = orch.summarize_search_run("ZZ Summary", result)

    log = test_db.query(ScrapeLog).filter(ScrapeLog.search_id == search.id).one()
    assert summary == "ZZ Summary - 6 seen, +6 new, 2 filtered out"
    assert (log.jobs_found, log.new_jobs) == (6, 6)


@pytest.mark.asyncio
async def test_summary_falls_back_to_the_result_dict_without_a_log_id(test_db):
    """Older callers (and the run-all path) hand over a plain result dict."""
    from backend.scraper.orchestrator import summarize_search_run

    summary = summarize_search_run("ZZ Summary", {
        "jobs_found": 9, "new_jobs": 0,
        "source_breakdown": {"indeed": {"seen": 9, "new": 0},
                             "zip_recruiter": {"seen": 0, "new": 0, "error": "403"}},
    })
    assert summary == "ZZ Summary - 9 seen, +0 new · zip_recruiter: 403"
    assert summarize_search_run("ZZ Summary", None) == "ZZ Summary - nothing ran"
