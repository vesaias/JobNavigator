"""R4-T1 · /api/settings, /api/llm, /api/autofill and /api/linkedin contract.

Settings is the one router with real value validation (ints, crons, enums),
because a bad value here can crash `configure_scheduler()` inside the lifespan
and stop the backend from starting at all.
"""
import pytest

from backend.tests.r4_support import (  # noqa: F401
    client, _clear_running_state, _no_outbound, assert_clean, assert_no_leak,
    make_persona, set_setting, big_string, EMOJI,
)


# ══ GET /api/settings ════════════════════════════════════════════════════════

SECRET_KEYS = ["llm_api_key", "gmail_refresh_token", "telegram_webhook_secret",
               "linkedin_password", "linkedin_session_id"]


def test_get_settings_redacts_secret_shaped_keys(client, test_db):
    for key in SECRET_KEYS:
        set_setting(test_db, key, "s3cret-value")
    body = client.get("/api/settings").json()
    for key in SECRET_KEYS:
        assert body[key] == "•" * 6, key
    # …and the API key itself, seeded by the fixture, is redacted too.
    assert body["dashboard_api_key"] == "•" * 6
    assert "s3cret-value" not in client.get("/api/settings").text
    assert "r4-test-key" not in client.get("/api/settings").text


def test_get_settings_empty_secret_stays_empty_not_dots(client, test_db):
    set_setting(test_db, "llm_api_key", "")
    assert client.get("/api/settings").json()["llm_api_key"] == ""


def test_get_settings_parses_json_values(client, test_db):
    set_setting(test_db, "dedup_tracking_params", ["a", "b"])
    assert client.get("/api/settings").json()["dedup_tracking_params"] == ["a", "b"]


def test_get_defaults_is_a_flat_map(client):
    r = assert_clean(client.get("/api/settings/defaults"), 200)
    assert isinstance(r.json(), dict) and r.json()


# ══ PATCH /api/settings — unknown keys ═══════════════════════════════════════

@pytest.mark.parametrize("key", ["nope", "", "DASHBOARD_API_KEY", "scrape_interval",
                                 "__class__", "; drop table settings;", EMOJI])
def test_patch_settings_rejects_unknown_keys(client, key):
    r = assert_clean(client.patch("/api/settings", json={key: "1"}), 400)
    assert "Unknown setting" in r.json()["detail"]


def test_patch_settings_rejects_the_whole_batch_when_one_key_is_unknown(client, test_db):
    before = client.get("/api/settings").json().get("scrape_interval_minutes")
    assert_clean(client.patch("/api/settings",
                              json={"scrape_interval_minutes": "45", "nope": 1}), 400)
    assert client.get("/api/settings").json().get("scrape_interval_minutes") == before


def test_patch_settings_error_names_every_unknown_key(client):
    r = client.patch("/api/settings", json={"aaa": 1, "zzz": 2})
    assert "aaa" in r.json()["detail"] and "zzz" in r.json()["detail"]


# ══ PATCH /api/settings — integers ═══════════════════════════════════════════

@pytest.mark.parametrize("value", ["abc", "", "1.5", "1e3", " ", "0x10", None, [], {}])
def test_patch_settings_rejects_non_integer_intervals(client, value):
    r = assert_clean(client.patch("/api/settings",
                                  json={"scrape_interval_minutes": value}), 400)
    assert "whole number" in r.json()["detail"]


@pytest.mark.parametrize("value", [-1, "-1", -999999])
def test_patch_settings_rejects_negative_intervals(client, value):
    r = assert_clean(client.patch("/api/settings",
                                  json={"scrape_interval_minutes": value}), 400)
    assert "negative" in r.json()["detail"]


@pytest.mark.parametrize("value", [True, False])
def test_patch_settings_rejects_booleans_for_integer_keys(client, value):
    """True is an int in Python; it must not become "1 minute"."""
    assert_clean(client.patch("/api/settings",
                              json={"scrape_interval_minutes": value}), 400)


@pytest.mark.parametrize("value", [0, "0", 5, "5", " 60 ", 10 ** 9])
def test_patch_settings_accepts_valid_integers(client, value):
    r = assert_clean(client.patch("/api/settings",
                                  json={"scrape_interval_minutes": value}), 200)
    assert r.json()["updated"] == ["scrape_interval_minutes"]


