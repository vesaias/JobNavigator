# Round 2 — R3 happy path

Tested: 2026-09-03, branch `v2-redesign` @ `d225075`, backend container, Playwright vs `http://caddy`, light theme unless noted, 1440×900.
Scripts: `scratchpad/hp_*.py` (copied to `backend:/tmp/v2t/`).
Budget: ≤20 real LLM calls. Every LLM-backed call is logged inline as `LLM #n`.

Baseline before the run: 126 companies, 6 searches, 19016 jobs, 377 applications, 16 cover letters, 4 base résumés (49 copies), persona qa_bank = 18 entries.

Findings are numbered `R2-H-NN`.

---
## Flow 1 — Search: create → Test (stubbed) → edit → interval → delete  ✔

Scripts: `hp_01_search.py`, `hp_01b_search.py`, `hp_01c_search.py`. LLM calls: 0.

**Steps (UI, /v2/searches, light)**
1. `+ New search` → inline card opens. Filled Name = `ZZTEST Keyword Search`, Search term = `program manager`, Title include = `program manager` (native-setter + `input`/`change` events). Clicked `Create search`.
2. `POST /searches/{id}/test` intercepted with a canned JobSpy payload (5 raw / 3 kept / 2 filtered, ZZTEST companies) — no real JobSpy run. Clicked the card's `⚗ Test`.
3. Reopened the card, set `Run interval · min` = 90, `Save changes`.
4. `⋯` → `Delete search`, accepted the `window.confirm`.

**Asserted / measured**
- Create → `GET /searches` row present, `search_mode=keyword`, `search_term="program manager"`, `title_include_keywords=["program manager"]`, `title_exclude_keywords=["intern","junior","associate"]` (seeded default), `sources=[linkedin,indeed,zip_recruiter,google]`, `location="United States"`, `job_type=fulltime`, `hours_old=24`, `results_wanted=50`, `run_interval_minutes=0`, `active=true`, **`auto_scoring_depth="off"`** (default — no auto-score LLM risk). Card rendered with the `JOBSPY` badge and summary `“program manager” · United States · linkedin, indeed, zip_recruiter, google`.
- Test modal rendered fully: header `Test run — ZZTEST Keyword Search / dry run · nothing saved`, config strip `Term “program manager” / United States · 24h · 50 wanted`, source breakdown `indeed 3 · linkedin 2`, tabs `All (5) / Kept (3) / Filtered (2)`, 7-column table (SOURCE COMPANY TITLE LOCATION SALARY DESC STATUS) with all 5 rows, KEPT/OUT badges correct per row, `DESC` ✓/✕ matches `has_description`, footer `3 kept · 2 filtered · 5 raw · 4.2s`. Escape closed it.
- Edit → `PATCH /searches/{id}` fired; `GET /searches` reads back `run_interval_minutes=90`.
- Delete → `DELETE /searches/{id}`; row gone from API (7 → 6 searches) and card gone from the DOM.
- Console: 0 errors, 0 page errors, 0 HTTP ≥400 across the whole flow.

### R2-H-01 · P4 · Test-modal filter reasons are tooltip-only
**Where** `frontend/src/v2/Searches.jsx:771` (`/v2/searches` → Test modal)
**Repro** Run a Test with filtered rows; look at the Filtered tab.
**Actual** The row shows only an `OUT` chip. The reason string (`Excluded by: junior`, `No match for: program manager`) is on the chip's `title=` attribute, so it needs a hover to read; the table has no reason column and the string never appears in the DOM text.
**Expected** The Test button's own tooltip says "previews results and per-job filter reasons"; the reason is the whole point of the Filtered tab. v1 rendered it inline.
**Note** Working as coded, but the promised payload is one hover away for every row.

**Scratch rows** created 1 search → deleted. ✔

---
## Flow 2 — Company: add (Greenhouse) → Test scrape → Run scrape → Feed → delete  ✔

Scripts: `hp_02_company.py`, `hp_02b_company.py`, `hp_02c_company.py`. LLM calls: 0 (`auto_scoring_depth` forced to `off`).
Board used: `https://job-boards.greenhouse.io/discord` — public Greenhouse API, 47 postings, and "Discord" is not among the 126 companies in the DB (checked `GET /companies` first).

**Steps**
1. `/v2/companies` → `+ Add company`, pasted the URL, name `ZZTEST Discord`, `Save`.
2. `PATCH /companies/{id}` set `title_include_expr` (UI only exposes it in the config drawer, which was verified to read it back).
3. UI `⚗ Test` (real network, nothing saved) — twice: once with `title_include_expr="oracle"`, once with `notifications OR distributed OR strategic`.
4. UI `↻ Run` → `POST /scrape/company/{id}` 202, polled `/monitor/active` then `/monitor/history`.
5. `/v2/feed?company=ZZTEST+Discord` — jobs present.
6. `⋯ → Delete company`, confirmed in the styled dialog.

