# Feed round 2 — six reported bugs

Fixed in source at HEAD 41d6b98 (branch `v2-redesign`). **Not rebuilt, not restarted, not committed.**
Measurements were taken against the *running* stack (pre-fix bundle) with Playwright inside the
backend container against `http://caddy`, plus the live API and run history.

Scripts (scratchpad): `feed2_companies.py`, `feed2_logs.py`, `feed2_logs2.py`, `feed2_measure.py`,
`feed2_measure2.py`, `feed2_measure3.py`, `feed2_v1.py`.
Data: read-only apart from 5 job status PATCHes, each restored to its recorded prior value
(HTTP 200 on every restore). No scratch rows created.

Touched `.py` files: `backend/scraper/sources/company_pages.py`, `backend/scraper/orchestrator.py`,
`backend/main.py`, `backend/tests/test_run_all_company_coverage.py` (new).
Touched JSX: `frontend/src/v2/JobFeed.jsx`, `frontend/src/v2/ui.jsx`,
`frontend/src/design-base/UiGallery.jsx` (git-ignored gallery).

Gates at exit: `py v2-testing/tools/stylelint.py` → 0 findings, exit 0 ·
`npx esbuild@0.21.5 --loader:.jsx=jsx` on all three JSX files → exit 0 ·
`pytest backend/tests` in the container → **886 passed** (was 880 + 6 new).

---

## F1 · The report panel opens over the iframe on jobs that have no report

**Root cause.** `reportOpen` is a *persisted* preference (`localStorage` `v2_feed_ui`), while the
band that obeys it renders on `dScored = reports.length > 0`, which is true for a **Light** score —
a number in `cv_scores` with nothing in `scoring_report`. So once the user had ever opened a report,
every later Light-scored job opened an empty panel (its body is the single line "This report was
quick-scored…") that took `flex: 1 1 0%` and pushed the posting container to `display: none`.

**Measured** (`feed2_measure2.py`, job `56ccec75` Camunda, `cv_scores {"PM": 63}`, `scoring_report {}`,
`v2_feed_ui = {reportOpen:true}`): detail children =
`[header 143px flex, report band **619px** flex, posting container **display:none**, height 0]`,
body text contains "quick-scored". The iframe is not on screen at all.

**Change.** `frontend/src/v2/JobFeed.jsx`
- `:797-798` — new derived state: `hasReport = reports.some(r => r.rpt)` and
  `reportShown = reportOpen && hasReport`. The persisted preference is kept; it just cannot open a
  panel that has nothing in it, so a job change to a report-less job stays collapsed and a change
  back to a job with a report restores the user's open state.
- `:1118, 1143, 1298` — band flex, report body and the posting container's `display` all switch on
  `reportShown` instead of `reportOpen`.
- `:1123-1127` — with no report the band header is not a toggle: no `onClick`, no hover class, no
  caret, `cursor: default`.
- `:1133-1141` — the band line ends with "Score at full depth to see the report" and an xs
  **Full report** button instead of the "N reports" count. It opens the existing rescore modal
  preselected on Full (`:461, 479` — `loadRescoreOpts(preferDepth)` / `openRescore(job, preferDepth)`;
  every other caller is unchanged and still follows the `scoring_default_depth` setting).

Result: a Light-scored job shows only the band line (ring + résumé name + hint + button) with the
iframe below it at full height.

---

## F2 · "Run all" skips some companies

**Root cause.** `backend/scraper/sources/company_pages.py::scrape_career_pages` selected
`Company.active == True` **and `Company.playwright_enabled == True`**. That flag has no UI anywhere
in v1 or v2, and the companies the app creates for the user are born with it `False`
(`routes_applications.py:298`, `routes_jobs.py:632`, `routes_companies.py:324`); only
`POST /api/companies` sets it `True` (`routes_companies.py:214`). So a company that was created when
you marked a job applied, then activated and given a career-page URL, is invisible to run-all
forever — while `POST /api/scrape/company/{id}` (`main.py:651`, which never looks at the flag)
scrapes it happily. The interval check was *not* the cause: `run_all(force=True)` already
propagates `force` into `scrape_career_pages`.

**Reproduction from the live data** (no new run-all needed — the last one is on record):

| | |
|---|---|
| `GET /api/companies` | 126 companies · 61 active with non-empty `scrape_urls` |
| of those | **6 with `playwright_enabled=False`**: Anthropic, Arize, Scale, Sierra, Snorkelai, Airtable |
| `GET /api/monitor/history` | one `scrape_all` (manual) 2026-09-04 **10:58:59 → 11:11:16**, then six `company_scrape` (manual) runs at **11:27:14–11:27:33** |
| `GET /api/scrape-log` | the 10:58–11:11 window holds **57 rows: 55 `playwright_<company>` + jobright + levels_fyi**. Zero rows for any of the six. |
| the six at 11:2x | Anthropic 33 found, Scale 20, Sierra 18/+1 new, Arize 5, Snorkelai 5, Airtable 4 — all clean, no errors |

i.e. run-all covered 55 of 61 eligible companies, and the user then had to run exactly the six
skipped ones by hand. Secondary skips found by reading the loop: an active company whose
`scrape_urls` are empty/blank is dropped silently, and anything raising outside
`scrape_single_career_page`'s own `try` (browser death, a DB error while writing the audit row)
ended the whole remaining batch.

**Change.**
- `backend/scraper/sources/company_pages.py:387-437` — the gate is now `active` + "has at least one
  non-blank scrape URL". `playwright_enabled` is no longer consulted (the column stays in the model
  and the API for back-compat). Companies dropped for having no URLs are collected with a reason.
