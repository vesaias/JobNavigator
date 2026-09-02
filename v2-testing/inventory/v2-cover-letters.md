# v2 Cover Letters — test inventory

Catalogued from source only (no app run, no source modified). Files:

- `frontend/src/v2/CoverLetters.jsx` (366 lines) — list + generate panel, route `/v2/cover-letters`. Abbreviated **CL** below.
- `frontend/src/v2/CoverLetterEditor.jsx` (498 lines) — editor, route `/v2/cover-letters/:id`. Abbreviated **ED** below.
- Shared: `frontend/src/v2/V2App.jsx` (shell), `frontend/src/v2/Toast.jsx` (toast API — **imported by neither screen**), `frontend/src/api.js` (axios), `frontend/src/useTitle.js`, `frontend/src/v2/theme.css`.
- Backend contract consulted: `backend/api/routes_cover_letters.py`, `backend/job_monitor.py`, `backend/api/routes_jobs.py`, `backend/api/routes_resumes.py`.

Conventions: every line is a checkbox so it can be pasted into the plan. "no toast" means neither `useToasts` nor `ToastStack` is used anywhere in the file; the only user-visible feedback is inline text where noted. "swallowed" = `.catch(() => {})` / empty `catch {}` with no UI. "console only" = `console.error` with no UI.

---

## Screen 1 — Cover Letters list (`/v2/cover-letters`)

### 1. Routes & params

