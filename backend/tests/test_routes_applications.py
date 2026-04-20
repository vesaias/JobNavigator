"""Tests for /api/applications endpoints + dedup + transition + company auto-create."""
import pytest


def _seed_first_run(test_db):
    """Seed an empty dashboard_api_key row so the auth middleware allows
    requests (first-run mode, matches seed.py default)."""
    from backend.models.db import Setting
    test_db.add(Setting(key="dashboard_api_key", value=""))
    test_db.commit()


@pytest.fixture(autouse=True)
def _stub_background_tasks(monkeypatch):
    """Stub slow / network-hitting background work so tests are fast + isolated."""
    # _cache_job_page — this is what the route actually schedules in background.
    # Make the coroutine a no-op so it doesn't fetch URLs or touch Playwright.
    async def _noop_cache(*a, **kw):
        return None
    monkeypatch.setattr(
        "backend.api.routes_applications._cache_job_page",
        _noop_cache,
        raising=False,
    )

    # fetch_h1b_for_company_id — scheduled when a new Company is auto-created.
    def _noop_h1b(*a, **kw):
        return None
    monkeypatch.setattr(
        "backend.analyzer.h1b_checker.fetch_h1b_for_company_id",
        _noop_h1b,
        raising=False,
    )


def test_create_application_returns_id(api_client, test_db):
    """POST /api/applications with valid body → 200 + id."""
    _seed_first_run(test_db)
    resp = api_client.post("/api/applications", json={
        "company": "Acme",
        "title": "Senior Product Manager",
        "url": "https://careers.acme.com/jobs/123",
    })
    assert resp.status_code in (200, 201), f"Unexpected status {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "id" in data
    assert data.get("status") == "applied"
    assert data.get("company") == "Acme"


def test_create_application_dedups_by_url(api_client, test_db):
    """Same URL with different UTM params → single Job row (external_id collision)."""
    _seed_first_run(test_db)
    api_client.post("/api/applications", json={
        "company": "Acme",
        "title": "Senior PM",
        "url": "https://careers.acme.com/jobs/123?utm_source=linkedin",
    })
    api_client.post("/api/applications", json={
        "company": "Acme",
        "title": "Senior PM",
        "url": "https://careers.acme.com/jobs/123?utm_campaign=x",
    })

    from backend.models.db import Job
    jobs = test_db.query(Job).filter(Job.company == "Acme").all()
    assert len(jobs) == 1, (
        f"Expected UTM-dedup to collapse both URLs into 1 job, got {len(jobs)}"
    )


def test_create_application_auto_creates_company(api_client, test_db):
    """POST with an unknown company name → Company row auto-created."""
    _seed_first_run(test_db)
    api_client.post("/api/applications", json={
        "company": "NewCoTestAbc",
        "title": "Senior PM",
        "url": "https://example.com/jobs/456",
    })

    from backend.models.db import Company
    co = test_db.query(Company).filter(Company.name == "NewCoTestAbc").first()
    assert co is not None, "Company should have been auto-created on apply"


def test_patch_application_status_records_transition(api_client, test_db):
    """PATCH status → Application.status_transitions has an entry with source='ui'."""
    _seed_first_run(test_db)
    created = api_client.post("/api/applications", json={
        "company": "Acme",
        "title": "Senior PM",
        "url": "https://x.com/1",
    }).json()
    aid = created["id"]

    resp = api_client.patch(f"/api/applications/{aid}", json={"status": "interview"})
    assert resp.status_code == 200

    from backend.models.db import Application
    app = test_db.query(Application).filter(Application.id == aid).first()
    assert app is not None
    assert app.status == "interview"
    assert any(
        t.get("to") == "interview" and t.get("source") == "ui"
        for t in (app.status_transitions or [])
    ), f"Expected ui-sourced transition to interview, got: {app.status_transitions}"


def test_list_applications_filters_by_status(api_client, test_db):
    """GET /api/applications?status=rejected returns only rejected apps."""
    _seed_first_run(test_db)
    api_client.post("/api/applications", json={
        "company": "Acme",
        "title": "PM1",
        "url": "https://x.com/1",
    })
    a2 = api_client.post("/api/applications", json={
        "company": "Acme",
        "title": "PM2",
        "url": "https://x.com/2",
    }).json()
    api_client.patch(f"/api/applications/{a2['id']}", json={"status": "rejected"})

    resp = api_client.get("/api/applications?status=rejected")
    assert resp.status_code == 200
    data = resp.json()
    # Response shape: {"total": N, "applications": [...]}
    apps = data.get("applications") if isinstance(data, dict) else data
    assert apps is not None, f"Unexpected response shape: {data}"
    titles = [a.get("title") for a in apps]
    assert "PM2" in titles, f"Expected PM2 in rejected list, got titles: {titles}"
    assert "PM1" not in titles, f"PM1 should not be in rejected list, got titles: {titles}"
