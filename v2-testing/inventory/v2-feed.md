# v2 Jobs Feed — inventory

Screen: **The Feed** — `frontend/src/v2/JobFeed.jsx` (1187 lines, read in full). Route `/v2/feed`.
Shell: `frontend/src/v2/V2App.jsx`. Toasts: `frontend/src/v2/Toast.jsx`. HTTP: `frontend/src/api.js`.
Below, bare `L123` means `frontend/src/v2/JobFeed.jsx:123`. Other files are named explicitly.
This is a catalogue for a later verification pass — nothing here has been run or fixed.

---

## 1. Routes & params

- [x] Route `/v2/feed` → `<V2JobFeed />`, nested under `/v2` shell (`frontend/src/App.jsx:153-155`); `/v2` index redirects to `feed` (`App.jsx:154`).
- [!] `?job=<id>` — job permalink. Read at L476 (`searchParams.get('job')`); fetched via `GET /jobs/{id}` at L479; pinned in `pinnedRef` (L478) so the panel stays open even when the job is not in the list (L274-277). Fetch failure clears the pin silently (L483, no toast). Kept in sync with whatever detail is open via `setSearchParams(…, { replace: true })` at L488-497 (adds/removes `job`, preserves other params).  _→ FEED-09_
- [x] `?search=<id>` — scope feed to one saved search. Read ONCE at mount from `window.location.search` (L179), NOT from `searchParams` — later in-app changes to `?search=` while mounted are not observed. Name resolved via `GET /searches` (L183) and shown in the "from “{name}”" pill (L611-616); clearing the pill does `setSearchParams({}, { replace: true })` (L612), which also momentarily removes `?job=` (re-added by L488-497).
- [~] `?company=<name>` — **NOT handled** by this screen, but `frontend/src/v2/Companies.jsx:393` links to `/v2/feed?company=…` ("View jobs in feed"). The param is silently ignored.  _(untestable in this harness — see feed.md “Couldn't test”)_
- [x] Inbound deep links from other v2 screens: `Applications.jsx:384` (`?job=`), `CoverLetterEditor.jsx:294` (`?job=`), `ResumeEditor.jsx:385` (`?job=`), `Searches.jsx:506` (`?search=`), `Companies.jsx:393` (`?company=`, unhandled).
- [x] Outbound navigations: `/v2/resumes/{id}` (L368 after copy, L381 openTailored, L382 fallback, L556 toast action), `/v2/cover-letters?job={id}` (L846), classic `/resumes?resume={id}` (L766 — row ✦ link, NOT a v2 route), `window.open(job.url)` (L439, L795), `<a target=_blank>` (L834, L1050).
- [x] localStorage `v2_feed_filters` — key L6; read L111 (merged over `DEFAULTS` L53); written on every filter change L115.
- [x] localStorage `v2_feed_sort` — key L7; read L114 (default `'score'`); written L116.
- [x] localStorage `v2_feed_ui` — key L8; read via `loadUI()` L9 into `headOpen` L124, `reportOpen` L125, `reqFilter` L127, `showMatched` L128, `breakdownOpen` L129, `keywordOpen` L130, `reqOpen` L131; written L132 (all seven keys as one JSON object).
- [x] localStorage `jobnavigator_api_key` — read by the axios request interceptor `frontend/src/api.js:11` → `X-API-Key` header on every call from this screen.
- [x] localStorage `jobnavigator_dark_mode` — read `V2App.jsx:52`, written `V2App.jsx:54` (not touched by JobFeed).
- [x] localStorage `jobnavigator_v2_rail` — read `V2App.jsx:48`, written `V2App.jsx:55` (not touched by JobFeed).
- [~] DOM attribute `data-jn-ext` on `<html>` — read L140 and polled every 200 ms up to 11 ticks (L141-149) to detect the Navigator extension; set by `extension/content_autofill.js:14`.  _(untestable in this harness — see feed.md “Couldn't test”)_
- [x] Global 401 → `window` event `jn:unauthorized` (`api.js:18-21`) — any call from this screen can trigger the shell's login modal.

## 2. Data loads

### On mount (once)
- [x] `GET /jobs/companies/list?counts=1` — L197 → `companyList` `[{name,count}]`. `.catch(() => {})` (silent). Note: called with NO current filters, so counts are all-status totals per company (`backend/api/routes_jobs.py:251-283`).
- [x] `GET /jobs/sources/list` — L198 → `sourceList`. Silent catch.
- [x] `GET /jobs/verdicts/list` — L199 → `verdictList`. Silent catch.
- [x] `GET /resumes?is_base=true` — L200 → `resumes` (base list for the picker modal). Silent catch.
- [x] `GET /jobs/feed-stats` — L201 → `stats {arrived_today, unscored}`. Silent catch. Re-fetched by `refreshStats()` L203 after every PATCH (L300), undo (L306), and in-flight completion (L562).
- [x] `GET /persona` — L471 → `personaAvailable` = `resume_content` has keys. Silent catch.
- [x] `GET /searches` — L183, only when `searchId` is set; failure → name falls back to the literal `'search'`.
- [x] `GET /jobs/{id}` — L479, only when `?job=` present and differs from current detail.

### On change (list)
- [!] `GET /jobs` with `buildParams(0)` — `fetchJobs` L220-231, triggered by `useEffect` L232 whenever `buildParams` identity changes, i.e. on any change to `filters`, `sortBy`, `dSearch`, `searchId` (L218). Params built L205-218: `limit=40`, `offset`, `status` (csv), `company` (csv), `source` (csv), `h1b_verdict` (csv), `min_score`, `min_salary`/`max_salary` (×1000), `title_search`, `search_id`, `sort_by` (omitted when `'date'`). **Error handling: `console.error` only (L229) — no toast, no error UI; `jobs`/`total` keep their previous values.**  _→ FEED-11_
- [!] `GET /jobs` with `buildParams(offset)` — `loadMore` L238-251 (infinite scroll, L252-255 threshold 320 px from bottom; also refill from `patchLocal` L291 when fewer than 12 rows remain). Dedups by id (L245). Error: `console.error` only (L249).  _→ FEED-38_
- [x] Title search debounce: 400 ms (L195) `search` → `dSearch`.
- [x] `GET /jobs/{id}` — `focusAt` L264 on every row focus / keyboard move; result replaces detail only if still the same id. Silent catch.

### On change (detail)
- [x] `GET /jobs/{id}/cached-page` — L456, when `viewCached` turns on and `cachedHtml` is empty; `responseType: 'text'`. Success: srcDoc; empty body or failure → `'<p …>No cached snapshot.</p>'` (L457-458).
- [x] `GET /jobs/{id}/frame-check` — L467, when detail has a URL, extension not detected, not viewing cached, `forceFrame` false and `frameOk === null`. `embeddable !== false` → true; failure → `true` (optimistic).

### Polling intervals
- [~] Extension marker poll: 200 ms × ≤11 ticks (~2 s), L144-147; stops once `data-jn-ext` seen or after 11 ticks.  _(untestable in this harness — see feed.md “Couldn't test”)_
- [~] Score-watch poll: every 3000 ms (L520) while `scoreWatchRef` non-empty; per watched id `GET /jobs/{id}` (L513) until `cv_scores` non-empty or 90 s elapsed (L303). Entries added only by `saveJob` on an unscored job (L308). Failures keep the entry (L516). Runs for the life of the component (interval always set, L520).  _(untestable in this harness — see feed.md “Couldn't test”)_
- [~] In-flight poll: every 3000 ms + immediate tick (L567) while any listed job has `in_flight` or `watchExtra` is non-empty (L526-528). Calls `GET /monitor/in-flight?job_ids=<csv>` (L532); when an id leaves in-flight after being seen (L534-536): `GET /monitor/finished?job_ids=<csv>&since=<epoch-ms − 20 s>` (L541, failure → assume ok), then `GET /jobs/{id}` per finished job (L547, silent catch), toast per `pendingRef` entry (L553-557), `refreshStats()` (L562). Whole tick wrapped in silent catch (L565). Effect re-arms whenever the set of in-flight ids changes (L570).  _(untestable in this harness — see feed.md “Couldn't test”)_

## 3. Interactive elements

Legend: **API** = calls made; **state** = React state mutated; **ok-toast** / **fail-toast** = whether a toast appears; "no catch" = promise has no rejection handler.

### 3a. Header (L595-603)
- [x] **"Score {N} unscored jobs"** pill — L601 (shown only when `stats.unscored > 0`); handler `openRescoreBulk` L404-412. API: `GET /resumes?is_base=true` + `GET /settings` (via `loadRescoreOpts` L336-346), `GET /jobs/unscored-ids` (L407, default backend limit 500). State: `rescoreDepth='full'`, `rescoreOpts`, `rescoreSel` (default resume only if `default_resume_id` matches, else all — L344), `rescoreJob {verb:'Score', title:'N unscored jobs', jobs:[{id}…]}`. ok-toast: none (opens the Rescore modal). fail: `console.error` only (L345, L411); if `ids` is empty nothing happens at all (L409) — no message.

### 3b. Filter bar (L606-686)
- [x] **Search titles…** text input — L609; `onChange → setSearch`; debounced 400 ms → `dSearch` (L195) → `GET /jobs`. Clears with normal text editing only (no ✕).
- [x] **"from “{searchName}” ✕"** pill — L612-615 (shown when `searchId`); click → `setSearchId('')`, `setSearchParams({}, {replace:true})`. Triggers `GET /jobs` refetch (buildParams dep). No API of its own.
- [x] **Source ▾ / "Source · N"** trigger — L617 via `Drop` default trigger L71-77; `onToggle → setMenu('source'|null)`. Active state when `filters.source.length > 0`.
  - [x] Source **✕ clear** — `Drop` L75 (`onClear` L617) → `setF({ source: [] })` (L572 also `setSel(0)`).
  - [x] Source **item checkbox** (one per `sourceList` entry) — `Check` L91-97 rendered at L618 → `togF('source', s)` L573. Label via `srcLabel` L50.
  - [x] Source **empty copy** "No sources" — L618.
- [x] **Company ▾ / "Company · N"** trigger — L620 (`width={248}`).
  - [x] Company **✕ clear** — L75 / L620 → `setF({ company: [] })`.
  - [!] Company **search input** (autoFocus) — L621; `onChange → setCompanyQuery`; placeholder shows `companyList.length`. NOT cleared when the menu closes (state persists across opens).  _→ FEED-32_
  - [x] Company **item row** — L631 → `togF('company', c.name)`; shows `c.count` (L634) in mono. Picked pin to top; list capped at 80 (L627).
  - [x] Company footnote "Top by open roles · picked companies pin to the top" — L637.
  - [x] Company **empty copy** "No matches" — L639.
- [x] **H-1B ▾ / "H-1B · N"** trigger — L642 (`width={196}`).
  - [x] H-1B **✕ clear** — L75 / L642 → `setF({ h1b_verdict: [] })`.
  - [x] H-1B **item checkbox** — L643, one per verdict in `['likely','possible','unlikely','unknown']` ∩ `verdictList` → `togF('h1b_verdict', v)`. Labels strip the "H-1B " prefix.
  - [x] H-1B **empty state — NONE** (empty panel with 8 px padding when `verdictList` is empty).
- [x] **Score ≥ / "Score ≥ N"** trigger — L645 (`width={212}`).
  - [x] Score **✕ clear** — L75 / L645 → `setF({ min_score: '' })`.
  - [x] Score **preset pills 70 / 80 / 90** — L647 → `setF({ min_score: String(n) })`.
  - [!] Score **"or at least" number input** — L651 → `setF({ min_score: e.target.value })` (fires a `GET /jobs` per keystroke — no debounce).  _→ FEED-33_
  - [!] Score note "Unscored jobs stay visible — this only hides low scores" — L653. (Backend filters on `best_cv_score >= min_score`, `routes_jobs.py:97-98` — NULLs excluded by SQL, so verify the note is actually true.)  _→ FEED-05_
- [x] **Salary / "Salary ≥ $NK" / "$NK–$MK" / "Salary ≤ $MK"** trigger — L655 (`width={224}`).
  - [x] Salary **✕ clear** — L75 / L655 → `setF({ min_salary: '', max_salary: '' })`.
  - [x] Salary **preset pills $150K / $180K / $220K** — L657 → `setF({ min_salary: String(n) })`.
  - [!] Salary **"at least" number input** — L661 → `setF({ min_salary })` (per keystroke).  _→ FEED-33_
  - [x] Salary **max input — DOES NOT EXIST**. `max_salary` is in `DEFAULTS` (L53), the label (L655), the clear (L655) and `buildParams` (L213), but no control sets it; only a stale `v2_feed_filters` localStorage value can populate it.
  - [!] Salary note "Jobs without a listed salary stay visible" — L663. (Backend filters `salary_max >= min_salary`, `routes_jobs.py:115-116` — NULLs excluded; verify.)  _→ FEED-06_
- [x] **Status · {labels|Any}** custom trigger — L665-675; `trigger` render L669; click → toggle `menu='status'`. `statusActive` when `filters.status` differs from `DEFAULTS.status` (`[]`).
  - [x] Status **✕** (when active) — L672 → `setF({ status: [] })` ("Any").
  - [x] Status **item checkbox** — L676, one per `STATUS_OPTS` (New/Saved/Applied/Skip/Ignored, L51) → `togF('status', v)`.
- [x] **Sort ▾** custom trigger — L679-680 (`align="right"`, `width={172}`); shows current `SORT_OPTS` label (L52).
  - [!] Sort **item** (Top score / Newest first / Salary, high to low / Company A–Z) — L682 → `setSortBy(v)`, `setMenu(null)`, `setSel(0)`. Persists to `v2_feed_sort` (L116). Triggers `GET /jobs`.  _→ FEED-04_
- [x] **Drop backdrop** (any open menu) — L81, fixed full-screen, click → `onToggle` (closes). Panel repositioned only on open (L60-67) — not on resize/scroll.

### 3c. List header (L692-713)
- [x] **Select-all checkbox** — L693; click → `setChecked(all shown ids)` or `∅` when all already checked. Title "Select all shown". Compares `checked.size === jobs.length`.
- [!] Text "{jobs.length} shown · {total} matching" — L694 (see §8).  _→ FEED-01_
- [x] Hint "⇧ range · {Ctrl|⌘} pick" — L696 (`PICK_KEY` L101-102).
- [x] **"?" keyboard-shortcuts toggle** — L697 → `setShortcutsOpen(v => !v)`.
  - [x] Shortcuts **backdrop** — L701 → `setShortcutsOpen(false)`.
  - [!] Shortcuts **popover** — L702-710 lists `SHORTCUTS` (L103): `j / ↓`, `k / ↑`, `s`, `x`, `a`, `e / o`, `r`, `{Ctrl|⌘}-click`, `Shift-click`.  _→ FEED-17_

### 3d. Bulk action bar (L715-725, shown when `checked.size > 0`)
- [x] Label "{checked.size} selected" — L717.
- [!] **Save** — L719 → `bulkStatus('saved')` L420-424. API: `POST /jobs/bulk-update {job_ids, updates:{saved:true,status:'saved'}}`; then `setChecked(∅)`, `fetchJobs()`. ok-toast: none. fail: `console.error` only (L423). No undo.  _→ FEED-20_
- [!] **Skip** — L720 → `bulkStatus('skip')`. API: `POST /jobs/bulk-update {job_ids, updates:{status:'skip'}}`. ok-toast: none. fail: `console.error` only. No undo (single-row skip has undo; bulk does not).  _→ FEED-20_
- [x] **Score** — L721 → `bulkScore` L425: for each checked job with `scoredCount === 0` → `scoreJob` (L326-333: `POST /analyze/{id}?depth=full` with `{}`; progress toast "Scoring “{title}”…" per job; error toast "Scoring failed for “{title}”" per failure; completion toast via in-flight poll). Then `setChecked(∅)`. Already-scored checked jobs are silently skipped.
- [x] **✦ Tailor** — L722 → `setPicker({ mode:'tailor', jobs: checked jobs })` (opens Create-copy modal, §3i).
- [x] **✕ clear selection** — L723 → `setChecked(∅)`.

### 3e. Job rows (L727-807)
- [x] **List scroll container** — L727 (`ref=listRef`, `onScroll=onListScroll` L252-255) → `loadMore` when within 320 px of bottom. No "loading more" or "end of list" indicator.
- [x] **Row click** — L738 → `rowClick(e, i, j)` L415-419: Ctrl/⌘-click toggles `checked` (L416), Shift-click range-selects from `lastIdx` (L417), plain click → `focusAt(i)` (L257-265: sets `sel`, `detail` (list-row data), resets `reportTab`, `viewCached`, `cachedHtml`, `forceFrame`, `frameOk`; releases `pinnedRef`; `GET /jobs/{id}` refresh, silent catch).
- [x] Row **score ring** — L745-749 (when `scoredCount > 0`): SVG ring (`ROW_C` L12, colour `scoreColor` L23) + number.
  - [x] Ring **"N" report-count badge** — L750 (when `nsc > 1`), title "{N} résumé reports". No handler.
- [x] Row **spinner** — L753-756 (when `in_flight` non-empty and unscored). No handler.
- [!] Row **"SCORE" dashed button** — L758 (when unscored and not running); `.v2-hover-accent`; `stopPropagation` + `scoreJob(j)`. API `POST /analyze/{id}?depth=full`. ok-toast: progress (kind `progress`) immediately; `success`/`error` on completion via poll (L553-557). fail-toast: yes, `error` (L332).  _→ FEED-13_
- [x] Row **checked mark ✓** — L760 (when in `checked`). No handler.
- [x] Row **title** — L765 (`title=` tooltip, ellipsis, strike-through when `ignored`).
- [~] Row **✦ tailored-résumé link** — L766, `<a href="/resumes?resume={tailored_resume_id}">` — **classic UI route**, not `/v2/resumes/{id}`; `stopPropagation`; title "Open tailored résumé". Full page navigation out of v2.  _(untestable in this harness — see feed.md “Couldn't test”)_
- [x] Row **status badge** — L767 (`BADGE` L39-44: Applied/Saved/Skipped/Ignored). No handler.
- [x] Row company / location / salary / visa / time-ago — L770-777 (display only; tooltips on company L770, location L772).
- [x] Row **action column** — L782 (`stopPropagation` on the whole column).
  - [!] **♥ Save** — L783 (`.v2-rail-save .v2-rail-cell`, title "Save (s)") → `saveJob(j)` L308: toggles `saved` and `status` (`'saved'`⇄`'new'`); if saving an unscored job → `watchForScore` (L302-304). API `PATCH /jobs/{id} {saved, status}` via `patchRemote` L298-301 (optimistic `patchLocal` first; `refreshStats` on success). ok-toast: none. fail-toast: **none** — `console.error` + `fetchJobs()` (L300). No undo.  _→ FEED-12, FEED-29_
  - [!] **✕ Skip** — L784 (`.v2-rail-skip`, title "Skip (x)") → `skipJob(j)` L309: `showUndo` (L305-307, `undo` toast "Skipped “{title}”", 5 s) THEN `patchRemote(j, {status:'skip'})`. Row removed optimistically (L286-292; refills via `loadMore` when < 12 rows). ok-toast: `undo` kind (shown before the PATCH resolves). fail-toast: none — `console.error` + `fetchJobs()`; the undo toast remains visible even if the PATCH failed.  _→ FEED-07, FEED-12_
    - [x] Undo toast **"Undo"** action — L306 → `PATCH /jobs/{id} {status: prev, saved: prev}`, `fetchJobs()`, `refreshStats()`. fail: `console.error` only, no toast.
  - [!] **⋯ More** — L785-790 (`.v2-rail-copy`, title "More") → computes fixed position (flips up when < 236 px below) and sets `rowMenu {id,left,top|bottom}`; click again closes.  _→ FEED-12_
    - [x] Row menu **backdrop** — L793 → `setRowMenu(null)`.
    - [x] Row menu **"Mark applied" (a)** — L795-796 → `applyJob(j)` L310: `showUndo` ("Applied to “{title}”") + `PATCH /jobs/{id} {status:'applied'}`. Toasts as Skip. Note: v2 does NOT create an Application record here (classic feed did) — PATCH only; verify backend PATCH side effects.
    - [x] Row menu **"Tailor résumé" (t)** — L795 (bold) → `setPicker({mode:'tailor', jobs:[j]})`. No `t` key handler exists.
    - [x] Row menu **"Rescore" (r)** — L795 → `openRescore(j)` L347: `rescoreJob {verb: 'Rescore'|'Score', …}` + `loadRescoreOpts()`.
    - [x] Row menu **"Open posting ↗" (e)** — L795 → `window.open(j.url, '_blank', 'noopener,noreferrer')`; silently no-op when `j.url` is empty (item still shown).
    - [!] Row menu **"Ignore {company} everywhere"** — L799 (`.v2-hover-bad`, red) → `ignoreCompany(j)` L313-325: removes every row with that company locally + clears detail if same company (L315-316), then `GET /settings` → `PATCH /settings {company_exclude_global:[…, name]}` (L319-322). **No confirm dialog** (classic `frontend/src/components/JobFeed.jsx:804` had `confirm()`), **no toast**, **no undo**. fail: `console.error` + `fetchJobs()` (L324). Long company names are not truncated inside the 228 px menu.  _→ FEED-08, FEED-34_

### 3f. Detail header (L815-859)
- [!] **Collapse chevron ⌄/›** — L817 (`.v2-hover-accent`) → `setHeadOpen(v => !v)` (persisted to `v2_feed_ui`).  _→ FEED-14_
- [x] **Header text block** (eyebrow / title / meta) — L818 → same `setHeadOpen` toggle (whole block clickable).
- [x] **Open ↗** anchor — L834 (`.v2-act`, `target=_blank rel=noopener noreferrer`), only when `d.url`.
- [~] **Primary button "Tailor résumé" / "✦ Open tailored ↗"** — L835 → if `tailored_resume_id`: `openTailored(d)` L380-384 (`navigate('/v2/resumes/{id}')`; else `GET /resumes` to find a non-base copy for the job (silent catch), else `setPicker({mode:'tailor'})`); otherwise `setPicker({mode:'tailor', jobs:[d]})`.  _(untestable in this harness — see feed.md “Couldn't test”)_
- [x] **⋯ More actions** — L837 (`.v2-act`, title "More actions"; accent-tinted while open) → `setHeadMenu(v => !v)`.
  - [x] Head menu **backdrop** — L840 → `setHeadMenu(false)`.
  - [x] Head menu **"✦ Re-tailor résumé" (t)** — L843 (only when `tailored_resume_id`; bold) → `setPicker({mode:'tailor', jobs:[d]})`.
  - [x] Head menu **"Mark applied" (a)** — L844 → `applyJob(d)`.
  - [x] Head menu **"Rescore" (r)** — L845 → `openRescore(d)`.
  - [x] Head menu **"Cover letter ↗" (c)** — L846 → `navigate('/v2/cover-letters?job={id}')` (handled by `CoverLetters.jsx:153`). No `c` key handler exists.
  - [x] Head menu **"Copy résumé with tracers"** — L847 → `setPicker({mode:'copy', jobs:[d]})`.
  - [!] Head menu **"Ignore {company} everywhere"** — L852 (`.v2-hover-bad`) → `ignoreCompany(d)` (same caveats as L799).  _→ FEED-08, FEED-34_

### 3g. Report band (L862-997, when `dScored`)
- [!] **Band header row** — L864 (`.v2-hover-accent`) → toggles `reportOpen`; when opening, sets `reportTab` to the best report's index. Shows ring (L867-871), best name (L873, ✦ prefix if tailored), "{coverage}% keywords" (L874), "{reqMet} of {reqRows.length} requirements met" (L875), "{N} report(s)" (L877).  _→ FEED-18_
- [x] **Report tab** (one per résumé score) — L886 (`.v2-tab`, title = name) → `setReportTab(k)`, `setReqFilter('all')`.
- [!] **"+ Rescore"** — L893 (`.v2-navlink`) → `openRescore(d)`.  _→ FEED-14_
- [x] **"Score breakdown" toggle** — L902 (`.v2-hover-accent`) → `setBreakdownOpen` (persisted). Grid L908-921, each criterion `val/20` + hairline bar.
- [x] **"Keyword coverage" toggle** — L928 (`.v2-hover-accent`) → `setKeywordOpen` (persisted). Bar L936; "{matched} matched · {missing} missing" L938.
  - [x] **"Show matched" / "Hide matched"** — L939 (only when matched list non-empty) → `setShowMatched` (persisted). Chips L941 (matched, `--accent-soft`/`--good`) and L942 (missing, `--bad-soft`/`--bad`).
- [x] **"Requirement mapping" toggle** — L951 (`.v2-hover-accent`) → `setReqOpen` (persisted); shows "{reqMet} of {N} met" L953.
  - [x] **All {N} / Gaps {N−met}** segmented control — L958 (only when `reqOpen`) → `setReqFilter('all'|'gaps')` (persisted).
  - [x] Requirement table — L963-974 (header L964-966, rows L967-973 filtered by `reqFilter`); evidence column falls back `cv_evidence || cv_match || '—'` (L970).
- [x] Hard blockers box — L980-983 (display only). ATS tip — L986-989 (display only). Fit strengths fallback (L898, only when no `rpt.summary`), fit gaps fallback (L991, only when no requirement rows), quick-scored notice (L992).

### 3h. Unscored / running bands and posting area (L1000-1059)
- [x] **"Score this role"** — L1009 (unscored band, when `!dScored && !running`) → `openRescore(d)`.
- [x] Running band — L1012-1021 (display only: "Scoring in progress — This continues in the background if you navigate away.").
- [!] **Live / Cached** segmented toggle — L1032 (`setViewCached(false)`) / L1033 (`setViewCached(true)` → triggers `GET /jobs/{id}/cached-page` L456). Only rendered when `dCached` (= `status === 'applied' && has_cached_page`, L590). Caption L1030: "Cached snapshot · captured when you applied" / "Live posting".  _→ FEED-35_
- [x] **Cached iframe** — L1038, `srcDoc={cachedHtml || '<p …>Loading cached snapshot…</p>'}`, `sandbox="allow-same-origin"`, title "cached".
- [!] **Live iframe** — L1041, `src={d.url}`, `sandbox="allow-scripts allow-same-origin allow-popups allow-forms"`, title "posting". Rendered whenever `d.url && (extActive || forceFrame || frameOk !== false)` — i.e. also while the frame-check is still pending (`frameOk === null`).  _→ FEED-22_
- [x] Frame-blocked panel — L1044-1054 (when `d.url` and `frameOk === false` and ext not active): copy L1047-1048; **"Open in new tab ↗"** anchor L1050; **"View cached snapshot"** L1051 (`.v2-act`, only when `dCached`) → `setViewCached(true)`. No "try to embed anyway" control (`forceFrame` is never set true — see §7).
- [x] Posting area is `display:none` (not unmounted) while `reportOpen` (L1025) so the iframe keeps its state.

### 3i. Create-résumé-copy modal (L1066-1126, when `picker`)
- [x] **Scrim backdrop** — L1070 → `setPicker(null)`. Card `stopPropagation` L1071.
- [x] Header: "Create résumé copy" / title (single job title or "{N} selected roles") / company — L1074-1076.
- [~] Existing-copy banner **"Open it ↗"** — L1083 (when single job has `tailored_resume_id`) → `setPicker(null)`, `openTailored(single)`.  _(untestable in this harness — see feed.md “Couldn't test”)_
- [x] **Method card "✦ Tailor with AI"** / **"⧉ Copy with tracers"** — L1094 → `pickMethod(m)` L393-396 (copy mode drops a `'persona'` base back to the first real base).
- [x] **Base résumé radio row** — L1108 (`.v2-act`) → `setCvBase(r.id)`; list from `cvBases` L397-401 (base résumés + "Persona" when tailoring and persona available, note "from /persona" L1111). Empty copy "No base résumés found." L1104. Default base seeded on open L387-391.
- [x] Footer note — L1119 ("Runs an LLM pass against résumé" / "Instant · no LLM cost · lands in Résumés").
- [x] **Cancel** — L1120 (`.v2-act`) → `setPicker(null)`.
- [x] **"Tailor résumé" / "Create copy"** confirm — L1121; disabled-looking when `cvBase == null` (guarded in onClick) → `runResume(cvMode, picker.jobs, cvBase)` L364-379:
  - copy: `POST /resumes/copy {base_resume_id, job_id}` per job; navigates to `/v2/resumes/{data.id}` only when exactly one job. ok-toast: **none** (multi-job copy is completely silent). fail-toast: `error` "Copy failed for “{title}”" (L376).
  - tailor: `progress` toast "Tailoring for “{title}”…" then `POST /resumes/tailor {base_resume_id, job_id}` per job; marks `in_flight: ['tailor_resume']` and adds to `watchExtra`. Completion `success` toast with "Open ↗" action → `/v2/resumes/{tailored_resume_id}` (L552-556) or `error` "Failed — …". fail-toast: `error` "Tailor failed for “{title}”".
  - always ends with `setChecked(∅)` (L378).

### 3j. Rescore modal (L1129-1181, when `rescoreJob`)
- [x] **Scrim backdrop** — L1130 → `setRescoreJob(null)`. Card `stopPropagation` L1131.
- [x] Header: "{Score|Rescore} against résumés" / title / company — L1134-1136.
- [x] "{rescoreSel.length} selected" — L1143.
- [x] **Résumé checkbox row** — L1149 (`.v2-act`) → toggles id in `rescoreSel`; note column `base` / `from /persona` (L1153). Empty copy "No résumés available." L1145 (also shown while `loadRescoreOpts` is still in flight — no loading branch).
- [x] **Depth card "Light — Scores only"** / **"Full — Report + keywords"** — L1164 → `setRescoreDepth(v)`.
- [x] Footer note "Runs in the background" — L1175.
- [x] **Cancel** — L1176 (`.v2-act`) → `setRescoreJob(null)`.
- [x] **Run scoring** — L1177 (grey when `rescoreSel` empty, but click still calls `runRescore`, which returns early L350 with no feedback) → `runRescore` L348-362: closes modal; if >1 job one `progress` toast "Scoring N jobs…"; per job `POST /analyze/{id}?depth={light|full}` `{cv_ids: rescoreSel}`, marks `in_flight`, adds to `watchExtra`. Single job: `progress` toast + `pendingRef` → completion toast. Multi job: **no completion toast** (pendingRef not set, L355) and **no error toast** on failure — `console.error` only (L360). Sequential awaits — 500 jobs = 500 serial POSTs with the modal already closed.

### 3k. Keyboard shortcuts (L428-446, window `keydown`; ignored inside INPUT/TEXTAREA/SELECT and with Ctrl/⌘/Alt held)
- [!] `f` / `j` / `ArrowDown` → `focusAt(idx+1)` (L434; `preventDefault`). `f` is undocumented in the popover.  _→ FEED-17_
- [!] `g` / `k` / `ArrowUp` → `focusAt(idx−1)` (L435). `g` undocumented.  _→ FEED-17_
- [x] `s` → `saveJob(job)` then advance to next (L436).
- [x] `x` → `skipJob(job)` then `focusAt(min(idx, len−2))` (L437).
- [x] `a` → `applyJob(job)` (L438).
- [!] `e` → `window.open(job.url)` if url (L439). **`o` is listed in the popover (L103) but NOT handled.**  _→ FEED-17_
- [x] `r` → `openRescore(job)` (L440).
- [!] `t`, `c` — shown as hints in menus (L795, L843, L846) but NOT handled.  _→ FEED-17_
- [!] `Escape` — NOT handled anywhere (menus, modals, shortcut popover close only via backdrop/Cancel).  _→ FEED-16_
- [!] `Enter` — NOT handled (classic feed toggled the detail with Enter).  _→ FEED-17_
- [x] Selected row auto-scrolls into view on `sel` change (L447, `scrollIntoView({block:'nearest'})`).
- [x] Ctrl/⌘-click and Shift-click on rows — see §3e (L416-417).

### 3l. Toasts (L1184 `ToastStack`)
- [x] Toast **✕ dismiss** — `Toast.jsx:71` → `onClose`. Toast **action label** (Undo / Open ↗) — `Toast.jsx:66-67` → `onAction()` then close. Kinds/TTLs: progress 2.5 s, success 2.5 s, undo 5 s, error sticky (`Toast.jsx:21`). Max 3 visible (`Toast.jsx:22`).

## 4. States rendered

### Jobs list (L727-807)
- [!] Loading — L728: "Loading…" (only during `fetchJobs`, not during `loadMore`).  _→ FEED-11_
- [!] Zero results — L729: "No jobs match." (same copy for "no jobs at all" and "filters exclude everything"; no clear-filters affordance in the empty state).  _→ FEED-24_
- [!] **Error branch — DOES NOT EXIST** for `GET /jobs` (L229) or `loadMore` (L249). On first-load failure the list shows "No jobs match."; on a later failure the stale list stays with no indication.  _→ FEED-11_
- [!] **Loading-more / end-of-list indicators — DO NOT EXIST**.  _→ FEED-38_
- [x] Long strings: title single-line ellipsis + tooltip (L765); company `maxWidth:230` ellipsis + tooltip (L770); location ellipsis + tooltip, `minWidth:40` (L772); salary `maxWidth:170` ellipsis (L775); "Salary not listed" fallback (L775). Ignored rows: hatched background (L739), 0.55 opacity (L740), strike-through (L765).

### Header stats (L598)
- [!] Initial render shows `0 open roles · 0 arrived today · 0 not yet scored` until `/jobs` and `/jobs/feed-stats` resolve (state seeds L108, L155). No loading/error branch.  _→ FEED-01, FEED-11_

### Filter dropdowns
- [!] Source empty — L618 "No sources". Company empty — L639 "No matches". H-1B empty — **no branch** (L643). Score/Salary/Status/Sort — static content, no data-dependent state.  _→ FEED-26_
- [x] Company list truncation — top 80 after filtering (L627), with footnote L637.
- [x] Search-scope pill name fallback — `'search'` when lookup fails or id not found (L183).

### Detail panel (L811-1061)
- [x] No selection — L812 "Select a job." (also after `ignoreCompany` clears the detail, L316, and when the list is empty, L268).
- [x] **Loading branch — DOES NOT EXIST**: row data is shown immediately and silently replaced by `GET /jobs/{id}` (L264). Fields absent from the list payload may pop in.
- [x] **Error branch — DOES NOT EXIST** for `GET /jobs/{id}` (L264 silent) or the `?job=` permalink (L483 silent — a bad id leaves "Select a job." with `?job=` still in the URL until the next sync).
- [x] Header expanded (L819-829) vs collapsed one-line summary (L830, ellipsis); title clamps to 2 lines expanded / 1 collapsed (L822) with tooltip; company `maxWidth:300` (L820); salary `maxWidth:230` (L825); location `maxWidth:270` (L826); visa text L577 ("· N LCAs" / "· no LCA records").
- [!] Report band — only when `dScored` (L862). Unscored band — `!dScored && !running` (L1000): "Not scored yet — Score against your résumés for the fit breakdown, requirements and keywords". Running band — `running` (L1012): "Scoring in progress …". Note `running` only checks `'analyze_job'` (L589); a running `tailor_resume` shows neither band change.  _→ FEED-19_
- [x] Report body branches: summary (L897) else fit_strengths (L898); breakdown only if `rpt.breakdown` has keys (L900); keyword section only if `coverage != null` (L926); requirement section only if rows (L948); hard blockers (L979); ATS tip (L985); fit_gaps only if no requirement rows (L991); quick-scored notice when no `rpt` AND no gaps AND no strengths (L992). A report with `rpt` but none of the sub-fields renders an empty body (no branch).
- [x] Best name `maxWidth:220` ellipsis + tooltip (L873); tab `maxWidth:230` ellipsis + tooltip (L886); requirement rows wrap (L968-971), no truncation; keyword chips wrap (L941-942).
- [x] Posting: cached iframe (L1038) with inline "Loading cached snapshot…" / "No cached snapshot." fallbacks (L457-458, L1038); live iframe (L1041); frame-blocked panel (L1044-1054) copy "This posting refuses to be framed — {company} sends X-Frame-Options, so the live page cannot render here. {You applied to this role, so a cached snapshot is available. | Open it in a new tab, or install the Navigator extension to strip frame-blocking headers.}"; no URL — L1056 "No posting URL captured for this job.". **No "probe in progress" state** — the live iframe is shown while `frameOk === null`, so a blocked site may flash the browser's refused-to-connect page before the panel swaps in.

### Modals
- [x] Picker: "No base résumés found." (L1104); modal title wraps unbounded for long job titles (L1075, no clamp); "{N} selected roles" for bulk (L1075).
- [x] Rescore: "No résumés available." (L1145) — doubles as the loading state (no spinner); title unbounded (L1135).
- [x] Bulk bar: none (only rendered when `checked.size > 0`).

## 5. Hover styles

All hover in this file is class-based; there are **no** `onMouseEnter`/`onMouseLeave` handlers and no `style-hover` attributes (grep: 0). Definitions live in `frontend/src/v2/theme.css`.

- [x] `.v2-row` — L738 (job row) → `theme.css:124` `background: var(--surface-2) !important`. Selected row uses `--surface-2` inline (L739), checked row `--accent-soft`; hover on a checked row overrides the accent tint because of `!important`.
- [x] `.v2-rail-cell` (base, no hover) — L783/784/785 → `theme.css:125`.
- [!] `.v2-rail-save` — L783 → `theme.css:127` (`--surface-2` / `--accent`).  _→ FEED-12_
- [!] `.v2-rail-skip` — L784 → `theme.css:128` (`--warn-soft` / `--warn`).  _→ FEED-12_
- [!] `.v2-rail-copy` — L785 → `theme.css:126` (`--surface-2` / `--text`).  _→ FEED-12_
- [!] `.v2-hover-accent` — L758 (row SCORE), L817 (head chevron), L864 (report band header), L902, L928, L951 (section toggles) → `theme.css:129` (`--surface-2` / `--text`).  _→ FEED-13, FEED-14_
- [x] `.v2-hover-bad` — L799, L852 (Ignore company) → `theme.css:130` (`--bad-soft !important`).
- [!] `.v2-menuitem` — `Check` L93, company item L631, sort item L682, row menu item L796, head menu item L849 → `theme.css:148` (`--surface-2`). Note the selected sort item sets inline `--accent-soft` background, which hover replaces (no `!important`, inline wins — verify which wins visually).  _→ FEED-04_
- [!] `.v2-act` — L834 (Open ↗), L837 (⋯), L1051 (View cached), L1108 (base radio row), L1120 (Cancel), L1149 (résumé checkbox row), L1176 (Cancel) → `theme.css:147` (`border-color: var(--accent) !important; background: var(--hover-soft) !important`).  _→ FEED-14_
- [x] `.v2-tab` — L886 → `theme.css:208` is a `transition` only; **no `:hover` rule exists for tabs**.
- [!] `.v2-navlink` — L893 ("+ Rescore") → `theme.css:133-134` (`--surface-2` / `--text`).  _→ FEED-14_
- [x] `.jn-v2 a:hover` — `theme.css:121` (`color: var(--text)`) applies to anchors L766 (✦ link — overrides its accent colour on hover), L834, L1050.
- [~] `.v2-scroll` — L82, L727, L896, L1025 → scrollbar styling `theme.css:221-223` (not hover, but a visual to compare).  _(untestable in this harness — see feed.md “Couldn't test”)_
- [~] `.v2-spin` — L754, L1015 → `theme.css:225-226`.  _(untestable in this harness — see feed.md “Couldn't test”)_
- [x] State-driven (not hover) tints that may be confused with hover during comparison: `Drop` active trigger (L72), Status trigger (L670), ⋯ open state (L790 row, L837 head), score/salary preset selected (L647/L657), sort selected (L682), method/depth cards (L1094/L1164), base/résumé rows (L1108/L1150), selected row (L739).
- [!] Controls with **no hover affordance at all** (inline-styled, no class): header "Score N unscored" pill (L601), search pill (L612), preset pills (L647, L657), select-all box (L693), "?" (L697), bulk bar buttons (L719-723), primary "Tailor résumé" (L835), "Show/Hide matched" (L939), All/Gaps segments (L958), "Score this role" (L1009), Live/Cached (L1032-1033), "Open in new tab ↗" (L1050), "Open it ↗" (L1083), method/depth cards (L1094, L1164), confirm buttons (L1121, L1177), modal scrims.  _→ FEED-15_

## 6. Theme

- [x] Dark mode is read in the shell, not here: `V2App.jsx:52` (`localStorage.jobnavigator_dark_mode === 'true'`), applied as `data-theme="dark|light"` on the `.jn-v2` wrapper `V2App.jsx:90`; toggled at `V2App.jsx:54` (buttons L146, L154 of V2App). JobFeed never reads the theme — it consumes CSS variables only.
- [x] Colour literals in `JobFeed.jsx`: **none** (grep for `#hex`, `rgb(`, `hsl(` → 0 matches). Only `'transparent'` / `'none'` keywords and `var(--…)` tokens.
- [x] Non-token colours reach the screen indirectly via the inline HTML strings for the cached iframe (L457, L458, L1038: `font-family:sans-serif`, no colour set → browser default black-on-white inside an iframe whose backdrop is `var(--iframe-bg)`), and via the live third-party iframe (L1041).
- [x] Tokens used (for the token audit): `--good --warn --bad --muted --accent --accent-soft --accent-ink --line --line-soft --edge --surface --surface-2 --text --text-2 --ink-2 --faint --track --rail --rail-ink --rail-accent --on-rail-sep --on-rail-line --on-rail-dim --bad-soft --warn-soft --scrim --shadow-menu --shadow-pop --shadow-modal --iframe-bg --serif --sans --mono`.

## 7. Suspicious

- [!] L576 `arrivedToday` — computed every render (24 h window over the loaded page), never rendered; the header uses `stats.arrived_today` (UTC-midnight, server-side) instead. Dead code.  _→ FEED-31_
- [!] L403 `unscored` memo — never referenced. Dead code.  _→ FEED-31_
- [!] L57 `Drop` destructures `align` but never uses it; passed at L665 and L679. Dead prop (right-alignment is actually done by the overflow flip at L65).  _→ FEED-31_
- [!] L135 `forceFrame` — only ever set to `false` (L263, L482); no control sets it `true`, so the "embed regardless" override and any "try anyway" button do not exist.  _→ FEED-31_
- [!] L103 `SHORTCUTS` lists `e / o` but only `e` is handled (L439); `f` and `g` are handled (L434-435) but not listed. Menu hints `t` (L795, L843) and `c` (L846) have no key handlers (L433-441).  _→ FEED-17_
- [!] No `Escape` handling for any menu/modal/popover (grep 0); no `Enter`.  _→ FEED-16_
- [!] L766 row ✦ link goes to the classic route `/resumes?resume={id}` (full-page leave of v2), while every other tailored-résumé path uses `/v2/resumes/{id}` (L368, L381, L382, L556).  _→ F-001 (fixed in source)_
- [!] L313-325 `ignoreCompany` — destructive, global setting change with no confirm (classic had one at `frontend/src/components/JobFeed.jsx:804`), no toast, no undo; rows removed locally BEFORE the settings round-trip.  _→ FEED-08_
- [!] L309-310 `skipJob`/`applyJob` push the undo toast before the PATCH is sent; a failed PATCH logs to console and refetches (L300) but the toast still says "Skipped/Applied to …".  _→ FEED-07_
- [!] L283-286 `patchLocal` assumes an empty status filter means "new + saved", and the comment at L274-276 claims applied/skipped jobs are filtered out of the default feed — but `backend/api/routes_jobs.py:90-92` applies **no status filter when `status` is absent**, so the default feed contains applied/skipped/ignored rows (with badges). After a skip the row vanishes locally and returns on the next refetch. Header copy "{total} open roles" (L598) is therefore mislabelled in the default view. Must verify against a live DB.  _→ FEED-01_
- [!] L53/L213/L655 `max_salary` is plumbed end-to-end but has no input control (only `min_salary` at L657/L661) — unreachable except via stale localStorage.  _→ FEED-30_
- [!] `Companies.jsx:393` deep-links to `/v2/feed?company=…`; this screen never reads `company` from the URL (only `job` L476, `search` L179).  _→ F-002 (fixed in source)_
- [x] L179 `searchId` is initialised from `window.location` once; not derived from `searchParams`, so it is not reactive.
- [!] L348-362 `runRescore` bulk path: failures are `console.error` only (no error toast, unlike `scoreJob` L332); no completion toast (`pendingRef` set only for a single job, L355); with up to 500 ids from `/jobs/unscored-ids` (`routes_jobs.py:238` default limit) the in-flight poll sends a ~18 KB `job_ids` query string every 3 s (L532) and then one `GET /jobs/{id}` per finished job (L547).  _→ FEED-20_
- [!] L404-412 `openRescoreBulk` — `loadRescoreOpts()` fires before knowing whether there are ids; empty ids → silent no-op although the header button advertised a count (stale `stats`). Title says "{ids.length} unscored jobs" which is capped at 500 while the button says `stats.unscored` (uncapped).  _→ FEED-21_
- [!] L364-379 `runResume` copy mode with >1 job: no navigation, no success toast — completely silent on success.  _→ FEED-20_
- [!] L1177 "Run scoring" and L1121 confirm look disabled but remain clickable; no feedback when the guard (L350 / L1121) short-circuits.  _→ FEED-21_
- [!] L1145 "No résumés available." is shown while `loadRescoreOpts` is in flight (modal opens at L347 before the fetch resolves) and can also show stale `rescoreOpts` from a previous open until the new fetch lands.  _→ FEED-21_
- [!] L795 "Open posting ↗" and L439 `e` silently do nothing when `url` is empty (the header hides "Open ↗" at L834 in that case — inconsistent).  _→ FEED-34_
- [!] L1041 live iframe rendered while `frameOk === null`; combined `sandbox="allow-scripts allow-same-origin"` lets framed content escape its sandbox (security note, out of scope for UI testing but worth flagging).  _→ FEED-22_
- [x] L60-67 `Drop` computes a fixed position only on open; window resize/scroll while open leaves the panel detached from its trigger (backdrop prevents scrolling the page, but not resize).
- [!] L621 `companyQuery` is never reset — reopening the Company menu shows the previous query.  _→ FEED-32_
- [!] L589 `running` checks only `analyze_job`; a job with `in_flight: ['tailor_resume']` shows the row spinner (L733 checks any op) but the detail shows the "Not scored yet" band if unscored.  _→ FEED-19_
- [!] L665 `active` is passed as a bare boolean (always true) — harmless because a custom trigger is supplied, but misleading.  _→ FEED-31_
- [x] L505-522 score-watch interval runs for the component's whole lifetime even when there is nothing to watch (cheap, but note).
- [x] `console.error` ×11 (L229, L249, L300, L306, L324, L332, L345, L360, L376, L411, L423). No `console.log`. No `TODO`/`FIXME`.
- [!] Unhandled-rejection audit: every promise has a `.catch`/`try` — but 8 paths swallow failures with no user feedback: `fetchJobs` L229, `loadMore` L249, `patchRemote` L300 (save/skip/apply), undo L306, `ignoreCompany` L324, `loadRescoreOpts` L345, `runRescore` per-job L360, `openRescoreBulk` L411, `bulkStatus` L423; plus 10 silent `.catch(() => {})` on read paths (L183, L197-201, L264, L382, L458, L467, L471, L483, L513-516, L547).  _→ FEED-07, FEED-11, FEED-20_

## 8. Counts that must agree

- [!] **Header "{total} open roles"** (L598) and **"{jobs.length} shown · {total} matching"** (L694) — both `total` from `GET /jobs` (`routes_jobs.py:120` `q.count()` under the CURRENT filters: status, company, source, verdict, min_score, salary, title_search, search_id). Same number, two labels; "open roles" is only true when the status filter is "new,saved" (and see §7 re default = all statuses). `jobs.length` grows by 40 per `loadMore` (L185) and shrinks by optimistic removals (L289) which also decrement `total` (L290).  _→ FEED-01_
- [!] **Rail "Jobs" badge** (`V2App.jsx:19`, `V2App.jsx:58`) — `GET /jobs?status=new&limit=1` → `data.total` (new-status only, no other filters), fetched once at shell mount and never refreshed by feed actions. Expect it to differ from the header total whenever a filter is active or the default feed includes non-new rows; it also goes stale after save/skip.  _→ FEED-01_
- [x] **"{stats.arrived_today} arrived today"** (L598) — `GET /jobs/feed-stats` (`routes_jobs.py:228-229`: `discovered_at >= UTC midnight`, all statuses, all searches). Row "just now / Nh ago" (L777, `timeAgo` L14-21) is relative-24 h, so rows labelled "Nh ago" with N < 24 may exceed the "arrived today" count and vice-versa around midnight UTC. Unused `arrivedToday` (L576) uses the 24 h rule.
- [x] **"{stats.unscored} not yet scored"** (L598) and **"Score {stats.unscored} unscored jobs"** (L601) — feed-stats (`routes_jobs.py:230-233`: status in new/saved AND `cv_scores` null/`{}`). Related but differently sourced: rescore modal title "{ids.length} unscored jobs" (L410) from `GET /jobs/unscored-ids` (same predicate, `limit=500`, `routes_jobs.py:238-248`); row "SCORE" button (L743/758) from client-side `scoredCount` = number of numeric `cv_scores` entries (L24-26) — a `cv_scores` object with only non-numeric values is "scored" for the backend and "unscored" for the row; unscored band (L1000) same client rule on the detail. Refreshed via `refreshStats` after PATCH / undo / completion, NOT after `bulkStatus` or `ignoreCompany`.
- [!] **Company dropdown counts** (L634) — `GET /jobs/companies/list?counts=1` (`routes_jobs.py:270-283`, aliases collapsed to canonical company, all statuses, no filters) vs the header/list `total` after picking that company (filtered by current status etc.). "Company · N" label (L620) is the number of companies picked, not jobs. Placeholder "Type to search {companyList.length} companies…" (L621) is the canonical-company count.  _→ FEED-26_
- [x] **Row ring badge "N"** (L750, `scoredCount` on the list payload) vs **band "{N} report(s)"** (L877, `reports.length` on the detail payload) vs **tab count** (L883) — same rule (numeric `cv_scores` entries) on two payloads; can differ transiently after a rescore until the poll refreshes both (L547).
- [!] **Row ring score** (L749, `bestScore` = max numeric) vs **band ring** (L871, `reports[0].score` after desc sort) — same derivation; vs **Score ≥ filter** which uses the server column `best_cv_score` (`routes_jobs.py:97-98`) — a stale `best_cv_score` would show a ring above the threshold while the filter hides it.  _→ FEED-27_
- [x] **"{reqMet} of {N} requirements met"** (L875) vs **"{reqMet} of {N} met"** (L953) vs **"All {N} / Gaps {N−met}"** (L958) — all from L585-586 on the active report; must agree with each other and with the ✓/✕ column (L971).
- [x] **"{coverage}% keywords"** (L874) vs **"{coverage}%"** (L931) vs bar width (L936) vs **"{matched} matched · {missing} missing"** (L938) — `keyword_coverage_pct` is a backend number; matched/missing are array lengths; verify `pct ≈ matched/(matched+missing)`.
- [x] **Breakdown "val/20"** (L915) sum vs the report score (L889) — five criteria × 20 = 100 per CLAUDE.md rubric; verify the sum equals the tab's `(score)`.
- [x] **"{checked.size} selected"** (L717) vs select-all box state (L693, `checked.size === jobs.length`) vs per-row ✓ (L760) — selection can include ids no longer in `jobs` after optimistic removal (L289 does not prune `checked`), so "N selected" may exceed visible checks.
- [x] **"{rescoreSel.length} selected"** (L1143) vs checked rows (L1147-1151).
- [x] **Picker "{N} selected roles"** (L1075) vs bulk bar count (L717) at the time Tailor was clicked (L722).
- [x] **H-1B verdict labels**: row "H-1B Likely/Possible/Unlikely/Unknown" (L776, `H1B` L33-38) vs detail "{label} · N LCAs | no LCA records" (L577) vs filter dropdown labels without the prefix (L643) — same `H1B` map.
- [x] **Salary**: row `fmtSalary` (L775) vs detail (L825, L830) — same helper L28-32 (`$NK` rounding, single value when min==max or one side missing); Salary filter label "$NK" (L655) is in thousands entered by the user, sent ×1000 (L212-213).

---

**Summary**
- Interactive elements catalogued: 118 (header 1, filter bar 27, list header 4, bulk bar 6, rows 15, detail header 10, report band 9, bands/posting 7, picker modal 8, rescore modal 8, keyboard 12, toasts 2, plus backdrops/scrims 6, shell-level 3).
- API endpoints used: 21 distinct (`GET /jobs`, `GET /jobs/{id}`, `PATCH /jobs/{id}`, `POST /jobs/bulk-update`, `GET /jobs/companies/list`, `GET /jobs/sources/list`, `GET /jobs/verdicts/list`, `GET /jobs/feed-stats`, `GET /jobs/unscored-ids`, `GET /jobs/{id}/cached-page`, `GET /jobs/{id}/frame-check`, `GET /resumes`, `GET /resumes?is_base=true`, `POST /resumes/copy`, `POST /resumes/tailor`, `POST /analyze/{id}`, `GET /settings`, `PATCH /settings`, `GET /persona`, `GET /searches`, `GET /monitor/in-flight`, `GET /monitor/finished`).
- Uncaught failure paths: 0 unhandled rejections, but 9 write/critical paths fail with console-only feedback and 10 read paths fail fully silently (19 user-invisible failure paths).
- Missing empty/error branches: 9 (jobs-list error, load-more indicator/error, detail loading, detail error, `?job=` bad-id error, H-1B dropdown empty, rescore-options loading, header-stats loading, report body with `rpt` but no sub-fields).
- Suspicious items: 27.
