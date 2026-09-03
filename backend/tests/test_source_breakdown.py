"""R3-A-03: a JobSpy board that hard-fails must not look like one that found nothing.

jobspy runs every configured board inside one `scrape_jobs()` call and swallows
per-board failures into its own loggers, so a ZipRecruiter 403 used to finish
`completed`, `is_warning=False`, summary "9 seen, +0 new". These tests pin the
per-source breakdown, the warning flag and the run summary.
"""
import logging
import sys
import types

import pytest

from backend.models.db import ScrapeLog, Search


def _board_logger(name):
    """A logger shaped exactly like jobspy's own create_logger() makes them.

    jobspy/util.py::create_logger does:

        logger = logging.getLogger(f"JobSpy:{name}")
        logger.propagate = False
        if not logger.handlers:
            logger.setLevel(logging.INFO)
            logger.addHandler(logging.StreamHandler())

    ``propagate = False`` is the whole point of these tests: it is why a capture
    handler on the *root* logger never sees a board failure. Reproduce it here
    so the tests fail against the root-only capture they replaced.
    """
    logger = logging.getLogger(name)
    logger.propagate = False
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        logger.addHandler(logging.NullHandler())
    return logger


def _fake_jobspy(rows, log_errors=()):
    """Install a stand-in `jobspy` module whose scrape_jobs returns `rows`.

    `log_errors` is a list of (logger_name, message) the fake emits before
    returning — exactly how the real library reports a refused board, down to
    the non-propagating logger it emits on.
    """
    import pandas as pd

    # Created at import time by the real library, so they already exist by the
    # time _capture_source_errors() enumerates them. Same here.
    boards = [_board_logger(name) for name, _ in log_errors]

    def scrape_jobs(**kwargs):
        for logger, (_, msg) in zip(boards, log_errors):
            logger.error(msg)
        return pd.DataFrame(rows)

    mod = types.ModuleType("jobspy")
    mod.scrape_jobs = scrape_jobs
    sys.modules["jobspy"] = mod
    return mod


def _row(site, title, company, url):
    return {
        "site": site, "title": title, "company": company, "job_url": url,
        "description": "A perfectly ordinary job description. " * 5,
        "location": "Remote", "min_amount": None, "max_amount": None,
    }


def _first_run_auth(db):
    """Empty dashboard_api_key → the middleware's first-run bypass, so the
    endpoint tests below exercise the serializer and not the 401."""
    from backend.models.db import Setting
    db.add(Setting(key="dashboard_api_key", value=""))
    db.commit()


def _search(db, sources):
    s = Search(name="ZZ Search", search_mode="keyword", active=True, sources=sources,
               search_term="program manager", title_include_keywords=[],
               title_exclude_keywords=[], company_filter=[], company_exclude=[])
    db.add(s)
    db.commit()
    return s


# ── the source module ───────────────────────────────────────────────────────

def test_breakdown_counts_each_board(test_db, monkeypatch):
    from backend.scraper.sources.jobspy import _run_sync

    _fake_jobspy([
        _row("indeed", "Program Manager", "Acme", "https://indeed.test/a"),
        _row("indeed", "Delivery Manager", "Acme", "https://indeed.test/b"),
        _row("linkedin", "Product Manager", "Beta", "https://linkedin.test/c"),
    ])
    search = _search(test_db, ["indeed", "linkedin"])

    result = _run_sync(search)

    assert result["jobs_found"] == 3
    assert result["source_breakdown"]["indeed"]["seen"] == 2
    assert result["source_breakdown"]["linkedin"]["seen"] == 1
    # every board reported a result — nothing errored
    assert not any("error" in v for v in result["source_breakdown"].values())


def test_breakdown_records_a_refused_board(test_db, monkeypatch):
    """The 403 ZipRecruiter logs is captured and condensed to its status code."""
    from backend.scraper.sources.jobspy import _run_sync

    _fake_jobspy(
        [_row("indeed", "Program Manager", "Acme", "https://indeed.test/a")],
        log_errors=[
            ("JobSpy:ZipRecruiter", "ZipRecruiter response status code 403"),
            ("JobSpy:Google", "initial cursor not found"),
        ],
    )
    search = _search(test_db, ["indeed", "zip_recruiter", "google"])

    result = _run_sync(search)

    bd = result["source_breakdown"]
    assert bd["indeed"]["seen"] == 1
    assert bd["zip_recruiter"]["error"] == "403"
    assert bd["google"]["error"] == "initial cursor not found"
    # the overall run still succeeded — the failure lives per source
    assert result["error"] is None


