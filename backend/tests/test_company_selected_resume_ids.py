"""Company.selected_resume_ids replaces selected_cv_ids (Task 6)."""
import uuid
from backend.models.db import Company, Resume


def test_company_has_selected_resume_ids_column():
    cols = {c.name for c in Company.__table__.columns}
    assert "selected_resume_ids" in cols
    assert "selected_cv_ids" not in cols  # renamed, not duplicated


def test_company_default_is_empty_list(test_db):
    co = Company(name="Acme", scrape_urls=[], aliases=[], active=True, playwright_enabled=True)
    test_db.add(co)
    test_db.commit()
    assert co.selected_resume_ids in ([], None)


def test_get_resume_texts_for_company_uses_selected_ids(test_db):
    """When the column has UUIDs of base resumes, those resumes' texts are returned."""
    from backend.analyzer.cv_scorer import _get_resume_texts_for_company
    pm = Resume(name="PM", is_base=True, template="inter",
                json_data={"summary": "PM summary", "experience": [], "skills": {}})
    other = Resume(name="Other", is_base=True, template="inter",
                   json_data={"summary": "Other summary", "experience": [], "skills": {}})
    test_db.add_all([pm, other])
    test_db.flush()
    co = Company(name="Acme", scrape_urls=[], aliases=[],
                 selected_resume_ids=[str(pm.id)],
                 active=True, playwright_enabled=True)
    test_db.add(co)
    test_db.commit()

    texts = _get_resume_texts_for_company(test_db, co)
    assert list(texts.keys()) == ["PM"]
