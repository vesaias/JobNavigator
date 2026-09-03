# Round 3 — Flow A (the daily loop)

Tested: 2026-09-03, branch `v2-redesign` @ `69d36b1`, Playwright inside the backend container vs `http://caddy`, light theme unless noted, 1440×900.
Scripts: `scratchpad/r3a_*.py` (copied to `backend:/tmp/v2t/`). Screenshots: `v2-testing/artifacts/round3-A/`. Prefix on every created row: **`ZZA`**.
Network: real. Board used `https://job-boards.greenhouse.io/vercel` (88 postings; "Vercel" is neither in `GET /companies` (126) nor in `company_exclude_global` (302) — checked before use).
Findings are numbered `R3-A-NN`.

Baseline before the run: **126 companies, 6 searches, 18843 jobs, 377 applications** (30 applied / 347 rejected), 4 base résumés, rail counts `Jobs 9 · Searches 6 · Companies 126 · Applications 377 · Résumés 4 · Cover Letters 16`.

---
## Step 1 — Company: add → Test scrape → Run scrape → monitor → ScrapeLog → Feed → rail counts

Scripts: `r3a_00_recon.py`, `r3a_01_company.py`, `r3a_02_test.py`, `r3a_03_run.py`, `r3a_04_jobs.py`, `r3a_05_dbcheck.py`, `r3a_06_diff.py`, `r3a_07_probe.py`, `r3a_08_phrase.py`. LLM calls: **0** (`auto_scoring_depth` set to `off` in the Add modal before saving).

**Steps (UI, `/v2/companies`, light)**
1. `+ Add company` → measured the ATS badge **before** typing (`—`), pasted `https://job-boards.greenhouse.io/vercel` → badge flipped to `GREENHOUSE` with the note *"Jobs are read from the board's API, so no page settings are needed."* Name `ZZA Vercel Co`, Depth → `Off`, `Save`.
2. Row → drawer (`Edit config` path via row click) → `Title include` = `manager` → `Save changes`.
3. Row `⚗ Test` (real network, nothing saved).
4. Row `↻ Run` (real scrape) → polled `/monitor/active` on `scope_key`, then `/monitor/history` and `/api/scrape-log`.

**Asserted / measured**
- Create: exactly one `POST /api/companies`. Row read back `{scrape_urls:["https://job-boards.greenhouse.io/vercel"], tier:2, active:true, auto_scoring_depth:"off", detected_scrape_types:{"…/vercel":"Greenhouse API"}, aliases:[], selected_resume_ids:[], scrape_interval_minutes:null}`. Companies 126 → 127. Row rendered `ZZA Vercel Co | T2 | not scraped yet | Default | GREENHOUSE | 0 +0 | · | – | Active`.
- Depth pills measured by computed `font-weight`: before any click `Off 400 / Light 600 / Full 400`; after clicking Off `Off 600 / Light 400 / Full 400`, and the created row came back `off`. (R2-H-03 is settled the other way — Searches now default to Light too, verified in step 2.)
- Drawer save: `title_include_expr` read back as `"manager"` from `GET /companies`. **Note:** `GET /api/companies/{id}` is **405 Method Not Allowed** — there is no single-company read endpoint; the UI only ever uses the list. Not a defect, but worth knowing for any future deep link.
- **Test scrape (real, 0.8 s)**: modal `Test scrape — ZZA Vercel Co`, config strip `URLs scraped · 1 / https://job-boards.greenhouse.io/vercel… (88 found via Greenhouse API) / Include manager`. All **88** rows rendered with `# / TITLE / STATUS / REASON / LINK` and **the reason inline in its own column** (round-2 R2-H-01 pattern now applied here): 70 × `OUT — No match for: manager`, 4 × `GLOBAL — Excluded by: marketing`, 14 × `KEPT`. Footer arithmetic: `14 kept · 74 keyword-filtered · 0 validation-rejected · 88 extracted · 18 pass this company's filters · 4 removed by the global list` — internally consistent (18 − 4 = 14). Escape closed it. **Nothing written**: `GET /jobs?company=ZZA+Vercel+Co` = 0 immediately after.
- **Run scrape**: `POST /api/scrape/company/{id}` → 202; row pill flipped to `Running`; `/monitor/active` = `{job_type:"company_scrape", trigger:"manual", scope_key:"<company_id>", company_id:"<company_id>"}` ✔ (the `company_id` the task asks for is present as its own field, not only in the scope key). Scope cleared in ~2 s; row line became `healthy · scraped just now`.
- `/monitor/history` top row: `{job_type:"company_scrape", trigger:"manual", status:"completed", duration_seconds:1.1, result_summary:"ZZA Vercel Co - 14 seen, +13 new", meta:{company:"ZZA Vercel Co"}}`.
- **`/api/scrape-log` top row: `{source:"playwright_ZZA Vercel Co", company_id:"<id>", jobs_found:14, new_jobs:13, is_warning:false, duration_seconds:1.08}`** — **R2-H-02 is fixed and verified**: a manual company scrape now writes the ScrapeLog row (in round 2 it wrote none).
- DB after the run: 87 rows for the company — **13 `new`**, 74 `ignored` (the filtered-out postings kept for dedup, by design). All 13 have real descriptions (3 651–10 978 chars) and 11 of 13 carry parsed `salary_min/max` from the Greenhouse ad. `cv_scores = {}` on every one — auto-scoring stayed off, no LLM fired.
- Feed: `/v2/feed?company=ZZA+Vercel+Co` lists the 13 (step 3).
- Rail counts: `Jobs 9 → 22`, `Companies 126 → 127` (`/api/stats` `new_jobs` 9 → 22, `total_jobs` 18844 → 18931). The company row's own counter went `0 +0` → `13 +87` with the round-2 honest tooltip *"…everything discovered, including titles the filters rejected"*.
- Console across all four scripts: **0 errors, 0 page errors, 0 HTTP ≥ 400, 0 failed requests.**

