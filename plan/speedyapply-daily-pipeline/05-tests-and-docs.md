# Subproblem 5: Verify and document the workflow

## 1. Goal
Prove the new workflow works without regressing existing scraping, scheduling, tailoring, and frontend behavior, then document setup and limits.

## 2. Why this step exists
This feature crosses network parsing, persistence, background jobs, LLM calls, scheduling, APIs, and UI. Focused tests plus existing regression suites are required before it is safe to hand off.

## 3. Files involved
- `backend/tests/test_speedyapply_source.py` - parser and importer tests.
- `backend/tests/test_speedyapply_pipeline.py` - queue and tailoring orchestration tests.
- `backend/tests/test_speedyapply_scheduler.py` - schedule/timezone tests.
- `backend/tests/test_routes_apply_queue.py` - ready-list, acknowledgement, and manual trigger API tests.
- `README.md` - document configuration, daily behavior, and manual-application boundary.
- Existing backend tests and `frontend/package.json` scripts - use as regression verification paths.

## 4. Exact changes
- Add network-free Markdown fixtures directly in tests.
- Mock description fetching and LLM tailoring; assert no real employer or model calls occur in tests.
- Cover idempotency, retryable failures, queue serialization, and acknowledgement.
- Update README feature and setup sections with the SpeedyApply workflow.
- Run focused tests, the complete backend test suite, and the frontend production build.

## 5. Out of scope
- Do not create brittle live-network CI tests.
- Do not claim every employer page can be scraped or framed.

## 6. Done condition
Focused tests pass, the frontend builds, and any failures in the full suite are either fixed or clearly proven unrelated.

## 7. Verification
- `python -m pytest backend/tests/test_speedyapply_source.py backend/tests/test_speedyapply_pipeline.py backend/tests/test_speedyapply_scheduler.py backend/tests/test_routes_apply_queue.py -q`
- `python -m pytest backend/tests -q`
- `npm run build` from `frontend/`
- `git diff --check`

## 8. Expected output
Regression coverage, a successful frontend build, and user-facing documentation.

## 9. Notes for the next step
No later implementation step remains; handoff should identify configuration defaults and operational requirements.

## 10. Risks or ambiguity
The full backend suite can be long and environment-sensitive. Focused tests are mandatory; any unrelated full-suite failure must be reported with evidence.
