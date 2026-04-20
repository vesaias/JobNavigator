"""Tests for the best_cv_score indexed numeric column on Job."""
import pytest


def test_best_cv_score_column_exists(test_db):
    from backend.models.db import Job
    assert hasattr(Job, "best_cv_score")


def test_best_cv_score_stores_float(test_db):
    from backend.models.db import Job
    job = Job(
        external_id="x1", content_hash="c1",
        company="Acme", title="Senior PM", url="https://x.com/1",
        best_cv_score=82.5,
    )
    test_db.add(job)
    test_db.commit()
    back = test_db.query(Job).filter(Job.external_id == "x1").first()
    assert abs(back.best_cv_score - 82.5) < 1e-6


def test_best_cv_score_defaults_null(test_db):
    """Unscored jobs have best_cv_score = None (NULL)."""
    from backend.models.db import Job
    job = Job(
        external_id="x2", content_hash="c2",
        company="Acme", title="PM Intern", url="https://x.com/2",
    )
    test_db.add(job)
    test_db.commit()
    back = test_db.query(Job).filter(Job.external_id == "x2").first()
    assert back.best_cv_score is None
