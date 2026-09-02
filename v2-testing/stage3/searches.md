# Stage 3 — Searches

Tested: 2026-09-02, bundle `index-Dnrx3n0f.js` (HEAD `3819fe8`, screen source at `f60ec5e` when the bundle was built), themes light+dark, viewport 1440×900 (+ narrow passes at 1280, 1024×700 and 900×700).
Design: `v2-testing/design/Searches Ops.dc.html` (markup + the `text/x-dc` logic block, read in full)
Inventory: `v2-testing/inventory/v2-searches.md`
v1 reference: `frontend/src/components/SearchManager.jsx`
Scripts: `srch_1.py` … `srch_13.py`, `srch_cleanup.py` (scratchpad → `/tmp/v2t/`)
Artifacts: `v2-testing/artifacts/searches/*.png` (17 shots)

Console/pageerror/4xx log was **clean on every happy-path run** (`report(pg)` = 0/0/0/0). The only console output came from the deliberately intercepted failure runs, which is the defect described in SRCH-04.

---

## Findings

### SRCH-01 · P2 · Test-modal source chips never render — the modal reads `by_source`, every backend path sends `source_breakdown`
**Where** `frontend/src/v2/Searches.jsx:558` (now `:566`), route `/v2/searches` → Test modal
**Repro** Run Test on any search; the params strip's right-hand chip cluster (`linkedin 19`, `indeed 14`, …) is empty.
**Expected + why** The design's params strip authors four per-board chips (`Searches Ops.dc.html:228-231`). The backend emits `source_breakdown` on **every** preview path: `routes_searches.py:391` (keyword), `:621` (levels_fyi), `sources/jobright.py:730`, `sources/freehire.py:330`, `sources/linkedin_personal.py:1123`. No path has ever emitted `by_source`.
**Actual** With a realistic keyword payload (`source_breakdown: {linkedin:19, indeed:14, zip_recruiter:6, google:3}`) injected via route interception: `source chips rendered: 0`. `srcChip()` (`:560-566`) was dead code.
**Proposed fix** `const bySource = d.source_breakdown || d.by_source || {}`
**Status** fixed in source (rebuild pending)

### SRCH-02 · P2 · A preview that fails with HTTP 200 + `{"error": …}` is rendered as “No results returned.”
**Where** `Searches.jsx:395` / `:401` (the two `setTest({name, data})` sites), route `/v2/searches`
**Repro** Intercept `POST /api/searches/{id}/test` → 200 with `{"search_name": …, "error": "Cloudflare challenge page detected — scrape aborted", "config": {…}}`.
**Expected + why** The modal has a dedicated error branch (`:597-598`, red `var(--bad)`), and four backend sites return exactly this shape at HTTP 200: `routes_searches.py:154` (search vanished), `:170` (async wrapper `except`), `:217` (JobSpy `scrape_jobs` threw), plus `jobright.py:746-754`, `freehire.py:346-349`, `linkedin_personal.py:955-959`.
**Actual** Modal opened on the **data** branch: tabs `All (0) / Kept (0) / Filtered (0)`, table copy `No results returned.`, footer `0 kept · 0 filtered · 0 raw`. The error string was never shown. A user reads this as “the scrape ran and found nothing”, which is the opposite of the truth.
**Proposed fix** A `settle(data)` helper in `runTest` that routes `data.error` to the error branch; applied to both the sync-200 and the poll-200 paths.
**Status** fixed in source (rebuild pending)

### SRCH-03 · P2 · A 422 from `POST /searches` alerts “[object Object]”
**Where** `Searches.jsx:367`, `create()`
**Repro** Intercept `POST /api/searches` → 422 with FastAPI's real shape `{"detail":[{"type":"string_type","loc":["body","name"],"msg":"Input should be a valid string"}]}`.
**Expected + why** The message should name the offending field. `e.response?.data?.detail` is a **string** for `HTTPException` but an **array of objects** for a Pydantic 422, and an array is truthy, so it short-circuits the `|| 'Could not create this search'` fallback and gets stringified.
**Actual** `ALERT on 422: ["[object Object]"]` (measured).
**Proposed fix** An `errText(e, fallback)` helper that unpacks a string detail, joins `.msg` over an array detail, else returns the fallback; used at every failure site on the screen.
**Status** fixed in source (rebuild pending)

