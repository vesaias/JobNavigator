# Stage 5 — Cross-cutting
Run 2026-09-02 on the real DB after the rebuild. Script `stage5.py`; raw `artifacts/stage5_part1.json`.

## Counts that must agree — all agree
| Number | Rail | Screen header | API | Stats |
|---|---|---|---|---|
| Jobs (new) | 9 | Feed "0 arrived today · 0 not yet scored" (`/jobs/feed-stats`) | `/jobs?status=new` total 9 | `new_jobs` 9 |
| Applications | 377 | "377 applications · 0 in interview · 0 offer · 25 waiting >7d" | 377 | `total_applications` 377 · "30 in play" = 30 applied |
| Companies | 126 | "126 tracked · 61 active · 1 need attention" | 126 / 61 active | — |
| Searches | 6 | "6 configs · 4 active · 1 need attention" | 6 | — |
| Cover letters | 16 | "16 letters · 1 live application" | 16 | — |
| Résumés (bases) | 4 | "4 bases · 49 tailored copies · 296 archived" | 4 (`is_base=true`) / 349 total | — |
Known disagreement, already logged: Feed header "18943 open roles" and "40 shown · 18943 matching" = every job including skipped/ignored (FEED-01); Stats "TOTAL JOBS 18,943" is the same number under an honest label.

## Background-job lifecycle (company scrape on a ZZTEST company, public Greenhouse board)
- `POST /scrape/company/{id}` → 202 `{run_id, status: running}`; immediate second POST → **409** "company_scrape is already running".
- `/monitor/active` lists `company_scrape` (its `target`/`company` fields are null — the UI must match by name; P4, see below).
- Companies screen shows the running state; navigating Feed → Companies keeps it (UI re-derives from `/monitor/active` on mount).
- Backend restarted mid-run (SIGTERM to uvicorn): healthy in 3 s; `/monitor/history` top row `company_scrape · failed · "Process restarted"`; `/monitor/active` empty; no partial jobs were written (0 ZZTEST jobs). Scratch company deleted.

## Overnight scheduler activity (explains jobs 19012 → 18943 since the baseline dump)
`job_cleanup 04:15 — "69 skipped jobs deleted (>180d old)"`, `auto_reject 04:00 — 0`, `db_backup 03:00 — 82 MB snapshot`, `email_check` every ~3 h. Normal behaviour; the final restore from the baseline dump reinstates the 69 rows.

## Deep links to missing ids — covered
Empty-DB sweep (Stage 3b) + F-007: `?job=<missing>` → feed renders, 404 logged, no crash (FEED-09 notes the real-DB case picks a different job); `/v2/resumes/<missing>` → silent redirect to the shelf (RES report); `/v2/cover-letters/<missing>` → "Could not load this letter." without a back link (CL report); `?job=abc` → 404 handled.

## Toasts, keyboard shortcuts, narrow viewports — covered in Stage 3
Error toasts persist (7.2 s check in the lab; every load-failure site re-verified after the rebuild). Feed shortcuts j/k/s/x/a/e/r verified (FEED report; `o` listed but unhandled, `f`/`g` handled but unlisted). Every screen had a 1024×700 pass: Feed filter bar now wraps (FEED-03 fixed), Applications notes column collapses to 26 px (APPS-09 open), Cover Letters Download button off-screen below ~1090 px (CL report), Searches/Companies/Settings no overflow.

## New findings
### X-01 · P4 · `/api/monitor/active` entries carry no target id for company scrapes
**Where** `backend/job_monitor.py` running-state dict (`target_id`/`company_id` null for `company_scrape`)
**Actual** `[["company_scrape", null, null]]` while a specific company was scraping — the Companies screen must infer "scraping now" by name/time.
**Proposed fix** Populate `target_id` with the company id in `launch_background` for company scrapes (résumé jobs already carry `(resume_id, target_job_id)`).
**Status** fixed (cf50554): `RunningJob.company_id` threaded through `tracked_run`/`launch_background`, serialised by `/monitor/active`; Companies keys its run map on `company_id` with `scope_key` fallback; 2 tests added (604 total). Verified live: a manual Anthropic scrape showed `{"job_type": "company_scrape", "company_id": "6f9e…"}` matching the company row.
