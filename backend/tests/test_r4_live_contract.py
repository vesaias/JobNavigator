"""R4-T1 · contract checks that only Postgres reproduces.

The SQLite test DB cannot exercise the `DataError -> 404` handler (it raises a
different exception class for a malformed UUID) or `LIMIT -5` (SQLite treats a
negative limit as "no limit"), so those are pinned here against the running
stack, over HTTP, using GETs only — this module never writes.

Auto-skips when the stack is not reachable, so the suite stays green outside the
backend container.
"""
import os

import pytest

pytestmark = pytest.mark.live

BASE = os.getenv("JN_LIVE_BASE", "http://caddy")


def _key():
    if os.getenv("JN_API_KEY"):
        return os.getenv("JN_API_KEY")
    try:
        from backend.config import INITIAL_API_KEY
        return INITIAL_API_KEY or ""
    except Exception:
        return ""


@pytest.fixture(scope="module")
def live():
    """An httpx client against the running stack, or a skip."""
    httpx = pytest.importorskip("httpx")
    client = httpx.Client(base_url=BASE, headers={"X-API-Key": _key()}, timeout=30)
    try:
        r = client.get("/health")
    except Exception as e:                      # noqa: BLE001 - any transport error
        client.close()
        pytest.skip(f"live stack not reachable at {BASE}: {e}")
    if r.status_code != 200:
        client.close()
        pytest.skip(f"live stack unhealthy at {BASE}: {r.status_code}")
    if client.get("/api/jobs?limit=1").status_code == 401:
        client.close()
        pytest.skip("no usable API key for the live stack")
    yield client
    client.close()


def _clean(resp, *allowed):
    body = resp.text or ""
    for marker in ("Traceback (most recent call last)", "/app/backend/",
                   "site-packages", 'File "', "sqlalchemy.exc", "psycopg2.errors"):
        assert marker not in body, f"{marker!r} leaked: {body[:300]}"
    if allowed:
        assert resp.status_code in allowed, f"expected {allowed}, got {resp.status_code}: {body[:300]}"
    return resp


# ── DataError -> 404 (malformed UUID in a path segment) ──────────────────────

@pytest.mark.parametrize("path", [
    "/api/jobs/abc", "/api/jobs/1", "/api/jobs/%C3%A9%C3%A8",
    "/api/monitor/run/abc", "/api/resumes/abc", "/api/cover-letters/abc",
    "/api/jobs/abc/cached-page", "/api/resumes/abc/preview",
    "/api/resumes/abc/tracer-stats", "/api/cover-letters/abc/tracer-stats",
])
def test_malformed_uuid_in_a_path_is_404(live, path):
    _clean(live.get(path), 404)
    assert live.get(path).json()["detail"] == "Not found"


# ── Malformed UUID in a query filter ─────────────────────────────────────────

@pytest.mark.parametrize("path", ["/api/jobs?search_id=abc", "/api/cover-letters?job_id=abc"])
def test_malformed_uuid_in_a_filter_is_currently_404(live, path):
    """Current contract, recorded: a list endpoint answers "Not found"."""
    _clean(live.get(path), 404)


@pytest.mark.parametrize("path", ["/api/jobs?search_id=abc", "/api/cover-letters?job_id=abc"])
@pytest.mark.xfail(strict=True, reason="R4-T1-09")
def test_malformed_uuid_in_a_filter_should_be_422(live, path):
    """A bad *filter* value is a request error, not a missing resource."""
    assert live.get(path).status_code == 422


@pytest.mark.parametrize("path", ["/api/monitor/finished?job_ids=abc",
                                  "/api/monitor/in-flight?job_ids=abc"])
def test_monitor_filters_drop_unparseable_ids_instead(live, path):
    """These two do it the graceful way — the inconsistency is the finding."""
    _clean(live.get(path), 200)


# ── Negative LIMIT ───────────────────────────────────────────────────────────

