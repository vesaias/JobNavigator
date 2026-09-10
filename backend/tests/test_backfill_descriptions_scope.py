"""The description backfill must reach hand-logged jobs too: they land at
`applied` straight away, so a `new`/`saved` filter never repairs them."""
import uuid

import pytest

from backend.models.db import Job


def _job(db, status, description=""):
    j = Job(id=uuid.uuid4(), external_id=uuid.uuid4().hex, company="Acme",
            title=f"PM {status}", url=f"https://acme.com/{status}", status=status,
            description=description)
    db.add(j)
    db.commit()
    return j


@pytest.mark.asyncio
async def test_backfill_covers_applied_jobs(test_db, monkeypatch):
    import backend.main as main
    captured = {}

    def _capture(job_type, coro_func, **kw):
        captured["func"] = coro_func
        return "run-1"

    monkeypatch.setattr(main, "launch_background", _capture)

    applied = _job(test_db, "applied")
    saved = _job(test_db, "saved")
    rejected = _job(test_db, "rejected")

    async def fake_fetch(url):
        # The backfill drops anything under 50 chars, so pad it.
        return f"JD for {url} — senior product role, roadmapping, discovery."

    monkeypatch.setattr("backend.scraper.ats._descriptions._fetch_job_description", fake_fetch)
    monkeypatch.setattr("asyncio.sleep", lambda *a, **kw: _noop())

    await main.trigger_backfill_descriptions()
    await captured["func"]()

    test_db.expire_all()
    assert test_db.query(Job).filter(Job.id == applied.id).first().description .startswith("JD for https://acme.com/applied")
    assert test_db.query(Job).filter(Job.id == saved.id).first().description .startswith("JD for https://acme.com/saved")
    # An out-of-scope status stays untouched -- the backfill is not a free-for-all.
    assert not (test_db.query(Job).filter(Job.id == rejected.id).first().description or "")


async def _noop():
    return None
