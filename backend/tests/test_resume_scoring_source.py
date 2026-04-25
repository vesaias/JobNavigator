"""Scoring source migrated from CV table to Resume table (Task 5)."""
import pytest
from backend.models.db import Resume, CV, Setting


def _seed_resume(test_db, name, summary):
    """Create a base Resume with a minimal json_data containing summary + one job."""
    r = Resume(
        name=name,
        is_base=True,
        template="inter",
        json_data={
            "summary": summary,
            "experience": [
                {"company": "Acme", "title": f"{name} Lead", "bullets": [f"shipped {name} platform"]}
            ],
            "skills": {"core": ["Python", "SQL"]},
        },
    )
    test_db.add(r)
    test_db.commit()
    return r


def test_get_resume_texts_returns_dict_keyed_by_name(test_db):
    from backend.analyzer.cv_scorer import _get_resume_texts
    _seed_resume(test_db, "PM", "Product manager focused on fintech")
    _seed_resume(test_db, "TPgM", "Technical program manager")

    texts = _get_resume_texts(test_db)
    assert set(texts.keys()) == {"PM", "TPgM"}
    assert "Product manager" in texts["PM"]
    assert "Technical program" in texts["TPgM"]


def test_get_resume_texts_skips_tailored_resumes(test_db):
    """is_base=False rows must NOT show up in scoring."""
    from backend.analyzer.cv_scorer import _get_resume_texts
    base = _seed_resume(test_db, "PM", "summary")
    # Tailored child
    test_db.add(Resume(
        name="PM → Acme tailored",
        is_base=False,
        parent_id=base.id,
        template="inter",
        json_data={"summary": "tailored", "experience": [], "skills": {}},
    ))
    test_db.commit()

    texts = _get_resume_texts(test_db)
    assert list(texts.keys()) == ["PM"]


def test_get_resume_texts_does_not_read_cv_table(test_db):
    """Even if CVs exist, they're ignored by the new source."""
    from backend.analyzer.cv_scorer import _get_resume_texts
    test_db.add(CV(version="OldCV", filename="legacy.pdf", pdf_data=b"x", extracted_text="legacy text"))
    _seed_resume(test_db, "PM", "current resume")
    test_db.commit()

    texts = _get_resume_texts(test_db)
    assert "OldCV" not in texts
    assert "PM" in texts
    assert "legacy text" not in texts["PM"]


def test_get_default_resume_reads_from_setting(test_db):
    from backend.analyzer.cv_scorer import _get_default_resume
    pm = _seed_resume(test_db, "PM", "summary")
    test_db.add(Setting(key="default_resume_id", value=str(pm.id)))
    test_db.commit()

    default = _get_default_resume(test_db)
    assert list(default.keys()) == ["PM"]
