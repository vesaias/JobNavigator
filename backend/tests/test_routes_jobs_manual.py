"""POST /jobs/manual adds one hand-typed posting to the feed and creates no application; create_manual_job is a plain route function taking its Session as a parameter, so tests call it directly (no backend.main, no TestClient)."""
import pytest
from fastapi import BackgroundTasks, HTTPException

from backend.api.routes_jobs import create_manual_job
from backend.models.db import Application, Job


def _add(db, **over):
    body = {"title": "Senior Backend Engineer", "company": "Acme",
            "url": "https://acme.test/jobs/1"}
    body.update(over)
    return create_manual_job(body, BackgroundTasks(), db=db)


def test_new_status_writes_the_row(test_db):
    out = _add(test_db, status="new")

    assert out["created"] is True and out["status"] == "new"
    job = test_db.query(Job).one()
    assert (job.source, job.status, job.saved, job.seen) == ("manual", "new", False, True)
    # the modal's own path — a feed job carries no application
    assert test_db.query(Application).count() == 0


def test_saved_status_moves_the_saved_flag_with_it(test_db):
    """The feed writes `saved: true` with status='saved'; this path must match."""
    _add(test_db, status="saved")
    assert test_db.query(Job).one().saved is True


def test_status_defaults_to_new(test_db):
    assert _add(test_db)["status"] == "new"


@pytest.mark.parametrize("status", ["applied", "interview", "skip", "banana"])
def test_application_stages_and_junk_are_refused(test_db, status):
    """`applied` belongs to POST /applications, which also writes the Application row."""
    with pytest.raises(HTTPException) as e:
        _add(test_db, status=status)
    assert e.value.status_code == 400
    assert test_db.query(Job).count() == 0


@pytest.mark.parametrize("blank", ["title", "company", "url"])
def test_the_three_required_fields(test_db, blank):
    with pytest.raises(HTTPException) as e:
        _add(test_db, **{blank: ""})
    assert e.value.status_code == 400


def test_a_known_posting_keeps_its_status(test_db):
    """Pasting the URL of a job already applied to must not send it back to `new`."""
    _add(test_db, status="new")
    test_db.query(Job).one().status = "applied"
    test_db.commit()

    out = _add(test_db, status="saved")

    assert out["created"] is False and out["status"] == "applied"
    assert test_db.query(Job).count() == 1


def test_enrichment_is_queued_for_a_new_row(test_db):
    """Without the JD fetch the first score, tailor or cover letter pays for it."""
    bg = BackgroundTasks()
    create_manual_job({"title": "Dev", "company": "Acme", "url": "https://acme.test/j/2"},
                      bg, db=test_db)
    assert [t.func.__name__ for t in bg.tasks] == ["_cache_job_page", "_fetch_and_store_description"]
