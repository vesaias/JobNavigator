# v2 Searches — screen inventory

Screen file: `frontend/src/v2/Searches.jsx` (668 lines, read in full). Shell: `frontend/src/v2/V2App.jsx`. Toast API: `frontend/src/v2/Toast.jsx` (NOT imported by this screen). Axios: `frontend/src/api.js`. Backend counterpart: `backend/api/routes_searches.py`, `backend/main.py` (monitor / scheduler / health endpoints).

All `file:line` references below are to `Searches.jsx` unless prefixed with another file name.

---

## 1. Routes & params

- [x] Route `/v2/searches` — registered as nested `<Route path="searches" element={<V2Searches />} />` under `/v2` (`App.jsx:153`, `App.jsx:159`). Rendered inside `V2App`'s `<Outlet />` (`V2App.jsx:158`).
- [x] Query params READ by this screen: **none**. `useSearchParams` is not used; `window.location.search` is never read.
- [x] Deep-link WRITTEN by this screen: `navigate('/v2/feed?search=${s.id}')` from the ⋯ menu item "View results in feed" (`506`). Consumer: `JobFeed.jsx:179` reads `?search=` and `JobFeed.jsx:183` resolves its name via `GET /searches`.
- [x] localStorage keys read/written in `Searches.jsx`: **none**.
- [x] localStorage read indirectly via the axios instance: `jobnavigator_api_key` (`api.js:11`, request interceptor → `X-API-Key` header).
- [x] localStorage read by the shell that wraps this screen: `jobnavigator_v2_rail` (`V2App.jsx:48` read, `V2App.jsx:55` write), `jobnavigator_dark_mode` (`V2App.jsx:52` read, `V2App.jsx:54` write).
- [x] 401 handling: `api.js:22-24` dispatches `jn:unauthorized` on any 401; the screen itself does nothing special on 401 (its catches swallow or `console.error`).

---

## 2. Data loads

### On mount (single `useEffect`, `317-325`, deps `[load]`)

- [x] `GET /searches` — via `load()` (`314-316`), called at `318`. Sets `searches`. Failure: `console.error(e)` only (`315`); list stays `[]`.
- [x] `GET /health/entities` (`319`) — builds `downMap[id] = reason` from `data.searches`. Failure: `.catch(() => {})` silently swallowed.
- [x] `GET /monitor/active` (`320`) — builds `running[scope_key] = true` for every row with a `scope_key` (ANY job type, not just `search_run`). Failure: swallowed.
- [x] `GET /scheduler/jobs` (`321-324`) — finds `id === 'scrape_all'`, stores `next_run` in `nextRun`. Failure: swallowed. Backend field: `main.py:804` (`"next_run": job.next_run_time.isoformat()`).

### Reloads triggered by actions

- [x] `load()` (`GET /searches`) re-run after: save (`362`), create (`366`), toggleActive (`369`), remove (`378`), duplicate (`382`), and whenever a polled `running` key disappears (`335`).
- [!] `/health/entities`, `/scheduler/jobs` are fetched ONCE on mount and never refreshed — `downMap` and `nextRun` go stale after a run finishes. — **SRCH-24**

### Polling

- [x] Run polling (`328-339`): while `Object.keys(running).length > 0`, `setInterval` every **3000 ms** → `GET /monitor/active`. If any previously-running key is now absent, calls `load()`. Errors: `catch { /* retry */ }` (`336`). Guarded by `mounted.current` (`333`). NOTE: effect deps are `[running, load]` and every tick calls `setRunning` with a fresh object, so the interval is torn down and recreated every 3 s.
- [~] Test polling (`385-406`): `POST /searches/{id}/test` with `timeout: 30000` (`388`). If response is **202** with `run_id` (async modes: `levels_fyi`, `linkedin_personal`, `jobright`, `freehire` — `routes_searches.py:143`), polls `GET /searches/test-result/{run_id}` (`timeout: 10000`) every **3000 ms**, up to **100** iterations (~5 min) (`390-399`). Stops on HTTP 200 (`395`); on 404 sets error "Test run expired or not found" (`397`); after 100 tries sets error "Test timed out after 5 minutes — check Stats › Run History" (`400`). While the backend still runs it returns 202 (`routes_searches.py:418`) and the loop continues. If the POST returns 200 directly (keyword mode runs synchronously, `routes_searches.py:180+`), result is used immediately (`401`). — _untestable: exercised via route interception only — no real preview allowed by the data rules_

---

## 3. Interactive elements

Legend: **API** = call(s) made; **State** = local state mutated; **Toast** = none of the handlers on this screen push a toast — `Toast.jsx` is not imported. Failure feedback is either `window.alert`, `console.error`, or nothing.

### 3.1 Header

- [x] **"+ New search"** pill button — `417-418` — inline `onClick`: `setNewOpen(v => !v); setEditing(null); setMenuFor(null)`. No API. Toggles the New-search card; closes any open editor and menu. No hover class.
- [x] Header count line — `414` — read-only text `countLine` (`353-358`). Ellipsis on overflow. See §8.

### 3.2 Empty state

- [x] **"+ New search"** text link in empty state — `540` — `onClick={() => setNewOpen(true)}`. No API. No hover class. Only rendered when `searches.length === 0 && !newOpen` (`536`).

