"""R4-T6 · line coverage for the branches of `backend/api/routes_jobs.py` the
contract pass (T1) never reached.

T1 drove the *bad input* side of this router; what stayed dark was the ordinary
work: the filter-list endpoints (`/companies/list`, `/sources/list`,
`/verdicts/list`) and the shared `_apply_common_filters` behind them, the
save-from-extension enrichment branches (re-save of a skipped row, description
backfill, a failing H-1B scan, the auto-score launch), the on-save score launch's
two failure arms, `/cache-applied`, and the three page endpoints (`cached-page`,
`frame-check`, `live-page`) with their helpers.

Every test pins what the code does today. Nothing here is xfailed.
"""
import uuid as _uuid
from unittest.mock import MagicMock

import pytest

from backend.tests.r4_support import (  # noqa: F401
    client, _clear_running_state, _no_outbound, assert_clean,
    make_job, make_company, make_search, make_resume, set_setting,
)


# ── shims ────────────────────────────────────────────────────────────────────

@pytest.fixture
def pg_cast_shim(test_db):
    """Let the two raw-SQL feed endpoints run under SQLite.

    `/feed-stats` and `/unscored-ids` compare `cv_scores::text` to `'{}'`.
    SQLite has no `::` cast operator, so the statement is a syntax error there
    and the endpoints' own Python has never been executed by a test. Dropping
    the cast keeps the comparison meaning the same (SQLite stores the JSON
    column as its serialised text) and leaves the handler untouched.
    """
    from sqlalchemy import event
    import backend.models.db as db_mod
    engine = db_mod.engine

    def _strip(conn, cursor, statement, parameters, context, executemany):
        return statement.replace("::text", ""), parameters

    event.listen(engine, "before_cursor_execute", _strip, retval=True)
    try:
        yield
    finally:
        event.remove(engine, "before_cursor_execute", _strip)


class _Resp:
    """Minimal stand-in for the httpx response `safe_get` returns."""

    def __init__(self, text="", headers=None, url="https://example.com/job", raise_exc=None):
        self.text = text
        self.headers = headers or {}
        self.url = url
        self._raise = raise_exc

    def raise_for_status(self):
        if self._raise:
            raise self._raise


def _patch_safe_get(monkeypatch, result):
    """Point `url_safety.safe_get` at `result` (a response, or an exception to raise)."""
    import backend.scraper._shared.url_safety as us

    async def _fake(*a, **kw):
        if isinstance(result, BaseException):
            raise result
        return result

    monkeypatch.setattr(us, "safe_get", _fake)


# ── POST /linkedin-import — the non-dict JSON body ───────────────────────────

@pytest.mark.parametrize("body", [[1, 2], "abc", 7, True])
def test_linkedin_import_json_that_is_not_an_object_is_422(client, body):
    """A body that parses as JSON but is not an object is a request error, not a
    500 — the handler's isinstance guard, distinct from the parse guard above it."""
    r = assert_clean(client.post("/api/jobs/linkedin-import", json=body), 422)
    assert "JSON object" in r.text


def test_linkedin_import_null_ids_is_accepted_zero(client):
    """`linkedin_ids: null` normalises to an empty list rather than raising."""
    r = assert_clean(client.post("/api/jobs/linkedin-import",
                                 json={"linkedin_ids": None}), 200)
    assert r.json() == {"accepted": 0, "message": "No IDs provided"}


# ── GET /linkedin-import/progress ────────────────────────────────────────────

def test_import_progress_is_idle_when_nothing_ran(client):
    from backend.scraper.sources.linkedin_extension import _linkedin_import_progress
    _linkedin_import_progress.clear()
    assert client.get("/api/jobs/linkedin-import/progress").json() == {"status": "idle"}


def test_import_progress_echoes_the_live_dict(client):
    """A non-empty progress dict is returned verbatim, not wrapped."""
    from backend.scraper.sources.linkedin_extension import _linkedin_import_progress
    _linkedin_import_progress.clear()
    _linkedin_import_progress.update({"status": "running", "done": 3, "total": 10})
    try:
        assert client.get("/api/jobs/linkedin-import/progress").json() == {
            "status": "running", "done": 3, "total": 10}
    finally:
        _linkedin_import_progress.clear()


# ── GET /api/jobs — the filters T1 left dark ─────────────────────────────────

def test_h1b_verdict_filter_single_value(client, test_db):
    make_job(test_db, url="https://x.com/a", h1b_verdict="likely")
    make_job(test_db, url="https://x.com/b", h1b_verdict="unlikely")
    r = assert_clean(client.get("/api/jobs?h1b_verdict=likely"), 200)
    assert r.json()["total"] == 1


