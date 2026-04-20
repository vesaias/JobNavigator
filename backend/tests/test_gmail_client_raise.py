"""Regression: gmail_client top-level errors propagate so tracked_run marks JobRun failed."""
import pytest


@pytest.mark.asyncio
async def test_check_emails_propagates_service_error(monkeypatch):
    """When something inside check_emails raises, it should re-raise (not swallow).

    Previously the top-level ``except Exception`` in ``check_emails`` logged + called
    ``log_activity`` but never re-raised, so when the scheduler ran it via
    ``tracked_run`` the JobRun was marked ``completed`` instead of ``failed``.
    """
    from backend.email_monitor import gmail_client

    entry_fn = getattr(gmail_client, "check_emails", None) or getattr(
        gmail_client, "run_email_check", None
    )
    assert entry_fn is not None, "expected check_emails or run_email_check entry point"

    # Ensure we get past the `if not access_token: return` early-out.
    async def fake_token():
        return "fake-token"

    # Force failure INSIDE the try block. `_load_processed_ids` is the first call
    # after `db = SessionLocal()` and executes inside the top-level try/except.
    def broken_loader(*a, **kw):
        raise RuntimeError("simulated gmail service failure")

    monkeypatch.setattr(gmail_client, "_get_access_token", fake_token)
    monkeypatch.setattr(gmail_client, "_load_processed_ids", broken_loader)

    # Stub activity log to avoid DB writes — it's imported locally inside the
    # except block via `from backend.activity import log_activity`.
    import backend.activity as _activity
    monkeypatch.setattr(_activity, "log_activity", lambda *a, **kw: None, raising=False)

    with pytest.raises(RuntimeError, match="simulated gmail"):
        await entry_fn()
