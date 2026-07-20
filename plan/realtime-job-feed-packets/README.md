# Task Plan: Realtime job feed packets

## Overall goal
Turn the existing daily SpeedyApply workflow into a durable five-minute monitor for the selected 2027 aggregate feeds. It must filter for the user's SWE, AI, and data targets, prepare one Persona-based resume without scoring, save a job-mapped application packet under the project, and send two idempotent Gmail notifications.

## Subproblems
1. `01-feed-model-and-parsers.md` - add durable feed state and normalize the three selected repositories - status: verified
2. `02-filter-dedup-and-ingest.md` - filter for eligibility, deduplicate across sources, and enqueue new jobs - status: verified
3. `03-tailor-and-export-packet.md` - tailor without scoring and atomically export mapped application packets - status: verified
4. `04-email-scheduler-api-ui.md` - add Gmail notifications, split schedulers, API status, settings, and Docker persistence - status: verified
5. `05-tests-and-docs.md` - run focused and regression verification and document setup - status: verified

## Dependencies
Step 2 consumes the normalized feed records and checkpoint tables from step 1. Step 3 consumes durable queue items created by step 2. Step 4 sends notifications for state transitions produced by steps 2 and 3 and exposes their state. Step 5 verifies the whole chain.

## Recommended execution order
Implement the storage model and pure parsers first. Add deterministic filters and cross-source identity next. Once ingestion is stable, add the no-score tailoring worker and packet writer. Register email and scheduling only after those operations are idempotent. Finish with the full verification pass and documentation.

## End-to-end verification
- Run the focused feed, pipeline, packet, Gmail, scheduler, and route pytest files.
- Run the complete `pytest` suite from the repository root.
- Run `npm run build` from `frontend/`.
- With external calls mocked, add one posting to a fixture and observe exactly one Job, one queue item, one detected notification, one packet directory, and one terminal notification.
- Confirm `application-packets/index.csv` maps the queue, job, resume, direct application URL, and packet path.
