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

from backend.analyzer.location import fold, parse
from backend.models.db import Job, SessionLocal

logger = logging.getLogger("jobnavigator.backfill.location")

BATCH = 500


def run(commit: bool = False) -> dict:
    db = SessionLocal()
    tally = collections.Counter()
    unresolved = collections.Counter()
    try:
        query = (db.query(Job)
                 .filter(Job.location.isnot(None), Job.location != "")
                 .filter(Job.loc_country.is_(None), Job.loc_region.is_(None),
                         Job.loc_city.is_(None))
                 .order_by(Job.discovered_at))
        pending = 0
        for job in query.yield_per(BATCH):
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
                job.loc_country = parsed["country"]
                job.loc_region = parsed["region"]
                job.loc_city = fold(parsed["city"]) if parsed["city"] else None
                pending += 1
                if pending >= BATCH:
                    db.commit()
                    pending = 0
        if commit:
            db.commit()
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
