import json
from datetime import datetime, timezone

import pytest

from backend.automation.speedyapply_pipeline import enqueue_candidates
from backend.models.db import (
    ApplicationQueueItem,
    Job,
    JobFeedPosting,
    Persona,
    Setting,
)
from backend.scraper.sources.job_feeds import (
    FeedJob,
    PollResult,
    evaluate_eligibility,
    sync_job_feeds,
)


NOW = datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)


def _row(source_id, repository_id, url, *, title="Software Engineer Intern", location="San Francisco, CA"):
    return FeedJob(
        source_id=source_id,
        repository_id=repository_id,
        job_type="intern",
        company="Acme",
        title=title,
        location=location,
        url=url,
        posted_at=NOW,
        age_days=0,
        flags={},
    )


def test_eligibility_filters_role_location_and_f1_blockers():
    allowed = {"swe", "ai", "data"}
    canada = _row(
        "vansh_summer_2027", "vansh_summer_2027",
        "https://jobs.example.com/1", location="Toronto, Canada",
    )
    assert not evaluate_eligibility(
        canada, allowed_families=allowed, has_advanced_degree=False
    ).eligible

    pm = _row(
        "vansh_summer_2027", "vansh_summer_2027",
        "https://jobs.example.com/2", title="Technical Program Manager Intern",
    )
    assert not evaluate_eligibility(pm, allowed_families=allowed, has_advanced_degree=False).eligible

    blocked = _row(
        "vansh_summer_2027", "vansh_summer_2027", "https://jobs.example.com/3",
    )
    result = evaluate_eligibility(
        blocked,
        allowed_families=allowed,
        has_advanced_degree=False,
        description="Applicants must be a U.S. citizen and hold a security clearance.",
    )
    assert not result.eligible
    assert any("citizenship" in blocker for blocker in result.blockers)


@pytest.mark.asyncio
async def test_cross_source_greenhouse_variants_create_one_job_and_queue(test_db, monkeypatch):
    test_db.add_all([
        Setting(key="job_feeds_backfill_days", value="7"),
        Setting(key="job_feeds_max_jobs_per_poll", value="25"),
        Setting(key="job_feeds_role_families", value=json.dumps(["swe", "ai", "data"])),
        Setting(key="job_feeds_resume_source", value="persona"),
        Persona(id=1, contact={"email": "candidate@example.com"}, resume_content={"summary": "Engineer"}),
    ])
    test_db.commit()

    rows = [
        _row(
            "speedyapply_intern_usa", "speedyapply_2027",
            "https://job-boards.greenhouse.io/acme/jobs/8489233002?utm_source=speedy",
        ),
        _row(
            "vansh_summer_2027", "vansh_summer_2027",
            "https://job-boards.greenhouse.io/embed/job_app?for=acme&token=8489233002&utm_source=vansh",
        ),
    ]

    async def fake_poll(force=False):
        return PollResult(rows=rows, changed_repositories=["speedyapply_2027", "vansh_summer_2027"])

    async def fake_descriptions(fetch_rows, max_concurrent=5):
        return [(row, "Build Python APIs for a distributed software platform.") for row in fetch_rows]

    monkeypatch.setattr("backend.scraper.sources.job_feeds.poll_feed_documents", fake_poll)
    monkeypatch.setattr("backend.scraper.sources.job_feeds._fetch_descriptions", fake_descriptions)

    sync = await sync_job_feeds()
    item_ids = enqueue_candidates(sync["queue_candidates"])

    assert sync["new_jobs"] == 1
    assert len(item_ids) == 1
    assert test_db.query(Job).count() == 1
    assert test_db.query(JobFeedPosting).count() == 2
    item = test_db.query(ApplicationQueueItem).one()
    assert item.status == "pending_tailor"
    assert item.priority == 100
    assert item.base_resume_key == "persona"


@pytest.mark.asyncio
async def test_jd_no_sponsorship_is_persisted_as_ineligible(test_db, monkeypatch):
    test_db.add_all([
        Setting(key="job_feeds_backfill_days", value="7"),
        Setting(key="job_feeds_max_jobs_per_poll", value="25"),
        Setting(key="job_feeds_role_families", value=json.dumps(["swe"])),
        Persona(id=1, resume_content={"summary": "Engineer"}),
    ])
    test_db.commit()
    row = _row(
        "speedyapply_intern_usa", "speedyapply_2027",
        "https://jobs.example.com/acme/blocked",
    )

    async def fake_poll(force=False):
        return PollResult(rows=[row], changed_repositories=["speedyapply_2027"])

    async def fake_descriptions(fetch_rows, max_concurrent=5):
        return [(fetch_row, "We will not provide employment visa sponsorship for this role.") for fetch_row in fetch_rows]

    monkeypatch.setattr("backend.scraper.sources.job_feeds.poll_feed_documents", fake_poll)
    monkeypatch.setattr("backend.scraper.sources.job_feeds._fetch_descriptions", fake_descriptions)

    sync = await sync_job_feeds()
    enqueue_candidates(sync["queue_candidates"])
    item = test_db.query(ApplicationQueueItem).one()
    assert item.status == "ineligible"
    assert any("sponsorship" in warning for warning in item.eligibility_warnings)