@pytest.mark.xfail(strict=True, reason="R4-T1-21")
def test_patch_settings_rejects_an_absurdly_large_interval(client):
    """10**18 minutes is not a schedule; APScheduler carries it as a real timedelta."""
    assert client.patch("/api/settings",
                        json={"scrape_interval_minutes": 10 ** 18}).status_code == 400


# ══ PATCH /api/settings — crons ══════════════════════════════════════════════

@pytest.mark.parametrize("cron", [
    "0 3 * * *", "*/5 * * * *", "0 0 1 1 0", "", "  ",
])
def test_patch_settings_accepts_valid_crons(client, cron):
    assert_clean(client.patch("/api/settings", json={"backup_cron": cron}), 200)


@pytest.mark.parametrize("cron", [
    "0 3 * *", "0 3 * * * *", "banana", "99 99 99 99 99",
    "* * * * mars", "@daily", "0 3 * * * extra",
])
def test_patch_settings_rejects_invalid_crons(client, cron):
    r = assert_clean(client.patch("/api/settings", json={"backup_cron": cron}), 400)
    assert "backup_cron" in r.json()["detail"]


@pytest.mark.parametrize("value", [5, None, [], {}, True])
def test_patch_settings_rejects_non_string_crons(client, value):
    assert_clean(client.patch("/api/settings", json={"digest_cron": value}), 400)


@pytest.mark.parametrize("key", ["backup_cron", "digest_cron", "h1b_cron",
                                 "cleanup_cron", "reject_cron"])
def test_every_cron_setting_is_validated(client, key):
    assert_clean(client.patch("/api/settings", json={key: "banana"}), 400)


# ══ PATCH /api/settings — enums ══════════════════════════════════════════════

@pytest.mark.parametrize("key", ["llm_provider", "llm_fallback_provider",
                                 "scoring_llm_provider", "email_llm_provider",
                                 "cv_tailor_llm_provider", "cover_letter_llm_provider",
                                 "autofill_llm_provider"])
def test_patch_settings_rejects_an_unknown_provider(client, key):
    r = assert_clean(client.patch("/api/settings", json={key: "skynet"}), 400)
    assert "must be one of" in r.json()["detail"]


@pytest.mark.parametrize("provider", ["claude_api", "claude_code", "openai",
                                      "ollama", "openrouter", ""])
def test_patch_settings_accepts_every_known_provider(client, provider):
    assert_clean(client.patch("/api/settings", json={"llm_provider": provider}), 200)


def test_patch_settings_provider_match_is_case_insensitive(client):
    assert_clean(client.patch("/api/settings", json={"llm_provider": "OpenAI"}), 200)


@pytest.mark.parametrize("key,bad", [
    ("scoring_default_depth", "deep"), ("on_save_action", "maybe"),
    ("tracer_links_url_style", "querystring"), ("tailor_auto_quick_score", "sometimes"),
])
def test_patch_settings_rejects_unknown_enum_values(client, key, bad):
    assert_clean(client.patch("/api/settings", json={key: bad}), 400)


@pytest.mark.parametrize("key,good", [
    ("scoring_default_depth", "full"), ("on_save_action", "off"),
    ("tracer_links_url_style", "param_jobid"), ("tailor_auto_quick_score", "light"),
])
def test_patch_settings_accepts_known_enum_values(client, key, good):
    assert_clean(client.patch("/api/settings", json={key: good}), 200)


@pytest.mark.parametrize("bad", [5, None, [], {}, True])
def test_patch_settings_rejects_non_string_enum_values(client, bad):
    assert_clean(client.patch("/api/settings", json={"scoring_default_depth": bad}), 400)


# ══ PATCH /api/settings — misc ═══════════════════════════════════════════════

def test_patch_settings_skips_the_redaction_placeholder(client, test_db):
    """Re-saving the Settings form must not overwrite a secret with six bullets."""
    set_setting(test_db, "llm_api_key", "real-key")
    r = assert_clean(client.patch("/api/settings",
                                  json={"llm_api_key": "•" * 6}), 200)
    assert r.json()["updated"] == []
    from backend.models.db import Setting
    row = test_db.query(Setting).filter(Setting.key == "llm_api_key").first()
    test_db.refresh(row)
    assert row.value == "real-key"


def test_patch_settings_empty_body_is_a_noop_200(client):
    r = assert_clean(client.patch("/api/settings", json={}), 200)
    assert r.json() == {"updated": [], "warnings": []}


