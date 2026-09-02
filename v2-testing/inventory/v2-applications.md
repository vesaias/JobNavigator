# v2 Applications — screen inventory

Screen file: `frontend/src/v2/Applications.jsx` (641 lines, read in full). Shell: `frontend/src/v2/V2App.jsx`. Axios: `frontend/src/api.js`. Backend: `backend/api/routes_applications.py`.
All `file:line` references below are to `Applications.jsx` unless prefixed. Catalogue only — nothing was run or modified.

Components in the file: `Applications` (main, :69-344), `Detail` (:347-509), `PrepModal` (:512-536), `LogModal` (:539-641).
Toast: **`Toast.jsx` is NOT imported by this screen** — no `useToasts`/`push` anywhere. Every "toast" column below is therefore "none". Failures surface only as `console.error`, a `window.alert`, or in-modal text.

---

## 1. Routes & params

- [ ] Route `/v2/applications` — registered `frontend/src/App.jsx:160` (`<Route path="applications" element={<V2Applications />} />`) nested under `/v2` shell `frontend/src/App.jsx:151`. Rail entry `V2App.jsx:24` (`countKey: 'apps'`).
- [ ] Query params handled: **none**. No `useSearchParams`/`useLocation` in the file (only `useNavigate` :2, :70). `?app=`, `?job=`, `?id=` deep-links are NOT supported; `CoverLetterEditor.jsx:288` navigates to bare `/v2/applications`, so no context is carried in.
- [ ] Deep-links OUT (see §3): `/v2/resumes/{tailored_resume_id}` :370, `/v2/feed?job={job_id}` :384, `/v2/cover-letters?job={job_id}` :385, `/api/jobs/{job_id}/cached-page` :376 (raw `<a>`), `d.url` :378.
- [ ] localStorage read/written by this file: **none**. Inherited: `jobnavigator_v2_rail` read `V2App.jsx:48` / written `:55`; `jobnavigator_dark_mode` read `V2App.jsx:52` / written `:54`; `jobnavigator_api_key` read `api.js:11` (request interceptor).
- [ ] sessionStorage / URL hash: none.
- [ ] Browser tab title: not set in this file (handled by `TitleSync` in `App.jsx:149`).

## 2. Data loads

- [ ] `GET /api/applications?limit=2000` — `load()` :92-100, fired on mount by effect :101. Response shape `{total, applications[]}` (routes_applications.py:352-356); the screen uses only `data.applications` :95 and ignores `total`. Sets `apps`, then `sel` to `keep ?? current ?? first row` :97. Failure: `catch → console.error` :98 only; `setLoaded(true)` :99 still runs, so a failed load renders as the **empty state**, not an error.
- [ ] Re-fetch triggers (`load(id)` after each mutation): stage patch :157 (success AND failure), delete :172, add interview :181, delete interview :185, toggle interview :188, log-modal save :341. Notes autosave does **not** re-fetch :164.
- [ ] `GET /api/resumes?is_base=true` — `LogModal` mount effect :551; result → résumé chips :606. Failure `.catch(() => {})` swallowed (chips row silently empty).
- [ ] `POST /api/applications/extract {url}` — on URL input blur :589 → `readUrl` :554-563, only if value starts with `http` :555.
- [ ] `GET /api/applications/{id}/prep` — on "Generate prep handover" click :431 → `openPrep` :190-195.
- [ ] Polling intervals: **none**. No `setInterval`, no focus/visibility refetch. The only timers are the notes debounce (700 ms, :166) and the "Copied ✓" reset (1800 ms, :198), both cleared on unmount :90.
- [ ] Shell counts (`V2App.jsx:58-71`) are fetched once when the shell mounts and are **not** refreshed by anything this screen does.

## 3. Interactive elements

Format per item: label/icon — JSX file:line — handler — API — state mutated — success toast / failure handling.

### 3a. Global keyboard & document handlers
- [ ] `Escape` — document `keydown` :106 — closes company/sort popovers + ⋯ menu (`closeAll` :103), closes Prep modal (`setPrep(null)`), closes Log modal (`setLogOpen(false)`). **Escape inside the Log modal discards all typed fields with no confirm.** No API. No toast.
- [ ] Document `click` :105 — `closeAll()` closes popovers/menu on any outside click. The company-filter wrapper :237, sort wrapper :262 and detail action cluster :375 call `e.stopPropagation()` so clicks inside them do not close.
- [ ] Other keyboard shortcuts (j/k, s, x, Enter, /): **none exist** on this screen (contrast with JobFeed).

