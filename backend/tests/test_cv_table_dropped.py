"""cvs table is gone (Task 11)."""
def test_cv_table_does_not_exist(test_db):
    from sqlalchemy import inspect
    insp = inspect(test_db.get_bind())
    assert "cvs" not in insp.get_table_names()


def test_cv_class_does_not_export(test_db):
    """The CV symbol should be removed from db.py."""
    import backend.models.db as db_mod
    assert not hasattr(db_mod, "CV"), "CV class still exported — remove from models/db.py"
