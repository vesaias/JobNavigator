"""PATCH /api/settings must reject keys nothing in the app reads; writable keys are the seeded DEFAULT_SETTINGS plus seed.RUNTIME_SETTING_KEYS (written by the app at runtime but never seeded)."""
import importlib.util

import pytest

from backend.models.db import Setting
from backend.seed import (
    DEFAULT_SETTINGS, RUNTIME_SETTING_KEYS, is_known_setting, unknown_setting_keys,
)


def _seed_first_run(db):
    """Empty dashboard_api_key = first-run mode, so the auth middleware lets the TestClient through."""
    db.add(Setting(key="dashboard_api_key", value=""))
    db.commit()


needs_container = pytest.mark.skipif(
    importlib.util.find_spec("apscheduler") is None,
    reason="imports backend.main (apscheduler) — run in the container",
)


def test_seeded_and_runtime_keys_are_known():
    assert is_known_setting("scrape_interval_minutes")      # seeded
    assert is_known_setting("gmail_processed_ids")          # runtime-only writer
    assert is_known_setting("llm_seeded_models")            # runtime-only writer
    assert not is_known_setting("scrape_interval_minutez")  # typo


def test_unknown_setting_keys_lists_every_offender():
    keys = ["scrape_interval_minutes", "zzz_one", "gmail_processed_ids", "zzz_two"]
    assert sorted(unknown_setting_keys(keys)) == ["zzz_one", "zzz_two"]


def test_runtime_keys_are_not_duplicated_in_defaults():
    assert not (RUNTIME_SETTING_KEYS & set(DEFAULT_SETTINGS))


@needs_container
def test_patch_rejects_unknown_key(api_client, test_db):
    _seed_first_run(test_db)
    resp = api_client.patch("/api/settings", json={"not_a_real_setting": "x"})
    assert resp.status_code == 400
    assert "Unknown setting: not_a_real_setting" in resp.json()["detail"]
    assert test_db.query(Setting).filter(Setting.key == "not_a_real_setting").first() is None


@needs_container
def test_patch_lists_all_unknown_keys_in_one_message(api_client, test_db):
    _seed_first_run(test_db)
    resp = api_client.patch("/api/settings", json={"bogus_b": 1, "bogus_a": 2,
                                                   "scrape_interval_minutes": "15"})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Unknown setting: bogus_a, bogus_b"
    # the whole request is rejected — the valid key is not written either
    row = test_db.query(Setting).filter(Setting.key == "scrape_interval_minutes").first()
    assert row is None or row.value != "15"


@needs_container
def test_patch_accepts_seeded_key(api_client, test_db):
    _seed_first_run(test_db)
    resp = api_client.patch("/api/settings", json={"scrape_interval_minutes": "15"})
    assert resp.status_code == 200
    assert resp.json()["updated"] == ["scrape_interval_minutes"]
    assert test_db.query(Setting).filter(
        Setting.key == "scrape_interval_minutes").one().value == "15"


@needs_container
def test_patch_accepts_runtime_only_key(api_client, test_db):
    _seed_first_run(test_db)
    resp = api_client.patch("/api/settings", json={"gmail_processed_ids": ["a", "b"]})
    assert resp.status_code == 200
    assert resp.json()["updated"] == ["gmail_processed_ids"]