### 3b. Header
- [ ] Heading "Applications" :221 + count line :222 (`countLine` :115-116 — `"{n} application(s) · {i} in interview · {o} offer[ · {s} waiting >7d]"`). Display only. Note "offer" is never pluralised (:115).
- [ ] **"+ Log application"** pill (green) :225 — inline `onClick` → `closeAll(); setLogOpen(true)` — no API — opens `LogModal` :341. No hover class.

### 3c. Toolbar
- [ ] Search input (placeholder "Search title or company…", ⌕ glyph :232) :233 — `onChange → setQuery` — no API, client-side filter :137-142 over `title + companyOf(a)` (case-insensitive substring), no debounce. Cleared only by deleting text (no ✕ button).
- [ ] **Company** filter pill "Company[ · N] ▾" :238-241 — `setOpenFlt('company' | null)` — no API — accent-tinted when open or when `companies.length > 0` :239.
- [ ] Company popover :243-256 (`width 240, maxHeight 340, overflow auto`, `.v2-scroll`) — items :248 `onClick → setCompanies(toggle name)` — **multi-select checkboxes** (✓ box :250). Two bands: `live` (≥1 non-rejected app) then `closed` (all rejected, muted colour, `title="Every application here is rejected"` :251) separated by a rule :246,:249. Per-company count :252 (`e.n`, see §8). Popover stays open on item click (wrapper stopPropagation :237). **No "clear all" / "select all" control.**
- [ ] "N of M shown" :261 — display only, rendered only when `visible.length !== apps.length`.
- [ ] **Sort** trigger "Sort {label} ▾" :263-265 — `setOpenFlt('sort' | null)` — no API.
- [ ] Sort popover :267-277 — options from `SORTS` :43: `Recent activity` (`recent`), `Waiting longest` (`oldest`), `Company name` (`company`) — item :271 `onClick → setSortBy(id); setOpenFlt(null)`. Comparators :144-148 (recent/oldest compare `daysSince(updated_at)` — **day granularity**, ties broken by title; company → locale name then title). Default `recent` :78. Sort choice is **not persisted** (no localStorage).

### 3d. List pane (left, 472 px, `.v2-scroll` :286)
- [ ] Stage group header (dot + APPLIED/INTERVIEW/OFFER/REJECTED + count + chevron) :292-298 — `onClick → setClosed(toggle st.id)` — no API — collapses/expands the group. Default: `rejected` collapsed :80. Count :296 = `visible.filter(status).length` (filtered, see §8). Chevron `›` closed / `⌄` open :297.
- [ ] Application row :303-316 (`className="v2-arow"`, 46 px) — `onClick → closeAll(); setSel(a.id)` — no API — selected row gets `--surface-2` :304. Contents: title (ellipsis, `title` tooltip, muted when unknown or rejected) :309; ✉ glyph :310 (accent when `last_email_received || last_email_snippet`, else `color: transparent` — still occupies space); company (ellipsis, `--edge` colour when `Unknown Company`) :312; `{N}d` since `updated_at` :314-315 (amber `--warn` when `isStale` :44 = >7 d and status applied/interview; tooltip "No movement for N days" / "Last activity Nd ago").
- [ ] Bulk selection / checkboxes / bulk actions: **none** on this screen.
- [ ] Row context menu / row-level actions: **none** (all actions are in the detail pane).