def test_h1b_verdict_filter_comma_list_is_an_in_clause(client, test_db):
    make_job(test_db, url="https://x.com/a", h1b_verdict="likely")
    make_job(test_db, url="https://x.com/b", h1b_verdict="unlikely")
    make_job(test_db, url="https://x.com/c", h1b_verdict="unknown")
    r = assert_clean(client.get("/api/jobs?h1b_verdict=likely,unlikely"), 200)
    assert r.json()["total"] == 2


def test_status_and_source_comma_lists_are_in_clauses(client, test_db):
    make_job(test_db, url="https://x.com/a", status="new", source="s1")
    make_job(test_db, url="https://x.com/b", status="saved", source="s2")
    make_job(test_db, url="https://x.com/c", status="ignored", source="s3")
    assert client.get("/api/jobs?status=new,saved").json()["total"] == 2
    assert client.get("/api/jobs?source=s1,s2").json()["total"] == 2


def test_only_the_most_recent_tailored_resume_is_reported_per_job(client, test_db):
    """Two tailored copies for one job: the list keeps the first row the
    updated_at-desc query yields and ignores the rest."""
    job = make_job(test_db)
    older = make_resume(test_db, name="Tailored old", is_base=False, job_id=job.id)
    newer = make_resume(test_db, name="Tailored new", is_base=False, job_id=job.id)
    # updated_at is set by the model default; force a deterministic ordering.
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    older.updated_at = now - timedelta(hours=1)
    newer.updated_at = now
    test_db.commit()
    row = assert_clean(client.get("/api/jobs"), 200).json()["jobs"][0]
    assert row["tailored_resume_id"] == str(newer.id)


def test_a_running_job_without_a_target_is_not_reported_in_flight(client, test_db):
    """`in_flight` is built from the running map; an entry with no
    `target_job_id` (a whole-feed scrape) must not attach itself to a row."""
    import backend.job_monitor as jm
    from datetime import datetime, timezone
    job = make_job(test_db)
    jm._running["scrape_all"] = jm.RunningJob(
        run_id=_uuid.uuid4(), job_type="scrape_all", trigger="manual",
        started_at=datetime.now(timezone.utc), target_job_id=None,
    )
    jm._running["analyze_job:x"] = jm.RunningJob(
        run_id=_uuid.uuid4(), job_type="analyze_job", trigger="manual",
        started_at=datetime.now(timezone.utc), target_job_id=job.id,
    )
    row = assert_clean(client.get("/api/jobs"), 200).json()["jobs"][0]
    assert row["in_flight"] == ["analyze_job"]


# ── _expand_company_filter ───────────────────────────────────────────────────

def test_company_filter_expands_aliases(client, test_db):
    make_company(test_db, name="Amazon", aliases=["Audible", "AWS"])
    make_job(test_db, url="https://x.com/a", company="Audible")
    make_job(test_db, url="https://x.com/b", company="Amazon")
    make_job(test_db, url="https://x.com/c", company="Elsewhere")
    r = assert_clean(client.get("/api/jobs?company=Amazon"), 200)
    assert r.json()["total"] == 2


def test_company_filter_for_an_unknown_name_passes_through(client, test_db):
    make_job(test_db, url="https://x.com/a", company="Nowhere Inc")
    r = assert_clean(client.get("/api/jobs?company=Nowhere Inc"), 200)
    assert r.json()["total"] == 1


def test_blank_company_filter_is_dropped_not_matched(client, test_db):
    """`_expand_company_filter` returns None for empty input, so `?company=`
    lists everything rather than matching the empty string."""
    make_job(test_db, url="https://x.com/a", company="Acme")
    assert client.get("/api/jobs/sources/list?company=").status_code == 200
    assert client.get("/api/jobs?company=").json()["total"] == 1


# ── /companies/list · /sources/list · /verdicts/list ─────────────────────────

def test_companies_list_collapses_aliases_to_the_parent(client, test_db):
    make_company(test_db, name="Amazon", aliases=["Audible"])
    make_job(test_db, url="https://x.com/a", company="Audible")
    make_job(test_db, url="https://x.com/b", company="Zeta")
    r = assert_clean(client.get("/api/jobs/companies/list"), 200)
    assert r.json() == ["Amazon", "Zeta"]


def test_companies_list_with_counts_sums_aliases_and_sorts_by_count(client, test_db):
    make_company(test_db, name="Amazon", aliases=["Audible"])
    make_job(test_db, url="https://x.com/a", company="Audible")
    make_job(test_db, url="https://x.com/b", company="Amazon")
    make_job(test_db, url="https://x.com/c", company="Zeta")
    r = assert_clean(client.get("/api/jobs/companies/list?counts=1"), 200)
    assert r.json() == [{"name": "Amazon", "count": 2}, {"name": "Zeta", "count": 1}]


