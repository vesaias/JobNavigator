# Task Plan: SpeedyApply daily application pipeline

## Overall goal
Add a daily, self-hosted workflow that reads the public `speedyapply/2027-SWE-College-Jobs` lists, imports only recent jobs, fetches each job description, creates a tailored resume with the existing LLM workflow, and shows an in-app application modal with the job form and resume links. The workflow prepares applications but does not submit forms automatically.

## Subproblems
1. `01-source-import.md` - parse configured SpeedyApply Markdown feeds and import recent jobs with descriptions - status: verified
2. `02-application-agent.md` - persist application preparation state and run one tracked resume-tailoring task per job - status: verified
3. `03-scheduler-and-api.md` - add the daily cron job, settings, manual trigger, and ready-queue API - status: verified
4. `04-dashboard-popup.md` - show ready jobs and resume/application paths in an in-app modal and expose settings - status: verified
5. `05-tests-and-docs.md` - add regression tests, build the frontend, and document the workflow - status: verified

## Dependencies
The source importer must exist before the application agent can consume imported jobs. The persisted queue and agent must exist before the scheduler and API can expose reliable state. The frontend depends on the queue API. Tests cover each layer and the final integrated behavior.

## Recommended execution order
Implement the source parser first, then the persisted application queue and tailoring orchestration. Register the scheduler and API only after the worker behavior is testable. Add the modal and settings after the API contract is stable. Finish with focused backend tests, the full backend test suite when practical, and the production frontend build.

## End-to-end verification
- Run focused pytest tests for SpeedyApply parsing, deduplication, queue processing, scheduler registration, and API acknowledgement.
- Run the existing backend pytest suite to detect regressions.
- Run `npm run build` in `frontend/`.
- Manually trigger `POST /api/apply-queue/run`, poll the run monitor, then confirm `GET /api/apply-queue/ready` returns application URLs and tailored resume PDF/editor URLs.
- Load the dashboard and confirm the ready-to-apply modal opens, links work, and acknowledgement prevents the same item from reopening.