### 3e. Detail pane header (`Detail` :347-415)
- [ ] `#short_id · Company` eyebrow :361-363 — display. Uses `d.company_canonical || d.company` (no "Unknown Company" fallback, unlike the list :118).
- [ ] Title :364-368 + ✉ :367 (same condition as row). Display.
- [ ] Meta line :369-373 "`{salary} · {location}` · applied with **{cv}[ ↗]**" — the cv span :370 `onClick → d.tailored_resume_id && navigate('/v2/resumes/' + id)` — no API — **no-op when there is no tailored résumé** (cursor default, tooltip "No tailored résumé for this job" :371; still rendered in accent colour). `cv` = `tailored_resume_name || cv_version_used || best_cv || 'unknown résumé'` :352.
- [ ] **"Cached"** :376-377 — plain `<a href="/api/jobs/{job_id}/cached-page" target="_blank" rel="noopener noreferrer">` (`.v2-bdc`, tooltip "Snapshot of the posting from application day") — rendered only when `d.has_cached_page`. **Bypasses axios**: no `X-API-Key` header is sent; relies solely on the `jn_session` cookie (`backend/main.py:137`). Backend `routes_jobs.py:655-664` returns reader HTML, 404 if no cache. No in-app viewer/iframe modal.
- [ ] **"Live ↗"** :378-379 — `<a href={d.url} target="_blank">` (`.v2-bdc`, tooltip "Open the live posting") — rendered only when `d.url`.
- [ ] **"⋯" More actions** :380-381 (`.v2-bd`, tooltip "More actions") — `setMenuOpen(v => !v)` — accent border/fill while open.
- [ ] Menu item **"☰ View job in feed"** :384,:386 — `setMenuOpen(false); navigate('/v2/feed?job=' + d.job_id)` — no API.
- [ ] Menu item **"✎ Open cover letter"** :385,:386 — `navigate('/v2/cover-letters?job=' + d.job_id)` — rendered only when `d.has_cover_letter`. There is **no "Generate cover letter"** path from here when none exists.
- [ ] Menu item **"✕ Delete application"** (red, `.v2-hover-bad`) :391-393 — `onDelete` → `remove(d)` :169-173: `setMenuOpen(false)`; `window.confirm('Delete the application for "{title}"?')` :171; `DELETE /api/applications/{id}` :172; on success `setSel(null); load(null)` (→ selects first remaining row :97). Backend also flips the linked job `applied → saved` (routes_applications.py:391-393). Success toast: none. Failure: `catch → console.error` :172, no user feedback, selection unchanged.
- [ ] Menu items "Open résumé", "Edit fields", "Duplicate", "Archive": **do not exist**.

### 3f. Stage stepper :400-414
- [ ] Four pills from `STAGES` :35-40 — each :405 `onClick → onStage(s.id)` → `patch(d.id, {status})` :155-158 (`.v2-bd`, tooltip = `s.hint`). Optimistic local merge :156, then `PATCH /api/applications/{id} {status}` :157, then `load(id)` on success **and** on failure (failure re-fetch reverts the optimistic value). Success toast: none. Failure: `console.error` :157 only.
  - [ ] **Applied** (`--stage-applied`, hint "Waiting on a first response") → `{status:'applied'}`; backend records transition `{from: <old>, to:'applied', source:'ui'}` (routes_applications.py:370-373 → db.py:239-252) when different.
  - [ ] **Interview** (`--warn`, "In the interview loop") → `{status:'interview'}` → transition `→interview`, source `ui`.
  - [ ] **Offer** (`--good`, "Offer received") → `{status:'offer'}` → transition `→offer`, source `ui`.
  - [ ] **Rejected** (`--bad` border/`--bad-soft` fill when active, "Closed — kept for the Stats funnel") → `{status:'rejected'}` → transition `→rejected`, source `ui`.
  - [ ] Clicking the **already-active** pill still sends the PATCH; backend skips the transition (db.py:242) but **bumps `updated_at`** (routes_applications.py:377) → the row's `{N}d` counter resets to 0 and any stale flag clears.
  - [ ] Statuses offered by backend `VALID_STATUSES` = exactly these four (routes_applications.py:15). `ghosted`/`withdrawn` (referenced in `Stats.jsx:168,:215`) cannot be set here and, if present on legacy rows, would render in **no group** while still counting in the header total.
  - [ ] No confirm on any transition; no undo toast.

