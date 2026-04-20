"""Tests for the Telegram webhook secret-token validation (#11)."""
from backend.models.db import Setting


def _seed_first_run(test_db):
    """Empty dashboard_api_key → first-run auth bypass for admin endpoints."""
    test_db.add(Setting(key="dashboard_api_key", value=""))
    test_db.commit()


def _seed_secret(test_db, value: str):
    test_db.add(Setting(key="telegram_webhook_secret", value=value, description="x"))
    test_db.commit()


def test_webhook_rejects_missing_header(api_client, test_db):
    """No X-Telegram-Bot-Api-Secret-Token header → 401."""
    _seed_secret(test_db, "correct-secret-abc")
    resp = api_client.post("/api/telegram/webhook", json={"update_id": 1})
    assert resp.status_code == 401


def test_webhook_rejects_wrong_header(api_client, test_db):
    """Wrong secret → 401 (uses hmac.compare_digest, constant time)."""
    _seed_secret(test_db, "correct-secret-abc")
    resp = api_client.post(
        "/api/telegram/webhook",
        json={"update_id": 1},
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
    )
    assert resp.status_code == 401


def test_webhook_rejects_empty_configured_secret(api_client, test_db):
    """If the configured secret is empty → 503 (service misconfigured),
    NEVER accept anonymous traffic."""
    _seed_secret(test_db, "")
    resp = api_client.post(
        "/api/telegram/webhook",
        json={"update_id": 1},
        headers={"X-Telegram-Bot-Api-Secret-Token": ""},
    )
    assert resp.status_code == 503


def test_webhook_accepts_correct_header(api_client, test_db, monkeypatch):
    """Matching header → 200 and handler is invoked."""
    _seed_secret(test_db, "correct-secret-abc")

    called = {"count": 0}

    async def fake_handle(data, message_id):
        called["count"] += 1
        return "ok"

    monkeypatch.setattr("backend.notifier.telegram.handle_callback", fake_handle)
    # Prevent the answerCallbackQuery httpx call from firing; easier than mocking
    monkeypatch.setattr("backend.main.TELEGRAM_BOT_TOKEN", "", raising=False)

    resp = api_client.post(
        "/api/telegram/webhook",
        json={
            "update_id": 1,
            "callback_query": {
                "id": "cb-1",
                "data": "noop",
                "message": {"message_id": 42},
            },
        },
        headers={"X-Telegram-Bot-Api-Secret-Token": "correct-secret-abc"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert called["count"] == 1


def test_rotate_webhook_secret_changes_value(api_client, test_db):
    """POST /api/telegram/rotate-webhook-secret returns a new value + persists it."""
    _seed_first_run(test_db)
    _seed_secret(test_db, "old-secret")
    resp = api_client.post("/api/telegram/rotate-webhook-secret")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    new_secret = data["webhook_secret"]
    assert new_secret and new_secret != "old-secret"
    # Persisted in DB
    row = test_db.query(Setting).filter(Setting.key == "telegram_webhook_secret").first()
    assert row.value == new_secret


def test_register_webhook_rejects_non_https(api_client, test_db):
    """register-webhook must reject http:// — Telegram only accepts https."""
    _seed_first_run(test_db)
    _seed_secret(test_db, "abc")
    resp = api_client.post(
        "/api/telegram/register-webhook",
        json={"public_url": "http://example.com"},
    )
    assert resp.status_code == 400


def test_seed_generates_random_webhook_secret(test_db):
    """First run: seed_settings populates telegram_webhook_secret with a
    cryptographically random value when the row is empty."""
    from backend.seed import seed_settings
    seed_settings(test_db)
    row = test_db.query(Setting).filter(Setting.key == "telegram_webhook_secret").first()
    assert row is not None
    assert row.value and len(row.value) >= 32
