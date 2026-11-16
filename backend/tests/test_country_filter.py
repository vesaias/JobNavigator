"""Allowed job countries: a new job placed only outside the list is stored as ignored."""
import json
import uuid

from backend.accounts.settings import put_setting
from backend.models.db import Job, JobLocation
from backend.scraper._shared.country_filter import allowed_countries, outside_allowed


def _job(db, places=(), status="new", loc_country=None):
    job = Job(id=uuid.uuid4(), external_id=uuid.uuid4().hex, company="Acme", title="Product Manager",
              url="https://acme.test/%s" % uuid.uuid4().hex, status=status, loc_country=loc_country)
    for index, country in enumerate(places):
        job.locations.append(JobLocation(country=country, is_primary=index == 0))
    db.add(job)
    db.commit()
    return job


def _allow(db, codes):
    put_setting(db, "job_countries_allowed", json.dumps(codes))
    db.commit()


def test_a_job_only_in_other_countries_is_stored_as_ignored(test_db):
    _allow(test_db, ["US", "GB", "DE", "CH"])
    assert _job(test_db, ["SG"]).status == "ignored"
    assert _job(test_db, ["KR", "JP"]).status == "ignored"


def test_a_job_with_one_allowed_country_stays_new(test_db):
    _allow(test_db, ["US", "GB", "DE", "CH"])
    assert _job(test_db, ["US"]).status == "new"
    assert _job(test_db, ["NL", "DE"]).status == "new"


def test_a_job_with_no_known_country_always_passes(test_db):
    _allow(test_db, ["US"])
    assert _job(test_db, []).status == "new"


def test_an_empty_list_keeps_every_job(test_db):
    _allow(test_db, [])
    assert _job(test_db, ["SG"]).status == "new"


def test_uk_is_read_as_gb_and_codes_are_case_insensitive(test_db):
    _allow(test_db, ["uk", " us "])
    assert allowed_countries(test_db) == {"GB", "US"}
    assert _job(test_db, ["GB"]).status == "new"


def test_only_new_jobs_are_touched(test_db):
    _allow(test_db, ["US"])
    assert _job(test_db, ["SG"], status="saved").status == "saved"


def test_the_primary_country_column_counts_when_there_are_no_location_rows(test_db):
    _allow(test_db, ["US"])
    job = Job(title="PM", loc_country="SG")
    assert outside_allowed(job, {"US"}) is True
    assert outside_allowed(Job(title="PM"), {"US"}) is False
