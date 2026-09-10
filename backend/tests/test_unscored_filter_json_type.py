"""The "not yet scored" predicate must never compile to a jsonb comparison.

`jobs.cv_scores` is `Column(JSON)`, which Postgres builds as native `json`.
Postgres has no `json = jsonb` operator, so a `'{}'::jsonb` literal in this
filter raises UndefinedFunction. That aborted every auto-scoring pass after a
scrape, and the only trace was the `error` column of the `scrape_all` JobRun.
"""
import os

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.dialects import postgresql

from backend.analyzer.cv_scorer import unscored_filter
from backend.models.db import Job


def _count_unscored():
    return select(func.count(Job.id)).where(unscored_filter())


def _compiled_for_postgres():
    return str(_count_unscored().compile(
        dialect=postgresql.dialect(),
        compile_kwargs={"literal_binds": True},
    ))


def test_the_unscored_filter_carries_no_jsonb_cast():
    """The compiled Postgres SQL touches cv_scores and mentions no jsonb."""
    sql = _compiled_for_postgres().lower()
    assert "cv_scores" in sql, sql
    assert "jsonb" not in sql, sql


def test_the_unscored_filter_selects_null_and_empty_scores(test_db):
    """Both "no scores" shapes match, and a scored job does not."""
    import uuid

    from sqlalchemy import null as sa_null

    for tag, scores in (("null", sa_null()), ("empty", {}), ("scored", {"PM": 70})):
        test_db.add(Job(id=uuid.uuid4(), external_id=tag, content_hash=tag,
                        company="Acme", title=tag, status="new", cv_scores=scores))
    test_db.commit()

    assert test_db.execute(_count_unscored()).scalar() == 2


@pytest.mark.live
def test_the_unscored_filter_runs_on_postgres():
    """Compiling is not proof. Run the real predicate against the real column type.

    Read-only: one COUNT. Skips wherever the tests do not have a Postgres URL.
    """
    url = os.getenv("DATABASE_URL", "")
    if not url.startswith("postgresql"):
        pytest.skip("no Postgres DATABASE_URL")
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            assert conn.execute(_count_unscored()).scalar() is not None
    finally:
        engine.dispose()
