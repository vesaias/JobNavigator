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


def test_seed_persona_creates_singleton(test_db):
    """seed_persona creates id=1 with empty nodes if missing."""
    from backend.seed import seed_persona
    assert test_db.query(Persona).count() == 0
    seed_persona(test_db)
    rows = test_db.query(Persona).all()
    assert len(rows) == 1
    assert rows[0].id == 1
    assert rows[0].contact == {}
    assert rows[0].qa_bank == []


def test_seed_persona_idempotent(test_db):
    """Calling seed_persona twice doesn't duplicate."""
    from backend.seed import seed_persona
    seed_persona(test_db)
    seed_persona(test_db)
    assert test_db.query(Persona).count() == 1