@pytest.mark.parametrize("body", [[1], "x", 3, None])
def test_patch_settings_non_object_body_is_422(client, body):
    assert_clean(client.patch("/api/settings", json=body), 422)


def test_patch_settings_ten_megabyte_prompt(client):
    r = client.patch("/api/settings", json={"scoring_rubric": big_string(10)})
    assert_clean(r, 200, 400, 413, 422)


def test_patch_settings_unicode_prompt_round_trips(client):
    assert_clean(client.patch("/api/settings", json={"scoring_rubric": EMOJI}), 200)
    assert client.get("/api/settings").json()["scoring_rubric"] == EMOJI


def test_patch_settings_reports_a_reconfigure_failure_as_a_warning(client, monkeypatch):
    """A broken scheduler reconfigure must not turn a valid PATCH into a 500."""
    import backend.api.routes_settings as rs

    def _boom():
        raise RuntimeError("scheduler down")
    monkeypatch.setattr(rs, "configure_scheduler", _boom)
    r = assert_clean(client.patch("/api/settings",
                                  json={"scrape_interval_minutes": "30"}), 200)
    assert r.json()["warnings"] and "configure_scheduler" in r.json()["warnings"][0]


def test_patch_dedup_tracking_params_reloads_the_cache(client, test_db):
    from backend.scraper._shared import dedup
    dedup._tracking_params_cache = {"stale"}
    assert_clean(client.patch("/api/settings",
                              json={"dedup_tracking_params": ["utm_source"]}), 200)
    assert dedup._tracking_params_cache != {"stale"}


# ══ /api/llm/models ══════════════════════════════════════════════════════════

@pytest.mark.parametrize("provider", ["bogus", "", "ollama", "claude"])
def test_llm_models_unsupported_provider_is_400(client, provider):
    assert_clean(client.get(f"/api/llm/models?provider={provider}"), 400)