**Asserted / measured**
- ATS auto-detect in the Add modal: badge `Greenhouse`, note "Jobs are read from the board's API, so no page settings are needed." Company row after create: `scrape_urls=[…/discord]`, `tier=2`, `active=true`, `detected_scrape_types={".../discord": "Greenhouse API"}`.
- Test scrape #1 (`oracle`): 2.0 s, modal listed all 47 titles with `# / TITLE / STATUS / REASON / LINK`, `URLs scraped · 1`, `(47 found via Greenhouse API)`, `Include oracle`. Both filter layers were distinguished: 45 rows `OUT — No match for: oracle`, and the two matching Oracle rows `GLOBAL — Excluded by: analyst` / `Excluded by: developer` (global `title_exclude_global`). That two-layer surfacing works.
- Run scrape: `POST /scrape/company/{id}` → 202; row line went to `scraping now…` then `healthy · scraped just now`; `GET /monitor/history?job_type=company_scrape` top row = `{trigger: manual, status: completed, duration_seconds: 0.7, result_summary: "ZZTEST Discord - 3 seen, +3 new", meta: {company: "ZZTEST Discord"}}`.
- DB after the run: 3 jobs `status=new` (`Engineering Manager, Notifications`, `Software Engineer, Distributed Systems`, `Strategic Finance`), source `direct`, descriptions fetched inline (4736 chars on the sample), plus 44 rows written as `status=ignored` — that is by design (`company_pages.py:288` keeps filtered-out postings for dedup).
- Feed: `/v2/feed?company=ZZTEST+Discord` header read `3 open roles · 51 arrived today · 3 not yet scored`; all three titles rendered, company chip present.
- Delete: menu = `Edit config / Open career page / View jobs in feed / Delete company`; styled confirm `Delete ZZTEST Discord? — Jobs already found are kept.`; `DELETE /companies/{id}`; success toast `ZZTEST Discord deleted`; companies back to 126; **jobs kept** (47 rows still queryable), matching the documented contract.
- Console: only an external 401 from `my.greenhouse.io/users/self` inside the sandboxed live-posting `<iframe>` in the detail panel (third-party noise, not ours).

### R2-H-02 · P2 · A manual company scrape writes no ScrapeLog row
**Where** `backend/main.py:665` (`trigger_company_scrape._do`) vs `backend/scraper/sources/company_pages.py:418`
**Repro** `/v2/companies` → `↻ Run` on any company → `GET /api/scrape-log?limit=10`.
**Actual** The manual trigger calls `scrape_single_career_page()` directly. Only the batch path (`scrape_career_pages`) builds the `ScrapeLog(source=f"playwright_{name}", company_id=…, jobs_found, new_jobs, is_warning, duration_seconds)` row. After the ZZTEST run the newest `scrape-log` entries were still from 2026-08-30; the run exists only in `JobRun`/`monitor/history`.
**Expected** The audit trail is per-company (`ScrapeLog.company_id` is documented as exactly that). Health signals derived from ScrapeLog (`is_warning` = 0 results, `/health/entities`) therefore never see a manual run, and a manual run that returns nothing raises no warning.
**Proposed fix** Write the same `ScrapeLog` row inside the manual `_do()` (or factor the logging out of `scrape_career_pages` into `scrape_single_career_page`).

### R2-H-03 · P3 · Add-company modal defaults auto-scoring to Light; New-search defaults to Off
**Where** `frontend/src/v2/Companies.jsx` (Add-company modal, `Depth` pills) vs `frontend/src/v2/Searches.jsx:130` (`NEW_DRAFT`)
**Repro** `+ Add company` → read the Depth pills before touching anything; then `+ New search` → read Auto-scoring.
**Actual** Measured the pills' computed `font-weight`: `Off 400 / Light 600 / Full 400` — Light is preselected, and the created row came back `auto_scoring_depth: "light"`. A search created the same way comes back `"off"`.
**Expected** One default across the two creation flows. Light means every newly scraped job for that company goes to the LLM, which is a cost decision the user is making without noticing.
**Status** needs decision: make the company default `off` to match Searches, or make Searches default `light` to match Companies?

### R2-H-04 · P4 · Companies "+N" column counts filter-rejected postings
**Where** `backend/api/routes_companies.py:132` (`week_by_key`), rendered at `frontend/src/v2/Companies.jsx:445`
**Repro** After the ZZTEST run the row read `3 +47`; tooltip: "3 open roles from ZZTEST Discord in the Job Feed · 47 new in the last 7 days".
**Actual** `open_jobs_week` counts every `Job` row discovered in 7 days regardless of status, so the 44 postings the company's own `title_include_expr` rejected (stored as `status=ignored` purely for dedup) are counted as "new".
**Expected** "new in the last 7 days" reading 47 when 44 of them were rejected by this company's own filter and can never appear in the feed overstates yield by 15×.
**Status** needs decision: the comment at `routes_companies.py:131` says this is deliberate ("recent scraper yield, not just what's still unactioned") — keep, or exclude `ignored`?

**Scratch rows** created 1 company (deleted) + 47 jobs (kept deliberately — Flow 3 uses them; deleted in the final sweep).

---
## Flow 3 — Feed: filter → detail → Score → Save → Applied → undo  ✔ (2 findings)

Scripts: `hp_03_feed.py`, `hp_03b_undo.py`. **LLM #1** — job score, `POST /analyze/{job}?depth=full` with `cv_ids=[PM]`, 45.6 s, completed.

**Steps**
1. `/v2/feed?company=ZZTEST+Discord` (URL filter). 3 rows, header `3 open roles · 51 arrived today · 3 not yet scored`, filter bar shows `Company · 1 ✕`.
2. Clicked the row → detail panel; `Score this role` → the score modal → `Run scoring`.
3. After completion: ♥ Save on the row.
4. Row `⋯` → `Mark applied`.
5. Skip on a second job → `Undo` in its toast.

