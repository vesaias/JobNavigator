"""GET /api/jobs/facets — the feed's filter menus narrow each other.

Each dimension is counted over the jobs matching all the OTHER active filters but
not its own, so Status = New leaves only the companies/sources New jobs have, while
a selected company can still be swapped for another one.
"""
from urllib.parse import quote


def _seed_first_run(db):
    from backend.models.db import Setting
    db.add(Setting(key="dashboard_api_key", value=""))
    db.commit()


def _seed_jobs(db):
    """Acme has one new + one saved job, Beta one new, Gamma one skipped."""
    from backend.models.db import Job
    rows = [
        Job(external_id="f1", content_hash="fh1", company="Acme", title="Product Manager",
            url="https://x.com/1", status="new", source="jobspy_linkedin",
            h1b_verdict="likely", best_cv_score=82.0, cv_scores={"Default": 82.0}),
        Job(external_id="f2", content_hash="fh2", company="Acme", title="Staff Engineer",
            url="https://x.com/2", status="saved", source="jobspy_indeed",
            h1b_verdict="unlikely", best_cv_score=91.0, cv_scores={"Default": 91.0}),
        Job(external_id="f3", content_hash="fh3", company="Beta Corp", title="Data Analyst",
            url="https://x.com/3", status="new", source="playwright_url",
            h1b_verdict="possible", best_cv_score=65.0, cv_scores={"Default": 65.0}),
        Job(external_id="f4", content_hash="fh4", company="Gamma Inc", title="Intern",
            url="https://x.com/4", status="skip", source="jobspy_indeed",
            h1b_verdict="unknown", best_cv_score=40.0, cv_scores={"Default": 40.0}),
    ]
    for j in rows:
        db.add(j)
    db.commit()


def _by_name(rows):
    return {r["name"]: r["count"] for r in rows}


def test_facets_unfiltered_lists_every_dimension(api_client, test_db):
    _seed_first_run(test_db)
    _seed_jobs(test_db)
    data = api_client.get("/api/jobs/facets").json()
    assert _by_name(data["companies"]) == {"Acme": 2, "Beta Corp": 1, "Gamma Inc": 1}
    assert _by_name(data["sources"]) == {"jobspy_linkedin": 1, "jobspy_indeed": 2, "playwright_url": 1}
    assert _by_name(data["h1b_verdicts"]) == {"likely": 1, "possible": 1, "unlikely": 1, "unknown": 1}
    assert _by_name(data["statuses"]) == {"new": 2, "saved": 1, "skip": 1}
    # score bands lift the score filter and count what each preset would leave
    assert _by_name(data["score_bands"]) == {"70": 2, "80": 2, "90": 1}


def test_status_new_narrows_companies_and_sources(api_client, test_db):
    """The bug: with Status = New the Company/Source menus still listed everything."""
    _seed_first_run(test_db)
    _seed_jobs(test_db)
    data = api_client.get("/api/jobs/facets?status=new").json()
    assert _by_name(data["companies"]) == {"Acme": 1, "Beta Corp": 1}
    assert _by_name(data["sources"]) == {"jobspy_linkedin": 1, "playwright_url": 1}
    assert _by_name(data["h1b_verdicts"]) == {"likely": 1, "possible": 1}
    # ...but the Status menu itself is counted with the status filter lifted,
    # otherwise picking New would hide the other statuses you could switch to
    assert _by_name(data["statuses"]) == {"new": 2, "saved": 1, "skip": 1}


def test_default_open_set_semantics(api_client, test_db):
    """The feed's default view sends status=new,saved — facets must scope to it."""
    _seed_first_run(test_db)
    _seed_jobs(test_db)
    data = api_client.get("/api/jobs/facets?status=new,saved").json()
    assert _by_name(data["companies"]) == {"Acme": 2, "Beta Corp": 1}
    assert "Gamma Inc" not in _by_name(data["companies"])


def test_selected_company_still_lists_the_others(api_client, test_db):
    """A dimension never filters itself, so you can switch companies while one is picked."""
    _seed_first_run(test_db)
    _seed_jobs(test_db)
    data = api_client.get("/api/jobs/facets?company=Acme").json()
    companies = _by_name(data["companies"])
    assert companies == {"Acme": 2, "Beta Corp": 1, "Gamma Inc": 1}
    # the other menus DO honour the company pick
    assert _by_name(data["sources"]) == {"jobspy_linkedin": 1, "jobspy_indeed": 1}
    assert _by_name(data["statuses"]) == {"new": 1, "saved": 1}


def test_selected_source_still_lists_the_others(api_client, test_db):
    _seed_first_run(test_db)
    _seed_jobs(test_db)
    data = api_client.get("/api/jobs/facets?source=playwright_url").json()
    assert _by_name(data["sources"]) == {"jobspy_linkedin": 1, "jobspy_indeed": 2, "playwright_url": 1}
    assert _by_name(data["companies"]) == {"Beta Corp": 1}


def test_selected_value_that_no_longer_matches_stays_at_zero(api_client, test_db):
    """Gamma Inc has only a skipped job: under Status = New it stays listed, at 0."""
    _seed_first_run(test_db)
    _seed_jobs(test_db)
    data = api_client.get(f"/api/jobs/facets?status=new&company={quote('Gamma Inc')}").json()
    assert _by_name(data["companies"])["Gamma Inc"] == 0
    # and the same for a source and a verdict that fall out of range
    data = api_client.get("/api/jobs/facets?status=new&source=jobspy_indeed&h1b_verdict=unknown").json()
    assert _by_name(data["sources"])["jobspy_indeed"] == 0
    assert _by_name(data["h1b_verdicts"])["unknown"] == 0


def test_facet_counts_match_the_list_totals(api_client, test_db):
    """Every facet count is the `total` GET /jobs reports for that same filter set."""
    _seed_first_run(test_db)
    _seed_jobs(test_db)
    base = "status=new,saved"
    data = api_client.get(f"/api/jobs/facets?{base}").json()
    for dim, param in (("companies", "company"), ("sources", "source"),
                       ("h1b_verdicts", "h1b_verdict"), ("score_bands", "min_score")):
        for row in data[dim]:
            listed = api_client.get(f"/api/jobs?{base}&{param}={quote(row['name'])}&limit=0").json()
            assert listed["total"] == row["count"], (dim, row)


def test_facets_honour_title_search_and_salary(api_client, test_db):
    _seed_first_run(test_db)
    _seed_jobs(test_db)
    data = api_client.get("/api/jobs/facets?title_search=Engineer").json()
    assert _by_name(data["companies"]) == {"Acme": 1}
    assert _by_name(data["sources"]) == {"jobspy_indeed": 1}


def test_company_aliases_collapse_onto_the_parent(api_client, test_db):
    """A job filed under an alias counts towards the canonical company, as in /jobs/companies/list."""
    from backend.models.db import Company, Job
    _seed_first_run(test_db)
    _seed_jobs(test_db)
    test_db.add(Company(name="Acme", aliases=["Acme Labs"]))
    test_db.add(Job(external_id="f5", content_hash="fh5", company="Acme Labs", title="Researcher",
                    url="https://x.com/5", status="new", source="jobspy_linkedin"))
    test_db.commit()
    data = api_client.get("/api/jobs/facets?status=new").json()
    assert _by_name(data["companies"])["Acme"] == 2   # Product Manager + the alias row
    assert "Acme Labs" not in _by_name(data["companies"])
