"""R4-T1 · main.py contract: triggers, monitor, stats, telegram, auth, error mapping.

The DataError -> 404 handler is exercised directly here (SQLite raises a
different exception class for a malformed UUID, so the live pin lives in
test_r4_live_contract.py).
"""
import uuid

import pytest

from backend.tests.r4_support import (  # noqa: F401
    client, _clear_running_state, _no_outbound, assert_clean, assert_no_leak,
    make_job, make_company, set_setting, big_string, EMOJI, MISSING_UUID, API_KEY,
)


# ══ Error mapping ════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_data_error_handler_maps_a_bad_uuid_to_404():
    from sqlalchemy.exc import DataError
    from backend.main import _bad_uuid_to_404

    exc = DataError("SELECT ...", {}, Exception('invalid input syntax for type uuid: "abc"'))
    resp = await _bad_uuid_to_404(_FakeRequest(), exc)
    assert resp.status_code == 404
    assert b"Not found" in resp.body


@pytest.mark.asyncio
async def test_data_error_handler_hides_every_other_data_error():
    from sqlalchemy.exc import DataError
    from backend.main import _bad_uuid_to_404

    exc = DataError("SELECT ...", {}, Exception("LIMIT must not be negative"))
    resp = await _bad_uuid_to_404(_FakeRequest(), exc)
    assert resp.status_code == 500
    assert resp.body == b'{"detail":"Internal server error"}'
    assert b"LIMIT" not in resp.body


class _FakeRequest:
    method = "GET"

    class url:
        path = "/api/jobs/abc"


# ══ Auth ═════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("path", ["/api/jobs", "/api/settings", "/api/monitor/active",
                                  "/api/stats", "/api/companies", "/api/persona"])
def test_protected_routes_need_a_key(client, path):
    r = client.get(path, headers={"X-API-Key": ""})
    assert_clean(r, 401)


@pytest.mark.parametrize("path", ["/api/jobs", "/api/settings"])
def test_protected_routes_reject_a_wrong_key(client, path):
    assert_clean(client.get(path, headers={"X-API-Key": "wrong"}), 401)


def test_session_cookie_is_accepted_instead_of_the_header(client):
    r = client.post("/api/auth/set-session", json={"api_key": API_KEY},
                    headers={"X-API-Key": API_KEY})
    assert_clean(r, 200)
    c = client.get("/api/jobs", headers={"X-API-Key": ""},
                   cookies={"jn_session": API_KEY})
    assert_clean(c, 200)


def test_verify_rejects_a_wrong_key(client):
    assert_clean(client.post("/api/auth/verify", json={"api_key": "nope"},
                             headers={"X-API-Key": API_KEY}), 401)


@pytest.mark.parametrize("body", [{}, {"api_key": None}])
def test_verify_bad_body_never_500(client, body):
    assert_clean(client.post("/api/auth/verify", json=body,
                             headers={"X-API-Key": API_KEY}), 401, 422)


@pytest.mark.parametrize("body", [{"api_key": 5}, {"api_key": [1]}, {"api_key": {"a": 1}}])
def test_verify_wrongly_typed_key_is_401_not_500(client, body):
    """`hmac.compare_digest(5, expected)` raises TypeError."""
    assert client.post("/api/auth/verify", json=body,
                       headers={"X-API-Key": API_KEY}).status_code in (401, 422)


@pytest.mark.parametrize("body", [{"api_key": 5}, {"api_key": [1]}])
def test_verify_wrongly_typed_key_never_leaks_internals(client, body):
    assert_no_leak(client.post("/api/auth/verify", json=body,
                               headers={"X-API-Key": API_KEY}))


@pytest.mark.parametrize("body", [{"api_key": 5}, {"api_key": [1]}])
def test_set_session_wrongly_typed_key_is_401_not_500(client, body):
    assert client.post("/api/auth/set-session", json=body,
                       headers={"X-API-Key": API_KEY}).status_code in (401, 422)


def test_health_is_public(client):
    assert_clean(client.get("/health", headers={"X-API-Key": ""}), 200)


def test_root_without_a_tracer_token_is_404(client):
    assert_clean(client.get("/"), 404)


def test_root_without_a_key_and_without_a_token_is_401(client):
    """The `?cv` bypass is narrow: a bare `/` still needs auth."""
    assert_clean(client.get("/", headers={"X-API-Key": ""}), 401)


