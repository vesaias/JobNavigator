"""PATCH /api/settings must reject values it can't parse back; the guard lives in seed.invalid_setting_values()."""
import importlib.util

import pytest

from backend.models.db import Setting
from backend.seed import (
    DEFAULT_SETTINGS, ENUM_SETTING_VALUES, INT_SETTING_KEYS, invalid_setting_values,
)


def _seed_first_run(db):
    """Empty dashboard_api_key means first-run mode, so the auth middleware lets the TestClient through."""
    db.add(Setting(key="dashboard_api_key", value=""))
    db.commit()


needs_container = pytest.mark.skipif(
    importlib.util.find_spec("apscheduler") is None,
    reason="imports backend.main (apscheduler) — run in the container",
)
needs_apscheduler = pytest.mark.skipif(
    importlib.util.find_spec("apscheduler") is None,
    reason="cron syntax check needs APScheduler — run in the container",
)


# ── the derived key sets ────────────────────────────────────────────────────

def test_int_keys_match_the_nine_rows_settings_marks_int():
    """Derived from the seeded defaults; must equal what Settings.jsx types as numeric."""
    assert INT_SETTING_KEYS == {
        "fit_score_threshold",
        "scrape_interval_minutes",
        "email_check_interval_minutes",
        "job_archive_after_days",
        "auto_reject_after_days",
        "scoring_max_concurrent",
        "tailoring_max_concurrent",
        "email_llm_confidence_threshold",
        "autofill_default_length",
    }


def test_every_validated_key_is_a_real_setting():
    for key in INT_SETTING_KEYS | set(ENUM_SETTING_VALUES):
        assert key in DEFAULT_SETTINGS, key


def test_every_seeded_default_passes_its_own_guard():
    """The shipped defaults must survive a round-trip through the validator."""
    updates = {k: v for k, (v, _d) in DEFAULT_SETTINGS.items()
               if k in INT_SETTING_KEYS or k in ENUM_SETTING_VALUES or k.endswith("_cron")}
    assert invalid_setting_values(updates) == []


# ── integers ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("value", ["", "abc", "1.5", "60m", None, [], True])
def test_non_integer_interval_rejected(value):
    problems = invalid_setting_values({"scrape_interval_minutes": value})
    assert len(problems) == 1
    assert problems[0].startswith("scrape_interval_minutes: must be a whole number")


def test_negative_integer_rejected():
    problems = invalid_setting_values({"scoring_max_concurrent": "-1"})
    assert problems == ["scoring_max_concurrent: must not be negative (got '-1')"]


@pytest.mark.parametrize("value", ["0", "60", " 60 ", 60])
def test_valid_integer_accepted(value):
    assert invalid_setting_values({"scrape_interval_minutes": value}) == []


# ── cron ────────────────────────────────────────────────────────────────────

def test_empty_cron_accepted():
    """Empty disables the job — the seeded help text says so."""
    assert invalid_setting_values({"backup_cron": ""}) == []
    assert invalid_setting_values({"backup_cron": "   "}) == []


@pytest.mark.parametrize("expr", ["invalid", "0 3 * *", "0 3 * * * *"])
def test_wrong_field_count_rejected(expr):
    problems = invalid_setting_values({"digest_cron": expr})
    assert problems == [
        "digest_cron: needs exactly 5 whitespace-separated fields (min hour day month dow)"
    ]


def test_non_string_cron_rejected():
    problems = invalid_setting_values({"h1b_cron": 5})
    assert problems == ["h1b_cron: must be a cron string (got 5)"]


@needs_apscheduler
def test_five_fields_but_unparseable_rejected():
    problems = invalid_setting_values({"cleanup_cron": "0 99 * * *"})
    assert len(problems) == 1
    assert problems[0].startswith("cleanup_cron: not a valid cron expression")


def test_valid_cron_accepted():
    assert invalid_setting_values({"reject_cron": "0 4 * * *"}) == []
    assert invalid_setting_values({"backup_cron": "*/15 * * * 1-5"}) == []


# ── enums ───────────────────────────────────────────────────────────────────

