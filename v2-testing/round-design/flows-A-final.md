# Round design-final — Flow A (the daily loop)

Tested: 2026-09-04, branch `v2-redesign` @ `d23817c` (design-consistency pass D1–D6 + fixups), Playwright inside the backend container vs `http://caddy`, light theme unless noted, 1440×900.
Method: a repeat of `v2-testing/round3/flows-A.md` — same ten steps, same assertions, no deeper. Focus of this pass: **every control the design pass migrated must still work** — buttons, pills, menus, dialogs, drawers, inputs, selects, rows, cards, undo toasts, keyboard (Enter/Space on primitives, Escape ordering with ConfirmDialog), Tab focus rings.
Scripts: `scratchpad/dfa_*.py` (copied to `backend:/tmp/v2t/`). Prefix on every created row: **`ZZA`**. Theme is now localStorage `jobnavigator_theme` (`light|dark|system`, legacy `jobnavigator_dark_mode` still migrated on first read).
Findings are numbered `DS-A-NN`.

Baseline before the run (`dfa_00_recon.py`): **126 companies, 6 searches, 18 843 jobs, 377 applications**, 349 résumés, 16 cover letters, `/stats` `new_jobs 9 · saved 5`, 4 base résumés (`PM · TPgM · PjM · PjM FinTech`, default `PM`), `on_save_action=full`. No `ZZ*` rows anywhere; `Vercel` absent from both `/companies` and `company_exclude_global`.

---
## Step 1 — Company: add → Test scrape → Run scrape → monitor → ScrapeLog → Feed → rail counts

Scripts: `dfa_00_recon.py`, `dfa_01_company.py`, `dfa_02_test.py`, `dfa_03_run.py`. LLM calls: **0** (`auto_scoring_depth` set to `off` in the Add modal before saving).

**Steps (UI, `/v2/companies`, light)** — identical to round 3: `+ Add company` → ATS badge measured before typing → paste `https://job-boards.greenhouse.io/vercel` → name `ZZA Vercel Co` → depth `Off` → `Save`; row → drawer → `Title include = manager` → `Save changes`; row `⚗ Test`; row `↻ Run` → `/monitor/active` → `/monitor/history` → `/api/scrape-log`.

**Asserted / measured**
- Theme plumbing after D6: `<html data-theme="light" data-skin="default">` and the `.jn-v2` root mirrors both. The legacy `jobnavigator_dark_mode` boolean the harness sets is still migrated into `jobnavigator_theme` on first read, so old scripts still steer the skin.
- **ATS badge**: `—` before typing → `GREENHOUSE` + note *"Jobs are read from the board's API, so no page settings are needed."* after. ✔
- **Depth pills — migrated to `ui.jsx` `Pill`, and the state signal changed**: round 3 measured selection by `font-weight` (400/600). The design pass moved every pill to `aria-pressed` + `--pill-on-bg`; `font-weight` is now a flat 400 on all three. Measured before any click: `Off pressed=false bg #fff · Light pressed=true bg rgb(234,241,235) · Full pressed=false bg #fff` — the Light default (R2-H-03) survives. All three carry `role="button" tabindex="0"`.
- **Keyboard on the migrated primitive**: focusing the `Off` pill and pressing **Space** flipped it (`Off pressed=true bg rgb(234,241,235)`, the other two off) and the created row came back `auto_scoring_depth:"off"`. `kb()` works. ✔
- **Tab focus rings are real**: walking 8 Tab stops from the search box gave `box-shadow: rgba(63,107,82,0.22) 0 0 0 2px` on **every** stop (Tier 1/2/3/Untiered pills, the company Row, the Active pill) — `theme.css:506` `[tabindex="0"]:focus-visible`. Note a programmatic `.focus()` shows no ring (Chromium reserves `:focus-visible` for keyboard entry); only a real Tab does. ✔
- **Row is now a keyboard primitive**: `.v2-crow` renders `role="button" tabindex="0"`, and pressing **Enter** on it opened the drawer. `Title include = manager` saved and read back from `GET /companies`. `GET /api/companies/{id}` is still **405** (no single-company read endpoint) — unchanged, not a defect.
- Create: exactly one `POST /api/companies`; read back `{scrape_urls:["…/vercel"], tier:2, active:true, auto_scoring_depth:"off", detected_scrape_types:{"…/vercel":"Greenhouse API"}, aliases:[], selected_resume_ids:[], scrape_interval_minutes:null}`. Companies 126 → 127. Row rendered `ZZA Vercel Co | T2 | not scraped yet | Default | GREENHOUSE | 0 +0 | · | – | Active | ↻ Run | ⚗ Test | ⋯`. `assert_int_tops` on `.v2-crow`: 0 fractional.
- **Test scrape (real, ~1 s)**: modal `Test scrape — ZZA Vercel Co`, config strip `URLs scraped · 1 / https://job-boards.greenhouse.io/vercel… (88 found via Greenhouse API) / Include manager`. All **88** rows rendered `# / TITLE / STATUS / REASON / LINK` with the reason inline: **70 × `OUT — No match for: manager`, 4 × `GLOBAL — Excluded by: marketing`, 14 × `KEPT — body check needs the description`**. 0 fractional row tops. Footer now reads `14 kept · 74 title-filtered · 0 validation-rejected · 88 extracted · 18 pass this company's filters · 4 removed by the global list · **14 not body-checked (needs the description)**` — **R3-A-01's fix is live and visible**, and the "keyword-filtered" label became "title-filtered". Escape closed it. **Nothing written**: `GET /jobs?company=ZZA+Vercel+Co` = 0 straight after.
- **Run scrape**: `POST /api/scrape/company/{id}` → row pill flipped `Run → Running` with a `Spinner`; `/monitor/active` = `{job_type:"company_scrape", trigger:"manual", scope_key:"<cid>", company_id:"<cid>"}`; scope cleared in ~2 s; row line became `healthy · scraped just now`.
- `/monitor/history` top row `{company_scrape, manual, completed, 2.1 s, "ZZA Vercel Co - 14 seen, +13 new", meta:{company:"ZZA Vercel Co"}}`. `/api/scrape-log` top row `{source:"playwright_ZZA Vercel Co", company_id:"<cid>", jobs_found:14, new_jobs:13, is_warning:false, source_breakdown:null, duration_seconds:2.04}` (R2-H-02 still fixed).
- DB after: 87 rows for the company — **13 `new`**, 74 `ignored`; all 13 with real descriptions (3 651–10 978 chars), 11 of 13 with parsed salary, `cv_scores = {}` on every one (no LLM fired). Identical to round 3.
- Rail counts: `Jobs 9 → 22`, `Companies 126 → 127`; `/stats` `total_jobs 18 843 → 18 930`, `new_jobs 9 → 22`. The row counter went `0 +0` → `13 +87` and the honest tooltip is intact: *"13 open roles from ZZA Vercel Co in the Job Feed · 87 found in the last 7 days — everything discovered, including titles the filters rejected"*.
- Console over all three scripts: **0 errors, 0 page errors, 0 HTTP ≥ 400, 0 failed requests.**
- Side note, not a finding: `/monitor/history` shows the scheduled email checks now reading `1 reply` — **R3-A-07's fix is live**.

