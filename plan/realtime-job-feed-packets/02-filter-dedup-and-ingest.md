# Subproblem 2: Filter, deduplicate, and ingest

## 1. Goal
Turn normalized feed rows into one eligible Job and one queue item per real posting without duplicate work across repositories.

## 2. Why this step exists
The chosen feeds overlap heavily and contain roles that are unsuitable for the user's F-1/OPT, US, SWE/AI/data search.

## 3. Files involved
- `backend/scraper/sources/job_feeds.py` - apply source filters, canonical identities, description enrichment, and persistence.
- `backend/scraper/_shared/dedup.py` - expose a stable normalized application identity helper.
- `backend/automation/speedyapply_pipeline.py` - enqueue generic candidates while preserving legacy entry points.
- `backend/tests/test_job_feeds_ingest.py` - cover role, location, work-authorization, and cross-source cases.

## 4. Exact changes
- Filter to US or Remote-US internships/new-grad roles in SWE, AI/ML, data engineering, and data science.
- Reject source flags for no sponsorship, citizenship, closure, or incompatible required degree.
- Extract ATS posting IDs where possible and fall back to normalized direct URL, then company/title/location fingerprint.
- Link every source occurrence through `JobFeedPosting` so one Job can retain several sources.
- Fetch employer JD text concurrently and run deterministic no-sponsorship, citizenship, clearance, and required-degree blockers.
- Enqueue first-run rows from the last seven days, live rows before backfill, with a per-poll cap of 25.

## 5. Out of scope
Do not call an LLM, export a resume, or send the terminal notification.

## 6. Done condition
Eligible duplicates from different sources converge on one Job and queue item, while hard-blocked rows do not enter tailoring.

## 7. Verification
- Run `pytest backend/tests/test_job_feeds_ingest.py backend/tests/test_shared_dedup.py backend/tests/test_speedyapply_pipeline.py`.

## 8. Expected output
An idempotent generic ingest operation that returns newly queued IDs and source health information.

## 9. Notes for the next step
The next worker may assume a queued Job has either a usable description or a retryable `pending_description` state.

## 10. Risks or ambiguity
Some feeds omit sponsorship flags. Only explicit negative JD language is a blocker; ambiguous sponsorship language remains eligible with a warning.
