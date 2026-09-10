"""Backfill the parsed location columns from `jobs.location`.

By default only rows whose parsed columns are still empty are touched, and
`location` itself is never rewritten. An ambiguous parse writes nothing, so a
job never lands in the wrong country.

`--reparse` reads every row that has a location instead, and rewrites the ones
the parser now reads differently. That is the flag to use after a parser fix:
the "IN, KA, Bengaluru" shape was filed as Indiana on 365 rows, and only a
re-parse of rows that already have columns can move them.

    python -m backend.scripts.backfill_location                      # dry run
    python -m backend.scripts.backfill_location --commit             # write
    python -m backend.scripts.backfill_location --reparse            # dry run
    python -m backend.scripts.backfill_location --reparse --commit   # write
"""
import argparse
import collections
import logging
import sys

from backend.analyzer.location import _places_of, apply_location_to_job, parse
from backend.models.db import Job, JobLocation, SessionLocal

logger = logging.getLogger("jobnavigator.backfill.location")

BATCH = 500


def _reparse_job(job, commit: bool):
    """Rewrite one job's parsed place when the parser now reads it differently.

    Returns (changed, before, after). The extra places a board named live on
    `job_locations`, and a scrape is the only thing that knows them, so a
    re-parse works from `job.location` alone and rebuilds the rows for that job
    from what it finds there.
    """
    places = _places_of([job.location]) if job.location else []
    after = places[0] if places else (None, None, None)
    before = (job.loc_country, job.loc_region, job.loc_city)
    if before == after:
        return False, before, after
    if commit:
        job.loc_country, job.loc_region, job.loc_city = after
        # delete and recreate: the parse that produced the old rows is gone, and
        # a partial update would leave a place the string no longer names.
        job.locations.clear()
        # flush the deletes now: in one flush SQLAlchemy inserts before it deletes,
        # and an unchanged place would collide with its own old row (uq_job_location)
        from sqlalchemy.orm import object_session
        session = object_session(job)
        if session is not None:
            session.flush()
        for index, (country, region, city) in enumerate(places):
            job.locations.append(JobLocation(country=country, region=region,
                                             city=city, is_primary=index == 0))
    return True, before, after


def run(commit: bool = False, reparse: bool = False) -> dict:
    db = SessionLocal()
    tally = collections.Counter()
    unresolved = collections.Counter()
    changes = []
    # A stable shape for the report, so a caller never has to guess whether a
    # missing key means zero or means the pass never ran.
    tally.update({"scanned": 0, "changed": 0} if reparse
                 else {"scanned": 0, "resolved": 0})
    try:
        query = (db.query(Job.id)
                 .filter(Job.location.isnot(None), Job.location != "")
                 .order_by(Job.discovered_at))
        if not reparse:
            query = query.filter(Job.loc_country.is_(None), Job.loc_region.is_(None),
                                 Job.loc_city.is_(None))
        # ids first, rows per batch: a commit inside a server-side cursor loop
        # invalidates the cursor on Postgres ("named cursor isn't valid anymore")
        ids = [row[0] for row in query.all()]
        for start in range(0, len(ids), BATCH):
            chunk = ids[start:start + BATCH]
            for job in db.query(Job).filter(Job.id.in_(chunk)).all():
                tally["scanned"] += 1
                if reparse:
                    changed, before, after = _reparse_job(job, commit)
                    if changed:
                        tally["changed"] += 1
                        if len(changes) < 20:
                            changes.append((job.location, before, after))
                    if not any(after):
                        unresolved[job.location] += 1
                    continue

                parsed = parse(job.location or "")
                if parsed["ambiguous"]:
                    tally["ambiguous"] += 1
                    unresolved[job.location] += 1
                    continue
                if not (parsed["country"] or parsed["region"] or parsed["city"]):
                    tally["unresolved"] += 1
                    unresolved[job.location] += 1
                    continue

                tally["resolved"] += 1
                if parsed["country"]:
                    tally["country"] += 1
                if parsed["city"]:
                    tally["city"] += 1
                if commit:
                    # One JobLocation row per place, primary first. The extra places
                    # a board named are only on the scraped rows, so a backfill sees
                    # the primary one alone.
                    apply_location_to_job(job)
            if commit:
                db.commit()
            else:
                db.expunge_all()
    finally:
        db.close()
    return {"tally": dict(tally), "unresolved": unresolved.most_common(15),
            "changes": changes}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", action="store_true",
                        help="write the results; without it nothing is saved")
    parser.add_argument("--reparse", action="store_true",
                        help=("re-read every row that has a location and rewrite "
                              "the ones the parser now reads differently, rows "
                              "with parsed columns included"))
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    report = run(commit=args.commit, reparse=args.reparse)
    tally = report["tally"]
    scanned = tally.get("scanned", 0) or 1

    logger.info("%s", "COMMIT" if args.commit else "DRY RUN - nothing written")
    if args.reparse:
        logger.info("scanned    %d", tally.get("scanned", 0))
        logger.info("changed    %d (%.1f%%)", tally.get("changed", 0),
                    100.0 * tally.get("changed", 0) / scanned)
        for text, before, after in report["changes"]:
            logger.info("    %-40r %s -> %s", text, before, after)
        logger.info("still unresolved %d distinct strings", len(report["unresolved"]))
        for text, count in report["unresolved"]:
            logger.info("    %4d  %r", count, text)
        return 0

    logger.info("scanned    %d", tally.get("scanned", 0))
    logger.info("resolved   %d (%.1f%%)", tally.get("resolved", 0),
                100.0 * tally.get("resolved", 0) / scanned)
    logger.info("  country  %d", tally.get("country", 0))
    logger.info("  city     %d", tally.get("city", 0))
    logger.info("ambiguous  %d  -> left empty on purpose", tally.get("ambiguous", 0))
    logger.info("unresolved %d", tally.get("unresolved", 0))
    for text, count in report["unresolved"]:
        logger.info("    %4d  %r", count, text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
