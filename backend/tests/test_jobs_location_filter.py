"""Tests for the territorial filter and its facet.

The rule under test is the one the menu depends on: a facet count must equal
what clicking that entry returns. A menu that says 5 and then shows 51 is worse
than no menu.
"""
import pytest

from backend.api.routes_jobs import _location_clause
from backend.models.db import Job


def _make(db, index, places):
    """`make_external_id` hashes the URL alone, so each row needs its own.

    `places` is every place the posting names; the first is the primary one and
    is also denormalised onto the row.
    """
    from backend.scraper._shared.dedup import make_external_id
    from backend.models.db import JobLocation

    url = "https://example.com/job/%d" % index
    job = Job(external_id=make_external_id("Acme", "Engineer %d" % index, url),
              company="Acme", title="Engineer %d" % index, url=url, status="new")
    if places:
        job.loc_country, job.loc_region, job.loc_city = places[0]
    db.add(job)
    for order, (country, region, city) in enumerate(places):
        job.locations.append(JobLocation(country=country, region=region, city=city,
                                         is_primary=order == 0))
    return job


@pytest.fixture(autouse=True)
def _first_run(test_db, request):
    """Put the app in first-run mode, so the auth middleware lets the facet
    requests through instead of answering 401 (which reads here as a facet with
    no places). The app has to be up first: its lifespan writes the environment
    key into an empty `dashboard_api_key`, so seeding before startup is undone."""
    if "api_client" in request.fixturenames:
        request.getfixturevalue("api_client")
    from backend.models.db import Setting
    row = test_db.query(Setting).filter(Setting.key == "dashboard_api_key").first()
    if row is None:
        test_db.add(Setting(key="dashboard_api_key", value=""))
    else:
        row.value = ""
    test_db.commit()


@pytest.fixture
def placed(test_db):
    """One row per shape the parser can produce, including the unresolved ones."""
    rows = [
        [("CA", "BC", "vancouver")],
        [("CA", "BC", "vancouver")],
        [("CA", "BC", "burnaby")],
        [("CA", "ON", "toronto")],
        [("CA", "AB", "calgary")],
        [("CA", "BC", None)],            # region only
        [("CA", None, "vancouver")],     # no region
        [("CA", None, None)],            # country only
        [("US", "CA", "san francisco")],
        [],                              # never resolved
    ]
    for index, places in enumerate(rows):
        _make(test_db, index, places)
    test_db.commit()
    return test_db


@pytest.fixture
def multi(test_db):
    """One posting open in three places, the way Lever and Ashby report them."""
    _make(test_db, 100, [("US", "NY", "new york"),
                         ("US", "CA", "los angeles"),
                         ("CA", "BC", "vancouver")])
    test_db.commit()
    return test_db


def _count(db, key):
    clause = _location_clause(key)
    q = db.query(Job)
    return q.filter(clause).count() if clause is not None else q.count()


# ── the hierarchy ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("key,expected", [
    ("CA", 8),                    # every Canadian row, whatever else is known
    ("CA:BC", 4),                 # BC rows only: 2 vancouver + burnaby + region-only
    ("CA:ON", 1),
    ("CA:AB", 1),
    ("US", 1),
    ("US:CA", 1),
    ("US:CA:san francisco", 1),
])
def test_a_key_keeps_everything_under_it(placed, key, expected):
    assert _count(placed, key) == expected


def test_city_key_includes_region_less_rows(placed):
    # 2 rows are BC+vancouver, 1 more is vancouver with no region.
    assert _count(placed, "CA:BC:vancouver") == 3


def test_a_region_key_does_not_absorb_the_unknowns(placed):
    """A row whose region was never resolved must not be counted in every
    province: that reported 51 jobs in Alberta when 5 were known to be there."""
    assert _count(placed, "CA:AB") == 1
    assert _count(placed, "CA:BC") == 4


def test_several_keys_are_an_or(placed):
    assert _count(placed, "CA:BC,CA:ON") == 5


def test_an_unresolved_row_answers_no_place(placed):
    """A job whose location never parsed is reachable only with no filter."""
    assert _count(placed, "CA") + _count(placed, "US") == 9
    assert placed.query(Job).count() == 10


def test_an_empty_filter_builds_no_clause():
    assert _location_clause("") is None
    assert _location_clause(None) is None
    assert _location_clause("  ,  ") is None


def test_a_country_only_key_still_matches_a_full_row(placed):
    assert _count(placed, "CA") >= _count(placed, "CA:BC:vancouver")


