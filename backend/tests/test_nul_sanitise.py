"""NUL-byte sanitisation at the Job-model choke point + per-job batch isolation.

Postgres rejects any text value containing \\x00 with "A string literal cannot
contain NUL (0x00) characters" and aborts the whole transaction — this bit
Jobright (job titles/descriptions occasionally carry stray control bytes from
its API) and sank the entire scrape run (nothing saved, not even the clean
jobs in the same batch). The fix has two parts, both exercised here:

1. `backend.models.db.sanitize_text` + SQLAlchemy attribute-`set` listeners on
   every String/Text column of `Job` (see models/db.py, near `_clean_job_url`)
   strip NUL/C0 control chars at assignment time, so it applies no matter
   which scraper/source module (or the extension save/import endpoints)
   builds the row.
2. Every source's per-job insert loop wraps `db.add(job); db.flush()` in a
   SAVEPOINT (`db.begin_nested()`) and now catches *any* exception (not just
   `IntegrityError`) so one poisoned/failing row is skipped and logged
   instead of sinking the whole batch.
"""
import asyncio

import pytest
import sqlalchemy.orm as sa_orm

from backend.models.db import Job, Search, sanitize_text


# ── 1. sanitize_text() the raw helper ───────────────────────────────────────

def test_sanitize_text_strips_nul_and_control_chars():
    assert sanitize_text("Senior\x00Engineer") == "SeniorEngineer"
    assert sanitize_text("a\x01b\x1fc") == "abc"


def test_sanitize_text_keeps_newlines_tabs_and_returns():
    s = "line1\nline2\ttabbed\r\n"
    assert sanitize_text(s) == s


def test_sanitize_text_passthrough_for_non_strings_and_empty():
    assert sanitize_text(None) is None
    assert sanitize_text("") == ""
    assert sanitize_text(42) == 42


# ── 2. Model-level round trip: a job dict with NUL bytes survives insert ───

def test_job_with_nul_in_title_and_description_round_trips_clean(test_db):
    job = Job(
        external_id="ext-nul-1",
        content_hash="hash-nul-1",
        company="Acme\x00Corp",
        title="Senior\x00Engineer",
        url="https://example.com/jobs/\x001",
        description="Great role\x00 with \x01 control \x1fchars\nand a real newline.",
        source="jobright",
        status="new",
    )
    test_db.add(job)
    test_db.commit()
    test_db.refresh(job)

    for field in (job.company, job.title, job.url, job.description, job.external_id):
        assert "\x00" not in field
        assert "\x01" not in field
        assert "\x1f" not in field

    assert job.company == "AcmeCorp"
    assert job.title == "SeniorEngineer"
    assert job.url == "https://example.com/jobs/1"
    assert "\n" in job.description  # real newline preserved
    assert "Great role" in job.description and "control" in job.description


def test_job_field_assignment_after_construction_is_also_sanitised(test_db):
    """The listener fires on attribute `set`, not just constructor kwargs —
    scrapers set salary_source / description etc. after building the Job()."""
    job = Job(external_id="ext-nul-2", content_hash="hash-nul-2", title="OK", company="Co")
    job.description = "desc with \x00 nul"
    job.location = "Remote\x00"
    assert job.description == "desc with  nul"
    assert job.location == "Remote"


# ── 3. Batch isolation: one failing job doesn't sink the others ───────────

def test_batch_survives_one_poisoned_job(test_db, monkeypatch):
    """Reproduces the per-job savepoint pattern shared by every scraper source
    (backend/scraper/sources/{jobright,jobspy,levelsfyi,freehire,linkedin_personal}.py
    and company_pages.py): each job is added inside `db.begin_nested()` and a
    failure is now caught broadly (IntegrityError for dup keys, plus a
    catch-all Exception for anything else — e.g. the DataError Postgres would
    raise for a NUL byte that somehow got past sanitisation) so the batch
    keeps going instead of aborting with nothing saved.
    """
    original_add = sa_orm.Session.add

    def flaky_add(self, instance, *a, **kw):
        if isinstance(instance, Job) and instance.title == "Boom Job":
            raise RuntimeError("simulated insert failure (e.g. a DataError)")
        return original_add(self, instance, *a, **kw)

    monkeypatch.setattr(sa_orm.Session, "add", flaky_add)

    jobs = [
        Job(external_id="e1", content_hash="c1", title="Good Job 1", company="A", status="new"),
        Job(external_id="e2", content_hash="c2", title="Boom Job", company="B", status="new"),
        Job(external_id="e3", content_hash="c3", title="Good Job 2", company="C", status="new"),
    ]

    saved = 0
    for job in jobs:
        try:
            with test_db.begin_nested():
                test_db.add(job)
                test_db.flush()
            saved += 1
        except Exception as e:
            logged = (job.title, str(e))  # what a source module logs — title + error
            assert logged[0] == "Boom Job"
            continue

    test_db.commit()

    assert saved == 2
    titles = {r[0] for r in test_db.query(Job.title).all()}
    assert titles == {"Good Job 1", "Good Job 2"}
    assert "Boom Job" not in titles