### 3g. Detail body — email, interviews, notes (:418-487)
- [ ] "Last email · Gmail detection" block :421-426 — display only; rendered when `last_email_received || last_email_snippet`. No link to Gmail / thread.
- [ ] "Interviews · N" label :430 (`ivs.length`).
- [ ] **"⧉ Generate prep handover for AI"** :431-435 (`.v2-bdc`, long tooltip :432) — `openPrep` :190-195: `closeAll(); setPrep('loading'); setCopied(false)`; `GET /api/applications/{id}/prep` → `setPrep({text})`. Opens `PrepModal` :340. Failure: caught → modal body shows `"Could not build the prep bundle: {e.message}"` :194 (axios message e.g. "Request failed with status code 500"; no `detail`). No toast.
- [ ] Interview card :438-448 — `iv.what` (ellipsis) :440; `[fmtWhen(when_at) · where_text] || 'Unscheduled'` :445; optional `iv.prep` :447.
  - [ ] Status chip (text = `iv.status`, tooltip "Toggle scheduled / done") :441 — `toggleInterview(iv)` :187-189 → `PATCH /api/applications/interviews/{iv.id} {status: done↔scheduled}`; `load(d.id)`. Not optimistic. Success toast: none. Failure: `console.error` :188 only.
  - [ ] **✕ Remove** (`.v2-hover-bad`, tooltip "Remove this interview") :442 — `delInterview(iv)` :184-186 → `DELETE /api/applications/interviews/{iv.id}`; `load(d.id)`. **No confirm dialog.** Success toast: none. Failure: `console.error` :185 only.
  - [ ] **Edit interview (what/when/where/prep)**: **does not exist** — backend `PATCH /interviews/{id}` accepts `what/where_text/status/prep/when_at` (routes_applications.py:478-490) but the UI only toggles `status`.
- [ ] **"+ Add interview"** dashed button :476 (`.v2-bdc`) — `setIntForm(true)` — no API. Replaced by the form while open (:450).
- [ ] Interview form :451-474 (accent border):
  - [ ] **What** text input :454 (placeholder "e.g. System design round") — `setIntWhat`. Defaults to `'Interview'` on save if blank :178.
  - [ ] **When** `type="datetime-local"` :459 — `setIntWhen`. Sent verbatim (zone-less local string) :178; backend `_parse_dt` stamps it **UTC** (routes_applications.py:26) and `fmtWhen` :17-22 renders it in local time → **shifted by the viewer's UTC offset**.
  - [ ] **Where** text input :463 (placeholder "Zoom · Onsite — London") — `setIntWhere`.
  - [ ] **Prep note · optional** text input :468 (single-line `<input>`, placeholder "Who I'm meeting, what to revise…") — `setIntPrep`.
  - [ ] **Cancel** :471 (`.v2-bdc`) — resets all four fields, closes form. No API.
  - [ ] **Add interview** (green) :472 — `addInterview` :174-183 → `POST /api/applications/{d.id}/interviews {what, when_at, where_text, status:'scheduled', prep}` (201); resets form; `load(d.id)`. **No client validation** — an entirely blank form creates an "Interview / Unscheduled" card. Not disabled while in flight (double-click → two POSTs). Success toast: none. Failure: `console.error` :182, form stays open with values.
  - [ ] Form draft state lives in the parent :82-84 and is **not** keyed by application — an open half-filled form persists when you click a different row.
- [ ] **Notes · autosaves** textarea :483-485 (`key={d.id}`, `defaultValue={d.notes}`, placeholder "Notes…", vertical resize) — `onChange → onNotes(v)` → `saveNotes(id, v)` :160-167 debounced 700 ms; `onBlur → onNotes(v, true)` flushes immediately. Each run: local state merge :163 then `PATCH /api/applications/{id} {notes}` :164 (fire-and-forget, `.catch(console.error)`). No `load()` afterwards. No "Saved" indicator (the label says "autosaves"; nothing changes on success). Failure: console only; local state keeps the unsaved text. Backend bumps `updated_at` on every notes patch (routes_applications.py:377) → **typing a note resets the `{N}d` counter / stale flag**.
- [ ] Editable fields that exist on the model but have **no UI here**: `next_action`, `next_action_date`, `cv_version_used`, `applied_at` (all in backend `allowed` set routes_applications.py:365), plus title/company/url.

### 3h. History rail :490-505
- [ ] Read-only timeline; entries built in `history` memo :202-212 from `status_transitions[]` ("Moved to {Stage}"), `last_email_received` ("Reply detected in Gmail"), `applied_at` ("Applied with {cv}"), `discovered_at` ("Discovered via {srcLabel(source)}" :29-33). Sorted newest first :211; relative time via `ago()` :8-15. No links, no hover.

