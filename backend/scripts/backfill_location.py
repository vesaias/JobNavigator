"""Backfill the parsed location columns from `jobs.location`.

Only rows whose parsed columns are still empty are touched, and `location`
itself is never rewritten. An ambiguous parse writes nothing, so a job never
lands in the wrong country.

    python -m backend.scripts.backfill_location            # dry run
    python -m backend.scripts.backfill_location --commit   # write
"""
import argparse
import collections
import logging
import sys

from backend.analyzer.location import apply_location_to_job, parse
from backend.models.db import Job, SessionLocal

logger = logging.getLogger("jobnavigator.backfill.location")

BATCH = 500


def run(commit: bool = False) -> dict:
    db = SessionLocal()
    tally = collections.Counter()
    unresolved = collections.Counter()
    try:
        query = (db.query(Job.id)
                 .filter(Job.location.isnot(None), Job.location != "")
                 .filter(Job.loc_country.is_(None), Job.loc_region.is_(None),
                         Job.loc_city.is_(None))
                 .order_by(Job.discovered_at))
        # ids first, rows per batch: a commit inside a server-side cursor loop
        # invalidates the cursor on Postgres ("named cursor isn't valid anymore")
        ids = [row[0] for row in query.all()]
        for start in range(0, len(ids), BATCH):
            chunk = ids[start:start + BATCH]
            for job in db.query(Job).filter(Job.id.in_(chunk)).all():
                tally["scanned"] += 1
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
    return {"tally": dict(tally), "unresolved": unresolved.most_common(15)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", action="store_true",
                        help="write the results; without it nothing is saved")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    report = run(commit=args.commit)
    tally = report["tally"]
    scanned = tally.get("scanned", 0) or 1

    logger.info("%s", "COMMIT" if args.commit else "DRY RUN - nothing written")
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