### DS-A-01 · P3 · The three company-row actions (Run · Test · ⋯) were left out of the primitive migration — no `role`, no tab stop
**Where** `frontend/src/v2/Companies.jsx:520`, `:528`, `:534` — three hand-written `<span onClick=…>` marked `{/* ui: keep — 25px Run/Test pills sized to the 46px row; Pill sm is 26 */}`
**Repro** `/v2/companies` → focus the search box → press Tab repeatedly.
**Actual** The Tab order runs Tier pills → the company `Row` → the `Active` `Pill` → **straight out of the list to the rail**. `Run`, `Test` and `⋯` are never focused, expose no `role="button"`, no `aria-label`, and cannot be fired with Enter/Space. Every other control on the screen picked up `kb()` from `ui.jsx` in the design pass — these three are the only ones that did not, and they are the row's primary verbs.
**Expected** Same as their migrated siblings: `tabIndex=0`, `role="button"`, Enter/Space activation. The reason they were kept hand-written is purely the 25 px height (`Pill size="sm"` is 26); that is a style argument, not a semantics one — spreading `kb(fn)` onto the existing spans is a 3-line change that keeps the 25 px.
**Proposed fix** `{...kb(() => runScrape(c.id))}` / `{...kb(() => runTest(c.id))}` / `{...kb(() => setMenuId(…))}` on the three spans, plus `aria-label`. (`kb` is already exported from `ui.jsx`.)
**Status** logged, not fixed (no source edits in this pass).

**Verdict: ✔** — every control the design pass migrated on this screen works; one set it did not migrate is keyboard-dead (DS-A-01).

---
## Step 2 — Search: create → Test (real) → Run (real) → badge → interval → pause/unpause

Scripts: `dfa_10_search.py`, `dfa_11_srun.py`, `dfa_12_sedit.py`, `dfa_13_gap.py`. LLM calls: **0** (`auto_scoring_depth = off`).

**Steps (UI, `/v2/searches`, light)** — as round 3: `+ New search` → measure the Auto-scoring default → name `ZZA Search`, term `technical program manager`, Location `United States`, Hours old 168, Results wanted 5, Title exclude cleared, Sources reduced to Indeed only, Depth → `Off` → `Create search`; card `⚗ Test` (real JobSpy); card `↻ Run` (real); `⋯ → Edit search` with `Run interval · min = 120`; status pill Pause → Resume; feed deep link.

**Asserted / measured**
- **R2-H-03 still settled**: the New-search form opens on `Light` — `Off pressed=false bg #fff · Light pressed=true bg rgb(234,241,235) · Full pressed=false bg #fff`.
- **Keyboard on migrated primitives**: focusing the `Off` depth `Pill` and pressing **Enter** flipped it (the Companies step used Space — both keys covered), and the created row read `auto_scoring_depth:"off"`.
- **Source chips** are `Pill`s with `aria-pressed`: default `✓ LinkedIn · ✓ Indeed · ✓ ZipRecruiter · ✓ Google Jobs · ○ Direct (Playwright)`; after three toggles `○ LinkedIn · ✓ Indeed · ○ ZipRecruiter · ○ Google Jobs · ○ Direct` and the row saved `sources:["indeed"]`. ✔
- Create: `{search_mode:"keyword", search_term:"technical program manager", location:"United States", hours_old:168, results_wanted:5, sources:["indeed"], title_include_keywords:[], title_exclude_keywords:[], auto_scoring_depth:"off", run_interval_minutes:0, active:true, job_type:"fulltime"}`. Searches 6 → 7. Card `ZZA Search | JOBSPY | "technical program manager" · United States · indeed | Active | ↻ Run | ⚗ Test | ⋯`.
- **Test (real JobSpy, ~1 s)**: modal `Test run — ZZA Search / dry run · nothing saved / ✕`, config strip `Term "technical program manager" / United States · 720h · 25 wanted / indeed 25`, tabs `All (25) / Kept (19) / Filtered (6)`, 7 columns `SOURCE COMPANY TITLE LOCATION SALARY DESC STATUS`, 0 fractional row tops, Escape closes. Footer `19 kept · 0 title-filtered · 6 would be ignored (body phrases) · 25 raw · 1.2s` — the R3-A-01 body-exclusion breakout is present here too. But see **DS-A-02**.
- **Run (real)**: `POST /searches/{id}/run`; the `Run` pill flipped to a `Spinner` + `Running`; `/monitor/active` `{job_type:"search_run", trigger:"manual", scope_key:"<sid>"}`; cleared in ~4 s; card summary picked up `· last run just now` and `last_run_at` was set.
- **R3-A-02 is fixed and verified live.** The 5-result Indeed run stored **5 distinct rows** — 3 `new` + 2 `ignored` — each on its own `jk` URL (`…viewjob?jk=3b466072c9e08951`, `…65b9b79c148e43bf`, `…19a17c5c309f9f8b`, …). History `ZZA Search - 3 seen, +3 new, 2 filtered out`. In round 3 the identical run stored **0**.
- **R3-A-03 is fixed and verified live.** `/api/scrape-log` now serializes `source_breakdown`: `{"indeed": {"new": 3, "seen": 3, "filtered": 2}}`, and the search carries `last_source_errors: []` (empty because Indeed did not fail this time).
- **`⋯` menu is a real menu now**: `role="menu"`, `aria-label="ZZA Search actions"`, four `role="menuitem" tabindex="0"` children — `✎ Edit search · ☰ View results in feed · ⧉ Duplicate · ✕ Delete search`. **Escape closed the menu** and left the page untouched (correct Escape ordering — innermost layer first). Focusing `Edit search` and pressing **Enter** opened the inline edit form.
- Edit: saved `{search_term, results_wanted:25, hours_old:720, run_interval_minutes:120}`, all read back from `GET /searches`; footer note `Changes apply from the next run`.
- **Pause / unpause on the migrated `Pill`**: before `{text:"Active", aria-pressed:"true", tabindex:"0", title:"Pause — leaves the schedule, config is kept"}`; **Space** on it → `PATCH` → `active:false` and the pill became `{text:"Paused", aria-pressed:"false", title:"Resume the schedule"}`; a mouse click restored `active:true`. Both input paths drive the same handler. ✔
- Feed deep link `/v2/feed?search={id}` rendered `3 open roles · 92 arrived today · 16 not yet scored` — exactly the 3 stored `new` rows of that run.
- Rail: `Jobs 22 → 25`, `Searches 6 → 7`.
- Console over all four scripts: **0 errors, 0 page errors, 0 HTTP ≥ 400, 0 failed requests.**