@pytest.mark.parametrize("provider", ["openai", "claude_api", "claude_code"])
def test_llm_models_without_a_key_is_400(client, provider, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    r = assert_clean(client.get(f"/api/llm/models?provider={provider}"), 400)
    assert "API key" in r.json()["detail"]


def test_llm_models_provider_rejection_is_502_not_500(client, test_db, monkeypatch):
    import httpx
    import backend.api.routes_llm as rl
    rl._cache.clear()
    set_setting(test_db, "llm_provider", "openai")
    set_setting(test_db, "llm_api_key", "bad-key")

    async def _boom(key):
        request = httpx.Request("GET", "https://api.openai.com/v1/models")
        response = httpx.Response(401, request=request)
        raise httpx.HTTPStatusError("401", request=request, response=response)
    monkeypatch.setattr(rl, "_fetch_openai", _boom)
    r = assert_clean(client.get("/api/llm/models?provider=openai"), 502)
    assert "rejected" in r.json()["detail"]


def test_llm_models_network_failure_is_502_not_500(client, monkeypatch):
    import backend.api.routes_llm as rl
    rl._cache.clear()

    async def _boom():
        raise OSError("dns is down")
    monkeypatch.setattr(rl, "_fetch_openrouter", _boom)
    assert_clean(client.get("/api/llm/models?provider=openrouter"), 502)


def test_llm_models_serves_a_stale_cache_when_the_provider_is_down(client, monkeypatch):
    import time
    import backend.api.routes_llm as rl
    rl._cache["openrouter"] = {"at": time.time() - 7200, "models": [{"id": "m1"}]}

    async def _boom():
        raise OSError("dns is down")
    monkeypatch.setattr(rl, "_fetch_openrouter", _boom)
    r = assert_clean(client.get("/api/llm/models?provider=openrouter"), 200)
    assert r.json()["stale"] is True
    rl._cache.clear()


# ══ /api/autofill ════════════════════════════════════════════════════════════

def test_autofill_config_shape(client, test_db):
    make_persona(test_db)
    body = assert_clean(client.get("/api/autofill/config"), 200).json()
    for key in ("answers", "field_patterns", "option_synonyms", "schema", "decline_self_id"):
        assert key in body


@pytest.mark.parametrize("body", [{}, {"question": ""}, {"question": "   "},
                                  {"question": None}])
def test_autofill_answer_requires_a_question(client, body):
    assert_clean(client.post("/api/autofill/answer", json=body), 400)


def test_autofill_missing_prompt_setting_is_500_with_a_reason(client, test_db):
    make_persona(test_db)
    r = client.post("/api/autofill/answer", json={"question": "Why us?"})
    assert r.status_code == 500
    assert_no_leak(r)
    assert "autofill_prompt" in r.text


@pytest.mark.xfail(strict=True, reason="R4-T1-22")
def test_autofill_stream_uses_the_editable_prompt_setting(client, test_db):
    """The SSE path hardcodes its own prompt, so an edited `autofill_prompt` is
    silently ignored by the variant the extension actually streams from."""
    make_persona(test_db)
    r = client.post("/api/autofill/answer/stream", json={"question": "Why us?"})
    assert r.status_code == 500 and "autofill_prompt" in r.text


def test_autofill_answer_llm_failure_is_502_not_500(client, test_db, monkeypatch):
    import backend.api.routes_autofill as ra
    make_persona(test_db)
    set_setting(test_db, "autofill_prompt", "{persona}{company}{position}{question}")

    async def _boom(*a, **k):
        raise RuntimeError("provider exploded")
    monkeypatch.setattr(ra, "call_autofill_llm", _boom)
    r = assert_clean(client.post("/api/autofill/answer",
                                 json={"question": "Why us?"}), 502)
    assert "provider exploded" not in r.text


def test_autofill_answer_trims_to_max_chars(client, test_db, monkeypatch):
    import backend.api.routes_autofill as ra
    make_persona(test_db)
    set_setting(test_db, "autofill_prompt", "{persona}{company}{position}{question}")

    async def _long(*a, **k):
        return {"text": '{"answer": "' + "y" * 500 + '"}', "usage": {}}
    monkeypatch.setattr(ra, "call_autofill_llm", _long)
    r = assert_clean(client.post("/api/autofill/answer",
                                 json={"question": "Why?", "max_chars": 40}), 200)
    assert len(r.json()["answer"]) <= 40
    assert r.json()["trimmed"] is True


@pytest.mark.parametrize("bad", ["abc", -5, "-5", None, [], {}])
def test_autofill_answer_bad_max_chars_falls_back_to_the_default(client, test_db,
                                                                 monkeypatch, bad):
    import backend.api.routes_autofill as ra
    make_persona(test_db)
    set_setting(test_db, "autofill_prompt", "{persona}{company}{position}{question}")

    async def _short(*a, **k):
        return {"text": '{"answer": "ok"}', "usage": {}}
    monkeypatch.setattr(ra, "call_autofill_llm", _short)
    r = assert_clean(client.post("/api/autofill/answer",
                                 json={"question": "Why?", "max_chars": bad}), 200)
    assert r.json()["max_chars"] > 0


def test_autofill_answer_ten_megabyte_question(client, test_db, monkeypatch):
    import backend.api.routes_autofill as ra
    make_persona(test_db)
    set_setting(test_db, "autofill_prompt", "{persona}{company}{position}{question}")

    async def _short(*a, **k):
        return {"text": '{"answer": "ok"}', "usage": {}}
    monkeypatch.setattr(ra, "call_autofill_llm", _short)
    r = client.post("/api/autofill/answer", json={"question": big_string(10)})
    assert_clean(r, 200, 400, 413, 422)


@pytest.mark.parametrize("body", [[1], "x", 3, None])
def test_autofill_answer_non_object_body_is_422(client, body):
    assert_clean(client.post("/api/autofill/answer", json=body), 422)


# ══ /api/linkedin ════════════════════════════════════════════════════════════

def test_linkedin_session_status_shape(client):
    body = assert_clean(client.get("/api/linkedin/session"), 200).json()
    for key in ("exists", "status", "summary", "phase"):
        assert key in body


@pytest.mark.parametrize("pin", ["", "   ", "abcd", "!!", EMOJI])
def test_linkedin_pin_without_digits_is_rejected(client, pin):
    r = assert_clean(client.post("/api/linkedin/session/pin", json={"pin": pin}), 200)
    assert r.json()["ok"] is False


@pytest.mark.parametrize("body", [{}, {"pin": None}, {"pin": 1234}, [1], "x"])
def test_linkedin_pin_bad_body_never_500(client, body):
    assert_clean(client.post("/api/linkedin/session/pin", json=body), 200, 400, 422)