- `:459-472` — the interval check is unchanged in behaviour (still skipped when `force=True`, so a
  **manual** run-all runs every active company with URLs) but a skipped company is now recorded as
  `not due (Nm of Mm)`; naive `last_scraped_at` values are treated as UTC instead of raising.
- `:480-511` — every company runs inside its own `try`. A failure logs, rolls the shared session
  back, writes that company's own `ScrapeLog` error row through `record_company_scrape_log` (own
  session), counts as `failed`, and the loop continues.
- `:519-524` — returns `{"scraped": n, "failed": n, "skipped": [{name, reason}, …]}` and logs the
  skip list.
- `backend/scraper/orchestrator.py:323, 335` — `run_all` keeps that summary and returns
  `{"companies": …}` (callers that ignore the return are unaffected).
- `backend/main.py:367-379` — `POST /api/scrape/run-all` appends it to the run summary:
  `… - 3 skipped: Foo (no scrape URLs), Bar (no scrape URLs), … +N more`.

**Tests** — `backend/tests/test_run_all_company_coverage.py` (6 new): a `playwright_enabled=False`
company is scraped by a manual run; `force=True` ignores the interval; `force=False` still honours it
and names the skip; one company raising does not stop the others and leaves its own error ScrapeLog
row; active companies with no/blank URLs are named as skipped while an inactive one is not; and
`run_all` hands the summary up. Full suite: 886 passed.

**Needs a backend restart to take effect** (uvicorn has no reload).

---

## F3 · After skip/save/apply the list keeps the old row and iframe

**Root cause.** Not the local list write — that was already immediate — but *who owns the panel*.
`focusAt` was the only place that released `pinnedRef` (the `?job=` permalink pin), and the rail
buttons (♥ / ✕ / ⋯) stop propagation, so they never go through it. The feed keeps `?job=` in the URL
at all times, so any reload or deep link re-arms the pin; after that, the `[jobs, loading]` effect
takes its `else if (pinnedRef.current) setSel(-1)` branch and never advances.

