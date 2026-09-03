"""R3-A-07: run summaries must use a real plural, not noun + "s".

The email-check summary read "1 repl" / "2 repls" because the only way to get
"replies" out of the "+s" rule was to pass the stem "repl". _activity_summary now
takes an explicit plural.
"""
from datetime import datetime, timedelta, timezone

import pytest

pytest.importorskip("apscheduler")   # scheduler.py imports it at module level

from backend.models.db import ActivityLog


def _rows(db, n, log_type="email"):
    for i in range(n):
        db.add(ActivityLog(type=log_type, message=f"m{i}"))
    db.commit()


def _since():
    return datetime.now(timezone.utc) - timedelta(minutes=5)


def test_singular_reply(test_db):
    from backend.scheduler import _activity_summary
    _rows(test_db, 1)
    assert _activity_summary(_since(), "email", "reply", "replies") == "1 reply"


def test_plural_replies(test_db):
    from backend.scheduler import _activity_summary
    _rows(test_db, 3)
    assert _activity_summary(_since(), "email", "reply", "replies") == "3 replies"


def test_zero_is_still_empty(test_db):
    """An empty string is what makes the caller's `or "No new replies"` fire."""
    from backend.scheduler import _activity_summary
    assert _activity_summary(_since(), "email", "reply", "replies") == ""


def test_regular_nouns_need_no_plural_argument(test_db):
    """The digest's "alert" / "alerts" caller keeps working unchanged."""
    from backend.scheduler import _activity_summary
    _rows(test_db, 1, log_type="telegram")
    assert _activity_summary(_since(), "telegram", "alert") == "1 alert"
    _rows(test_db, 1, log_type="telegram")
    assert _activity_summary(_since(), "telegram", "alert") == "2 alerts"


@pytest.mark.asyncio
async def test_email_check_run_summary_reads_reply(test_db, monkeypatch):
    """The scheduled email check writes the pluralised string to JobRun.summary."""
    import backend.scheduler as sched

    async def fake_check_emails():
        test_db.add(ActivityLog(type="email", message="Email check: 2 messages found"))
        test_db.commit()

    import backend.email_monitor.gmail_client as gmail
    monkeypatch.setattr(gmail, "check_emails", fake_check_emails)

    await sched.run_email_check()

    from backend.models.db import JobRun
    run = test_db.query(JobRun).filter(JobRun.job_type == "email_check").one()
    assert run.result_summary == "1 reply"
