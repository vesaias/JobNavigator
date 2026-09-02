# Endpoint inventory (from /openapi.json, 94 paths, 110 operations)

Check = exercised in this pass. Used-by is filled from the screen inventories.

| ✓ | Method | Path | Tag | Summary | Used by (v2 / v1) |
|---|---|---|---|---|---|
| [ ] | GET | `/api/activity-log` | scheduler | Activity log | |
| [ ] | POST | `/api/analyze/{job_id}` | triggers | Analyze a single job | |
| [ ] | POST | `/api/applications` | applications | Create Application | |
| [ ] | GET | `/api/applications` | applications | List Applications | |
| [ ] | POST | `/api/applications/extract` | applications | Extract Posting | |
| [ ] | PATCH | `/api/applications/interviews/{interview_id}` | applications | Update Interview | |
| [ ] | DELETE | `/api/applications/interviews/{interview_id}` | applications | Delete Interview | |
| [ ] | PATCH | `/api/applications/{app_id}` | applications | Update Application | |
| [ ] | DELETE | `/api/applications/{app_id}` | applications | Delete Application | |
| [ ] | POST | `/api/applications/{app_id}/interviews` | applications | Add Interview | |
| [ ] | GET | `/api/applications/{app_id}/prep` | applications | Prep Bundle | |
| [ ] | POST | `/api/auth/logout` | auth | Clear session cookie | |
| [ ] | POST | `/api/auth/set-session` | auth | Set session cookie from API key | |
| [ ] | POST | `/api/auth/verify` | auth | Verify an API key without setting a session | |
| [ ] | POST | `/api/auto-reject/run` | triggers | Run auto-reject now | |
| [ ] | POST | `/api/autofill/answer` | autofill | Autofill Answer | |
| [ ] | POST | `/api/autofill/answer/stream` | autofill | Autofill Answer Stream | |
| [ ] | GET | `/api/autofill/config` | autofill | Autofill Config | |
| [ ] | GET | `/api/companies` | companies | List Companies | |
| [ ] | POST | `/api/companies` | companies | Create Company | |
| [ ] | POST | `/api/companies/auto-create-from-jobs` | companies | Auto Create From Jobs | |
| [ ] | POST | `/api/companies/backfill-h1b-jobs` | companies | Backfill H1B Jobs | |
| [ ] | POST | `/api/companies/bulk-activate` | companies | Bulk Activate | |
| [ ] | POST | `/api/companies/refresh-h1b` | companies | Refresh H1B All | |
| [ ] | PATCH | `/api/companies/{company_id}` | companies | Update Company | |
| [ ] | DELETE | `/api/companies/{company_id}` | companies | Delete Company | |
| [ ] | POST | `/api/companies/{company_id}/test-scrape` | companies | Test Scrape Company | |
| [ ] | GET | `/api/cover-letters` | cover-letters | List Cover Letters | |
| [ ] | POST | `/api/cover-letters` | cover-letters | Create Cover Letter | |
| [ ] | POST | `/api/cover-letters/generate` | cover-letters | Generate Cover Letter | |
| [ ] | GET | `/api/cover-letters/templates` | cover-letters | List Templates | |
| [ ] | GET | `/api/cover-letters/{cl_id}` | cover-letters | Get Cover Letter | |
| [ ] | PATCH | `/api/cover-letters/{cl_id}` | cover-letters | Update Cover Letter | |
| [ ] | DELETE | `/api/cover-letters/{cl_id}` | cover-letters | Delete Cover Letter | |
| [ ] | GET | `/api/cover-letters/{cl_id}/pdf` | cover-letters | Export Pdf | |
| [ ] | GET | `/api/cover-letters/{cl_id}/tracer-stats` | cover-letters | Get Tracer Stats | |
| [ ] | POST | `/api/db/backup` | triggers | Run database backup | |
| [ ] | POST | `/api/db/cleanup` | triggers | Database cleanup | |
| [ ] | POST | `/api/email/check-now` | triggers | Check Gmail now | |
| [ ] | POST | `/api/h1b/refresh` | triggers | Refresh H-1B data | |
| [ ] | GET | `/api/health/entities` | stats | Companies/searches needing attention | |
| [ ] | GET | `/api/jobs` | jobs | List Jobs | |
| [ ] | POST | `/api/jobs/backfill-descriptions` | triggers | Fetch descriptions for jobs missing them | |
| [ ] | POST | `/api/jobs/bulk-update` | jobs | Bulk Update Jobs | |
| [ ] | POST | `/api/jobs/cache-applied` | jobs | Cache Applied Jobs | |
| [ ] | GET | `/api/jobs/companies/list` | jobs | List Job Companies | |
| [ ] | GET | `/api/jobs/feed-stats` | jobs | Feed Stats | |
| [ ] | POST | `/api/jobs/linkedin-import` | jobs | Linkedin Import | |
| [ ] | GET | `/api/jobs/linkedin-import/progress` | jobs | Linkedin Import Progress | |
| [ ] | POST | `/api/jobs/save-from-extension` | jobs | Save From Extension | |
| [ ] | GET | `/api/jobs/sources/list` | jobs | List Job Sources | |
| [ ] | GET | `/api/jobs/unscored-ids` | jobs | Unscored Ids | |
| [ ] | GET | `/api/jobs/verdicts/list` | jobs | List Job Verdicts | |
| [ ] | GET | `/api/jobs/{job_id}` | jobs | Get Job | |
| [ ] | PATCH | `/api/jobs/{job_id}` | jobs | Update Job | |
| [ ] | GET | `/api/jobs/{job_id}/cached-page` | jobs | Get Cached Page | |
| [ ] | GET | `/api/jobs/{job_id}/frame-check` | jobs | Frame Check | |
| [ ] | GET | `/api/jobs/{job_id}/live-page` | jobs | Get Live Page | |
| [ ] | GET | `/api/linkedin/session` | linkedin | Session Status | |
| [ ] | POST | `/api/linkedin/session/pin` | linkedin | Session Pin | |
| [ ] | POST | `/api/linkedin/session/refresh` | linkedin | Session Refresh | |
| [ ] | GET | `/api/llm/models` | settings | List Models | |
| [ ] | GET | `/api/monitor/active` | monitor | Currently running jobs | |
| [ ] | GET | `/api/monitor/finished` | monitor | Recently finished per-job runs | |
| [ ] | GET | `/api/monitor/history` | monitor | Run history | |
| [ ] | GET | `/api/monitor/in-flight` | monitor | Per-job active operations | |
| [ ] | GET | `/api/monitor/run/{run_id}` | monitor | Single run details | |
| [ ] | GET | `/api/persona` | persona | Get Persona | |
| [ ] | PATCH | `/api/persona` | persona | Update Persona | |
| [ ] | POST | `/api/persona/qa-bank` | persona | Append Qa Bank | |
| [ ] | GET | `/api/resumes` | resumes | List Resumes | |
| [ ] | POST | `/api/resumes` | resumes | Create Resume | |
| [ ] | POST | `/api/resumes/copy` | resumes | Copy Resume For Job | |
| [ ] | POST | `/api/resumes/import-pdf` | resumes | Import Pdf | |
| [ ] | GET | `/api/resumes/shelf` | resumes | Resume Shelf | |
| [ ] | POST | `/api/resumes/tailor` | resumes | Tailor Resume | |
| [ ] | GET | `/api/resumes/templates` | resumes | List Templates | |
| [ ] | GET | `/api/resumes/{resume_id}` | resumes | Get Resume | |
| [ ] | PATCH | `/api/resumes/{resume_id}` | resumes | Update Resume | |
| [ ] | DELETE | `/api/resumes/{resume_id}` | resumes | Delete Resume | |
| [ ] | GET | `/api/resumes/{resume_id}/pdf` | resumes | Export Pdf | |
| [ ] | GET | `/api/resumes/{resume_id}/preview` | resumes | Preview Resume | |
| [ ] | POST | `/api/resumes/{resume_id}/score-check` | resumes | Score Check | |
| [ ] | GET | `/api/resumes/{resume_id}/tracer-stats` | resumes | Get Tracer Stats | |
| [ ] | GET | `/api/scheduler/jobs` | scheduler | List scheduled jobs | |
| [ ] | GET | `/api/scrape-log` | stats | Scrape log history | |
| [ ] | POST | `/api/scrape/company/{company_id}` | triggers | Scrape a single company | |
| [ ] | POST | `/api/scrape/run-all` | triggers | Run all scrapes | |
| [ ] | GET | `/api/searches` | searches | List Searches | |
| [ ] | POST | `/api/searches` | searches | Create Search | |
| [ ] | GET | `/api/searches/test-result/{run_id}` | searches | Get Test Result | |
| [ ] | PATCH | `/api/searches/{search_id}` | searches | Update Search | |
| [ ] | DELETE | `/api/searches/{search_id}` | searches | Delete Search | |
| [ ] | POST | `/api/searches/{search_id}/run` | searches | Trigger Search | |
| [ ] | POST | `/api/searches/{search_id}/test` | searches | Test Search | |
| [ ] | GET | `/api/settings` | settings | Get Settings | |
| [ ] | PATCH | `/api/settings` | settings | Update Settings | |
| [ ] | GET | `/api/settings/defaults` | settings | Get Defaults | |
| [ ] | GET | `/api/stats` | stats | Dashboard statistics | |
| [ ] | GET | `/api/stats/llm-costs` | stats | LLM cost + cache hit stats | |
| [ ] | GET | `/api/stats/sankey` | stats | Application flow data for Sankey diagram | |
| [ ] | GET | `/api/stats/score-distribution` | stats | Resume score distribution | |
| [ ] | GET | `/api/stats/timeline` | stats | Job discovery timeline | |
| [ ] | POST | `/api/telegram/digest` | triggers | Send Telegram digest | |
| [ ] | POST | `/api/telegram/register-webhook` | telegram | Register Telegram webhook | |
| [ ] | POST | `/api/telegram/rotate-webhook-secret` | telegram | Rotate Telegram webhook secret | |
| [ ] | POST | `/api/telegram/test` | telegram | Send test message | |
| [ ] | POST | `/api/telegram/webhook` | telegram | Telegram webhook | |
| [ ] | GET | `/cv/{token}` | tracer | Tracer link redirect (path style) | |
| [ ] | GET | `/health` | system | Health check | |