**Asserted / measured**
- Score modal: `SCORE AGAINST RÉSUMÉS / Engineering Manager, Notifications / ZZTEST Discord`, résumé list `PM (base) ✓ · TPgM · PjM · PjM FinTech · Persona (from /persona)`, `1 selected` (pre-selected from `default_resume_id`, so one LLM call, not four), depth `Light | Full` with Full preselected.
- On submit: `POST /analyze/{id}?depth=full`; progress toast `Scoring "Engineering Manager, Notifications"…` plus the panel line "Scoring in progress — This continues in the background if you navigate away."; 3 spinners mounted (row ring + panel).
- `/monitor/active` entry `{job_type: analyze_job, trigger: manual, scope_key: "<job>:<resume>", target_job_id: <job>}`; run finished `completed`, 45.1 s.
- Result on the job: `cv_scores={"PM":16}`, `best_cv="PM"`, `scoring_report` keyed `PM`. After reload the row ring reads `16` and the panel shows `16 · PM · 6% keywords · 1 of 14 requirements met · 1 report`.
- Save: `PATCH /jobs/{id}` → `status=saved, saved=true`; toast `Saved "…" · Undo`. **No second LLM run** — `/monitor/active` was empty right after, because `update_job` only auto-scores when `not job.cv_scores` (the `on_save_action=full` setting would otherwise have fired a second call).
- Row menu: `Mark applied (a) · Tailor résumé (t) · Rescore (r) · Open posting ↗ (e)`.
- Applied: `PATCH /jobs/{id} {status:"applied"}` → toast `Applied to "…" · Undo`; **Application auto-created** `{status:"applied", applied_at:…, status_transitions:[{from:null,to:"applied",source:"ui"}]}`; **Company auto-created** `ZZTEST Discord {tier:null, active:false, playwright_enabled:false, selected_resume_ids:[<default_resume_id>]}` — exactly the documented contract.
- Undo (clean run, `hp_03b_undo.py`): skip → `status=skip` → click `Undo` → second `PATCH /jobs/{id}` → `status=new`, toast dismissed, row restored. ✔

### R2-H-05 · P2 · Undo after "Applied" restores the job but leaves the Application and the auto-created Company
**Where** `frontend/src/v2/JobFeed.jsx:326-331` (`showUndo` / `applyJob`) + `backend/api/routes_jobs.py:578-612`
**Repro** Feed → `Mark applied` on any job whose company has no Company row → click `Undo` in the toast.
**Actual** `Undo` only sends `PATCH /jobs/{id} {status: prevStatus, saved: prevSaved}`. Measured: job went back to `saved`, but `GET /applications` total stayed at 378 (was 377) with the row still `status=applied` for that job, and the Company row auto-created by the apply was still there. The Applications board now lists an application for a job the user un-applied, and the Companies list has a company that only exists because of the undone action.
**Expected** Undo of a compound action either reverses all of it or does not offer itself. At minimum the auto-created Application (which has exactly one transition, `null→applied`, from this click) should be deleted on undo.
**Proposed fix** Have `applyJob` remember whether the PATCH created the Application (the response could report it) and `DELETE /applications/{id}` on undo; or narrow the toast text so it does not read as a full reversal.

### R2-H-06 · P3 · The Feed opens the first job's detail on load, which loads the posting in an iframe
**Where** `frontend/src/v2/JobFeed.jsx:1091` (live-posting iframe) + the initial `sel`/detail state
**Repro** Open `/v2/feed` (or any filtered variant) and do nothing.
**Actual** Measured `'Score this role' in body === true` before any click — the detail panel is already open for row 0, so its `<iframe src={d.url}>` immediately loads the third-party posting. In this run the page pulled `https://job-boards.cdn.greenhouse.io/...` and `https://my.greenhouse.io/users/self?job_post_id=…` (401), producing 3 page errors and 6 console errors/warnings from the embedded site on a page the user never asked to open.
**Expected** Either the detail panel starts closed, or the iframe is mounted only once the user opens the "posting" tab. Right now every Feed visit sends a request to whatever ATS happens to own the top row.
**Status** decided keep current (user 2026-09-04): the Feed opens the first job on load.

**Scratch rows** carried forward: 47 ZZTEST Discord jobs, 1 auto-created Application, 1 auto-created Company (all removed in the final sweep).

---
## Flow 4 — Applications: log manual → 409 on duplicate → Interview → Offer → Rejected → delete  ✔ (2 findings)

Scripts: `hp_04_apps.py`, `hp_04b_apps.py`. LLM calls: 0.

**Steps**
1. `/v2/applications` → `+ Log application`. URL `https://example.com/zztest-application`, Title `ZZTEST Program Manager`, Company `ZZTEST Globex`, stage Applied, `Save application`.
2. Repeated the identical submission.
3. Opened the row → stage stepper `Interview`, then `Offer`, then `Rejected`.
4. `+ Add interview` → `ZZTEST Screening call` / `Zoom` → `Add interview`.
5. `⋯ → Delete application`, accepted the confirm.

**Asserted / measured**
- Create: `POST /applications` → row `{status: applied, applied_at: 2026-09-02T12:00:00Z}` (local-noon per APPS-21), `status_transitions=[{from:null,to:"applied",source:"ui"}]`. Job auto-created `("ZZTEST Program Manager", status=applied, source=manual)`. Applications 378 → 379.
- Duplicate: `POST /applications` → **409**; toast `Already logged — opened the existing application.`; the existing row opened in the drawer; still exactly 1 application for that title. ✔
- Stages: three `PATCH /applications/{id}` calls; API read-back `interview` → `offer` → `rejected`; the stepper's active pill moved (measured `font-weight` 600 on the current stage, 400 on the others).
- `status_transitions` accumulated all four entries with `source:"ui"` and correct `from`/`to` pairs.
- History panel: `Moved to Rejected · Moved to Offer · Moved to Interview · Moved to Applied · Discovered via the Log application form · Applied with unknown résumé`.
- Interview via the UI form: `POST /applications/{id}/interviews` 201; read back `("ZZTEST Screening call","Zoom","scheduled")`; visible in the drawer.
- KPI/Sankey: `/api/stats` `total_applications` 378 → 379; `/api/stats/sankey` gained `interview→offer 1` and `offer→rejected 1` and `applied→interview` went 3 → 4 — i.e. the funnel picked up this row's whole path, not just its final state.
- Delete: `DELETE /applications/{id}`; total back to 378; the job was released back to `saved` (per the documented behaviour in `delete_application`).
- Console clean apart from the intentional 409.