def test_unknown_tracer_token_is_404(client):
    assert_clean(client.get("/cv/zzzzzzzz", headers={"X-API-Key": ""}), 404)


# ══ Triggers ═════════════════════════════════════════════════════════════════

TRIGGERS = [
    "/api/scrape/run-all", "/api/email/check-now", "/api/h1b/refresh",
    "/api/db/cleanup", "/api/auto-reject/run", "/api/jobs/backfill-descriptions",
    "/api/db/backup", "/api/telegram/digest", "/api/telegram/test",
]


@pytest.mark.parametrize("path", TRIGGERS)
def test_every_trigger_is_409_while_its_job_type_is_running(client, path):
    """Occupy the scope key by hand, then confirm the endpoint refuses politely."""
    import backend.job_monitor as jm
    from datetime import datetime, timezone

    job_type = {
        "/api/scrape/run-all": "scrape_all",
        "/api/email/check-now": "email_check",
        "/api/h1b/refresh": "h1b_refresh",
        "/api/db/cleanup": "job_cleanup",
        "/api/auto-reject/run": "auto_reject",
        "/api/jobs/backfill-descriptions": "backfill_descriptions",
        "/api/db/backup": "db_backup",
        "/api/telegram/digest": "daily_digest",
        "/api/telegram/test": "telegram_test",
    }[path]
    jm._running[job_type] = jm.RunningJob(
        run_id=uuid.uuid4(), job_type=job_type, trigger="manual",
        started_at=datetime.now(timezone.utc),
    )
    r = assert_clean(client.post(path), 409)
    assert job_type in r.json()["detail"]


def test_analyze_job_trigger_is_409_for_the_same_scope(client, test_db, monkeypatch):
    import asyncio
    import backend.analyzer.cv_scorer as scorer
    gate = asyncio.Event()

    async def _slow(job_id, cv_ids=None, depth="full"):
        await gate.wait()
        return "done"
    monkeypatch.setattr(scorer, "score_single_job", _slow)

    job = make_job(test_db)
    assert_clean(client.post(f"/api/analyze/{job.id}"), 202)
    assert_clean(client.post(f"/api/analyze/{job.id}"), 409)
    gate.set()


def test_analyze_job_different_cv_sets_are_different_scopes(client, test_db, monkeypatch):
    import asyncio
    import backend.analyzer.cv_scorer as scorer
    gate = asyncio.Event()

    async def _slow(job_id, cv_ids=None, depth="full"):
        await gate.wait()
        return "done"
    monkeypatch.setattr(scorer, "score_single_job", _slow)

    job = make_job(test_db)
    assert_clean(client.post(f"/api/analyze/{job.id}", json={"cv_ids": ["a"]}), 202)
    assert_clean(client.post(f"/api/analyze/{job.id}", json={"cv_ids": ["b"]}), 202)
    gate.set()


def test_analyze_trigger_with_a_malformed_job_id_never_500s(client):
    """`uuid.UUID(job_id)` runs before the job even exists — a bad id must be clean."""
    assert_no_leak(client.post("/api/analyze/not-a-uuid"))


def test_analyze_trigger_with_a_malformed_job_id_is_404_or_422(client):
    assert client.post("/api/analyze/not-a-uuid").status_code in (404, 422)


@pytest.mark.parametrize("depth", ["banana", "", "FULL", "5"])
def test_analyze_trigger_accepts_any_depth_string(client, test_db, monkeypatch, depth):
    """Current contract: `depth` is a free query string, normalised downstream."""
    import backend.analyzer.cv_scorer as scorer

    async def _noop(job_id, cv_ids=None, depth="full"):
        return "done"
    monkeypatch.setattr(scorer, "score_single_job", _noop)
    job = make_job(test_db)
    assert_clean(client.post(f"/api/analyze/{job.id}?depth={depth}"), 202)


# ══ Monitor ══════════════════════════════════════════════════════════════════

def test_monitor_active_is_empty_by_default(client):
    assert assert_clean(client.get("/api/monitor/active"), 200).json() == []