def test_companies_list_honours_the_shared_filters(client, test_db):
    make_job(test_db, url="https://x.com/a", company="Acme", status="new")
    make_job(test_db, url="https://x.com/b", company="Beta", status="ignored")
    assert client.get("/api/jobs/companies/list?status=new").json() == ["Acme"]
    assert client.get("/api/jobs/companies/list?status=new&counts=1").json() == [
        {"name": "Acme", "count": 1}]


def test_sources_list_plain_and_counted(client, test_db):
    make_job(test_db, url="https://x.com/a", source="indeed")
    make_job(test_db, url="https://x.com/b", source="indeed")
    make_job(test_db, url="https://x.com/c", source="extension")
    assert client.get("/api/jobs/sources/list").json() == ["extension", "indeed"]
    assert client.get("/api/jobs/sources/list?counts=1").json() == [
        {"name": "extension", "count": 1}, {"name": "indeed", "count": 2}]


def test_verdicts_list_plain_and_counted(client, test_db):
    make_job(test_db, url="https://x.com/a", h1b_verdict="likely")
    make_job(test_db, url="https://x.com/b", h1b_verdict="likely")
    make_job(test_db, url="https://x.com/c", h1b_verdict="unknown")
    assert client.get("/api/jobs/verdicts/list").json() == ["likely", "unknown"]
    assert client.get("/api/jobs/verdicts/list?counts=1").json() == [
        {"name": "likely", "count": 2}, {"name": "unknown", "count": 1}]


def test_filter_list_endpoints_apply_every_shared_filter(client, test_db):
    """One request carrying the whole `_apply_common_filters` surface; the
    matching row satisfies all of them and the decoys each fail exactly one."""
    search = make_search(test_db, name="S")
    make_job(test_db, url="https://x.com/hit", company="Acme", title="Senior PM",
             source="indeed", status="new", h1b_verdict="likely", saved=True,
             remote=True, salary_min=100, salary_max=200, best_cv_score=90.0,
             search_id=search.id)
    make_job(test_db, url="https://x.com/miss1", company="Acme", title="Senior PM",
             source="indeed", status="ignored", h1b_verdict="likely", saved=True,
             remote=True, salary_min=100, salary_max=200, best_cv_score=90.0,
             search_id=search.id)
    make_job(test_db, url="https://x.com/miss2", company="Acme", title="Janitor",
             source="indeed", status="new", h1b_verdict="likely", saved=True,
             remote=True, salary_min=100, salary_max=200, best_cv_score=90.0,
             search_id=search.id)
    qs = ("status=new&company=Acme&h1b_verdict=likely&min_score=50&saved=true"
          "&title_search=PM&remote=true&min_salary=150&max_salary=150"
          f"&search_id={search.id}")
    r = assert_clean(client.get(f"/api/jobs/sources/list?{qs}"), 200)
    assert r.json() == ["indeed"]
    r2 = assert_clean(client.get(f"/api/jobs/verdicts/list?{qs.replace('h1b_verdict=likely&', '')}"), 200)
    assert r2.json() == ["likely"]


def test_filter_lists_accept_a_comma_separated_source(client, test_db):
    """`_apply_common_filters` turns a multi-value `source` into an IN clause."""
    make_job(test_db, url="https://x.com/a", source="s1", h1b_verdict="likely")
    make_job(test_db, url="https://x.com/b", source="s2", h1b_verdict="unknown")
    make_job(test_db, url="https://x.com/c", source="s3", h1b_verdict="unlikely")
    r = assert_clean(client.get("/api/jobs/verdicts/list?source=s1,s2"), 200)
    assert r.json() == ["likely", "unknown"]


def test_filter_list_endpoints_reject_a_malformed_search_id(client):
    """`_apply_common_filters` routes `search_id` through `uuid_filter`, so junk
    is a 422 here exactly as it is on the list endpoint."""
    for path in ("/api/jobs/companies/list", "/api/jobs/sources/list",
                 "/api/jobs/verdicts/list"):
        assert_clean(client.get(f"{path}?search_id=not-a-uuid"), 422)


# ── /feed-stats and /unscored-ids ────────────────────────────────────────────

def test_feed_stats_counts_todays_arrivals_and_unscored(client, test_db, pg_cast_shim):
    from datetime import datetime, timezone, timedelta
    yesterday = datetime.now(timezone.utc) - timedelta(days=2)
    make_job(test_db, url="https://x.com/a", status="new", cv_scores={})
    make_job(test_db, url="https://x.com/b", status="saved", cv_scores={"PM": 70})
    old = make_job(test_db, url="https://x.com/c", status="new", cv_scores={})
    old.discovered_at = yesterday
    test_db.commit()
    body = assert_clean(client.get("/api/jobs/feed-stats"), 200).json()
    assert body["arrived_today"] == 2          # the two rows created just now
    assert body["unscored"] == 2               # both `{}`-scored rows, any age


