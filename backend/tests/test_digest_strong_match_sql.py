"""The daily digest's strong-match subquery must cast cv_scores to jsonb.

`jobs.cv_scores` is `Column(JSON)` -> native `json` in Postgres, and the
`jsonb_*` functions have no `json` overload. An uncast reference made
`send_digest` raise `COALESCE could not convert type jsonb to json`, so the
digest reported nothing every day. Same failure class as `unscored_filter`.
"""
import os
import re

import pytest
from sqlalchemy import create_engine, text

from backend.notifier.telegram import STRONG_MATCH_SQL


def test_every_cv_scores_reference_is_cast_to_jsonb():
    """No bare `cv_scores` may reach a jsonb function or a jsonb literal."""
    bare = [m.start() for m in re.finditer(r"cv_scores(?!::jsonb)", STRONG_MATCH_SQL)]
    assert not bare, f"uncast cv_scores at {bare}: {STRONG_MATCH_SQL}"


@pytest.mark.live
def test_the_strong_match_subquery_runs_on_postgres():
    """Read-only: one COUNT against the real column type."""
    url = os.getenv("DATABASE_URL", "")
    if not url.startswith("postgresql"):
        pytest.skip("no Postgres DATABASE_URL")
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            stmt = text(f"SELECT count(*) FROM jobs WHERE {STRONG_MATCH_SQL}")
            assert conn.execute(stmt, {"threshold": 60}).scalar() is not None
    finally:
        engine.dispose()
