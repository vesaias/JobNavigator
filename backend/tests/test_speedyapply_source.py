import json

import pytest

from backend.models.db import ApplicationQueueItem, Job, Setting
from backend.scraper._shared.dedup import make_external_id
from backend.scraper.sources.speedyapply import (
    configured_feeds,
    parse_markdown_jobs,
    _select_unqueued_candidates,
    sync_speedyapply_jobs,
)


USA_MARKDOWN = """
### Other
| Company | Position | Location | Salary | Posting | Age |
|---|---|---|---|---|---|
| <a href="https://acme.example"><strong>Acme</strong></a> | Software Engineer Intern | Remote - USA | $50/hr | <a href="https://jobs.example.com/acme/123"><img alt="Apply"/></a> | 0d |
| <a href="https://old.example"><strong>Old Co</strong></a> | Old Internship | Boston, MA | $100k/yr | <a href="https://jobs.example.com/old/1"><img alt="Apply"/></a> | 9d |
"""

INTL_MARKDOWN = """
### FAANG+
| Company | Position | Location | Posting | Age |
|---|---|---|---|---|
| <a href="https://globex.example"><strong>Globex</strong></a> | Graduate Software Engineer | Shanghai, China | <a href="https://jobs.example.com/globex/456"><img alt="Apply"/></a> | 1d |
| Broken | Missing URL | Anywhere | Apply | 0d |
"""


def test_parse_markdown_jobs_handles_salary_and_non_salary_tables():
    usa = parse_markdown_jobs(USA_MARKDOWN, "intern_usa")
    intl = parse_markdown_jobs(INTL_MARKDOWN, "new_grad_intl")

    assert usa[0]["company"] == "Acme"
    assert usa[0]["salary_min_hint"] == 104000
    assert usa[0]["salary_max_hint"] == 104000
    assert usa[0]["url"] == "https://jobs.example.com/acme/123"
    assert intl == [{
        "company": "Globex",
        "title": "Graduate Software Engineer",
        "location": "Shanghai, China",
        "url": "https://jobs.example.com/globex/456",
        "age_days": 1,
        "salary_min_hint": None,
        "salary_max_hint": None,
        "feed_id": "new_grad_intl",
    }]


def test_configured_feeds_validates_and_preserves_order():
    assert configured_feeds(json.dumps(["new_grad_usa", "bad", "intern_usa", "new_grad_usa"])) == [
        "new_grad_usa",
        "intern_usa",
    ]


def test_run_cap_skips_jobs_that_already_have_queue_items(test_db):
    queued_job = Job(
        external_id="already-queued",
        content_hash="already-queued-content",
        company="Acme",
        title="First",
        url="https://jobs.example.com/first",
    )
    test_db.add(queued_job)
    test_db.flush()
    test_db.add(ApplicationQueueItem(job_id=queued_job.id, status="pending_tailor"))
    test_db.commit()

    candidates = [
        {"external_id": "already-queued", "company": "Acme", "title": "First"},
        {"external_id": "not-queued", "company": "Globex", "title": "Second"},
    ]
    selected = _select_unqueued_candidates(test_db, candidates, max_jobs=1)
    assert [item["external_id"] for item in selected] == ["not-queued"]


@pytest.mark.asyncio
async def test_sync_imports_recent_jobs_reuses_existing_and_fetches_description(test_db, monkeypatch):
    test_db.add_all([
        Setting(key="speedyapply_feeds", value=json.dumps(["intern_usa", "new_grad_intl"])),
        Setting(key="speedyapply_max_age_days", value="1"),
        Setting(key="speedyapply_max_jobs_per_run", value="25"),
    ])
    existing = Job(
        external_id=make_external_id("Globex", "Graduate Software Engineer", "https://jobs.example.com/globex/456"),
        content_hash="existing-content",
        company="Globex",
        title="Graduate Software Engineer",
        url="https://jobs.example.com/globex/456",
        source="extension",
    )
    test_db.add(existing)
    test_db.commit()

    async def fake_feed(feed_id):
        return USA_MARKDOWN if feed_id == "intern_usa" else INTL_MARKDOWN

    async def fake_descriptions(rows, max_concurrent=5):
        return [(row, f"Full job description for {row['company']} with Python and APIs") for row in rows]

    monkeypatch.setattr("backend.scraper.sources.speedyapply._fetch_feed", fake_feed)
    monkeypatch.setattr("backend.scraper.sources.speedyapply._fetch_descriptions", fake_descriptions)

    result = await sync_speedyapply_jobs()

    assert result["jobs_found"] == 3
    assert result["jobs_considered"] == 2
    assert result["new_jobs"] == 1
    assert result["reused_jobs"] == 1
    assert len(result["queue_candidates"]) == 2

    jobs = test_db.query(Job).order_by(Job.company).all()
    assert [job.company for job in jobs] == ["Acme", "Globex"]
    assert jobs[0].description.startswith("Full job description")
    assert jobs[0].remote is True
    assert jobs[0].salary_min == 104000
    assert jobs[1].source == "extension"
    assert jobs[1].description.startswith("Full job description")
