"""get_all_running() exposes target_job_id (Task 10 of 12)."""
import uuid
from datetime import datetime, timezone


def test_active_includes_target_job_id(monkeypatch):
    """Each entry in /api/monitor/active returns target_job_id (str or None)."""
    from backend.job_monitor import RunningJob, get_all_running
    import backend.job_monitor as mon

    job_uuid = uuid.uuid4()
    fake = {
        "tailor_resume:base1:job1": RunningJob(
            run_id=uuid.uuid4(),
            job_type="tailor_resume",
            trigger="manual",
            started_at=datetime.now(timezone.utc),
            scope_key="base1:job1",
            target_job_id=job_uuid,
        ),
        "scrape_all": RunningJob(
            run_id=uuid.uuid4(),
            job_type="scrape_all",
            trigger="scheduler",
            started_at=datetime.now(timezone.utc),
            scope_key=None,
            target_job_id=None,
        ),
    }
    monkeypatch.setattr(mon, "_running", fake)

    rows = get_all_running()
    assert len(rows) == 2
    by_type = {r["job_type"]: r for r in rows}
    assert by_type["tailor_resume"]["target_job_id"] == str(job_uuid)
    assert by_type["scrape_all"]["target_job_id"] is None


def test_active_includes_company_id_for_company_scrape(monkeypatch):
    """X-01: a company_scrape entry carries the Company id, not just a scope_key."""
    from backend.job_monitor import RunningJob, get_all_running
    import backend.job_monitor as mon

    company_uuid = str(uuid.uuid4())
    fake = {
        f"company_scrape:{company_uuid}": RunningJob(
            run_id=uuid.uuid4(),
            job_type="company_scrape",
            trigger="manual",
            started_at=datetime.now(timezone.utc),
            scope_key=company_uuid,
            company_id=company_uuid,
        ),
        "scrape_all": RunningJob(
            run_id=uuid.uuid4(),
            job_type="scrape_all",
            trigger="scheduler",
            started_at=datetime.now(timezone.utc),
        ),
    }
    monkeypatch.setattr(mon, "_running", fake)

    by_type = {r["job_type"]: r for r in get_all_running()}
    assert by_type["company_scrape"]["company_id"] == company_uuid
    assert by_type["company_scrape"]["scope_key"] == company_uuid   # unchanged
    assert by_type["scrape_all"]["company_id"] is None


def test_launch_background_stores_company_id(monkeypatch):
    """launch_background(company_id=...) lands on the in-memory run record."""
    import asyncio
    import backend.job_monitor as mon

    monkeypatch.setattr(mon, "_insert_job_run", lambda *a, **k: None)
    monkeypatch.setattr(mon, "_finish_job_run", lambda *a, **k: None)
    monkeypatch.setattr(mon, "_running", {})

    company_uuid = str(uuid.uuid4())
    gate = asyncio.Event()

    async def _body():
        await gate.wait()

    async def _drive():
        mon.launch_background(
            "company_scrape", _body, trigger="manual",
            scope_key=company_uuid, company_id=company_uuid,
        )
        rows = mon.get_all_running()
        assert len(rows) == 1
        assert rows[0]["job_type"] == "company_scrape"
        assert rows[0]["company_id"] == company_uuid
        gate.set()
        await asyncio.sleep(0)

    asyncio.run(_drive())