# ── 4. End-to-end: the real Jobright source module survives a poisoned job ─

def test_jobright_run_saves_clean_jobs_when_one_job_fails_to_insert(test_db, monkeypatch):
    """Exercises the actual fixed code path in backend/scraper/sources/jobright.py:
    a NUL byte in one job's title/description is stripped by the model-level
    sanitiser, and a second, unrelated insert failure on a different job is
    caught by the broadened except-and-continue so the run still saves the
    clean jobs instead of coming back with `new_jobs=0` for the whole batch.
    """
    from backend.scraper.sources import jobright as jobright_mod

    search = Search(name="JR test", search_mode="jobright", search_term="engineer",
                     location="", min_fit_score=0, require_salary=False,
                     title_include_keywords=[], title_exclude_keywords=[],
                     company_exclude=[])
    test_db.add(search)
    test_db.commit()

    raw_jobs = [
        {
            "jobResult": {"jobId": "1", "jobTitle": "Nul\x00Byte Engineer",
                          "applyLink": "https://example.com/apply/1",
                          "jobSummary": "Great\x00 role"},
            "companyResult": {"companyName": "Acme"},
        },
        {
            "jobResult": {"jobId": "2", "jobTitle": "Boom Job",
                          "applyLink": "https://example.com/apply/2"},
            "companyResult": {"companyName": "Boomcorp"},
        },
        {
            "jobResult": {"jobId": "3", "jobTitle": "Plain Engineer",
                          "applyLink": "https://example.com/apply/3"},
            "companyResult": {"companyName": "Widgets Inc"},
        },
    ]

    async def fake_ensure_session(force_relogin=False):
        return "sess"

    async def fake_fetch_search_ssr(keyword, location=""):
        return raw_jobs, len(raw_jobs)

    async def fake_check_job_h1b(job, db, **kwargs):
        return None

    def fake_apply_salary_to_job(job, median=None):
        return None

    monkeypatch.setattr(jobright_mod, "_ensure_session", fake_ensure_session)
    monkeypatch.setattr(jobright_mod, "_fetch_search_ssr", fake_fetch_search_ssr)
    monkeypatch.setattr("backend.analyzer.h1b_checker.check_job_h1b", fake_check_job_h1b)
    monkeypatch.setattr("backend.analyzer.salary_extractor.apply_salary_to_job", fake_apply_salary_to_job)

    original_add = sa_orm.Session.add

    def flaky_add(self, instance, *a, **kw):
        if isinstance(instance, Job) and instance.company == "Boomcorp":
            raise RuntimeError("simulated insert failure")
        return original_add(self, instance, *a, **kw)

    monkeypatch.setattr(sa_orm.Session, "add", flaky_add)

    result = asyncio.run(jobright_mod.run(search))

    assert result["error"] is None
    # Boomcorp's job failed to insert; the other two must still have saved —
    # before the fix, one raising insert aborted the whole (uncommitted) batch.
    assert result["new_jobs"] == 2

    saved_companies = {r[0] for r in test_db.query(Job.company).all()}
    assert saved_companies == {"Acme", "Widgets Inc"}

    nul_job = test_db.query(Job).filter(Job.company == "Acme").first()
    assert nul_job is not None
    assert "\x00" not in nul_job.title
    assert nul_job.title == "NulByte Engineer"
    assert "\x00" not in (nul_job.description or "")
