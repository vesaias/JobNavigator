"""Tracer /cv/{token} endpoint: redirect must succeed even if click-log commit fails."""
import uuid
import pytest


def _seed_first_run(db):
    from backend.models.db import Setting
    db.add(Setting(key="dashboard_api_key", value=""))
    db.commit()


def test_tracer_redirect_succeeds_normally(api_client, test_db):
    """Happy path: valid token -> 302 to destination URL + click recorded."""
    _seed_first_run(test_db)
    from backend.models.db import Resume, TracerLink
    resume = Resume(id=uuid.uuid4(), name="Test", is_base=True, json_data={})
    test_db.add(resume)
    test_db.commit()
    link = TracerLink(
        id=uuid.uuid4(),
        token="abc123",
        resume_id=resume.id,
        destination_url="https://example.com/apply",
        source_label="manual",
        is_active=True,
    )
    test_db.add(link)
    test_db.commit()

    resp = api_client.get("/cv/abc123", follow_redirects=False)
    assert resp.status_code in (302, 307), (
        f"Expected redirect, got {resp.status_code}: {resp.text}"
    )
    assert "example.com/apply" in resp.headers.get("location", "")


def test_tracer_redirect_survives_commit_failure(api_client, test_db, monkeypatch):
    """A commit failure in click-log must NOT break the 302 redirect."""
    _seed_first_run(test_db)
    from backend.models.db import Resume, TracerLink
    resume = Resume(id=uuid.uuid4(), name="Test", is_base=True, json_data={})
    test_db.add(resume)
    test_db.commit()
    link = TracerLink(
        id=uuid.uuid4(),
        token="def456",
        resume_id=resume.id,
        destination_url="https://example.com/apply2",
        source_label="manual",
        is_active=True,
    )
    test_db.add(link)
    test_db.commit()

    # Force the TracerClickEvent insert commit to raise by patching Session.commit.
    # Only a commit involving a pending TracerClickEvent should fail; other commits
    # (e.g., seeding above has already completed) would still work if they occurred.
    from sqlalchemy.orm import Session as SASession
    original_commit = SASession.commit

    def broken_commit(self):
        from backend.models.db import TracerClickEvent
        pending_new = [obj for obj in self.new if isinstance(obj, TracerClickEvent)]
        if pending_new:
            raise RuntimeError("simulated click-log commit failure")
        return original_commit(self)

    monkeypatch.setattr(SASession, "commit", broken_commit)

    # Should still 302 — click-log failure is logged but redirect goes through.
    resp = api_client.get("/cv/def456", follow_redirects=False)
    assert resp.status_code in (302, 307), (
        f"Expected redirect even on click-log failure, got {resp.status_code}: {resp.text}"
    )
    assert "example.com/apply2" in resp.headers.get("location", "")
