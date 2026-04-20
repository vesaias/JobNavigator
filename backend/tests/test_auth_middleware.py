"""Tests for dashboard API-key middleware."""
import pytest
import logging


def test_first_run_empty_key_allows_all(api_client, test_db, caplog):
    """When dashboard_api_key is empty, all endpoints allow access (first-run)."""
    # Seed an empty dashboard_api_key row → first-run mode (matches seed.py behavior)
    from backend.models.db import Setting
    test_db.add(Setting(key="dashboard_api_key", value=""))
    test_db.commit()
    with caplog.at_level(logging.WARNING):
        resp = api_client.get("/api/settings")
    assert resp.status_code == 200
    # Bypass MUST log a warning so operators can detect misconfigured restores
    bypass_logs = [r for r in caplog.records
                    if "bypass" in r.message.lower() or "first-run" in r.message.lower()]
    assert len(bypass_logs) >= 1, f"Expected bypass warning in logs, got: {[r.message for r in caplog.records]}"


def test_configured_key_rejects_missing_header(api_client, test_db):
    """Key set → request without X-API-Key returns 401."""
    from backend.models.db import Setting
    test_db.add(Setting(key="dashboard_api_key", value="sekret"))
    test_db.commit()
    resp = api_client.get("/api/settings")
    assert resp.status_code == 401


def test_configured_key_rejects_wrong_header(api_client, test_db):
    from backend.models.db import Setting
    test_db.add(Setting(key="dashboard_api_key", value="sekret"))
    test_db.commit()
    resp = api_client.get("/api/settings", headers={"X-API-Key": "wrong"})
    assert resp.status_code == 401


def test_configured_key_accepts_correct_header(api_client, test_db):
    from backend.models.db import Setting
    test_db.add(Setting(key="dashboard_api_key", value="sekret"))
    test_db.commit()
    resp = api_client.get("/api/settings", headers={"X-API-Key": "sekret"})
    assert resp.status_code == 200


def test_health_endpoint_skips_auth(api_client, test_db):
    """/health must never require auth — used by monitors."""
    from backend.models.db import Setting
    test_db.add(Setting(key="dashboard_api_key", value="sekret"))
    test_db.commit()
    resp = api_client.get("/health")
    assert resp.status_code == 200
