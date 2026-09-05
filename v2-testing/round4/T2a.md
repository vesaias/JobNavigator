# Round 4 · T2 part A — frontend state matrix (Job Feed, Searches, Companies, Applications)

Branch `v2-redesign` @ `81df231`, bundle `index-D2u_A578.js`. Playwright inside the backend container against `http://caddy`, API key `pick-a-password`, theme `default`, light unless stated. Viewport 1440×900 unless stated. Live DB: 19 190 jobs · 6 searches · 126 companies · 377 applications.

Scripts: `scratchpad/r4c.py` (helpers) + `r4_00..r4_18` copied to `backend:/tmp/v2t/`. Screenshots: `v2-testing/artifacts/round4/t2a/` (183 PNGs).

**Method.** Every state that is not "the real data" was produced by `page.route` mocking of the screen's own list endpoint (empty body / one row / 500 / 401 / held-open for the loading case / `route.abort()` for backend-down) or by CDP `Network.emulateNetworkConditions` (slow 3G). Every *write* endpoint was mocked in the shortcut/undo pass, so no real row was mutated. Zoom is emulated the way a browser zoom actually behaves — CSS viewport `1440/z × 900/z` with `deviceScaleFactor = z` — because `Emulation.setPageScaleFactor` / `setDeviceMetricsOverride` is reset by Playwright's own viewport on navigation (the first attempt reported `window.innerWidth === 1440` at every zoom level and was discarded).

**Scratch rows.** One search, `ZZR4-T2A probe` (id `37952e83…`), created via the API, run once (one small JobSpy/LinkedIn call, 0 results), deleted at the end. Text typed into the New-search card, the Companies drawer (`ZZR4-T2A-alias`) and the Log-application modal (`ZZR4-T2A typed title`) was always discarded, never saved. Final sweep: 0 `ZZR4-T2A` rows in searches, companies, applications, résumés and jobs; `/monitor/active` empty. The two `ZZR4-Base*` résumés belong to another round-4 track and were only read.

---

## Findings

### R4-T2A-01 · P2 · Job Feed · widths 1024 and 900 — the detail pane clips its own header actions
The list column is a hard `width: 472, flex: 0 0 472px` (`JobFeed.jsx:937`) and never narrows, so the detail `<section>` absorbs every pixel lost. At 1024 it is 346 px and the header row (`Open ↗` · `Tailor résumé` · `⋯`) is cut mid-word — the screenshot shows `Ta`; the report band reads `Score at full depth to see the r…`. At 900 the pane is 222 px and all three controls are entirely outside the viewport, with the job title clipped as well. The overflow is `overflow: hidden`, not scrollable, so the buttons cannot be reached at all — `document.documentElement.scrollWidth === innerWidth` while 11–12 descendants report `getBoundingClientRect().right` up to 1185 px. Collapsing the rail (+156 px) is the only workaround.
**Repro** `/v2/feed` at 1024×860 → look at the detail header. **Screenshots** `t2a/feed-w1024.png`, `t2a/feed-w900.png`.
**Status**: needs decision

### R4-T2A-02 · P2 · Applications · loading — no reserved shell, the whole screen is blank
`Applications.jsx:306` is `if (!loaded) return <div style={{flex:1, background:'var(--bg)'}} />`, so until `GET /api/applications` settles there is no page title, no toolbar, no stage headers — just an empty pane beside the rail. Measured with the list endpoint held open: `document.querySelector('h1') === null` at 200 ms *and* at 2 s; the shell only appears when the request resolves. On slow 3G that is ~10 s of blank pane. The other three screens all keep their box (Feed paints title, filter bar, count line as `NBSP` and "Select a job."), so this is the odd one out; it also means a first-load failure is preceded by nothing at all.
**Repro** hold `GET /api/applications` (or throttle to slow 3G), load `/v2/applications`, screenshot at 200 ms. **Screenshots** `t2a/applications-loading-200ms.png`, `t2a/applications-loading-2s.png`, `t2a/applications-slow3g-early.png` (contrast: `t2a/feed-loading-200ms.png`).
**Status**: needs decision