def test_monitor_active_reports_a_running_entry(client):
    import backend.job_monitor as jm
    from datetime import datetime, timezone
    jm._running["x"] = jm.RunningJob(run_id=uuid.uuid4(), job_type="x", trigger="manual",
                                     started_at=datetime.now(timezone.utc), scope_key="s")
    body = assert_clean(client.get("/api/monitor/active"), 200).json()
    assert body[0]["job_type"] == "x" and body[0]["scope_key"] == "s"
    assert body[0]["elapsed_seconds"] >= 0


def test_monitor_in_flight_only_lists_job_scoped_runs(client):
    import backend.job_monitor as jm
    from datetime import datetime, timezone
    jid = uuid.uuid4()
    jm._running["a"] = jm.RunningJob(run_id=uuid.uuid4(), job_type="scrape_all",
                                     trigger="scheduler",
                                     started_at=datetime.now(timezone.utc))
    jm._running["b"] = jm.RunningJob(run_id=uuid.uuid4(), job_type="analyze_job",
                                     trigger="manual",
                                     started_at=datetime.now(timezone.utc),
                                     target_job_id=jid)
    body = assert_clean(client.get("/api/monitor/in-flight"), 200).json()
    assert body == {str(jid): ["analyze_job"]}


@pytest.mark.parametrize("qs", ["", "job_ids=", "job_ids=abc", f"job_ids={MISSING_UUID}",
                                "job_ids=,,,", "job_ids=" + ",".join([MISSING_UUID] * 500)])
def test_monitor_in_flight_bad_filters_never_500(client, qs):
    assert_clean(client.get(f"/api/monitor/in-flight?{qs}"), 200)


@pytest.mark.parametrize("qs", ["", "since=abc", "since=-1", "since=0",
                                f"job_ids={MISSING_UUID}",
                                "job_ids=abc", "job_ids=abc,def", "limit=1"])
def test_monitor_finished_bad_filters_never_500(client, qs):
    assert_clean(client.get(f"/api/monitor/finished?{qs}"), 200)


@pytest.mark.parametrize("since", ["99999999999999999999", "-99999999999999999999"])
@pytest.mark.xfail(strict=True, reason="R4-T1-25")
def test_monitor_finished_out_of_range_since_is_ignored(client, since):
    """The handler means to swallow an unusable `since`; an out-of-range one escapes."""
    assert client.get(f"/api/monitor/finished?since={since}").status_code == 200


@pytest.mark.parametrize("since", ["99999999999999999999"])
def test_monitor_finished_out_of_range_since_never_leaks_internals(client, since):
    assert_no_leak(client.get(f"/api/monitor/finished?since={since}"))


def test_monitor_finished_drops_unparseable_ids_but_keeps_good_ones(client):
    r = assert_clean(client.get(f"/api/monitor/finished?job_ids=abc,{MISSING_UUID}"), 200)
    assert r.json() == []


@pytest.mark.parametrize("qs", ["", "limit=1", "offset=0", "offset=-5",
                                "job_type=scrape_all", "status=failed",
                                "job_type=" + EMOJI, "status=banana"])
def test_monitor_history_query_contract(client, qs):
    assert_clean(client.get(f"/api/monitor/history?{qs}"), 200)


def test_monitor_history_rejects_a_negative_limit(client):
    assert client.get("/api/monitor/history?limit=-5").status_code == 422


def test_monitor_run_detail_missing_id_is_404(client):
    assert_clean(client.get(f"/api/monitor/run/{MISSING_UUID}"), 404)


def test_scheduler_jobs_is_a_list(client):
    assert isinstance(assert_clean(client.get("/api/scheduler/jobs"), 200).json(), list)


# ══ Stats ════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("path", [
    "/api/stats", "/api/stats/sankey", "/api/stats/score-distribution",
    "/api/stats/score-distribution?detail=true", "/api/stats/timeline",
    "/api/stats/timeline?days=1", "/api/stats/timeline?days=0",
    "/api/stats/timeline?days=-5", "/api/stats/llm-costs",
    "/api/stats/llm-costs?days=0", "/api/stats/llm-costs?days=-1",
    "/api/health/entities", "/api/health/entities?window=1",
    "/api/scrape-log", "/api/scrape-log?errors_only=true",
    "/api/scrape-log?warnings_only=true", "/api/activity-log",
    "/api/activity-log?type=scrape", "/api/activity-log?company=" + EMOJI,
])
def test_stats_endpoints_answer_cleanly(client, path):
    assert_clean(client.get(path), 200)