- [x] Route: `<Route path="cover-letters" element={<V2CoverLetters />} />` nested under `/v2` → `V2App` shell — `frontend/src/App.jsx:161` (parent `App.jsx:153`).
- [x] Tab title comes from `TitleSync` route table ("Cover Letters · JobNavigator") — `frontend/src/useTitle.js:14,41`. The list does NOT call `useTitle`.
- [!] `?job=<id>` deep-link: read once on mount (`[]` deps, eslint-disabled) — CL:152-170. Sets `genJob` (CL:156), then `GET /api/jobs/{id}` to prepend the job to the picker options if it is outside the 200-row window (CL:158-160, swallowed on failure). — **CL-04**
- [x] `?resume=<id>` deep-link: sets `genResume` (CL:163), then `GET /api/resumes/{id}` to prepend the résumé if missing from base list (CL:164-166, swallowed).
- [x] Both params are cleared immediately with `setSearchParams({}, { replace: true })` — CL:168. Reloading the page after arrival therefore loses the pre-selection.
- [x] `?resume=persona` is NOT special-cased: it sets `genResume='persona'` (valid backend id) but also fires `GET /api/resumes/persona` (CL:164) which will 404/500 → swallowed. Verify no visible side-effect.
- [x] Deep-link to a job that no longer exists: `genJob` stays set to the dead id (CL:156), Picker shows placeholder (no matching option, CL:44,49) but `canGenerate` is true (CL:224) → Generate → backend 404 "Job not found" → inline `err` (CL:241,320).
- [x] localStorage **read**: `v2_cl_archive_open` (const `ARCH_KEY` CL:21) — read in `useState` initialiser CL:119 (`=== '1'`).
- [x] localStorage **write**: `v2_cl_archive_open` — written `'1'`/`'0'` on every change of `archOpen` — CL:124 (also writes `'0'` on first mount when nothing stored).
- [x] localStorage read by axios on every request: `jobnavigator_api_key` — `frontend/src/api.js:11`.
- [x] Shell localStorage (affects this screen's theme/rail): `jobnavigator_dark_mode` read `V2App.jsx:52`, written `:54`; `jobnavigator_v2_rail` read `:48`, written `:55`.
- [x] No other query params, no `location.state`, no sessionStorage.

### 2. Data loads

- [!] `GET /api/cover-letters` — `load()` CL:130-132, called on mount CL:135 and after any pending run disappears CL:183. Failure: console only (CL:131) — list stays `[]` and the UI shows the "No cover letters yet" copy (see §4). — **CL-05**
- [x] `GET /api/resumes?is_base=true` — on mount CL:136 → `resumes`. Failure swallowed.
- [x] `GET /api/persona` — on mount CL:137 → `personaAvailable = Object.keys(resume_content).length > 0`. Failure swallowed (persona option simply absent).
- [x] `GET /api/jobs?status=saved,applied&limit=200` — on mount CL:140-141 → `jobs = data.jobs`. 200 is the backend cap (`routes_jobs.py:84` `Query(50, le=200)`). Jobs beyond the 200 newest are not pickable except via `?job=`. Failure swallowed.
- [x] `GET /api/settings` — on mount CL:142-148 → `cover_letter_voice_presets` (string JSON, parsed CL:144; parse failure → `[]`) and `cover_letter_default_voice` → `genVoice` (fallback `list[0]?.id`, else `''`) CL:147. Failure swallowed → presets `[]`, voice `''`.
- [x] `GET /api/jobs/{id}` — only on `?job=` deep-link CL:158. Swallowed.
- [x] `GET /api/resumes/{id}` — only on `?resume=` deep-link CL:164. Swallowed.
- [x] **Polling** `GET /api/monitor/active` — CL:173-189: immediate `tick()` on mount (CL:186) then `setInterval(tick, 3000)` (CL:187), cleared on unmount (CL:188). Runs are filtered by `r.job_type === 'generate_cover_letter'` (CL:178) — NOT by scope_key, so Regenerate runs launched from the editor (scope `cl:{letter_id}`) also show as pending rows here. `pending` is replaced only when the joined `run_id` list differs (CL:181-182). When any previously-pending `run_id` disappears → `load()` (CL:183) — regardless of whether the run completed or failed. Poll failure swallowed (CL:184).
- [x] `POST /api/cover-letters/generate` — `generate()` CL:226-243, body `{resume_id, job_id, voice, length}` (CL:231-233). Response `{run_id}` (backend 202, `routes_cover_letters.py:359`). On success: `runMeta[run_id]` recorded (CL:234), optimistic `pending` entry with `scope_key: cl:{resume}:{job}` (CL:235-236), `genJob` cleared (CL:239). On failure: `err = e.response.data.detail || 'Generation failed'` (CL:241) — covers 400 (no description / persona empty / resume empty / missing ids), 404 (job/resume), 409 duplicate ("generate_cover_letter is already running for this pair", `routes_cover_letters.py:361`), 500 (prompt setting empty).
- [!] No polling of `/api/monitor/history` — a run that FAILS in the background is indistinguishable from one that succeeded: the row vanishes, the list reloads, nothing new appears, no message (see §4/§7). — **CL-06**

### 3. Interactive elements

Generate panel (left column, CL:291-321):

- [x] **Search input** — placeholder `Search letters, companies… ` (note trailing space) — CL:284-285; `onChange → setQuery`; no API; mutates `query` → `visible` (CL:200-204, matches `name`/`company`/`title`, case-insensitive substring) and `showArch` (CL:123: a non-empty query force-shows archived rows without touching the stored preference). No debounce. No clear button. No toast.
- [!] **Résumé Picker** (`Your résumé`) — CL:296 → `Picker` CL:36-69. Control div CL:47 toggles `open`; option row CL:57 `onPick(o.id)` → `setGenResume`; closes on any document click (CL:38-43); wrapper `stopPropagation` (CL:46). Options: `Persona (full profile)` (only if `personaAvailable`) + base résumés (CL:191-194). Empty-options copy `Nothing to pick yet.` CL:55. No API. Hint text `Base for achievements and motivation` CL:297. — **CL-07, CL-08**
- [!] **Job Picker** (`Target job`) — CL:302, placeholder `Select a saved or applied job…`; options `"{company} — {title}"` or `title` or `Untitled role` (CL:196-198); `onPick → setGenJob`. Note `${j.title}` is not null-guarded when `company` exists → can render `"Acme — null"`. — **CL-07, CL-08**
- [x] **Voice chips** — `VoicePicker` CL:307 → CL:72-86; each chip CL:78 `onClick → setGenVoice(v.id)`; `title` = preset `instruction` (CL:78). Selected state via inline colours (CL:80-81). Renders NOTHING when `presets` is empty (no copy).
- [x] **Length segments** — `LengthPicker` CL:312 → CL:88-102; `Concise / Standard / Detailed` (CL:16); CL:94 `onClick → setGenLength(id)`. Default `standard` CL:116.
- [x] **✦ Generate cover letter** button (div) — CL:315-319; handler `generate` CL:226; guarded by `canGenerate = genResume && genJob && !thisPairRunning` (CL:223-224; guard also at CL:227 so a click on the dimmed button is a no-op). Tooltip variants CL:315: `Already writing this one` / `Pick a résumé and a job first` / `Write the letter — you can start others while it runs`. Label switches to spinner + `Generating…` only while THIS pair's run is active (CL:317-318). API: `POST /api/cover-letters/generate`. Mutates `runMeta`, `pending`, `genJob` (cleared), `err`. Success: NO toast (an optimistic dashed row appears instead). Failure: inline red `err` under the button CL:320 (no toast). Caught.
- [!] **Pending row** — CL:331-339: dashed accent box, spinner, `Generating — {label}` from `rowLabel` (CL:246-251: `runMeta` label ` · voice · length`, else `company — title` of `target_job_id`, else `a cover letter`), right-hand static `~30s` (CL:337). **No handler** — not clickable, not cancellable. — **CL-09**

List (right column, CL:324-362):

- [x] **Letter row** (active) — `row(c, false)` CL:341 → CL:254-274; whole row `onClick → navigate('/v2/cover-letters/{id}')` CL:259; class `v2-bd`. Content: serif `name` with `title` tooltip (CL:263), sub-line `source_name · voice label · length label · edited {ago} ago` (CL:255-257), stage chip (CL:266-269, only when `c.stage` or archived; class from `STAGE_CLASS` CL:19 else `cc-generic`; text `stage` or `Draft`; tooltip `Stage of the linked application` / `No application yet`), right column `ago(updated_at)` (CL:270), chevron `›` (CL:271). No API on click. No toast.
- [!] **Archived band** — CL:344-352; `onClick → setArchOpen(v => !v)`; label `Archived · N letter(s) from rejected applications & skipped jobs`; right text `hide ⌄` / `browse ›` driven by `showArch` (CL:350), so while a search query is active the band reads `hide ⌄` even if the stored preference is closed, and clicking it toggles the stored pref without visibly changing anything. Only rendered when `archived.length > 0` (CL:343). Mutates `archOpen` → localStorage (CL:124). No API. — **CL-23**
- [x] **Archived letter row** — `row(c, true)` CL:354 (only when `showArch`): same handler as active row; dimmed (`--recessed` bg, `--line-soft` border, `--text-2` name) CL:260-263; chip always shown (`stage` or `Draft`).
- [x] Explicitly NOT present on this screen: no ⋯ menu on rows, no delete from the list, no sort control, no status/stage filter, no date filter, no "open" secondary action, no rename, no bulk select, no pagination. Delete only exists inside the editor.
- [x] All buttons/rows are `div`/`span` with `onClick` — no `role`, `tabIndex`, or key handlers; only the search `<input>` is keyboard reachable.

### 4. States rendered

- [x] **Empty (no letters at all)**: `letters.length === 0` and nothing pending → `No cover letters yet — generate one on the left.` CL:356-358.
- [x] **Zero search results**: `visible.length === 0 && pending.length === 0 && letters.length > 0` → `Nothing matches that search.` CL:358.
- [x] **Pending only** (empty list + running generation): the empty copy is suppressed by `pending.length === 0` guard (CL:356) — only the dashed row shows.
- [x] **Archived present**: band CL:343-353; rows only when `showArch` CL:354. Active/archived split rule CL:206-213: `stage ? stage !== 'rejected' : job_status ∈ {new,saved,applied}`; letters whose job was deleted (`job_status` null) sink to archive; any non-`rejected` application stage (e.g. ghosted/withdrawn if such exist) counts as active.
- [x] **Loading**: DOES NOT EXIST — `letters` starts `[]` (CL:108) so the "No cover letters yet" copy flashes until `GET /cover-letters` resolves.
- [!] **List load error (500/network)**: DOES NOT EXIST — console only (CL:131); screen shows "No cover letters yet" (misleading). — **CL-05**
- [x] **No résumés to pair**: only the shared Picker popover copy `Nothing to pick yet.` CL:55 (no panel-level hint, Generate stays dimmed with tooltip `Pick a résumé and a job first`).
- [x] **No saved/applied jobs**: same shared `Nothing to pick yet.` CL:55. No link to the feed.
- [!] **No voice presets** (settings empty/unparseable): DOES NOT EXIST — `VoicePicker` renders an empty flex row (CL:74-84), `genVoice=''` is sent to the backend. — **CL-13**
- [x] **Generate 409 duplicate**: inline `err` = backend detail `generate_cover_letter is already running for this pair` CL:241,320. Normally unreachable from the UI because `thisPairRunning` dims the button and `genJob` is cleared after launch (CL:239) — reachable if another tab/session started the same pair.
- [x] **Generate request failure (400/404/500)**: inline `err` CL:320 with backend detail (e.g. `Job has no description`, `Persona has no resume_content — fill it in /persona first`, `cover_letter_prompt setting is empty — configure it in Settings`). Cleared on next Generate click (CL:228) only.
- [!] **Background generation failure** (LLM error after 202): DOES NOT EXIST — row disappears, `load()` runs, no new letter, no message, no toast (CL:183). — **CL-06**
- [!] **Pending row label fallback**: `a cover letter` when neither `runMeta` nor a matching job is known (CL:250) — e.g. Regenerate runs launched from the editor (their `target_job_id` may be outside the 200-job window). — **CL-20**
- [x] **Long strings**: row name single-line ellipsis + `title` tooltip CL:263; sub-line ellipsis CL:264; header count line ellipsis CL:281; Picker control label ellipsis CL:48; Picker option label/sub ellipsis CL:61-62; pending label ellipsis CL:334; voice chips `nowrap` — long preset labels widen chips and wrap the row CL:81. `h1` has no ellipsis (static text).
- [x] **Stage chip class coverage**: only `applied/interview/offer/rejected` mapped (CL:19); every other stage value renders `cc-generic`.
- [~] `ago()` helper CL:7-14 floors to minutes; minimum `1m`; no "just now"; no seconds; `''` for null → sub-line reads `edited  ago` (double space) when `updated_at` is null. — untestable: no way to produce a null updated_at (server default, non-null)

### 5. Hover styles

- [!] `.v2-menuitem` on Picker options — CL:57 → `theme.css:148` (`background: var(--surface-2)`). — **CL-08**
- [x] `.v2-bd` on letter rows — CL:259 → `theme.css:152` (`border-color: var(--accent) !important`). Archived rows get the same accent border on hover despite the dimmed look.
- [x] `.v2-archband` on the archive band — CL:344 → `theme.css:167` (`border-color: var(--edge) !important`).
- [x] `.v2-ctl` on the band's `browse ›` span — CL:349 → `theme.css:160` — NOT a hover rule (line-height only).
- [~] `.v2-scroll` scrollbar skin — CL:54, 291, 330 → `theme.css:221-223`. `.v2-gutter-head` / `.v2-gutter` — CL:325, 330 → `theme.css:215-216` (scrollbar-gutter, not hover). — untestable: overlay scrollbars are 0 px wide in headless Linux
- [x] `.v2-spin` — CL:317, 333 → `theme.css:226`.
- [x] Chip classes `cc-smartrecruiters / cc-workday / cc-tier1 / cc-generic` — CL:19, 267 → `theme.css:182-198` (no hover).
- [x] No `onMouseEnter`/`onMouseLeave`, no `style-hover`, no `:focus` styling anywhere in the file. Inline state-driven (not hover) colour switches: Picker open border CL:47; selected option CL:59-60; chip/segment "on" CL:80-81, 96-97; Generate `opacity .55`/cursor CL:316.
- [x] **No hover at all** on: Generate button (CL:315), voice chips (CL:78), length segments (CL:94), Picker control (CL:47), search input (CL:284, `outline: none` — no focus ring either).

### 6. Theme

- [x] Dark mode read: `V2App.jsx:52` (`localStorage.jobnavigator_dark_mode === 'true'`), applied as `data-theme="dark"|"light"` on `.jn-v2` root `V2App.jsx:90`; token overrides in `theme.css:74` (`.jn-v2[data-theme="dark"]`). CoverLetters.jsx never reads the theme — it only uses `var(--*)` tokens.
- [x] Colour literals in CoverLetters.jsx: **none** (grep for `#hex`, `rgb(`, `hsl(` returned nothing). Only `'transparent'` (CL:60, 285, 317, 333).
- [x] Tokens used: `--muted --edge --surface --text --text-2 --line --line-soft --line-strong --shadow-menu --accent --accent-soft --accent-ink --recessed --bg --bad --serif --mono --sans`. Verify each is defined in both palettes in `theme.css:4-118`.

### 7. Suspicious

- [x] CL:36,54 — `Picker` prop `width` is never passed by any caller (CL:296, 302, ED:473); always falls back to `'100%'`.
- [x] CL:62 — `o.sub` (two-line option) is rendered but no caller ever supplies `sub` (`resumeOpts` CL:191, `jobOpts` CL:196, `sourceOpts` ED:232) — dead branch; the comment at CL:34-35 justifying the custom popover ("two-line job labels") describes a feature that is not used.
- [!] CL:46 + CL:38-43 — Picker closes on document click, but the wrapper `stopPropagation` means clicking the OTHER Picker's control does not close the first: résumé and job popovers can be open simultaneously (job popover overlaps and z-index ties at 40). — **CL-07**
- [!] CL:152-170 — deep-link effect has `[]` deps with `eslint-disable`; a dead `?job=` id leaves `genJob` set to an unpickable value and Generate enabled (backend 404 surfaces as inline err). — **CL-04**
- [x] CL:164 — `?resume=persona` triggers `GET /api/resumes/persona` (guaranteed failure, swallowed).
- [!] CL:131 — `load()` failure is console-only; screen then claims "No cover letters yet". — **CL-05**
- [!] CL:183 — a run that ends in `failed` triggers a reload identical to success; no failure UI (no `/monitor/history` lookup, no toast). — **CL-06**
- [!] CL:178 — pending filter is by `job_type` only; editor Regenerate runs appear as list pending rows labelled `a cover letter`. — **CL-20**
- [x] CL:215-216 — `live` counts LETTERS with a non-rejected stage, but the copy says `N live application(s)`; two letters for the same job count twice.
- [!] CL:347 vs CL:216 — archived count derives from `visible` (search-filtered) while the header count line uses unfiltered `letters` — they disagree while a query is typed. — **CL-23**
- [x] CL:126 — `runMeta` is never pruned (grows for the session); harmless.
- [x] CL:212-213 — `useMemo` deps omit `isActive`/`LIVE_JOB` (re-created every render) — lint smell only, behaviour correct.
- [x] CL:197, 250 — `${j.title}` unguarded when `company` is set → `"Acme — null"` possible.
- [x] CL:284 — placeholder has a trailing space `Search letters, companies… `.
- [!] Toast.jsx is never imported: zero toasts on this screen (HANDOVER item 2 expects the non-dismissing `error` toast at every failure site). — **CL-18**
- [x] No `console.log`, no `TODO/FIXME`. `console.error` at CL:131 only.
- [!] All controls are non-semantic `div`/`span` — no keyboard operability, no `aria-*`. — **CL-21**

### 8. Counts that must agree

- [!] Header line `N letter(s) · M live application(s)` — CL:216: `N = letters.length` (`GET /api/cover-letters` array length, unfiltered), `M` = letters where `stage && stage !== 'rejected'` (`stage` = newest `Application.status` for the letter's job, `routes_cover_letters.py:135,147`). — **CL-23**
- [!] "All letters" gutter number — CL:327: `letters.length + pending.length` — includes running generations (and editor Regenerate runs, which will NOT add a row when they finish → the number drops by one on completion). — **CL-20**
- [!] Rail badge `Cover Letters · N` — `V2App.jsx:63` (`GET /api/cover-letters` length, fetched once at shell mount, never refreshed after generate/delete) vs CL:216 `letters.length` (refreshed after each completed run). Expect drift until full reload. — **CL-17**
- [x] Archived band `Archived · N letter(s)` — CL:347: `archived.length` from the search-filtered `visible`; must equal the rows rendered when expanded (CL:354) and, with an empty query, `letters.length − active.length`.
- [x] Row age appears twice per row: sub-line `edited {ago} ago` (CL:257) and right column `{ago}` (CL:270) — both from `updated_at`; must match each other and the editor's `saved … ago` after navigation.
- [~] Stage chip text (CL:268) must match the editor top-bar badge (ED:243,257) and the card's column on `/v2/applications` for the same job. — untestable: cross-screen: /v2/applications not in scope; API stage value verified only
- [x] Sub-line voice/length labels (CL:255-256) resolve preset id → `label` from `/api/settings`; must match the editor context band (ED:244-246) for the same letter.
- [x] `~30s` (CL:337) is static copy; compare against the editor modal's `~30 seconds` (ED:486).

---

## Screen 2 — Cover Letter Editor (`/v2/cover-letters/:id`)

### 1. Routes & params

- [x] Route: `<Route path="cover-letters/:id" element={<V2CoverLetterEditor />} />` — `frontend/src/App.jsx:162`, nested under `/v2` (`App.jsx:153`). `id` from `useParams()` ED:63.
- [x] Tab title: `useTitle(doc?.name)` ED:66 → `"{name} · JobNavigator"` once loaded (`useTitle.js:47-54`); before load, `TitleSync` gives "Cover Letters · JobNavigator" (`useTitle.js:14`).
- [!] Missing / deleted id: `GET /api/cover-letters/{id}` → 404 (`routes_cover_letters.py:187`) → `.catch` sets `err='Could not load this letter.'` ED:106 → full-screen centred text ED:237-239. No redirect, no back link (rail still visible). Same copy for 500 and network failure. — **CL-15**
- [!] Non-UUID id (e.g. `/v2/cover-letters/abc`): backend compares a string to a UUID column → likely 500 on Postgres; UI branch identical to 404. — **CL-16**
- [x] Changing `:id` while mounted re-runs the load effect (`[id]` deps ED:108) with a `dead` flag ED:97,100,107; the secondary loads (templates/resumes/persona/settings) do NOT re-run (`[]` ED:120).
- [x] No query params handled. No `location.state`.
- [x] localStorage **read**: `v2_cl_sections` (const `UI_KEY` ED:14) via `loadUI()` ED:15 in the three `useState` initialisers ED:86-88 (`headOpen` default `false`, `recipOpen` default `false`, `letterOpen` default `true`).
- [x] localStorage **write**: `v2_cl_sections` = `JSON.stringify({headOpen, recipOpen, letterOpen})` on any change — ED:89 (also on first mount).
- [x] Axios reads `jobnavigator_api_key` — `api.js:11`. Shell keys as for Screen 1.

### 2. Data loads

- [x] `GET /api/cover-letters/{id}` — ED:99-107 on mount / id change → `doc`, `data = {...EMPTY, ...json_data}` (ED:101), `template`, `format` (default `letter`), `savedAt = updated_at`, `rSource` (`'persona'` if `from_persona` else `resume_id`), `rVoice`, `rLength` (ED:102-104); `loaded.current = true` gates autosave (ED:105,127). Failure → `err` (ED:106).
- [x] `GET /api/cover-letters/templates` — ED:111 → `templates` `[{id,name,description}]` (`routes_cover_letters.py:33-50,81-83`). Swallowed.
- [x] `GET /api/resumes?is_base=true` — ED:112 → `resumes` (Regenerate source options). Swallowed.
- [x] `GET /api/persona` — ED:113 → `personaAvailable`. Swallowed.
- [x] `GET /api/settings` — ED:114-119 → `presets` (parsed), `rVoice` fallback to `cover_letter_default_voice` only if the letter had no voice (ED:118). Swallowed.
- [!] `PATCH /api/cover-letters/{id}` — `persist(patch)` ED:126-133: 500 ms trailing debounce (ED:129,132) keyed on ONE timer for all patch kinds; body is exactly the last `patch` passed (`{json_data}` from `update` ED:139, `{template}` ED:164, `{page_format}` ED:165). On success `savedAt = client now`, `err=''` (ED:130). On failure: console + `err='Could not save — your last edit is not stored.'` (ED:131). Allowed fields server-side: `name, template, page_format, json_data, job_id, resume_id, voice, length` (`routes_cover_letters.py:196-197`). — **CL-01**
- [x] `GET /api/cover-letters/{id}/pdf` (arraybuffer, abortable) — live preview effect ED:145-162: fires 900 ms after any change to `data | template | format | doc | id` (ED:150,162); `pdfBusy=true` immediately on every keystroke (ED:149); previous in-flight request aborted on re-run (ED:160); blob URL swapped and old one revoked (ED:153-156). Failure: console only unless `CanceledError` (ED:157); `pdfBusy` cleared (ED:158); previous PDF (or "Rendering the preview…") remains.
- [x] `GET /api/cover-letters/{id}/pdf` (blob) — `download()` ED:169-180 on demand.
- [x] `DELETE /api/cover-letters/{id}` — `remove()` ED:182-187 on demand (server also deletes tracer links, `routes_cover_letters.py:239`).
- [x] `POST /api/cover-letters/generate` — `regenerate()` ED:189-201, body `{resume_id: rSource, job_id: doc.job_id, voice: rVoice, length: rLength, cover_letter_id: id}` (ED:193-196). Server scope key becomes `cl:{cover_letter_id}` (`routes_cover_letters.py:341`).
- [!] **Polling** `GET /api/monitor/active` — ED:204-223, ONLY while `regening` is true; `setInterval` 2000 ms (ED:221), no immediate tick. Keyed by `job_type === 'generate_cover_letter'` only (ED:210) — NOT by `scope_key === 'cl:{id}'`, so it waits for every cover-letter run system-wide. When none live: `clearInterval` (ED:212) THEN `GET /api/cover-letters/{id}` (ED:213) → state reset (ED:215-218), `regening=false`, modal closed. Poll failure swallowed (ED:220). — **CL-02, CL-03**
- [x] `GET /api/cover-letters/{id}/tracer-stats` — **never called** (endpoint exists `routes_cover_letters.py:206`). No tracer-stats UI on this screen.
- [x] Regenerate state is NOT rehydrated from `/monitor/active` on mount (unlike the résumé editor's background score-resume described in CLAUDE.md): navigate away and back mid-regenerate → no spinner, no poll; the letter silently changes on a later reload.

### 3. Interactive elements

Top bar (ED:253-262):

- [x] **‹ Cover Letters** — ED:254; `navigate('/v2/cover-letters')`; class `v2-ctl`; no API.
- [x] **Stage badge** — ED:256-257 (`stage.toUpperCase()` or `DRAFT`, class from `STAGE_CLASS`/`cc-generic`); not interactive.
- [x] **Letter name** — ED:258; `title` tooltip, `maxWidth 420` ellipsis; not editable anywhere in v2 (backend allows `name` PATCH; regenerate overwrites it to `"{company} — {title}"` `routes_cover_letters.py:450`).
- [x] **Save status text** — ED:259-261: `err` (red) | `saved {ago} · autosaves` | `autosaves`. `savedAt` after a save is the CLIENT clock (ED:130) while the initial value is the server `updated_at` (ED:102). Not interactive. `ago` only re-renders on other state changes (no timer) so "saved just now" can go stale.

Context band (ED:265-312):

- [x] **Written for … · from {source_name} ↗** — ED:268-271; source span `onClick → doc.resume_id && navigate('/v2/resumes/{resume_id}')`; cursor/`↗` only when `resume_id` (Persona source is inert with tooltip `Written from your Persona`); no hover class. Only rendered when `source_name` is truthy (ED:269). Note `${doc.title}` unguarded when `company` set (ED:268).
- [x] **Regenerate…** (pill) — ED:275-281; `onClick → setRegenOpen(true); setMenuOpen(false)`; tooltip `Rewrite the letter — pick base résumé, voice and length`; shows spinner in place of `↻` while `regening` (ED:277-279); class `v2-ctl`; always clickable (even while regening — reopens the modal).
- [x] **⋯ menu toggle** — ED:283-284; `setMenuOpen(v => !v)`; tooltip `More actions`; open-state border/background inline; wrapper stops propagation (ED:282); closes on document click / Escape (ED:225-230).
- [x] **▤ View application** — ED:288-291; only if `doc.has_application`; `navigate('/v2/applications')` — NO deep-link to the specific application/company. class `v2-menuitem`.
- [x] **☰ View job in feed** — ED:294-297; only if `doc.job_id`; `navigate('/v2/feed?job={job_id}')`. class `v2-menuitem`.
- [x] **↗ Open job posting** — ED:300-303; only if `doc.job_url`; real `<a target=_blank rel=noopener noreferrer>`; `onClick → setMenuOpen(false)`. The only keyboard-focusable control besides inputs. class `v2-menuitem`.
- [x] **✕ Delete letter** — ED:305-308 → `remove` ED:182-187: closes menu, native `window.confirm('Delete "{name}"? This cannot be undone.')` (ED:184), then `DELETE /api/cover-letters/{id}` → `navigate('/v2/cover-letters')`. Success: no toast, no undo. Failure: console + `err='Could not delete this letter.'` in the top-bar slot (ED:186); no toast. class `v2-hover-bad`. Always present in the menu.

Header card (ED:318-355; `Card` ED:38-60):

- [x] **Card toggle (Header)** — ED:318 → header row ED:41 `onClick=onToggle` → `setHeadOpen`; chevron rotates (ED:43-46); persisted to `v2_cl_sections` (ED:89). class `v2-clhead`.
- [x] **Full name** input — ED:321; `update(d => d.header.name = …)` → `PATCH {json_data}` (debounced); `style INPUT` (`outline: none`).
- [x] **Contact item ▲ Move up** — ED:333-334; swaps `contact_items[i-1]↔[i]`; inert at `i===0` (opacity .35, cursor default; handler short-circuits). class `v2-hover-accent-text`. Tooltip `Move up`.
- [x] **Contact item ▼ Move down** — ED:335-336; symmetrical; inert on last.
- [!] **Contact "Display text"** input — ED:338-339; `contact_items[i].text`; `CELL` style, fixed 170 px. — **CL-24**
- [x] **Contact "URL (optional)"** input — ED:340-341; `contact_items[i].url`; accent-coloured text.
- [x] **Contact "id" stub** input — ED:343-345; rendered ONLY when `tracked = url && !url.startsWith('mailto:')` (ED:329); tooltip `Short stub for the tracer link id (e.g. l, w, gh)`; `contact_items[i].stub`. Typing a URL makes this field appear mid-row (layout shift). Column header hint `text · link · stub` ED:326 is always shown even when no row is tracked.
- [x] **Contact ✕ Remove** — ED:347-348; `splice(i,1)`; no confirm. class `v2-hover-bad-text`. Tooltip `Remove`.
- [x] **+ Add contact item** — ED:352-353; appends `{text:'', url:''}`. class `v2-dashadd`.

Recipient card (ED:357-377):

- [x] **Card toggle (Recipient)** — ED:357-358; `note` = `company · date` (ED:357) with ellipsis (ED:50); `setRecipOpen`.
- [x] **Company** input — ED:362; `recipient.company`.
- [x] **Date** input — ED:366; plain text `data.date` (no date picker, no validation/format).
- [x] **Hiring manager** input — ED:370; placeholder `Unknown`; `recipient.manager`.
- [x] **Address** input — ED:374; placeholder `—`; `recipient.address`; single-line (no multiline address).

Letter card (ED:379-412):

- [x] **Card toggle (Letter)** — ED:379-380; `note` = `N paragraph(s)`; `setLetterOpen` (default open).
- [x] **Greeting** input — ED:383; `data.greeting` (default `Dear Hiring Team,` from `EMPTY` ED:11 only when `json_data` lacks the key).
- [x] **Paragraph ↑ Move up** — ED:389-390; swap `body_paragraphs[i-1]↔[i]`; inert at 0 (colour `--line-strong`, cursor default). class `v2-parabtn`. Tooltip `Move up`.
- [x] **Paragraph ↓ Move down** — ED:391-392; inert on last. class `v2-parabtn`.
- [x] **Paragraph ✕ Delete** — ED:393-394; `splice(i,1)`; no confirm; can delete the last paragraph (→ `0 paragraphs`). class `v2-parabtn-bad`. Tooltip `Delete paragraph`.
- [x] **Paragraph textarea** — ED:396-397; `rows=4`, `resize: none`, no auto-grow (long text scrolls inside 4 rows); `body_paragraphs[i] = value`. Keyed by index (ED:386) — reorder/delete re-keys, cursor/focus may jump.
- [x] **+ Add paragraph** — ED:400-401; appends `''`. class `v2-dashadd`.
- [x] **Closing** input — ED:405; `data.closing` (default `Sincerely,`).
- [x] **Signature** input — ED:409; `data.signature`.
- [x] Not present: no bold/italic/rich text, no word/char count, no spell-check toggle, no "reset to generated", no per-paragraph regenerate, no undo.

Preview toolbar (ED:417-452):

- [x] **Template control** `Template {name} ▾` — ED:422-425; `setTplOpen(v=>!v); setFmtOpen(false)`; tooltip `Cover letter template`; classes `v2-bd v2-ctl`; label = `templates.find(id).name || template || 'Template'` (ED:247). Wrapper stops propagation (ED:421).
- [!] **Template option** — ED:429-430 → `pickTemplate(t.id)` ED:164: `setTemplate`, close, `persist({template})` → `PATCH`. `title` = template `description`. class `v2-menuitem`. Selected = accent. Popover 210 px, `maxHeight 300`, class `v2-scroll`. Renders EMPTY popover (no copy) when `templates=[]`. — **CL-01, CL-08**
- [x] **Paper control** `Paper {US Letter|A4} ▾` — ED:437-440; `setFmtOpen(v=>!v); setTplOpen(false)`; tooltip `Paper size — US Letter or A4`; classes `v2-bd v2-ctl`. Options from `PAGE_FORMATS` ED:13 (hard-coded, not from API).
- [!] **Paper option** — ED:444-445 → `pickFormat(f)` ED:165: `setFormat`, close, `persist({page_format})` → `PATCH`. class `v2-menuitem`. — **CL-08**
- [!] **↓ Download PDF** — ED:451 → `download` ED:169-180: `GET …/pdf` as blob via axios (keeps `X-API-Key`), filename from `content-disposition` else `CoverLetter.pdf` (ED:172-176), synthetic `<a download>` click, URL revoked after 1 s. Success: no toast. Failure: console + `err='Could not download the PDF.'` in the top-bar slot (ED:179). class `v2-ctl`. Note: downloads the SERVER state — if clicked within the 500 ms save debounce, the PDF lacks the last keystrokes. — **CL-11**
- [x] **PDF spinner** — ED:419 while `pdfBusy`; not interactive.
- [~] **PDF iframe** — ED:455 `src={pdfUrl}#view=FitH`, `title="cover letter preview"`; browser-native PDF viewer controls (zoom/print/download inside the viewer bypass the app). Fallback text ED:456. — untestable: headless Linux has no PDF plug-in; blob loads but renders nothing

Regenerate modal (ED:461-495):

- [x] **Scrim** — ED:462; `onClick → !regening && setRegenOpen(false)`; inner panel stops propagation (ED:463).
- [!] **Escape key** — ED:227: closes menus AND the modal unconditionally (`setRegenOpen(false)` even while `regening` — inconsistent with scrim/Cancel guards). The regenerate still completes; the poll (ED:204) still reloads. — **CL-25**
- [x] **From résumé Picker** — ED:473; options = Persona (if available) + base résumés (ED:232-235); `onPick → setRSource`; placeholder `Select a source…`; hint ED:474. If the letter's original `resume_id` was since deleted, `rSource` holds an unpickable id (control shows placeholder) but the Regenerate button is enabled → backend 404 `Resume not found` → `err`.
- [x] **Voice chips** — ED:478 (`VoicePicker`, shared) → `setRVoice`.
- [x] **Length segments** — ED:482 (`LengthPicker`, shared) → `setRLength`.
- [x] **Cancel** — ED:487; `!regening && setRegenOpen(false)`; no hover class.
- [x] **Regenerate** (primary) — ED:488-491 → `regenerate` ED:189-201; guard `regening || !rSource` (ED:190; button dimmed `.6`, cursor default). API `POST /api/cover-letters/generate` with `cover_letter_id`. On 202: `regening=true`, poll starts (ED:204), label `Regenerating…` + spinner (ED:489-490), modal stays open until reload. Request failure (400/404/409/500): `regening=false`, `err` = backend detail (ED:198-199) — shown in the TOP BAR slot (ED:260), i.e. behind the still-open modal scrim, not inside the modal. No toast either way.
- [!] **Lineage on regenerate**: NONE. Backend rewrites the same row in place (`routes_cover_letters.py:445-461`: `name, resume_id, from_persona, json_data, voice, length` replaced; `template`/`page_format` kept because the editor does not send them). `parent_id` is neither set nor read by v2 (it is in the API dict `routes_cover_letters.py:97` but unused in ED). Previous text is unrecoverable — modal copy ED:467 warns `your edits to this draft are replaced`. Post-reload `savedAt = updated_at` (ED:216) → header reads `saved just now`. — **CL-22**
- [x] Links to paired records: source résumé (ED:269, context band), job in feed (ED:294), application board (ED:288), posting URL (ED:300). No link from the editor to "other letters for this job".

### 4. States rendered

- [x] **Loading**: `!doc` → centred `Loading…` ED:237-239 (shares the branch with error).
- [!] **Id not found / load error**: `!doc && err` → `Could not load this letter.` ED:106,238. No retry, no back link, no distinction 404 vs 500. — **CL-15**
- [!] **Autosave states** ED:259-261: `autosaves` (never saved this session) | `saved {ago} · autosaves` | red `err` text (save/download/delete/regenerate failure). `err` is cleared only by a successful save (ED:130) or by starting a regenerate (ED:191) — a download failure message therefore persists until the user edits something. — **CL-28**
- [x] **Save failure**: `Could not save — your last edit is not stored.` ED:131 (local state keeps the edit; next keystroke retries the whole `json_data`).
- [x] **PDF not yet rendered**: `Rendering the preview…` ED:456 (also the permanent state if every PDF request fails — no error copy). Spinner ED:419 while a request is pending/debouncing.
- [!] **PDF failure (500 `PDF generation failed`, missing template 400)**: DOES NOT EXIST — console only ED:157; last good preview stays. — **CL-19**
- [!] **Regenerate request failure**: `err` in top bar (ED:199,260); modal remains open. **Background regeneration failure**: DOES NOT EXIST — poll sees no live run, reloads the unchanged letter, closes the modal silently (ED:211-218). — **CL-14**
- [x] **Regenerate 409** (same letter already regenerating from another tab / after navigating away and back): `err` = `generate_cover_letter is already running for this pair` ED:199. Not otherwise guarded on mount.
- [x] **No templates** (`templates=[]`): control label falls back to raw `template` id or `Template` (ED:247); popover renders empty with no copy (ED:427-432).
- [x] **No résumés + no persona** in the Regenerate modal: Picker `Nothing to pick yet.` (CL:55, shared); Regenerate stays dimmed.
- [x] **No voice presets**: `VoicePicker` renders empty (no copy); `voiceLen` in the context band falls back to `voice and length not recorded` only when BOTH are falsy (ED:246); otherwise shows the raw id.
- [x] **Menu with nothing linked** (no application, no job, no url): only `Delete letter` (ED:287-308 conditionals).
- [x] **Persona-sourced letter**: source label inert, tooltip `Written from your Persona`, no `↗` (ED:270-271).
- [x] **Letter without job** (`job_id` null): `Written for {doc.name}` fallback (ED:268); modal copy `this role` (ED:467); Regenerate posts `job_id: null` → backend 400 `resume_id and job_id are required` → `err`.
- [x] **Zero paragraphs**: note `0 paragraphs` (ED:379), only the add button; PDF renders an empty body.
- [x] **Zero contact items**: only `+ Add contact item` (ED:352); hint `text · link · stub` still shown (ED:326).
- [x] **Missing json_data keys**: `EMPTY` defaults merged (ED:8-12,101) — `header`, `recipient`, `greeting`, `closing`, `body_paragraphs=['']`; inputs use `?.` + `|| ''` (ED:321,362-374,383,405,409).
- [x] **Long strings**: name ellipsis + tooltip ED:258 (maxWidth 420); context line ellipsis ED:267; Card note ellipsis ED:50; template option names NOT ellipsed in the 210 px popover (ED:430) — long names wrap; paragraph textarea fixed 4 rows (ED:396); contact URL cell shrinks (`flex:1, minWidth 0`); stage badge no truncation (uppercase raw stage string ED:243). `err` string in the top bar is unbounded and can push the name off (no ellipsis on ED:259).
- [!] `ago()` ED:17-24 has `just now` (unlike the list's helper CL:7-14) — the two screens format the same timestamp differently (`5m` vs `5m ago`). — **CL-26**

### 5. Hover styles

- [x] `.v2-clhead` — Card header rows ED:41 → `theme.css:163` (`background: var(--bg)`).
- [x] `.v2-ctl` — ED:254, 276, 422, 437, 451, 488 → `theme.css:160` (line-height only; NOT a hover rule — none of these have a hover style: back link, Regenerate pill, Download, modal Regenerate).
- [x] `.v2-menuitem` — ED:288, 294, 300, 429, 444 → `theme.css:148`.
- [x] `.jn-v2 a:hover` (`theme.css:121`, `color: var(--text)`) applies to the `Open job posting` anchor ED:300, but the inline `color: var(--text-2)` wins (no `!important`) — text colour does not change on hover; only the `v2-menuitem` background does.
- [x] `.v2-hover-bad` — Delete menu item ED:305 → `theme.css:130` (`background: var(--bad-soft) !important`).
- [x] `.v2-hover-accent-text` — contact ▲▼ ED:334, 336 → `theme.css:173` (`color: var(--accent) !important`) — also applies to the DISABLED end arrows (opacity .35) on hover.
- [x] `.v2-hover-bad-text` — contact ✕ ED:348 → `theme.css:174`.
- [x] `.v2-dashadd` — add contact ED:353, add paragraph ED:401 → `theme.css:145-146` (border/background/color).
- [x] `.v2-parabtn` — paragraph ↑↓ ED:389, 391 → `theme.css:169` (`background: var(--surface-2)`) — also on the disabled end arrows.
- [x] `.v2-parabtn-bad` — paragraph ✕ ED:393 → `theme.css:170`.
- [x] `.v2-bd` — Template/Paper controls ED:422, 437 → `theme.css:152` (accent border).
- [x] `.v2-scroll` — ED:316 (editor column), 427 (template popover). `.v2-spin` — ED:278, 419, 489.
- [x] Chip `cc-*` on the stage badge ED:256 (no hover).
- [x] No `onMouseEnter`/`onMouseLeave`, no `style-hover`. State-driven (not hover) inline switches: ⋯ open border/background ED:284; Regenerate primary opacity ED:488; selected template/format option ED:430, 445; disabled arrow colours ED:390, 392.
- [!] **No hover** on: Cancel ED:487, scrim ED:462, source-résumé link ED:269, ⋯ toggle ED:283, all inputs. **No focus ring** on any input/textarea (`outline: 'none'` at ED:30 `CELL`, ED:34 `INPUT`, ED:397 textarea) — keyboard focus is invisible. — **CL-21**

### 6. Theme

- [x] Dark mode read: `V2App.jsx:52`; applied `data-theme` on `.jn-v2` `V2App.jsx:90`; dark tokens `theme.css:74`. CoverLetterEditor.jsx never reads the theme itself.
- [x] Colour literals in CoverLetterEditor.jsx: **none** (grep empty). Only `'transparent'` (ED:278, 397, 419, 430, 445, 489) and `currentColor` (ED:45 SVG stroke, ED:278 spinner border).
- [~] The PDF preview (ED:455) is server-rendered paper — always white regardless of `data-theme`; the `#view=FitH` hash is a PDF viewer hint, not a colour. Check the dark-mode iframe chrome/background seam against `--surface-2` (ED:416). — untestable: no PDF plug-in in the container, seam not judgeable
- [x] Tokens used beyond the list's set: `--surface-2 --scrim --shadow-modal --line-strong` (plus `--bad-soft`, `--hover-soft` via theme.css hover rules). Verify all exist in both palettes.

### 7. Suspicious

- [!] ED:126-133 **debounce drops patches**: `persist()` keeps ONE timer and replaces the pending `patch` wholesale. Typing (`{json_data}`) then picking a template (`{template}`) within 500 ms discards the `json_data` patch; picking a template then typing within 500 ms discards the `template` patch (template is then never saved until re-picked). Patches are not merged. — **CL-01**
- [!] ED:212-213 **stuck regenerating**: `clearInterval(iv)` runs BEFORE the reload `GET`; if that GET throws it is swallowed (ED:220), the interval is already gone, `regening` stays `true` → spinner and modal locked (Cancel/scrim refuse while `regening`; only Escape ED:227 closes the modal, and the Regenerate button stays dimmed). — **CL-02**
- [!] ED:210 poll matches ANY `generate_cover_letter` run, not `scope_key === 'cl:{id}'` — a generation started on the list keeps this editor's modal open until all runs finish. — **CL-03**
- [x] ED:189-201 / ED:96-108 `regening` not rehydrated from `/monitor/active` on mount — leave and return mid-regenerate → no indication; a second click gets 409.
- [!] ED:227 Escape closes the modal during regeneration while ED:462/487 refuse — inconsistent guard. — **CL-25**
- [x] ED:135-142 `persist()` side-effect inside the `setData` updater (runs twice under React StrictMode in dev; harmless because debounced, but a smell).
- [x] ED:145-162 PDF debounce (900 ms) is independent of the save debounce (500 ms) — if the `PATCH` takes >400 ms the preview renders the pre-edit server state; also `setPdfBusy(true)` on every keystroke (ED:149) makes the spinner flicker continuously while typing.
- [x] ED:169-180 Download reads server state; within the 500 ms save window the file is stale; no "saving…" guard.
- [!] `GET /cover-letters/{id}/tracer-stats` never called — stub inputs (ED:343) configure tracer links but no stats/click counts are displayed anywhere in v2. — **CL-22**
- [x] ED:288 `View application` navigates to `/v2/applications` with no id/company deep-link.
- [!] ED:259-260 single `err` slot shared by load/save/download/delete/regenerate; regenerate failures render behind the modal scrim (ED:462 zIndex 60 over the top bar) — the user may not see them. — **CL-14, CL-28**
- [x] ED:184 native `window.confirm` for delete (inconsistent with the design's modal language); no undo toast after delete.
- [!] ED:106,238 identical copy for 404 / 500 / offline; no back link or retry. — **CL-15**
- [x] ED:103 `rSource` may hold a deleted résumé id → Regenerate enabled → 404. Same class of bug as CL:156.
- [x] ED:268 `${doc.title}` unguarded when `company` is set → `"Acme — null"` possible.
- [x] ED:326 column hint `text · link · stub` is shown even when no row has a stub cell.
- [x] ED:386 paragraph rows keyed by array index — moving/deleting re-keys textareas; check focus/cursor after ↑↓ while typing.
- [x] ED:4 imports `Picker, VoicePicker, LengthPicker, LENGTHS, STAGE_CLASS` from `./CoverLetters` — the list screen module is loaded for the editor route; a change to the list file affects the editor.
- [x] ED:11 `EMPTY` defaults `greeting: 'Dear Hiring Team,'`, `closing: 'Sincerely,'` are injected client-side when the key is missing — but NOT persisted until the user edits something (server PDF may differ from the editor's displayed defaults until then).
- [!] Toast.jsx never imported: zero toasts on this screen (delete, download, save, regenerate all silent on success). — **CL-18**
- [x] No `console.log`, no `TODO/FIXME`. `console.error` at ED:131, 157, 179, 186.
- [!] All buttons are `div`/`span` — no keyboard access except inputs and the one `<a>` (ED:300). No `aria-expanded` on the three popovers/menu. — **CL-21**
- [x] Dead/unused: none found beyond the shared `Picker` `width`/`sub` props (see list §7). `Card` prop `note` optional (Header card omits it) — fine.

### 8. Counts that must agree

- [x] Letter card note `N paragraph(s)` — ED:379 from `data.body_paragraphs.length`; must equal the paragraph blocks rendered (ED:385) and the paragraphs in the PDF preview/download (server `json_data.body_paragraphs`).
- [x] Recipient card note `{company} · {date}` — ED:357 from `data.recipient.company` / `data.date`; must match the PDF header block and the Company/Date inputs.
- [x] Stage badge ED:243/257 = `doc.stage` (newest `Application.status` for `doc.job_id`, `routes_cover_letters.py:135`) — must agree with the list row chip (CL:268) and `/v2/applications`.
- [x] `has_application` (ED:287) is derived server-side as `bool(stage)` (`routes_cover_letters.py:113`) — the `View application` item and the non-DRAFT badge must appear/disappear together.
- [x] `saved {ago}` ED:260 — initial from server `updated_at`, then client clock after each PATCH; must be consistent with the list row `edited {ago} ago` / right-column age (CL:257,270) after navigating back (list uses server `updated_at` from a fresh `GET`).
- [x] Context band `voice · length` ED:244-246 vs list sub-line CL:255-256 vs the modal's pre-selected chips (`rVoice`/`rLength`, ED:104) — all from the same letter fields; after Regenerate all three must update together (ED:217 resets `rVoice`/`rLength` from the reloaded doc).
- [x] `~30 seconds` ED:486 vs list `~30s` CL:337 — static copy; check both against real generation time.
- [x] Template control label ED:247 (`templates[].name`) vs the rendered PDF layout (the list does not show template).
- [!] Rail badge `Cover Letters · N` (`V2App.jsx:63`) does not decrement after Delete (ED:185) until a full reload. — **CL-17**

---

## Summary

- Interactive elements catalogued: **63** (list 10 incl. Picker sub-controls and the inert pending row; editor 53 incl. per-row contact/paragraph controls, popover options, modal controls and the Escape handler).
- Distinct API endpoints used: **14** (`GET /cover-letters`, `GET /cover-letters/{id}`, `GET /cover-letters/templates`, `PATCH /cover-letters/{id}`, `DELETE /cover-letters/{id}`, `GET /cover-letters/{id}/pdf`, `POST /cover-letters/generate`, `GET /resumes`, `GET /resumes/{id}`, `GET /persona`, `GET /jobs`, `GET /jobs/{id}`, `GET /settings`, `GET /monitor/active`); `GET /cover-letters/{id}/tracer-stats` exists but is never called.
- Failure paths with no user-visible feedback: **17** (0 promises are literally uncaught — every call has a catch — but 17 are swallowed or console-only: list 9 incl. background-generation failure; editor 8 incl. PDF failure, background-regeneration failure and the stuck-regenerating reload path).
- Missing empty/error branches: **8** (list loading, list load error, no-voice-presets, background generation failure; editor PDF failure, background regeneration failure, empty template popover, 404-vs-500 distinction / no back link).
- Suspicious items: **41** (list 17, editor 24) — highest-value: ED:126-133 debounce drops patches, ED:212-213 stuck `regening`, ED:210 scope-agnostic poll, CL:183 silent failed runs, CL:347-vs-216 count disagreement.