**Two accounting details, both traced to intended behaviour (not findings):**
- 14 kept in the Test but 13 stored: `Sr. Manager, Accounting (India)` was written as `ignored` because the inline body-exclusion scan matched the user's own phrase `"12+ years"` (`h1b_jd_flag=true`, snippet confirmed). Working as designed — see R3-A-01 for the reporting gap it creates.
- 88 extracted but 87 rows: `Startups Program Lead` collided on the `jobs.url` unique constraint with an existing row (`company="Vercel"`, `status=skip`) already in the DB from another source; the `IntegrityError` branch in `company_pages.py:317` swallows it. Correct dedup.

### R3-A-01 · P4 · Test scrape promises N kept, the run stores N−1, and nothing says why
**Where** `frontend/src/v2/Companies.jsx:840` (TestModal footer) vs `backend/scraper/sources/company_pages.py:305-309`
**Repro** Test-scrape a company whose board contains a posting whose *body* matches a `body_exclusion_phrases` entry, then Run the scrape and compare.
**Actual** Test footer read `14 kept`; the run reported `14 seen, +13 new` and stored the fourteenth as `status=ignored`. The test preview only applies the two *title* layers, so a body-exclusion drop is invisible in the preview and unexplained in the run summary (`+13 new` with no "1 body-excluded"). The reason exists on the row (`h1b_jd_snippet`) but no screen shows it.
**Expected** Either the preview says the body scan is not simulated, or the run summary breaks out the body-excluded count the way the test modal breaks out `removed by the global list`.
**Status** needs decision.

**Verdict: ✔**

---
## Step 2 — Search: create → Test (real) → Run (real) → badge → interval → pause/unpause

Scripts: `r3a_10_search.py` … `r3a_21_badge.py`. LLM calls: **0** (`auto_scoring_depth` = `off`).

**Steps (UI, `/v2/searches`, light)**
1. `+ New search` → measured the Auto-scoring default → Name `ZZA Search`, term `technical program manager`, Location `United States`, Hours old 168, Results wanted 5, Title exclude cleared, Sources reduced to Indeed only, Depth → `Off` → `Create search`.
2. Card `⚗ Test` (real JobSpy run).
3. Card `↻ Run` (real) → `/monitor/active` → `/monitor/history` → `/api/scrape-log`.
4. `⋯ → Edit search` → term/results/hours changed **and `Run interval · min` = 120** → `Save changes`.
5. Two more real runs while diagnosing (see R3-A-02), then one on the LinkedIn source that produced results.
6. Feed deep link `/v2/feed?search={id}`; status pill Pause → Resume.

**Asserted / measured**
- **R2-H-03 settled and verified:** the New-search form now opens on `Light` (`font-weight` `Off 400 / Light 600 / Full 400`), the same as the Add-company modal. Clicking `Off` flipped it to `600/400/400` and the created row came back `auto_scoring_depth:"off"`.
- Create: `{search_mode:"keyword", search_term:"technical program manager", location:"United States", hours_old:168, results_wanted:5, sources:["indeed"], title_include_keywords:[], title_exclude_keywords:[], run_interval_minutes:0, active:true, job_type:"fulltime"}`. Searches 6 → 7. Card badge `JOBSPY`, summary `"technical program manager" · United States · indeed`.
- **Test (real JobSpy, 1.4 s)**: modal `Test run — ZZA Search`, tabs `All (5) / Kept (3) / Filtered (2)`, 7 columns `SOURCE COMPANY TITLE LOCATION SALARY DESC STATUS`, footer `3 kept · 2 filtered · 5 raw · 1.4s`. **The filter reason is now rendered inline under the title** — `Body exclusion: …Sponsorship is not available f…` on both `OUT` rows — so **R2-H-01 is fixed and verified**.
- **Run**: `POST /searches/{id}/run` → 202; `/monitor/active` `{job_type:"search_run", trigger:"manual", scope_key:"<search_id>"}`; history `ZZA Search - 4 seen, +0 new`; `/api/scrape-log` row `{search_id:"<id>", source:"jobspy", jobs_found:4, new_jobs:0, is_warning:false}`; card summary picked up `· last run just now` and `last_run_at` was set.
- Edit: `⋯` menu = `Edit search · View results in feed · Duplicate · Delete search`; the inline form saved `{search_term, results_wanted:25, hours_old:720, run_interval_minutes:120}`, all read back from `GET /searches`. Footer note `Changes apply from the next run`.
- Pause / unpause: clicking the status pill fired `PATCH /searches/{id}` → `active:false`, pill text `Active → Paused` with `title="Resume the schedule"`; clicking again restored `active:true`. ✔
- Feed deep link `/v2/feed?search={id}`: header `10 open roles · 103 arrived today · 25 not yet scored`, filter chip **`from "ZZA Search" ✕`**, exactly the 10 rows of that run. (There is no per-row search badge in v2 — the provenance is the filter chip; the row shows company/location/salary/H-1B/age.)
- Console over all six scripts: **0 errors, 0 page errors, 0 HTTP ≥ 400.**

