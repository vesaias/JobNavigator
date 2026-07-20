# Subproblem 3: Schedule and expose the workflow

## 1. Goal
Register a configurable daily cron job, allow a manual run, and expose ready items plus acknowledgement through authenticated API routes.

## 2. Why this step exists
The workflow must run unattended each day and the frontend needs a stable contract for showing only items that still need the user's attention.

## 3. Files involved
- `backend/seed.py` - add defaults for enabled state, cron, timezone, feeds, age, run cap, auto-tailor, and base resume.
- `backend/scheduler.py` - register and run the daily SpeedyApply pipeline.
- `backend/api/routes_settings.py` - reconfigure the scheduler when SpeedyApply timing settings change.
- `backend/api/routes_apply_queue.py` - new list, acknowledge, retry/manual-run endpoints.
- `backend/main.py` - include the new router and tag.

## 4. Exact changes
- Seed a daily cron and `Asia/Shanghai` timezone while keeping both editable.
- Extend scheduler configuration to add `speedyapply_daily` only when enabled and the cron is valid.
- Use `ZoneInfo` for the SpeedyApply trigger so Docker host timezone does not shift the requested local time.
- Run the pipeline inside `tracked_run` and reject overlapping runs.
- Add `POST /api/apply-queue/run` as a tracked background manual trigger.
- Add `GET /api/apply-queue/ready` with `unseen_only` and useful form/resume paths.
- Add `POST /api/apply-queue/{item_id}/acknowledge`.
- Return queue errors and running status without exposing LLM/API secrets.

## 5. Out of scope
- Do not add a second scheduler service or an operating-system task.
- Do not expose unauthenticated mutation endpoints.

## 6. Done condition
The scheduler contains the daily job with the configured timezone, settings changes reconfigure it, manual runs are monitored, and the ready endpoint returns stable paths.

## 7. Verification
- Run `python -m pytest backend/tests/test_speedyapply_scheduler.py backend/tests/test_routes_apply_queue.py -q`.
- Inspect a configured trigger and verify its timezone and job ID.

## 8. Expected output
A daily in-process schedule and authenticated queue API.

## 9. Notes for the next step
The dashboard can poll `GET /api/apply-queue/ready?unseen_only=true` after login and acknowledge displayed items.

## 10. Risks or ambiguity
APScheduler runs only while the backend container is running. The UI and documentation must state this operational requirement.
