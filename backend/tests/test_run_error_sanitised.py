"""A run error must not carry driver internals into the database or the API.

`JobRun.error` held `str(exc)` verbatim. For a DBAPI failure that string is the
driver module path, the failed statement and its bound parameters, and
`/api/monitor/history` returned all three to the browser.
"""
from sqlalchemy.orm import sessionmaker

from backend.job_monitor import MAX_RUN_ERROR_CHARS, sanitize_run_error

# The exact text a failed scrape_all run stored, shortened.
RAW_DB_ERROR = (
    "(psycopg2.errors.UndefinedFunction) operator does not exist: json = jsonb\n"
    "LINE 3: WHERE (jobs.cv_scores IS NULL OR jobs.cv_scores = '{}'::json...\n"
    "HINT:  No operator matches the given name and argument types.\n"
    "\n"
    "[SQL: SELECT jobs.id, jobs.cv_scores FROM jobs WHERE jobs.cv_scores IS NULL]\n"
    "[parameters: {'status': 'new'}]\n"
    "(Background on this error at: https://sqlalche.me/e/20/f405)"
)

# Markers backend/tests/r4_support.py forbids in any response body.
LEAK_MARKERS = ("psycopg2.errors", "sqlalchemy.exc", "[SQL:", "[parameters:")


def test_the_sanitiser_drops_the_statement_the_parameters_and_the_driver_path():
    clean = sanitize_run_error(RAW_DB_ERROR)
    for marker in LEAK_MARKERS:
        assert marker not in clean, f"{marker!r} survived: {clean}"
    # The diagnosis itself stays readable.
    assert clean.startswith("UndefinedFunction: operator does not exist: json = jsonb")


def test_the_sanitiser_leaves_an_application_message_alone():
    reason = "Scoring failed: provider returned no usable JSON"
    assert sanitize_run_error(reason) == reason


def test_the_sanitiser_is_idempotent_and_bounded():
    once = sanitize_run_error(RAW_DB_ERROR)
    assert sanitize_run_error(once) == once
    assert sanitize_run_error(None) is None
    assert sanitize_run_error("") is None
    long = sanitize_run_error("x" * (MAX_RUN_ERROR_CHARS * 5))
    assert len(long) == MAX_RUN_ERROR_CHARS + len("...")


def test_finishing_a_run_stores_the_sanitised_text(test_db, monkeypatch):
    """The single writer of JobRun.error sanitises, so no raw string is stored."""
    import uuid

    from backend.models.db import JobRun
    import backend.job_monitor as jm

    TestSession = sessionmaker(bind=test_db.get_bind())
    monkeypatch.setattr(jm, "SessionLocal", TestSession)

    run_id = uuid.uuid4()
    jm._insert_job_run(run_id, "scrape_all", "scheduler", None)
    jm._finish_job_run(run_id, "failed", None, RAW_DB_ERROR)

    s = TestSession()
    stored = s.query(JobRun).filter_by(job_type="scrape_all").first().error
    s.close()
    for marker in LEAK_MARKERS:
        assert marker not in stored, f"{marker!r} reached the column: {stored}"


def test_the_history_endpoint_never_returns_a_stored_driver_error(api_client, test_db):
    """Rows written before the sanitiser landed must still come back clean."""
    from backend.models.db import JobRun, Setting

    test_db.add(Setting(key="dashboard_api_key", value=""))
    test_db.add(JobRun(job_type="scrape_all", trigger="scheduler", status="failed"))
    test_db.commit()
    # Write past the sanitising writer: this is what the column already holds
    # for the 11 scrape_all runs the json/jsonb bug poisoned.
    test_db.query(JobRun).filter_by(job_type="scrape_all").update(
        {"error": RAW_DB_ERROR}, synchronize_session=False)
    test_db.commit()

    body = api_client.get("/api/monitor/history").text
    assert "scrape_all" in body, body[:300]
    for marker in LEAK_MARKERS:
        assert marker not in body, f"{marker!r} reached the response: {body[:300]}"