### DS-A-02 · P2 · The Searches test preview never applies `title_exclude_global`, so it promises jobs the run then stores as `ignored`
**Where** `backend/api/routes_searches.py:340-364` (`test_search` builds `mask` from `title_include_keywords`, `title_exclude_keywords`, `company_filter`, company-exclude and body phrases — **`title_exclude_global` is not read at all**) vs `backend/scraper/sources/jobspy.py:285` (`global_title_excl = json.loads(get_setting_value(db_excl, "title_exclude_global", "[]"))`, applied at insert time). The Companies test scrape does the opposite and *does* surface that layer (`routes_companies.py:456`, `:577`).
**Repro** Create a keyword search with an empty per-search `Title exclude` → `⚗ Test` → read the footer → `↻ Run` → read the DB.
**Actual, measured twice in this pass**
- 5-result run: preview footer `5 kept · 0 title-filtered · 5 raw`, every row `KEPT`. The run then reported `3 seen, +3 new, 2 filtered out` and stored `Intern, Design Engineering` and `Staff Technical Product Marketing Manager` as **`ignored`** (`intern` and `marketing` are both in `title_exclude_global`; `h1b_jd_flag` is `false` on both, so it is not the body scan).
- 25-result run: the very first row of the preview is `Staff Technical Product Marketing Manager … ✓ KEPT`, and the footer says `0 title-filtered`.
So the two test previews in the app disagree about which filter layers they simulate: Companies shows `GLOBAL — Excluded by: marketing` as its own status, Searches shows the same job as `KEPT`.
**Expected** The same treatment the Companies preview already ships (and `CLAUDE.md` documents under "Two title-exclude layers"): a `GLOBAL` status with `Excluded by: <keyword>` inline, and a `· N removed by the global list` term in the footer arithmetic.
**Proposed fix** In `test_search`, after the per-search `exclude_kw` mask, read `title_exclude_global` the way `sources/jobspy.py:285` does, mask on it, record the matched keyword per row, and add `global_excluded_count` to the response — the frontend footer already renders an equivalent term for companies.
**Status** logged, not fixed (no source edits in this pass).

**Verdict: ✔ for the flow** — create / test / run / edit / interval / pause / resume / deep link all work, and the two round-3 P1/P3 data findings (R3-A-02, R3-A-03) are confirmed fixed. **DS-A-02 (P2)** raised against the preview's honesty.

---
## Step 3 — Feed triage: filters, sort, title search, keyboard, bulk skip + undo, bulk save

