"""Persona model has the right column shape (Phase 1 / Task 1)."""
from backend.models.db import Persona


def test_persona_table_name():
    assert Persona.__tablename__ == "personas"


def test_persona_columns_present():
    """Every node must exist as a JSON column with default {}."""
    expected = {
        "contact",
        "work_auth",
        "demographics",
        "compensation",
        "preferences",
        "resume_content",
        "qa_bank",
        "writing_samples",
    }
    cols = {c.name for c in Persona.__table__.columns}
    missing = expected - cols
    assert not missing, f"Persona missing columns: {missing}"


def test_persona_singleton_id_is_int(test_db):
    """Persona uses a small int PK so we can hardcode id=1 as the singleton row."""
    p = Persona(id=1, contact={"name": "Test"})
    test_db.add(p)
    test_db.commit()
    back = test_db.query(Persona).filter(Persona.id == 1).first()
    assert back is not None
    assert back.contact == {"name": "Test"}
