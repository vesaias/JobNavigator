"""A company pass fills location/arrangement on rows the feed already holds; set values are never overwritten."""
import uuid

from backend.models.db import Job
from backend.scraper.sources.company_pages import _refresh_known_jobs


def _job(db, ext, **kw):
    j = Job(id=uuid.uuid4(), external_id=ext, content_hash=ext, company="Acme", title="PM",
            url=f"https://acme.test/{ext}", status="ignored", **kw)
    db.add(j)
    db.commit()
    return j


def test_refresh_fills_empty_rows_from_the_scraped_dict(test_db):
    j = _job(test_db, "e1")
    n = _refresh_known_jobs(test_db, {"e1": {"location": "Toronto, ON", "arrangement": "Hybrid",
                                             "locations": ["Toronto, ON", "Vancouver, BC"]}})
    test_db.commit(); test_db.refresh(j)
    assert n == 1
    assert j.location == "Toronto, ON"
    assert (j.loc_country, j.loc_region, j.loc_city) == ("CA", "ON", "toronto")
    assert sorted((r.region, r.city) for r in j.locations) == [("BC", "vancouver"), ("ON", "toronto")]
    assert (j.arr_remote, j.arr_hybrid, j.arr_onsite) == (False, True, False)


def test_refresh_leaves_resolved_rows_alone(test_db):
    j = _job(test_db, "e2", location="Berlin, Germany", loc_country="DE", loc_city="berlin",
             arr_remote=True, arr_hybrid=False, arr_onsite=False)
    n = _refresh_known_jobs(test_db, {"e2": {"location": "Paris, France", "arrangement": "OnSite"}})
    test_db.commit(); test_db.refresh(j)
    assert n == 0
    assert (j.location, j.loc_country, j.loc_city, j.arr_remote) == ("Berlin, Germany", "DE", "berlin", True)


def test_refresh_without_signal_writes_nothing(test_db):
    j = _job(test_db, "e3")
    n = _refresh_known_jobs(test_db, {"e3": {"title": "PM"}})
    test_db.commit(); test_db.refresh(j)
    assert n == 0 and j.location is None and j.loc_country is None and j.arr_remote is None


def test_refresh_only_touches_the_ids_it_is_given(test_db):
    other = _job(test_db, "e4")
    _job(test_db, "e5")
    _refresh_known_jobs(test_db, {"e5": {"location": "Austin, TX"}})
    test_db.commit(); test_db.refresh(other)
    assert other.loc_country is None
