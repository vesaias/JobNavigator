# Stage 3 — Feed

Tested: 2026-09-02, bundle `index-Dnrx3n0f.js` (branch `v2-redesign`, HEAD 438d27a), themes light+dark,
viewport 1440×900 + a narrow 1024×700 pass.
Design: `v2-testing/design/JobNavigator Redesign.dc.html` — Feed artboard, markup L69–484, `<script type="text/x-dc">` L916+ (read in full)
Inventory: `v2-testing/inventory/v2-feed.md`   v1 reference: `frontend/src/components/JobFeed.jsx`
Scripts (scratchpad, prefix `feed_`): `feed_1` API recon · `feed_seed` scratch rows · `feed_2` counts/geometry/hostile data ·
`feed_3` fractional-top trace · `feed_4`/`feed_5` filter bar · `feed_6` rows/hovers/actions/bulk ·
`feed_7`/`feed_8` detail + report band · `feed_9`/`feed_10` posting, deep links, errors, load-more, modals ·
`feed_11` 401 / rescore / ignoreCompany · `feed_12` dark + narrow + leftovers.
Screenshots: `v2-testing/artifacts/feed/` (11 PNGs).

Pre-logged, re-verified **in source only** (the served bundle predates both fixes, so neither can be
exercised at runtime — `?company=` is still ignored by the running build, measured):
- **F-001** row ✦ link → `JobFeed.jsx:769` now `href="/v2/resumes/{id}"` + `navigate()`. Present.
- **F-002** `?company=` → `JobFeed.jsx:111-115`, read in the `filters` initializer. Present.

---

## Findings

### FEED-01 · P2 · The default view labels every row in the database "open roles"
**Where** `frontend/src/v2/JobFeed.jsx:601`; backend `api/routes_jobs.py:87-90`
**Repro** open `/v2/feed` with no filters.
**Expected** "N open roles" should count the open feed. The inventory flags `patchLocal` (`:283-286`)
as already assuming an empty status filter means "new + saved".
**Actual** `routes_jobs.py:87` only filters when `status` is supplied, so `total` is every job.
Measured: header "**18952** open roles"; DB status split `ignored 10938 · skip 7616 · applied 375 ·
new 9 · saved 5`; `GET /jobs?status=new` total = **14**, which is what the rail's Jobs badge shows
(`V2App.jsx:19`). Header and rail badge therefore differ by three orders of magnitude, and the list
really does contain SKIPPED / IGNORED / APPLIED rows (badges render).
`{jobs.length} shown · {total} matching` (`:696`) uses the same number and is not wrong — only the
header's noun is.
**Proposed fix** either send `status=new,saved` when `filters.status` is empty (matches `patchLocal`'s
assumption and makes the optimistic row-removal correct), or relabel to "N jobs".
**Status** fixed + verified after rebuild (`JobFeed.jsx` buildParams sends `status=new,saved` when no Status filter; header "14 open roles")

### FEED-02 · P3 · Every list row lands on a half pixel; 1px borders drop on alternating rows
**Where** `JobFeed.jsx:601` (header subline), `:770` (status badge), `:777` (salary row)
**Repro** `/v2/feed`, measure `getBoundingClientRect().top` of `[data-row]`.
**Expected** integer tops — the handover makes this a hard rule ("Half-pixel rows drop their 1px borders").
**Actual** `assert_int_tops('[data-row]')` → **37 of 40 fractional** (173.5, 250.9375, 328.375, …);
row height 77.4375. Traced the chain: header 90.5px because the subline is 13px text at the inherited
`line-height:1.5` = **19.5px**; inside the row, the status badge is 20.25px (9.5px × 1.5 + 4 padding + 2
border) and the salary/visa/age line is 13.1875px (11px × 1.2). Report-body rows are affected too
(31/31 fractional).
**Proposed fix** integer line-heights: subline `20px`, badge `14px`, salary row `13px` → header 91,
row 77.
**Status** fixed in source (rebuild pending)

### FEED-03 · P2 · The filter bar does not wrap; at 1024 px the Sort control is off-screen
**Where** `JobFeed.jsx:609`
**Repro** viewport 1024×700, `/v2/feed`.
**Expected** the design's filter bar is `flex-wrap:wrap;row-gap:8px`
(`JobNavigator Redesign.dc.html:81`).
**Actual** measured `flexWrap: nowrap`, bar `scrollWidth 946 / clientWidth 818`, and the Sort trigger's
`right` = **1151.7** in a 1024-wide viewport. The shell clips (`documentElement.scrollWidth == 1024`),
so Sort is unreachable, not merely scrolled.
**Proposed fix** `flexWrap:'wrap', rowGap:8` on the bar (design parity).
**Status** fixed in source (rebuild pending)

### FEED-04 · P2 · Sort-menu items have a dead hover
**Where** `JobFeed.jsx:685`; `theme.css:149` `.v2-menuitem:hover{background:var(--surface-2)}`
**Repro** open Sort, hover an unselected option.
**Expected** design `style-hover="background:var(--surface-2)"` on every non-current sort row
(`…Redesign.dc.html:154-156`).
**Actual** `hover_delta` → `changed: []` on both the selected and unselected rows. The item sets an
inline `background: 'transparent'`, and an inline style beats a class `:hover` without `!important` —
the trap the handover documents. Every other `.v2-menuitem` in this screen (Source, Company, H-1B,
Status, row menu, head menu) does hover correctly because none of them sets an inline background.
**Proposed fix** only emit the inline background when the row is current:
`...(sortBy === v ? { background: 'var(--accent-soft)' } : {})`.
**Status** fixed in source (rebuild pending)