### R4-T2A-03 · P2 · Applications · width 900 — the detail pane collapses into overlapping controls
Same fixed 472 px list column. At 900 the detail pane is 222 px: the four stage cells of the `Segmented` stepper overlap each other (`App|Interview|Offer|Rejected` collide, text on text), the meta sentence breaks to roughly one word per line, the `⋯` button is half cut, and `⧉ Generate prep handover for AI` overflows the pane to `right: 999` (99 px past the viewport). 12 overflowing descendants. At 1024 the same screen is still acceptable (the history rail wraps under the body), so the failure starts below 1024.
**Repro** `/v2/applications` at 900×860 with a row selected. **Screenshot** `t2a/applications-w900.png` (compare `t2a/applications-w1024.png`).
**Status**: needs decision

### R4-T2A-04 · P3 · Companies · width 900 — the sticky actions cell covers the Status pill
`.v2-cactions` is `position: sticky; right: 0` with an opaque ground (`Companies.jsx:510`). At 900 the row is wider than the pane, so the cell parks on top of the Status column and clips every `Active` pill mid-word. The column head also overflows: one empty spacer `<span style={{flex:'0 0 190px'}}/>` reports `right: 932` against a 900 px viewport, so the head and the rows no longer share an axis. Clean at 1024 and 1440 (the four sheddable columns drop as designed — `showResumes ≥1130`, `showAts ≥998`, `showFit ≥890`, `showApps ≥842`), and the code comment at `Companies.jsx:361` names 1024 as the design floor.
**Repro** `/v2/companies` at 900×860. **Screenshot** `t2a/companies-w900.png` (compare `t2a/companies-w1024.png`).
**Status**: needs decision

### R4-T2A-05 · P3 · Searches, Companies, Applications — an outside click that dismisses a menu also fires the control underneath
These three screens close their menus from a bare `document.addEventListener('click', …)` with no backdrop, so the dismissing click keeps travelling. Measured:
* **Companies** — Sort menu open, click over a company row → menu closes **and the edit drawer opens** for that row (`{menus:0, dialogs:1}`).
* **Applications** — Company filter open, click over a list row → menu closes **and the selected application changes** (detail moved from row 0 to row 9).
* **Searches** — a card's `⋯` menu open, click on another card's title → menu closes **and that card's inline editor opens** (`input[aria-label="Max pages · 1–50"]` count 0 → 1).
The Job Feed does it correctly: `Drop` renders a `position:fixed; inset:0; zIndex:44` backdrop, and the same probe leaves the selected row unchanged (`0 → 0`).
**Repro** open any of those menus, click over a row. **Screenshots** `t2a/companies-probe-outsideclick.png`, `t2a/applications-probe-outsideclick.png`, `t2a/searches-probe-outsideclick.png`, `t2a/feed-probe-outsideclick.png`.
**Status**: needs decision

### R4-T2A-06 · P3 · all four screens — two tabs never converge
No screen re-reads its list on window focus, on a timer, or from a `storage` / BroadcastChannel event; the only pollers are `/monitor/active` (Searches, Companies — and only while something is already running) and `/monitor/in-flight` (Feed). With two tabs open on `/v2/searches`, pausing a search in tab A left tab B showing the stale pill after 12 s idle, after `bring_to_front()`, and after a synthetic `focus` event; only `reload()` picked it up. The rail badges are the same — `loadCounts()` only re-runs on the in-page `jn:counts-changed` event. Nothing warns the user, so tab B will happily write over what tab A changed.
**Repro** two tabs on `/v2/searches`, toggle Active in A, watch B. **Screenshots** `t2a/twotab-A-after-change.png`, `t2a/twotab-B-stale.png`.
**Status**: needs decision