@pytest.mark.parametrize("path", [
    "/api/stats/timeline?days=abc", "/api/stats/llm-costs?days=abc",
    "/api/health/entities?window=abc", "/api/scrape-log?errors_only=maybe",
    "/api/activity-log?limit=abc",
])
def test_stats_endpoints_reject_bad_query_types(client, path):
    assert_clean(client.get(path), 422)


def test_llm_costs_negative_days_means_all_time(client):
    """Documented: days <= 0 disables the date filter."""
    assert assert_clean(client.get("/api/stats/llm-costs?days=-1"), 200) \
        .json()["window_days"] == -1


def test_timeline_rejects_an_out_of_range_day_count(client):
    """999999999 days overflows timedelta and escapes as a bare 500."""
    assert client.get("/api/stats/timeline?days=999999999").status_code == 422


def test_timeline_out_of_range_day_count_never_leaks_internals(client):
    assert_no_leak(client.get("/api/stats/timeline?days=999999999"))


def test_health_entities_rejects_a_non_positive_window(client, test_db):
    """window=0 flags every active company with "No results in the last 0 scrapes"."""
    make_company(test_db, name="Acme", active=True)
    r = client.get("/api/health/entities?window=0")
    assert r.status_code == 422 or r.json()["count"] == 0


def test_score_distribution_ignores_malformed_cv_scores(client, test_db):
    make_job(test_db, cv_scores={"A": 55})
    make_job(test_db, cv_scores={"A": "high"}, url="https://x.com/2")
    make_job(test_db, cv_scores=[], url="https://x.com/3")
    r = assert_clean(client.get("/api/stats/score-distribution?detail=true"), 200)
    assert r.json()["scored_count"] == 1


def test_sankey_tolerates_malformed_transition_rows(client, test_db):
    from backend.models.db import Application
    job = make_job(test_db)
    test_db.add(Application(job_id=job.id, status="applied", status_transitions=[
        {"to": "applied"}, {"from": "applied"}, {}, {"from": "applied", "to": "offer"},
    ]))
    test_db.commit()
    r = assert_clean(client.get("/api/stats/sankey"), 200)
    assert {"source": "applied", "target": "offer", "value": 1} in r.json()


# ══ Telegram ═════════════════════════════════════════════════════════════════

def test_telegram_webhook_without_a_configured_secret_is_503(client):
    assert_clean(client.post("/api/telegram/webhook", json={},
                             headers={"X-API-Key": ""}), 503)