### FEED-05 · P2 · "Unscored jobs stay visible — this only hides low scores" is false
**Where** `JobFeed.jsx:655` (the note); backend `routes_jobs.py:96-97`
**Repro** `GET /jobs?title_search=<scratch>&min_score=1`.
**Actual** 10 scratch rows → **3** returned; the 7 unscored ones are dropped. `Job.best_cv_score >= n`
excludes NULL in SQL, so the note states the opposite of the behaviour.
**Proposed fix** either `or_(Job.best_cv_score >= n, Job.best_cv_score.is_(None))` in the backend (makes
the note true) or change the copy to "hides unscored jobs too".
**Status** fixed in source (rebuild pending): copy, not filter — note now reads “Also hides unscored
jobs — they have no score to compare” (`JobFeed.jsx:674`). Changing `min_score` to keep NULLs would
silently re-define the parameter for every other consumer (classic JobFeed, saved filters), which is a
data-semantics decision, not a copy bug.

### FEED-06 · P2 · "Jobs without a listed salary stay visible" is false
**Where** `JobFeed.jsx:665` (the note); backend `routes_jobs.py:114-117`
**Actual** `min_salary=1000` over the same 10 rows → **2** returned; every NULL-salary row is dropped
(`Job.salary_max >= min_salary`). Same for `max_salary` (`Job.salary_min <= …`) → 2.
**Proposed fix** as FEED-05.
**Status** fixed in source (rebuild pending): copy — note now reads “Also hides jobs without a listed
salary” (`JobFeed.jsx:684`). Same reasoning as FEED-05; `salary_max`/`salary_min` semantics unchanged.

