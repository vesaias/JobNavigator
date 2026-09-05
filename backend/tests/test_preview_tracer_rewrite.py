"""/resumes/{id}/preview and /resumes/{id}/pdf must serve the same tracer-rewritten URLs, reusing one TracerLink per (owner, destination)."""
import pytest

from backend.api.routes_resumes import _rewrite_urls_with_tracers, preview_resume
from backend.models.db import Resume, Setting, TracerLink

RESUME_ID = "4d444444-44d4-44d4-8444-444444444444"


def _header():
    return {"header": {"name": "Dana", "contact_items": [
        {"text": "LinkedIn", "url": "https://linkedin.com/in/dana", "stub": "li"},
        {"text": "Portfolio", "url": "https://dana.example", "stub": "w"},
        {"text": "dana@example.com", "url": ""},
    ]}}


def _setup(db, enabled="true"):
    for k, v in [("tracer_links_enabled", enabled),
                 ("tracer_links_base_url", "https://track.example"),
                 ("tracer_links_url_style", "path")]:
        db.add(Setting(key=k, value=v))
    db.add(Resume(id=RESUME_ID, name="Base", is_base=True, json_data=_header()))
    db.commit()


def _html(db):
    return preview_resume(RESUME_ID, db=db).body.decode()


def test_preview_serves_the_tracked_urls(test_db):
    _setup(test_db)
    html = _html(test_db)

    links = test_db.query(TracerLink).filter(TracerLink.resume_id == RESUME_ID).all()
    assert len(links) == 2                      # the two items that have a URL
    for link in links:
        assert f"https://track.example/cv/{link.token}" in html
    # and none of the raw destinations survived
    assert "linkedin.com/in/dana" not in html
    assert "dana.example" not in html


def test_preview_then_pdf_mints_no_extra_links(test_db):
    """The PDF path calls the same helper — previewing first must not double up."""
    _setup(test_db)
    _html(test_db)
    after_preview = {l.token for l in test_db.query(TracerLink).all()}

    # what export_pdf does before handing the data to the renderer
    resume = test_db.query(Resume).filter(Resume.id == RESUME_ID).one()
    _rewrite_urls_with_tracers(resume.json_data or {}, RESUME_ID, test_db)

    assert {l.token for l in test_db.query(TracerLink).all()} == after_preview
    assert len(after_preview) == 2


def test_preview_and_pdf_carry_the_same_tokens(test_db):
    _setup(test_db)
    html = _html(test_db)
    resume = test_db.query(Resume).filter(Resume.id == RESUME_ID).one()
    pdf_data = _rewrite_urls_with_tracers(resume.json_data or {}, RESUME_ID, test_db)

    for item in pdf_data["header"]["contact_items"]:
        if item.get("url"):
            assert item["url"].startswith("https://track.example/cv/")
            assert item["url"] in html


def test_preview_is_untouched_when_tracing_is_off(test_db):
    _setup(test_db, enabled="false")
    html = _html(test_db)

    assert "linkedin.com/in/dana" in html
    assert test_db.query(TracerLink).count() == 0


def test_preview_still_404s_for_a_missing_resume(test_db):
    from fastapi import HTTPException
    _setup(test_db)
    with pytest.raises(HTTPException) as e:
        preview_resume("5e555555-55e5-45e5-8555-555555555555", db=test_db)
    assert e.value.status_code == 404