### R4-T2A-07 · P3 · Searches — a Test run does not survive a reload and cannot be recovered
`POST /searches/{id}/test` never registers with `job_monitor` (`routes_searches.py:186-224` runs keyword tests synchronously and the slow modes through a bare `asyncio.create_task` into the module-level `_test_results` dict), so `GET /monitor/active` is empty for the whole preview — verified live, `[]` while a test was in flight. The spinner lives only in the component's `testingId`, so a refresh during a test loses the spinner *and* the result: after the reload there is no dialog, no busy pill and no message, while the backend may still be finishing the run and parking a result nobody can reach. Contrast with the two paths that do resume correctly (verified by serving a fabricated `/monitor/active`): a `search_run` restores `Running` + "running now. Results appear in the Job Feed as they are found."; a `company_scrape` restores `scraping now…` + `Running` (from `company_id` *and* from a bare `scope_key`); and a Feed job carrying `in_flight: ['analyze_job']` restores the busy ring and the "Scoring in progress" band across a reload.
**Repro** start a Test on a keyword search, reload while it runs. **Screenshots** `t2a/resume-searches-testing.png`, `t2a/resume-searches-testing-reload.png`, and the working cases `t2a/resume-searches-running.png`, `t2a/resume-companies-running.png`, `t2a/resume-feed-inflight-reload.png`.
**Status**: needs decision

### R4-T2A-08 · P3 · all four screens — the header count line reports 0 after a failed load
A 500, a 401 and an aborted request all leave the subtitle asserting zeroes next to a body that says the load failed: `0 open roles · 0 arrived today · 0 not yet scored`, `0 configs · 0 active`, `0 tracked · 0 active · 0 need attention`, `0 applications · 0 interviewing · 0 offers`. Companies also paints `Tier A 0 / Tier B 0 / Tier C 0 / Untiered 0` and Applications keeps `APPLIED 0 · INTERVIEW 0 · OFFER 0 · REJECTED 0` above the error. The rail gets this right — a failed badge keeps its slot empty rather than printing 0 (`V2App.jsx:108-113`) — and `Applications.jsx:73` already keeps `total` at `null` until the first fetch lands, but `shown = total ?? apps.length` then falls back to `0`.
**Repro** mock any list endpoint to 500 and read the subtitle. **Screenshots** `t2a/feed-err500.png`, `t2a/searches-err500.png`, `t2a/companies-err500.png`, `t2a/applications-err500.png` (+ `-dark` variants).
**Status**: needs decision

### R4-T2A-09 · P3 · shell · backend down — the rail health dot stays green
With every `/api/**` request aborted the rail reads a green dot and `No scrape recorded yet` — the same thing a fresh install shows. `healthy = failing === 0 && health?.status !== 'failed'` (`V2App.jsx:142`) has no "unknown" state, so an unreachable backend is indistinguishable from a healthy one that has never run. The screens behind it are all showing their error states at the same time.
**Repro** `page.route('**/api/**', abort)`, load any v2 screen, read the rail footer. **Screenshot** `t2a/companies-down.png` (also `feed-down`, `searches-down`, `applications-down`).
**Status**: needs decision

### R4-T2A-10 · P3 · Companies drawer — the résumé helper contradicts "Score new jobs automatically: Off"
`Drawer.resumeHelp` (`Companies.jsx:586`) only looks at `selected_resume_ids`, never at `auto_scoring_depth`, so a company with depth **Off** still reads "New jobs are scored against PM." with the PM chip lit. The Add-company modal gets this right (`scoreNote`, `Companies.jsx:765`, says "New jobs arrive unscored — you can score them by hand from the feed." when depth is off).
**Repro** open any company whose depth is Off (e.g. Addepar). **Screenshot** `t2a/companies-drawer-bottom.png`.
**Status**: needs decision

### R4-T2A-11 · P3 · Job Feed — infinite scroll silently drops rows; some jobs are unreachable
With the Status filter opened to every status (19 190 rows) and `sort_by=score`, six page loads of `limit=40` produced 40 → 78 → 118 → 156 → 185 → 222 → 256 rows: 24 of 240 fetched rows were duplicates that `loadMore`'s `seen` set discarded (`JobFeed.jsx:326`). The backend has no tiebreaker on any sort — `order_by(desc(Job.best_cv_score).nullslast())`, `desc(Job.salary_max)`, `asc(Job.company)`, `desc(Job.discovered_at)` (`routes_jobs.py:122-129`) — so `LIMIT/OFFSET` over a tie-heavy column is non-deterministic in Postgres: every duplicate returned means another row was never returned, and it cannot be reached by scrolling. The client-side dedup hides the problem instead of surfacing it. (Fix belongs with T1: append `Job.id` as a final sort key.)
**Repro** set Status to all five values, scroll the list to the bottom six times, count `[data-row]`. **Screenshots** `t2a/feed-many-thousands.png`, `t2a/feed-many-scrolled.png`.
**Status**: needs decision