# ── the facet must agree with the filter ─────────────────────────────────────

def test_every_facet_count_equals_its_filter_count(placed, api_client):
    """The contract the menu rests on."""
    resp = api_client.get("/api/jobs/facets?status=new")
    assert resp.status_code == 200
    entries = resp.json()["locations"]
    assert entries, "no places in the facet"

    for entry in entries:
        listed = api_client.get(
            "/api/jobs?status=new&limit=1&brief=1&location=%s" % entry["key"])
        assert listed.status_code == 200
        assert listed.json()["total"] == entry["count"], (
            "facet says %d for %r but the filter returns %d"
            % (entry["count"], entry["key"], listed.json()["total"]))


def test_the_facet_indents_by_level(placed, api_client):
    entries = api_client.get("/api/jobs/facets?status=new").json()["locations"]
    by_key = {e["key"]: e for e in entries}
    assert by_key["CA"]["level"] == 0
    assert by_key["CA:BC"]["level"] == 1
    assert by_key["CA:BC:vancouver"]["level"] == 2


def test_the_facet_drops_a_duplicate_region_less_city(placed, api_client):
    """Vancouver appears with and without a region, but one entry covers both."""
    keys = [e["key"] for e in
            api_client.get("/api/jobs/facets?status=new").json()["locations"]]
    assert "CA:BC:vancouver" in keys
    assert "CA::vancouver" not in keys


def test_the_facet_labels_a_place_coarsest_last(placed, api_client):
    entries = {e["key"]: e["name"] for e in
               api_client.get("/api/jobs/facets?status=new").json()["locations"]}
    assert entries["CA:BC:vancouver"] == "Vancouver, BC, Canada"
    assert entries["CA:BC"] == "BC, Canada"
    assert entries["CA"] == "Canada"


# ── one posting, several places ──────────────────────────────────────────────

@pytest.mark.parametrize("key", [
    "US:NY:new york", "US:CA:los angeles", "CA:BC:vancouver", "US", "CA",
])
def test_a_posting_answers_every_place_it_names(multi, key):
    """A job open in three cities has to be findable under all three."""
    assert _count(multi, key) == 1


def test_a_posting_is_returned_once_however_many_places_match(multi):
    """The filter is an EXISTS, not a join: three matching places, one row."""
    assert _count(multi, "US:NY:new york,US:CA:los angeles,CA:BC:vancouver") == 1


def test_the_primary_place_is_denormalised_onto_the_row(multi):
    job = multi.query(Job).filter(Job.title == "Engineer 100").one()
    assert (job.loc_country, job.loc_region, job.loc_city) == ("US", "NY", "new york")
    assert len(job.locations) == 3
    assert sum(1 for row in job.locations if row.is_primary) == 1


def test_deleting_the_job_removes_its_places(multi):
    job = multi.query(Job).filter(Job.title == "Engineer 100").one()
    from backend.models.db import JobLocation
    multi.delete(job)
    multi.commit()
    assert multi.query(JobLocation).count() == 0


# ── the work-arrangement filter ──────────────────────────────────────────────

@pytest.fixture
def arranged(test_db):
    """Every combination the flags can take, including the two-way posting."""
    from backend.scraper._shared.dedup import make_external_id
    rows = [
        ("remote-only", True, False, False),
        ("hybrid-only", False, True, False),
        ("onsite-only", False, False, True),
        ("remote-and-hybrid", True, True, False),
        ("unknown", None, None, None),
    ]
    for index, (name, remote, hybrid, onsite) in enumerate(rows):
        url = "https://example.com/arr/%d" % index
        test_db.add(Job(external_id=make_external_id("Acme", name, url),
                        company="Acme", title=name, url=url, status="new",
                        arr_remote=remote, arr_hybrid=hybrid, arr_onsite=onsite))
    test_db.commit()
    return test_db


def _arr_count(db, value):
    from backend.api.routes_jobs import _arrangement_clause
    clause = _arrangement_clause(value)
    q = db.query(Job)
    return q.filter(clause).count() if clause is not None else q.count()


@pytest.mark.parametrize("value,expected", [
    ("remote", 2),    # remote-only and the two-way posting
    ("hybrid", 2),    # hybrid-only and the two-way posting
    ("onsite", 1),
    ("unknown", 1),
])
def test_a_posting_answers_every_arrangement_it_offers(arranged, value, expected):
    assert _arr_count(arranged, value) == expected