### 3i. Prep modal (`PrepModal` :512-536)
- [ ] Scrim :514 — `onClick → onClose` (`setPrep(null)` :340). Content `stopPropagation` :515.
- [ ] Title "Prep handover — {company}" :517 + hint "paste into the AI of your choice" :518.
- [ ] **✕** :519 (`.v2-hover-accent`) — `onClose`.
- [ ] Body `<pre>` :522-524 — `'Building the bundle…'` while `prep === 'loading'`, else `prep.text` (`.v2-scroll`, `pre-wrap`, `break-word`).
- [ ] Footer text "Edit the closing ask in Settings → AI" :527 — **plain text, not a link** (the setting lives under Settings.jsx:258 "Interview prep").
- [ ] **Close** :528 — `onClose`. No hover class.
- [ ] **⧉ Copy to clipboard / Copied ✓** :529-531 — `copyPrep` :196-199: `navigator.clipboard.writeText(prep?.text || '')` with the rejection **swallowed** :197, then `setCopied(true)` regardless → shows "Copied ✓" (green fill) for 1.8 s **even when the clipboard write failed** or while text is still `'loading'` (button is clickable during loading; copies empty string). No toast.

### 3j. Log-application modal (`LogModal` :539-641)
- [ ] Scrim :580 — `onClose` (`setLogOpen(false)` :341). Content `stopPropagation` :581.
- [ ] Copy: "Log application" / "For applications made outside the app — jobs from the feed log themselves when you mark them applied." :583-584; footer note "The posting is cached on save" :634.
- [ ] **Posting URL** input (mono, placeholder "Paste the job URL — title and company are read from it") :589-591 — `onChange → setUrl`; `onBlur → readUrl(value)` :554-563 → `POST /api/applications/extract {url}` (only when value starts with `http`) → fills **Title** and **Company** only if those fields are still empty :559-560. Label suffix "· reading…" while in flight :588. Failure: `console.error` :561, fields left as-is, no message. Backend returns 400 "Unsafe URL" for non-public hosts (routes_applications.py:411-414).
- [ ] **Title** input (placeholder "Senior Backend Engineer") :596 — `setTitle`.
- [ ] **Company** input (placeholder "Acme") :600 — `setCompany`.
- [ ] **Applied with** résumé chips :606-609 (`.v2-bd`, one per base résumé from `GET /resumes?is_base=true`) — `setCv(on ? '' : r.name)` — single-select toggle; sends `cv_version_used: name | null` :571. Empty list renders nothing (no "no résumés" copy).
- [ ] **Stage** chips :616-619 (`.v2-bd`): `Applied` / `Interview` / `Offer` — `setStage(id)`; default `applied` :545. **Rejected is not offered** here.
- [ ] **Applied on** `type="date"` :624 — default today (`toISOString().slice(0,10)` :546 — UTC date, may be yesterday/tomorrow vs local); sent as `new Date(when).toISOString()` :572 (UTC midnight).
- [ ] **Notes** textarea (placeholder "Optional — referral, recruiter contact…") :629 — `setNotes`.
- [ ] **Cancel** :635 — `onClose`. No hover class.
- [ ] **Save application / Saving…** :636 — `save` :565-576: client check `title && company && url` else `window.alert('URL, title and company are all required')` :566 (URL is mandatory even for off-app applications); `setBusy(true)`; `POST /api/applications {url,title,company,cv_version_used,notes,status,applied_at}` :569-573 → backend find-or-create Job by `external_id` (routes_applications.py:232-249), **upsert** Application (:262-292 — an existing application for the same job is overwritten, with a transition recorded), auto-creates Company + H-1B lookup (:296-311), caches page in background (:314-315); `onSaved(data.id)` :574 → `setLogOpen(false); load(id)` :341. While busy: `onClick` is `undefined` :636, opacity .6, label "Saving…". Success toast: none. Failure: `window.alert(e.response?.data?.detail || 'Could not save this application')` :575; busy reset.
- [ ] Because page caching is a background task, the **"Cached" button will not appear** for the new row until a later re-fetch (the immediate `load(id)` runs before caching completes).

## 4. States rendered

### Whole screen
- [ ] Not yet loaded (`!loaded`) :214 → an **empty `--bg` div, no spinner, no copy**. Exists.
- [ ] Load error → **no branch**. `catch` :98 only logs; `setLoaded(true)` :99 → screen shows the empty-state copy below. No retry, no message. **Missing.**
- [ ] Any `api` 401 → global `jn:unauthorized` event (`api.js:22-23`) handled by the shell, not here.

