"""Smoke test for new conftest fixtures."""
import pytest


def test_test_db_fixture_creates_tables(test_db):
    """test_db yields a SQLAlchemy session with all tables created in SQLite."""
    from backend.models.db import Setting
    test_db.add(Setting(key="smoke", value="ok"))
    test_db.commit()
    row = test_db.query(Setting).filter(Setting.key == "smoke").first()
    assert row is not None
    assert row.value == "ok"


def test_api_client_fixture_returns_client(api_client):
    """api_client yields a FastAPI TestClient wired to the in-memory DB."""
    resp = api_client.get("/health")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_mock_httpx_fixture(mock_httpx):
    """mock_httpx yields a dict with 'client' and 'response' mocks."""
    import httpx
    async with httpx.AsyncClient() as client:
        resp = await client.get("http://example.com/api")
        assert resp is mock_httpx["response"]


def test_mock_telegram_fixture(mock_telegram):
    """mock_telegram is a list that captures telegram HTTP calls during the test."""
    assert mock_telegram is not None
    assert isinstance(mock_telegram, list)