def test_unknown_is_not_swept_in_with_the_others(arranged):
    """Three flags picked still leave the unresolved posting out."""
    assert _arr_count(arranged, "remote,hybrid,onsite") == 4
    assert _arr_count(arranged, "unknown") == 1


def test_several_arrangements_are_an_or_without_double_counting(arranged):
    """The two-way posting matches both terms and is returned once."""
    assert _arr_count(arranged, "remote,hybrid") == 3


def test_an_empty_arrangement_filter_builds_no_clause():
    from backend.api.routes_jobs import _arrangement_clause
    assert _arrangement_clause("") is None
    assert _arrangement_clause(None) is None
    assert _arrangement_clause("nonsense") is None


def test_every_arrangement_facet_count_equals_its_filter_count(arranged, api_client):
    resp = api_client.get("/api/jobs/facets?status=new")
    entries = resp.json()["arrangements"]
    assert {e["name"] for e in entries} == {"remote", "hybrid", "onsite", "unknown"}
    for entry in entries:
        listed = api_client.get(
            "/api/jobs?status=new&limit=1&brief=1&arrangement=%s" % entry["name"])
        assert listed.json()["total"] == entry["count"], entry["name"]


# ── a hand-added job is searchable too ───────────────────────────────────────

def test_a_manual_job_answers_the_work_filter(test_db, api_client):
    """POST /jobs/manual runs the same analyzers every scraper path runs."""
    resp = api_client.post("/api/jobs/manual", json={
        "title": "Staff Engineer (Remote)",
        "company": "Acme",
        "url": "https://example.com/manual/1",
        "status": "new",
    })
    assert resp.status_code == 200, resp.text
    job = test_db.query(Job).filter(Job.id == resp.json()["id"]).one()
    assert (job.arr_remote, job.arr_hybrid, job.arr_onsite) == (True, False, False)


def test_a_manual_job_answers_the_location_filter(test_db, api_client):
    """A typed-in location has to reach the territorial filter."""
    resp = api_client.post("/api/jobs/manual", json={
        "title": "Staff Engineer",
        "company": "Acme",
        "url": "https://example.com/manual/2",
        "location": "Toronto, Ontario, Canada",
        "status": "new",
    })
    assert resp.status_code == 200, resp.text
    job = test_db.query(Job).filter(Job.id == resp.json()["id"]).one()
    assert (job.loc_country, job.loc_region, job.loc_city) == ("CA", "ON", "toronto")
    assert [(r.country, r.region, r.city) for r in job.locations] == [("CA", "ON", "toronto")]
    assert _count(test_db, "CA:ON:toronto") == 1


def test_a_manual_job_without_a_location_stays_unplaced(test_db, api_client):
    """Nothing to parse means nothing written, not a wrong guess."""
    resp = api_client.post("/api/jobs/manual", json={
        "title": "Staff Engineer",
        "company": "Acme",
        "url": "https://example.com/manual/3",
        "status": "new",
    })
    job = test_db.query(Job).filter(Job.id == resp.json()["id"]).one()
    assert job.loc_country is None
    assert list(job.locations) == []


# ── a hand-logged application is searchable too ──────────────────────────────

def test_a_logged_application_answers_both_filters(test_db, api_client):
    """POST /applications creates the job row itself, so it has to run the same
    analyzers every other writer runs."""
    resp = api_client.post("/api/applications", json={
        "title": "Staff Engineer (Remote)",
        "company": "Acme",
        "url": "https://example.com/logged/1",
        "location": "Toronto, Ontario, Canada",
    })
    assert resp.status_code in (200, 201), resp.text

    job = test_db.query(Job).filter(Job.url == "https://example.com/logged/1").one()
    assert (job.arr_remote, job.arr_hybrid, job.arr_onsite) == (True, False, False)
    assert (job.loc_country, job.loc_region, job.loc_city) == ("CA", "ON", "toronto")
    assert _count(test_db, "CA:ON:toronto") == 1


def test_a_logged_application_without_a_location_stays_unplaced(test_db, api_client):
    resp = api_client.post("/api/applications", json={
        "title": "Staff Engineer",
        "company": "Acme",
        "url": "https://example.com/logged/2",
    })
    assert resp.status_code in (200, 201), resp.text
    job = test_db.query(Job).filter(Job.url == "https://example.com/logged/2").one()
    assert job.loc_country is None
    assert list(job.locations) == []