def test_unscored_ids_returns_only_unscored_new_and_saved(client, test_db, pg_cast_shim):
    a = make_job(test_db, url="https://x.com/a", status="new", cv_scores={})
    make_job(test_db, url="https://x.com/b", status="new", cv_scores={"PM": 60})
    make_job(test_db, url="https://x.com/c", status="ignored", cv_scores={})
    ids = assert_clean(client.get("/api/jobs/unscored-ids"), 200).json()["ids"]
    # Raw SQL, so the id comes back in whatever spelling the driver stores
    # (SQLite: bare hex; Postgres: dashed) — normalise before comparing.
    assert [_uuid.UUID(i) for i in ids] == [a.id]


def test_unscored_ids_honours_the_limit(client, test_db, pg_cast_shim):
    for i in range(3):
        make_job(test_db, url=f"https://x.com/{i}", status="new", cv_scores={})
    assert len(client.get("/api/jobs/unscored-ids?limit=2").json()["ids"]) == 2


# ── POST /save-from-extension — the enrichment branches ──────────────────────

def test_resaving_a_skipped_job_puts_it_back_in_the_feed(client, test_db):
    """`skip` is the user's "not now"; saving the same posting again clears it."""
    job = make_job(test_db, url="https://x.com/one", company="Acme",
                   title="PM", status="skip")
    r = assert_clean(client.post("/api/jobs/save-from-extension", json={
        "title": "PM", "company": "Acme", "url": "https://x.com/one"}), 200)
    body = r.json()
    assert body == {"id": str(job.id), "company": "Acme", "title": "PM",
                    "new": False, "saved": True, "status": "new"}
    test_db.refresh(job)
    assert job.status == "new"


def test_resaving_an_ignored_job_explains_why_it_stays_out(client, test_db):
    make_job(test_db, url="https://x.com/one", company="Acme", title="PM",
             status="ignored")
    body = assert_clean(client.post("/api/jobs/save-from-extension", json={
        "title": "PM", "company": "Acme", "url": "https://x.com/one"}), 200).json()
    assert body["saved"] is False and body["status"] == "ignored"
    assert "stays out of the feed" in body["reason"]


def test_resaving_backfills_a_missing_description(client, test_db, monkeypatch):
    """A second capture that carries the description fills in the row the first
    one left bare, and re-runs the salary pass over it."""
    import backend.analyzer.h1b_checker as h1b
    seen = {}

    async def _median(db, name, allow_live=False):
        seen["company"] = name
        return {"median_salary": 175000}

    monkeypatch.setattr(h1b, "resolve_company_h1b", _median)
    job = make_job(test_db, url="https://x.com/one", company="Acme", title="PM",
                   status="new", description=None)
    assert_clean(client.post("/api/jobs/save-from-extension", json={
        "title": "PM", "company": "Acme", "url": "https://x.com/one",
        "description": "We pay $150,000 - $200,000 per year."}), 200)
    test_db.refresh(job)
    assert job.description.startswith("We pay")
    assert seen["company"] == "Acme"


def test_resaving_does_not_overwrite_an_existing_description(client, test_db):
    job = make_job(test_db, url="https://x.com/one", company="Acme", title="PM",
                   status="new", description="original")
    assert_clean(client.post("/api/jobs/save-from-extension", json={
        "title": "PM", "company": "Acme", "url": "https://x.com/one",
        "description": "replacement"}), 200)
    test_db.refresh(job)
    assert job.description == "original"


def test_a_failing_h1b_scan_does_not_fail_the_save(client, test_db, monkeypatch):
    """The analysis pass is best-effort: the row is still written when it raises."""
    import backend.analyzer.h1b_checker as h1b

    async def _boom(job, db):
        raise RuntimeError("MyVisaJobs down")

    monkeypatch.setattr(h1b, "check_job_h1b", _boom)
    body = assert_clean(client.post("/api/jobs/save-from-extension", json={
        "title": "PM", "company": "Acme", "url": "https://x.com/new"}), 200).json()
    assert body["new"] is True and body["saved"] is True


def test_a_body_exclusion_hit_is_saved_as_ignored_with_the_phrase(client, test_db, monkeypatch):
    import backend.analyzer.h1b_checker as h1b

    async def _flag(job, db):
        job.h1b_jd_flag = True
        job._h1b_matched_phrase = "no sponsorship"

    monkeypatch.setattr(h1b, "check_job_h1b", _flag)
    body = assert_clean(client.post("/api/jobs/save-from-extension", json={
        "title": "PM", "company": "Acme", "url": "https://x.com/new",
        "description": "text"}), 200).json()
    assert body["status"] == "ignored" and body["saved"] is False
    assert body["reason"] == "description matched the excluded phrase 'no sponsorship'"