### 3.3 New-search card (`425-440`, rendered when `newOpen`)

- [x] `<ConfigForm d={newDraft} set=…/>` — `432` — every field below (§3.6) mutates `newDraft` via `setNewDraft(x => ({...x, ...p}))`.
- [x] **Cancel** — `435` — `onClick={() => setNewOpen(false)}`. `.v2-bdc`. Does NOT reset `newDraft` — partially-typed values survive reopen (only `create()` success resets it, `366`).
- [!] **Create search** — `436` — `onClick={create}` (`364-368`). — **SRCH-03, SRCH-04**
  - Validation: `if (!newDraft.name.trim()) { window.alert('Name is required'); return }` (`365`).
  - **API**: `POST /searches` with `toPayload(newDraft)` (`366`).
  - Success: `setNewOpen(false); setNewDraft(NEW_DRAFT); load()`. **No success toast.**
  - Failure: `window.alert(e.response?.data?.detail || 'Could not create this search')` (`367`). Caught. NOTE: on a Pydantic 422 `detail` is an ARRAY of objects, which is truthy → alert text becomes `[object Object]`.
  - Backend has no duplicate-name check (`routes_searches.py:65-70`).

### 3.4 Search card summary row (one per search, `443-534`)

- [x] **Summary row click** — `461` — `onClick={() => openEdit(s)}` (`360`): closes menu; toggles inline editor (`editing` = id / null); on open builds `draft = draftOf(s)`. No API. Whole row is `cursor: pointer`. Card hover `.v2-card` (or `.v2-card v2-bd-warn` when warned; no class while open) — `458`.
- [x] Warn triangle ▲ — `462` — no handler; `title="Needs attention — {warn}"`. Rendered when `warnOf(s)` truthy (`350-351`).
- [x] Mode badge — `466` — no handler; class from `MODES[s.search_mode]` (`31-40`), falls back to `[MODE.toUpperCase(), 'sm-extension']` for unknown modes (`447`).
- [x] Summary line — `468` — no handler; `title={summary}`; copy from `451`.
- [x] Auto-scoring depth indicator (`Light ●` / `Full ●●`) — `470-477` — no handler; `cursor: help`; `title` explains depth; hidden when depth is `off`. Does NOT `stopPropagation` → clicking it opens the editor.
- [!] **Active / Paused** pill — `479-483` — `onClick={(e) => { e.stopPropagation(); toggleActive(s) }}` (`369`). `.v2-bd`. Shown for ALL searches incl. extension ones (different `title` copy for ext, `480`). — **SRCH-04**
  - **API**: `PATCH /searches/{id}` body `{ active: !s.active }`. Then `load()`.
  - Success: no toast. Failure: `console.error(e)` only (`369`) — **no user-visible feedback**.
- [x] **Extension placeholder** "extension • passive capture" — `485-486` — no handler; `cursor: help`; `title="Jobs arrive from the browser extension — there is nothing to run or test"`. Rendered INSTEAD of Run / Test / ⋯ when `isExt(s.search_mode)` (`484`).
- [!] **Run** (↻ / spinner "Running") — `489-494` — `onClick={() => runNow(s)}` (`370-374`). `.v2-bdc`. Hidden for extension searches. — **SRCH-04, SRCH-06**
  - Guard: `if (running[s.id]) return` (`371`).
  - Optimistic: `setRunning(m => ({...m, [s.id]: true}))` (`372`) → spinner + summary "running now — results land in the Job Feed as they arrive…" (`451`), colour `var(--accent)` (`452`), `title` swaps (`490`).
  - **API**: `POST /searches/{id}/run` (backend returns 202 + run_id, or **409** JSON if already running — `routes_searches.py:103-128`).
  - Success: nothing beyond the optimistic spinner; the poll (`328-339`) later clears it and reloads. **No toast.**
  - Failure (incl. 409): `console.error(e)` and spinner removed (`373`). **No user-visible feedback.** On a 409 the run IS in progress but the spinner is cleared anyway (until the next poll re-adds it — but the poll only runs while `running` is non-empty, so if this was the only key the poll stops).