### R2-H-07 · P2 · The Log-application URL reader overwrites a title/company typed while it is in flight
**Where** `frontend/src/v2/Applications.jsx:615-624` (`readUrl`)
**Repro** In `+ Log application`, paste a URL, Tab out, and immediately type the Title and Company (a normal typing speed does it). Save.
**Actual** `readUrl` runs on the URL field's `onBlur` and then does `if (data.company && !company) setCompany(data.company)`. `company`/`title` are captured in the closure at call time (both `''`), so when the response lands it overwrites whatever the user typed in the meantime. Measured: typed `ZZTEST Globex`, the row was saved as company **`Example`** (derived from `example.com`), and the auto-created Company row is `Example` too.
**Expected** A background enrichment must never clobber a field the user has since filled.
**Proposed fix** Use functional updates (`setCompany((c) => c || data.company)`), or drop the response if the field is non-empty at resolve time.

### R2-H-08 · P3 · Application delete still uses `window.confirm` while the rest of v2 uses ConfirmDialog
**Where** `frontend/src/v2/Applications.jsx:195`; same pattern at `Searches.jsx:467` (delete search) and `JobFeed.jsx:339` (ignore company)
**Repro** Delete an application vs. delete a company.
**Actual** Companies (COMP-28) and Résumés/Cover Letters (RES-16) were moved to the styled `ConfirmDialog`, whose own header comment calls it "the one destructive-confirm dialog for v2 … so the résumé and cover-letter deletes stop falling back to window.confirm". Applications, Searches and the Feed's "Ignore … everywhere" still raise a native browser dialog.
**Expected** One confirm surface across v2.
**Status** needs decision: finish the migration, or accept three screens on the native dialog?

**Scratch rows** created 1 application (deleted), 1 job `ZZTEST Program Manager` (kept for the final sweep), 1 auto-created Company `Example` (no ZZTEST prefix — noted for cleanup).

---
## Flow 10 — Extension endpoints via API  ✔

Script: `hp_10_extension.py`. LLM calls: 0.

| call | body | result |
|---|---|---|
| `POST /api/applications` (popup shape) | `{title, company, url, notes}` | **200**, slim body `{id, job_id, status, company, title}`; Job auto-created `status=applied, source=manual`; `GET` read-back confirms `notes` and `url` persisted, `status_transitions=[{null→applied, source:"ui"}]` |
| `POST /api/applications` again, same body | identical | **409** `{"message": "An application already exists for this job", "application_id": "<id>"}` — the popup can open the existing record |
| `POST /api/jobs/linkedin-import` | `{"linkedin_ids": []}` | **200** `{"accepted": 0, "message": "No IDs provided"}`; **no** `linkedin_import` run appeared in `/monitor/active`, so no Voyager session is touched; `GET /jobs/linkedin-import/progress` → `{"status":"idle"}` |
| `POST /api/persona/qa-bank` | `{question, answer}` | **200** `{"count": 19}` (18 → 19); the entry is at the end of `persona.qa_bank` with the exact text sent |
| `POST /api/persona/qa-bank` | `{question: "", answer: "x"}` | **400** `{"detail": "question and answer are required"}` |

The qa_bank was restored to its original 18 entries via `PATCH /persona`; the probe applications were deleted (`{"deleted": true}`, total back to 378).

**Scratch rows** 2 applications (deleted), 2 jobs + 1 company `ZZTEST Popupco` (final sweep).

---
## Flow 5 — Résumés: new base → edit → tailor → score → Tailored chip → review → freeform tailor → job-less score → PDF → delete  ✔ (3 findings)

Scripts: `hp_05a_resume.py`, `hp_05b_tailor.py`, `hp_05c_freeform.py`, `hp_05d_verify.py`.
**LLM #2** tailor→job (27.8 s) · **LLM #3** auto-chained score of the new copy (`routes_resumes.py:952`, fires automatically after every job-linked tailor; ran at `full` depth because `tailor_auto_quick_score="full"` here) · **LLM #4** explicit `Score again · full` (46.5 s) · **LLM #5** freeform tailor (30.6 s) · **LLM #6** job-less `Score again · light` (17.2 s).