### SRCH-04 · P2 · `Toast.jsx` was never imported — toggleActive, runNow, delete and duplicate failed with zero user-visible feedback
**Where** `Searches.jsx:369, 373, 378, 382` (and `:315` for the list load); `HANDOVER.md` §“Error paths” asks for the `error` toast at every failure site
**Repro** Intercept each mutation with 500 and watch the UI.
**Expected + why** `Toast.jsx` defines an `error` kind whose `TTL.error = null` precisely so a failure cannot evaporate before it is read. Only `JobFeed.jsx` and `ResumeEditor.jsx` imported it.
**Actual** (all measured)
- `PATCH` 500 from the Active/Paused pill → `alerts: []`, `toasts: []`, pill silently stays `Active`. The user believes nothing happened; in fact the write failed.
- `POST /run` 409 → `alerts: []`, `toasts: []`, spinner cleared (see SRCH-06).
- `DELETE` 500 → `alerts: []`, `toasts: []`, row remains with no explanation.
- `PATCH` 500 from **Save changes** → `window.alert('Could not save this search')` (native dialog, and it discards the server's message).
- `GET /searches` 500 on mount → nothing at all (see SRCH-05).
**Proposed fix** Import `useToasts`/`ToastStack`; add a `fail(e, fallback)` helper that logs and pushes `{kind:'error', text: errText(e, fallback)}`; use it in `load`, `save`, `create`, `toggleActive`, `runNow`, `remove`, `duplicate`. `window.alert('Name is required')` becomes an error toast; `window.confirm` on delete is kept (the design authors no confirm modal).
**Status** fixed in source (rebuild pending)

### SRCH-05 · P2 · No loading and no error state for the list — a failed GET renders “No searches yet · 0 configs”
**Where** `Searches.jsx:299` (`searches` initialised to `[]`, no `loading`/`error` flag), empty branch at `:536`
**Repro** (a) load the screen normally and watch the first frame; (b) intercept `GET /api/searches` → 500; (c) → 401.
**Expected + why** An empty database and a broken backend must not look identical; the empty state's call to action (“Create one to start pulling roles into the Job Feed”) is actively wrong advice when the list simply failed to load.
**Actual** Both 500 and 401 render, verbatim: `"No searches yet\nCreate one to start pulling roles into the Job Feed on a schedule.\n+ New search"` with the header reading `0 configs · 0 active`. (On 401 the global `jn:unauthorized` handler at `App.jsx:137-141` does raise the LoginModal over the top — the underlying lie remains.) The same empty state also flashes on every mount before the first response lands.
**Proposed fix** `loading` + `loadErr` state set in `load()`; a quiet spinner row while loading, a `Couldn’t load your searches` + message + `Try again` row on failure, and the real empty state only when `!loading && !loadErr`.
**Status** fixed in source (rebuild pending)

### SRCH-06 · P2 · A 409 from Run clears the spinner although the run really is in flight
**Where** `Searches.jsx:373`, `runNow`
**Repro** Intercept `POST /api/searches/{id}/run` → 409 `{"detail":"search_run is already running"}` (the real response, `routes_searches.py:126-128`).
**Expected + why** 409 means the run *is* live. Clearing `running[s.id]` also stops the `/monitor/active` poll (the effect at `:328` bails when `running` is empty), so the card goes quiet until a full remount.
**Actual** After the 409 the button reads `↻ Run`, no spinner, no message.
**Proposed fix** Treat 409 as “keep the spinner”: return early with a `progress` toast instead of deleting the key.
**Status** fixed in source (rebuild pending)

### SRCH-07 · P3 · Every card in the list lands on a half pixel
**Where** `Searches.jsx:465` (name) and `:468` (summary), card container `:459`
**Repro** `assert_int_tops(pg, '.v2-card')`
**Actual** `{count: 6, fractional: 3, samples: [105.5, 256.5, 407.5]}`; card height 67.5px. 15.5px serif + 11.5px sans under Tailwind preflight's `line-height: 1.5` give 23.25 + 3 + 17.25 = 43.5 of content, + 22 padding + 2 border = 67.5, so every other card starts on `x.5` and Chrome rounds its 1px border away — the exact failure mode HANDOVER §Conventions describes.
**Proposed fix** Explicit integer line-heights: `lineHeight: '23px'` on the name span, `'17px'` on the summary span → 43 + 22 + 2 = 67px cards, integer tops throughout.
**Status** fixed in source (rebuild pending)

### SRCH-08 · P3 · Test-modal table rows land on `.75` px
**Where** `Searches.jsx:637` rows inside the modal panel at `:590`
**Actual** `{count: 5, fractional: 5, samples: [419.75, 453.75, 487.75, 521.75, 555.75]}`. Row *heights* are an exact 34px, so the borders do not alternate — the whole modal is offset because its own height is fractional (measured 389.5px) and it is vertically centred. The fractional height comes from the chrome: the params strip (11px × 1.5 = 16.5 + 18 padding), the footer (11.5px × 1.5 = 17.25 + 22) and the title row.
**Proposed fix** Integer line-heights on the params strip (17px), the footer summary (17px) and the modal title (26px), as done for the card list.
**Status** decided 2026-09-02: keep (row heights are integer; only the centred modal's total height is fractional)

### SRCH-09 · P3 · Header “N need attention” and the rail's “N sources need attention” count different things
**Where** `Searches.jsx:350-352, 356` vs `V2App.jsx:65-68, :74, :78-79`
**Actual** Header: `6 configs · 4 active · 1 need attention · …` — that 1 is *LinkedIn Recommended + Top*, flagged by its `last_error` (`Page.fill: Timeout 30000ms exceeded`). Rail: `1 source needs attention` — `GET /health/entities` returns `{"companies":[{"name":"Oracle",…}],"searches":[],"count":1}`, i.e. **zero** searches and one company. The two 1s are unrelated; they agree by coincidence today and will not tomorrow.
The screen's predicate (`last_error ‖ downMap[id] ‖ last_run_warning`) is deliberately broader than health's 3-run verdict, and the per-card ▲ triangles track the screen's predicate (measured: exactly 1 triangle, on the LinkedIn card, `color: rgb(154,91,40)` = `--warn`), so the screen is internally consistent.
**Proposed fix** Either narrow the header to `downMap` only, or label it distinctly (e.g. “1 search needs attention” vs the rail's cross-entity total).
**Status** fixed + verified after rebuild: the header's attention count uses `/health/entities` like the rail (row ▲ / drawer keep the broader predicate)

### SRCH-10 · P3 · The rail “Searches” badge diverges from the header count after create / duplicate / delete
**Where** `V2App.jsx:62` fetches `GET /searches` once and never refetches; `Searches.jsx:354` recomputes from its own `load()`
**Repro** Duplicate a search.
**Actual** Immediately after Duplicate: header `9 configs · 7 active · …`, rail badge `Searches 8`. After deleting the copy: header `8 configs`, rail still `8` (agreeing only by luck). Same divergence after Create (header 8, rail 6) and after Delete.
**Proposed fix** Have the shell expose a `refreshCounts()` via context (or an outlet context / custom event) that the screen calls after every mutation.
**Status** fixed + verified after rebuild: create/duplicate/delete dispatch `jn:counts-changed`; rail badge measured 6 → 7 → 6

### SRCH-11 · P3 · A legacy `url`-mode search shows a Mode dropdown reading “Keyword (JobSpy)”
**Where** `Searches.jsx:196-202`, `MODE_OPTIONS` at `:41-47` omits `url`
**Repro** Any row with `search_mode='url'`; open its editor.
**Actual** (measured on a scratch row) `Mode select value: 'keyword' | displayed: {"si":0,"shown":"Keyword (JobSpy)","opts":["keyword","levels_fyi","linkedin_personal","jobright","freehire"]}` — the DOM coerces the unmatched `value="url"` to the first option. The badge still reads `URL`, the `Direct URL` cell still renders, and the draft still holds `'url'` so a blind Save does **not** corrupt the mode; but the picker lies about the current state, and one click on it silently converts a legacy search.
**Proposed fix** Push a disabled `['url', 'Direct URL (legacy)']` option into `MODE_OPTIONS` when `d.search_mode === 'url'`.
**Status** closed: no `url`-mode search exists (modes in the DB: keyword, levels_fyi, linkedin_personal, jobright, extension, linkedin_extension); the backend still accepts the mode via API — removing it is a separate decision

### SRCH-12 · P3 · `toPayload` silently rewrites three fields the user just cleared
**Where** `Searches.jsx:123` (`location: d.location || 'United States'`), `:125-127` (`parseInt(x) || default`)
**Repro** Open a keyword search, clear Location, set Hours old = 0, Results wanted = 0, Save; read back via API.
**Actual** `{"location":"United States","hours_old":24,"results_wanted":50,"run_interval_minutes":0}` — the cleared Location came back as “United States” and both explicit zeros became 24/50, with no indication in the UI. (`run_interval_minutes: 0` is intended and survives correctly.) `location` is also sent for levels_fyi / jobright / freehire / extension searches, where it means nothing.
The non-numeric half of the concern is moot: the fields are `type="number"`, so letters cannot be typed at all (measured).
**Proposed fix** `?? ` instead of `||` for the numerics, and only default Location for keyword mode.
**Status** awaiting the user's call (explained in chat 2026-09-02): needs decision: is “0 hours old” a meaningful configuration, or is the coercion the intended guard-rail?

### SRCH-13 · P3 · Test modal is 980px wide; the design says 880px
**Where** `Searches.jsx:590` vs `Searches Ops.dc.html:218` (`width:880px;max-height:660px`)
**Actual** measured `w: 980` at 1440 and 1280 viewports.
Related, and **not** a defect: the inventory predicted horizontal overflow below 980px. Measured at 900×700 the panel shrinks to `w: 900, left: 0` with `document.scrollWidth === clientWidth` — it is a flex item and shrinks by default, so there is no overflow. At 1024×700 it renders at 980 with 22px of gutter.
**Status** decided 2026-09-02: keep 980 px

### SRCH-14 · P3 · Test-modal Salary column is 120px / 9.5px; the design says 92px / 10.5px
**Where** `Searches.jsx:629` + `:642` vs `Searches Ops.dc.html:241` + `:249`
**Actual** measured column widths `Source 80 · Company 200.1 · Title 307.9 · Location 116 · Salary 120 · Desc 44 · Status 66`. Design fixed bases: `80 / 116 / 92 / 44 / 66`. Salary is the only differing one, and its font is 9.5px against the design's 10.5px.
**Status** decided 2026-09-02: keep

### SRCH-15 · P3 · New-search card body and edit drawer paint `--bg`; the design specifies `#fdfcf9` → `--recessed`
**Where** `Searches.jsx:431` and `:523` vs `Searches Ops.dc.html:69` and `:150`
**Actual** measured `background-color: rgb(252, 251, 247)` = `--bg` (`theme.css:5`). `--recessed` is `#fdfcf9` light / `#221f19` dark (`theme.css:12`, `:80`) and the design→token map in the brief maps `#fdfcf9`→`--recessed` explicitly. HANDOVER §Conventions: “`--recessed` … for set-back rows”.
**Status** fixed + verified after rebuild: New-search card body and edit drawer paint `--recessed` (rgb 253,252,249)

### SRCH-16 · P3 · Header rule is full-bleed and the left gutter is 24px; the design insets the rule by 30px and pads symmetrically
**Where** `Searches.jsx:411` (`borderBottom` on `<header>`, padding `22px 30px 16px 24px`) and `:423` (body padding `14px 30px 24px 24px`) vs `Searches Ops.dc.html:52` (padding `22px 30px 16px`), `:61` (a separate divider `margin:0 30px`), `:63` (body padding `14px 30px 24px`)
**Actual** measured `header padding: 22px 30px 16px 24px`, `border-bottom: 1px rgb(226,221,208)` spanning the full 1234px content width.
**Status** awaiting the user's call (explained in chat 2026-09-02): needs decision: the 24px left gutter looks like a deliberate cross-screen shell convention — confirm and close, or restore the design's inset rule?

### SRCH-17 · P4 · Hovers present in code that the design does not author
**Where** `theme.css` classes applied in `Searches.jsx`
**Actual** every design `style-hover` is implemented and measured correct:
| element | design `style-hover` | measured |
|---|---|---|
| new/edit Cancel, Run, Test | `border-color:#3f6b52;color:#3f6b52` | `.v2-bdc` → borderColor + color → `rgb(63,107,82)` ✓ |
| Active/Paused pill, ⋯ | `border-color:#3f6b52` | `.v2-bd` → borderColor only ✓ |
| menu items | `background:#f3f0e8` | `.v2-menuitem` → `--surface-2` ✓ |
| Delete search | `background:#f7ecea` | `.v2-hover-bad` → `--bad-soft` ✓ |
| modal ✕ | `background:#f3f0e8;color:#1b1a16` | `.v2-hover-accent` → `rgb(246,244,238)` ✓ |
Extras the design does **not** author: `.v2-card` on the whole card (`border-color: --accent` + `background: --hover-soft`, measured), `.v2-bd` on the Sources/Collections chips, on the three depth pills and on the modal's three tabs, and `.v2-bdc` on the modal's **Close** button (design line 257 has no `style-hover`). Confirmed absent where the design also has none: the header “+ New search” pill (`changed: []`), and an open card correctly carries `className=""` with a measured empty hover delta.
**Status** decided 2026-09-02: keep the hovers (consistency)

### SRCH-18 · P4 · Card action cluster deviates from the design in five small ways
**Where** `Searches.jsx:479-499` vs `Searches Ops.dc.html:133-147`
**Actual** measured: actions wrapper `width 169, margin-left -11px, gap 3px` (design `flex:0 0 148px`, gap 4px, no negative margin); Run/Test padding `0 9px` (design `0 10px`); Active pill fixed at `flex: 0 0 62px` (design `padding:0 11px`, auto width); the extension placeholder reads `extension • passive capture` right-aligned (design `passive capture`, `justify-content:flex-start`).
The fixed-width pill is explained by an in-code comment (“so Active matches Paused and both sit on one vertical axis”) and was verified: both `Active` and `Paused` pills measure exactly `w: 62, h: 23`.
**Status** awaiting the user's call (explained in chat 2026-09-02): needs decision: all five read as deliberate alignment work — confirm, or restore the design metrics?

### SRCH-19 · P4 · `until()` has no day unit, so a two-day-out sweep reads “next scheduled run in 58h 20m”
**Where** `Searches.jsx:16-23`
**Actual** the real `scrape_all` next run is `2026-09-04T06:38` (interval 3500 min); the header renders `6 configs · 4 active · 1 need attention · next scheduled run in 58h 20m`. `ago()` does have a day unit (`:14`). The `m <= 0` branch also yields the odd “next scheduled run in any moment”.
**Status** awaiting the user's call (explained in chat 2026-09-02): needs decision: add `Xd Yh` above 24h?

### SRCH-20 · P4 · “last run 3d ago” and “next scheduled run in …” freeze until an unrelated re-render
**Where** `Searches.jsx:7-23`, computed at render time with no timer
**Actual** confirmed by reading; the numbers only moved between separate page loads in my runs (58h 20m → 58h 19m → 58h 18m across three fresh loads).
**Status** awaiting the user's call (explained in chat 2026-09-02): logged
### SRCH-21 · P4 · Escape closes the ⋯ menu and the test modal, but not the edit drawer or the New-search card
**Where** `Searches.jsx:343`
**Actual** measured: menu open → Escape → menu count 0 ✓; document click-away → menu count 0 ✓; test modal → Escape / backdrop / ✕ all close ✓; drawer open → Escape → drawer still open (child count stays 2).
**Status** awaiting the user's call (explained in chat 2026-09-02): logged
### SRCH-22 · P4 · New-card Cancel keeps the typed draft
**Where** `Searches.jsx:435` — only `create()` success resets `newDraft` (`:366`)
**Actual** typed `ZZTEST discarded draft` into Name → Cancel → reopen → Name is still `'ZZTEST discarded draft'`. (After a *successful* create the draft does reset correctly — measured `Name: ''`, `Hours old: '24'`.)
**Status** fixed + verified after rebuild: Cancel resets the New-search draft
### SRCH-23 · P4 · No concurrency guard on Test
**Where** `Searches.jsx:386` / `:395` / `:405` — a second Test overwrites `testingId`, and whichever finishes first clears the other's spinner and can replace its modal.
**Status** fixed + verified after rebuild: one Test at a time — other rows' Test buttons inert (opacity .5, title) and a second click on the running row is ignored

### SRCH-24 · P4 · `/health/entities` and `/scheduler/jobs` are fetched once and never refreshed
**Where** `Searches.jsx:319`, `:321` (mount-only), while `load()` re-runs after every mutation
**Actual** confirmed by reading + by the counts: after a run completes, `downMap` and `nextRun` are whatever they were at mount. Both fetches also swallow failures with `.catch(() => {})`.
**Status** fixed in source: `/health/entities` and `/scheduler/jobs` re-fetched after every mutation and when a run finishes (previous values kept on failure)
### SRCH-25 · P4 · The depth indicator advertises `cursor: help` but its click opens the editor
**Where** `Searches.jsx:470-477` — no `stopPropagation`
**Actual** measured `cursor: help`; clicking it opened the drawer (`child count === 2`).
**Status** decided 2026-09-02: keep
### SRCH-26 · P3 · The backend does not enforce the extension-search gating the UI applies
**Where** `routes_searches.py:73-100` (PATCH/DELETE unguarded), `:103-128` (`/run` unguarded); UI gating at `Searches.jsx:484-486`
**Actual** `POST /api/searches/{Extension LI id}/run` → **202** with a `run_id`; same for `Extension`. The run is a harmless no-op — `orchestrator._search_mode_is_valid()` (`:103-121`) returns `False` for both extension modes, so `_run_search_by_id` returns before any network call or DB write — but a `JobRun` row is created and appears in Stats › Run history. `POST /{ext}/test` **is** correctly blocked (400, “Test only supports keyword, levels_fyi, linkedin_personal, jobright, and freehire searches”). DELETE was **not** exercised, per the brief.
UI gating itself verified for both seeded rows: Run/Test/⋯ hidden, the `extension • passive capture` label present with the right tooltip, Mode rendered as a **disabled** input (`value "Extension (manual Save-to-Feed)"`, `background --surface-2`, `color --muted`, `grid-column: span 2`), no `<select>`, no Run-interval input, no Sources/Collections chips, the correct note banner, and the Active pill still live with the extension-specific tooltip (`Resume importing captured jobs` — toggled and restored).
**Proposed fix** 404/409 on `/run` and `DELETE` when `search_mode` is an extension mode.
**Status** awaiting the user's call (explained in chat 2026-09-02): needs decision: add a server-side guard (backend restart required), or accept UI-only protection?

### SRCH-27 · P4 · A preview row with a null `url` renders as a styled but dead link
**Where** `Searches.jsx:640`
**Actual** a job with `url: null` renders `<a>` with `href` absent — measured `href: null`, still painted `color: var(--text)` and clickable-looking. Same row also proved the screen survives `company: null`, `location: null`, `salary: null` (renders `—`) and a 200-character title (ellipsised, full text in `title=`).
**Status** awaiting the user's call (explained in chat 2026-09-02): logged
### SRCH-28 · P4 · The run poll tears itself down and rebuilds every 3s, and keys on any job's `scope_key`
**Where** `Searches.jsx:328-339` — effect deps `[running, load]`, and every tick calls `setRunning` with a fresh object; `:320`/`:334` accept every `scope_key`, so a company scrape or a résumé score keeps this screen re-rendering every 3s.
**Status** awaiting the user's call (explained in chat 2026-09-02): logged
### SRCH-29 · P4 · No pending state on “Create search” or “Save changes”
**Where** `Searches.jsx:436`, `:528` — a double click fires two POSTs (the backend has no duplicate-name check, `routes_searches.py:65-70`).
**Status** fixed + verified after rebuild: Create/Save show "Creating…"/"Saving…" and ignore clicks while pending (one POST under a double click)
---

## Verified working (highlights, all measured)

- **Create round-trip**: every field in the New card persisted exactly — `location "Austin, TX"`, `is_remote true`, `job_type "contract"`, `hours_old 72`, `results_wanted 37`, `sources ["linkedin","indeed","zip_recruiter","direct"]` (Google toggled off, Direct on), `title_include_keywords ["platform","backend"]`, `title_exclude_keywords ["intern","staff"]`, `company_filter ["Stripe"]`, `company_exclude ["Walmart"]`, `auto_scoring_depth "full"`, `run_interval_minutes 90`, `exclude_active_companies true`. Empty-name validation fires and keeps the card open.
- **Edit drawer per mode**: label sets measured for all six modes and match `fieldsFor()` in the design's logic block — keyword 8 cells + Sources chips; levels_fyi Max pages + a `span 3` URL cell; linkedin_personal Name+Mode only + 2 Collections chips + the Settings hint; jobright Search term/Results wanted/Min score + `sm-jobright` note; freehire term/URL(`span 2`)/Results wanted with both `sub` help lines; legacy url → Direct URL cell, Test button correctly absent. Note banners render only for levels_fyi / jobright / the two extension modes, with the right `sm-*` palettes in both themes.
- **Save → PATCH → reload** round-trips (`search_term`, `hours_old`, `auto_scoring_depth` read back correct); drawer closes on success and stays open on failure.
- **Duplicate** copies the whole payload and appends ` (copy)`; **Delete** confirms with the native dialog and only fires `DELETE` when accepted (dismiss → no request, measured).
- **Active/Paused toggle** flips the row, the pill label and the header's “N active” (7 → 6).
- **Run** with a live `/monitor/active` row: spinner element present, label `Running`, colour `--accent`, summary swapped to *“running now — results land in the Job Feed as they arrive…”* in `--accent`, tooltip swapped to *“Run in progress — …”*; all revert when the run leaves `/monitor/active`.
- **Test flow**: sync 200, async **202 + poll** (spinner survives the polling window, modal opens on the first 200, spinner clears), 404 on poll → *“Test run expired or not found”*, 400 → the backend's detail, 500 → the detail. Tabs filter correctly (All 5 / Kept 3 / Filtered 2 → 3 and 2 rows). Row rendering: `--bad-faint` background, line-through and `--muted` title for filtered rows, `✓/✕` Desc in `--accent`/`--line-strong`, `KEPT`/`OUT` pills with the reason in `title=`.
- **Tab counts vs footer**: verified agreeing by construction — every preview path appends exactly one result per unique raw row (`routes_searches.py:371-382`, `jobright.py:704`, `freehire.py:309`, `linkedin_personal.py:1101`), so `raw_count === jobs.length` and `after_filter === kept.length`.
- **F-005**: `run_interval_minutes = 45` + `active` on a scratch search produced `{"id":"search_<id>","name":"Search: ZZTEST keyword search","schedule":"Every 45 min (search override)","trigger_url":"/searches/<id>/run"}` in `GET /api/scheduler/jobs`, and the row disappears when the search is paused. `POST` on that `trigger_url` returned **202**.
- **Bad ids**: `POST /searches/<random uuid>/run`, `PATCH`, `DELETE` all → 404; `GET /searches/test-result/nope` → 404.
- **Deep link out**: ⋯ → View results in feed navigated to `/v2/feed?search=<id>` and the feed scoped to it.
- **Dark mode**: every measured surface differs from light with no light-only value surviving — cards `#28251b`/`#3e3b32`, warn edge `#6b5638` with a `#d4a06a` triangle, `+ New search` `#8dbb9f` on `#15140f`, modal panel `#28251b`, scrim `rgba(0,0,0,.58)`, sticky header + footer `#1e1c17`, filtered rows `#241a18` with `#d98a7e` OUT pills, `sm-jobright` note `#1f3432`/`#96c8c0`, drawer `#1e1c17` with `#28251b` inputs.
- **Narrow**: 1024×700 and 900×700 both render with `scrollWidth === clientWidth` — no horizontal overflow anywhere, drawer open or modal open.

---

## Fixed in source

All in `frontend/src/v2/Searches.jsx`; syntax-checked with esbuild; **rebuild pending**.

- `:4` — import `useToasts` / `ToastStack`.
- `:29-38` — new `errText(e, fallback)` helper: unpacks a string `detail`, joins `.msg` over a 422 array detail (SRCH-03).
- `:321-334` — `loading` / `loadErr` state; `load()` sets both and pushes an error toast (SRCH-04, SRCH-05).
- `:380-405` — `fail()` helper; `save`, `create`, `toggleActive`, `remove`, `duplicate` all surface an error toast; `window.alert` removed from the three sites (SRCH-04). `runNow` keeps the spinner on 409 and shows a `progress` toast (SRCH-06).
- `:418-438` — `settle(data)` in `runTest` routes a 200-with-`error` payload to the modal's error branch, on both the sync and the poll path (SRCH-02); the catch uses `errText`.
- `:503`, `:506` — integer `lineHeight` on the card name (23px) and summary (17px) (SRCH-07).
- `:574-591` — loading spinner row and a `Couldn’t load your searches` + `Try again` row; the real empty state now requires `!loading && !loadErr` (SRCH-05).
- `:599` — `<ToastStack>` mounted.
- `:612-615` — `bySource` reads `source_breakdown` first (SRCH-01).

No backend edits were made, so **no backend restart is needed**.

---

## Couldn't test

- **A real preview against a live board.** The Test flow's network half (`levels_fyi`, `jobright`, `linkedin_personal`, `freehire`) is off-limits under the data rules; every Test path was exercised with route interception using payload shapes copied from `routes_searches.py` / the source modules. Sync-200, 202+poll, poll-404, 400 and 500 were all covered.
- **A real search run.** `POST /run` was fired only against a scratch search whose config `_search_mode_is_valid()` rejects (no external work) and against the two extension searches (no-op by the same guard). The spinner lifecycle was driven by intercepting `/monitor/active`.
- **`DELETE` on the seeded extension searches** — explicitly forbidden by the brief, so the backend's missing guard there is inferred from `routes_searches.py:93-100`, not measured.
- **The StrictMode `mounted.current` trap** (inventory §7, `:311-312`) is a dev-server-only behaviour; the Docker bundle is a production build, so it cannot be reproduced here. Confirmed harmless in production by the working 202+poll run.
- **Two concurrent Tests** (SRCH-23) — would need two live previews.
- **Empty-database rendering** — a separate later pass per the brief.

---

## Scratch data

- Created: `ZZTEST keyword search` (via API, later mutated to `levels_fyi` then legacy `url` mode), `ZZTEST UI search` (via the New-search card), `ZZTEST UI search (copy)` (via Duplicate).
- Deleted: all three. `GET /searches` now returns exactly the original six rows with their original `active` values (`JobSpy` false, `3 Days Levels Search` true, `LinkedIn Recommended + Top` false, `Jobright 3 Days` true, `Extension LI` true, `Extension` true), and `GET /scheduler/jobs` has no `search_*` rows.
- Reversible edits to real rows, all restored and verified: `Extension`'s `active` toggled false → true (original true).
- **Residue that cannot be removed**: four `JobRun` history rows from `POST /searches/{id}/run` — two on `Extension LI` and two on `Extension` (the brief asked for this probe). All four are instant no-ops; they will appear in Stats › Run history dated 2026-09-02.
- **Scratch rows remaining: 0.**

---

## Summary

- **Inventory boxes: 160 total — 114 verified OK (`[x]`), 40 failed (`[!]`, each tagged with its finding id), 6 untestable (`[~]`, each with its reason).**
- **Findings: 29 — P1 0 · P2 6 · P3 10 · P4 13.**
- **Fixes applied: 9 edits covering SRCH-01 … SRCH-07 (frontend only, rebuild pending).** No backend change, so no restart needed.
- **Needs decision: 11** — SRCH-08 (modal half-pixels), SRCH-09 (attention predicate), SRCH-10 (rail badge staleness, cross-screen), SRCH-11 (legacy `url` picker), SRCH-12 (silent value coercion), SRCH-13 (modal width 980 vs 880), SRCH-14 (salary column), SRCH-15 (`--bg` vs `--recessed`), SRCH-16 (header rule inset / left gutter), SRCH-17 (unauthored hovers), SRCH-18 (action-cluster metrics), SRCH-26 (server-side extension guard).
- **Console clean** on every non-intercepted run, in both themes and at every viewport tested.
- **Scratch rows remaining: 0.**