### FEED-07 · P2 · Skip / Mark-applied announce success before the PATCH resolves, and stay wrong when it fails
**Where** `JobFeed.jsx:311-312` (`skipJob` / `applyJob`), `:300` (`patchRemote`)
**Repro** intercept `PATCH /api/jobs/*` → 500, press `x`.
**Expected** an `error` toast (the taxonomy has one, and it is sticky) and the row restored.
**Actual** the `undo` toast "Skipped “…”" appears **before** the request is sent; on the 500 the server
status stays `new`, `fetchJobs()` puts the row back, `console.error` fires — and the toast still reads
"Skipped “…”" with an Undo button that would now undo nothing. No error toast at all.
On the success path everything is correct (verified: PATCH fired, row removed, header 10→9, server
`skip`, **Undo restores the previous status** — verified end-to-end).
**Proposed fix** push the undo toast in the `.then`, and add `pushToast({kind:'error'})` in
`patchRemote`'s catch.
**Status** fixed in source (rebuild pending): `patchRemote` now returns success/failure and, on failure,
pushes a sticky `error` toast (“Couldn't update …”) before the existing `fetchJobs()` revert; `skipJob`/
`applyJob` await it and only then push the undo toast with the pre-PATCH status (`JobFeed.jsx:310-325`).

### FEED-08 · P2 · "Ignore {company} everywhere" is destructive with no confirm, no toast and no undo
**Where** `JobFeed.jsx:315-327`; v1 had a `confirm()` at `frontend/src/components/JobFeed.jsx:804`
**Repro** ⋯ → "Ignore ZZTESTFEED Alpha everywhere".
**Actual** measured: no dialog, list **9 rows → 1** instantly, detail cleared, **zero toasts**, and
`company_exclude_global` grows from 302 to 303 entries — a global scraper setting that now suppresses
that company on every future scrape. Nothing tells the user it happened or how to reverse it.
(Restored to 302 during the test.)
**Proposed fix** restore v1's confirm, or push an `undo` toast whose action PATCHes the previous array back.
**Status** fixed in source (rebuild pending): `window.confirm` naming the company, the number of rows it
hides and where to reverse it (Settings → global company exclude), then a `success` toast with the count and
an `error` toast + refetch on failure (`JobFeed.jsx:328-343`). The `if (!name) return` guard moved above the
local row removal, which also kills the silent company-less deletion half of FEED-34. Undo-toast variant not
taken: re-PATCHing the whole `company_exclude_global` array 5 s later can clobber a concurrent settings edit.

### FEED-09 · P2 · A bad `?job=` id silently opens a different job
**Where** `JobFeed.jsx:479-485` (fetch, silent catch), `:489-498` (URL re-sync)
**Repro** `/v2/feed?job=11111111-2222-3333-4444-555555555555`.
**Expected** the inventory predicts "Select a job." with `?job=` left in the URL.
**Actual** worse: `GET /jobs/{id}` 404s, `pinnedRef` is cleared, the list-focus effect focuses row 0,
and the sync effect **rewrites the URL** to that unrelated job's id. Measured: URL became
`job=817d67df-…` and the panel showed "ZZTESTFEED scored by tailored resume". No toast, no message.
A shared permalink for a deleted job therefore looks like it worked.
**Proposed fix** on the 404 keep the pin cleared but set a "That job no longer exists." state, and strip
`?job=` rather than replacing it.
**Status** fixed in source (rebuild pending): the 404 branch clears the pin, sets a new `deadPinRef` so the
list effect leaves the panel empty instead of focusing row 0, calls `setDetail(null)` (which drops `?job=`
via the sync effect rather than rewriting it) and pushes an `error` toast “That job no longer exists”
(`JobFeed.jsx:196, 271, 288, 499-506`). `focusAt` releases the dead pin when the user picks a row.

### FEED-10 · P2 · `GET /api/jobs/{non-uuid}` returns 500 (backend)
**Where** backend `api/routes_jobs.py` — the `/{job_id}` getter compares a `str` to a `UUID` column
**Repro** `/v2/feed?job=not-a-uuid` → measured `500 http://caddy/api/jobs/not-a-uuid`
(psycopg2 `operator does not exist: uuid = text`). The feed swallows it silently (`:483`).
**Proposed fix** parse the id with `uuid.UUID(job_id)` and raise 404 on `ValueError`, in `get_job`
(and the same guard on `/{job_id}/cached-page` and `/{job_id}/frame-check`).
**Status** fixed by F-007 (DataError→404 handler in `backend/main.py`), verified live: `GET /api/jobs/abc` → 404
turns `invalid input syntax for type uuid` into a 404 for every id route (not just `get_job`), and logs +
500s anything else. No further change needed; verify at runtime after the next backend restart.

### FEED-11 · P2 · A failed job list is indistinguishable from an empty one
**Where** `JobFeed.jsx:229` (`console.error` only), `:731` (the empty branch)
**Repro** intercept `GET /api/jobs?*` → 500, load `/v2/feed`.
**Actual** the list renders "**No jobs match.**", the header reads "**0 open roles · 0 arrived today ·
0 not yet scored**", and **no toast appears**. Only `v2 feed load failed AxiosError…` in the console.
The 401 path is fine by contrast — measured: the shell's LoginModal ("Enter your dashboard API key…")
opens via `jn:unauthorized`.
**Proposed fix** an `error` state next to `loading`, rendering "Couldn't load jobs — retry", plus an
error toast.
**Status** fixed in source (rebuild pending): `loadError` state set in `fetchJobs`' catch and cleared on
success; renders a “Couldn't load jobs · **Try again**” row ahead of the empty branch (`JobFeed.jsx:109,
233-241, 752`). The toast is suppressed on 401 so the shell's LoginModal stays the only signal there.

### FEED-12 · P3 · The row action rail's hovers are half dead
**Where** `JobFeed.jsx:785-787`; `theme.css:126-128`
**Expected** design: ♥ `background:var(--surface-2);color:var(--accent)`; ✕ `background:var(--warn-soft);
color:var(--warn)`; ⋯ `background:var(--surface-2);color:var(--text)`
(`…Redesign.dc.html:228-231`).
**Actual** measured `hover_delta`:
| control | design | measured |
|---|---|---|
| ♥ | bg surface-2 + fg accent | bg `rgb(246,244,238)` only — **colour unchanged** `rgb(87,83,74)` |
| ✕ | bg warn-soft + fg warn | bg `rgb(246,238,228)` only — **colour unchanged** |
| ⋯ | bg surface-2 + fg text | **nothing changed at all** |
Cause: each cell sets an inline `color` (and ⋯ also an inline `background`), which beats the
non-`!important` rules in `theme.css`.
**Proposed fix** add `!important` to the `color`/`background` in `.v2-rail-save/.v2-rail-skip/.v2-rail-copy`,
or drop the inline colours.
**Status** fixed + verified after rebuild: `.v2-rail-save/-skip/-copy` hovers carry `!important`; per the user's follow-up ♥ now tints `--accent-soft` and ⋯ `--line-soft` so all three read as clearly as ✕

### FEED-13 · P3 · The row SCORE button's hover is the wrong hover
**Where** `JobFeed.jsx:760` (`.v2-hover-accent`); `theme.css:129`
**Expected** design `style-hover="border-color:var(--accent);border-style:solid;color:var(--accent);
background:var(--accent-soft)"` (`…Redesign.dc.html:212`).
**Actual** measured: only `backgroundColor → rgb(246,244,238)` (`--surface-2`). Border stays dashed
`rgb(138,130,110)`, colour stays `rgb(109,104,98)`.
**Status** fixed + verified after rebuild: the row SCORE button hovers like the design — dashed border and text turn accent, no wash (`.v2-bdc`)

### FEED-14 · P3 · Detail chevron and "+ Rescore" get a background wash instead of the design's colour change
**Where** `JobFeed.jsx:820` / `:822` (chevron, `.v2-hover-accent`), `:895` (`+ Rescore`, `.v2-navlink`)
**Expected** design: chevron `style-hover="color:var(--accent)"` (`…dc.html:253`);
"+ Rescore" `style-hover="color:var(--accent)"` (`…dc.html:325`). Neither has a background hover.
**Actual** both measured as `backgroundColor → rgb(246,244,238)`, colour unchanged (inline
`color:'var(--muted)'` wins).
Same class on the report-band header row measures bg `--surface-2` where the design says
`background:var(--line-soft)` (`…dc.html:299`) — that one at least fires.
**Status** fixed + verified: `.v2-hover-accent` colour half hardened tree-wide — chevron and + Rescore change colour and background (the unified accent hover)
authored property is the one that fails to apply)