### List pane
- [ ] Zero applications (`visible.length === 0 && apps.length === 0`) :322-324 → `"No applications yet — mark a job applied in the Feed, or log one here."` (34 px padding, centred, muted). The four group headers with `0` are still rendered above it :287-298.
- [ ] Zero results with filter/search active (`visible.length === 0 && apps.length > 0`) :324 → `"Nothing matches those filters."` No "clear filters" control.
- [ ] Empty stage group → header with `0` only; **no per-group empty copy** (:299 renders nothing). Missing by design.
- [ ] Group collapsed → rows hidden :299; count still shown.
- [ ] Company popover with zero companies → **empty 240 px box** (no copy) :243. Missing.
- [ ] Long strings: row title ellipsis + tooltip :309; row company ellipsis + tooltip :312; header count line ellipsis :222; popover company name ellipsis :251; interview `what` ellipsis :440. Row height fixed 46 px :304 so overflow cannot grow the row.

### Detail pane
- [ ] No selection (`d === null`) :337 → `"Select an application."` centred. Reached after deleting the last row, or when `apps` is empty.
- [ ] Selected app hidden by the current filter → **detail still shows it** (`d` :152 is looked up in `apps`, not `visible`). No branch. Note for verification.
- [ ] Title fallback `'Unknown Role'` :365; meta fallback `'No posting details captured'` :351; cv fallback `'unknown résumé'` :352; eyebrow company has **no fallback** (may render `#id · ` with empty company) :362.
- [ ] Email block absent when no email :421; snippet fallback `"A reply was detected, but no snippet was stored."` :424. Snippet is not clamped/ellipsised (wraps).
- [ ] Interviews empty → only the label "Interviews · 0" and the "+ Add interview" button; **no "no interviews yet" copy**. Missing by design.
- [ ] Interview unscheduled → `'Unscheduled'` :445; `fmtWhen` returns `''` for invalid dates :20.
- [ ] Notes empty → placeholder "Notes…" :484. No saving / saved / failed indicator. Missing.
- [ ] History empty :504 → `"No history recorded yet."`
- [ ] Long strings in detail: title wraps (`textWrap: 'pretty'`, no clamp) :364; eyebrow company no ellipsis :362; history `what` wraps inside the 250 px rail (a long tailored-résumé name in "Applied with …" :209 will wrap over several lines) :499; interview `prep` wraps :447; email snippet wraps :424.
- [ ] Stage pills are `flex:1` :406 — four labels always fit; no overflow branch.

### Prep modal
- [ ] Loading :523 → `'Building the bundle…'`.
- [ ] Error :194 → `"Could not build the prep bundle: {e.message}"` rendered as the bundle text (same styling as success; Copy still enabled and would copy the error).
- [ ] Empty `data.text` → blank body; no branch.

### Log modal
- [ ] Reading URL :588 → label "Posting URL · reading…". No error branch for extract failure (silent).
- [ ] Résumé list loading/empty/error → nothing rendered; no copy. Missing.
- [ ] Validation :566 → `window.alert`. Saving :636 → "Saving…". Save error :575 → `window.alert(detail)`.

## 5. Hover styles

All hover is via class names defined in `frontend/src/v2/theme.css`; **no `onMouseEnter`/`onMouseLeave`, no `:hover` inline** in this file.
- [ ] `.v2-arow:hover { background: var(--surface-2) !important }` (theme.css:150) — list rows :303.
- [ ] `.v2-menuitem:hover { background: var(--surface-2) }` (theme.css:148) — company popover items :248, sort options :271, ⋯ menu items :386.
- [ ] `.v2-bd:hover { border-color: var(--accent) !important }` (theme.css:152) — ⋯ button :380, stage stepper pills :405 (incl. Rejected → accent border on hover even though its active colour is `--bad`), Log-modal résumé chips :608, Log-modal stage chips :618.
- [ ] `.v2-bdc:hover { border-color + color: var(--accent) !important }` (theme.css:155) — Cached :376, Live :378, Generate prep :431, interview-form Cancel :471, "+ Add interview" :476.
- [ ] `.v2-hover-bad:hover { background: var(--bad-soft) !important }` (theme.css:130) — Delete application :391, interview ✕ :442.
- [ ] `.v2-hover-accent:hover { background: var(--surface-2); color: var(--text) }` (theme.css:129) — Prep modal ✕ :519.
- [ ] `.v2-scroll` (theme.css:221-223) — scrollbar skin only, not hover: :243, :286, :418, :521, :586.
- [ ] Controls with **no hover affordance at all** (cursor pointer only): "+ Log application" :225, Company filter pill :238, Sort trigger :263, stage group headers :292, résumé link span :370, interview status chip :441, "Add interview" submit :472, Prep modal Close :528 / Copy :529, Log modal Cancel :635 / Save :636.
- [ ] Selected-row highlight `--surface-2` :304 is the **same colour as the row hover** (theme.css:150) — hovering a non-selected row makes it indistinguishable from the selected one.

