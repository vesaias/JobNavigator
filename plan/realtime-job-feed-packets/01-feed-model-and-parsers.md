# Subproblem 1: Feed model and parsers

## 1. Goal
Represent upstream feed checkpoints and source observations durably, then parse the selected SpeedyApply and Vansh repositories into one normalized record shape.

## 2. Why this step exists
Polling every five minutes must survive restarts and must not bind the pipeline to one table header convention.

## 3. Files involved
- `backend/models/db.py` - add checkpoint and source-observation models and extend queue metadata.
- `backend/seed.py` - add idempotent PostgreSQL migrations and default feed settings.
- `backend/scraper/sources/job_feeds.py` - define source registry, Atom polling, date parsing, and normalized parsers.
- `backend/scraper/sources/speedyapply.py` - keep compatibility exports for existing callers and tests.
- `backend/tests/test_job_feeds_source.py` - test every supported table shape and checkpoint behavior.

## 4. Exact changes
- Add `JobFeedCheckpoint` keyed by repository ID with last commit SHA, content hash, timestamps, and error state.
- Add `JobFeedPosting` keyed by source plus source posting key and linked to one Job.
- Extend `ApplicationQueueItem` with source-posted time, priority, artifact path, and notification timestamps.
- Register the four selected US feeds across three repositories and fetch commit Atom XML before raw documents.
- Normalize header aliases, HTML links, inherited companies, age values, date-posted values, salary hints, and legend flags into `FeedJob`.
- Keep legacy SpeedyApply parser imports working.

## 5. Out of scope
Do not fetch employer JDs, run filters, tailor resumes, or send notifications in this step.

## 6. Done condition
Fixtures from all selected repositories parse into the same fields, and unchanged checkpoints result in no raw-feed work.

## 7. Verification
- Run `pytest backend/tests/test_job_feeds_source.py backend/tests/test_speedyapply_source.py`.

## 8. Expected output
Durable feed models, a generic source module, compatibility wrappers, and passing parser tests.

## 9. Notes for the next step
The next step may assume every record contains a source ID, repository ID, company, title, location, direct URL, posted time or age, role kind, and source flags.

## 10. Risks or ambiguity
Vansh dates omit a year, so parse them as the most recent non-future month/day. Upstream formatting can drift; malformed rows must be skipped without discarding other valid rows.
