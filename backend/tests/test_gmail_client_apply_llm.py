"""Tests for gmail_client._apply_llm_result_to_app — forward-only transitions + rejection bypass.

The function signature is:
    _apply_llm_result_to_app(db, matched_app, llm_result: dict, body: str, subject: str)

Forward-only rule uses a rank dict where rejected=99, so rejection bypasses the rule
implicitly (99 > any other rank). "no_change" / unknown statuses return -1, so they
never exceed current_rank — effectively a no-op.

`record_transition` is imported inside the function from `backend.models.db`, so we
patch it at the source module (not at gmail_client).
"""
from unittest.mock import MagicMock


def _make_app(status="applied"):
    """Stub Application with attributes the function reads/writes."""
    app = MagicMock()
    app.id = "app-1"
    app.status = status
    app.status_transitions = []
    return app


def _make_result(status, confidence=90, summary="test"):
    return {"status": status, "confidence": confidence, "summary": summary}


def test_forward_transition_applied_to_interview(monkeypatch):
    """applied (rank 0) -> interview (rank 3) is forward; should trigger record_transition."""
    from backend.email_monitor import gmail_client

    transitions = []
    monkeypatch.setattr(
        "backend.models.db.record_transition",
        lambda app, new, source: transitions.append((new, source)),
        raising=True,
    )

    app = _make_app("applied")
    db = MagicMock()
    gmail_client._apply_llm_result_to_app(db, app, _make_result("interview"), "body", "subj")

    assert ("interview", "email") in transitions
    # Side effects: timestamps set + commit called
    assert app.last_email_snippet == "body"
    db.commit.assert_called_once()


def test_backward_transition_blocked_by_forward_only(monkeypatch):
    """interview (rank 3) -> applied (rank 0) is NOT forward; should NOT trigger a transition."""
    from backend.email_monitor import gmail_client

    transitions = []
    monkeypatch.setattr(
        "backend.models.db.record_transition",
        lambda app, new, source: transitions.append((new, source)),
        raising=True,
    )

    app = _make_app("interview")
    db = MagicMock()
    gmail_client._apply_llm_result_to_app(db, app, _make_result("applied"), "body", "subj")

    assert transitions == [], (
        f"Forward-only rule should block interview -> applied; got transitions: {transitions}"
    )
    # Commit still happens (last_email_* fields get updated regardless)
    db.commit.assert_called_once()


def test_rejection_always_allowed_from_any_state(monkeypatch):
    """Rejection (rank 99) bypasses forward-only — works from any advanced state."""
    from backend.email_monitor import gmail_client

    transitions = []
    monkeypatch.setattr(
        "backend.models.db.record_transition",
        lambda app, new, source: transitions.append((new, source)),
        raising=True,
    )

    # Rejection from "interview" — rank 99 > rank 3, so transition fires
    app = _make_app("interview")
    db = MagicMock()
    gmail_client._apply_llm_result_to_app(db, app, _make_result("rejected"), "body", "subj")

    assert ("rejected", "email") in transitions


def test_no_change_is_noop(monkeypatch):
    """status='no_change' maps to rank -1 which is never > current_rank — no transition."""
    from backend.email_monitor import gmail_client

    transitions = []
    monkeypatch.setattr(
        "backend.models.db.record_transition",
        lambda app, new, source: transitions.append((new, source)),
        raising=True,
    )

    app = _make_app("applied")
    db = MagicMock()
    gmail_client._apply_llm_result_to_app(db, app, _make_result("no_change", confidence=50), "body", "subj")

    assert transitions == []
