# Subproblem 2: Track and prepare applications

## 1. Goal
Persist one preparation item per job and run a bounded, tracked resume-tailoring task that produces a ready-to-apply item.

## 2. Why this step exists
The existing tailoring endpoint launches a background task for an interactive request, but a daily workflow needs durable status, retries, deduplication, and a reliable link from each job to its generated resume.

## 3. Files involved
- `backend/models/db.py` - add the application preparation queue model and relationships.
- `backend/seed.py` - add idempotent PostgreSQL migration SQL for the new table and indexes.
- `backend/automation/__init__.py` - new package marker.
- `backend/automation/speedyapply_pipeline.py` - new daily orchestration and per-job preparation worker.
- `backend/api/routes_resumes.py` - reuse `_tailor_impl`; make only narrow changes if its return value is needed to identify the generated resume.
- `backend/job_monitor.py` - reuse tracked job runs without changing its API unless a result summary is necessary.

## 4. Exact changes
- Add `ApplicationQueueItem` with unique `job_id`, selected base identifier, generated `resume_id`, source feed, status, attempt count, error, acknowledgement timestamp, and created/updated timestamps.
- Add migrations that create the table for existing PostgreSQL deployments.
- Resolve the base resume in this order: SpeedyApply-specific setting, global default resume, populated Persona, then most recently updated base resume.
- For each imported job, create or reuse a queue item.
- Retry missing JD extraction before tailoring; keep a clear failed state when no truthful description can be obtained.
- Reuse the existing truthful resume-tailoring implementation and its concurrency semaphore. Prevent duplicate tailored resumes for the same queue item.
- Track each per-job worker as `speedyapply_prepare` with `target_job_id` so the UI and run history expose progress.
- Mark the queue item `ready` only after a resume row exists; otherwise store the exception and leave it retryable.

## 5. Out of scope
- Do not automatically accept speculative suggested bullets.
- Do not generate or store answers to employer-specific form questions.
- Do not automatically apply or mark a job applied.

## 6. Done condition
Each eligible job has at most one queue item. Successful processing links exactly one tailored resume and reaches `ready`; failures are recorded and can be retried by a later run.

## 7. Verification
- Run `python -m pytest backend/tests/test_speedyapply_pipeline.py -q`.
- Verify ready, failure, retry, base-resume resolution, and duplicate-run cases.

## 8. Expected output
A durable preparation queue and a bounded background-agent pipeline that turns imported jobs into ready application tasks.

## 9. Notes for the next step
The API can serialize ready queue items without discovering resumes indirectly from job rows.

## 10. Risks or ambiguity
LLM calls cost money and may fail. The max-jobs setting, posting-age filter, concurrency semaphore, and durable error state bound and expose that risk.