## 6. Theme

- [ ] Dark mode is read in the shell: `V2App.jsx:52` `localStorage.getItem('jobnavigator_dark_mode') === 'true'` → `data-theme="dark"|"light"` on `.jn-v2` `V2App.jsx:90`; tokens swap in `theme.css:74` (`.jn-v2[data-theme="dark"]`). This file only imports `./theme.css` :4 and never reads the theme.
- [ ] Colour literals (hex / rgb / hsl) in `Applications.jsx`: **none** (grep confirmed). Only `'transparent'` :234, :272, :304, :310 and `var(--*)` tokens.
- [ ] Every token referenced exists in both light and dark blocks of theme.css: `accent, accent-ink, accent-soft, bad, bad-soft, bg, edge, good, line, line-soft, line-strong, muted, scrim, stage-applied, surface, surface-2, text, text-2, warn` (2 definitions each); `mono, sans, serif, shadow-menu, shadow-modal` (defined once, theme-independent). Verified 2026-09-02.
- [ ] Theme-sensitive spots to eyeball: interview chip `scheduled` uses `--good` text on `--accent-soft` :441; Rejected pill active `--bad` on `--bad-soft` :407-409; stale `--warn` :315; `Unknown Company` in `--edge` :312 (edge is a border tone, low contrast on both themes); modal scrim `--scrim` :514, :580; email quote `--bg` inside `--surface` :424.

## 7. Suspicious

- [ ] `closeAll` is passed to `Detail` :330 and destructured :347 but **never used inside `Detail`** (unused prop).
- [ ] `GROUP_LABEL` :42 duplicates `STAGES[].label` :35-40 (dead duplication; used only at :295).
- [ ] `Toast.jsx` not imported — no success feedback for any of the 9 mutations; **8 `console.error`-only failure paths**: :98 (load), :157 (stage patch), :164 (notes), :172 (delete), :182 (add interview), :185 (delete interview), :188 (toggle interview), :561 (extract). `console.log`/`TODO`/`FIXME`: none.
- [ ] `copyPrep` :196-199 shows "Copied ✓" even when `navigator.clipboard.writeText` rejects (error swallowed :197); also clickable while `prep === 'loading'` (copies `''`).
- [ ] Interview `when_at` timezone drift: form sends zone-less local `datetime-local` :178 → backend treats as UTC (routes_applications.py:26) → `fmtWhen` :21 shows local → off by the UTC offset.
- [ ] Stage pill click on the already-active stage still PATCHes :405/:157 → backend bumps `updated_at` (routes_applications.py:377) → resets the `{N}d` / stale indicator without any transition.
- [ ] Notes autosave and interview add/toggle also bump `updated_at` → "Recent activity" sort and "waiting >7d" both treat a note edit as pipeline movement (:44, :145).
- [ ] Notes debounce timer is cleared on unmount :90 → the last ≤700 ms of typing is **lost** if the user navigates away (rail click) without blurring the textarea. Also :161 clears the previous app's pending timer when typing starts in another app's notes within 700 ms.
- [ ] `useMemo` for `visible` :136-150 and `companyOpts` :120-134 close over `companyOf` (defined :118, recreated every render) without listing it in deps — works because it's pure, but violates exhaustive-deps.
- [ ] `sortBy: 'recent'` uses `daysSince` (integer days) :145 — everything updated today ties and falls back to **alphabetical by title**, so "Recent activity" is not actually most-recent-first within a day.
- [ ] `<a href="/api/jobs/{id}/cached-page">` :376 bypasses the axios interceptor → no `X-API-Key`; only works when the `jn_session` cookie is set (main.py:137). In localStorage-key-only setups it 401s in the new tab.
- [ ] `d` :152 is resolved from `apps`, not `visible` → a filtered-out application stays open in the detail pane with no indication.
- [ ] Detail eyebrow :362 has no `Unknown Company` fallback (list uses `companyOf` :118) — inconsistent.
- [ ] `countLine` :115 never pluralises "offer" ("2 offer").
- [ ] Interview form state (:82-84) is global to the screen, not per application → an open form with typed values persists across row changes and could be submitted against a different application.
- [ ] `addInterview` :174 has no in-flight guard (double submit) and no validation; `delInterview` :184 has no confirm.
- [ ] `LogModal` default date :546 uses `toISOString().slice(0,10)` → **UTC** calendar date; near midnight the default "Applied on" is off by a day for non-UTC users. Save converts date-only → UTC midnight :572.
- [ ] `LogModal` requires a URL :566 although the copy says it is for applications made outside the app; no "no URL" path.
- [ ] Backend `POST /applications` **upserts** by job (routes_applications.py:262-272): logging the same URL+title+company twice silently overwrites the earlier application's status/notes and records a transition — no client warning.
- [ ] Escape :106 closes the Log modal and discards the form without confirmation.
- [ ] Rail badge (`V2App.jsx:60`) is never refreshed after log/delete on this screen → stale count until the shell remounts.
- [ ] `limit: 2000` :94 — hard cap; `data.total` is ignored, so >2000 applications would silently truncate the list and the header count.
- [ ] `srcLabel` :29-33 maps `direct` → "a company scrape", but `POST /applications` creates jobs with `source="direct"` (routes_applications.py:242) → a hand-logged application's history reads "Discovered via a company scrape".
- [ ] Legacy statuses (`ghosted`, `withdrawn` — `Stats.jsx:168`) have no group in `STAGES` :35-40 → such rows are invisible in the list but counted in `apps.length`.