### FEED-15 · P3 · Score/Salary preset pills and every bulk-bar button have no hover
**Where** `JobFeed.jsx:649` / `:659` (presets), `:721-725` (bulk bar)
**Expected** design: presets `style-hover="border-color:var(--accent)"` (`…dc.html:124-125, 137-139`);
bulk Skip/Score/Tailor `style-hover="border-color:#f6f3ea"`, bulk ✕ `style-hover="color:#f6f3ea"`
(`…dc.html:171-175`).
**Actual** `hover_delta` → `changed: []` for the "80" preset and for both bulk "Skip" and "Score".
**Proposed fix** `.v2-bdc` / `.v2-bd` already exist in `theme.css:157-160` for exactly this.
**Status** fixed + verified after rebuild: score/salary preset pills and the bulk-bar buttons carry the `.v2-bdc` pill hover

### FEED-16 · P3 · `Escape` closes nothing
**Where** `JobFeed.jsx:430-448` (the key handler)
**Actual** measured Escape against: filter dropdown (still open), row ⋯ menu (still open), head ⋯ menu
(still open), Create-copy modal (still open), Rescore modal (still open). Only the shortcuts popover
appeared to close, and that was the click that preceded it. Every overlay is backdrop-only.
**Proposed fix** one `if (e.key === 'Escape')` branch closing `menu`, `rowMenu`, `headMenu`,
`shortcutsOpen`, `picker`, `rescoreJob`.
**Status** fixed + verified after rebuild: Escape closes filter dropdowns, row/head menus, the shortcuts popover, the copy/tailor picker and the rescore modal — and Escape also works from inside a menu's search box

### FEED-17 · P3 · The keyboard legend and the handler disagree
**Where** `JobFeed.jsx:103` (`SHORTCUTS`), `:430-443` (handler), `:797`/`:845`/`:848` (menu hints)
**Actual** measured, one key at a time, on a focused row:
- `o` — listed in the popover as "e / o · Open posting" — **opened nothing** (0 new tabs). `e` opened 1.
- `f` and `g` — **work** (verified they move the selection) but are absent from the popover.
- `t` (hinted in both ⋯ menus) — did not open the tailor modal.
- `c` (hinted in the head menu) — did not navigate; URL unchanged.
- `Enter` — no effect (v1 toggled the detail).
Popover contents measured: `j/↓, k/↑, s, x, a, e/o, r, Ctrl-click, Shift-click` (width 214).
**Proposed fix** handle `o`, `t`, `c` (three `case` lines), and list `f`/`g`.
**Status** fixed + verified after rebuild: `o` opens the posting (same as `e`), `t` opens the tailor picker, `c` goes to the cover letter; the legend lists j/f, k/g, t, c and Esc

### FEED-18 · P3 · The collapsed report band mixes the best report's identity with the active tab's numbers
**Where** `JobFeed.jsx:866-880`
**Repro** open a job with 2 reports, open the band, switch to the second tab, read the band header.
**Actual** measured: "**88 · PM · 41% keywords · 0 of 2 requirements met · 2 reports**" — ring, score and
résumé name come from `best` (`:869-875`) while `coverage` and `reqRows` come from `active` (`:583-586`).
The header therefore attributes TPgM's coverage to PM.
**Expected/design** the design derives `bandScore`/`bandResumeLabel` from `dBest`
(`…dc.html` x-dc L826-834) and `bandCounts`/`dReqSummary` from `active` (L845, L803) — i.e. the design has
the same split, it is just never visible there because its band is only shown collapsed.
**Proposed fix** drive the whole band header off `active`, or hide the counts while the band is open.
**Status** fixed + verified after rebuild: the collapsed band's ring, score, name, keyword % and requirements all come from the best report (measured 65% / 10 of 14 = the best report's own numbers)

### FEED-19 · P3 · Rescoring an already-scored job gives no signal in the detail panel
**Where** `JobFeed.jsx:591` (`running`), `:359-361` (`runRescore` updates `jobs` but not `detail`),
`:864` (`dScored` ignores `running`)
**Repro** open a scored job → `r` → Run scoring.
**Actual** measured: the row spinner appears (1 `.v2-spin`), but in the detail panel
`{report: true, running: false, notScored: false}` — the report band simply stays as it was.
Two reasons: `runRescore` never sets `in_flight` on `detail`, and even if it did, both the report band
and the running band would render at once because `dScored = reports.length > 0` does not exclude
`running`. The design defines `dScored = !!dBest && !dRunning` (x-dc L794) so exactly one band shows.
**Proposed fix** `const dScored = reports.length > 0 && !running`, and mirror the `in_flight` update onto
`detail`.
**Status** fixed in source: in-flight state is mirrored onto the open detail (score, rescore, tailor and the poll), and the report band yields to the running band while a rescore runs

### FEED-20 · P3 · Bulk Save / Skip are silent and leave the header counts stale
**Where** `JobFeed.jsx:422-426`
**Actual** measured: `POST /jobs/bulk-update` fires and the list refetches, but there is **no toast on
success, none on failure (console.error only), no undo**, and `refreshStats()` is never called — the
header's "arrived today / not yet scored" figures do not move after a bulk skip. Single-row skip has an
undo; the bulk version, which can hit 40 rows at once, has none.
**Status** fixed + verified in source: bulk Skip/Save toast success ("Skipped N jobs") or error, and refresh the header stats

