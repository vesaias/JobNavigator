"""Tests for GET /api/jobs filter and sort combinations."""
import pytest


def _seed_first_run(db):
    from backend.models.db import Setting
    db.add(Setting(key="dashboard_api_key", value=""))
    db.commit()


def _seed_jobs(db):
    """Add 3 jobs with varied attributes."""
    from backend.models.db import Job
    jobs = [
        Job(
            external_id="j1", content_hash="h1",
            company="Acme", title="Senior Product Manager",
            url="https://x.com/1", status="saved", source="jobspy_linkedin",
            best_cv_score=82.0, cv_scores={"Default": 82.0},
            salary_min=150000, salary_max=200000,
        ),
        Job(
            external_id="j2", content_hash="h2",
            company="Beta Corp", title="Staff Software Engineer",
            url="https://x.com/2", status="new", source="playwright_url",
            best_cv_score=65.0, cv_scores={"Default": 65.0},
            salary_min=180000, salary_max=240000,
        ),
        Job(
            external_id="j3", content_hash="h3",
            company="Acme", title="Junior PM Intern",
            url="https://x.com/3", status="skip", source="jobspy_indeed",
            best_cv_score=40.0, cv_scores={"Default": 40.0},
            salary_min=None, salary_max=None,
        ),
    ]
    for j in jobs:
        db.add(j)
    db.commit()
    return jobs


def test_list_jobs_filters_by_status(api_client, test_db):
    _seed_first_run(test_db)
    _seed_jobs(test_db)
    resp = api_client.get("/api/jobs?status=saved")
    assert resp.status_code == 200
    data = resp.json()
    titles = [j["title"] for j in data["jobs"]]
    assert "Senior Product Manager" in titles
    assert "Staff Software Engineer" not in titles


def test_list_jobs_filters_by_company_single(api_client, test_db):
    _seed_first_run(test_db)
    _seed_jobs(test_db)
    resp = api_client.get("/api/jobs?company=Acme")
    data = resp.json()
    companies = [j["company"] for j in data["jobs"]]
    assert all(c == "Acme" for c in companies)
    assert len(companies) == 2


def test_list_jobs_filters_by_min_score(api_client, test_db):
    """best_cv_score column makes this SQLite-portable."""
    _seed_first_run(test_db)
    _seed_jobs(test_db)
    resp = api_client.get("/api/jobs?min_score=70")
    data = resp.json()
    titles = [j["title"] for j in data["jobs"]]
    assert "Senior Product Manager" in titles  # score=82
    assert "Staff Software Engineer" not in titles  # score=65
    assert "Junior PM Intern" not in titles  # score=40


def test_list_jobs_filters_by_title_search(api_client, test_db):
    _seed_first_run(test_db)
    _seed_jobs(test_db)
    resp = api_client.get("/api/jobs?title_search=Senior")
    data = resp.json()
    titles = [j["title"] for j in data["jobs"]]
    assert "Senior Product Manager" in titles
    assert "Junior PM Intern" not in titles


def test_list_jobs_filters_by_source(api_client, test_db):
    _seed_first_run(test_db)
    _seed_jobs(test_db)
    resp = api_client.get("/api/jobs?source=jobspy_linkedin")
    data = resp.json()
    sources = [j["source"] for j in data["jobs"]]
    assert sources == ["jobspy_linkedin"]


def test_list_jobs_sort_by_score(api_client, test_db):
    """sort_by=score descends on best_cv_score with NULLs last.

    The response exposes `best_score` (derived from cv_scores JSON), not
    `best_cv_score` directly. Since we seed cv_scores to mirror best_cv_score,
    asserting order on best_score validates the ORDER BY.
    """
    _seed_first_run(test_db)
    _seed_jobs(test_db)
    resp = api_client.get("/api/jobs?sort_by=score")
    data = resp.json()
    jobs = data["jobs"]
    # Order should be: 82, 65, 40 (descending by score)
    scores = [j.get("best_score") for j in jobs if j.get("best_score")]
    assert len(scores) >= 2
    assert scores == sorted(scores, reverse=True), f"Expected desc sort, got: {scores}"
