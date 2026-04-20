"""Tests for models/db.record_transition — append status transitions + update status."""
import pytest


def _make_app(status="new", transitions=None):
    """Minimal Application stub — function is pure w.r.t. the ORM object."""
    from backend.models.db import Application
    return Application(
        id="app-1",
        status=status,
        status_transitions=transitions if transitions is not None else [],
    )


def test_record_transition_appends_entry():
    from backend.models.db import record_transition
    app = _make_app("new")
    record_transition(app, "applied", "ui")
    assert len(app.status_transitions) == 1
    t = app.status_transitions[0]
    assert t.get("from") == "new"
    assert t.get("to") == "applied"
    assert t.get("source") == "ui"
    assert "at" in t


def test_record_transition_updates_status():
    from backend.models.db import record_transition
    app = _make_app("new")
    record_transition(app, "applied", "ui")
    assert app.status == "applied"


def test_record_transition_noop_when_same_status():
    """Transitioning X → X should not append a duplicate entry (idempotent)."""
    from backend.models.db import record_transition
    app = _make_app("applied")
    record_transition(app, "applied", "ui")
    assert app.status_transitions == []
    assert app.status == "applied"


def test_record_transition_initializes_empty_list():
    """When status_transitions is None, record_transition initializes it to a list."""
    from backend.models.db import record_transition
    app = _make_app("new", transitions=None)
    record_transition(app, "applied", "ui")
    assert isinstance(app.status_transitions, list)
    assert len(app.status_transitions) == 1


def test_record_transition_preserves_source_label():
    from backend.models.db import record_transition
    app = _make_app("new")
    record_transition(app, "interview", "email")
    record_transition(app, "offer", "telegram")
    sources = [t.get("source") for t in app.status_transitions]
    assert sources == ["email", "telegram"]
    assert app.status == "offer"
