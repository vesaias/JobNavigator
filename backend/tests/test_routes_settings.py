"""Tests for PATCH /api/settings reconfig error surfacing."""
import pytest


def _seed_first_run(db):
    from backend.models.db import Setting
    db.add(Setting(key="dashboard_api_key", value=""))
    db.commit()


def test_patch_settings_reports_scheduler_reconfig_error(api_client, test_db, monkeypatch):
    """configure_scheduler raises → response body contains warnings with the error."""
    _seed_first_run(test_db)

    def broken_configure():
        raise RuntimeError("scheduler config broken")

    monkeypatch.setattr(
        "backend.api.routes_settings.configure_scheduler",
        broken_configure,
        raising=False,
    )

    resp = api_client.patch("/api/settings", json={"scrape_interval_minutes": "15"})
    assert resp.status_code == 200
    data = resp.json()
    warnings = data.get("warnings") or []
    assert any("scheduler" in str(w).lower() for w in warnings), (
        f"Expected scheduler error in warnings, got: {data}"
    )


def test_patch_settings_no_warnings_on_clean_reconfig(api_client, test_db):
    """When all reconfigs succeed, response should NOT include warnings (or empty list)."""
    _seed_first_run(test_db)
    resp = api_client.patch("/api/settings", json={"scrape_interval_minutes": "15"})
    assert resp.status_code == 200
    data = resp.json()
    warnings = data.get("warnings") or []
    assert warnings == []
