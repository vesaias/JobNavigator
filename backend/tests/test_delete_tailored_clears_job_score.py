"""Deleting a tailored copy must clear its `Tailored` cv_scores entry, scoring_report entry, and any best_cv pointing at it."""
from backend.api.routes_resumes import delete_resume
from backend.models.db import Job, Resume

JOB_ID = "4d444444-44d4-44d4-8444-444444444444"
BASE_ID = "5e555555-55e5-45e5-8555-555555555555"
COPY_ID = "6f666666-66f6-46f6-8666-666666666666"
COPY2_ID = "7a777777-77a7-47a7-8777-777777777777"


def _job(db, scores, report=None, best="Tailored", best_score=35.0):
    db.add(Job(id=JOB_ID, external_id="ext-r3b05", title="PM", company="Anthropic",
               url="https://x.test/1", cv_scores=scores, scoring_report=report,
               best_cv=best, best_cv_score=best_score))


def _copies(db, *ids):
    db.add(Resume(id=BASE_ID, name="PM", is_base=True, json_data={}))
    for rid in ids:
        db.add(Resume(id=rid, name="PM → Anthropic", is_base=False,
                      parent_id=BASE_ID, job_id=JOB_ID, json_data={}))


def test_tailored_score_and_report_are_dropped_and_best_recomputed(test_db):
    _job(test_db, {"PM": 40, "Tailored": 35},
         report={"PM": {"summary": "base"}, "Tailored": {"summary": "tailored"}})
    _copies(test_db, COPY_ID)
    test_db.commit()

    delete_resume(COPY_ID, db=test_db)

    job = test_db.query(Job).one()
    assert job.cv_scores == {"PM": 40}
    assert "Tailored" not in (job.scoring_report or {})
    # the one remaining report unwraps back to the flat single-CV shape
    assert job.scoring_report == {"summary": "base", "scored_with": "PM"}
    assert job.best_cv == "PM"
    assert job.best_cv_score == 40.0


def test_best_is_cleared_when_tailored_was_the_only_score(test_db):
    _job(test_db, {"Tailored": 35}, report={"Tailored": {"summary": "t"}})
    _copies(test_db, COPY_ID)
    test_db.commit()

    delete_resume(COPY_ID, db=test_db)

    job = test_db.query(Job).one()
    assert job.cv_scores == {}
    assert job.scoring_report is None
    assert job.best_cv is None and job.best_cv_score is None


def test_another_tailored_copy_keeps_the_score(test_db):
    """The score belongs to whichever copy is current, not to the deleted one."""
    _job(test_db, {"PM": 40, "Tailored": 35})
    _copies(test_db, COPY_ID, COPY2_ID)
    test_db.commit()

    delete_resume(COPY_ID, db=test_db)

    job = test_db.query(Job).one()
    assert job.cv_scores == {"PM": 40, "Tailored": 35}
    assert job.best_cv == "Tailored"


def test_deleting_the_base_clears_its_children_jobs_too(test_db):
    """Deleting a base takes its copies with it — and their orphaned scores."""
    _job(test_db, {"PM": 40, "Tailored": 35})
    _copies(test_db, COPY_ID)
    test_db.commit()

    out = delete_resume(BASE_ID, db=test_db)

    assert out["children_deleted"] == 1
    job = test_db.query(Job).one()
    assert job.cv_scores == {"PM": 40}
    assert job.best_cv == "PM"


def test_job_without_a_tailored_score_is_left_alone(test_db):
    _job(test_db, {"PM": 40}, best="PM", best_score=40.0)
    _copies(test_db, COPY_ID)
    test_db.commit()

    delete_resume(COPY_ID, db=test_db)

    job = test_db.query(Job).one()
    assert job.cv_scores == {"PM": 40}
    assert job.best_cv == "PM" and job.best_cv_score == 40.0