def test_telegram_webhook_with_a_wrong_secret_is_401(client, test_db):
    set_setting(test_db, "telegram_webhook_secret", "s3cret")
    assert_clean(client.post("/api/telegram/webhook", json={},
                             headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"}), 401)


def test_telegram_webhook_with_the_right_secret_accepts_an_empty_update(client, test_db):
    set_setting(test_db, "telegram_webhook_secret", "s3cret")
    assert_clean(client.post("/api/telegram/webhook", json={},
                             headers={"X-Telegram-Bot-Api-Secret-Token": "s3cret"}), 200)


@pytest.mark.parametrize("update", [
    {"callback_query": None}, {"callback_query": {}},
    {"callback_query": {"data": None}},
])
def test_telegram_webhook_malformed_updates_never_500(client, test_db, update, monkeypatch):
    import backend.notifier.telegram as tg

    async def _noop(data, message_id):
        return "ok"
    monkeypatch.setattr(tg, "handle_callback", _noop, raising=False)
    set_setting(test_db, "telegram_webhook_secret", "s3cret")
    assert_clean(client.post("/api/telegram/webhook", json=update,
                             headers={"X-Telegram-Bot-Api-Secret-Token": "s3cret"}), 200)


@pytest.mark.parametrize("url", ["", "http://x.com", "ftp://x.com", "x.com", "//x.com"])
def test_register_webhook_requires_https(client, url):
    assert_clean(client.post("/api/telegram/register-webhook",
                             json={"public_url": url}), 400)


def test_register_webhook_missing_body_key_is_400(client):
    assert_clean(client.post("/api/telegram/register-webhook", json={}), 400)


def test_rotate_webhook_secret_returns_a_new_value(client, test_db):
    set_setting(test_db, "telegram_webhook_secret", "old")
    r = assert_clean(client.post("/api/telegram/rotate-webhook-secret"), 200)
    assert r.json()["webhook_secret"] != "old"


@pytest.mark.xfail(strict=True, reason="R4-T1-26")
def test_telegram_webhook_null_message_is_not_a_500(client, test_db, monkeypatch):
    """`callback_query.get("message", {}).get(...)` breaks on an explicit null."""
    import backend.notifier.telegram as tg

    async def _noop(data, message_id):
        return "ok"
    monkeypatch.setattr(tg, "handle_callback", _noop, raising=False)
    set_setting(test_db, "telegram_webhook_secret", "s3cret")
    assert client.post("/api/telegram/webhook", json={"callback_query": {"message": None}},
                       headers={"X-Telegram-Bot-Api-Secret-Token": "s3cret"}).status_code == 200


def test_telegram_webhook_null_message_never_leaks_internals(client, test_db):
    set_setting(test_db, "telegram_webhook_secret", "s3cret")
    assert_no_leak(client.post("/api/telegram/webhook",
                               json={"callback_query": {"message": None}},
                               headers={"X-Telegram-Bot-Api-Secret-Token": "s3cret"}))


# ── R4 fix-loop regressions ──────────────────────────────────────────────────

@pytest.mark.parametrize("path", [
    "/api/monitor/history?limit=-5", "/api/monitor/finished?limit=-5",
    "/api/activity-log?limit=-3", "/api/scrape-log?limit=-3",
])
def test_negative_limit_is_422_on_every_system_listing(client, path):
    """R4-T1-07: a plain `int` limit reached Postgres as LIMIT -5."""
    assert_clean(client.get(path), 422)


@pytest.mark.parametrize("path", [
    "/api/monitor/history?offset=-5", "/api/activity-log?offset=-5",
])
def test_negative_offset_stays_clamped_not_rejected(client, path):
    """`offset` was already clamped with max(0, …) and keeps that contract."""
    assert_clean(client.get(path), 200)


@pytest.mark.parametrize("days", [0, -5, 1, 30, 3650])
def test_timeline_still_accepts_the_windows_the_ui_uses(client, days):
    """R4-T1-08 bounds only the top: days<=0 is a legal empty window."""
    assert_clean(client.get(f"/api/stats/timeline?days={days}"), 200)


@pytest.mark.parametrize("days", [3651, 999999999, 10**12])
def test_timeline_rejects_a_window_that_overflows_timedelta(client, days):
    assert_clean(client.get(f"/api/stats/timeline?days={days}"), 422)


@pytest.mark.parametrize("window", [0, -1, -100])
def test_health_entities_rejects_a_non_positive_window_value(client, test_db, window):
    """R4-T1-10: window=0 made all([]) true and flagged every active entity."""
    make_company(test_db, name="Acme", active=True)
    assert_clean(client.get(f"/api/health/entities?window={window}"), 422)


def test_health_entities_still_answers_for_a_sane_window(client, test_db):
    make_company(test_db, name="Acme", active=True)
    r = assert_clean(client.get("/api/health/entities?window=3"), 200)
    assert r.json()["count"] == 0


@pytest.mark.parametrize("bad", ["not-a-uuid", "1", "abc-def"])
def test_analyze_trigger_malformed_job_id_is_404(client, bad):
    """R4-T1-23: uuid.UUID(job_id) ran inside the launch call, before any lookup."""
    assert_clean(client.post(f"/api/analyze/{bad}"), 404)


@pytest.mark.parametrize("path", ["/api/auth/verify", "/api/auth/set-session"])
@pytest.mark.parametrize("key", [5, 1.5, [1], {"a": 1}, True])
def test_auth_wrongly_typed_key_is_401(client, path, key):
    """R4-T1-24: hmac.compare_digest(5, expected) raised TypeError on a public route."""
    assert_clean(client.post(path, json={"api_key": key},
                             headers={"X-API-Key": API_KEY}), 401)


def test_auth_still_accepts_the_real_key(client):
    assert_clean(client.post("/api/auth/verify", json={"api_key": API_KEY},
                             headers={"X-API-Key": API_KEY}), 200)