def test_unknown_provider_rejected():
    problems = invalid_setting_values({"llm_provider": "gemini"})
    assert len(problems) == 1
    assert problems[0].startswith("llm_provider: must be one of ")
    assert "claude_api" in problems[0]


def test_unknown_depth_rejected():
    problems = invalid_setting_values({"scoring_default_depth": "deep"})
    assert problems == ["scoring_default_depth: must be one of full, light (got 'deep')"]


def test_empty_provider_accepted_it_means_inherit():
    assert invalid_setting_values({"scoring_llm_provider": ""}) == []


def test_legacy_boolean_tailor_depth_still_accepted():
    """routes_resumes._resolve_chain_score_depth still maps 'true'/'false'."""
    assert invalid_setting_values({"tailor_auto_quick_score": "true"}) == []
    assert invalid_setting_values({"tailor_auto_quick_score": "off"}) == []


def test_enum_is_case_insensitive():
    assert invalid_setting_values({"on_save_action": "Full"}) == []


# ── one message, every offender ─────────────────────────────────────────────

def test_all_offenders_listed_in_one_pass():
    problems = invalid_setting_values({
        "scrape_interval_minutes": "soon",
        "backup_cron": "nope",
        "llm_provider": "gemini",
        "fit_score_threshold": "60",      # fine — must not appear
    })
    assert len(problems) == 3
    keys = [p.split(":")[0] for p in problems]
    assert keys == sorted(keys)           # deterministic order
    assert "fit_score_threshold" not in keys


# ── the endpoint ────────────────────────────────────────────────────────────

@needs_container
def test_patch_rejects_non_integer_interval(api_client, test_db):
    _seed_first_run(test_db)
    resp = api_client.patch("/api/settings", json={"scrape_interval_minutes": "abc"})
    assert resp.status_code == 400
    assert "scrape_interval_minutes" in resp.json()["detail"]
    assert test_db.query(Setting).filter(
        Setting.key == "scrape_interval_minutes").first() is None


@needs_container
def test_patch_rejects_negative_integer(api_client, test_db):
    _seed_first_run(test_db)
    resp = api_client.patch("/api/settings", json={"job_archive_after_days": -3})
    assert resp.status_code == 400
    assert "must not be negative" in resp.json()["detail"]


@needs_container
def test_patch_rejects_bad_cron(api_client, test_db):
    _seed_first_run(test_db)
    resp = api_client.patch("/api/settings", json={"backup_cron": "0 3 * *"})
    assert resp.status_code == 400
    assert "backup_cron" in resp.json()["detail"]


@needs_container
def test_patch_rejects_unknown_enum(api_client, test_db):
    _seed_first_run(test_db)
    resp = api_client.patch("/api/settings", json={"scoring_default_depth": "deep"})
    assert resp.status_code == 400
    assert "scoring_default_depth" in resp.json()["detail"]


@needs_container
def test_patch_lists_every_invalid_key_in_one_message(api_client, test_db):
    _seed_first_run(test_db)
    resp = api_client.patch("/api/settings", json={
        "scrape_interval_minutes": "abc",
        "backup_cron": "nope",
        "llm_provider": "gemini",
    })
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert detail.startswith("Invalid setting value — ")
    for key in ("scrape_interval_minutes", "backup_cron", "llm_provider"):
        assert key in detail
    # the whole request is rejected — nothing was written
    assert test_db.query(Setting).filter(Setting.key == "llm_provider").first() is None


@needs_container
def test_patch_accepts_valid_values(api_client, test_db):
    _seed_first_run(test_db)
    resp = api_client.patch("/api/settings", json={
        "scrape_interval_minutes": "15",
        "backup_cron": "0 3 * * *",
        "scoring_default_depth": "full",
    })
    assert resp.status_code == 200
    assert sorted(resp.json()["updated"]) == [
        "backup_cron", "scoring_default_depth", "scrape_interval_minutes"]


@needs_container
def test_patch_ignores_the_redacted_placeholder(api_client, test_db):
    """A GET returns '••••••' for secrets; PATCHing that back must not be validated or written as a real value."""
    _seed_first_run(test_db)
    resp = api_client.patch("/api/settings", json={"llm_api_key": "•" * 6})
    assert resp.status_code == 200
    assert resp.json()["updated"] == []