def test_board_logger_does_not_propagate_to_root():
    """Pin the library behaviour the capture has to work around.

    If this ever stops holding, the root-logger fallback would be enough and the
    per-board attachment could go — but as long as it holds, a root-only handler
    is a no-op against a real board failure.
    """
    from backend.scraper.sources.jobspy import _SourceLogCapture

    board = _board_logger("JobSpy:ZipRecruiter")
    assert board.propagate is False

    root_only = _SourceLogCapture()
    logging.getLogger().addHandler(root_only)
    try:
        board.error("ZipRecruiter response status code 403")
    finally:
        logging.getLogger().removeHandler(root_only)
    assert root_only.errors == {}


def test_capture_attaches_to_the_non_propagating_board_logger():
    """The context manager itself, exercised directly against the real condition."""
    from backend.scraper.sources.jobspy import _capture_source_errors

    _board_logger("JobSpy:ZipRecruiter")
    with _capture_source_errors(["indeed", "zip_recruiter"]) as capture:
        logging.getLogger("JobSpy:ZipRecruiter").error("ZipRecruiter response status code 403")
    assert capture.errors == {"zip_recruiter": "403"}


def test_capture_handler_is_removed_afterwards(test_db):
    """No logger — root or board — may keep collecting after the call returns."""
    from backend.scraper.sources.jobspy import _run_sync

    board = _board_logger("JobSpy:Indeed")
    before_root = len(logging.getLogger().handlers)
    before_board = len(board.handlers)

    _fake_jobspy([], log_errors=[("JobSpy:Indeed", "boom 500")])
    _run_sync(_search(test_db, ["indeed"]))

    assert len(logging.getLogger().handlers) == before_root
    assert len(board.handlers) == before_board


def test_condense_error_keeps_non_http_text():
    from backend.scraper.sources.jobspy import _condense_error, _site_key

    assert _condense_error("ZipRecruiter response status code 403") == "403"
    assert _condense_error("initial cursor not found") == "initial cursor not found"
    assert _site_key("JobSpy:ZipRecruiter") == "zip_recruiter"
    assert _site_key("JobSpy:Google") == "google"
    assert _site_key("uvicorn.error") is None


# ── the ScrapeLog row ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_scrape_log_flags_a_failed_source(test_db, monkeypatch):
    import backend.scraper.orchestrator as orch

    search = _search(test_db, ["indeed", "zip_recruiter"])

    async def fake_run_search(s, proxy_url=None):
        return {
            "jobs_found": 9, "new_jobs": 0, "error": None, "duration": 1.0,
            "source_breakdown": {
                "indeed": {"seen": 9, "new": 0},
                "zip_recruiter": {"seen": 0, "new": 0, "error": "403"},
            },
        }

    monkeypatch.setattr(orch, "run_search", fake_run_search)
    await orch._run_search_by_id(str(search.id), auto_score=False)

    log = test_db.query(ScrapeLog).filter(ScrapeLog.search_id == search.id).one()
    assert log.is_warning is True
    assert log.source_breakdown["zip_recruiter"]["error"] == "403"
    assert log.source_breakdown["indeed"]["seen"] == 9


@pytest.mark.asyncio
async def test_scrape_log_unchanged_when_every_source_is_fine(test_db, monkeypatch):
    import backend.scraper.orchestrator as orch

    search = _search(test_db, ["indeed", "linkedin"])

    async def fake_run_search(s, proxy_url=None):
        return {
            "jobs_found": 9, "new_jobs": 3, "error": None, "duration": 1.0,
            "source_breakdown": {
                "indeed": {"seen": 6, "new": 2},
                "linkedin": {"seen": 3, "new": 1},
            },
        }

    monkeypatch.setattr(orch, "run_search", fake_run_search)
    await orch._run_search_by_id(str(search.id), auto_score=False)

    log = test_db.query(ScrapeLog).filter(ScrapeLog.search_id == search.id).one()
    assert log.is_warning is False
    assert log.error is None
    assert log.source_breakdown["indeed"]["new"] == 2