### FEED-21 · P3 · "Run scoring" with nothing selected is a silent no-op
**Where** `JobFeed.jsx:350-352`, `:1180`
**Actual** measured with 0 résumés selected: the button renders grey (`background rgb(138,130,110)`,
`cursor: default`) but is still clickable; clicking fires **no POST**, leaves the modal open and shows
no message. Same shape on the picker's confirm (`:1124`) when `cvBase == null`.
**Proposed fix** disable pointer events, or surface "Pick at least one résumé".
**Status** fixed in source: Run scoring with nothing selected is inert (pointer-events none, tooltip "Pick at least one résumé")

### FEED-22 · P3 · The live iframe mounts before the frame-check answers, so blocked postings throw a console error and flash
**Where** `JobFeed.jsx:1044` — rendered whenever `d.url && (extActive || forceFrame || frameOk !== false)`,
which includes `frameOk === null`
**Actual** during an ordinary browse of the real feed the console collected
`Refused to display 'https://jobs.citi.com/…' in a frame because it set 'X-Frame-Options' to 'deny'`
**twice**, plus two `net::ERR_BLOCKED_BY_RESPONSE` request failures, before the blocked panel replaced
the frame. `GET /{id}/frame-check` does a live fetch of the posting with a 12 s timeout
(`routes_jobs.py:680`), so the window is long on a slow site.
The blocked panel itself is correct once it arrives — measured copy matches the design verbatim and the
"Open in new tab ↗" button measures h 34 / pad 0 16px / accent, exactly the design's numbers
(`…dc.html:447`).
**Proposed fix** render the "probing" placeholder (or nothing) while `frameOk === null`.
**Status** fixed + verified after rebuild: nothing mounts while the frame-check is pending (0 iframes, 0 X-Frame-Options console errors during the probe)

### FEED-23 · P3 · Requirement table: unmet rows aren't tinted, header isn't sticky
**Where** `JobFeed.jsx:966-976`
**Expected** design rows carry `background:{{ r.bg }}` = `var(--bad-soft)` for unmet rows (x-dc L1593),
and the column header is `position:sticky;top:0;z-index:2;background:var(--surface)` (`…dc.html:381`).
**Actual** measured every row `backgroundColor: rgba(0,0,0,0)`; header `position: static`.
Everything else in the table is right — 2 of 4 met, ✓/✕ in `--good`/`--bad`, `cv_evidence || cv_match || '—'`
fallback all verified, and the All/Gaps segmented control filters correctly (4 rows → 2, both unmet).
**Status** decided 2026-09-02: keep (no tint)

### FEED-24 · P3 · Empty state is one bare line where the design has a guided one
**Where** `JobFeed.jsx:731`
**Expected** design: a dashed card — "No titles match “q”" + "Search looks at job titles only — company
and source have their own filters." + a **Clear search** button (`…dc.html:180-184`) — and a full
"Nothing to show" overlay on the detail pane (`…dc.html:246-250`).
**Actual** "No jobs match." only, in both the no-results and the filtered-to-nothing case, with no way
back. The detail pane shows "Select a job."
**Status** fixed + verified after rebuild: a filtered miss shows "No jobs match." + a Clear filters link (resets filters, search and the search-scope)

### FEED-25 · P3 · Title search has no clear affordance
**Where** `JobFeed.jsx:611`
**Expected** design has a ✕ inside the input (`clearTitleQuery`, `…dc.html:84`) plus a
`Title · “{query}”` removable chip in the filter bar (`…dc.html:145-148`).
**Actual** neither exists; the only way to clear is to select-all-and-delete. Every other filter has a ✕.
**Status** fixed + verified after rebuild: the title search shows a ✕ while it has text; clicking clears it and the list comes back

### FEED-26 · P3 · Source and H-1B dropdowns show no per-value counts
**Where** `JobFeed.jsx:620` / `:645`
**Expected** design shows a mono count on every Source row (LinkedIn 64, Indeed 51, …) and every H-1B row
(Likely 112, …) — `…dc.html:88-93, 106-111`. The Company dropdown in code does show counts.
**Actual** measured Source menu text "Direct | Extension | Jobright | Levels | LinkedIn Extension";
H-1B "Likely | Possible | Unlikely | Unknown". `/jobs/companies/list?counts=1` exists; there is no
equivalent counted endpoint for sources/verdicts.
**Status** fixed + verified after rebuild + restart: `/jobs/sources/list?counts=1` and `/jobs/verdicts/list?counts=1` return `[{name, count}]`; the Source and H-1B dropdowns show a mono count per value

### FEED-27 · P3 · Score ring geometry and colour scale differ from the design
**Where** `JobFeed.jsx:12` (`ROW_C`), `:23` (`scoreColor`), `:747-751`
**Expected** design row ring: 40×40, `viewBox 0 0 44 44`, `r 17.5`, `stroke-width 1.5` (≈1.36 px rendered),
colours `>=80 → --accent`, `>=65 → --text-2`, else `--muted` (x-dc L1474-1478, with an authored comment
explaining the three tiers).
**Actual** measured 44×44, `viewBox 0 0 88 88`, `r 35`, `stroke-width 5` (2.5 px rendered), colours
`>=70 → --good`, `>=50 → --warn`, else `--bad`. The band ring (34px, viewBox 78, sw 5) does match the design.
**Status** decided 2026-09-02: keep
match the design?

