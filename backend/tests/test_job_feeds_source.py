import json
from datetime import datetime, timezone

import pytest

from backend.models.db import JobFeedCheckpoint, Setting
from backend.scraper.sources.job_feeds import (
    configured_feeds,
    parse_feed_document,
    poll_feed_documents,
)


NOW = datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)


SPEEDY = """
| Company | Position | Location | Salary | Posting | Age |
|---|---|---|---|---|---|
| <a href="https://acme.example"><strong>Acme</strong></a> | Software Engineer Intern | Remote - USA | $50/hr | <a href="https://jobs.example.com/acme/123?utm_source=x">Apply</a> | 0d |
"""


VANSH = """
| Company | Role | Location | Application/Link | Date Posted |
|---|---|---|---|---|
| **Acme** | ML Engineer Intern | San Francisco, CA | <a href="https://jobs.example.com/acme/ml">Apply</a> | Jul 18 |
| ↳ | Data Engineer Intern 🛂 | New York, NY | <a href="https://jobs.example.com/acme/data">Apply</a> | Jul 17 |
"""


SIMPLIFY_HTML = """
<table><thead><tr><th>Company</th><th>Role</th><th>Location</th><th>Application</th><th>Age</th></tr></thead>
<tbody>
<tr><td>Globex</td><td>Software Engineer Intern</td><td>Seattle, WA</td><td><a href="https://jobs.example.com/globex/1">Apply</a></td><td>1d</td></tr>
<tr><td>↳</td><td>AI Engineer Intern 🇺🇸</td><td>Boston, MA</td><td><a href="https://jobs.example.com/globex/2">Apply</a></td><td>2d</td></tr>
</tbody></table>
"""


def test_parse_speedy_and_vansh_headers_to_one_shape():
    speedy = parse_feed_document(SPEEDY, "speedyapply_intern_usa", now=NOW)
    vansh = parse_feed_document(VANSH, "vansh_summer_2027", now=NOW)

    assert speedy[0].company == "Acme"
    assert speedy[0].age_days == 0
    assert speedy[0].salary_min_hint == 104000
    assert vansh[0].posted_at.date().isoformat() == "2026-07-18"
    assert vansh[1].company == "Acme"
    assert vansh[1].flags["no_sponsorship"] is True


def test_parse_html_table_and_inherited_company():
    rows = parse_feed_document(SIMPLIFY_HTML, "vansh_summer_2027", now=NOW)
    assert [row.company for row in rows] == ["Globex", "Globex"]
    assert rows[1].flags["citizenship_required"] is True


def test_date_without_year_uses_most_recent_non_future_year():
    january = NOW.replace(month=1, day=2)
    document = VANSH.replace("Jul 18", "Dec 31").replace("Jul 17", "Jan 01")
    rows = parse_feed_document(document, "vansh_summer_2027", now=january)
    assert rows[0].posted_at.year == 2025
    assert rows[1].posted_at.year == 2026


def test_configured_feeds_rejects_unknown_and_preserves_order():
    raw = json.dumps(["vansh_summer_2027", "bad", "speedyapply_intern_usa", "vansh_summer_2027"])
    assert configured_feeds(raw) == ["vansh_summer_2027", "speedyapply_intern_usa"]


@pytest.mark.asyncio
async def test_unchanged_checkpoint_does_not_download_raw_document(test_db, monkeypatch):
    test_db.add(Setting(key="job_feeds_sources", value=json.dumps(["speedyapply_intern_usa"])))
    test_db.add(JobFeedCheckpoint(
        repository_id="speedyapply_2027",
        last_commit_sha="a" * 40,
        last_success_at=NOW,
    ))
    test_db.commit()

    async def fake_head(repository):
        return "a" * 40, NOW

    async def fail_raw(*args, **kwargs):
        raise AssertionError("raw document must not be fetched for an unchanged commit")

    monkeypatch.setattr("backend.scraper.sources.job_feeds._fetch_repository_head", fake_head)
    monkeypatch.setattr("backend.scraper.sources.job_feeds._fetch_text", fail_raw)

    result = await poll_feed_documents()
    assert result.rows == []
    assert result.unchanged_repositories == ["speedyapply_2027"]
