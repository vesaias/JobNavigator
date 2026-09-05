"""R4-T0-01 · the migration list must not abort on its first bad statement.

`run_migrations()` used to share one session with no rollback, so the first
failure poisoned the transaction and every statement after it logged
`InFailedSqlTransaction` instead of running. On Postgres that silently no-ops
the whole tail; the SQLite fixture reproduces the ordering property (a failure
must not stop the list) even though it raises a different exception class.
"""
import pytest
from sqlalchemy import text

from backend.seed import run_migration_statements
from backend.tests.r4_support import client, _clear_running_state, _no_outbound  # noqa: F401


def test_one_bad_statement_does_not_stop_the_rest(test_db):
    stmts = [
        "CREATE TABLE r4_mig_a (id INTEGER)",
        "SELECT this_function_does_not_exist(1)",      # the poisoning statement
        "CREATE TABLE r4_mig_b (id INTEGER)",
        "CREATE TABLE r4_mig_c (id INTEGER)",
    ]
    failed = run_migration_statements(test_db, stmts)

    assert failed == [stmts[1]], "exactly the broken statement must be reported"
    for table in ("r4_mig_a", "r4_mig_b", "r4_mig_c"):
        test_db.execute(text(f"SELECT count(*) FROM {table}"))   # raises if missing


def test_every_statement_after_a_failure_still_commits(test_db):
    run_migration_statements(test_db, [
        "CREATE TABLE r4_mig_d (id INTEGER)",
        "THIS IS NOT SQL",
        "INSERT INTO r4_mig_d (id) VALUES (7)",
    ])
    assert test_db.execute(text("SELECT id FROM r4_mig_d")).scalar() == 7


def test_an_all_good_list_reports_nothing_failed(test_db):
    assert run_migration_statements(test_db, [
        "CREATE TABLE r4_mig_e (id INTEGER)",
        "INSERT INTO r4_mig_e (id) VALUES (1)",
    ]) == []


def test_an_empty_list_is_safe(test_db):
    assert run_migration_statements(test_db, []) == []


def test_the_cv_scores_backfill_casts_to_jsonb():
    """The statement that used to poison every fresh install.

    `jobs.cv_scores` is `Column(JSON)`, so create_all() builds it as native
    Postgres `json` on a new database and the jsonb_* functions have no overload
    for that type. Every reference must carry an explicit ::jsonb cast.
    """
    import backend.seed as seed
    import inspect

    src = inspect.getsource(seed.run_migrations)
    backfill = [line for line in src.splitlines() if "jsonb_typeof" in line or "jsonb_each_text" in line]
    assert backfill, "the cv_scores backfill statement disappeared"
    for line in backfill:
        assert "cv_scores::jsonb" in line, f"uncast cv_scores reaches a jsonb function: {line.strip()}"
