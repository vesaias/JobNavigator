from backend.models.db import ApplicationQueueItem, Job, JobFeedCheckpoint, Setting


def test_job_feed_status_reports_settings_queue_and_source_health(api_client, test_db):
    job = Job(
        external_id="feed-status-job",
        content_hash="feed-status-content",
        company="Acme",
        title="Software Engineer Intern",
        url="https://example.com/jobs/1",
        source="vansh_summer_2027",
    )
    test_db.add(job)
    test_db.flush()
    test_db.add_all([
        Setting(key="dashboard_api_key", value=""),
        Setting(key="job_feeds_enabled", value="true"),
        Setting(key="job_feeds_interval_minutes", value="5"),
        ApplicationQueueItem(job_id=job.id, status="pending_tailor"),
        JobFeedCheckpoint(
            repository_id="vanshb03/Summer2027-Internships",
            last_commit_sha="abc123",
            consecutive_errors=0,
        ),
    ])
    test_db.commit()

    response = api_client.get("/api/job-feeds/status")

    assert response.status_code == 200
    data = response.json()
    assert data["settings"]["job_feeds_enabled"] == "true"
    assert data["queue"] == {"pending_tailor": 1}
    assert data["sources"][0]["repository_id"] == "vanshb03/Summer2027-Internships"
    assert data["sources"][0]["last_commit_sha"] == "abc123"


def test_job_feed_manual_run_is_forced(api_client, test_db, monkeypatch):
    test_db.add(Setting(key="dashboard_api_key", value=""))
    test_db.commit()
    captured = {}

    def fake_launch(*args, **kwargs):
        captured.update(kwargs)
        return "feed-run-123"

    monkeypatch.setattr("backend.api.routes_job_feeds.launch_background", fake_launch)

    response = api_client.post("/api/job-feeds/run")

    assert response.status_code == 202
    assert response.json() == {"run_id": "feed-run-123", "status": "running"}
    assert captured["func_kwargs"] == {"trigger": "manual", "force": True}