### FEED-28 · P3 · Sort's fourth option differs from the design
**Where** `JobFeed.jsx:52`
**Expected** design list: Top score / Newest first / Salary, high to low / **Last updated** (`…dc.html:158`).
**Actual** measured: Top score / Newest first / Salary, high to low / **Company A–Z**. All four code
options work (`sort_by=score|<omitted>|salary|company` verified on the wire) and the choice persists to
`v2_feed_sort`.
**Status** decided 2026-09-02: keep

### FEED-29 · P4 · Save gives no feedback; the design gives it an undo toast
**Where** `JobFeed.jsx:310` (`saveJob`)
**Expected** design `job.save` → `setStatusWithUndo(i,"saved","♥","Saved “…”")` (x-dc L1544).
**Actual** measured: PATCH fires and the server flips `saved`/`status` correctly, **zero toasts**. Skip
and Apply both toast; Save does not, so the one action that does not remove the row is also the one with
no confirmation.
**Status** fixed + verified after rebuild: Save/unsave shows the undo toast ("Saved “title” · Undo")

### FEED-30 · P4 · Row metrics drift from the design
**Where** `JobFeed.jsx:742-780`
| property | design | measured |
|---|---|---|
| row content padding | `12px 12px 12px 22px` | `10px 12px` |
| company max-width | 170 px | 230 px |
| title/badge row | `align-items: baseline` | `center` |
| badge border (skip/ignored) | `var(--edge)` | `var(--line)` |
| list header padding | `12px 30px 8px` | `12px 14px 8px 24px` |
| header / filter-bar left pad | 30 px | 24 px |
Pill geometry, panel widths (216/248/196/212/224/172/228/236/436) and the detail header
(`20px 30px 15px`, 26px title, clamp 2 → collapsed `11px 30px 12px`, 17px, clamp 1) all match exactly.
**Status** decided 2026-09-02: keep

### FEED-31 · P4 · Dead code
**Where** `JobFeed.jsx:578` `arrivedToday` (computed every render, never rendered — the header uses
`stats.arrived_today`); `:405` `unscored` memo (never referenced); `:57` `Drop`'s `align` prop
(destructured, never used; passed at `:667` and `:681`); `:135` `forceFrame` (only ever set `false`, so the
"embed anyway" override does not exist); `theme.css:208` `.v2-tab { transition: color .12s }` with no
`:hover` rule anywhere — measured `changed: []`, which **matches the design** (no `style-hover` on tabs),
so the transition is simply inert.
**Status** fixed + verified after rebuild: `arrivedToday`, the `unscored` memo, `Drop`'s `align` prop and `forceFrame` removed (a leftover `setForceFrame` call was caught by the build and removed too); 0 console errors

### FEED-32 · P4 · The Company menu remembers the previous query
**Where** `JobFeed.jsx:623`
**Actual** measured: type `ZZTEST`, pick a company, close, reopen → the input still reads `ZZTEST` and
the list is still filtered. Nothing resets `companyQuery`.
**Status** fixed + verified after rebuild: the Company menu's search box resets when the menu closes

### FEED-33 · P4 · The Score and Salary number inputs fire one request per keystroke
**Where** `JobFeed.jsx:653` / `:663`
**Actual** measured **3** `GET /jobs` requests while typing "55" (clear + two digits). The title search is
debounced 400 ms (`:195`); these are not debounced at all.
**Status** fixed + verified after rebuild: Score / Salary boxes commit 400 ms after the last keystroke (0 requests while typing "55", 1 afterwards)

### FEED-34 · P4 · A job with no company still offers "Ignore  everywhere"
**Where** `JobFeed.jsx:801` / `:854`, handler `:315-327`
**Actual** measured on a company-less job: the menu item renders as "**Ignore everywhere**", and clicking
it removes every company-less row from the list before `if (!name) return` aborts — a silent local
deletion with no server change. The detail eyebrow also renders a leading separator: "· DIRECT · JUST NOW".
**Proposed fix** hide the item when `!job.company`; skip the leading `·` in the eyebrow.
**Status** fixed + verified after rebuild: the Ignore item is hidden for a company-less job (both menus) and the detail eyebrow drops its leading separator

### FEED-35 · P4 · The posting pane is an iframe where the design is a reader column
**Where** `JobFeed.jsx:1027-1060`
**Expected** design renders the description as a 66ch reader column — `About the role` / `What you'll do`
/ `Requirements` (`…dc.html:456-478`) — with the Live/Cached toggle as an **inset card**
(`margin:0 0 16px; padding:7px 11px; border:1px solid var(--line); border-radius:9px`).
**Actual** a full-bleed third-party iframe, with the toggle as a full-width bar (`padding:'9px 30px'`,
`borderBottom`). The cached path works: measured `iframe[title="cached"]` with a 1595-char `srcDoc`,
caption "Cached snapshot · captured when you applied", body text read through the frame, and Live
switches back. The no-URL case renders "No posting URL captured for this job." and hides the header's
`Open ↗` (verified) while the row ⋯ menu still shows a no-op "Open posting ↗".
**Status** decided 2026-09-02: keep

