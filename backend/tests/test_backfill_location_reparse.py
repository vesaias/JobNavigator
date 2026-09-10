"""`backfill_location --reparse` rewrites rows the parser now reads differently.

The plain backfill only fills empty columns, so a parser fix cannot reach a row
that was already parsed wrongly: 365 live rows written "IN, KA, Bengaluru" sat
under Indiana with a city called "ka, bengaluru". This is the flag that moves
them, and it is the one that deletes rows, so it is worth a test.
"""
import uuid

from backend.models.db import Job, JobLocation
from backend.scripts.backfill_location import run


def _job(db, location, country=None, region=None, city=None, places=()):
    job = Job(id=uuid.uuid4(), external_id=uuid.uuid4().hex, company="Acme",
              title="Engineer", url="https://acme.test/%s" % uuid.uuid4().hex,
              status="new", location=location,
              loc_country=country, loc_region=region, loc_city=city)
    db.add(job)
    for index, (pc, pr, pcity) in enumerate(places):
        job.locations.append(JobLocation(country=pc, region=pr, city=pcity,
                                         is_primary=index == 0))
    db.commit()
    return job


def test_a_dry_run_counts_the_rows_and_writes_nothing(test_db):
    job = _job(test_db, "IN, KA, Bengaluru", "US", "IN", "ka, bengaluru",
               [("US", "IN", "ka, bengaluru")])

    report = run(commit=False, reparse=True)

    assert report["tally"]["changed"] == 1
    test_db.expire_all()
    assert (job.loc_country, job.loc_region, job.loc_city) == ("US", "IN", "ka, bengaluru")
    assert [(r.country, r.region, r.city) for r in job.locations] == [
        ("US", "IN", "ka, bengaluru")]


def test_a_commit_rewrites_the_columns_and_the_rows(test_db):
    job = _job(test_db, "IN, KA, Bengaluru", "US", "IN", "ka, bengaluru",
               [("US", "IN", "ka, bengaluru")])

    report = run(commit=True, reparse=True)

    assert report["tally"]["changed"] == 1
    test_db.expire_all()
    assert (job.loc_country, job.loc_region, job.loc_city) == ("IN", "KA", "bengaluru")
    # delete and recreate: the place the old parse invented is gone, not kept
    assert [(r.country, r.region, r.city)
            for r in test_db.query(JobLocation).all()] == [("IN", "KA", "bengaluru")]
    assert test_db.query(JobLocation).one().is_primary is True


def test_a_row_the_parser_still_reads_the_same_way_is_left_alone(test_db):
    _job(test_db, "Seattle, WA", "US", "WA", "seattle", [("US", "WA", "seattle")])

    report = run(commit=True, reparse=True)

    assert report["tally"]["changed"] == 0
    assert report["tally"]["scanned"] == 1


def test_without_the_flag_a_parsed_row_is_not_touched(test_db):
    """The default pass fills empty columns only, which is why it could not fix
    the rows this flag exists for."""
    _job(test_db, "IN, KA, Bengaluru", "US", "IN", "ka, bengaluru")

    report = run(commit=True)

    assert report["tally"].get("scanned", 0) == 0
