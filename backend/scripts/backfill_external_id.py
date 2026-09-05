"""One-shot backfill: recompute Job.external_id with the canonical hash.

Context: v2-testing/round4/dup-report.md Section 2 ("Recommended follow-up").
`_canonical_for_hash()` in backend/scraper/_shared/dedup.py now folds scheme,
`www.`, path case, a trailing slash, an ATS apply/thanks suffix, and
query-param order before hashing. Stored `Job.external_id` values were never
rewritten when that landed, so ~35% of rows carry an id that no longer matches
what a fresh scrape of the same posting would compute. Layer 2 (`content_hash`)
covers the practical risk today; this script closes the gap so layer 1 keeps
carrying the load.

This is a maintenance script, not a seed step — run it by hand, once, inside
the backend container:

    python -m backend.scripts.backfill_external_id --dry-run
    python -m backend.scripts.backfill_external_id --apply

Always run --dry-run first and compare the counts against the report before
--apply. Take a `pg_dump` before --apply (project rule for any destructive/
data-changing op) — this script only ever UPDATEs existing rows (never
merges or deletes), but back up anyway.

Collision policy: this recomputes `external_id` for EVERY row and groups the
results globally (not batch-local) because a collision can span batches. When
two or more rows land on the same new id, one row (the "winner" — the row
that already holds that id unchanged, if any, else the row with the smallest
UUID for determinism) is updated (or left alone if it's already correct); the
rest are SKIPPED — their existing `external_id` is left untouched — and
recorded in v2-testing/round4/backfill-collisions.md. Nothing is ever merged
or deleted.
"""
import argparse
import sys
from collections import defaultdict
from pathlib import Path

from sqlalchemy import text

from backend.models.db import SessionLocal, Job
from backend.scraper._shared.dedup import make_external_id

BATCH_SIZE = 1000
REPO_ROOT = Path(__file__).resolve().parents[2]
COLLISIONS_REPORT = REPO_ROOT / "v2-testing" / "round4" / "backfill-collisions.md"


def fetch_all_rows(db):
    """SELECT id, company, title, url, external_id for every job, in batches of 1000."""
    rows = []
    last_id = None
    while True:
        q = db.query(Job.id, Job.company, Job.title, Job.url, Job.external_id).order_by(Job.id)
        if last_id is not None:
            q = q.filter(Job.id > last_id)
        batch = q.limit(BATCH_SIZE).all()
        if not batch:
            break
        rows.extend(batch)
        last_id = batch[-1][0]
        if len(batch) < BATCH_SIZE:
            break
    return rows


def compute_new_ids(rows):
    """Return (id, company, title, url, stored_id, new_id) for every row."""
    computed = []
    for id_, company, title, url, stored_id in rows:
        new_id = make_external_id(company, title, url)
        computed.append((id_, company, title, url, stored_id, new_id))
    return computed


def resolve_updates(computed):
    """Decide, per row, whether it is unchanged, updated, or skipped as a collision.

    Grouping is global (across the whole table), matching how dup-report.md
    computed "distinct ids under the new normalisation": every row's
    recomputed id is grouped, and any id claimed by more than one row is a
    collision to resolve here rather than an UPDATE to run.
    """
    groups = defaultdict(list)
    for rec in computed:
        groups[rec[5]].append(rec)

    updates = []     # (id, new_id)
    skipped = []     # (skipped_id, kept_id, skipped_url, skipped_stored_id)
    unchanged = 0

    for new_id, recs in groups.items():
        if len(recs) == 1:
            id_, _company, _title, _url, stored_id, _new_id = recs[0]
            if stored_id == new_id:
                unchanged += 1
            else:
                updates.append((id_, new_id))
            continue

        # Collision: prefer the row that already holds this id (no-op for it),
        # else pick deterministically (smallest UUID) so reruns are stable.
        winner = next((r for r in recs if r[4] == new_id), None)
        if winner is None:
            winner = min(recs, key=lambda r: str(r[0]))

        for rec in recs:
            id_, _company, _title, url, stored_id, _new_id = rec
            if rec is winner:
                if stored_id == new_id:
                    unchanged += 1
                else:
                    updates.append((id_, new_id))
            else:
                skipped.append((id_, winner[0], url, stored_id))

    return updates, skipped, unchanged


def apply_updates(db, updates):
    """UPDATE rows in batches of 1000, one transaction per batch."""
    stmt = text("UPDATE jobs SET external_id = :new_id WHERE id = :id")
    for i in range(0, len(updates), BATCH_SIZE):
        batch = updates[i:i + BATCH_SIZE]
        params = [{"id": id_, "new_id": new_id} for id_, new_id in batch]
        db.execute(stmt, params)
        db.commit()


def write_collisions_report(skipped, computed_by_id, dry_run):
    COLLISIONS_REPORT.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# External-id backfill collisions",
        "",
        "Generated by `backend/scripts/backfill_external_id.py` "
        f"({'--dry-run' if dry_run else '--apply'}). See dup-report.md Section 2.",
        "",
        "Rows below kept their existing `external_id` because the recomputed id "
        "was already claimed by another row (the \"kept id\" row). Nothing was "
        "merged or deleted.",
        "",
    ]
    if not skipped:
        lines.append("No collisions found.")
    else:
        lines.append("| skipped id | kept id | skipped row's url | skipped row's stored external_id |")
        lines.append("|---|---|---|---|")
        for skipped_id, kept_id, url, stored_id in skipped:
            lines.append(f"| {skipped_id} | {kept_id} | {url} | {stored_id} |")
    COLLISIONS_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Compute and print counts only. No writes.")
    parser.add_argument("--apply", action="store_true", help="Write the recomputed external_id values.")
    args = parser.parse_args()

    if args.dry_run and args.apply:
        parser.error("pass either --dry-run or --apply, not both")
    if not args.dry_run and not args.apply:
        parser.error("pass --dry-run or --apply")
    dry_run = args.dry_run

    db = SessionLocal()
    try:
        rows = fetch_all_rows(db)
        computed = compute_new_ids(rows)
        updates, skipped, unchanged = resolve_updates(computed)

        update_label = "would update" if dry_run else "updated"
        print(f"total jobs:          {len(rows)}")
        print(f"unchanged:           {unchanged}")
        print(f"{update_label}:{' ' * (21 - len(update_label))}{len(updates)}")
        print(f"skipped-collisions:  {len(skipped)}")

        write_collisions_report(skipped, {r[0]: r for r in computed}, dry_run)
        print(f"collision list written to {COLLISIONS_REPORT}")

        if dry_run:
            print("\n--dry-run: no writes made.")
        else:
            apply_updates(db, updates)
            print(f"\n--apply: committed {len(updates)} updates in "
                  f"{(len(updates) + BATCH_SIZE - 1) // BATCH_SIZE or 0} batch(es).")
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