**Measured before the fix** (`feed2_measure.py`, page opened at `/v2/feed?job=b82d1d80…`, then the
row's ✕ clicked): rows 12 → 11 immediately, but at +300 ms, +1 s and **+3 s** the detail title was
still `"Product Manager- Electronic Trading"` (the skipped job), `location.search` still
`?job=b82d1d80…`, and no row was selected (`selected: -1`).

**Change.** `frontend/src/v2/JobFeed.jsx`
- `:312-323` — `focusAt(idx)` split into `focusJob(job, idx)` + `focusAt`. `focusJob` releases the
  pin, sets `sel`, the detail and the iframe state, so any caller can open a job by object.
- `:340-378` — `patchLocal` is now `patchLocalMany(ids, changes)` (one row or a bulk set) and owns
  the transition: when the new status leaves the current view (`leavesView`, which knows the
  "empty filter = new+saved" rule) it removes the rows, decrements `total`, refills below 12 rows,
  and — if the open job was one of them — calls `focusJob` on the next surviving row (falling back
  to the previous one, then to an empty panel) in the same tick. The iframe follows because
  `focusJob` sets its state. `setTotal`/`loadMore` also moved out of the `setJobs` updater, where
  they were render-phase side effects.
- `:608-609` — the keyboard `s`/`x` no longer step by hand when the row leaves the view (that is now
  `patchLocalMany`'s job, and it works off the post-removal list instead of the stale one); they
  still advance when the row stays, e.g. saving while the Status filter shows "saved".

The undo toast path is untouched (still `showUndo` after the PATCH resolves). Click and keyboard now
share one advance.

---

## F4 · The iframe takes longer to appear than in v1

**Root cause.** v1 (`frontend/src/components/JobFeed.jsx:1309-1315`) mounts
`<iframe key={job.id} src={job.url}>` in the same render as the selection — no probe. v2 called
`GET /api/jobs/{id}/frame-check` on every selection and rendered *nothing*
(`frameOk === null` → an empty `div`) until it answered. That endpoint
(`backend/api/routes_jobs.py:708`) is a **server-side fetch of the posting** (12 s timeout).

**Measured** (`feed2_measure3.py`; "blank gap" = h2 title change → the posting area first shows
anything):

| row | host | title at | posting area at | **blank gap** |
|---|---|---|---|---|
| 2 | Microsoft | 6 ms | 1882 ms | **1877 ms** |
| 3 | PayPal | 5 ms | 928 ms | **923 ms** |
| 4 | Visa | 5 ms | 812 ms | **808 ms** |
| 5 | Microsoft (2nd time) | 4 ms | 62 ms | 57 ms |

Matching `frame-check` API latencies from the same run: 1827 / 917 / 805 ms.
(v1 could not be driven in the container: at `/` its default filters return "0 jobs found" against
this DB, so there was no row to click — `feed2_v1.py`/`feed2_v1b.py`. Its gap is 1 render by
construction: the `src` is set in the same commit as the selection.)

**Change.** `frontend/src/v2/JobFeed.jsx`
- `:14-22` — `FRAME_KEY = 'v2_feed_frameable'` per-host cache in `localStorage` (`{host: 1|0}`,
  capped at 300 entries) + `hostOf()`.
- `:165-169` — `frameOk` now starts `true`; `frameGuess(url)` returns `false` only for a host already
  measured as blocked, so a known-bad host shows the "refuses to be framed" panel with no wait and
  everything else renders the live frame immediately.
- `:316, 670` — `focusJob` and the `?job=` deep-link path seed `frameOk` from `frameGuess` instead
  of `null`.
- `:640-654` — the probe still runs, but only **once per host**, in the background, and only writes
  its answer to the cache + state (guarded on the panel still showing the same job). A failed probe
  leaves the optimistic frame up, as v1 would.
- `:1311` — the render drops the `frameOk === null` blank branch: `extActive || frameOk !== false`
  → iframe, otherwise the unchanged frame-blocked panel.

Expected after the fix: 0 ms wait for a cached host and for any first visit (the frame mounts at
once); a first-seen blocking host shows the frame for ~0.8–1.9 s before it swaps to the fallback
panel, and never waits again.

---

## F5 · The list is slow to reflect status updates

**Measured on the single-row path — already optimistic, nothing to fix**: clicking a row's ♥ flips
the row's badge in **3 ms** (`feed2_measure2.py`); `patchLocal` writes local state before the PATCH
is even sent.

**The slow path is the bulk bar.** `bulkStatus` did `await api.post('/jobs/bulk-update')` and then
`fetchJobs()`, which sets `loading` — so the whole list is replaced by its "Loading…" state for the
POST + full `GET /jobs` round trip. Measured (`feed2_measure3.py`, 3 rows Ctrl-picked, Skip):
**12 rows → 0 rows 21 ms after the click**, and back only when the reload landed.

**Change.** `frontend/src/v2/JobFeed.jsx`
- `:566-582` — the bulk write goes through `patchLocalMany(ids, updates)` first (rows patched in
  place, or removed with the panel advancing per F3), then the POST; success only calls
  `refreshStats()` and pushes the undo toast, failure falls back to `fetchJobs()`. No `loading`
  state, no blank list. The undo snapshot is taken before the local write, as before.
- `:1027` — the row's ♥ now carries the saved state itself (`--accent` when saved, title
  "Save/Unsave"), so the control the user clicked answers immediately instead of only the badge
  beside the title.

Row *position* is not touched: none of the four sorts (score, date, salary, company) is a function
of status, so a status change never moves a row that stays in view.

---

## F6 · The score-loading spinner in a row is larger than the row's ring

**Root cause.** The row's busy state was `<Spinner size={44}>` filling the whole 44 px slot, while
`ScoreRing size="md"` draws its arc at `r=35 + stroke/2 = 37.5` units in an 88-unit viewBox scaled
to 44 px → a **37.5 px** circle with a 2.5 px band. So the spinner was 6.5 px wider with a 1.5 px
band, and the row jumped when the score landed. (The report band's version, `Spinner size={28}
weight="bold"` in a 34 px box, was near-correct: the `sm` ring draws 32.7 px at 2.18 px.)

**Change.**
- `frontend/src/v2/ui.jsx:922, 934-943` — `ScoreRing` gains a `busy` prop: the same `viewBox`, `r`,
  stroke and box as the value state, with an indeterminate quarter-arc
  (`--ring-accent-border` on `--ring-track`) spun by the existing `.v2-spin` keyframes. No token
  changes, no new geometry constants; the doc block above the primitive says so.
- `frontend/src/v2/JobFeed.jsx:989` — the row uses `<ScoreRing busy size="md">`, keeping the accent
  `···` marker as its child.
- `:1288` — the report band's running state uses `<ScoreRing busy size="sm">` too, so the two
  loading states share one drawing and cannot drift again. `Spinner` is no longer imported by
  JobFeed.
- `frontend/src/design-base/UiGallery.jsx:366-386` — a "busy — md · sm (same box + arc as the score
  it replaces)" row beside a real `md` ring, and the note mentions `busy`.

---

## Open / for the user

- **F2 needs `docker compose restart backend`**; F1/F3/F4/F5/F6 need a frontend rebuild. Nothing was
  rebuilt, restarted or committed here.
- `Company.playwright_enabled` is now dead weight: it is still stored and returned by
  `GET /api/companies` but nothing reads it. Removing the column (or giving it a UI) is a separate
  decision.
- `scrape_single_career_page` returns early when a company yields **0 jobs**, so `last_scraped_at`
  is not written on empty runs — spotted while reading, not part of any of the six reports, not
  changed.

---

## Right-side collapse (per design)

The earlier read of this was wrong. It searched the **old** Claude Design project
("JobNavigator Frontend 2.0 Redesign", `298bd32b-…`), concluded the board had no
whole-panel collapse, and instead turned the *header caret* into a title-only 48px
strip. The current board is in **"JobNavigator redesign approach"**
(`4d073a40-62f3-4af1-adc2-4f5acbae6a31`), file **`JobNavigator Redesign.dc.html`**
(2,272 lines), and it does have the control — it is not the header caret.

### What the board shows

A **grab-line**: a full-width strip at the very top of the detail `<section>`, *above*
the metadata header, that folds the **whole top of the right side** away — the header
**and** the score/report band together — so the posting iframe rises to the top of the
pane.

Markup, `JobNavigator Redesign.dc.html` **l.252-254** (first flex child of the detail
section, after the absolutely-positioned "Nothing to show" overlay):

```html
<div onClick="{{ toggleAnalysis }}" title="{{ analysisHint }}"
     style="flex:0 0 auto;display:flex;align-items:center;justify-content:center;
            height:11px;background:var(--surface-2);border-bottom:1px solid var(--line);
            cursor:pointer"
     style-hover="background:var(--line-soft)">
  <span style="width:44px;height:3px;border-radius:99px;background:var(--edge)"></span>
</div>
```

- **Where / what it looks like.** Not a caret and not a labelled control: an 11px band
  (12px with its 1px rule) spanning the full width of the detail pane, carrying a bare
  44 x 3 px rounded handle centred in it. No glyph, no text, no border of its own.
- **Colours → our tokens** (the board's palette block is the same one `theme.css`
  carries): band `var(--surface-2)`, rule `var(--line)`, handle `var(--edge)`, handle
  radius `99px` → `var(--radius-control)`. Hover: the band goes to `var(--line-soft)`
  — one notch darker in both themes.
- **What collapses.** Exactly two elements, both bound to the same flag:
  - **l.255** the header wrapper — `display:{{ headWrapDisplay }}` — the eyebrow, the
    title, the salary/location/H-1B line **and** the Open ↗ / Tailor résumé / ⋯ action
    row. The whole metadata header, at whatever size its own caret left it.
  - **l.301** the `dScored` wrapper — `display:{{ analysisWrapDisplay }}` — the score
    band line **and** the expanded report inside it. **Yes, the report strip goes too.**
  - `l.1734-1735` sets both from one value: `anaCollapsed ? "none" : "flex"`.
  - The board does **not** bind the two placeholder bands — the unscored "Score this
    role" line (**l.418**) and the "Scoring in progress" line (**l.429**) both keep a
    plain `display:flex`.
- **Collapsed state.** Nothing above the posting but the 12px grab-line itself. No
  one-line summary strip, no floating pill: **the grab-line is the re-expand
  affordance**, and it is the only thing that survives.
- **Collapsed height of the top area: 12px** (11 + 1px rule).
- **Hint text** (`analysisHint`, l.1736), used verbatim:
  `"Hide job details & analysis — posting only"` / `"Show job details & analysis"`.
- **Persistence.** `localStorage` key **`jn_feed_analysis_collapsed`** (`'1'`/`'0'`),
  read at l.1403-1404, written in `toggleAnalysis` at l.1737-1741 — its own key,
  deliberately outside the panel-prefs blob. It survives reloads **and job selection**:
  the board's select handler (**l.1545**) resets `report / menuFor / headMenu / checked
  / filterOpen / viewCached` and never touches this or `headOpen`.
- **Keyboard shortcut: none.** The board's whole `Component` has one lifecycle hook
  (`componentDidMount`, l.1388) and no key handler at all — no shortcut for this or for
  anything else on the Feed.

**Origin — `PanelB-CollapseAll.dc.html`** (193 lines). The concept was a "View" segmented
picker with three modes (l.150): `Everything` (head + report), `Report only`, and
**`Focus posting`** (`head:false, report:false`) — with a live *"Posting height {{ h }}"*
readout in its top bar (l.33, l.145: `900 - 42 - (head?96:56) - 54 - (report?300:0) - 36`).
The point of the artboard was that folding both bands is what buys the posting its
height. The final board keeps the outcome and drops the mode picker in favour of the
one grab-line.

### What was reverted

`646f8ee`'s metadata-collapse part, and only that part — the six bug fixes F1-F6 from the
same commit are untouched. `git diff 4c02e3e -- frontend/src/v2/JobFeed.jsx` now shows no
`headOpen` change at all; the header caret is byte-identical to its pre-commit form:

- `META_KEY` / `loadMetaOpen()` (the `jobnavigator_v2_feed_meta` key) removed; `headOpen`
  is back to `loadUI().headOpen ?? true` and rides in the `v2_feed_ui` blob again.
- the `toggleHead` callback and its `localStorage` effect removed.
- the `collapsedMeta` derivation removed.
- header pad back to `11px 30px 12px` collapsed, the caret cell back to a fixed `19x26`,
  the title's tooltip back to `d.title`, and the collapsed **`Helper` meta line is back**
  (`company · salary · location · H-1B · source · age`).

So the header caret is again a *shrink to two lines* (26px title + meta block → 17px
title + one Helper line), which is what the board's own `headOpen` does (l.259-276:
`headTitleSize` 26/17, `headBtnH` 36/30, and an `sc-if headClosed` summary span at
l.275). The two collapses are independent and stack, exactly as on the board.

### What was built

`frontend/src/v2/JobFeed.jsx`:

- `ANA_KEY = 'jn_feed_analysis_collapsed'` + `loadAnaCollapsed()` — the board's key and
  its `'1'`/`'0'` encoding.
- `anaCollapsed` state, a write-through effect, and `toggleAna`.
- the grab-line as the first child of the detail pane's `d` branch — 11px band,
  `var(--surface-2)` on `var(--line)`, a 44x3 `var(--edge)` handle at
  `var(--radius-control)`. Keyboard-reachable through `kb(toggleAna)` (tabIndex 0,
  `role="button"`, Enter/Space) plus `aria-expanded={!anaCollapsed}` and the board's
  `title`. **No shortcut** — the board has none, and every free letter is taken
  (`j k s x a u e o t c r v`, Enter, Escape).
- `HeaderRow` gets `display: anaCollapsed ? 'none' : 'flex'` (it spreads the caller's
  `style` last, so this wins over its own `display:flex`).
- the `dScored` band wrapper gets the same `display` binding — band line and expanded
  report together.
- the unscored and "Scoring in progress" bands keep their line, as on the board.
- `theme.css`: `.v2-grab:hover { background:var(--line-soft) !important; }`, next to the
  other rail hovers. It needs its own rule because the strip already *rests* on
  `--surface-2`, which is what `--hover-wash-bg` hovers to — `v2-hover-accent` would be
  invisible here. `!important` for the usual reason: the strip sets its background
  inline.

**One deliberate departure from the board.** The board computes
`postingDisplay: dScored && S.reportOpen ? "none" : "flex"` (l.1766) from `reportOpen`
alone, so collapsing while the report is open hides the band *and* the posting and
renders an empty pane. Here the posting is gated on a new `reportCovers = reportShown &&
!anaCollapsed`, so the report only covers the posting while the top is actually standing.

### Expected measurements

Computed from the padding, not measured — this was a source-only pass, nothing was
rebuilt, restarted or committed.

| Detail pane, top area | Open | Collapsed |
|---|---|---|
| grab-line | 12px (11 + 1 rule) | 12px |
| metadata header, `headOpen` | 142px | 0 |
| metadata header, header caret closed | 66px | 0 |
| score band line (scored job, report closed) | 51px (8 + 34 ring + 8 + 1 rule) | 0 |
| **total, scored job, head open, report closed** | **205px** | **12px** |
| **total, scored job, header caret already closed** | **129px** | **12px** |
| **total, unscored job** (its band stays) | 205px | 63px |

So on a scored job with the header open the posting frame gains **193px**; with the
header caret already closed it gains **117px**. Open ↔ collapsed is one click on the
grab-line, and the choice survives job selection and reload.

**Status**: fixed — the last commit's title-only header collapse was reverted, and the
board's actual control (the 11px grab-line that folds header + report band together)
was built in its place.

Verified: `py v2-testing/tools/stylelint.py` → `0 findings, 98 allowed, 0 css` (exit 0);
`npx esbuild@0.21.5 --loader:.jsx=jsx` parses clean; brace/paren/bracket balance net 0
against HEAD. Source-only — nothing rebuilt, restarted or committed.

---

## Iframe switch — the previous posting stays up until the next one loads

**Reported.** Stepping through the feed (click, or `j`/`k`) leaves the *old* posting in
the pane until the new one has painted. It is a browser artifact, not our state: assigning
a new `src` to a live `<iframe>` keeps the current document on screen while the next
navigation is in flight, so on a slow host the pane shows the wrong job for seconds.

**Fixed** in `frontend/src/v2/JobFeed.jsx`:

- **l.32-34** — `FRAME_LOAD_MS = 8000`, the safety window a frame gets before the pane
  gives up on it.
- **l.185-196** — `frameLoadId` / `frameDeadId` (both hold a *job id*, never a boolean)
  and `frameDoneRef`. The id is the stale-guard the whole fix turns on: a rapid `j`/`k`
  run can leave several timers alive, and each one only acts if its captured id is still
  the one on screen, so the newest job always wins and no cover is ever left behind.
- **l.688-694** — `cachedAvail` / `frameJobId` / `frameSrc` hoisted above the effects.
  `frameSrc` is the single source of truth for "the live frame is what this pane shows":
  it is null for the cached snapshot, for a host the F4 probe confirmed blocked, and for
  a job whose frame timed out — each of those falls through to the branch it already had.
  The render's `dCached` (l.864) now just reads `cachedAvail`.
- **l.695-712** — a `useLayoutEffect` on `[frameSrc, frameJobId]`: raises the cover, arms
  the 8 s timer, clears both on unmount. Layout, not a plain effect, so the cover is
  painted in the same frame as the empty iframe — otherwise `--iframe-bg` flashes once.
  On timeout the job is marked `frameDeadId`, which nulls `frameSrc` and routes it to the
  existing "This posting refuses to be framed" panel (Open in new tab / cached snapshot).
  Nothing is written to the F4 per-host cache — a slow host must not teach the cache that
  it is blocked.
- **l.713-716** — `settleFrame(id)`, the `onLoad`/`onError` handler; it drops the cover
  only if that job is still the selected one.
- **l.1390-1408** — the live branch. `key={`${frameJobId}|${frameSrc}`}` remounts the
  iframe per job, so the old document is destroyed the instant the selection changes
  instead of lingering. Its wrapper is `flex:1 · minHeight:0 · position:relative ·
  display:flex`, i.e. exactly the box the bare iframe used to fill, and the iframe keeps
  `flex:1 / width:100%` underneath — the cover is `position:absolute; inset:0`, so it
  never takes the frame out of flow and `onLoad` still fires normally. No layout shift.
- The cover itself: `--bg` ground, centred `Spinner size={12}` (the primitive's md step)
  over a `Helper` line reading `Loading stripe.com …` — `hostOf()` minus a leading `www.`.
  Tokens and primitives only; no colour, font, radius or shadow inline.
- `setFrameDeadId(null)` was added to both places that open a job (l.346 `focusJob`,
  l.729 the `?job=` permalink), beside the existing `setFrameOk(frameGuess(...))`, so a
  job that timed out once is given a fresh try when it is opened again.

**Unchanged.** The F4 optimistic per-host logic (`frameGuess`, the background
`/frame-check` probe, the `v2_feed_frameable` cache) is untouched; the cached-snapshot
iframe (`viewCached`) has no cover and no remount key; the "refuses to be framed" panel
and the "No posting URL captured" line are the same nodes as before.

**Behaviour now.** Selecting a job blanks the pane at once — neutral `--bg`, spinner,
`Loading <host> …` — and the posting appears the moment it loads. Holding `j` scrolls
through jobs with the cover following the selection; only the newest job's cover is ever
up. A posting that never loads inside 8 s hands over to the frame-blocked panel.

**Status**: fixed — source only.

Verified: `py v2-testing/tools/stylelint.py` → `0 findings, 98 allowed, 0 css` (exit 0);
`npx esbuild@0.21.5 --loader:.jsx=jsx frontend/src/v2/JobFeed.jsx` → exit 0; brace and
paren balance net 0 against HEAD 04b3508 (`{` `}` 1479 → 1496 each, `(` `)` 1781 → 1822
each). Not rebuilt, not restarted, not committed.

---

## Grab-line, re-read from the board (the user changed it)

Re-read from Claude Design project `4d073a40…`, `JobNavigator Redesign.dc.html`
(2272 lines now; the copy in `v2-testing/design/` is stale at 2257 and has no grab-line
at all). What the board draws today:

| | board (line) | before, in code | now |
|---|---|---|---|
| band | `position:absolute;top:0;left:0;right:0;z-index:20;height:12px` (l.252) | in-flow strip, `height:11px`, `--surface-2` ground, `border-bottom:1px --line` | as the board: a floating 12px hit area, no ground, no border |
| handle | `width:52px;height:4px;border-radius:99px;background:var(--edge)` (l.253) | 44 x 3, `--edge` | 52 x 4, `--edge` |
| ring | `box-shadow:0 0 0 3px var(--surface)` (l.253) | — | `.v2-grab > span` |
| hover | `background:var(--accent);width:64px` (l.253, `style-hover`) | strip ground → `--line-soft` | handle → `--accent`, 64px |
| transition | `background .12s,width .12s` (l.253) | none | same, plus the fold |
| state | `analysisWrapDisplay`/`headWrapDisplay` = `anaCollapsed ? "none" : "flex"` (l.1734-1735), persisted to `jn_feed_analysis_collapsed` (l.1737-1741) | same | same flag, animated |

The band no longer takes a row of its own: it floats over the top of the pane, so the
header starts at y=0 and the handle sits in its 20px (open) / 11px (header-caret closed)
top padding — and over the posting's first 12px when the top is folded away. Collapsed,
the pane top is now 0px of chrome instead of 12.

**The animation.** The board itself does not animate the collapse — it flips
`display:none`/`flex` (l.1734-1735), and the only transition it declares anywhere is the
handle's `background .12s,width .12s` (l.253); there are no `@keyframes` beyond `jnspin`
and no `prefers-reduced-motion` block. So .12s ease is the board's timing, and the fold
was built to it rather than invented:

- `theme.css` l.457-479 — `.v2-grab > span` (ring + `.12s` hover transition),
  `.v2-grab:hover > span` (the board hangs the hover on the handle; here the whole 12px
  strip is the trigger, because a 4px band is not a hover target — a deliberate
  departure), `.v2-fold` / `.v2-fold[data-collapsed="true"]` / `.v2-foldbody`, and a
  `prefers-reduced-motion: reduce` block that turns both transitions off.
- The fold is **`grid-template-rows: 1fr → 0fr` plus `opacity`**, at `.12s ease`, not
  `max-height`: the report band is `flex:1 1 0%` while the report is open and `0 0 auto`
  otherwise, and no single max-height holds both — a grid row travels the real content
  height in either state. `visibility:hidden` is layered on with a `0s linear .12s`
  delay so the folded header leaves the tab order the way `display:none` did, without
  cutting the fade short.
- `JobFeed.jsx` l.1138-1150 — the grab-line's new geometry (absolute, 12px, 52x4 handle);
  l.1152-1158 — the fold wrapper: `.v2-fold` carrying the flex the report band used to
  take (`reportCovers ? '1 1 0%' : '0 0 auto'`) with `.v2-foldbody` inside it, wrapping
  the header (l.1161) and the score band (l.1219) — the two the board folds together.
  Both dropped their own `display: anaCollapsed ? 'none' : 'flex'`; the wrapper's
  `data-collapsed` is the one switch now.
- `JobFeed.jsx` l.35-37, l.175-186 — `FOLD_MS = 200` and the `folding` flag. The body
  clips only while the fold travels: with `overflow:hidden` standing, the header's ⋯ menu
  (`position:absolute; top:100%`, l.1194) would be cut off.
- The unscored band and the "Scoring in progress" band stay outside the fold and keep
  their line when the top is collapsed, exactly as before.

**Status**: fixed — source only.

Verified: `py v2-testing/tools/stylelint.py` → `0 findings, 98 allowed, 0 css` (exit 0);
`npx esbuild@0.21.5 --loader:.jsx=jsx frontend/src/v2/JobFeed.jsx` → exit 0; JSX brace and
paren balance net 0 against HEAD 04b3508, `theme.css` braces balanced. Not rebuilt, not
restarted, not committed.