@pytest.mark.parametrize("depth", ["light", "full"])
def test_auto_score_is_launched_for_a_kept_extension_save(client, test_db, monkeypatch, depth):
    make_search(test_db, name="Extension", search_mode="extension",
                auto_scoring_depth=depth)
    calls = []
    import backend.api.routes_jobs as rj
    monkeypatch.setattr(rj, "launch_background",
                        lambda *a, **kw: calls.append(kw) or "run-1")
    assert_clean(client.post("/api/jobs/save-from-extension", json={
        "title": "PM", "company": "Acme", "url": "https://x.com/new"}), 200)
    assert len(calls) == 1
    assert calls[0]["func_kwargs"]["depth"] == depth
    assert calls[0]["scope_key"].endswith(":extension")


def test_auto_score_is_skipped_when_the_extension_search_opted_out(client, test_db, monkeypatch):
    make_search(test_db, name="Extension", search_mode="extension",
                auto_scoring_depth="off")
    calls = []
    import backend.api.routes_jobs as rj
    monkeypatch.setattr(rj, "launch_background",
                        lambda *a, **kw: calls.append(kw) or "run-1")
    assert_clean(client.post("/api/jobs/save-from-extension", json={
        "title": "PM", "company": "Acme", "url": "https://x.com/new"}), 200)
    assert calls == []


def test_a_duplicate_auto_score_launch_is_swallowed(client, test_db, monkeypatch):
    """The save is the user's action; a scoring run already in flight for the
    same job must not turn it into an error."""
    from backend.job_monitor import JobAlreadyRunningError
    make_search(test_db, name="Extension", search_mode="extension",
                auto_scoring_depth="light")
    import backend.api.routes_jobs as rj

    def _busy(*a, **kw):
        raise JobAlreadyRunningError("analyze_job", 3.0)

    monkeypatch.setattr(rj, "launch_background", _busy)
    body = assert_clean(client.post("/api/jobs/save-from-extension", json={
        "title": "PM", "company": "Acme", "url": "https://x.com/new"}), 200).json()
    assert body["saved"] is True


def test_an_unexpected_auto_score_failure_is_swallowed(client, test_db, monkeypatch):
    make_search(test_db, name="Extension", search_mode="extension",
                auto_scoring_depth="light")
    import backend.api.routes_jobs as rj

    def _boom(*a, **kw):
        raise RuntimeError("no event loop")

    monkeypatch.setattr(rj, "launch_background", _boom)
    body = assert_clean(client.post("/api/jobs/save-from-extension", json={
        "title": "PM", "company": "Acme", "url": "https://x.com/new"}), 200).json()
    assert body["saved"] is True


def test_extension_search_title_include_miss_is_saved_as_ignored(client, test_db):
    make_search(test_db, name="Extension", search_mode="extension",
                title_include_keywords=["manager"], auto_scoring_depth="off")
    body = assert_clean(client.post("/api/jobs/save-from-extension", json={
        "title": "Chef", "company": "Acme", "url": "https://x.com/new"}), 200).json()
    assert body["status"] == "ignored"
    assert "matches none of the required keywords" in body["reason"]


def test_extension_search_title_exclude_hit_is_saved_as_ignored(client, test_db):
    make_search(test_db, name="Extension", search_mode="extension",
                title_exclude_keywords=["intern"], auto_scoring_depth="off")
    body = assert_clean(client.post("/api/jobs/save-from-extension", json={
        "title": "Product Intern", "company": "Acme", "url": "https://x.com/new"}), 200).json()
    assert body["status"] == "ignored"
    assert "'intern'" in body["reason"]


def test_extension_search_company_exclude_is_saved_as_ignored(client, test_db):
    make_search(test_db, name="Extension", search_mode="extension",
                company_exclude=["Acme"], auto_scoring_depth="off")
    body = assert_clean(client.post("/api/jobs/save-from-extension", json={
        "title": "PM", "company": "acme", "url": "https://x.com/new"}), 200).json()
    assert body["status"] == "ignored"
    assert body["reason"] == "company excluded by 'Acme'"


# ── PATCH /{job_id} — the on-save scoring arms ───────────────────────────────

def test_saving_a_job_launches_the_on_save_score(client, test_db, monkeypatch):
    set_setting(test_db, "on_save_action", "full")
    job = make_job(test_db)
    calls = []
    import backend.api.routes_jobs as rj
    monkeypatch.setattr(rj, "launch_background",
                        lambda *a, **kw: calls.append(kw) or "run-1")
    assert_clean(client.patch(f"/api/jobs/{job.id}", json={"saved": True}), 200)
    assert calls and calls[0]["func_kwargs"]["depth"] == "full"
    assert calls[0]["scope_key"].endswith(":on-save")


