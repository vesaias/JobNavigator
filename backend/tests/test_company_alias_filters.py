"""Company aliases collapse in filter list + expand in filter application (#aliases)."""
from backend.models.db import Company, Job, Setting


def _seed_first_run(test_db):
    test_db.add(Setting(key="dashboard_api_key", value=""))
    test_db.commit()


def _seed_amazon_with_aliases(test_db):
    co = Company(
        name="Amazon",
        tier=1,
        scrape_urls=[],
        aliases=["AWS", "Audible", "Prime Video & Amazon MGM Studios"],
        active=True,
        playwright_enabled=True,
    )
    test_db.add(co)
    test_db.commit()
    return co


def test_companies_list_collapses_aliases(api_client, test_db):
    """Three jobs under three Amazon aliases -> /api/jobs/companies/list returns just 'Amazon'."""
    _seed_first_run(test_db)
    _seed_amazon_with_aliases(test_db)
    test_db.add_all([
        Job(external_id="a1", content_hash="ah1", company="Amazon", title="PM", status="new"),
        Job(external_id="a2", content_hash="ah2", company="Audible", title="PM", status="new"),
        Job(external_id="a3", content_hash="ah3", company="Prime Video & Amazon MGM Studios", title="PM", status="new"),
    ])
    test_db.commit()

    resp = api_client.get("/api/jobs/companies/list")
    assert resp.status_code == 200
    assert resp.json() == ["Amazon"]


def test_companies_list_passes_orphans_through(api_client, test_db):
    """A job with a company that has no Company record stays as its raw name."""
    _seed_first_run(test_db)
    _seed_amazon_with_aliases(test_db)
    test_db.add_all([
        Job(external_id="o1", content_hash="oh1", company="Amazon", title="PM", status="new"),
        Job(external_id="o2", content_hash="oh2", company="UnknownCo Inc.", title="PM", status="new"),
    ])
    test_db.commit()

    resp = api_client.get("/api/jobs/companies/list")
    assert sorted(resp.json()) == ["Amazon", "UnknownCo Inc."]


def test_jobs_filter_expands_aliases(api_client, test_db):
    """company=Amazon should match jobs whose raw Job.company is 'Audible' or 'AWS'."""
    _seed_first_run(test_db)
    _seed_amazon_with_aliases(test_db)
    test_db.add_all([
        Job(external_id="f1", content_hash="fh1", company="Amazon", title="PM", status="new"),
        Job(external_id="f2", content_hash="fh2", company="Audible", title="PM", status="new"),
        Job(external_id="f3", content_hash="fh3", company="AWS", title="PM", status="new"),
        Job(external_id="f4", content_hash="fh4", company="Google", title="PM", status="new"),
    ])
    test_db.commit()

    resp = api_client.get("/api/jobs?company=Amazon")
    assert resp.status_code == 200
    titles_by_company = sorted({r["company"] for r in resp.json()["jobs"]})
    assert titles_by_company == ["AWS", "Amazon", "Audible"]