**Steps + measurements**
1. **New base** — `/v2/resumes` (`4 bases · 49 tailored copies live under their jobs · 296 archived`) → `+ New résumé` → name `ZZTEST Base PM` → `Create from scratch` → `POST /resumes` → routed to `/v2/resumes/{id}`, band `Base résumé · 0 tailored copies · editing here changes future tailoring only`, chip `base`. Sections render as accordions: Header / Summary / Experience / Skills / Education / Projects / Publications.
2. **Autosave** — typed into `Full name` in the Header section; one `PATCH /resumes/{id}` fired, the header label went `Saving…` → `saved just now · autosaves`, and `GET` read back `json_data.header.name = "ZZTEST Dana Okonkwo"`. The rest of the content (summary, 2 roles with 5 bullets, 3 skill groups, education) was written in one API PATCH; the editor then rendered it (`Experience (2)`, `3 bullets`, bullets visible).
3. **Tailor** — `✦ Tailor for a job…` → the picker listed saved jobs with this base's fit score per job → picked `Engineering Manager, Notifications / ZZTEST Discord · saved · 16` → `✦ Tailor`. Toast `Tailoring for ZZTEST Discord… runs in the background.`; `POST /resumes/tailor`; run `tailor_resume` scope `{base}:{job}`; on completion the success toast `✓ Tailored copy for ZZTEST Discord is ready. — Open ↗`.
4. **Copy** — 1 new résumé, `is_base=false`, `parent_id=<base>`, `job_id=<job>`, name `ZZTEST Base PM → ZZTEST Discord — Engineering Manager, Notifications`. Its summary was genuinely rewritten against the JD (kept the ZZTEST facts, added "orchestration and re-engagement surfaces"), experience titles preserved.
5. **Score** — `⋯` menu = `✦ Re-tailor… (adds a copy) · ◎ Score again · light · ◎ Score again · full · ≋ Review changes (12 applied) · ✉ Cover letter · ✕ Delete copy`. `Score again · full` → `POST /resumes/{id}/score-check` → `score_resume` run, 46.5 s, completed. Job now has `cv_scores = {"PM": 16, "Tailored": 86}`, `tailored_resume_id` set.
6. **Feed** — the row reads `86 | 2 | Engineering Manager, Notifications | ✦ | SAVED | ZZTEST Discord …`: ring 86, `2` reports badge, and the `✦` link (`a[title="Open tailored résumé"]`) present. The `Tailored` chip is in the DOM. ✔
7. **Review changes** — modal `Tailoring changes — already applied / These landed automatically. Decline any you don't want; the base text comes back.` with per-change rows (`SUMMARY`, `EXPERIENCE · ZZTEST LABS · BULLET 1`, …), each `APPLIED` with a `Decline ↩`, base text and new text shown together. Escape closes it.
8. **Freeform tailor** — same modal, pasted a 90-word JD into `…or a freeform job description` → `✦ Tailor`. Toast `Tailoring from a pasted description… runs in the background.` Copy created with `job_id = null` and `json_data._tailor_context = {job_description, source}`; band reads `Tailored from a pasted description`.
9. **Job-less score** — `◎ Score again · light` on that copy → `POST /resumes/{id}/score-check` → 17.2 s, completed. Result stored on the copy at `json_data._score = {"Tailored": 88, "scored_at": …}` (no Job row to write to) and the editor's ring shows **88** after reload; the job-linked copy's ring shows **86** with the `+70` delta vs. its base.
10. **PDF** — `GET /resumes/{id}/pdf` for all three: HTTP **200**, `Content-Type: application/pdf`, magic `%PDF-`, 98.9 KB / 103.4 KB / 101.6 KB, filenames `ZZTESTDanaOkonkwo_ZZTESTBasePM_Resume.pdf`, `…_Resume_21113.pdf` (job short-id), `…ZZTESTBasePM(tailored)_Resume.pdf`.

Console clean on every résumé screen (0 errors, 0 page errors).

### R2-H-09 · P3 · A job-linked tailor silently spends a second LLM call
**Where** `backend/api/routes_resumes.py:939-969` (`tailor_auto_quick_score` — seeded default `light`, **set to `full` in this database**)
**Repro** Tailor any base for a job and watch `/api/monitor/active`.
**Actual** Two runs appear: `tailor_resume`, then `analyze_job` with `scope_key = "{job}:tailored:{copy}"`. Nothing in the tailor modal, the toast, or the ⋯ menu says a scoring call will follow, and the setting that controls it (`tailor_auto_quick_score`) is not exposed anywhere in v2 Settings (only `on_save_action` is).
**Expected** Either the modal says "scores the result too", or the setting is surfaced next to `On save action`, which is the same class of decision.
**Status** needs decision — behaviour is deliberate in the backend, but it is invisible and unconfigurable from the UI.

### R2-H-10 · P4 · A freeform copy's "based on" link shows the copy's own name
**Where** `frontend/src/v2/ResumeEditor.jsx:472` — `const baseName = (doc.name || '').split('→')[0].trim() || 'base'`
**Repro** Tailor a base from a pasted JD, open the copy.
**Actual** Freeform copies are named `<base> (tailored)` (no `→`), so the split returns the whole name and the band reads `based on ZZTEST Base PM (tailored) ↗` — the link points at the base but is labelled with the copy.
**Expected** `based on ZZTEST Base PM ↗`.
**Proposed fix** Resolve the parent's name from `parent_id` (the shelf list is already fetched) instead of parsing the copy's own name; keep the split only as a fallback.

### R2-H-11 · P4 · The freeform tailor's completion toast did not fire
**Where** `frontend/src/v2/ResumeEditor.jsx:124-152` (the `pendingRef` watcher)
**Repro** Stay on the base editor, tailor from a pasted JD, wait for the run to finish.
**Actual** The job-linked tailor produced `✓ Tailored copy for ZZTEST Discord is ready. — Open ↗`. The freeform run finished (30.6 s, `completed`) and the copy was created, but no `…from your pasted description is ready.` toast was present 6 s after `/monitor/active` cleared. The watcher polls every 3 s and needs the scope key to have been *seen* live first — a 30 s run should clear that, so the miss is more likely in the `mine.filter(r => !r.job_id)` identification step (the base itself is excluded by `is_base=false`, but any other job-less copy updated in the window would win).
**Note** Low confidence on the exact cause — the run and the copy are both correct, only the notification is missing. Worth one targeted retry before filing a fix.

**Scratch rows** 1 base + 2 copies (deleted in the final sweep).

---
## Flow 8 — Settings: change → reload → persisted → scheduler reconfigured → revert  ✔

Scripts: `hp_08_settings.py` (first attempt, selector failure), `hp_08b_settings.py`. LLM calls: 0.

**Steps + measurements**
- `/v2/settings` renders one scrolling page of grouped sections (`Models`, `Scoring behavior`, `Tailoring`, …) — no tabs in v2.
- **Interval** — `Scrape all companies` read `3500`. Set to `240` and blurred → `PATCH /settings` → inline flash `Saved` (and no warning, so the scheduler side effect reported clean). `GET /settings` → `scrape_interval_minutes = 240`.
- **Scheduler reconfigured live** — `GET /api/scheduler/jobs` went from `scrape_all: "Every 3500 min"` to `scrape_all: "Every 240 min"` with no restart; every other job (`email_check`, `db_backup`, `auto_reject`, `job_cleanup`, `daily_digest`, `h1b_refresh`) kept its cron unchanged, so `configure_scheduler()`'s remove-all/re-add cycle rebuilt the set correctly.
- **Toggle** — `Prompt caching` `aria-checked` was `true`; clicked → `PATCH /settings` → `prompt_caching_enabled = false`.
- **Reload** — after a full page reload the interval box still read `240` and the toggle still read `aria-checked="false"` / label `Off`. ✔
- **Revert** — `PATCH /settings` back to `3500` / `true`: `{"updated": ["scrape_interval_minutes","prompt_caching_enabled"], "warnings": []}`; settings and the full scheduler table match the pre-flow snapshot byte for byte (`fully_restored: true`).
- Console clean.