def test_on_save_scoring_is_off_by_default(client, test_db, monkeypatch):
    job = make_job(test_db)
    calls = []
    import backend.api.routes_jobs as rj
    monkeypatch.setattr(rj, "launch_background",
                        lambda *a, **kw: calls.append(kw) or "run-1")
    assert_clean(client.patch(f"/api/jobs/{job.id}", json={"saved": True}), 200)
    assert calls == []


def test_on_save_scoring_is_skipped_for_an_already_scored_job(client, test_db, monkeypatch):
    set_setting(test_db, "on_save_action", "light")
    job = make_job(test_db, cv_scores={"PM": 71})
    calls = []
    import backend.api.routes_jobs as rj
    monkeypatch.setattr(rj, "launch_background",
                        lambda *a, **kw: calls.append(kw) or "run-1")
    assert_clean(client.patch(f"/api/jobs/{job.id}", json={"saved": True}), 200)
    assert calls == []


def test_a_duplicate_on_save_score_does_not_fail_the_save(client, test_db, monkeypatch):
    from backend.job_monitor import JobAlreadyRunningError
    set_setting(test_db, "on_save_action", "light")
    job = make_job(test_db)
    import backend.api.routes_jobs as rj

    def _busy(*a, **kw):
        raise JobAlreadyRunningError("analyze_job", 1.0)

    monkeypatch.setattr(rj, "launch_background", _busy)
    assert_clean(client.patch(f"/api/jobs/{job.id}", json={"saved": True}), 200)
    test_db.refresh(job)
    assert job.saved is True


def test_an_unexpected_on_save_score_failure_does_not_fail_the_save(client, test_db, monkeypatch):
    set_setting(test_db, "on_save_action", "light")
    job = make_job(test_db)
    import backend.api.routes_jobs as rj

    def _boom(*a, **kw):
        raise RuntimeError("no loop")

    monkeypatch.setattr(rj, "launch_background", _boom)
    assert_clean(client.patch(f"/api/jobs/{job.id}", json={"saved": True}), 200)
    test_db.refresh(job)
    assert job.saved is True


def test_applying_reuses_an_existing_application_and_company(client, test_db):
    """The compound "applied" action reports what it created; when both already
    exist it creates neither and says so with two nulls."""
    from backend.models.db import Application
    job = make_job(test_db, company="Acme")
    make_company(test_db, name="Acme")
    test_db.add(Application(job_id=job.id, status="applied"))
    test_db.commit()
    body = assert_clean(client.patch(f"/api/jobs/{job.id}",
                                     json={"status": "applied"}), 200).json()
    assert body["created_application_id"] is None
    assert body["created_company_id"] is None


# ── POST /cache-applied ──────────────────────────────────────────────────────

def test_cache_applied_queues_only_uncached_applied_jobs(client, test_db, monkeypatch):
    import backend.api.routes_applications as ra
    queued = []

    async def _spy(job_id, url):
        queued.append((job_id, url))

    monkeypatch.setattr(ra, "_cache_job_page", _spy)
    want = make_job(test_db, url="https://x.com/a", status="applied")
    make_job(test_db, url="https://x.com/b", status="new")            # wrong status
    make_job(test_db, url=None, status="applied", external_id="no-url")  # no url
    cached = make_job(test_db, url="https://x.com/d", status="applied")
    cached.cached_page_html = "<p>already</p>"
    test_db.commit()
    r = assert_clean(client.post("/api/jobs/cache-applied"), 200)
    assert r.json() == {"queued": 1}
    assert queued == [(str(want.id), "https://x.com/a")]


def test_cache_applied_with_nothing_to_do_is_zero(client):
    assert client.post("/api/jobs/cache-applied").json() == {"queued": 0}


# ── GET /{job_id}/cached-page ────────────────────────────────────────────────

def test_cached_page_renders_the_reader_shell_with_the_cache_date(client, test_db):
    from datetime import datetime, timezone
    job = make_job(test_db)
    job.cached_page_html = "<h1>Senior PM</h1><p>Body</p>"
    job.page_cached_at = datetime(2026, 3, 14, tzinfo=timezone.utc)
    test_db.commit()
    r = assert_clean(client.get(f"/api/jobs/{job.id}/cached-page"), 200)
    assert "<h1>Senior PM</h1>" in r.text
    assert "Cached on Mar 14, 2026" in r.text
    assert r.headers["content-security-policy"].startswith("sandbox;")


def test_cached_page_without_a_timestamp_says_unknown(client, test_db):
    job = make_job(test_db)
    job.cached_page_html = "<p>Body</p>"
    test_db.commit()
    r = assert_clean(client.get(f"/api/jobs/{job.id}/cached-page"), 200)
    assert "Cached on Unknown" in r.text


