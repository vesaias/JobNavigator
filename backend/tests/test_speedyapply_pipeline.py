import uuid

import pytest

from backend.automation.speedyapply_pipeline import (
    enqueue_candidates,
    prepare_queue_item,
    resolve_base_resume_key,
    run_speedyapply_pipeline,
)
from backend.models.db import ApplicationQueueItem, Job, Persona, Resume, Setting, SessionLocal


def _job(test_db, suffix="1", description="A detailed role requiring Python and APIs"):
    job = Job(
        external_id=f"speedy-{suffix}",
        content_hash=f"speedy-content-{suffix}",
        company="Acme",
        title="Software Engineer",
        url=f"https://jobs.example.com/{suffix}",
        description=description,
        source="speedyapply_new_grad_usa",
    )
    test_db.add(job)
    test_db.commit()
    return job


def _base_resume(test_db):
    resume = Resume(
        name="Base SWE",
        is_base=True,
        json_data={"summary": "Engineer", "experience": [], "skills": {"Languages": "Python"}},
    )
    test_db.add(resume)
    test_db.commit()
    return resume


def test_resolve_base_resume_prefers_feature_setting_then_persona(test_db):
    base = _base_resume(test_db)
    test_db.add(Setting(key="speedyapply_resume_id", value=str(base.id)))
    test_db.commit()
    assert resolve_base_resume_key(test_db) == str(base.id)

    test_db.query(Setting).filter(Setting.key == "speedyapply_resume_id").delete()
    test_db.delete(base)
    test_db.add(Persona(id=1, resume_content={"summary": "Persona engineer"}))
    test_db.commit()
    assert resolve_base_resume_key(test_db) == "persona"


@pytest.mark.asyncio
async def test_prepare_queue_item_creates_and_links_tailored_resume(test_db, monkeypatch):
    job = _job(test_db)
    base = _base_resume(test_db)
    test_db.add(Setting(key="speedyapply_resume_id", value=str(base.id)))
    test_db.commit()
    item_id = enqueue_candidates([{"job_id": str(job.id), "feed_id": "new_grad_usa"}])[0]

    async def fake_tailor(base_resume_key, job_id):
        db = SessionLocal()
        try:
            resume = Resume(
                name="Tailored for Acme",
                is_base=False,
                parent_id=uuid.UUID(base_resume_key),
                job_id=uuid.UUID(job_id),
                json_data={"summary": "Tailored"},
            )
            db.add(resume)
            db.commit()
            return str(resume.id)
        finally:
            db.close()

    monkeypatch.setattr("backend.automation.speedyapply_pipeline._tailor_resume", fake_tailor)

    async def fake_export(item_id):
        db = SessionLocal()
        try:
            item = db.query(ApplicationQueueItem).filter(ApplicationQueueItem.id == uuid.UUID(item_id)).first()
            item.status = "ready"
            item.artifact_dir = f"application-packets/{item_id}"
            db.commit()
            return {"status": "ready"}
        finally:
            db.close()

    monkeypatch.setattr("backend.automation.speedyapply_pipeline._export_packet", fake_export)

    resume_id = await prepare_queue_item(item_id)
    test_db.expire_all()
    item = test_db.query(ApplicationQueueItem).filter(ApplicationQueueItem.id == uuid.UUID(item_id)).first()
    assert item.status == "ready"
    assert str(item.resume_id) == resume_id
    assert item.attempts == 1

    # A retry reuses the linked resume and does not create another version.
    assert await prepare_queue_item(item_id) == resume_id
    assert test_db.query(Resume).filter(Resume.is_base == False).count() == 1


@pytest.mark.asyncio
async def test_prepare_queue_item_records_retryable_description_failure(test_db, monkeypatch):
    job = _job(test_db, suffix="missing", description=None)
    base = _base_resume(test_db)
    test_db.add(Setting(key="speedyapply_resume_id", value=str(base.id)))
    test_db.commit()
    item_id = enqueue_candidates([{"job_id": str(job.id), "feed_id": "intern_usa"}])[0]

    async def no_description(url):
        return None

    monkeypatch.setattr("backend.automation.speedyapply_pipeline._fetch_description", no_description)
    with pytest.raises(RuntimeError, match="Could not retrieve"):
        await prepare_queue_item(item_id)

    test_db.expire_all()
    item = test_db.query(ApplicationQueueItem).filter(ApplicationQueueItem.id == uuid.UUID(item_id)).first()
    assert item.status == "failed"
    assert "retry" in item.error
    assert item.attempts == 1


@pytest.mark.asyncio
async def test_pipeline_enqueues_once_and_runs_workers(test_db, monkeypatch):
    job = _job(test_db, suffix="pipeline")
    _base_resume(test_db)
    test_db.add_all([
        Setting(key="speedyapply_auto_tailor", value="true"),
        Setting(key="speedyapply_max_jobs_per_run", value="25"),
    ])
    test_db.commit()

    async def fake_sync():
        return {
            "jobs_found": 1,
            "jobs_considered": 1,
            "new_jobs": 1,
            "reused_jobs": 0,
            "queue_candidates": [{"job_id": str(job.id), "feed_id": "new_grad_usa"}],
            "feed_errors": [],
        }

    prepared = []

    async def fake_prepare(item_id, trigger):
        prepared.append((item_id, trigger))
        return {"item_id": item_id, "status": "ready", "resume_id": "fake"}

    monkeypatch.setattr("backend.scraper.sources.speedyapply.sync_speedyapply_jobs", fake_sync)
    monkeypatch.setattr("backend.automation.speedyapply_pipeline._prepare_tracked", fake_prepare)

    first = await run_speedyapply_pipeline(trigger="scheduler")
    second = await run_speedyapply_pipeline(trigger="scheduler")

    assert first["queued"] == 1
    assert second["queued"] == 1
    assert len(prepared) == 2
    assert test_db.query(ApplicationQueueItem).count() == 1