### R4-T2A-12 · P3 · all screens — `⧉` (U+29C9) renders as a missing-glyph box
Measured against the app's own `--sans` stack at 40 px: `⧉` = 24.0 px, exactly the advance of the unassigned codepoint U+FFFF (24.0), while `⚗` = 35.9, `✦` = 33.5 and `M` = 34.5 — i.e. it is falling through to `.notdef`. Visible as an empty rectangle in the 3× crop. Used in five places: the Feed's `⧉ Copy with tracked links` method card, the Searches row menu's `⧉ Duplicate`, the Applications `⧉ Generate prep handover for AI` pill and `⧉ Copy to clipboard` button, and `PromptDialog`'s `⧉ Copy`. Caveat: font availability is per machine — this is the container's Chromium font set, and a Windows/macOS user may have a face that covers U+29C9 — but the glyph is rare enough that it should not be load-bearing.
**Repro** `/v2/applications`, look at the prep pill. **Screenshots** `t2a/px-prep-glyph-x3.png`, `t2a/many-applications-light.png`.
**Status**: needs decision

### R4-T2A-13 · P4 · Companies — the Add-company modal throws typed input away on Escape
Escape (or a scrim click) closes the modal and clears every field with no confirmation: typed `https://jobs.ashbyhq.com/zzr4t2a`, pressed Escape, reopened → the URL field is `''`. The two neighbouring flows both guard: the Companies drawer raises "Discard changes? · Edits to <name> have not been saved." and the Applications Log modal raises "Discard this application? · Everything typed will be lost." (and Cancel on that confirm correctly leaves the typed title in place — verified).
**Repro** `+ Add company`, type a URL, press Escape, reopen. **Screenshots** `t2a/companies-add-ats.png`, `t2a/companies-drawer-discard.png`, `t2a/applications-log-discard.png`.
**Status**: needs decision

### R4-T2A-14 · P4 · Applications — Escape does not close the "+ Add interview" form
`useEscape` on this screen closes the filter menus, the prep modal, the interview *edit* form and the Log modal (`Applications.jsx:134`), but never `intForm`. Opening `+ Add interview` and pressing Escape leaves the card open with its four fields (`input[aria-label="What"]` count 1 before and after). The edit form even advertises "Escape cancels" in its own footer, so the add form is the inconsistent one.
**Repro** select an application, `+ Add interview`, press Escape. **Screenshot** `t2a/applications-interview-form.png`.
**Status**: needs decision

### R4-T2A-15 · P4 · Companies — the row `⋯` menu stays open behind the delete confirm
`deleteCompany` only calls `setMenuId(null)` inside `onConfirm`, so opening Delete from the row menu leaves the menu mounted (`{menus:1, dialogs:1}`) under the confirm's scrim. It is correctly *below* the scrim (`elementFromPoint` over the menu returns the z-70 scrim, `menuInsideScrim: false`), so it only reads as clutter, and Escape closes both; cancelling with the button leaves the menu open. The Feed clears its menu before raising the same dialog (`setRowMenu(null); ignoreCompany(j)`).
**Repro** row `⋯` → Delete company. **Screenshots** `t2a/companies-confirm-delete.png`, `t2a/companies-confirm-menu-stack.png`.
**Status**: needs decision

### R4-T2A-16 · P4 · Searches, Companies — the error headline and its detail line are the same sentence
On a network failure the block reads "Couldn't load companies" / "Could not load companies" / "Try again" — the second line adds nothing (on a 500 it at least appends " — boom"). Searches is identical ("Couldn't load your searches" / "Could not load your searches"). Applications does it well: "Couldn't load your applications" over "The server returned error 500. Try again. — boom".
**Repro** abort the list endpoint. **Screenshots** `t2a/companies-down.png`, `t2a/searches-down.png`.
**Status**: needs decision

