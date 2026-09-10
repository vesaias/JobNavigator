"""Tests for the territorial filter and its facet.

The rule under test is the one the menu depends on: a facet count must equal
what clicking that entry returns. A menu that says 5 and then shows 51 is worse
than no menu.
"""
import pytest

from backend.api.routes_jobs import _location_clause
from backend.models.db import Job


def _make(db, index, **kw):
    """`make_external_id` hashes the URL alone, so each row needs its own."""
    from backend.scraper._shared.dedup import make_external_id
    url = "https://example.com/job/%d" % index
    job = Job(external_id=make_external_id("Acme", "Engineer %d" % index, url),
              company="Acme", title="Engineer %d" % index, url=url,
              status="new", **kw)
    db.add(job)
    return job


@pytest.fixture
def placed(test_db):
    """One row per shape the parser can produce, including the unresolved ones."""
    rows = [
        dict(loc_country="CA", loc_region="BC", loc_city="vancouver"),
        dict(loc_country="CA", loc_region="BC", loc_city="vancouver"),
        dict(loc_country="CA", loc_region="BC", loc_city="burnaby"),
        dict(loc_country="CA", loc_region="ON", loc_city="toronto"),
        dict(loc_country="CA", loc_region="AB", loc_city="calgary"),
        dict(loc_country="CA", loc_region="BC", loc_city=None),   # region only
        dict(loc_country="CA", loc_region=None, loc_city="vancouver"),  # no region
        dict(loc_country="CA", loc_region=None, loc_city=None),   # country only
        dict(loc_country="US", loc_region="CA", loc_city="san francisco"),
        dict(loc_country=None, loc_region=None, loc_city=None),   # never resolved
    ]
    for index, row in enumerate(rows):
        _make(test_db, index, **row)
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