### FEED-36 · P4 · `--iframe-bg` is the same white in both themes
**Where** `theme.css:34`
**Actual** measured `backgroundColor rgb(255,255,255)` for the posting iframe in light **and** dark — the
only token in the whole sweep that does not change. Defensible for third-party pages; it also applies to
our own cached-snapshot document.
**Status** decided 2026-09-02: keep the white frame ground

### FEED-37 · P4 · Palette values differ from the design's map
**Where** `theme.css:5`
**Actual** `--surface-2` is `#f6f4ee` (design `#f3f0e8`), `--bg` is `#fcfbf7` (design `#faf8f3`).
Screen-wide, not feed-specific.
**Status** decided 2026-09-02: keep — the user changed `--surface-2` (#f6f4ee) and `--bg` (#fcfbf7) on purpose

### FEED-38 · P4 · No load-more or end-of-list indicator
**Where** `JobFeed.jsx:240-257`
**Actual** infinite scroll works — measured 40 → 80 rows with `limit=40&offset=40` on the wire — but
nothing renders while the page is in flight and nothing marks the end of the list.
**Status** fixed + verified after rebuild: "Loading more…" while a page is in flight, "End of the list · N jobs" once exhausted

---

## Verified working (no finding)

- Filter pills: geometry matches the design exactly (h 30, `padding 0 13px`, `border-radius 99px`,
  `font-size 12.5px`, border `--edge`), active state `--accent` / `--accent-soft` / `--accent`.
- Every filter and its ✕: Source (`source=direct`), Company (`company=ZZTESTFEED+Alpha`),
  H-1B (`h1b_verdict=likely`), Score presets + free entry (`min_score=80`, `55`), Salary presets
  (`min_salary=180000`), Status multi-select (`status=applied,new`), Sort (`sort_by=score|salary|company`,
  omitted for date) — each verified on the wire and each clear verified to remove exactly its own param.
- Company dropdown: autofocused search, 1373-company placeholder count, per-company counts, picked
  companies pin to the top, "No matches" empty copy, 80-row cap.
- Panel widths: Source 216, Company 248, H-1B 196, Score 212, Salary 224, Sort 172, row menu 228,
  head menu 236, modals 436 — all match the design. Sort right-aligns via the overflow flip.
- `max_salary`'s label branch renders (`$150K–$250K`) when seeded from stale `v2_feed_filters`; there is
  still no control for it (as the inventory says).
- Rows: 200-character title ellipsises with a tooltip (`scrollWidth 1447 / clientWidth 346`) and keeps
  the row at one line; a job with no company renders without a stray separator; `cv_scores = {}` shows the
  dashed SCORE button; ignored rows measured with the hatched `repeating-linear-gradient`, `opacity .55`
  and `line-through`.
- Selection: Ctrl-click toggles, Shift-click ranges ("3 selected"), select-all toggles both ways
  ("9 selected" → 0), the floating bar renders on `--rail` with the design's 27px buttons.
- Undo: skip → `PATCH status=skip` → Undo → status restored (verified against the API both ways).
- Mark applied: `PATCH status=applied` — and the **backend does create an Application row** with a
  `{from:null,to:'applied',source:'ui'}` transition (the inventory's "v2 does not create an Application"
  note is wrong). Note the Undo only reverts `Job.status`; the Application row survives.
- Report band: collapsed height 50, `padding 8px 30px 8px 4px`, `--surface-2` — all design values;
  ring dash `193.5 220` = 2π·35·88/100 ✓; header counts agree with the data (78% keywords, 2 of 4
  requirements, 2 reports); tabs show `(score)` desc-sorted with the accent underline; `+ Rescore`,
  breakdown grid (5 criteria ×/20), keyword bar + chips (`--accent-soft`/`--good` matched,
  `--bad-soft`/`--bad` missing), matched/missing counts, hard-blockers box, ATS tip, quick-scored notice
  for a report-less score — all render correctly, and switching tabs re-derives every number.
- Section collapse states (`breakdownOpen`, `keywordOpen`, `reqOpen`, `reqFilter`, `showMatched`,
  `headOpen`, `reportOpen`) all persist to `v2_feed_ui` — round-tripped.
- Rescore modal: default selection follows `default_resume_id` ("1 selected" = PM), depth cards work,
  `POST /analyze/{id}?depth=light` on the wire, modal closes, progress toast, row spinner.
- Header "Score N unscored jobs" pill: appears only when `stats.unscored > 0`, count agrees with
  `/jobs/feed-stats` and with `/jobs/unscored-ids` (3/3), and opens the bulk modal titled "3 unscored jobs".
- Picker modal: method cards, base list incl. "Persona · from /persona", footer note switches with the
  method, Cancel closes, and a 500 from `POST /resumes/copy` produces the sticky `error` toast
  "Copy failed for “…”" (still present after 4 s — `TTL.error = null` confirmed).
- `?job=<valid>` opens the right job and keeps the param; `?search=<id>` scopes the feed (678 matching =
  the API's total for that search), shows `from “3 Days Levels Search” ✕`, and clearing it restores
  18952 and drops the param.
- 401 on any call opens the shell's LoginModal.
- Dark mode: 20 of 22 measured surfaces change (bg, text, lines, rail, badges, chips, ring stroke,
  menus, hatch pattern, selected row). No light-only value survives.
- Console is clean on every flow apart from the expected iframe noise (404s from scratch URLs; the XFO
  errors are FEED-22).

## Fixed in source
- `frontend/src/v2/JobFeed.jsx:601` — header subline `lineHeight: '20px'` (FEED-02)
- `frontend/src/v2/JobFeed.jsx:770` — status badge `lineHeight: '14px'` (FEED-02)
- `frontend/src/v2/JobFeed.jsx:777` — salary/visa/age row `lineHeight: '13px'` (FEED-02)
- `frontend/src/v2/JobFeed.jsx:609` — filter bar `flexWrap:'wrap', rowGap:8` (FEED-03)
- `frontend/src/v2/JobFeed.jsx:685` — sort item background only when current, so `.v2-menuitem:hover` fires (FEED-04)

All five are JSX: **fixed in source, rebuild pending** — none are in the served bundle.

## Couldn't test
- Row ✦ tailored link and "✦ Open tailored ↗" at runtime — no scratch row could be given a real
  `tailored_resume_id` without creating a résumé, and the served bundle predates F-001 anyway. Verified
  in source only.
- Tailor success path (`POST /resumes/tailor` → in-flight poll → success toast with "Open ↗") — the POST
  is a real LLM run; every script routed it to a 202 stub, so `/monitor/in-flight` and `/monitor/finished`
  never produced a completion. The failure path was exercised via `POST /resumes/copy` → 500.
- Score-watch poll (`:507-524`, save-an-unscored-job → poll `/jobs/{id}` until scored) — needs a real
  scoring run to land.
- Extension marker (`data-jn-ext`) and `extActive` — no extension in the container.
- Scrollbar styling (`.v2-scroll::-webkit-scrollbar`) — headless Linux uses overlay scrollbars
  (`scrollbarColor: auto` in both themes); the handover flags this as untestable here.
- `Drop` panel drift on window resize while open — the backdrop makes this hard to trigger meaningfully
  headless.
- Empty-database rendering — explicitly a later pass.

## LLM budget
2 real `analyze_job` runs fired accidentally (a `section .v2-hover-accent` selector matched a row's
SCORE button in the list, not the detail chevron). Both completed; the affected scratch rows were reset
to `cv_scores = {}`. Every script after that routes `POST /api/analyze/**`, `/resumes/tailor` and
`/resumes/copy` to stubs, so no further real calls were made. Budget: 2 of 2 used.

## Scratch data
- Created: 9 jobs, titles prefixed `ZZTEST…` (renamed mid-run to `ZZTESTFEED…` to stop colliding with
  another agent's `ZZTEST Alpha` rows), company `ZZTESTFEED Alpha`, plus one company-less row.
- Deleted: all 9 (`delete from jobs where title like 'ZZTESTFEED%'` → 9 rows; 0 remain). Applications
  created by the Mark-applied test deleted too.
- Reversible edits made and restored:
  - `company_exclude_global` 302 → 303 (ignoreCompany test) → **restored to 302**, `ZZTESTFEED Alpha` absent.
  - A bulk select-all fired Skip on 40 rows belonging to another agent's `ZZTEST Alpha` scrape set
    (the reload had cleared my title filter). All 40 **restored to `ignored`** immediately
    (`status='skip' and company='ZZTEST Alpha' and title not like 'ZZTEST%'` → 40 rows).
- **Scratch rows remaining: 0.**

## Summary
- Inventory boxes: **239 total — 157 `- [x]` verified OK, 72 `- [!]` failed or confirmed-suspicious
  (each annotated with its finding id), 10 `- [~]` untestable** (listed above).
- Findings: **11 × P2**, **17 × P3**, **10 × P4**, 0 × P1. Total 38.
- Fixes applied: 5, all JSX, all "fixed in source, rebuild pending".
- Backend finding FEED-10 left unfixed on purpose (no hot-reload; restart is the coordinator's call).
- Scratch rows remaining: **0**.

## P2 triage (2026-09-02)

| id | action | note |
|---|---|---|
| FEED-05 | fixed | Copy, not filter: note now says the Score filter also hides unscored jobs. Backend `min_score` semantics left alone — changing them would re-define the parameter for classic JobFeed too. |
| FEED-06 | fixed | Same, for the Salary note. |
| FEED-07 | fixed | `patchRemote` returns success + pushes a sticky `error` toast on failure; skip/apply push the undo toast only after the PATCH resolves. |
| FEED-08 | fixed | `window.confirm` (company + row count + how to reverse), `success` toast with the count, `error` toast + refetch on failure; company-less jobs now bail before the local removal. |
| FEED-09 | fixed | A 404 on `?job=` leaves the panel empty (new `deadPinRef` stops the auto-focus), drops `?job=` instead of rewriting it, and toasts “That job no longer exists”. |
| FEED-10 | already fixed by F-007 | `main.py:230-240` `DataError` → 404 covers every id route; nothing left to change. |
| FEED-11 | fixed | `loadError` state → “Couldn't load jobs · Try again” row + `error` toast (suppressed on 401, where the LoginModal already fires). |

All six JSX fixes are **fixed in source, rebuild pending** — none are in the served bundle. No backend file was
touched; the only backend change these findings needed (FEED-10) is already in `main.py`.