### R4-T2A-17 · P4 · Searches, Applications — raw internal error text is shown verbatim
Live data on the Searches screen renders a Playwright call log as a card's summary line — `Page.fill: Timeout 30000ms exceeded. Call log: -waiting for locator("#username") · paused` — and a psycopg message on another — `A string literal cannot contain NUL (0x00) characters. · acknowledged 13h ago`; both are `last_error` passed straight through `summaryOf`/`warnTextOf` with no truncation, so the newline-flattened call log runs into the acknowledgement clause. The prep modal does the same with an Axios string: "Could not build the prep handover: Request failed with status code 500 — prep builder failed".
**Repro** `/v2/searches` with a failed LinkedIn/Jobright run; `/v2/applications` → prep with the endpoint at 500. **Screenshots** `t2a/many-searches-light.png`, `t2a/applications-prep-error.png`.
**Status**: needs decision

### R4-T2A-18 · P4 · Job Feed, Applications, Companies — popovers open on a half pixel
Every filter popover under the Feed's filter bar and the Applications toolbar lands at `top: 127.5` (Companies' Sort at `123.38`), because `Drop`/`POPOVER` anchor off the trigger's own rect and that row ends on a fraction (`91.5 → 122.5` for the Feed pill). Five of the six Feed popovers also open on a fractional `left` (`562.03`, `670.06`, `750.09`, `850.61`, `941.64`). Their 1 px `--menu-border` is therefore drawn across two device rows/columns. Faint rather than obvious in the 3× crop, but it is the same class of defect as D-19/RES-32 and neither `Drop` nor `Menu` has any pixel snap (`ModalPanel` has `useSnapTop`, popovers have nothing).
**Repro** open any Feed filter pill, read `getBoundingClientRect()` of `[role=menu]`. **Screenshot** `t2a/px-menu-top-x3.png`.
**Status**: needs decision

### R4-T2A-19 · P4 · Job Feed — Enter does nothing
The round-4 brief lists Enter (toggle detail, as in v1) among the Feed shortcuts. v2 has no Enter branch in the key handler (`JobFeed.jsx:610-623`) and the shortcuts popover does not claim one, so nothing is *broken* — but the v1 behaviour is gone and the key is unassigned. Every other documented shortcut works: `j`/`f`/`↓` next, `k`/`g`/`↑` previous (both clamp at the ends), `s` save + advance, `x` skip + advance, `a` mark applied, `e` and `o` each open the posting in a new tab, `r` opens the rescore modal, `t` the tailor picker, `c` navigates to the cover letter, Escape closes every overlay, Ctrl-click picks, Shift-click ranges.
**Repro** `/v2/feed`, press Enter. **Screenshot** `t2a/feed-shortcuts.png`.
**Status**: needs decision

---

## What passed