### R3-A-02 · P1 · Every Indeed result is silently discarded: `jk` is in the dedup tracking-param list, so all Indeed URLs hash to one `external_id`
**Where** `backend/scraper/_shared/dedup.py:120` (`make_external_id` hashes the canonical URL only) + `_DEFAULT_TRACKING_PARAMS` at `dedup.py:32` and the `dedup_tracking_params` setting, which both contain **`jk`**
**Repro** Create any keyword search with `sources:["indeed"]` and run it (I ran four times with two different terms).
**Actual**
- `make_external_id` hashes **only** `_canonical_for_hash(url)`; company and title are used only when the URL is empty. Indeed's entire job identity is the `jk` query param, and `jk` is stripped as "tracking", so `https://www.indeed.com/viewjob?jk=<anything>` canonicalises to `https://www.indeed.com/viewjob` — **one `external_id` for the whole of Indeed**.
- Measured directly: the ten distinct postings returned by a live test (`PetVet Care Centers ×6`, `La Familia ×2`, `Merck`, `US Dept of Veterans Affairs`) all produced the **same** `external_id`, and that id is already owned by `Datadog — Senior Group Manager, Field Operations` (source `jobright`, `https://www.indeed.com/viewjob?jk=ec3af3a391951b18`, discovered **2026-03-13**). Every one is skipped at `sources/jobspy.py:198`.
- Consequence in the live DB: **`SELECT … WHERE source LIKE 'jobspy_%'` returns 0 rows out of 18 933.** Four real runs in this pass reported `4 seen +0 new`, `17 seen +0 new`, `9 seen +0 new`, `9 seen +0 new`. The same search on `sources:["linkedin"]` (whose URLs are `/jobs/view/<id>` with no query string) stored `10 seen, +10 new` on the first try — so the pipeline is fine; the tracking list is not.
- Nothing anywhere reports this: the run is `completed`, `is_warning:false`, and the summary reads like a legitimate "no new jobs today".
**Expected** An Indeed search that returns ten different jobs stores ten jobs. The dedup key must not be able to erase a posting's identity.
**Proposed fix** Two independent guards, both cheap: (a) drop `jk` from `_DEFAULT_TRACKING_PARAMS` and from the `dedup_tracking_params` seed (and audit the other very generic entries in that list — `v`, `r`, `a`, `st`, `for`, `country`, `category`, `ss`, `bid` — each is an identity param on some board); (b) make `make_external_id` hash `company + title + canonical_url` as `CLAUDE.md` still documents it, so stripping a param can never merge two different postings. (b) alone fixes the class of bug; (a) also restores per-posting URLs.
**Status** needs decision on the fix shape — but the defect itself is not in doubt.

### R3-A-03 · P3 · A source that hard-fails (ZipRecruiter 403) is indistinguishable from a source that found nothing
**Where** `backend/scraper/sources/jobspy.py:112-136` / `job_monitor` summary
**Repro** Run a keyword search with `sources:["google","zip_recruiter","indeed"]`.
**Actual** The backend log shows `JobSpy:ZipRecruiter - ZipRecruiter response status code 403` and `JobSpy:Google - initial cursor not found`, but the run finished `completed`, `is_warning:false`, summary `ZZA Search - 9 seen, +0 new`, and the ScrapeLog row records no error. Neither the Searches card nor Stats shows that one of the three configured boards refused the request.
**Expected** A 403 from a configured source belongs in `ScrapeLog.error` / `is_warning`, the way an empty company scrape does.
**Status** needs decision.

**Verdict: ✔ for the UI flow (create / test / run / edit / interval / pause / delete all work); ✖ for the Indeed data path (R3-A-02).**

---
## Step 3 — Feed triage: filters, sort, title search, keyboard, bulk skip + undo, bulk save

Scripts: `r3a_30_feedfilters.py`, `r3a_31_feedsort.py`, `r3a_32_feedkb.py`, `r3a_33_bulk.py`, `r3a_34_status.py`. LLM calls: **0**.
Data: the 13 `new` ZZA Vercel Co jobs from step 1, entered as `/v2/feed?company=ZZA+Vercel+Co` (header read `13 shown · 13 matching`).

**Filters** — each opened, its options read, applied, the outgoing `GET /api/jobs` query string captured, then cleared:

| filter | menu contents (counts are live) | applied | request | result |
|---|---|---|---|---|
| Source | `Direct 15179 · Extension 28 · Jobright 2182 · LinkedIn 10 · Levels 668 · LinkedIn Extension 874 · manual 6` | Direct | `…&source=direct` | 13 |
| Company | search box + `✓ ZZA Vercel Co 87 · Amazon 2497 · Google 2351 · …` (picked company pinned to the top) | (came from the deep link) | `…&company=ZZA+Vercel+Co` | 13 |
| H-1B | `Likely 6046 · Possible 422 · Unlikely 1297 · Unknown 3150` | Unknown | `…&h1b_verdict=unknown` | 13 |
| Score ≥ | `70 / 80 / 90` + free number + note *"Also hides unscored jobs"* | 70 | `…&min_score=70` | **0** (correct — none scored yet) |
| Salary | `$150K / $180K / $220K` + free number + note *"Also hides jobs without a listed salary"* | $150K | `…&min_salary=150000` | **11** (the two without a posted salary drop out — matches the DB) |
| Status | `New · Saved · Applied · Skip · Ignored` | Saved | `…&status=saved` | **0**, then back to 13 on clear |

Every filter's ✕ restored the previous set. The status pill is the only one that is always "active"-styled (it defaults to `new,saved`) — as designed.

**Sort** — all four options, checked by request param *and* by the resulting order:
- `Newest first` → no `sort_by` param (server default) → `Technical Account Manager, Strategic Sourcing Manager, Strategic Finance Manager…`
- `Top score` → `&sort_by=score`
- `Salary, high to low` → `&sort_by=salary` → top row `Senior Manager, Solutions Architect` ($280–350K, the highest of the 13) ✔
- `Company A–Z` → `&sort_by=company`
The choice persists to `localStorage['v2_feed_sort']`.

**Title search**: typing `Solutions` (500 ms debounce) → one request `…&title_search=Solutions` → `2 shown · 2 matching` = `Manager, Solutions Architecture`, `Senior Manager, Solutions Architect`. The ✕ inside the box cleared it back to 13.

**Keyboard** (focus on the page header, not the detail iframe):
- The `?` sheet lists exactly: `j / f / ↓ Next job · k / g / ↑ Previous job · s Save/unsave · x Skip · a Mark applied · e / o Open posting · r Rescore · t Tailor résumé · c Cover letter · Esc Close menus · Ctrl-click Select · Shift-click Select range`.
- `j, j, k, ↓, ↑` from row 0 left the cursor on row 1: pressing `s` acted on **`Manager of the Technical Staff - Next.js`** (row 1 in the current order) — toast `Saved "…" · Undo`; the cursor auto-advanced, so the next `x` acted on **`Manager, Solutions Architecture`** (row 2) — toast `Skipped "…" · Undo` and the list shrank 13 → 12. Both `Undo` links reverted the PATCH (list back to 13, statuses back to `new`). ✔
- `Enter` — **not bound** in v2 (nothing changed). `Escape` closes menus/pickers only; it does not close the detail panel. Both match the shortcut sheet, which advertises neither; see R3-A-04.