# ── GET /{job_id}/frame-check ────────────────────────────────────────────────

def test_frame_check_without_a_url_is_not_embeddable(client, test_db):
    job = make_job(test_db, url=None, external_id="fc-no-url")
    assert client.get(f"/api/jobs/{job.id}/frame-check").json() == {"embeddable": False}


def test_frame_check_allows_a_page_with_no_framing_headers(client, test_db, monkeypatch):
    _patch_safe_get(monkeypatch, _Resp(headers={}))
    job = make_job(test_db)
    assert client.get(f"/api/jobs/{job.id}/frame-check").json() == {"embeddable": True}


@pytest.mark.parametrize("headers", [
    {"x-frame-options": "DENY"},
    {"x-frame-options": "SAMEORIGIN"},
    {"content-security-policy": "frame-ancestors 'self'"},
    {"content-security-policy": "FRAME-ANCESTORS 'none'"},
])
def test_frame_check_blocks_on_a_confident_framing_signal(client, test_db, monkeypatch, headers):
    _patch_safe_get(monkeypatch, _Resp(headers=headers))
    job = make_job(test_db)
    assert client.get(f"/api/jobs/{job.id}/frame-check").json() == {"embeddable": False}


def test_frame_check_refuses_an_unsafe_url(client, test_db, monkeypatch):
    from backend.scraper._shared.url_safety import UnsafeURLError
    _patch_safe_get(monkeypatch, UnsafeURLError("private range"))
    job = make_job(test_db)
    assert client.get(f"/api/jobs/{job.id}/frame-check").json() == {"embeddable": False}


def test_frame_check_treats_a_fetch_error_as_embeddable(client, test_db, monkeypatch):
    """Unknown is not blocked — the browser still gets to try the live frame."""
    _patch_safe_get(monkeypatch, RuntimeError("connection reset"))
    job = make_job(test_db)
    assert client.get(f"/api/jobs/{job.id}/frame-check").json() == {"embeddable": True}


def test_frame_check_missing_job_is_404(client):
    assert_clean(client.get(f"/api/jobs/{_uuid.uuid4()}/frame-check"), 404)


# ── _inject_base ─────────────────────────────────────────────────────────────

def test_inject_base_puts_the_tag_just_after_head():
    from backend.api.routes_jobs import _inject_base
    out = _inject_base("<html><head><title>T</title></head><body>x</body></html>",
                       "https://boards.example.com/jobs/1")
    assert '<head><base href="https://boards.example.com/jobs/1">' in out


def test_inject_base_prepends_when_there_is_no_head():
    from backend.api.routes_jobs import _inject_base
    out = _inject_base("<p>bare</p>", "https://e.com/j")
    assert out.startswith('<base href="https://e.com/j">')


def test_inject_base_strips_an_embedded_csp_meta():
    from backend.api.routes_jobs import _inject_base
    raw = ('<html><head><meta http-equiv="Content-Security-Policy" '
           'content="default-src \'none\'"><title>T</title></head><body>b</body></html>')
    out = _inject_base(raw, "https://e.com/j")
    assert "Content-Security-Policy" not in out
    assert "<title>T</title>" in out


def test_inject_base_escapes_the_url():
    from backend.api.routes_jobs import _inject_base
    out = _inject_base("<p>x</p>", 'https://e.com/j?a="b"')
    assert '&quot;b&quot;' in out


# ── GET /{job_id}/live-page ──────────────────────────────────────────────────

_LONG_BODY = "<html><head></head><body><p>" + ("Responsibilities. " * 40) + "</p></body></html>"


def test_live_page_returns_the_pages_own_html_and_warms_the_cache(client, test_db, monkeypatch):
    _patch_safe_get(monkeypatch, _Resp(text=_LONG_BODY, url="https://e.com/final"))
    job = make_job(test_db)
    r = assert_clean(client.get(f"/api/jobs/{job.id}/live-page"), 200)
    assert '<base href="https://e.com/final">' in r.text
    assert r.headers["content-security-policy"].startswith("sandbox;")
    test_db.refresh(job)
    assert job.cached_page_html and "Responsibilities" in job.cached_page_text


def test_live_page_never_overwrites_an_existing_snapshot(client, test_db, monkeypatch):
    _patch_safe_get(monkeypatch, _Resp(text=_LONG_BODY, url="https://e.com/final"))
    job = make_job(test_db)
    job.cached_page_html = "<p>the original snapshot</p>"
    test_db.commit()
    assert_clean(client.get(f"/api/jobs/{job.id}/live-page"), 200)
    test_db.refresh(job)
    assert job.cached_page_html == "<p>the original snapshot</p>"