* **Overlays** — all 20 menus/popovers/modals/drawers opened, closed on **Escape**, and closed on an **outside/scrim click**: Feed (6 filter drops, Sort, shortcuts, row `⋯`, detail `⋯`, tailor picker, rescore modal, ignore-company confirm), Searches (row `⋯`, delete confirm, New-search card, inline editor, Test modal + error branch), Companies (Sort, row `⋯`, delete confirm, drawer + dirty-discard, Add modal, Test modal + error branch), Applications (Company filter, Sort, detail `⋯`, delete confirm, prep modal + error branch, Log modal + dirty-discard). The New-search draft resets on Escape exactly as Cancel does.
* **Undo toasts** — every path issues the right calls with the write endpoints mocked: `s` → `PATCH {saved,status}` then undo `PATCH {status:'new',saved:false}`; `x` → `PATCH {status:'skip'}` + revert; `a` → `PATCH {status:'applied'}` then the compound undo in order `DELETE /applications/{id}` → `DELETE /companies/{id}` → `PATCH` back, with the "Application removed" success toast (the R2-H-05 fix still holds); bulk skip → `POST /jobs/bulk-update` then one grouped revert + "Restored 3 jobs.".
* **Loading (except Applications)** — Feed, Searches and Companies reserve their full shell at 200 ms and the `h1`/`main` boxes are byte-identical at 200 ms, 2 s and after settle; nothing jumps, nothing flashes. Warm-start counters paint from cache and cross-fade.
* **Empty states** — all four read well and offer the right next step ("No open roles yet" with links to Searches/Companies; "No searches yet" + "+ New search"; "No companies yet" + the Add-company sentence; "No applications yet — mark a job applied in the Feed, or log one here."). Filtered-empty is distinct from database-empty on Feed, Companies and Applications.
* **401** — the shell's login modal opens over the v2 screen and the Feed suppresses its "Couldn't load jobs" toast on 401 as intended; the styling matches v2.
* **Throttled (slow 3G)** — no layout jump, no flash of wrong content; the rail badges hold their slots empty until the counts land.
* **Zoom 75 / 90 / 110 %** — zero overflow on all four screens at all three levels, sticky heads track the pane width, and every popover stays anchored to its trigger and inside the viewport.
* **Popover flipping** — the Feed's 288 px Salary drop right-aligns instead of overflowing at 900 (`left 230 → right 518`), and Companies' sticky actions cell stays inside the viewport at every width.
* **Back / forward** — `?job=` is kept with `replace: true`, so picking rows does not spam history; going Companies → back returns to the Feed with the same job open, the same H-1B filter and the same row count; forward returns to Companies.
* **Focus and hover** — every control takes a visible `box-shadow: rgba(63,107,82,.22) 0 0 0 2px` focus ring in tab order; the three search inputs use an accent border instead (`rgb(138,130,110) → rgb(63,107,82)`), so nothing is focus-invisible. Row hovers, the Feed's ♥/✕ rail cells and card hovers all respond.
* **Console** — zero `pageerror`s in every pass; the only console noise is the expected cross-origin `frame-ancestors` refusals from the posting iframe and the mocked HTTP failures.

---

## Coverage

| state | Job Feed | Searches | Companies | Applications |
|---|---|---|---|---|
| empty | ok | ok | ok | ok |
| one row | ok | ok | ok | ok |
| many (real data) | ok | ok | ok | ok |
| thousands (19 190) | **R4-T2A-11** | n/a | n/a | n/a (377 in one page) |
| error 500 | R4-T2A-08 | R4-T2A-08, -16 | R4-T2A-08, -16 | R4-T2A-08 |
| error 401 | ok (login modal) + R4-T2A-08 | R4-T2A-08 | R4-T2A-08 | R4-T2A-08 |
| loading (5 s hold, 200 ms vs settled) | ok | ok | ok | **R4-T2A-02** |
| backend down (abort) | R4-T2A-08, -09 | R4-T2A-08, -09, -16 | R4-T2A-08, -09, -16 | R4-T2A-08, -09 |
| throttled (slow 3G) | ok | ok | ok | R4-T2A-02 |
| modals / drawers / menus + Esc + outside click | ok | R4-T2A-05 | R4-T2A-05, -10, -13, -15 | R4-T2A-05, -14 |
| keyboard shortcuts | ok, R4-T2A-19 (Enter) | n/a | n/a | n/a |
| undo toasts | ok (save · skip · applied compound · bulk) | n/a | n/a | not exercised — the only undo here is "remove interview", which needs a real row |
| refresh mid-run | ok (in-flight ring) | **R4-T2A-07** (Test); Run now ok | ok | n/a |
| back / forward with state | ok | ok | ok | ok |
| two tabs | R4-T2A-06 | R4-T2A-06 | R4-T2A-06 | R4-T2A-06 |
| width 1440 | ok | ok | ok | ok |
| width 1024 | **R4-T2A-01** | ok | ok | ok |
| width 900 | **R4-T2A-01** | ok | R4-T2A-04 | **R4-T2A-03** |
| zoom 75 / 90 / 110 % | ok | ok | ok | ok |
| dark (empty + error) | ok | ok | ok | ok |
| pixel alignment of popovers | R4-T2A-18 | ok | R4-T2A-18 | R4-T2A-18 |
| glyph coverage | R4-T2A-12 | R4-T2A-12 | ok | R4-T2A-12 |

Totals: **19 findings** — 3 × P2, 9 × P3, 7 × P4. No P1.