# ── the run summary ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_summary_names_the_failed_sources(test_db, monkeypatch):
    import backend.api.routes_searches as rs
    import backend.scraper.orchestrator as orch

    search = _search(test_db, ["indeed", "zip_recruiter", "google"])

    async def fake_run(search_id, auto_score=None):
        return {
            "jobs_found": 9, "new_jobs": 0, "error": None, "duration": 1.0,
            "source_breakdown": {
                "indeed": {"seen": 9, "new": 0},
                "zip_recruiter": {"seen": 0, "new": 0, "error": "403"},
                "google": {"seen": 0, "new": 0, "error": "initial cursor not found"},
            },
        }

    monkeypatch.setattr(orch, "_run_search_by_id", fake_run)

    captured = {}

    def fake_launch(job_type, coro_func, **kw):
        captured["coro"] = coro_func
        return "run-1"

    monkeypatch.setattr("backend.job_monitor.launch_background", fake_launch)
    await rs.trigger_search(str(search.id), db=test_db)

    summary = await captured["coro"]()
    assert summary.startswith("ZZ Search - 9 seen, +0 new · ")
    assert "zip_recruiter: 403" in summary
    assert "google: initial cursor not found" in summary


@pytest.mark.asyncio
async def test_run_summary_unchanged_when_sources_are_clean(test_db, monkeypatch):
    import backend.api.routes_searches as rs
    import backend.scraper.orchestrator as orch

    search = _search(test_db, ["indeed"])

    async def fake_run(search_id, auto_score=None):
        return {"jobs_found": 12, "new_jobs": 4, "error": None, "duration": 1.0,
                "source_breakdown": {"indeed": {"seen": 12, "new": 4}}}

    monkeypatch.setattr(orch, "_run_search_by_id", fake_run)

    captured = {}
    monkeypatch.setattr("backend.job_monitor.launch_background",
                        lambda job_type, coro_func, **kw: captured.setdefault("coro", coro_func) and "r")
    await rs.trigger_search(str(search.id), db=test_db)
    assert await captured["coro"]() == "ZZ Search - 12 seen, +4 new"


# ── the API surface the Searches screen reads ───────────────────────────────

def test_search_dict_exposes_last_source_errors(test_db):
    from backend.api.routes_searches import _search_to_dict

    search = _search(test_db, ["indeed", "zip_recruiter"])
    log = ScrapeLog(search_id=search.id, source="jobspy", jobs_found=9, new_jobs=0,
                    is_warning=True, duration_seconds=1.0,
                    source_breakdown={"indeed": {"seen": 9, "new": 0},
                                      "zip_recruiter": {"seen": 0, "new": 0, "error": "403"}})
    test_db.add(log)
    test_db.commit()

    d = _search_to_dict(search, last_log=log)
    assert d["last_source_errors"] == [
        {"source": "zip_recruiter", "label": "ZipRecruiter", "error": "403"}
    ]


def test_scrape_log_endpoint_serializes_source_breakdown(test_db, api_client):
    """R3-A-03: the run-history endpoint has to carry the per-board outcome.

    A row can hold a perfectly populated breakdown and still be useless if the
    endpoint drops the column on the way out.
    """
    _first_run_auth(test_db)
    search = _search(test_db, ["indeed", "zip_recruiter"])
    test_db.add(ScrapeLog(
        search_id=search.id, source="jobspy", jobs_found=9, new_jobs=0,
        is_warning=True, duration_seconds=1.0,
        source_breakdown={"indeed": {"seen": 9, "new": 0},
                          "zip_recruiter": {"seen": 0, "new": 0, "error": "403"}},
    ))
    test_db.commit()

    rows = api_client.get("/api/scrape-log").json()
    row = next(r for r in rows if r["search_id"] == str(search.id))
    assert row["source_breakdown"]["zip_recruiter"]["error"] == "403"
    assert row["source_breakdown"]["indeed"]["seen"] == 9


def test_scrape_log_endpoint_source_breakdown_is_null_when_absent(test_db, api_client):
    _first_run_auth(test_db)
    search = _search(test_db, ["indeed"])
    test_db.add(ScrapeLog(search_id=search.id, source="jobspy", jobs_found=1, new_jobs=1,
                          is_warning=False, duration_seconds=1.0))
    test_db.commit()

    rows = api_client.get("/api/scrape-log").json()
    row = next(r for r in rows if r["search_id"] == str(search.id))
    assert row["source_breakdown"] is None


def test_search_dict_has_no_source_errors_on_a_clean_run(test_db):
    from backend.api.routes_searches import _search_to_dict

    search = _search(test_db, ["indeed"])
    log = ScrapeLog(search_id=search.id, source="jobspy", jobs_found=9, new_jobs=2,
                    is_warning=False, duration_seconds=1.0,
                    source_breakdown={"indeed": {"seen": 9, "new": 2}})
    test_db.add(log)
    test_db.commit()
    assert _search_to_dict(search, last_log=log)["last_source_errors"] == []