def test_live_page_without_a_url_is_404(client, test_db):
    job = make_job(test_db, url=None, external_id="lp-no-url")
    r = assert_clean(client.get(f"/api/jobs/{job.id}/live-page"), 404)
    assert "No posting URL" in r.text


def test_live_page_missing_job_is_404(client):
    assert_clean(client.get(f"/api/jobs/{_uuid.uuid4()}/live-page"), 404)


def test_live_page_refuses_an_unsafe_url(client, test_db, monkeypatch):
    from backend.scraper._shared.url_safety import UnsafeURLError
    _patch_safe_get(monkeypatch, UnsafeURLError("loopback"))
    job = make_job(test_db)
    r = assert_clean(client.get(f"/api/jobs/{job.id}/live-page"), 400)
    assert "URL not allowed" in r.text


def test_live_page_upstream_failure_is_502(client, test_db, monkeypatch):
    _patch_safe_get(monkeypatch, RuntimeError("timed out"))
    job = make_job(test_db)
    r = assert_clean(client.get(f"/api/jobs/{job.id}/live-page"), 502)
    assert "Could not fetch posting" in r.text


def test_live_page_http_error_status_is_502(client, test_db, monkeypatch):
    _patch_safe_get(monkeypatch, _Resp(text="nope", raise_exc=RuntimeError("403")))
    job = make_job(test_db)
    assert_clean(client.get(f"/api/jobs/{job.id}/live-page"), 502)


def test_live_page_reraises_an_httpexception_from_the_fetch(client, test_db, monkeypatch):
    """An HTTPException raised inside the fetch block keeps its own status
    instead of being re-wrapped as a generic 502."""
    from fastapi import HTTPException
    _patch_safe_get(monkeypatch, HTTPException(status_code=418, detail="teapot"))
    job = make_job(test_db)
    r = assert_clean(client.get(f"/api/jobs/{job.id}/live-page"), 418)
    assert "teapot" in r.text


def test_live_page_empty_response_is_502(client, test_db, monkeypatch):
    _patch_safe_get(monkeypatch, _Resp(text="   "))
    job = make_job(test_db)
    r = assert_clean(client.get(f"/api/jobs/{job.id}/live-page"), 502)
    assert "no content" in r.text


def test_live_page_client_side_shell_is_502(client, test_db, monkeypatch):
    """A JS app shell extracts to almost no text — that is a failure, not a page."""
    _patch_safe_get(monkeypatch, _Resp(text="<html><body><div id=root></div></body></html>"))
    job = make_job(test_db)
    r = assert_clean(client.get(f"/api/jobs/{job.id}/live-page"), 502)
    assert "rendered client-side" in r.text


def test_live_page_survives_a_failed_cache_write(client, test_db, monkeypatch):
    """Warming the cache is opportunistic; a commit failure rolls back and the
    page is still served."""
    _patch_safe_get(monkeypatch, _Resp(text=_LONG_BODY, url="https://e.com/final"))
    job = make_job(test_db)
    import backend.models.db as db_mod
    real_commit = db_mod.SessionLocal.class_.commit
    calls = {"n": 0}

    def _flaky(self, *a, **kw):
        calls["n"] += 1
        raise RuntimeError("disk full")

    monkeypatch.setattr(db_mod.SessionLocal.class_, "commit", _flaky)
    try:
        r = assert_clean(client.get(f"/api/jobs/{job.id}/live-page"), 200)
    finally:
        monkeypatch.setattr(db_mod.SessionLocal.class_, "commit", real_commit)
    assert calls["n"] >= 1
    assert '<base href="https://e.com/final">' in r.text


# ── _normalize_report ────────────────────────────────────────────────────────

def test_normalize_report_wraps_a_flat_report_under_its_cv_name():
    from backend.api.routes_jobs import _normalize_report
    out = _normalize_report({"summary": "s", "scored_with": "PM"}, "Other")
    assert out == {"PM": {"summary": "s"}}


def test_normalize_report_falls_back_to_best_cv_then_unknown():
    from backend.api.routes_jobs import _normalize_report
    assert _normalize_report({"summary": "s"}, "PM") == {"PM": {"summary": "s"}}
    assert _normalize_report({"summary": "s"}, None) == {"Unknown": {"summary": "s"}}


def test_normalize_report_leaves_an_already_nested_report_alone():
    from backend.api.routes_jobs import _normalize_report
    nested = {"PM": {"summary": "s"}}
    assert _normalize_report(nested, "PM") is nested


def test_normalize_report_passes_through_empty_and_non_dicts():
    from backend.api.routes_jobs import _normalize_report
    assert _normalize_report(None, "PM") is None
    assert _normalize_report({}, "PM") is None
    assert _normalize_report("text", "PM") == "text"