## 8. Counts that must agree

- [ ] **Header total** `apps.length` :115 (`GET /api/applications?limit=2000` → `applications[].length`) ⇔ **rail badge "Applications"** `V2App.jsx:60` (`GET /api/applications` default limit 200 → uses `data.total` — full count) ⇔ **Stats KPI "Applications"** `Stats.jsx:267` (`GET /api/stats` → `total_applications` = `Application.count()`, `main.py:1345`). All three count `Application` rows; rail is fetched once per shell mount (stale after mutations here); header caps at 2000.
- [ ] **"N in interview" / "N offer"** :112-113 (client filter on `status`) ⇔ Stats `application_statuses.interview/offer` (`main.py:1347-1349`, `Stats.jsx:167`) ⇔ Stats funnel rows `reached.interview || st.interview` (`Stats.jsx:203-204` — `reached` counts Sankey transitions *into* a stage, so it can exceed the current-status count once rows move on).
- [ ] **Stage group counts** :296 = `visible.filter(status).length` — they reflect the **current search/company filter**, not totals; sum of the four = `visible.length` (:261 "N of M shown") only if every row has one of the four statuses.
- [ ] **Company popover counts** `e.n` :252 = Application rows grouped by `company_canonical || company` (alias-canonicalised, routes_applications.py:620-621) ⇔ **Companies screen "Apps" column** `Companies.jsx:366` / editor subtitle `:427` = `application_count` from `routes_companies.py:95-110`: UNION of `Application.job_id` **and** `Job.status='applied'` job ids, grouped by raw `Job.company` lower-cased with spaces stripped. Differences to expect: jobs marked applied without an Application row (count only on Companies), alias grouping (popover merges aliases; Companies keys on raw name), whitespace/case variants.
- [ ] **"Interviews · N"** :430 = `d.interviews.length` ⇔ number of interview cards rendered :437 (same array) ⇔ nothing elsewhere (Stats has no interview-card count).
- [ ] **"N waiting >7d"** :114/:116 (`isStale` :44 on `updated_at`) ⇔ amber `{N}d` cells :315 in the Applied/Interview groups — same predicate; appears nowhere else.
- [ ] **History "Moved to …" rows** :204-207 ⇔ Stats Sankey edges (`GET /api/stats/sankey`, `main.py:1243`) — both read `status_transitions[]`; a stage click here must add exactly one edge there (none when clicking the active stage).
- [ ] **"Applied" job status on the Feed** ⇔ this list: deleting here flips the job to `saved` (routes_applications.py:391-393); logging here sets the job to `applied` (:249) — the Feed's status chip and the Companies "Apps" column must follow.
