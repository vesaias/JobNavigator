from backend.models.db import ApplicationQueueItem, Job, Resume, Setting


def _ready_item(test_db):
    job = Job(
        external_id="ready-job",
        content_hash="ready-content",
        company="Acme",
        title="New Grad Software Engineer",
        location="Shanghai, China",
        url="https://jobs.example.com/apply/123",
        source="speedyapply_new_grad_intl",
        description="Build reliable Python services.",
    )
    resume = Resume(name="Acme tailored", is_base=False, json_data={"summary": "Tailored"})
    test_db.add_all([job, resume])
    test_db.flush()
    item = ApplicationQueueItem(
        job_id=job.id,
        resume_id=resume.id,
        source_feed="new_grad_intl",
        application_url="https://jobs.example.com/apply/123",
        status="ready",
        attempts=1,
    )
    test_db.add(item)
    test_db.commit()
    return item, job, resume


def test_ready_queue_returns_form_and_resume_paths_then_acknowledges(api_client, test_db):
    test_db.add(Setting(key="dashboard_api_key", value=""))
    item, job, resume = _ready_item(test_db)

    response = api_client.get("/api/apply-queue/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    ready = data["items"][0]
    assert ready["application_url"] == "https://jobs.example.com/apply/123"
    assert ready["resume_pdf_url"] == f"/api/resumes/{resume.id}/pdf"
    assert ready["resume_editor_url"] == f"/resumes?resume={resume.id}"

    ack = api_client.post(f"/api/apply-queue/{item.id}/acknowledge")
    assert ack.status_code == 200
    assert api_client.get("/api/apply-queue/ready").json()["total"] == 0
    assert api_client.get("/api/apply-queue/ready?unseen_only=false").json()["total"] == 1


def test_manual_run_returns_background_run_id(api_client, test_db, monkeypatch):
    test_db.add(Setting(key="dashboard_api_key", value=""))
    test_db.commit()
    monkeypatch.setattr(
        "backend.api.routes_apply_queue.launch_background",
        lambda *args, **kwargs: "run-123",
    )

    response = api_client.post("/api/apply-queue/run")
    assert response.status_code == 202
    assert response.json() == {"run_id": "run-123", "status": "running"}
