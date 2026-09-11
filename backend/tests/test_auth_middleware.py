"""Tests for dashboard API-key middleware.

The middleware is fail-closed: an empty/unset ``dashboard_api_key`` must never
grant access (the old "blank-key first run" behaviour). A configured key must
match the ``X-API-Key`` header (or the ``jn_session`` cookie) via a timing-safe
comparison.
"""
import logging

from backend.models.db import Setting


def test_empty_key_rejects(api_client, test_db, caplog, monkeypatch):
    """Fail-closed: an empty key with no env bootstrap grants nothing."""
    import backend.main as main_mod
    monkeypatch.setattr(main_mod, "INITIAL_API_KEY", "")
    test_db.add(Setting(key="dashboard_api_key", value=""))
    test_db.commit()
    with caplog.at_level(logging.ERROR):
        resp = api_client.get("/api/settings")
    assert resp.status_code == 401
    # The refusal must be visible in the logs so operators can detect a botched
    # restore that cleared the key.
    blocked = [r for r in caplog.records if "BLOCKED" in r.message]
    assert blocked, f"Expected a fail-closed BLOCKED log, got: {[r.message for r in caplog.records]}"


def test_configured_key_rejects_wrong_header(api_client, test_db):
    """Key set → a non-matching X-API-Key returns 401."""
    test_db.add(Setting(key="dashboard_api_key", value="sekret"))
    test_db.commit()
    resp = api_client.get("/api/settings", headers={"X-API-Key": "wrong"})
    assert resp.status_code == 401


def test_configured_key_rejects_missing_header(anon_client, test_db):
    """Key set → a request with no X-API-Key (and no session cookie) returns 401."""
    test_db.add(Setting(key="dashboard_api_key", value="sekret"))
    test_db.commit()
    resp = anon_client.get("/api/settings")
    assert resp.status_code == 401


def test_configured_key_accepts_correct_header(api_client, test_db):
    """Key set → the matching X-API-Key returns 200."""
    test_db.add(Setting(key="dashboard_api_key", value="sekret"))
    test_db.commit()
    resp = api_client.get("/api/settings", headers={"X-API-Key": "sekret"})
    assert resp.status_code == 200


def test_health_endpoint_skips_auth(api_client, test_db):
    """/health must never require auth — used by monitors."""
    test_db.add(Setting(key="dashboard_api_key", value="sekret"))
    test_db.commit()
    resp = api_client.get("/health")
    assert resp.status_code == 200
