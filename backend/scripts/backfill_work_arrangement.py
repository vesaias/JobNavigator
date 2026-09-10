"""Backfill `jobs.remote` from the work-arrangement cascade.

Only rows where `remote IS NULL` are touched, so a value a scraper already wrote
is never overwritten. Run the dry pass first and read the counts.

    python -m backend.scripts.backfill_work_arrangement            # dry run
    python -m backend.scripts.backfill_work_arrangement --commit   # write
"""
import argparse
import collections
import logging
import sys

from backend.analyzer.work_arrangement import REMOTE, extract_arrangement
from backend.models.db import Job, SessionLocal

logger = logging.getLogger("jobnavigator.backfill.arrangement")

BATCH = 500


def run(commit: bool = False, limit: int = None) -> dict:
    """Resolve every unresolved job. Returns the tally."""
    db = SessionLocal()
    tally = collections.Counter()
    by_tier = collections.Counter()
    try:
        query = db.query(Job).filter(Job.remote.is_(None)).order_by(Job.discovered_at)
        if limit:
            query = query.limit(limit)

        pending = 0
        for job in query.yield_per(BATCH):
            tally["scanned"] += 1
            result = extract_arrangement(
                location=job.location,
                title=job.title,
                description=job.description,
            )
            arrangement = result["arrangement"]
            if arrangement is None:
                tally["unresolved"] += 1
                continue

            tally[arrangement] += 1
            by_tier[result["arrangement_source"]] += 1
            if commit:
                job.remote = arrangement == REMOTE
                pending += 1
                if pending >= BATCH:
                    db.commit()
                    pending = 0

        if commit:
            db.commit()
    finally:
        db.close()

    tally["resolved"] = tally["scanned"] - tally["unresolved"]
    return {"tally": dict(tally), "by_tier": dict(by_tier)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", action="store_true",
                        help="write the results; without it nothing is saved")
    parser.add_argument("--limit", type=int, default=None,
                        help="stop after this many unresolved jobs")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    report = run(commit=args.commit, limit=args.limit)

    tally, by_tier = report["tally"], report["by_tier"]
    mode = "COMMIT" if args.commit else "DRY RUN — nothing written"
    logger.info("%s", mode)
    logger.info("scanned    %d", tally.get("scanned", 0))
    logger.info("resolved   %d", tally.get("resolved", 0))
    logger.info("  remote   %d", tally.get("remote", 0))
    logger.info("  hybrid   %d  -> remote=False", tally.get("hybrid", 0))
    logger.info("  onsite   %d  -> remote=False", tally.get("onsite", 0))
    logger.info("unresolved %d  -> left NULL", tally.get("unresolved", 0))
    logger.info("decided by: %s", by_tier or "-")
    return 0


if __name__ == "__main__":
    sys.exit(main())
