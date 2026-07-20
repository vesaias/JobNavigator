# Subproblem 5: Tests and documentation

## 1. Goal
Prove the feature works across restarts, duplicated sources, external failures, and the production frontend build, then document the exact setup.

## 2. Why this step exists
Silent monitoring or mapping failures would defeat the purpose of applying quickly.

## 3. Files involved
- `backend/tests/test_job_feeds_source.py` - parser and checkpoint regression coverage.
- `backend/tests/test_job_feeds_ingest.py` - filters, identity, and queue coverage.
- `backend/tests/test_application_packets.py` - packet and no-score coverage.
- Existing Gmail, scheduler, apply-queue, and SpeedyApply tests - backward compatibility.
- `README.md` and `LEGAL_DISCLAIMER.md` - setup, limits, and human-submit boundary.

## 4. Exact changes
- Add failure and restart scenarios for Atom/raw fetches, JD fetches, LLM responses, PDF rendering, disk writes, and Gmail sends.
- Assert the first run backfills seven days and live work outranks backlog.
- Assert a duplicated posting creates one packet and one pair of notifications.
- Document Gmail reauthorization, Persona prerequisites, packet location, source-latency limits, manual trigger, and status endpoint.
- Run focused tests, full pytest, and frontend production build; fix regressions within the approved feature scope.

## 5. Out of scope
Do not perform live applications or send real notification emails during tests.

## 6. Done condition
Focused tests, the full backend suite, and frontend build pass, and a new user can configure the feature from the README.

## 7. Verification
- Run `pytest` from the repository root.
- Run `npm run build` from `frontend/`.
- Inspect `git diff --check`.

## 8. Expected output
Regression-tested implementation, updated documentation, and all plan statuses marked verified.

## 9. Notes for the next step
No later implementation step remains; the result is ready for user configuration and live OAuth reauthorization.

## 10. Risks or ambiguity
Live upstream formatting and Gmail authorization cannot be fully validated in an offline test, so the documentation must include a manual smoke test.
