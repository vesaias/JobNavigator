"""A résumé and its cover letter for the same job share one tracer link/token; the row carries both FKs so rendering order never re-parents the click history."""
from backend.api.routes_resumes import _rewrite_urls_with_tracers, get_tracer_stats
from backend.api.routes_cover_letters import get_tracer_stats as get_cl_tracer_stats
from backend.models.db import CoverLetter, Job, Resume, Setting, TracerClickEvent, TracerLink

JOB_ID = "1a111111-11a1-41a1-8111-111111111111"
RESUME_ID = "2b222222-22b2-42b2-8222-222222222222"
CL_ID = "3c333333-33c3-43c3-8333-333333333333"


def _header():
    return {"header": {"name": "Dana", "contact_items": [
        {"text": "LinkedIn", "url": "linkedin.com/in/dana", "stub": "li"},
    ]}}


def _setup(db):
    for k, v in [("tracer_links_enabled", "true"),
                 ("tracer_links_base_url", "https://example.com"),
                 ("tracer_links_url_style", "param_jobid")]:
        db.add(Setting(key=k, value=v))
    db.add(Job(id=JOB_ID, short_id=20892, external_id="ext-r3b03", title="PM",
                company="Anthropic", url="https://x.test/1"))
    db.add(Resume(id=RESUME_ID, name="Base → Anthropic", job_id=JOB_ID, json_data=_header()))
    db.add(CoverLetter(id=CL_ID, name="Anthropic", job_id=JOB_ID, resume_id=RESUME_ID,
                       json_data=_header()))
    db.commit()


def _render_resume(db):
    return _rewrite_urls_with_tracers(_header(), RESUME_ID, db, job_id=JOB_ID)


def _render_letter(db):
    return _rewrite_urls_with_tracers(_header(), None, db, cover_letter_id=CL_ID, job_id=JOB_ID)


def test_both_documents_report_after_every_render_order(test_db):
    _setup(test_db)

    _render_resume(test_db)
    assert len(get_tracer_stats(RESUME_ID, db=test_db)) == 1

    _render_letter(test_db)
    # the letter now reports it, and so does the résumé
    assert len(get_cl_tracer_stats(CL_ID, db=test_db)) == 1
    assert len(get_tracer_stats(RESUME_ID, db=test_db)) == 1, \
        "rendering the letter must not empty the résumé's tracer stats"

    _render_resume(test_db)
    assert len(get_tracer_stats(RESUME_ID, db=test_db)) == 1
    assert len(get_cl_tracer_stats(CL_ID, db=test_db)) == 1, \
        "re-rendering the résumé must not empty the letter's tracer stats"

    # one shared row, one token, owned by both
    links = test_db.query(TracerLink).all()
    assert len(links) == 1
    assert links[0].token == "20892li"
    assert str(links[0].resume_id) == RESUME_ID
    assert str(links[0].cover_letter_id) == CL_ID


def test_clicks_stay_attributed_across_renders(test_db):
    _setup(test_db)
    _render_resume(test_db)
    link = test_db.query(TracerLink).one()
    test_db.add(TracerClickEvent(tracer_link_id=link.id, is_likely_bot=False))
    test_db.commit()

    _render_letter(test_db)
    _render_resume(test_db)

    assert get_tracer_stats(RESUME_ID, db=test_db)[0]["clicks"] == 1
    assert get_cl_tracer_stats(CL_ID, db=test_db)[0]["clicks"] == 1
    # the row was never recreated, so the event still hangs off the same link
    assert test_db.query(TracerLink).one().id == link.id


def test_deleting_the_letter_leaves_the_resume_its_link(test_db):
    from backend.api.routes_cover_letters import delete_cover_letter
    _setup(test_db)
    _render_resume(test_db)
    _render_letter(test_db)

    delete_cover_letter(CL_ID, db=test_db)

    rows = get_tracer_stats(RESUME_ID, db=test_db)
    assert len(rows) == 1 and rows[0]["token"] == "20892li"
    assert test_db.query(TracerLink).one().cover_letter_id is None


def test_deleting_the_resume_leaves_the_letter_its_link(test_db):
    from backend.api.routes_resumes import delete_resume
    _setup(test_db)
    _render_resume(test_db)
    _render_letter(test_db)

    delete_resume(RESUME_ID, db=test_db)

    rows = get_cl_tracer_stats(CL_ID, db=test_db)
    assert len(rows) == 1 and rows[0]["token"] == "20892li"
    assert test_db.query(TracerLink).one().resume_id is None


def test_unshared_links_are_still_deleted_with_their_owner(test_db):
    """The release-instead-of-delete path must not leak rows for solo owners."""
    from backend.api.routes_resumes import delete_resume
    _setup(test_db)
    _render_resume(test_db)          # résumé-only link, no letter rendered

    delete_resume(RESUME_ID, db=test_db)

    assert test_db.query(TracerLink).count() == 0