- [x] **Test** (⚗ / spinner) — `496-499` — `onClick={() => runTest(s)}` (`385-406`). `.v2-bdc`. Rendered only when `TESTABLE.includes(s.search_mode)` (`495`, `TESTABLE` = keyword, levels_fyi, linkedin_personal, jobright, freehire — `50`). Hidden for extension searches and legacy `url` mode.
  - `setMenuFor(null); setTestingId(s.id); setTestTab('all')` (`386`). Spinner shows while `testingId === s.id` (`498`).
  - **API**: `POST /searches/{id}/test` (timeout 30 s), then `GET /searches/test-result/{run_id}` polling as in §2.
  - Success: `setTest({name, data})` → `TestModal` opens (`545`). **No toast.**
  - Failure: `setTest({name, error: e.response?.data?.detail || e.message})` (`403`) → modal opens in error branch. Caught. Also 400 from backend for unsupported modes (`routes_searches.py:178`) surfaces here.
  - No concurrency guard: clicking Test on a second card while the first runs overwrites `testingId` (first card's spinner vanishes); when the first finishes, `setTestingId(null)` (`395`/`405`) clears the second card's spinner too, and the second's result modal replaces the first's when it lands.
- [x] **⋯ More actions** — `501-502` — `onClick={() => setMenuFor(menuFor === s.id ? null : s.id)}`. `.v2-bd`. Accent border/background when open. Hidden for extension searches. Wrapper span at `488` has `onClick={(e) => e.stopPropagation()}` so clicks inside Run/Test/⋯/menu never bubble to the card row or to the document click-away listener.
- [x] ⋯ menu container — `503-516` — absolutely positioned, `zIndex: 40`, `width: 236`. Closes on: document click (`342`), Escape (`343`), or any item handler that calls `setMenuFor(null)`.
  - [x] Menu item **✎ Edit search** — `505` — `() => openEdit(s)`. `.v2-menuitem`. No API.
  - [x] Menu item **☰ View results in feed** — `506` — `() => navigate('/v2/feed?search=' + s.id)`. `.v2-menuitem`. No API. Does not call `setMenuFor(null)` (moot — navigates away).
  - [!] Menu item **⧉ Duplicate** — `507` — `() => duplicate(s)` (`380-383`). `.v2-menuitem`. — **SRCH-04**
    - **API**: `POST /searches` body `{...toPayload(draftOf(s)), name: s.name + ' (copy)'}`. Then `load()`.
    - Success: no toast. Failure: `console.error(e)` only — **no user-visible feedback**.
  - [!] Menu item **✕ Delete search** — `512-514` — `() => remove(s)` (`375-379`). `.v2-hover-bad`, red text. — **SRCH-04**
    - Confirm: `window.confirm('Delete "' + s.name + '"?')` (`377`) — native dialog, not a modal.
    - **API**: `DELETE /searches/{id}`. Then `load()`.
    - Success: no toast. Failure: `console.error(e)` only — **no user-visible feedback**.

### 3.5 Inline edit drawer (`522-531`, rendered when `editing === s.id && draft`)

- [x] Drawer container — `523` — `onClick={(e) => e.stopPropagation()}` so field clicks don't toggle the editor closed.
- [x] `<ConfigForm d={draft} set=…/>` — `524` — every field (§3.6) mutates `draft`.
- [x] Helper copy "Changes apply from the next run" — `526` — static.
- [x] **Cancel** — `527` — `onClick={() => setEditing(null)}`. `.v2-bdc`. Draft discarded (not cleared; rebuilt on next open).
- [!] **Save changes** — `528` — `onClick={() => save(s)}` (`361-363`). — **SRCH-04**
  - **API**: `PATCH /searches/{id}` body `toPayload(draft)` (full payload, every field incl. `search_mode` — backend `allowed` set at `routes_searches.py:78-84`).
  - Success: `setEditing(null); load()`. **No toast.**
  - Failure: `console.error(e); window.alert('Could not save this search')` (`362`). Caught.
- [x] No "unsaved changes" guard: clicking the summary row (`461`) or "+ New search" (`417`) while editing closes the drawer and silently drops the draft.

### 3.6 ConfigForm fields (`184-294`) — shared by New card (§3.3) and Edit drawer (§3.5)

Grid 1 (`240`, `1.2fr 1fr 1fr`), fields pushed in `190-236`:

- [x] **Name** text input — `191` — `set({name})`; placeholder "e.g. TPM roles — Tier 1". Always shown.
- [x] **Mode** — two variants:
  - [x] Extension searches: disabled `Cell` with literal value "Extension (manual Save-to-Feed)" / "LinkedIn Extension (passive capture)", `span={2}`, `onChange={() => {}}` — `193-194`.
  - [x] Otherwise: `<select>` with `MODE_OPTIONS` (`41-47`: Keyword (JobSpy), Levels.fyi, LinkedIn Personal, Jobright.ai, freehire.me) — `196-202`. On change sets `search_mode` AND resets `sources` (linkedin_personal → `['recommended','top-applicant']`; jobright → `['recommended']`; keyword → 4 boards; levels_fyi/freehire → sources untouched). Legacy `url` mode is NOT in the picker, so a legacy-`url` search shows a `<select>` whose `value="url"` matches no option (browser shows first option / blank).
- [x] keyword only (`204-212`): **Search term** (mono, `206`), **Location** (`207`, placeholder "United States"), **Remote** select `['', 'Any'] / ['true','Remote only'] / ['false','On-site only']` (`208`), **Job type** select Full-time / Part-time / Contract (`209`), **Hours old** `type=number` (`210`), **Results wanted** `type=number` (`211`).
- [x] levels_fyi only (`213-218`): **Max pages** number (`215`), **Levels.fyi URL · filters applied** mono `span={3}` (`216-217`).
- [x] jobright only (`219-224`): **Search term · optional** (`221`), **Results wanted · 20–500** number (`222`, no min/max enforced client-side), **Min score** number (`223`, placeholder "0 = no filter").
- [x] freehire only (`225-233`): **Search term · optional** mono with `sub` help (`227-228`), **freehire.me URL · filters forwarded** mono `span={2}` with `sub` (`229-231`), **Results wanted** number (`232`).
- [x] url (legacy) only (`234-236`): **Direct URL** mono `span={2}` (`235`).
- [x] linkedin_personal: NO mode-specific cells in grid 1 (only Name + Mode), collections chips below.
- [x] Extension modes: NO mode-specific cells (only Name + disabled Mode).
- [x] Note banner — `242-244` — static text from `noteFor(m)` (`64-70`): levels_fyi (`sm-levels`), jobright (`sm-jobright`), extension (`sm-levels`), linkedin_extension (`sm-levels`); none for keyword/linkedin_personal/freehire/url.
- [x] **Sources** chips ×5 (LinkedIn, Indeed, ZipRecruiter, Google Jobs, Direct (Playwright)) — `246-251`, `Chip` at `158-162`, `.v2-bd` — keyword only; `toggleSrc(id)` (`187`) adds/removes from `d.sources`. No API.
- [x] **Collections** chips ×2 (Recommended, Top Applicant) — `252-258` — linkedin_personal only; same `toggleSrc`. Static hint "Credentials live in Settings › Accounts" (`256`).
- [x] Grid 2 (`260-265`, always shown): **Title include · comma-separated** mono (`261`), **Title exclude** mono (`262`), **Company include · exact** (`263`), **Company exclude · exact** (`264`). All comma-joined strings, split by `toPayload.list` (`119`).
- [x] Grid 3 (`267-291`, always shown):
  - [x] **Auto-scoring** `DepthPills` Off / Light ● / Full ●● — `270`, component `169-181`, `.v2-bd`, each with `title={d.hint}` (`53-55`); `e.stopPropagation()` then `onPick(id)` → `set({auto_scoring_depth})`. Help "How deeply new results are scored as they arrive" (`271`).
  - [x] **Run interval · min** `<input type=number min=0>` — `276-277` — `set({run_interval_minutes})`; help "0 follows the global schedule from Settings" (`278`). **Hidden for extension searches** (`273`, replaced by empty `<div />` at `280`).
  - [x] **Skip active companies** `Check` — `284-286`, component `163-168` — toggles `exclude_active_companies`; `title="Their Company scrapes already bring these postings"`. No hover class. Always shown.
  - [x] **Require salary** `Check` — `287-288` — jobright only; toggles `require_salary`.

### 3.7 Test-run modal (`551-668`, rendered when `test` non-null, `545`)

- [x] Backdrop — `589` — `onClick={onClose}` (`setTest(null)`); `zIndex: 60`, `background: var(--scrim)`.
- [x] Modal panel — `590` — `onClick={(e) => e.stopPropagation()}`; `width: 980, maxHeight: 660`. Not responsive below 980px.
- [x] Title "Test run — {name}" — `592` — ellipsis.
- [x] Sub "dry run · nothing saved" — `593`.
- [x] **✕ close** — `594` — `onClick={onClose}`, `.v2-hover-accent`.
- [x] **Escape** key — `343` — `setTest(null)` (document keydown listener; also clears `menuFor`).
- [!] Params strip (`601-612`): Term chip (`602-604`, only when `cfg.search_term` and mode not jobright/freehire), `params.join(' · ')` (`605`, built `569-586`), per-source chips from `Object.entries(bySource)` (`607-611`, `srcChip` `560-566`). No handlers. — **SRCH-01**
- [x] **Tabs** All (n) / Kept (n) / Filtered (n) — `614-621` — `onClick={() => setTab(id)}` → `setTestTab` in parent (`545`). `.v2-bd`. Bold + accent when active.
- [x] Sticky column header — `624-632` — static; "Desc" has `title="Description scraped"`.
- [x] Row **title link** — `640` — `<a href={j.url} target="_blank" rel="noopener noreferrer">`; `title={j.title}`; strikethrough + muted when `!j.kept`. Hover via `.jn-v2 a:hover` (theme.css:121).
- [x] Row company (`639`), location (`641`), salary (`642`) — `title` attributes; no handlers.
- [x] Row Desc ✓/✕ — `643` — colour only.
- [x] Row status pill Kept / Out — `645` — `title={j.reason || 'Passed all filters'}`; `cursor: help` only when a reason exists.
- [x] Footer summary "N kept · N filtered · N raw · Ns" — `658-660` — static (see §8).
- [x] **Close** — `661` — `onClick={onClose}`, `.v2-bdc`.

### 3.8 Keyboard / global listeners (`341-346`)

- [x] `document` **click** → `setMenuFor(null)` (`342`). Note: clicks inside the actions wrapper (`488`) and the edit drawer (`523`) call `stopPropagation`, so they never reach this listener.
- [!] `document` **keydown Escape** → `setMenuFor(null); setTest(null)` (`343`). Does NOT close the edit drawer or the New-search card. — **SRCH-21**
- [x] No other keyboard shortcuts on this screen (no j/k, no Enter-to-save, no Ctrl+S).

### 3.9 Extension searches (`search_mode` ∈ `linkedin_extension` / `extension`, `isExt` `49`) — what differs

- [x] Badge: both render "EXTENSION" with class `sm-extension` (`37-38`).
- [x] Summary line fixed copy: `'Passive capture on linkedin.com/jobs/collections/* · title filters apply on import'` / `'Manual “Save to Job Feed” button on any website'` (`76-77`); `last run` suffix NOT appended for ext modes.
- [x] **Hidden**: Run, Test, ⋯ menu (and therefore Edit-via-menu, View results in feed, Duplicate, Delete) — replaced by the "extension • passive capture" label (`484-486`).
- [x] **Still available**: summary-row click to open the editor (`461`), Active/Paused toggle (`479`, different tooltip copy at `480`).
- [x] Edit drawer differences: Mode cell disabled with literal label (`193-194`); no mode-specific cells; note banner shown (`67-68`); Run interval hidden (`273-280`); Sources/Collections chips absent; Require salary absent. Filters grid, DepthPills, Skip-active-companies remain.
- [!] Backend does NOT protect extension searches: `DELETE /searches/{id}` (`routes_searches.py:93-100`) and `PATCH` of `search_mode` (`routes_searches.py:78`) are unguarded — protection is UI-only. — **SRCH-26**
- [x] Ext searches are counted in "N configs" and "N active" (`348`, `354-355`).

---

## 4. States rendered

### 4.1 Search list

- [!] **Loading**: **NO loading branch.** `searches` initialises to `[]` (`299`) with no `loading` flag, so until `GET /searches` resolves the screen shows the EMPTY state ("No searches yet", `536-542`) and the header reads "0 configs · 0 active" (`353-358`). Flash-of-empty-state on every mount. — **SRCH-05**
- [!] **Error** (GET /searches fails): **NO error branch.** `console.error` (`315`); list stays `[]` → empty-state copy is shown, indistinguishable from a real empty DB. — **SRCH-05**
- [x] **Empty** (`536-542`, only when `searches.length === 0 && !newOpen`): "No searches yet" (`538`) / "Create one to start pulling roles into the Job Feed on a schedule." (`539`) / "+ New search" link (`540`).
- [x] **Zero-results filtering**: n/a — no list filters or sort on this screen.
- [x] **Per-card summary variants** (`451-452`): running → "running now — results land in the Job Feed as they arrive…" in `var(--accent)`; warned → `warnOf(s)` text in `var(--warn)` where warn = `s.last_error` ‖ `downMap[s.id]` (health reason) ‖ `'Last run finished cleanly but returned no jobs'` when `last_run_warning` (`350-351`); else `summaryOf(s)` (`73-99`) in `var(--muted)`.
- [x] `summaryOf` fallback for unknown mode: `${short(direct_url) || 'no URL'}${last}` (`98`).
- [x] **Long strings**: name ellipsis (`465`), summary ellipsis + `title` (`468`), header count line ellipsis (`414`), URLs cut by `short(u, 52)` (`24-27`) in summaries, `short(…, 70)` / `short(…, 60)` in the test params strip (`575`, `578`). Badge is `whiteSpace: nowrap` and `flex: 0 0 auto` (`466`) — a very long name shrinks, the badge never does.
- [!] `ago()` (`7-15`) and `until()` (`16-23`) are computed at render time only; no timer re-renders them, so "next scheduled run in 12m" and "last run 3m ago" freeze until something else triggers a render. — **SRCH-20**

### 4.2 New-search card

- [!] Only two states: hidden / shown (`425`). No pending/submitting state on "Create search" — double-click sends two POSTs. — **SRCH-29**
- [x] Validation error: `window.alert('Name is required')` (`365`) — no inline field error.

### 4.3 Edit drawer

- [!] Rendered only when `isOpen && draft` (`522`). No pending/submitting state on "Save changes". No dirty indicator. — **SRCH-29**

### 4.4 Run button

- [x] `spin` (`446`) from `running[s.id]`: spinner + "Running" label + accent colour (`491-493`). No failed-run state on the button itself — failure is only visible via `last_error` in the summary after `load()`.

### 4.5 Test flow

- [x] **In progress**: spinner replaces ⚗ on the Test button only (`498`); no modal, no progress toast, no "testing…" copy elsewhere.
- [x] **Modal error branch** (`597-598`): `test.error` in `var(--bad)`. Reached from: axios error (`403`), 404 on poll (`397`), 100-poll timeout (`400`).
- [x] **Modal data branch** (`599-664`): params strip, tabs, table, footer.
- [x] **Table empty** (`650-654`): per-tab copy — filtered: "Nothing was filtered out."; kept: "Nothing passed the filters."; all: "No results returned."
- [!] **MISSING branch — backend soft error with HTTP 200**: `jobright.preview` (`scraper/sources/jobright.py:746-754`), `freehire.preview` (`freehire.py:346-349`), `linkedin_personal.preview` (`linkedin_personal.py:955-959`) and the async wrapper's `except` (`routes_searches.py:170`) all return `{"error": str(e), ...}` with status 200. The screen stores this as `test.data` (`395`, `401`) and never reads `data.error`, so the modal shows the DATA branch with "No results returned." and "0 kept · 0 filtered · 0 raw" instead of the error message. — **SRCH-02**
- [!] **MISSING data — source chips** (`607-611`): the modal reads `d.by_source` (`558`) but every backend path returns `source_breakdown` (`routes_searches.py:387`, `:621`, `jobright.py:730`, `freehire.py:330`, `linkedin_personal.py:1123`). `bySource` is always `{}` → source chips NEVER render. `srcChip` (`560-566`) is effectively dead. — **SRCH-01**
- [x] Params strip for keyword: backend `config` has no `mode` key (`routes_searches.py:398-406`) so `cfg.mode` is `undefined` → falls to the `else` branch (`580-586`) — works by accident. `cfg.location` / `is_remote` / `hours_old` / `results_wanted` present.
- [x] Params strip for levels_fyi reads `cfg.url || cfg.direct_url` (`575`) — backend sends `url` (`routes_searches.py:484`, `:634`) ✓.
- [x] Params strip for linkedin_personal reads `cfg.collections || cfg.sources` (`573`) — backend sends `collections` ✓.
- [x] `hasDesc` reads `j.desc_length || j.description_length || j.has_description` (`635`) — backend sends `has_description` + `desc_length` ✓.
- [x] Modal has no loading state and no "expired" state distinct from error text.

---

## 5. Hover styles

All hover is via classes defined in `frontend/src/v2/theme.css`; there is NO inline `onMouseEnter`/`onMouseLeave` and no `style-hover` pattern in this file.

- [!] `.v2-card` — card container when not open and not warned (`458`). theme.css:138 (transition), :142 (`border-color: var(--accent) !important; background: var(--hover-soft) !important`). — **SRCH-17**
- [x] `.v2-card v2-bd-warn` — warned card (`458`); theme.css:153 `border-color: var(--warn) !important` (declared after `.v2-card:hover` so it wins — see the comment at `454-457`).
- [x] Open card: `className={undefined}` (`458`) — deliberately no hover.
- [!] `.v2-bd` (border → accent on hover, theme.css:152) on: `Chip` (`159`), `DepthPills` (`174`), Active/Paused pill (`479`), ⋯ button (`501`), test-modal tabs (`618`). — **SRCH-17**
- [!] `.v2-bdc` (border + text → accent, theme.css:155) on: New-card Cancel (`435`), Run (`489`), Test (`496`), Edit Cancel (`527`), modal Close (`661`). — **SRCH-17**
- [x] `.v2-menuitem` (bg → `var(--surface-2)`, theme.css:148) on the three non-destructive menu items (`508`).
- [x] `.v2-hover-bad` (bg → `var(--bad-soft) !important`, theme.css:130) on Delete search (`512`).
- [x] `.v2-hover-accent` (bg → `var(--surface-2)`, colour → `var(--text)`, theme.css:129) on modal ✕ (`594`).
- [x] `.jn-v2 a:hover { color: var(--text) }` (theme.css:121) on the test-row title link (`640`) — note this overrides the muted/strikethrough colour for filtered rows on hover.
- [x] `.v2-spin` (theme.css:226, animation only) on Run/Test spinners (`492`, `498`).
- [x] `.v2-scroll` (custom scrollbar, theme.css:221-223) on the body (`423`) and the modal table (`623`).
- [x] **No hover feedback** on: header "+ New search" (`417`), "Create search" (`436`), "Save changes" (`528`), empty-state "+ New search" link (`540`), `Check` boxes (`164`), depth indicator on the card (`470`), all `Cell` inputs/selects (`149-153`), run-interval input (`276`).

---

## 6. Theme

- [x] Dark mode is NOT read in `Searches.jsx`. The shell reads `localStorage['jobnavigator_dark_mode'] === 'true'` (`V2App.jsx:52`) and stamps `data-theme="dark"|"light"` on the `.jn-v2` root (`V2App.jsx:90`); `theme.css:4` defines light tokens, `theme.css:74` (`.jn-v2[data-theme="dark"]`) overrides them. Toggle: `V2App.jsx:54` (`toggleTheme`), buttons at `V2App.jsx:146` (collapsed) and `:154` (expanded).
- [x] Colour literals in `Searches.jsx`: **none** — grep for `#hex`, `rgb(`, `hsl(` returns nothing. Every colour is a `var(--…)` token. The only non-token colour words are `'transparent'` (`492`, `498` spinner `borderTopColor`; `637` kept-row background).
- [x] Tokens used that must exist in both palettes: `--bg --surface --surface-2 --text --text-2 --muted --edge --line --line-soft --line-strong --accent --accent-soft --accent-ink --warn --warn-line --warn-soft --bad --bad-soft --bad-faint --good --scrim --shadow-menu --shadow-modal --serif --sans --mono`, plus badge pairs `--sm-{keyword,levels,lipersonal,jobright,freehire,extension,url}-{bg,fg}` (theme.css:199-205).
- [x] Mode-badge classes reused as note-banner backgrounds (`243`) and test-source chips (`561-565`): `sm-levels`, `sm-jobright`, `sm-keyword`, `sm-lipersonal`, `sm-extension`.

---

## 7. Suspicious

- [!] `console.error` at `315`, `362`, `369`, `373`, `378`, `382` — six sites; four of them (`369` toggleActive, `373` runNow, `378` remove, `382` duplicate) are the ONLY failure handling → silent failure for the user. — **SRCH-04**
- [!] `window.alert` at `362`, `365`, `367` and `window.confirm` at `377` — native dialogs; `Toast.jsx` / `useToasts` is not imported anywhere in this file, contrary to HANDOVER §"Error paths" (`HANDOVER.md:55-58`) which asks for the `error` toast at every failure site. — **SRCH-04**
- [x] `367`: `e.response?.data?.detail || …` — a 422 `detail` is an array → alert shows `[object Object]`.
- [!] `558`: reads `d.by_source`; backend never sends it (sends `source_breakdown`) → `srcChip` (`560-566`) and the chip loop (`607-611`) are dead in practice. — **SRCH-01**
- [!] `395`/`401`: `test.data.error` from a 200 soft-error payload is ignored → misleading "No results returned." (see §4.5). — **SRCH-02**
- [!] `536`: empty state doubles as loading state and as error state (no `loading`/`error` flags). — **SRCH-05**
- [~] `311-312` + `main.jsx:7` `<React.StrictMode>`: in DEV, StrictMode runs the effect's cleanup once on mount, setting `mounted.current = false` permanently (nothing resets it to `true`). Consequences in dev only: run-poll responses are discarded (`333`), async test polling returns after the first sleep (`392`) so the modal never opens, and `setTestingId(null)` at `405` is skipped so the Test spinner sticks. Production builds (Docker) are unaffected. — _untestable: dev-server-only; the Docker bundle is a production build_
- [!] `328-339`: polling effect depends on `running`, and every tick replaces `running` with a new object → interval is destroyed and recreated every 3 s and the component re-renders every 3 s even when nothing changed. — **SRCH-28**
- [!] `320`/`334`: `running` is keyed by `scope_key` for ALL job types (company scrapes, resume scoring, cover-letter generation…), so any unrelated background job keeps the 3 s poll alive on this screen. — **SRCH-28**
- [!] `373`: a 409 (already running) is treated as failure and clears the spinner although the run is live. — **SRCH-06**
- [!] `386`/`395`/`405`: no guard against two concurrent Tests; second click overwrites `testingId`, and either completion clears the other's spinner. — **SRCH-23**
- [!] `435`: New-card Cancel does not reset `newDraft`; stale input reappears on reopen (only `366` resets it). — **SRCH-22**
- [!] `123`: `toPayload` forces `location: 'United States'` when empty — sent for every mode, including levels_fyi/jobright/freehire/extension where location is meaningless; a user who clears Location on a keyword search silently gets "United States" back. — **SRCH-12**
- [!] `125-127`, `134`: `parseInt(x) || default` — entering `0` for Hours old / Results wanted / Max pages is coerced to 24 / 50 / 50; `run_interval_minutes` 0 is intended. Non-numeric input silently becomes the default. — **SRCH-12**
- [!] `196-202`: legacy `url`-mode searches render a Mode `<select>` whose value matches no option (`MODE_OPTIONS` omits `url`, `41-47`) — the select displays the first option ("Keyword (JobSpy)") while `d.search_mode` is still `'url'`; saving without touching Mode keeps `url`, but the UI misrepresents it. Comment at `29-30` acknowledges `url` is legacy. — **SRCH-11**
- [x] `234-236`: the `url` branch and `MODES.url` (`39`) are reachable only for legacy rows — semi-dead code.
- [!] `319`/`321`: `/health/entities` and `/scheduler/jobs` are fetched once; after a run completes and `load()` refreshes the list, `downMap`/`nextRun` are stale until a full remount. — **SRCH-24**
- [!] `357`: `until(nextRun)` shows "next scheduled run in any moment" when `m <= 0` (`19`) — copy reads oddly ("in any moment"). — **SRCH-19**
- [!] `470-477`: depth indicator has `cursor: help` but propagates the click to the row → opens the editor; inconsistent with the `help` affordance. — **SRCH-25**
- [x] `506`: "View results in feed" does not close the menu before navigating (harmless, but `menuFor` is left set if navigation is intercepted). — _verified: navigates to /v2/feed?search=<id>_
- [x] `590`: modal is a fixed 980 px wide with no `maxWidth: 100%` → horizontal overflow on narrow viewports. — _measured: the panel is a flex item and shrinks — 900px viewport gives w=900, no overflow. Width deviation logged as SRCH-13_
- [!] `343`: Escape closes menu + test modal but NOT the edit drawer / New-search card — inconsistent. — **SRCH-21**
- [x] No `TODO` / `FIXME` markers in the file. No `console.log` (only `console.error`).
- [x] Props: every prop of `Cell` (`139`), `Chip` (`158`), `Check` (`163`), `DepthPills` (`169`), `ConfigForm` (`184`), `TestModal` (`551`) is supplied at its call sites — no missing-prop issues found. `Cell.type` is passed only for numeric fields; `Cell.sub` only in the freehire branch.
- [x] Backend guard gap (UI-only protection): `DELETE` / `PATCH search_mode` on the two seeded extension searches are not blocked server-side (`routes_searches.py:73-100`).

---

## 8. Counts that must agree

- [!] **Header "N configs"** (`354`) = `searches.length` from `GET /searches` (`315`). Must equal the **rail badge "Searches"** count = `GET /searches` array length fetched ONCE by the shell (`V2App.jsx:62`, `counts.searches`, rendered `V2App.jsx:124`). They agree on first paint, then DIVERGE after Create / Duplicate / Delete on this screen because the shell never refetches. Both include the two seeded extension searches and paused searches. — **SRCH-10**
- [x] **Header "N active"** (`355`) = `searches.filter(s => s.active).length` (`348`) from `GET /searches`. No other screen shows this number; Stats KPIs do not expose it.
- [!] **Header "N need attention"** (`352`, `356`) = count of searches where `last_error` ‖ `downMap[id]` ‖ `last_run_warning` (`350-351`). Sources: `last_error`/`last_run_warning` from `GET /searches` (`routes_searches.py:665-666`, latest `ScrapeLog`); `downMap` from `GET /health/entities` `.searches[].reason` (`main.py:1172-1175`, requires ALL of the last 3 runs to have errored/warned). Compare against: — **SRCH-09**
  - Rail **amber dot / "N sources need attention"** = `warn.searches + warn.companies` from `GET /health/entities` ONLY (`V2App.jsx:65-68`, `:74`, `:78-79`). The screen's number is ≥ the rail's `searches` component because it also counts a single failed/empty run. Expect a mismatch whenever a search has exactly one recent error or one empty run.
  - Per-card ▲ triangle (`462`) and amber summary — same `warnOf` predicate, so triangles on screen must equal "N need attention".
- [~] **"next scheduled run in Xh Ym"** (`357`) = `GET /scheduler/jobs` → item `id === 'scrape_all'` → `next_run` (`main.py:804`). Must agree with the Stats page's scheduler table for the same job (also `/scheduler/jobs`), modulo staleness (fetched once here). — _untestable: Stats scheduler table not cross-checked in this pass_
- [~] **Per-card "last run Xm ago"** (`74`) = `GET /searches` `.last_run_at` (`routes_searches.py:662`). Compare with Stats › Run history for the same search. — _untestable: Stats run history not cross-checked in this pass_
- [~] **Running spinner / "running now"** (`446`, `451`) = `GET /monitor/active` rows whose `scope_key === s.id` (`main.py:889` → `job_monitor.get_all_running`, `job_monitor.py:65`; the search route launches with `scope_key=search_id` string, `routes_searches.py:123-124`). Must agree with Stats "Scheduler jobs / running" and with the rail health line derived from `/monitor/history` (`V2App.jsx:70-71`). — _untestable: driven by intercepted /monitor/active; Stats not cross-checked_
- [x] **Test modal tab counts vs footer** — tabs: `All (jobs.length)`, `Kept (kept.length)`, `Filtered (filtered.length)` (`615`) computed client-side from `d.jobs[].kept`; footer: `d.after_filter ?? kept.length` kept, `(d.raw_count ?? jobs.length) - (d.after_filter ?? kept.length)` filtered, `d.raw_count ?? jobs.length` raw (`659`) — server fields (`routes_searches.py:384-390`, `:609-620`). For keyword and levels the backend appends one result per raw row (no `continue` between `raw_count` and `results.append`), so they should agree; verify for jobright/freehire/linkedin_personal previews where dedup may happen before `results`. — _verified: every preview path appends one result per raw row, so the counts agree_
- [!] **Source chips in the test modal** (`607-611`) SHOULD sum to raw count — but they never render (see §4.5 / §7 `by_source`). — **SRCH-01**
- [~] **JobFeed `?search=` scoping**: "View results in feed" (`506`) → `JobFeed.jsx:179`, `:215` filters `search_id`; the feed's header count for that scope should match `last_jobs_found` / `last_new_jobs` fields returned by `GET /searches` (`routes_searches.py:667-668`) which this screen receives but does NOT display. — _untestable: the scratch search had 0 jobs, so the counts could not be compared_

---

## Summary

- Interactive elements catalogued: **62** checkbox lines across §3 (header 2, empty state 1, new-search card 3, card row + ⋯ menu 14, edit drawer 6, ConfigForm 18 field/chip/pill groups, test modal 14, keyboard/global 3, extension-search notes 6 — note that chip groups such as the 5 Sources chips and 3 depth pills are one line each, so the raw count of clickable DOM controls is higher).
- API endpoints used: **10** — `GET /searches`, `POST /searches`, `PATCH /searches/{id}`, `DELETE /searches/{id}`, `POST /searches/{id}/run`, `POST /searches/{id}/test`, `GET /searches/test-result/{run_id}`, `GET /health/entities`, `GET /monitor/active`, `GET /scheduler/jobs`.
- Uncaught / user-invisible failure paths: **7** — `load` (`315`), `toggleActive` (`369`), `runNow` (`373`, incl. 409), `remove` (`378`), `duplicate` (`382`) all `console.error`-only; plus `/health/entities`, `/monitor/active`, `/scheduler/jobs` mount fetches swallowed (`319-324`) and the poll `catch {}` (`336`). No promise is entirely without a `catch`, but none reaches the user.
- Missing empty/error branches: **5** — list loading state; list error state; test-modal loading state; test-modal handling of `data.error` (HTTP 200 soft errors); test-modal source chips (`by_source` never populated).
- Suspicious items: **25** (§7), the highest-impact being the `by_source`/`source_breakdown` mismatch, the ignored `data.error`, the StrictMode-dev `mounted` ref, the empty-state-as-loading flash, and the `[object Object]` alert on 422.
