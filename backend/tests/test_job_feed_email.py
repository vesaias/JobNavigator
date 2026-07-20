import pytest

from backend.models.db import (
    ApplicationQueueItem,
    Job,
    JobFeedPosting,
    Persona,
    Setting,
)


def _notification_item(test_db, *, status="pending_tailor", attempts=0):
    job = Job(
        external_id=f"email-{status}-{attempts}",
        content_hash=f"email-content-{status}-{attempts}",
        company="Acme",
        title="2027 Software Engineer Intern",
        location="United States",
        url="https://boards.greenhouse.io/acme/jobs/12345",
        source="speedyapply_intern_usa",
        description="Build Python services.",
    )
    test_db.add(job)
    test_db.flush()
    test_db.add(JobFeedPosting(
        source_id="speedyapply_intern_usa",
        repository_id="speedyapply/2027-SWE-College-Jobs",
        source_key=f"greenhouse:{status}:{attempts}",
        job_id=job.id,
        source_url=job.url,
    ))
    item = ApplicationQueueItem(
        job_id=job.id,
        source_feed="speedyapply_intern_usa",
        application_url=job.url,
        status=status,
        attempts=attempts,
        artifact_dir="application-packets/2026-07-19/acme-role",
    )
    test_db.add_all([
        item,
        Persona(id=1, contact={"email": "candidate@example.com"}, resume_content={}),
        Setting(key="job_feeds_email_enabled", value="true"),
    ])
    test_db.commit()
    return item


@pytest.mark.asyncio
async def test_detected_and_terminal_notifications_are_sent_once(test_db, monkeypatch):
    item = _notification_item(test_db, status="ready", attempts=1)
    sent = []

    async def fake_send(to, subject, text, html):
        sent.append({"to": to, "subject": subject, "text": text, "html": html})
        return True

    monkeypatch.setattr("backend.email_monitor.gmail_client.send_gmail_message", fake_send)

    from backend.notifier.email import dispatch_pending_notifications

    first = await dispatch_pending_notifications()
    second = await dispatch_pending_notifications()

    assert first == {"detected": 1, "terminal": 1}
    assert second == {"detected": 0, "terminal": 0}
    assert len(sent) == 2
    assert sent[0]["to"] == "candidate@example.com"
    assert sent[0]["subject"].startswith("[New Job]")
    assert sent[1]["subject"].startswith("[Resume Ready]")
    assert "application-packets/2026-07-19/acme-role" in sent[1]["text"]

    test_db.expire_all()
    refreshed = test_db.query(ApplicationQueueItem).filter(ApplicationQueueItem.id == item.id).one()
    assert refreshed.detected_notified_at is not None
    assert refreshed.terminal_notified_at is not None


@pytest.mark.asyncio
async def test_failed_packet_not_notified_until_third_attempt(test_db, monkeypatch):
    item = _notification_item(test_db, status="failed", attempts=2)
    sent = []

    async def fake_send(*args):
        sent.append(args)
        return True

    monkeypatch.setattr("backend.email_monitor.gmail_client.send_gmail_message", fake_send)
    from backend.notifier.email import send_terminal_notification

    assert await send_terminal_notification(str(item.id)) is False
    assert sent == []

    item.attempts = 3
    test_db.commit()
    assert await send_terminal_notification(str(item.id)) is True
    assert len(sent) == 1


@pytest.mark.asyncio
async def test_gmail_failure_leaves_timestamp_unset_for_retry(test_db, monkeypatch):
    item = _notification_item(test_db)

    async def fail_send(*args):
        return False

    monkeypatch.setattr("backend.email_monitor.gmail_client.send_gmail_message", fail_send)
    from backend.notifier.email import send_detected_notification

    assert await send_detected_notification(str(item.id)) is False
    test_db.expire_all()
    refreshed = test_db.query(ApplicationQueueItem).filter(ApplicationQueueItem.id == item.id).one()
    assert refreshed.detected_notified_at is None


@pytest.mark.asyncio
async def test_dispatch_ignores_preexisting_non_feed_queue_items(test_db, monkeypatch):
    job = Job(
        external_id="legacy-queue-job",
        content_hash="legacy-queue-content",
        company="Old Co",
        title="Software Engineer",
        url="https://example.com/legacy",
        source="manual",
    )
    test_db.add(job)
    test_db.flush()
    test_db.add_all([
        ApplicationQueueItem(job_id=job.id, status="ready", attempts=1),
        Persona(id=1, contact={"email": "candidate@example.com"}, resume_content={}),
        Setting(key="job_feeds_email_enabled", value="true"),
    ])
    test_db.commit()
    sent = []

    async def fake_send(*args):
        sent.append(args)
        return True

    monkeypatch.setattr("backend.email_monitor.gmail_client.send_gmail_message", fake_send)
    from backend.notifier.email import dispatch_pending_notifications

    assert await dispatch_pending_notifications() == {"detected": 0, "terminal": 0}
    assert sent == []