Scripts: `dfa_30_feedfilters.py`, `dfa_31_feedsort.py`, `dfa_32_feedkb.py`, `dfa_33_bulk.py`. LLM calls: **1** (the `s` key on an unscored job auto-scores — see step 4's tally).
Data: the 13 `new` ZZA Vercel Co jobs from step 1, entered as `/v2/feed?company=ZZA+Vercel+Co` (`13 shown · 13 matching`, 13 `[data-row]`s, 0 fractional tops).

**Filter bar** — every trigger is now a migrated `Pill` carrying `aria-haspopup="menu"` + `aria-expanded`, and every panel a `Menu` with `role="menu"`. Chips read `Source▾ · Company · 1✕ · H-1B▾ · Score ≥▾ · Salary▾ · Status · Any▾`. Each was opened, its options read, applied, the outgoing query captured, then cleared:

| filter | menu contents (counts live) | applied | request | result |
|---|---|---|---|---|
| Source | `Direct 15178 · Extension 28 · Jobright 2182 · Indeed 5 · Levels 668 · LinkedIn Extension 874` | Direct | `…&source=direct` | 13 |
| Company | search box + `✓ ZZA Vercel Co 87 · Amazon 2497 · Google 2351 · Apple 1631 · …` (picked pinned to the top) | (from the deep link) | `…&company=ZZA+Vercel+Co` | 13 |
| H-1B | `Likely 6046 · Possible 422 · Unlikely 1295 · Unknown 3145` | Unknown | `…&h1b_verdict=unknown` | 13 |
| Score ≥ | `70 / 80 / 90` + free number + *"Also hides unscored jobs — they have no score to compare"* | 70 | `…&min_score=70` | **0** (correct) |
| Salary | `$150K / $180K / $220K` + free number + *"Also hides jobs without a listed salary"* | $150K | `…&min_salary=150000` | **11** |
| Status | `New · Saved · Applied · Skip · Ignored` | Saved | `…&status=saved` | **0**, back to 13 on clear |

**Escape closed every open filter menu** and left the page and the detail panel alone (correct innermost-first ordering), and every chip's `✕` restored the previous set. The Status chip is the only permanently "active"-styled one (it defaults to `new,saved`) — as designed.

**Sort** — the control is a hand-written text trigger (`Sort <value> ▾`, class `v2-hover-accent-text`); its panel is a proper `Menu` of `MenuItem`s with a `✓` hint on the current value. All four verified by request param **and** by the resulting order:
- `Top score` → `&sort_by=score`
- `Salary, high to low` → `&sort_by=salary` → top row `Senior Manager, Solutions Architect` (the $280–350K row) ✔
- `Company A–Z` → `&sort_by=company`
- `Newest first` → no `sort_by` (server default) → `Technical Account Manager, Strategic Sourcing Manager, Strategic Finance Manager, Product`
The choice persists to `localStorage['v2_feed_sort']`.

**Title search**: typing `Solutions` fired **exactly one** request after the 500 ms debounce → `…&title_search=Solutions` → `2 shown · 2 matching` (`Senior Manager, Solutions Architect`, `Manager, Solutions Architecture`). The `✕` inside the box (`span.v2-x`) cleared it back to 13.

**Keyboard** (focus on the page header):
- The `?` sheet (a `Menu role="group"`) lists exactly `j / f / ↓ Next job · k / g / ↑ Previous job · s Save / unsave · x Skip · a Mark applied · e / o Open posting · r Rescore · t Tailor résumé · c Cover letter · Esc Close menus · Ctrl-click Select · Shift-click Select range`, and **Escape closes it**.
- `j, j, k, ↓, ↑` walked the detail panel `Engineering Manager, CDN → Product Communications Manager → Product Manager, Observability → back → forward → back`. ✔
- `s` on `Product Communications Manager` → toast `Saved "…" · Undo · ✕`, API `status=saved, saved=true`, cursor auto-advanced; `Undo` → `status=new, saved=false`. ✔
- `x` on `Product Manager, Observability` → toast `Skipped "…" · Undo · ✕`, API `status=skip`, list 13 → 12; `Undo` → `status=new`, list back to 13. ✔
- `Enter` is still **not bound** in the feed, and `Escape` still does **not** close the detail panel — both unchanged from round 3 and consistent with the sheet, which advertises neither.

**Bulk** — Ctrl-clicking three rows raised the floating bar `3 selected | Save | Skip | Score | ✦ Tailor | ✕`.
- `Skip` → one `POST /api/jobs/bulk-update` → toast **`Skipped 3 jobs. · Undo · ✕`** → list 13 → 10.
- **R3-A-04 is fixed and verified**: clicking that `Undo` fired a **second** `bulk-update` and the list went straight back to 13 (round 3's bulk toast had no Undo at all). The same `· Undo` is on the bulk **Save** toast.
- Re-skipped, then `Save` on three others → one `bulk-update` → toast `Saved 3 jobs. · Undo`.
- Header checkbox `Select all shown` → `10 selected`, click again → cleared. Ctrl-click row 0 then **Shift-click row 3** → `4 selected`. The bar's `✕` cleared the selection.
- Final DB state for the 13: **`7 new · 3 skip · 3 saved`** — exactly what the clicks asked for, and exactly round 3's end state.
- API cross-check of the CSV status filter: `new,saved` → 10, `new,saved,skip` → 13, `skip` → 3, `+ignored` → 87. Correct at every arity.

Console: the only errors in the whole step are the third-party posting the detail panel embeds (`my.greenhouse.io/users/self` 401, `Failed to fetch uncacheable_attributes`, a Snowplow beacon) — the known R2-H-06 side effect, decided "keep current".

**Verdict: ✔** — nothing in the feed's migrated control set regressed, and R3-A-04 is closed.

---
## Step 4 — Scoring: Light then Full on a ZZA job, report contents, `llm_call_log` provenance

Scripts: `dfa_40_score.py`, `dfa_42_full2.py`. **LLM calls: 2** here (plus the 2 incidental `s`-key auto-scores from step 3 — full tally at the end).
Job under test: `Senior Manager, Solutions Architect @ ZZA Vercel Co` (`43ad11f7…`), unscored at the start.

**Light** — row selected, `r` → the modal opened reading `SCORE AGAINST RÉSUMÉS / Senior Manager, Solutions Architect / ZZA Vercel Co`, résumé list `ZZB Base · ZZB Import PM · ✓ PM · TPgM · PjM · PjM FinTech` (all `base`), `1 selected` (pre-picked from `default_resume_id`, so one call not six), `DEPTH  Light "Scores only" | Full "Report + keywords"`. The **Light card is pre-selected** — `background rgb(234,241,235)` (`--accent-soft`) + `border rgb(63,107,82)` (`--accent`), Full transparent on `--edge`. `Run scoring` → `POST /api/analyze/{id}?depth=light`, progress toast `Scoring "Senior Manager, Solutions Architect"… ✕`, `/monitor/active` `{job_type:"analyze_job", trigger:"manual", scope_key:"<job>:<resume>", target_job_id:"<job>"}`. **~11 s**, completed.
Result: `cv_scores {"PM": 22}`, `best_cv "PM"`, **`scoring_report` empty** — Light really is scores-only. ✔

**Full** — same job, `r` again; the modal header now read **`RESCORE AGAINST RÉSUMÉS`** (the verb still switches once a score exists ✔). Clicking the `Full` card moved the accent wash across correctly — measured `Light bg rgba(0,0,0,0) bd rgb(138,130,110)` / `Full bg rgb(234,241,235) bd rgb(63,107,82)`. `Run scoring` → `POST /api/analyze/{id}?depth=full`, **~52 s**, completed.
Result: `cv_scores {"PM": 27}`; `scoring_report.PM` carries the full key set `ats_tip · breakdown · hard_blockers · keyword_coverage_pct · matched_keywords · missing_keywords · requirement_mapping · summary`. `keyword_coverage_pct = 28`, `requirement_mapping` 13 entries, `matched_keywords` 8 / `missing_keywords` 14, a real `summary` ("…a strong B2B SaaS Product Manager in WealthTech/banking… but the role requires a Senior Manag…"), a real `ats_tip`, and populated `hard_blockers`.
The detail panel's band line read exactly **`27 · PM · 28% keywords · 4 of 13 requirements met · 1 report`**, and the row chip flipped from a dashed `SCORE` box to `27`. ✔
As in round 3, `apply_recommendation` / `fit_strengths` / `fit_gaps` stayed **null** — that content now lives in `scoring_report.<résumé>`; `CLAUDE.md` still documents the three columns as populated (doc drift, not a defect, unchanged from round 3).

**`llm_call_log` provenance** — `/stats/llm-costs?days=1` shows every call in the window on **`claude_code`**: `score_full claude-sonnet-5`, `score_light claude-sonnet-5`, `tailor claude-sonnet-5`, `pdf claude-sonnet-5`, `email claude-haiku-4-5`. **R2-H-15 stays fixed** — no `claude_api / claude-sonnet-4-6` rows appeared for any new call. `input_tokens`/`output_tokens`/`cost_usd` are 0 on every row (the `claude_code` provider reports no usage), so the 30-day total is `$0.00`.

**Two method notes, not findings:**
- The row's dashed `SCORE` pill still posts `?depth=<the `scoring_default_depth` setting>` in one click; the Light/Full choice only exists behind `r` / `⋯ → Rescore`. Unchanged from round 3.
- `r` opens the modal reliably once a **row** has been clicked; pressing it straight after a `?job=` deep link (with only the page header clicked) missed once in this pass — the detail panel's third-party `<iframe>` can take focus before the keydown, the same hazard round 3 flagged as "focus on the page header, not the detail iframe". Same behaviour as round 3, not a design-pass regression.

**Verdict: ✔**

---
## Step 5 — Applied: application + company auto-created → Undo removes both → Applied again

Script: `dfa_50_apply.py`. LLM calls: 0.

Seed: `POST /api/jobs/save-from-extension {title:"ZZA Delivery Program Manager", company:"ZZA Acme Systems", url:"https://example.com/zza-acme-systems-pm-002"}` → `{new:true, status:"new"}`, linked to the hardcoded `Extension` search. `ZZA Acme Systems` confirmed absent from `GET /companies` first.

**Measured**
- Row `⋯` menu is a real `Menu` (`role="menu"`, `aria-label="Job actions"`) of five `role="menuitem" tabindex="0"` rows: `Mark applied a · Tailor résumé t · Rescore r · Open posting ↗ e · Ignore ZZA Acme Systems everywhere`.
- `Mark applied` → `PATCH /jobs/{id}` → job `applied`; toast `Applied to "ZZA Delivery Program Manager" · Undo · ✕`.
- **Application auto-created**: `{status:"applied", applied_at:…, status_transitions:[{from:null,to:"applied",source:"ui"}]}`; total 377 → 378.
- **Company auto-created**: `ZZA Acme Systems {tier:null, active:false, selected_resume_ids:["<default_resume_id>"]}`; 127 → 128 — the documented contract.
- **`Undo` reversed all three**: job back to `new` (`saved=false`), applications **378 → 377** with no `ZZA Acme Systems` application left, companies **128 → 127** with the auto-created company gone. **R2-H-05 stays fixed.**
- `Mark applied` again → job `applied`, one new Application (`f73d9463…`), company re-created, no duplicates.
- Console: only the three 404s from the deliberately fake `example.com` posting URL.

**Verdict: ✔**

---
## Step 6 — Manual log: typed text kept, reader fills empty fields, duplicate → 409

Scripts: `dfa_60_log.py`, `dfa_61_esc.py`, `dfa_62_log2.py`, `dfa_63_escbug.py`. LLM calls: 0.

- **Log #1** (URL from the ZZA scrape, `…/vercel/jobs/6163585004` = `SOX Manager`): the reader filled `{title:"SOX Manager", company:"Vercel"}`; saved 200. Because that URL already belongs to a Job row the application **linked to the existing job** — read back `{company:"ZZA Vercel Co", title:"SOX Manager", source:"direct", has_cached_page:true, short_id:21122, status_transitions:[{from:null,to:"applied",source:"ui"}], applied_at:"…T12:00:00Z"}` (local noon, APPS-21). Applications 378 → 379.
- **Log #2 — the reader**: typed `Title = ZZA Manual Log PM`, left Company empty, pasted a Duolingo Greenhouse URL and blurred. The label switched to `Posting URL · reading…`; on completion **the typed Title was untouched and only the empty Company was filled** — **R2-H-07 stays fixed**. Overwrote Company with `ZZA Manual Co`, saved 200; the drawer opened on the new row. Applications 379 → 380.
- **Duplicate**: same URL + title + company again → `POST /api/applications` → **409**; toast `Already logged — opened the existing application. ✕`; the modal closed, the **existing** application opened in the drawer, the count stayed at 380 and exactly one `ZZA Manual Co` row exists. The only console error is the expected 409. ✔

### R3-A-05 is fixed and verified — the URL reader no longer returns the ATS brand
Re-measured against the same four URLs:

| URL | returned title | returned company | round 3 |
|---|---|---|---|
| `job-boards.greenhouse.io/duolingo/jobs/8730683002` | `Duolingo Careers` | **`Duolingo`** ✔ | `Greenhouse` |
| `job-boards.greenhouse.io/vercel/jobs/6163585004` | `SOX Manager` | **`Vercel`** ✔ | `Greenhouse` |
| `www.linkedin.com/jobs/view/4452146724` | `iVET360 hiring Veterinary Practice Manager…` | **`null`** ✔ (blocklisted rather than guessed) | `Linkedin` |
| `careers.duolingo.com/jobs/8730683002` (own domain) | `Duolingo Careers` | `Duolingo` ✔ | ✔ |

The slug lookup + ATS-brand blocklist both landed. The residual title weakness on SPA shells (`Duolingo Careers`) is unchanged and was never the P2.

### DS-A-03 · P2 · After the Log-application modal saves, every later Escape on the Applications screen raises "Discard this application?" over a page with no form — and its scrim blocks all clicks
**Where** `frontend/src/v2/Applications.jsx:480` (`onSaved={(id) => { setLogOpen(false); load(id); … }}` — closes the modal **without** clearing `logDirty`) + `:129-136` (`logDirty` / `closeLog` / `dropLog`) + `:153` (`useEscape(() => { closeAll(); setPrep(null); setEditIv(null); closeLog() }, !confirm)` — `closeLog()` runs on **every** Escape, whether or not the modal is open)
**Repro** `/v2/applications` → `+ Log application` → type anything (so `logDirty` is set) → `Save application` (200 **or** the 409 duplicate path — both close the modal and open the drawer) → press **Escape** once.
**Actual, measured** the first Escape mounts a `position:fixed; z-index:70` `ModalPanel` scrim, `1440×900`, `background rgba(20,19,15,0.42)`, reading **"Discard this application? / Everything typed will be lost. / Cancel / Discard"** — for a form that was already submitted and unmounted. `document.elementFromPoint` over `+ Log application` returns that scrim (`isBtn:false`), so **every click on the screen is dead** until a second Escape (or Cancel) dismisses it. Two Escapes restore the page. Path 1 (drawer opened by clicking a row, no prior save) and path 2 (modal opened and Escaped without saving) are both clean — the defect needs a completed save first.
**Why it is new** `logDirty` was never reset on the save path before either, but the discard confirm used to be `window.confirm` (the R2-A-01 note at `:130` — "the styled dialog, not the browser's"). Playwright — and a user hitting Return — dismisses a native dialog instantly, so it read as a stray flash. The design pass replaced it with the DOM `ConfirmDialog`, which owns a full-viewport scrim and stays up, turning a cosmetic slip into a **click-blocking** one. It is exactly the Escape/ConfirmDialog ordering this pass was asked to check.
**Expected** After a save the form is gone, so Escape must do nothing to it. Round 3's own script hit this sequence (`Escape` → `+ Log application`) and passed.
**Proposed fix** Either (a) `onSaved={(id) => { logDirty.current = false; setLogOpen(false); … }}` — one line, or better (b) gate the call: `useEscape(() => { closeAll(); setPrep(null); setEditIv(null); if (logOpen) closeLog() }, !confirm)`. (a) and (b) are independent and both are worth having.
**Status** logged, not fixed (no source edits in this pass).

**Verdict: ✔ for the flow (all three saves behave, 409 handled); R3-A-05 closed; DS-A-03 (P2) raised.**

---
## Step 7 — Stages, interviews, notes, prep pack

Scripts: `dfa_70_stages.py`, `dfa_71_interview.py`, `dfa_72_prep.py`. LLM calls: 0 (the prep pack is assembled server-side, by design).
Subject: the `ZZA Delivery Program Manager @ ZZA Acme Systems` application from step 5.

- **Stages**: the drawer stepper's four cells carry the design's tooltips — `Applied "Waiting on a first response" · Interview "In the interview loop" · Offer "Offer received" · Rejected "Closed — kept for the Stats funnel"` — and the current cell is `font-weight 600` on `rgb(234,241,235)` (`--accent-soft`). Clicking `Interview` → `Offer` → `Rejected` fired three `PATCH /applications/{id}`; `status` read back `interview`, `offer`, `rejected`, and `status_transitions` accumulated **all four** entries with correct `from`/`to` pairs and `source:"ui"`: `null→applied`, `applied→interview`, `interview→offer`, `offer→rejected`. ✔ (The stepper cells are hand-written `div.v2-bd` with no `role`/`tabindex` — DS-A-01 again.)
- **History panel**: `Moved to Rejected 1m · Moved to Offer 2m · Moved to Interview 2m · Applied with PM 8m · Moved to Applied 8m · Discovered via the extension 8m` — all six, newest first. ✔
- **Interview row**: `+ Add interview` → `What = ZZA Hiring manager screen`, `When` (a real `datetime-local`) `2026-09-15T14:30`, `Where = Zoom`, `Prep note = …`. `POST /applications/{id}/interviews` → read back `{what, when_at:"2026-09-15T14:30:00+00:00", where_text:"Zoom", status:"scheduled", prep:…}`; the block rendered `INTERVIEWS · 1 | ⧉ Generate prep handover for AI | ZZA Hiring manager screen | SCHEDULED | ✕ | Tue, Sep 15, 02:30 PM · Zoom | Meet Dana; revise the delivery metrics story | + Add interview`.
- **R3-A-06 is fixed and verified**: the row and its date line now carry `title="Edit this interview"`; clicking the row opens the inline four-field form, changing `Where` to `Zoom (rescheduled)` and pressing `Save` persisted it via `PATCH /applications/interviews/{id}`, and **Escape cancels the form** without touching the row. No blank-page regression.
- **Status chip** still toggles `scheduled ⇄ done` (verified both directions).
- **Delete + Undo**: `✕` deleted with no confirm and raised `Removed "ZZA Hiring manager screen" · Undo · ✕`; `Undo` re-created the row with `what`, `when_at`, `where_text` (including the edited `Zoom (rescheduled)`), `prep` and `status` all intact. ✔
- **Notes**: typed into the drawer textarea (`NOTES · AUTOSAVES`), `PATCH` on blur, read back `"ZZA note — referred by Dana, follow up Friday."`.
- **Prep pack**: `⧉ Generate prep handover for AI` → `GET /applications/{id}/prep` → modal `Prep handover — ZZA Acme Systems / paste into the AI of your choice / ✕`, **5 331 characters**, sections `# ZZA Delivery Program Manager at ZZA Acme Systems · ## The role · ## My résumé — PM (### Summary / Experience / Skills / Education) · ## The posting · ## What I need from you`. It carries the role (title, company, posting URL, `Stage: Rejected`, the booked interview *with the edited location and its prep note*, my notes) **and** the whole `PM` base résumé, resolved through the auto-created company's `selected_resume_ids`. Escape closed it. ✔
- Console clean across all three scripts.

**Verdict: ✔** — R3-A-06 closed.

---
## Step 8 — Stats: KPIs, funnel, Sankey, run history, activity log, LLM costs

Scripts: `dfa_80_stats.py`, `dfa_81_statsui.py`. LLM calls: 0.

**Header + KPI row** — `Stats · Last sweep 4d ago · 1 source needs attention · $0.00 on LLM calls in 30d · ↻ Refresh`, then `TOTAL JOBS 18,937 · NEW THIS WEEK 527 (−150 vs last) · SAVED 8 · APPLICATIONS 380 (32 in play) · BEST OPEN SCORE 77 Meta`. `/health/entities` backs the "1 source" (`Oracle — No results in the last 3 scrapes`), and `/stats` agrees: `{total_jobs:18937, new_jobs:19, saved_jobs:8, total_applications:380, application_statuses:{applied:32, rejected:348}}`.

**Funnel tab** — `Applied 380 · Interview 4 · Offer 1 · Rejected 349`, note *"Every row counts applications that ever reached that stage; bars are relative to Applied"*, conversion strip `applied → interview 1% · interview → offer 25%`. Baseline before this flow was `Interview 3 · Offer 0` — **+1 at every stage I walked**.

**Flow (Sankey) tab** — renders `new (380) → applied (380) → rejected (349) / interview (4) → offer (1)`, and `/api/stats/sankey` carries the two edges only my run could produce: **`interview→offer 1`** and **`offer→rejected 1`**.

**Run history tab** — columns `TIME | JOB ID | TRIGGER | STATUS | DURATION | RESULT`, and **every row carries a RESULT** (R2-H-13 stays fixed): `analyze_job … "Senior Manager, Solutions Architect - best 27 (PM), full"` / `"… best 22 (PM), light"` / `"ZZA Delivery Program Manager - best 40 (PM), light"`, plus group B's `tailor_resume` / `score_resume` / `generate_cover_letter` summaries, and earlier `company_scrape "ZZA Vercel Co - 14 seen, +13 new"` and `search_run "ZZA Search - 3 seen, +3 new, 2 filtered out"`.

**Activity log** — carries this pass's rows with the right `type`/`company` tags: `scrape · "ZZA Vercel Co (Greenhouse): 13 new / 14 found in 2.0s" · company ZZA Vercel Co`; `scrape · "JobSpy search 'ZZA Search': 3 new / 3 found (2 filtered out) in 4.4s"`; `cv_score · "Scored job 'Senior Manager, Solutions Architect' at ZZA Vercel Co: best=27"` and `best=22`; `cv_score · "… 'Product Communications Manager' … best=15"`, `"… 'Manager of the Technical Staff - Next.js' … best=15"`, `"… 'ZZA Delivery Program Manager' at ZZA Acme Systems: best=40"`.

**Timeline** — the `2026-09-03` bucket reads `{total:94, new:10, saved:3, applied:3, skipped:2, filtered:76}`; the 74 filter-rejected ZZA rows plus the 2 title-filtered Indeed rows land in `filtered`, not `new`. ✔

**Score distribution** — `3,605 scored jobs · best résumé per job · avg 46.2 · tailored 71.4`, buckets `309 / 1368 / 876 / 959 / 93`.

**LLM costs card** — `1d / 7d / 30d / all` toggles; `SPEND $0.00 · CALLS 792 · AVG/CALL $0.00`; table `PURPOSE | MODEL | CALLS | COST | CACHE` with `score_light claude-sonnet-5 540 · email claude-haiku-4-5 30 · score_full claude-sonnet-5 107 · tailor 35 · autofill 69 · cover_letter claude-sonnet-4-6 8 · pdf 1 · cover_letter claude-sonnet-5 2`. The two `cover_letter` rows still split exactly at the R2-H-15 fix (8 historical on `claude-sonnet-4-6`, all new ones on `claude-sonnet-5`).

**Schedules card** — 8 jobs (7 system + **`Search: ZZA Search — Every 120 min (search override)`**, which picked up the interval I set in step 2), each with `JOB / JOB ID / SCHEDULE / NEXT RUN / STATUS / RUN`. Console clean on every Stats visit.

**Verdict: ✔**

---
## Step 9 — Alerts: Telegram digest and Gmail check

Script: `dfa_90_alerts.py`. LLM calls: 0 of mine (the email classifier's own `claude-haiku-4-5` call is the app's).
Both were fired from the real UI (`/v2/stats` → Schedules → `Run now`), not from curl.

- `/scheduler/jobs` lists each job with its `trigger_url`, including the per-search override `search_7fe7df67… → /searches/{id}/run · Every 120 min (search override)`.
- **Digest**: `POST /api/telegram/digest` → **202**, toast `Send daily Telegram digest started. ✕`; run `daily_digest` completed in **0.1 s** with `result_summary "1 alert"`, and the activity log recorded `telegram · "Daily digest sent: 10 new jobs, 0 strong matches"` — **one real Telegram message sent**, as sanctioned.
- **Gmail**: `POST /api/email/check-now` → **202**, toast `Check Gmail for replies started. ✕`; run `email_check` completed in **0.4 s**, `result_summary` **`1 reply`** — **R3-A-07 is fixed and verified** (round 3 read `1 repl`). Activity log `email · "Email check: 1 messages found from known domains"`.
- Console clean on both.

**Verdict: ✔ (both trigger, both complete, both report)**

---
## Step 10 — Cleanup and sweep

Scripts: `dfa_95_enum.py`, `dfa_96_delapps.py`, `dfa_97_deljobs.py`, `dfa_98_delco.py`, `dfa_99_finish.py`, `dfa_a4_sweep.py`.

**What existed before cleanup** (`dfa_95_enum.py`): 89 ZZA-prefixed jobs (`ZZA Vercel Co` 87 = 74 ignored / 7 new / 3 saved / 2 skip / 1 applied, `ZZA Acme Systems` 1, `ZZA Manual Co` 1) + 5 non-prefixed jobs created by the `ZZA Search` Indeed run (3 `new`, 2 `ignored`) — a keyword search cannot be made to produce prefixed rows; 3 applications; 4 companies (`ZZA Vercel Co` added by hand, `ZZA Acme Systems` + `ZZA Manual Co` auto-created by apply/log, and **`Vercel`** auto-created by the Log-application reader in step 6 — see below); 1 search; 1 interview row; 2 ScrapeLog rows.

1. **Applications — UI, with the ConfirmDialog** (3 × drawer `⋯ → ✕ Delete application`). The drawer menu is `☰ View job in feed · ✕ Delete application`; the dialog reads `Delete the application for "<title>"? / The job goes back to Saved in the feed. This cannot be undone. / Cancel / Delete`. On the first one I checked both dismiss paths: **`Cancel` dismissed it (total still 380)** and **`Escape` dismissed it (total still 380)** — the ConfirmDialog owns Escape while it is up, and nothing behind it acted. Each real confirm fired `DELETE /api/applications/{id}` → 200 with the toast `✓ Application deleted`. **380 → 377**, back to baseline. The interview row went with its application (`SELECT count(*) FROM interviews WHERE what LIKE 'ZZA%'` = 0).
2. **Jobs — two scoped SQL statements** (there is no job delete endpoint), run in the container through `backend.models.db.SessionLocal`:
   - `DELETE FROM jobs WHERE company LIKE 'ZZA%' OR title LIKE 'ZZA%'` → **89 rows**
   - `DELETE FROM jobs WHERE search_id = '<ZZA Search id>'` → **5 rows**
   Nothing outside those two predicates was touched; `SELECT count(*) FROM jobs` went 18 937 → **18 843**, the exact pre-run number.
3. **Companies + search — UI, with the ConfirmDialog.** `Delete ZZA Vercel Co? / Jobs already found are kept.` and `Delete "ZZA Search"? / Jobs this search already found are kept.`
   **R3-A-08 is fixed and verified**: `ZZA Vercel Co` (one ScrapeLog row from its manual scrape) and `ZZA Search` (one ScrapeLog row from its manual run) **both deleted with `DELETE … → 200`** and the toasts `✓ ZZA Vercel Co deleted` / `✓ "ZZA Search" deleted`. In round 3 both returned **500** on the `scrape_log` FK. The audit rows survived as orphans exactly as the fix intends — `SELECT id, source, company_id, search_id FROM scrape_log …` returned `('playwright_ZZA Vercel Co', NULL, NULL)`. `ZZA Acme Systems` and `ZZA Manual Co` deleted cleanly too.
4. **One stray non-prefixed company of mine**, found by arithmetic (the count read 130 before the deletes, not 129): **`Vercel`** — `{tier:null, active:false, selected_resume_ids:[default], scrape_urls:[], last_scraped_at:null}`, the auto-create signature. It was created by **Log #1**, where I saved the application with the reader's own value (`company: "Vercel"`) instead of overwriting it — the side effect of R3-A-05's fix now returning the real employer. Absent from both my recon and round 3's, so unambiguously mine; deleted through the UI (`DELETE → 200`, `companies 127 → 126`). Its 10 pre-existing `Vercel` **jobs** were left alone.
5. **My two ScrapeLog rows** (`playwright_ZZA Vercel Co`, and the `jobspy` row from my search run) removed by id/time-scoped SQL — 2 rows, both written by this run.

**Sweep** (`dfa_a4_sweep.py`) — every list endpoint plus a direct SQL pass, matching `name` / `title` / `company` / `source` / `question` against the `ZZA` prefix:

| endpoint | rows | ZZA rows |
|---|---|---|
| `/companies` | 126 | **0** |
| `/searches` | 6 | **0** |
| `/jobs` (first 200, all statuses) | 200 | **0** |
| `/jobs?title_search=ZZA` | 0 | **0** |
| `/applications` (company + title) | 377 | **0** |
| `/resumes` | 353 | **0** |
| `/cover-letters` | 17 | **0** |
| `/jobs/companies/list` (feed facet) | 1356 | **0** |
| `/persona` `qa_bank` | 20 | **0** |
| SQL `jobs WHERE company/title LIKE 'ZZA%'` | — | **0** |
| SQL `scrape_log WHERE source LIKE '%ZZA%'` | — | **0** |
| SQL `companies` / `searches` / `applications` / `interviews` | — | **0** |

**`SWEEP_ZZA_ROWS_REMAINING = 0`.**

**Counts back to baseline exactly: 126 companies · 6 searches · 18 843 jobs · 377 applications.** `/resumes` 353 and `/cover-letters` 17 are group B's working set (349 / 16 at my recon), untouched by me. Settings were never modified. The only rows I removed outside the `ZZA` prefix are the 5 jobs my own search stored, the 2 ScrapeLog rows my own runs wrote, and the one `Vercel` company row my own Log #1 created.

**Verdict: ✔ (no workaround needed this time — R3-A-08's fix carried the whole cleanup)**

---

## Summary

| step | verdict | LLM calls | findings |
|---|---|---|---|
| 1 · Company add / test scrape / run / monitor / ScrapeLog / feed / rail | ✔ | 0 | DS-A-01 (P3) |
| 2 · Search create / test / run / interval / pause | ✔ | 0 | **DS-A-02 (P2)** |
| 3 · Feed filters / sort / search / keyboard / bulk + undo | ✔ | 2 (incidental `s`-key auto-scores) | — |
| 4 · Light + Full scoring, report, LLM provenance | ✔ | 2 | — |
| 5 · Applied → auto-create → Undo → re-apply | ✔ | 1 (auto-score on the extension job) | — |
| 6 · Manual log / reader / duplicate 409 | ✔ | 0 | **DS-A-03 (P2)** |
| 7 · Stages / interviews / notes / prep pack | ✔ | 0 | — |
| 8 · Stats KPIs / funnel / Sankey / runs / activity / costs | ✔ | 0 | — |
| 9 · Telegram digest + Gmail check | ✔ | 0 | — |
| 10 · Cleanup + sweep | ✔ | 0 | — |

**Total LLM calls: 5** — verified line by line against `llm_call_log` (19 rows in the window; the other 14 are group B's `tailor` / `score_resume` / `cover_letter` / `autofill` / `pdf`). All five are `claude_code` / `claude-sonnet-5`:
`score_full` ×3 — the two `s`-key auto-scores on *Manager of the Technical Staff - Next.js* (55.0 s) and *Product Communications Manager* (30.6 s), plus the explicit Full rescore (50.8 s) — and `score_light` ×2 — the explicit Light score (11.3 s) and the auto-score chain on the save-from-extension job *ZZA Delivery Program Manager* (20.8 s). Identical to round 3's tally of 5. No search or company auto-scoring fired — everything I created was set to `auto_scoring_depth = off` before any scrape.

**Findings: 3 — P2 ×2 · P3 ×1.**
- **DS-A-02 · P2** — the Searches test preview never applies `title_exclude_global`, so it promises jobs the run then stores as `ignored` (5 kept promised, 3 stored; the Companies preview does show that layer).
- **DS-A-03 · P2** — after the Log-application modal saves, every later Escape on Applications raises "Discard this application?" over a page with no form, and its scrim blocks every click until a second Escape. Made blocking by the design pass's `window.confirm → ConfirmDialog` swap.
- **DS-A-01 · P3** — the hand-written controls the primitive migration deliberately skipped (`ui: keep`) are keyboard-dead: Companies' and Searches' row `Run` / `Test` / `⋯`, the Feed's `Sort` trigger, the Feed row rail's `♥ / ✕ / ⋯`, the Feed's `Select all shown` box and `?` badge, and the Applications stage stepper — no `role`, no `tabindex`, no Enter/Space. Every *migrated* control (Button, Pill, IconButton, Row, MenuItem, Menu, Select, Input, Card, Band) carries `kb()` and works.

**Round-3 findings re-verified as fixed, live, in this pass:**
`R3-A-01` (the Companies test footer now breaks out `14 not body-checked (needs the description)`) · **`R3-A-02`** (an Indeed run stores 5 distinct rows on 5 distinct `jk` URLs — round 3 stored 0) · `R3-A-03` (`/scrape-log` serializes `source_breakdown`, the search carries `last_source_errors`) · `R3-A-04` (bulk Skip/Save toasts now carry `· Undo`, and it fires a second `bulk-update`) · **`R3-A-05`** (the URL reader returns `Duolingo` / `Vercel`, and `null` rather than `Linkedin`) · `R3-A-06` (interview rows carry `title="Edit this interview"`, the inline form saves and Escape cancels) · `R3-A-07` (`1 reply`, not `1 repl`) · **`R3-A-08`** (a scraped company and a run search both delete with 200; their ScrapeLog rows are orphaned, not blocking).

**Round-2 fixes still holding:** R2-H-01 (filter reasons inline in both test modals), R2-H-02 (manual company scrape writes a ScrapeLog row), R2-H-03 (New search defaults to Light), R2-H-04 (honest "everything discovered" tooltip on the +N column), R2-H-05 (Undo after Applied removes the application *and* the auto-created company), R2-H-07 (the URL reader does not overwrite typed text), R2-H-13 (Run history RESULT populated for every job type), R2-H-15 (every new LLM call logs `claude_code` / `claude-sonnet-5`).

**Design-pass control audit (the focus of this pass).** Every migrated primitive was exercised and works:
`Button` (Save, Save changes, Create search, Run scoring, Add interview, Save application, Cancel, Delete, Refresh, + Add company, + New search, + Log application) · `Pill` (depth Off/Light/Full — clicked **and** driven by Space *and* Enter, source chips, tier chips, every Feed filter trigger, the search status Active/Paused toggle) · `IconButton` · `Row` (`.v2-crow` and `[data-row]`: `role="button" tabindex="0"`, click **and Enter** open the drawer / select the job) · `Menu` + `MenuItem` (`role="menu"` / `role="menuitem" tabindex="0"` on the Searches ⋯, the Companies ⋯, the Feed row ⋯, the Applications drawer ⋯, and every filter panel — Enter on a menuitem activates it) · `ModalPanel` (Add company, both test modals, the rescore modal, Log application, the prep handover, ConfirmDialog) · `Drawer` (Companies config, Applications detail) · `Input` / `Textarea` / `SearchInput` (all typed into, all read back through the API; the 500 ms search debounce still fires exactly one request; the `✕` clear works) · `Select` · `Card` · `Chip` · `Toast` (progress, undo and error toasts, all with `Undo` / `✕`).
**Keyboard**: `kb()`'s Enter **and** Space both activate on `Pill`, `Row` and `MenuItem`. **Focus rings**: a real Tab walk showed `box-shadow: rgba(63,107,82,0.22) 0 0 0 2px` on **every** tab stop (`theme.css:506`); note a programmatic `.focus()` shows none — Chromium reserves `:focus-visible` for keyboard entry. **Escape ordering**: filter menus, the shortcuts sheet, both test modals, the rescore modal, the prep modal, the Log modal, the interview edit form and the ConfirmDialog each consume Escape at their own layer and leave the layer behind untouched — the one exception is DS-A-03. **Geometry**: `assert_int_tops` was 0-fractional on every list measured (`.v2-crow`, `[data-row]`, the Companies test-modal rows, the Searches test-modal rows).

**Environment notes:** the only browser console errors in the whole pass came from the third-party posting the Feed embeds in its detail-panel `<iframe>` (`my.greenhouse.io/users/self` 401, `Failed to fetch uncacheable_attributes`, a Snowplow beacon) — the known R2-H-06 side effect, decided "keep current" — plus the two deliberate error paths (404 on the fake `example.com` posting URL, 409 on the duplicate application). **No 500s anywhere in this pass.** Theme after D6: `<html data-theme data-skin>` plus the same pair mirrored on `.jn-v2`; `jobnavigator_theme` is the store, and the legacy `jobnavigator_dark_mode` boolean is still migrated on first read, so the existing harness scripts steer the skin unchanged.