**Bulk**: Ctrl-clicking three rows raised the floating bar `3 selected | Save | Skip | Score | ✦ Tailor | ✕`.
- `Skip` → one `POST /api/jobs/bulk-update` → toast `✓ Skipped 3 jobs.` → list 13 → 10; DB confirms `Engineering Manager, CDN`, `Product Communications Manager`, `Product Manager, Observability` = `skip`.
- Re-selected three of the remaining rows → `Save` → one `POST /api/jobs/bulk-update` → toast `✓ Saved 3 jobs.`; DB confirms `Senior Integrated Campaigns Manager`, `Senior Manager, Solutions Architect`, `Senior Partner Manager, AWS` = `saved`, `saved=true`.
- The header checkbox `Select all shown` → `10 selected`; clicking again → cleared.
- Final DB state for the 13: `7 new · 3 skip · 3 saved` — exactly what the clicks asked for.
- API cross-check: `status=new,saved` → 10, `status=new,saved,skip` → 13, `status=skip` → 3, `status=…,ignored` → 87. The CSV status filter is correct at every arity.

Console: the only errors in the whole step are the third-party posting the detail panel embeds (`my.greenhouse.io/users/self` 401, Greenhouse's own React hydration warnings, a blocked reCAPTCHA/Dropbox asset) — the known R2-H-06 side effect, decided "keep current".

### R3-A-04 · P4 · Bulk skip/save give no Undo, while the single-row versions do
**Where** `frontend/src/v2/JobFeed.jsx:482-486` (`bulkStatus`) vs `:326-331` (`showUndo`)
**Repro** Select 3 jobs → `Skip` on the floating bar.
**Actual** Toast is `✓ Skipped 3 jobs.` with no `Undo`. Skipping the same three one at a time gives three undoable toasts. The bulk path is the one where a mis-click costs the most (it is the only way to skip N rows at once) and it is the one that cannot be reversed from the UI — the rows leave the list and the user has to find them again through `Status · Skip`.
**Expected** The same `· Undo` affordance, restoring the previous per-job status (the endpoint already takes a list, so undo is one more `bulk-update` with the recorded prior statuses).
**Status** needs decision.

**Verdict: ✔**

---
## Step 4 — Scoring: Light then Full on a ZZA job, report contents, `llm_call_log` provenance

Scripts: `r3a_40_score.py`–`r3a_44_llm.py`. **LLM calls: 4** (see the tally at the end).
Job under test: `Senior Technical Account Manager @ ZZA Vercel Co` (`8d2f853b…`), unscored at the start.

**Light** — row selected, `r` → the rescore modal opened reading `SCORE AGAINST RÉSUMÉS / Senior Technical Account Manager / ZZA Vercel Co`, résumé list `ZZB Base · ZZB Import PM · ✓ PM · TPgM · PjM · PjM FinTech`, `1 selected` (pre-picked from `default_resume_id`, so one call not six), `DEPTH Light "Scores only" | Full "Report + keywords"`. Picking `Light` turned its background `rgb(234,241,235)` (`--accent-soft`) while Full stayed transparent. `Run scoring` → `POST /api/analyze/{id}?depth=light`, progress toast `Scoring "Senior Technical Account Manager"…`, `/monitor/active` `{job_type:"analyze_job", scope_key:"<job>:<resume>", target_job_id:"<job>"}`. **17.1 s**, `completed`.
Result: `cv_scores {"PM": 28}`, `best_cv "PM"`, **`scoring_report` empty** — Light really is scores-only. The row chip rendered `28`.

**Full** — same job, `r` again; the modal header now read `RESCORE AGAINST RÉSUMÉS` (the verb switches once a score exists ✔). Picked `Full` → `POST /api/analyze/{id}?depth=full`, **49.0 s**, `completed`.
Result: `cv_scores {"PM": 34}`, `scoring_report.PM` with keys `ats_tip · summary · breakdown · hard_blockers · matched_keywords · missing_keywords · requirement_mapping · keyword_coverage_pct`. `keyword_coverage_pct = 22`; `requirement_mapping` has 12 entries, 3 matched. The detail panel's band line read exactly **`34 · PM · 22% keywords · 3 of 12 requirements met · 1 report`**, and the report body carried a real `summary` ("…the JD calls for a Senior Technical Account Manager with a customer-facing technical title…") and an `ats_tip` naming the missing terms. Keyword coverage, requirement mapping, strengths/gaps (as `summary` + `hard_blockers`) and the band summary are all present and consistent.

**`llm_call_log` provenance** — 13 rows in the hour, **every one `claude_code` / `claude-sonnet-5`**, including the two `cover_letter` rows (group B's): **R2-H-15 is fixed and verified** — in round 2 cover-letter rows logged `claude_api / claude-sonnet-4-6`. My four rows: `score_full` 49.4 s, `score_full` 30.6 s, `score_light` 17.1 s, `score_full` 49.0 s. `input_tokens` / `output_tokens` / `cost_usd` are 0 on every row — expected for the `claude_code` provider, which reports no usage, so `/stats/llm-costs` totals `$0.00`.

**Two side-observations, logged not filed:**
- The row's dashed `SCORE` pill (and the detail panel's "Score this role") calls `scoreJob()`, which posts `?depth=full` unconditionally — the one-click path always spends the expensive call, and the Light/Full choice only exists behind `r` / `⋯ → Rescore`. Deliberate-looking, but it is the path a new user hits first.
- Pressing `s` (save) on an unscored job fired a **full** background score by itself (`on_save_action=full`, `update_job` auto-scores when `cv_scores` is empty) — correct per the documented contract, and the reason my LLM tally is 4 rather than 2.
- `apply_recommendation`, `fit_strengths` and `fit_gaps` stayed **null** after a full score; the equivalent content now lives in `scoring_report.<résumé>`. `CLAUDE.md` still documents those three columns as populated — doc drift, not a defect.

**Verdict: ✔**

---
## Step 5 — Applied: application + company auto-created → Undo removes both → Applied again

Script: `r3a_50_apply.py`. LLM calls: 0.

Seed: `POST /api/jobs/save-from-extension {title:"ZZA Delivery Program Manager", company:"ZZA Acme Systems", url:"https://example.com/zza-acme-systems-pm-002"}` → `{new:true, status:"new"}`, linked to the hardcoded `Extension` search. `ZZA Acme Systems` was confirmed absent from `GET /companies` first.
*(The first attempt used the title "ZZA Robotics Program Manager" and came back `status:"ignored"` — `robotics` is in `title_exclude_global`. Correct behaviour, and worth knowing: the extension endpoint applies the global title filter silently and such a job never reaches the feed.)*

**Measured**
- Row `⋯` menu = `Mark applied a · Tailor résumé t · Rescore r · Open posting ↗ e`.
- `Mark applied` → `PATCH /jobs/{id}` → job `applied`; toast `Applied to "ZZA Delivery Program Manager" · Undo`.
- **Application auto-created**: `{status:"applied", applied_at:…, status_transitions:[{from:null,to:"applied",source:"ui"}]}`; total 377 → 378.
- **Company auto-created**: `ZZA Acme Systems {tier:null, active:false, selected_resume_ids:["<default_resume_id>"]}`; total 128 → 129 — the documented contract.
- **`Undo` reversed all three**: job back to `new` (`saved=false`), applications **378 → 377** with no `ZZA Acme Systems` application left, companies **129 → 128** with the auto-created company gone. **R2-H-05 is fixed and verified** (in round 2 Undo left both rows behind).
- `Mark applied` again → job `applied`, one new Application (`6108ff47…`), company re-created. No duplicates.
- Console: only 404s from the deliberately fake `example.com` posting URL.

**Verdict: ✔**

---
## Step 6 — Manual log: typed text kept, reader fills empty fields, duplicate → 409

Scripts: `r3a_60_log.py`, `r3a_61_log2.py`, `r3a_62_dup.py`. LLM calls: 0.

- **Log #1** (URL from the ZZA scrape, `…/vercel/jobs/6163585004` = `SOX Manager`): saved 200; because that URL already belongs to a Job row the application **linked to the existing job** instead of creating one — the row reads `{company:"ZZA Vercel Co", title:"SOX Manager", source:"direct", has_cached_page:true, short_id:21123}` with `status_transitions [{from:null,to:"applied",source:"ui"}]` and `applied_at` at local noon (APPS-21). Applications 378 → 379.
- **Log #2 — the reader**: typed `Title = ZZA Manual Log PM`, left Company empty, pasted a Duolingo Greenhouse URL and blurred. The label switched to `Posting URL · reading…`; on completion **the typed Title was untouched and only the empty Company was filled** — **R2-H-07 is fixed and verified** (in round 2 the late response overwrote typed text). The value it filled was wrong (`Greenhouse`) — that is R3-A-05, not a regression of this fix. Overwrote Company with `ZZA Manual Co`, saved 200; the drawer opened on the new row. Applications 379 → 380.
- **Duplicate**: same URL + title + company again → `POST /api/applications` → **409**; toast `Already logged — opened the existing application.`; the modal closed, the **existing** application opened in the drawer, the count stayed at 380 and exactly one `ZZA Manual Co` row exists. The only console error is the expected 409. ✔

### R3-A-05 · P2 · The Log-application URL reader fills Company with the ATS brand, not the employer
**Where** `backend/api/routes_applications.py:406-467` (`extract_posting`), surfaced at `frontend/src/v2/Applications.jsx:644` (`readUrl`)
**Repro** Applications → `+ Log application` → paste any ATS-hosted posting URL → blur.
**Actual** measured against five live URLs:

| URL | returned title | returned company |
|---|---|---|
| `job-boards.greenhouse.io/duolingo/jobs/8730683002` | `Duolingo Careers` | **`Greenhouse`** |
| `job-boards.greenhouse.io/vercel/jobs/6163585004` | `SOX Manager` | **`Greenhouse`** |
| `jobs.lever.co/…` | `null` | **`Lever`** |
| `www.linkedin.com/jobs/view/4452146724` | `Veterinary Practice Manager at iVET360 — Shreveport, LA (+ " \| LinkedIn Jobs")` | **`Linkedin`** |
| `careers.duolingo.com/jobs/8730683002` (own domain) | `Duolingo Careers` | `Duolingo` ✔ |

The chain is JSON-LD `hiringOrganization` → `og:site_name` → hostname. ATS-hosted boards emit no JSON-LD `hiringOrganization` and set `og:site_name` to their own brand, so the fallback wins — and ATS URLs are essentially the only URLs a user pastes into this form. The value goes straight into the Company field the user is about to save, and becomes the `Job.company` and the Application grouping key. Title is unreliable on the same boards too (`Duolingo Careers` is the SPA shell title, not the role).
**Expected** For a Greenhouse/Lever/Ashby/SmartRecruiters/Workday URL the employer slug is in the path (`/duolingo/jobs/…`, `jobs.lever.co/matterport/…`), and `scraper/ats/*` already parses exactly these shapes. At minimum never return a value that is a known ATS brand — leave the field empty rather than fill it wrong, because the "only fill empty fields" rule makes a wrong value sticky.
**Proposed fix** In `extract_posting`, add a slug lookup for the known ATS hosts ahead of the hostname fallback, plus a blocklist (`greenhouse, lever, ashby, workday, smartrecruiters, rippling, linkedin, indeed, ziprecruiter`) that suppresses the fallback instead of guessing.

**Verdict: ✔ for the flow; R3-A-05 raised against the reader.**

---
## Step 7 — Stages, interviews, notes, prep pack

Scripts: `r3a_70_stages.py`, `r3a_71_interview.py`, `r3a_72_prep.py`, `r3a_73_prepui.py`. LLM calls: 0 (the prep pack is assembled server-side with no LLM, by design).
Subject: the `ZZA Delivery Program Manager @ ZZA Acme Systems` application from step 5.

- **Stages**: the drawer stepper pills carry the design's tooltips (`In the interview loop`, `Offer received`). Clicking `Interview` → `Offer` → `Rejected` fired three `PATCH /applications/{id}` calls; `status` read back `interview`, `offer`, `rejected`, and `status_transitions` accumulated all four entries with correct `from`/`to` pairs and `source:"ui"`: `null→applied`, `applied→interview`, `interview→offer`, `offer→rejected`.
- **History panel**: `Moved to Rejected · Moved to Offer · Moved to Interview · Moved to Applied · Applied with PM · Discovered via the extension` — all six, newest first.
- **Interview row**: `+ Add interview` → `What = ZZA Hiring manager screen`, `When` (a `datetime-local`) `2026-09-15T14:30`, `Where = Zoom`, `Prep note = …`. `POST /applications/{id}/interviews` → read back `{what, when_at:"2026-09-15T14:30:00+00:00", where_text:"Zoom", status:"scheduled", prep:…}`; the block rendered `INTERVIEWS · 1 | ZZA Hiring manager screen | SCHEDULED | ✕ | Tue, Sep 15, 02:30 PM · Zoom | Meet Dana; revise the delivery metrics story`.
- **Edit**: the status chip toggles `scheduled ⇄ done` via `PATCH /applications/interviews/{id}` (verified both ways). There is **no field-level edit** — see R3-A-06.
- **Delete + Undo**: `✕` deleted it with no confirm and raised `Removed "ZZA Hiring manager screen" · Undo`; `Undo` re-created the row with `what`, `when_at`, `where_text`, `prep` and `status` all intact (APPS-13's design). ✔
- **Notes**: typed into the drawer textarea, `PATCH` on blur, read back `"ZZA note — referred by Dana, follow up Friday."`.
- **Prep pack**: `⧉ Generate prep handover for AI` → `GET /applications/{id}/prep` → modal `Prep handover — ZZA Acme Systems / paste into the AI of your choice`, **5 317 characters**, sections `# <role> at <company> · ## The role · ## My résumé — PM (Summary / Experience / Skills / Education) · ## The posting · ## What I need from you`. It contains **the role** (title, company, posting URL, current stage, the booked interview with its prep note, my notes) **and the résumé** (the whole `PM` base résumé, resolved through the auto-created company's `selected_resume_ids`). Escape closed it. ✔
- Console clean across all four scripts.

### R3-A-06 · P4 · An interview row can only be deleted and re-added, never edited
**Where** `frontend/src/v2/Applications.jsx:519-530`
**Repro** Add an interview, then try to change its time or location.
**Actual** The row exposes only a status toggle (`scheduled ⇄ done`) and `✕`. A rescheduled interview — the most common change there is — means deleting the row and retyping all four fields. The backend already has `PATCH /applications/interviews/{id}` and the UI already calls it for `status`.
**Expected** Click the row (or a small ✎) to reopen the same four-field form bound to that PATCH.
**Status** needs decision.

**Verdict: ✔**

---
## Step 8 — Stats: KPIs, funnel, Sankey, run history, activity log, LLM costs

Scripts: `r3a_80_stats.py`, `r3a_81_statsui.py`. LLM calls: 0.

**KPI row** — `TOTAL JOBS 18,944 · NEW THIS WEEK 534 (−143 vs last) · SAVED 8 · APPLICATIONS 380 (32 in play) · BEST OPEN SCORE 77 Meta`. Header line `Stats · Last sweep 4d ago · 1 source needs attention · $0.00 on LLM calls in 30d`, and `/health/entities` backs the "1 source" (`Oracle — No results in the last 3 scrapes`).

**Funnel tab** — `Applied 380 · Interview 4 · Offer 1 · Rejected 349`, note *"Every row counts applications that ever reached that stage"*, conversion strip `applied → interview 1% · interview → offer 25%`. Before my flow the same numbers were `Interview 3 · Offer 0 · Rejected 348` — **+1 at every stage I walked**, exactly as expected.

**Flow (Sankey) tab** — `new (380) → applied (380) → rejected (349) / interview (4) → offer (1)`. `/api/stats/sankey` gained the two edges only my run could produce: `interview→offer 1` and `offer→rejected 1` (both were absent from the pre-run snapshot).

**Run history tab** — `TIME | JOB ID | TRIGGER | STATUS | DURATION | RESULT`, and **every row now carries a RESULT**: `company_scrape "ZZA Vercel Co - 14 seen, +13 new"`, four `search_run` rows (`ZZA Search - 4/17/9 seen +0 new`, then `10 seen, +10 new`), `analyze_job "Senior Technical Account Manager - best 34 (PM), full"` / `"… best 28 (PM), light"` / `"ZZA Delivery Program Manager - best 38 (PM), light"`, plus group B's `tailor_resume` / `score_resume` / `generate_cover_letter` summaries. **R2-H-13 is fixed and verified** — in round 2 every non-scrape row read `—`.

**Activity log** — carries this pass's rows with the right `type` and `company` tags: `scrape · "ZZA Vercel Co (Greenhouse): 13 new / 14 found in 1.1s" · company ZZA Vercel Co`; five `scrape · "JobSpy search 'ZZA Search': …"` rows; `cv_score · "Scored job 'Senior Technical Account Manager' at ZZA Vercel Co: best=34"` and `best=28`; `cv_score · "Scored job 'ZZA Delivery Program Manager' at ZZA Acme Systems: best=38"`; then `telegram · "Daily digest sent: 16 new jobs, 0 strong matches"` and `email · "Email check: 2 messages found from known domains"` from step 9.

**Timeline** — the `2026-09-03` bucket read `{total:101, new:16, saved:3, applied:3, skipped:3, filtered:76}`; the 74 filter-rejected ZZA rows land in `filtered`, not `new`. ✔

**LLM costs card** — `1d / 7d / 30d / all` toggles; `SPEND $0.00 · CALLS 848 · AVG/CALL $0.00`; table `PURPOSE | MODEL | CALLS | COST | CACHE` with `score_light claude-sonnet-5 571 · score_full claude-sonnet-5 115 · autofill 71 · tailor 42 · email claude-haiku-4-5 38 · cover_letter claude-sonnet-4-6 8 · cover_letter claude-sonnet-5 2 · pdf 1`. The two `cover_letter` rows split exactly at the R2-H-15 fix — 8 historical rows mispriced against `claude-sonnet-4-6`, 2 new rows correctly on `claude-sonnet-5`.

**Schedules card** — 8 jobs (7 system + the per-search override `Search: ZZA Search — Every 120 min (search override)`, which picked up the interval I set in step 2), each with `JOB / JOB ID / SCHEDULE / NEXT RUN / STATUS / RUN`. Console clean on every Stats visit.

**Verdict: ✔**

---
## Step 9 — Alerts: Telegram digest and Gmail check

Scripts: `r3a_90_alerts.py`, `r3a_91_alerts2.py`, `r3a_92_email.py`. LLM calls: 0 of mine (the email classifier's own `claude-haiku-4-5` call is the app's).
Both were fired from the real UI (`/v2/stats` → Schedules → `Run now`), not from curl.

- **Digest**: `POST /api/telegram/digest` → **202**, toast `Send daily Telegram digest started.`; the row's button flipped to `Running…`; run `daily_digest` completed in **0.2 s** with `result_summary "1 alert"`, and the activity log recorded `telegram · "Daily digest sent: 16 new jobs, 0 strong matches"` — **one real Telegram message sent**, as sanctioned.
- **Gmail**: `POST /api/email/check-now` → **202**, toast `Check Gmail for replies started.`; run `email_check` completed in **0.7 s**, `result_summary "1 repl"`, activity log `email · "Email check: 2 messages found from known domains"`.
- Console clean on both.

### R3-A-07 · P4 · The email-check run summary reads "1 repl" / "2 repls"
**Where** `backend/main.py:392` and `backend/scheduler.py:157` pass the noun `"repl"` into `_activity_summary(since, "email", noun)` at `scheduler.py:116-124`, which appends `"s"` when `n != 1`
**Repro** Stats → Schedules → `Run now` on *Check Gmail for replies* → Run history.
**Actual** `RESULT` reads `1 repl` (and `2 repls` on the two scheduled runs earlier today). The helper's own docstring says it should read `"3 replies"`.
**Expected** `1 reply` / `2 replies`.
**Proposed fix** Give `_activity_summary` an optional plural (`_activity_summary(since, "email", "reply", "replies")`), or pass a pre-pluralised noun.
**Status** contained one-liner; not applied (this stage is read-only).

**Verdict: ✔ (both trigger, both complete, both report)**

---
## Step 10 — Cleanup and sweep

Scripts: `r3a_95_enum.py` … `r3a_a4_sweep.py`.

**What existed before cleanup**: 90 ZZA-prefixed jobs (`ZZA Vercel Co` 87, `ZZA Acme Systems` 1, `ZZA Acme Robotics` 1, `ZZA Manual Co` 1) + 10 non-prefixed jobs created by the `ZZA Search` LinkedIn run (real veterinary employers — a keyword search cannot be made to produce prefixed rows); 3 applications; 3 companies (`ZZA Vercel Co` added by hand, `ZZA Acme Systems` and `ZZA Manual Co` auto-created by apply/log); 1 search; 1 interview row; 6 ScrapeLog rows.

1. **Applications — UI, with the confirm dialog** (3 × drawer `⋯ → ✕ Delete application`): the styled dialog reads `Delete the application for "<title>"? / The job goes back to Saved in the feed. This cannot be undone. / Cancel / Delete`; `Cancel` and Escape both dismiss. Each confirm fired `DELETE /api/applications/{id}` and raised `✓ Application deleted`. **377 → back to the 377 baseline.** The interview row went with its application.
2. **Jobs — one scoped SQL statement each** (there is no job delete endpoint), run in the container through `backend.models.db.SessionLocal`:
   - `DELETE FROM jobs WHERE company LIKE 'ZZA%' OR title LIKE 'ZZA%'` → **90 rows**
   - `DELETE FROM jobs WHERE search_id = '<ZZA Search id>'` → **10 rows**
   Nothing outside those two predicates was touched; `SELECT count(*) FROM jobs` went 18 944 → **18 844**.
3. **Companies — UI, with the confirm dialog**: `ZZA Acme Systems` and `ZZA Manual Co` deleted cleanly (`Delete <name>? / Jobs already found are kept.` → `✓ <name> deleted`). **`ZZA Vercel Co` and `ZZA Search` both returned HTTP 500** — see R3-A-08. To finish the sweep I removed the six ScrapeLog rows those two entities owned (`DELETE FROM scrape_log WHERE company_id=… / search_id=…`, 1 + 5 rows, all written by this run) and the API deletes then returned `{"deleted": true}`.

### R3-A-08 · P1 · A company that has ever been scraped, or a search that has ever run, cannot be deleted — HTTP 500 (ScrapeLog FK)
**Where** `backend/api/routes_companies.py:256-264` (`delete_company`) and `backend/api/routes_searches.py:100-113` (`delete_search`); FKs at `backend/models/db.py:260-261` (`ScrapeLog.search_id`, `ScrapeLog.company_id` — plain `ForeignKey`, no `ondelete`, no relationship cascade)
**Repro** Add a company with a valid board URL → `↻ Run` once → `⋯ → Delete company` → confirm. Same for a search: create it → `↻ Run` once → `⋯ → Delete search`.
**Actual** `DELETE /api/companies/{id}` → **500 Internal Server Error**; the UI shows `! Could not delete ZZA Vercel Co` and the row stays. Backend log:
`psycopg2.errors.ForeignKeyViolation: update or delete on table "companies" violates foreign key constraint "scrape_log_company_id_fkey" on table "scrape_log"` (and the identical `scrape_log_search_id_fkey` for searches). Measured: the two entities with ScrapeLog rows failed; the two companies with none deleted fine.
**Why it is new** In round 2 this looked healthy only because a *manual* company scrape wrote no ScrapeLog row at all (R2-H-02). Fixing R2-H-02 (commit `f75f2a1`) means every manual scrape now writes one — so **the fix made every scraped company undeletable through the UI.** Scheduled scrapes have always written these rows, so the user's real companies are affected too: `Anthropic`, `Intuit`, `Adobe`, `Mastercard` and every other row with a `playwright_*` ScrapeLog entry cannot be deleted today either. `Job.search_id` is the same shape, so a search that has stored jobs fails for the same reason even with the log rows gone.
**Expected** Deleting a company or a search succeeds and its audit rows are either cascaded or orphaned (`ON DELETE SET NULL` keeps the history readable, which suits an audit table), exactly as jobs are deliberately kept.
**Proposed fix** Either (a) in both delete handlers, `db.query(ScrapeLog).filter(...).update({"company_id": None})` / `{"search_id": None}` (and `Job.search_id → None` for searches) before `db.delete`, or (b) declare the relationships with `passive_deletes`/`ondelete="SET NULL"` — but note there is no Alembic here, so (a) is the only change that takes effect without a schema migration. Whatever the shape, the 500 must also become a handled error rather than a bare `Internal Server Error`.
**Status** needs fixing in R3-3; not applied here (this stage is read-only).

**Sweep** — every list endpoint plus a direct SQL pass, matching `name` / `title` / `company` / `source_name` / `question` against the `ZZA` prefix (`r3a_a4_sweep.py`):

| endpoint | rows | ZZA rows |
|---|---|---|
| `/companies` | 126 | **0** |
| `/searches` | 6 | **0** |
| `/jobs` (first 200, all statuses) | 200 | **0** |
| `/jobs?title_search=ZZA` | 0 | **0** |
| `/applications` | 377 | **0** |
| `/resumes` | 349 | **0** |
| `/cover-letters` | 16 | **0** |
| `/jobs/companies/list` (feed facet) | 1356 | **0** |
| `/persona` `qa_bank` | 18 | **0** |
| SQL `jobs WHERE company/title LIKE 'ZZA%'` | — | **0** |
| SQL `scrape_log WHERE source LIKE '%ZZA%'` | — | **0** |

**`SWEEP_ZZA_ROWS_REMAINING = 0`.**

Counts back to baseline: **126 companies, 6 searches, 377 applications**. `jobs` reads 18 844 against a pre-run 18 843 — the +1 arrived before my first scrape and is not mine (0 ZZA rows, 0 rows on the deleted search). `/resumes` 349 and `/cover-letters` 16 are group B's working set, untouched by me. Settings were never modified. The only rows I removed outside the ZZA prefix are the 10 jobs my own search stored and the 6 ScrapeLog rows my own runs wrote.

**Verdict: ✔**

---

## Summary

| step | verdict | LLM calls | findings |
|---|---|---|---|
| 1 · Company add / test scrape / run / monitor / ScrapeLog / feed / rail | ✔ | 0 | R3-A-01 (P4) |
| 2 · Search create / test / run / interval / pause | ✔ UI, ✖ data | 0 | **R3-A-02 (P1)**, R3-A-03 (P3) |
| 3 · Feed filters / sort / search / keyboard / bulk | ✔ | 0 | R3-A-04 (P4) |
| 4 · Light + Full scoring, report, LLM provenance | ✔ | 5 | — |
| 5 · Applied → auto-create → Undo → re-apply | ✔ | 0 | — |
| 6 · Manual log / reader / duplicate 409 | ✔ | 0 | **R3-A-05 (P2)** |
| 7 · Stages / interviews / notes / prep pack | ✔ | 0 | R3-A-06 (P4) |
| 8 · Stats KPIs / funnel / Sankey / runs / activity / costs | ✔ | 0 | — |
| 9 · Telegram digest + Gmail check | ✔ | 0 | R3-A-07 (P4) |
| 10 · Cleanup + sweep | ✔ (after a workaround) | 0 | **R3-A-08 (P1)** |

**Total LLM calls: 5** — verified against `llm_call_log`, all `claude_code` / `claude-sonnet-5`:
`score_full` ×3 (the `s`-key auto-score on *Manager of the Technical Staff*, the row `SCORE` pill on a *Veterinary Practice Manager*, the explicit Full rescore) and `score_light` ×2 (the explicit Light score, and the auto-score chain on the save-from-extension job). No search or company auto-scoring fired — everything I created was set to `auto_scoring_depth = off` before any scrape.

**Findings by severity:** P1 ×2 (R3-A-02 Indeed dedup collapse, R3-A-08 undeletable scraped company/search) · P2 ×1 (R3-A-05 URL reader returns the ATS brand) · P3 ×1 (R3-A-03 silent 403 from a source) · P4 ×4 (R3-A-01, R3-A-04, R3-A-06, R3-A-07).

**Round-2 fixes confirmed working in this pass:** R2-H-01 (filter reasons inline, both the Searches test modal and the Companies test modal), R2-H-02 (manual company scrape writes a ScrapeLog row — and see R3-A-08 for its consequence), R2-H-03 (New search now defaults to Light, matching Add company), R2-H-04 (honest "everything discovered" tooltip on the +N column), R2-H-05 (Undo after Applied removes the application *and* the auto-created company), R2-H-07 (the URL reader no longer overwrites typed text), R2-H-13 (Run history RESULT populated for every job type), R2-H-15 (cover-letter LLM calls now log `claude_code` / `claude-sonnet-5`).

**Environment notes:** the only browser console errors in the whole pass came from the third-party posting the Feed embeds in its detail-panel `<iframe>` (`my.greenhouse.io/users/self` 401, Greenhouse's own React hydration warnings, a blocked reCAPTCHA/Dropbox asset) — the known R2-H-06 side effect, decided "keep current" — plus the two deliberate error paths (404 on the fake `example.com` posting URL, 409 on the duplicate application) and the two 500s of R3-A-08.