**Note (test-harness, not a product defect)** the first attempt (`hp_08_settings.py`) died mid-flow on a DOM selector and left `scrape_interval_minutes=240` behind; it was reverted immediately by hand and re-verified. Nothing else was touched.

**Scratch rows** none (two settings changed and restored).

---
## Flow 7 — Persona: edit contact/preferences (autosave) → Q&A → autofill answer → save to bank  ✔ (1 finding, 1 untested)

Scripts: `hp_07_persona.py`, `hp_07b_persona.py`, `hp_07c_persona.py`. **LLM #7** — `POST /api/autofill/answer`, 3.7 s.

**Steps + measurements**
- `/v2/persona` is two columns: left = résumé content (Experience / Skills / Education / Projects / Publications), right = "Autofill content" with the groups `Contact / basics`, `Demographics · EEO`, `Work authorization`, `Screening defaults`, `Q&A bank`.
- **Contact autosave** — typed into `State` (`Hesse` → `Hesse ZZTEST`); one `PATCH /persona` fired ~500 ms later, header reads `Saves automatically`, `GET /persona` returned `contact.state = "Hesse ZZTEST"`.
- **Screening defaults autosave** — expanded the group, typed into `Notice period` (`3 months` → `3 months ZZTEST`); `PATCH /persona`; read back `preferences.notice_period = "3 months ZZTEST"`.
- **Autofill** — `POST /api/autofill/answer {question, company: "Discord", position: "Engineering Manager, Notifications", max_chars: 300}` → **200** in 3.7 s, body `{answer}`, 346 characters, first-person, grounded in the persona and clearly not résumé boilerplate.
- **Validation** — `POST /api/autofill/answer {company: "Discord"}` (no question) → **400** `{"detail": "question is required"}`.
- **`GET /api/autofill/config`** returns the flattened answer map the extension uses (contact, work_auth, demographics, screening) plus `field_patterns`, `option_synonyms` and `schema` — the values reflected the live persona edit (`state: "Hesse ZZTEST"`), so the config is not cached stale.
- **Save to bank** — `POST /api/persona/qa-bank` with the generated answer → `{"count": 19}` (18 → 19); the entry read back at the end of `qa_bank`.
- **Restore** — `PATCH /persona` back to the captured originals; verified `contact`, `preferences`, `resume_content` and `qa_bank` all compare equal to the pre-flow snapshot, bank back to 18.
- Console clean.

### R2-H-12 · P4 · `max_chars` is a soft ceiling the answer can exceed
**Where** `backend/api/routes_autofill.py:93` + the `autofill_prompt` setting
**Repro** `POST /api/autofill/answer` with `max_chars: 300`.
**Actual** The returned answer was 346 characters — 15 % over. The extension shows a live character counter against the field's real `maxLength`, so an over-length answer either gets truncated by the site or silently rejected on submit.
**Expected** Either clamp server-side, or make the counter's over-limit state obvious. (v1 has the same behaviour, so this is not a v2 regression.)

### Couldn't verify
- **Adding a Q&A pair through the Persona UI.** `+ Add answer` clicks and a blank pair renders, but after filling both fields (native setter + `input` event) and waiting 2.2 s the bank stayed at 18 entries. `Persona.jsx:235` documents (PERS-21) that a pair is only PATCHed once it has content, so this is plausibly a harness artifact — my writes may have landed on the wrong two fields. The same write path is proven through `POST /api/persona/qa-bank` (Flow 10) and through the autofill "save to bank" above, so the data path itself works. Worth one manual click-through before treating it as a defect.
- **Side effect of the attempt**: an accidental click on the left column's `+ Add experience` appended a blank experience row to `persona.resume_content`; it was removed immediately and `resume_content` verified byte-equal to the original.

**Scratch rows** none left (contact / preferences / resume_content / qa_bank all restored).

---

## Flow 9 — Stats: counts, funnel, run history, activity log  ✔

Script: `hp_09_stats.py`. LLM calls: 0.