NEGATIVE_LIMIT_PATHS = [
    "/api/jobs?limit=-5",
    "/api/jobs/unscored-ids?limit=-5",
    "/api/monitor/history?limit=-5",
    "/api/monitor/finished?limit=-5",
    "/api/activity-log?limit=-3",
    "/api/scrape-log?limit=-3",
    "/api/applications?limit=-3",
]


@pytest.mark.parametrize("path", NEGATIVE_LIMIT_PATHS)
@pytest.mark.xfail(strict=True, reason="R4-T1-07")
def test_negative_limit_is_rejected_not_a_500(live, path):
    assert live.get(path).status_code == 422


@pytest.mark.parametrize("path", NEGATIVE_LIMIT_PATHS)
def test_negative_limit_never_leaks_internals(live, path):
    _clean(live.get(path))


def test_negative_offset_is_clamped_not_an_error(live):
    _clean(live.get("/api/monitor/history?offset=-5"), 200)


# ── Other numeric edges ──────────────────────────────────────────────────────

@pytest.mark.xfail(strict=True, reason="R4-T1-10")
def test_health_entities_rejects_a_negative_window(live):
    assert live.get("/api/health/entities?window=-1").status_code == 422


@pytest.mark.xfail(strict=True, reason="R4-T1-10")
def test_health_entities_window_zero_does_not_flag_everything(live):
    """window=0 makes `all([])` true, so every active entity looks broken."""
    r = live.get("/api/health/entities?window=0")
    assert r.status_code == 422 or r.json()["count"] == 0


@pytest.mark.xfail(strict=True, reason="R4-T1-08")
def test_timeline_rejects_an_out_of_range_day_count(live):
    assert live.get("/api/stats/timeline?days=999999999").status_code == 422


def test_timeline_out_of_range_returns_a_bare_body_not_a_trace(live):
    r = live.get("/api/stats/timeline?days=999999999")
    _clean(r)
    assert r.text.strip() in ("Internal Server Error", '{"detail":"Internal server error"}')


# ── Things that already behave ───────────────────────────────────────────────

@pytest.mark.parametrize("path", [
    "/api/jobs?min_score=abc", "/api/jobs?remote=maybe", "/api/jobs?limit=abc",
    "/api/stats/timeline?days=abc", "/api/companies?tier=abc",
    "/api/companies?active=maybe",
])
def test_wrongly_typed_query_params_are_422(live, path):
    _clean(live.get(path), 422)


@pytest.mark.parametrize("path", [
    "/api/jobs?company=%F0%9F%9A%80", "/api/jobs?title_search=%F0%9F%9A%80%20Se%C3%B1or",
    "/api/activity-log?company=%F0%9F%9A%80", "/api/jobs?status=zzz",
    "/api/jobs?source=zzz", "/api/applications?status=zzz",
])
def test_unicode_and_unknown_filter_values_return_an_empty_page(live, path):
    _clean(live.get(path), 200)


@pytest.mark.parametrize("size", [3000, 6000])
def test_a_huge_query_string_is_handled(live, size):
    _clean(live.get("/api/jobs?title_search=" + "a" * size), 200, 414, 431)


def test_llm_models_unknown_provider_is_400(live):
    _clean(live.get("/api/llm/models?provider=bogus"), 400)


def test_settings_never_return_a_secret_value(live):
    body = live.get("/api/settings").text
    _clean(live.get("/api/settings"), 200)
    for env_key in ("ANTHROPIC_API_KEY", "TELEGRAM_BOT_TOKEN", "GMAIL_CLIENT_SECRET",
                    "GMAIL_REFRESH_TOKEN", "INITIAL_API_KEY"):
        value = os.getenv(env_key, "")
        if len(value) > 8:
            assert value not in body, f"{env_key} leaked through GET /api/settings"


def test_protected_routes_require_a_key(live):
    r = live.get("/api/jobs", headers={"X-API-Key": ""})
    assert r.status_code == 401