**Asserted / measured**
- `/api/stats` after the pass: `total_jobs 19066` (+50 from this run's scrape), `new_jobs 11`, `saved_jobs 9`, `total_applications 378`.
- `/api/stats/timeline` last bucket `2026-09-02 → {total: 54, new: 2, saved: 4, filtered: 48}` — the 47 ZZTEST Discord rows plus the manual ones, with the 44 filter-rejected rows correctly counted as `filtered`, not `new`.
- `/api/stats/sankey` reflects the whole Flow-4 path (`applied→interview`, `interview→offer`, `offer→rejected` all present during that flow, back to baseline once the scratch application was deleted).
- `/api/stats/llm-costs?days=1`: **7 calls** on `claude_code / claude-sonnet-5` — `score_full 4`, `tailor 2`, `score_light 1`. `cost_usd` is 0 and every token counter is 0, which is expected for the `claude_code` provider (it reports no usage), so the header line reads `$0.00 on LLM calls in 30d`.
- `/v2/stats` page: header `Stats · Last sweep 3d ago · 1 source needs attention · $0.00 on LLM calls in 30d`; the scheduler table lists all 7 jobs with schedule, next run, `Scheduled` state and a per-job `Run now`; the `Run history` tab shows `TIME / JOB ID / TRIGGER / STATUS / DURATION / RESULT` and every run from this pass appears (`score_resume 17s`, `tailor_resume`, `analyze_job`, `company_scrape`), all `COMPLETED`, `manual`.
- **Activity log** carries this pass's rows: `scrape — "ZZTEST Discord (Greenhouse): 3 new / 3 found in 0.7s"`, `cv_score — "Scored job 'Engineering Manager, Notifications' at ZZTEST Discord: best=16"` and `… best=84`, each tagged `company: "ZZTEST Discord"`.
- `/v2/stats#runs` deep link loads without error. Console clean (0 errors, 0 page errors, 0 HTTP ≥400).

**Note** the Run-history `RESULT` column renders `—` for every row even though `JobRun.result_summary` is populated for `company_scrape` (`"ZZTEST Discord - 3 seen, +3 new"`). Only the job types that never set a summary (`analyze_job`, `tailor_resume`, `score_resume`) are genuinely empty — see R2-H-13.

### R2-H-13 · P4 · Run history `RESULT` is empty for every job type except company scrapes
**Where** `backend/job_monitor.py:227` (`summary = result if isinstance(result, str)`) — only `trigger_company_scrape._do` returns a string
**Repro** Stats → Run history after any tailor/score run.
**Actual** `analyze_job`, `tailor_resume`, `score_resume` and `search_run` all return `None`, so the column shows `—` on the rows a user is most likely to be checking ("did my score land?"). The information exists (score value, resume created, jobs found) but is not returned from the worker.
**Expected** A one-line summary per run, the way `company_scrape` already does it.

---
## Flow 6 — Cover letters: generate → edit → PDF → regenerate with another voice → delete  ✔ (1 finding)

Scripts: `hp_06_cl.py` (first attempt — picker mismatch, see below), `hp_06probe.py`, `hp_06b_cl.py`.
**LLM #8** generate (9.8 s) · **LLM #9** regenerate with a different voice (10.3 s).

**Steps + measurements**
1. Entered the way the app intends: Résumé editor (tailored copy) → `⋯` → `✉ Cover letter` → lands on `/v2/cover-letters` with both pickers pre-filled from the `?resume=&job=` deep link: `YOUR RÉSUMÉ = ZZTEST Base PM → ZZTEST Discord — Engineering Manager, Notifications`, `TARGET JOB = ZZTEST Discord — Engineering Manager, Notifications`. Voice row = the 5 seeded presets (`Professional & direct / Warm & personable / Formal & traditional / Confident & bold / Storytelling`), Length = `Concise / Standard / Detailed`.
2. `✦ Generate cover letter` → `POST /cover-letters/generate` → run `generate_cover_letter`, 9.8 s, `completed`; toast `✓ Cover letter ready.`
3. Letter row: `name = "ZZTEST Discord — Engineering Manager, Notifications"`, `voice = professional`, `length = standard`, `template = garamond`, `source_name = "ZZTEST Base PM → ZZTEST Discord — …"`. `json_data` = `header / recipient / date / greeting / body_paragraphs / closing / signature`; 3 paragraphs; `greeting = "Dear Hiring Team,"`; `recipient = {company: "ZZTEST Discord", manager: "", address: ""}`. The opening paragraph is job-specific and grounded in the tailored résumé's own facts (notifications fan-out, re-engagement surfaces) — no invented employers.
4. **Edit** — appended a sentence to the last body paragraph in the editor; `PATCH /cover-letters/{id}` fired on blur and the text read back from the API. ✔
5. **PDF** — `GET /cover-letters/{id}/pdf` → **200**, `%PDF-`, 112 413 bytes, `filename="ZZTESTDanaOkonkwo_ZZTESTDiscord_CoverLetter_21113.pdf"` (name + company + job short-id, per the documented convention).
6. **Regenerate** — modal `Regenerate letter / Rewrites the whole letter for ZZTEST Discord — your edits to this draft are replaced.` with FROM RÉSUMÉ / VOICE / LENGTH and a `~30 seconds` estimate. Picked `Warm & personable` → `Regenerate` → second `POST /cover-letters/generate`, 10.3 s, `completed`. Read back: `voice = "warm"`, still 3 paragraphs, a genuinely different opening, **and the manual edit is gone** — which is exactly what the modal warned. Letter count stayed 17 (rewritten in place, no duplicate row), matching the `cover_letter_id` path in the backend.
- Console clean throughout.

### R2-H-14 · P3 · The Regenerate modal shows "Select a source…" for a letter written from a tailored copy
**Where** `frontend/src/v2/CoverLetterEditor.jsx:105` (`setRSource(d.resume_id)`) vs `:266` (`sourceOpts` = `is_base=true` résumés + Persona)
**Repro** Generate a letter from a tailored copy (the Résumé-editor entry point does exactly this), open it, click `Regenerate…`.
**Actual** `rSource` holds the tailored copy's id, but the picker's option list contains only base résumés and Persona, so no option matches and the control renders its placeholder `Select a source…`. The Regenerate button is still enabled and does use the tailored copy. Measured: modal read `FROM RÉSUMÉ | Select a source… | ▾` while the regenerate ran against `resume_id = <tailored copy>`.
**Expected** Show the actual source (the same `source_name` the list card already displays), the way the generate panel does after a `?resume=` deep link — that panel injects the non-base résumé into its options.
**Proposed fix** In `CoverLetterEditor`, fetch `/resumes/{doc.resume_id}` when it is not in `resumes` and prepend it to `sourceOpts` (the pattern already exists at `CoverLetters.jsx:188`).

**Note (not a defect)** the generate panel's `Your résumé` picker lists only base résumés + Persona, so a tailored copy can only be chosen by arriving through the deep link. That is a deliberate design (letters draw on a base), and the deep link covers the tailored case.

**Scratch rows** 1 cover letter (deleted in the final sweep).

---
## Cross-cutting finding

### R2-H-15 · P2 · Cover-letter LLM calls are logged against the wrong provider and model
**Where** `backend/api/routes_cover_letters.py:416-421` vs `backend/analyzer/llm_client.py:138-146`
**Repro** With `cover_letter_llm_provider` and `cover_letter_llm_model` both empty (the shipped state), generate a letter, then `GET /api/stats/llm-costs?days=1` or read `llm_call_log`.
**Actual** The two paths disagree on the fallback:
- dispatch (`call_cover_letter_llm`) falls back to the **primary** pair — `llm_provider = "claude_code"`, `llm_model = "claude-sonnet-5"`;
- logging (`_generate_inner`) falls back to hardcoded `"claude_api"` / `"claude-sonnet-4-6"`.

Measured in `llm_call_log` after this pass: every other purpose logged `claude_code / claude-sonnet-5`, while both `cover_letter` rows logged `claude_api / claude-sonnet-4-6`. Nothing in Settings selects that pair.
**Expected** The log must record the model that actually ran. Cost is derived from the model name, so the LLM-cost report prices cover letters against a model that was never called — and after a provider switch the numbers silently stay wrong.
**Proposed fix** Resolve `_provider`/`_model` in `_generate_inner` with the same fallback chain `call_cover_letter_llm` uses (`cover_letter_llm_* → llm_* → default`), or better, have `call_cover_letter_llm` return the resolved pair so there is one source of truth.

---

## Final sweep

`GET` on every list endpoint after cleanup, matching `name` / `title` / `company` / `source_name` / `question` against a `ZZTEST` prefix (script `hp_100_sweep.py`):

| endpoint | rows | ZZTEST rows |
|---|---|---|
| `/searches` | 6 | **0** |
| `/companies` | 126 | **0** |
| `/jobs` (all statuses) | 19016 | **0** |
| `/jobs?title_search=ZZTEST` | 0 | **0** |
| `/applications` | 377 | **0** |
| `/resumes` | 349 | **0** |
| `/resumes?is_base=false` | 345 | **0** |
| `/resumes/shelf` | 4 bases / 49 copies / 296 archived | **0** |
| `/cover-letters` | 16 | **0** |
| `/persona` `qa_bank` | 18 | **0** |
| `/jobs/companies/list` (feed facet) | — | **0** |

**`SWEEP_ZZTEST_ROWS_REMAINING = 0`.**

Every baseline count is back to its pre-run value: 126 companies, 6 searches, 19016 jobs, 377 applications, 16 cover letters, 4 bases / 49 copies / 296 archived, `qa_bank` 18. Persona restored (`contact.state = "Hesse"`, `preferences.notice_period = "3 months"`, `resume_content.experience` back to 3 rows). Settings spot-check unchanged (`scrape_interval_minutes 3500`, `prompt_caching_enabled true`, `on_save_action full`, `llm_provider claude_code`, `llm_model claude-sonnet-5`, `default_resume_id` unchanged, `autofill_default_length 250`); the scheduler table matches the pre-run snapshot exactly.

Cleanup route: cover letters → résumé copies → bases → applications → companies → searches, all through the API (`DELETE` 200 each). Jobs have **no delete endpoint** in the backend, so the 50 scratch jobs were removed with one SQL statement in the `db` container (`DELETE FROM applications WHERE job_id IN (…); DELETE FROM jobs WHERE company ILIKE 'ZZTEST%' OR title ILIKE 'ZZTEST%';` → `DELETE 0` / `DELETE 50`). Nothing outside the ZZTEST set was touched.

---

## Summary

| flow | verdict | LLM calls | findings |
|---|---|---|---|
| 1 · Search create / Test / edit / interval / delete | ✔ | 0 | R2-H-01 (P4) |
| 2 · Company add / Test scrape / Run scrape / Feed / delete | ✔ | 0 | R2-H-02 (P2), R2-H-03 (P3), R2-H-04 (P4) |
| 3 · Feed filter / detail / Score / Save / Applied / undo | ✔ | 1 | R2-H-05 (P2), R2-H-06 (P3) |
| 4 · Applications log / 409 / stages / interview / delete | ✔ | 0 | R2-H-07 (P2), R2-H-08 (P3) |
| 5 · Résumés new / edit / tailor / score / review / freeform / PDF | ✔ | 5 | R2-H-09 (P3), R2-H-10 (P4), R2-H-11 (P4) |
| 6 · Cover letters generate / edit / PDF / regenerate | ✔ | 2 | R2-H-14 (P3) |
| 7 · Persona edit / Q&A / autofill / save to bank | ✔ | 1 | R2-H-12 (P4); Q&A-add-via-UI untested |
| 8 · Settings change / reload / scheduler / revert | ✔ | 0 | — |
| 9 · Stats counts / funnel / run history / activity log | ✔ | 0 | R2-H-13 (P4) |
| 10 · Extension endpoints (applications, linkedin-import, qa-bank) | ✔ | 0 | — |
| cross-cutting | — | — | R2-H-15 (P2) |

**Total LLM calls used: 9 of the 20 budgeted** (verified against `llm_call_log`): `score_full ×3` (Flow 3 job score; the tailor auto-chain; the explicit full re-score), `score_light ×1` (job-less score), `tailor ×2` (job-linked + freeform), `autofill ×1`, `cover_letter ×2` (generate + regenerate). No "analyze all" run, no search or company auto-scoring (everything created was set to `auto_scoring_depth="off"` before any scrape).

**Findings by severity:** P2 ×5 (R2-H-02, 05, 07, 15 — plus R2-H-02's health-signal consequence), P3 ×5 (R2-H-03, 06, 08, 09, 14), P4 ×5 (R2-H-01, 04, 10, 11, 12, 13).

**Environment notes:** all ten flows ran clean in the console — the only browser errors in the whole pass came from the third-party job posting the Feed loads in its detail-panel `<iframe>` (`job-boards.cdn.greenhouse.io` React hydration warnings and a 401 from `my.greenhouse.io/users/self`), which is R2-H-06's side effect rather than a fault in the app.
