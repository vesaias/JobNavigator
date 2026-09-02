# v1 Inventory — Job Feed / Applications / Companies

Catalogue of the legacy v1 React screens for the v2 regression pass. Line refs are `file:line` at the
time of writing (branch `v2-redesign`). Nothing here was executed — this is a static read of:

- `frontend/src/components/JobFeed.jsx` (1556 lines) — route `/`
- `frontend/src/components/ApplicationBoard.jsx` (306 lines) — route `/applications`
- `frontend/src/components/CompanyManager.jsx` (899 lines) — route `/companies`
- Shared: `frontend/src/api.js`, `frontend/src/App.jsx` (ClassicShell)

## Shared context (applies to all three screens)

- [ ] All three render inside `ClassicShell` — `frontend/src/App.jsx:48-103` (sidebar nav, dark-mode toggle, collapse toggle, `HealthBanner`, `WhatsNewBanner`, `<Outlet/>`).
- [ ] Axios instance `frontend/src/api.js:3-7` — `baseURL: '/api'`, `withCredentials: true` (session cookie `jn_session`).
- [ ] Request interceptor `api.js:10-16` — attaches `X-API-Key` from `localStorage['jobnavigator_api_key']` when present.
- [ ] Response interceptor `api.js:19-27` — any 401 dispatches `window` event `jn:unauthorized`; `App.jsx:137-141` opens the login modal. **This is the only global error surface** — every other failure in these three screens is `console.error` or silent.
- [ ] `App.jsx:129-134` — on app boot, `POST /api/auth/set-session` syncs the localStorage key to the cookie; 401 opens login modal.
- [ ] localStorage `jobnavigator_dark_mode` — `App.jsx:106-117`.
- [ ] localStorage `jobnavigator_api_key` — read in `api.js:11`, `App.jsx:130`.
- [ ] sessionStorage `jn:welcome` — `App.jsx:110-112`, gates `WelcomeModal`.

---

## 1. Job Feed — route `/` (`frontend/src/components/JobFeed.jsx`)

### 1.1 Route & storage

- [ ] Route `/` → `JobFeed` — `App.jsx:173`. Rendered inside ClassicShell layout route (`App.jsx:172`).
- [ ] Query param `?job=<id>` — deep-link opens the detail panel — `JobFeed.jsx:501-510`. Fetches `GET /api/jobs/{id}`, sets `selectedJob`, sets `viewCached` from `has_cached_page`, then **clears the query string** via `setSearchParams({}, { replace: true })` (`:507`). Guarded by `!selectedJob` so it only fires when nothing is open.
- [ ] localStorage `jobfeed_filters` — const `STORAGE_KEY` at `:47`; read `loadFilters()` `:69-78`; written on every filter change `:80-82` + `:291`. Shape: `{status[], company[], min_score, h1b_verdict[], source[]}` (`DEFAULT_FILTERS` `:64-67`, default status `['new']`). Both read and write are try/catch-swallowed.
- [ ] localStorage `jobfeed_filters_panel` — filter panel open/closed, read `:109-111`, written `:294-296`.
- [ ] **NOT persisted** (reset on reload): `titleSearch` `:137`, `sortBy` `:142`, `minSalary`/`maxSalary` `:198-199`, `offset` `:117`.
- [ ] Page-size constant `limit = 30` — `:118`.

### 1.2 Data loads

- [ ] `GET /api/jobs` (params: `limit`, `offset`, `status`, `company`, `source`, `h1b_verdict`, `min_score`, `title_search`, `sort_by`, `min_salary`, `max_salary`) — `fetchJobs` `:298-325`, called on mount and on every change to filters/offset/title-search/sort/salary (`:327`). Failure: `console.error` only (`:322`); `loading` still cleared, list keeps stale contents.
- [ ] `GET /api/jobs/companies/list` — dynamic company filter list, debounced 300ms — `:241`. Failure: `.catch(() => {})` — **silently swallowed**.
- [ ] `GET /api/jobs/sources/list` — dynamic source filter list — `:253`. Failure: silently swallowed.
- [ ] `GET /api/jobs/verdicts/list` — dynamic H-1B verdict list — `:265`. Failure: silently swallowed.
- [ ] Filter-list debounce timer 300ms — `:228-268`; title-search debounce 500ms — `:219-225`.
- [ ] **Polling A — in-flight ops**, `GET /api/monitor/in-flight?job_ids=…` every 3000ms — `:332-453` (`setInterval` `:444`, immediate first tick `:445`). Only runs while at least one visible job has `in_flight` or a `watchExtra` entry exists (`:335` early-return = zero idle cost). Failure: bare `catch {}` `:441` — next tick retries.
- [ ] Polling A side-effects: for each job that leaves in-flight, `GET /api/jobs/{id}` refetch — `:382` (per-job `catch {}` `:386`); `GET /api/monitor/finished?job_ids=…&since=…` to resolve completed vs failed for the toast — `:396` (`catch {}` `:403`, toast skipped rather than guessed).
- [ ] **Polling B — save-triggered score watch**, `GET /api/jobs/{id}` every 3000ms per watched id — `:472-498`. Watch registered by `watchForScore()` `:459-468` with a 60s deadline (`:462`, `:479`); interval is unconditional (runs even with an empty watch list, but early-returns at `:475`). Failure per job: `catch` re-queues (`:492`).
- [ ] `GET /api/jobs/{id}` for `?job=` deep-link — `:504`. Failure: silently swallowed (`:508`).
- [ ] `GET /api/jobs` refill when the triage list drains below 10 — `refillIfLow` `:641-667` (threshold const `:639`). Failure: `console.error` `:665`.

### 1.3 Interactive elements

Header / filter bar:

- [ ] **Info (keyboard shortcuts) button** — `:910-916`, toggles `showShortcuts` popover `:917-934`. No API.
- [ ] **Reset button** — `:940-943`. Resets filters to `DEFAULT_FILTERS`, offset, title search, sort, both salary fields. Triggers refetch via effect. No API of its own. Note: it does **not** clear `localStorage` directly — the persistence effect rewrites it.
- [ ] **Filter panel toggle** — `:944-949`, persists to `jobfeed_filters_panel`.
- [ ] **Title search input** — `:957-959`, 500ms debounce → `title_search` param.
- [ ] **Sort select** (Newest / Top Score / Top Salary / Company A-Z) — `:960-966`; resets offset; sends `sort_by` only when ≠ `date` (`:309`).
- [ ] **Status filter chips** (new / saved / applied / skip / ignored) — `:972-983`, `toggleFilter('status', …)` `:626-632`; resets offset; persisted.
- [ ] **Source filter chips** — `:987-995`, values come from `/jobs/sources/list`; label map at `:988` (direct, extension, jobspy_*, levels_fyi, linkedin_personal, linkedin_extension, jobright, freehire, playwright_url, playwright_direct); persisted.
- [ ] **H-1B verdict chips** (likely/possible/unlikely/unknown, intersected with `verdictList`) — `:999-1004`; persisted.
- [ ] **Score ≥ input** — `:1008-1010`; resets offset; persisted.
- [ ] **Min $K / Max $K salary inputs** — `:1014-1020`; values multiplied by 1000 before sending (`:311-312`); **not** persisted.
- [ ] **Company filter chips** — `:1028-1033`, from `/jobs/companies/list`; persisted.
- [ ] **Filter auto-pruning**: stale source/company/verdict selections are dropped when they vanish from the dynamic lists — `:271-288` (three effects).

Job list:

- [ ] **Select-all checkbox** — `:1050-1052`, `toggleSelectAll` `:874-880`. Selects/clears the current page's ids only.
- [ ] **Per-card checkbox** — `:1070-1073`, `toggleSelectJob` `:864-872`.
- [ ] **Card click** — `:1061`: toggles the detail panel for that job, sets `viewCached` (only when `has_cached_page && status==='applied'`), sets `selectedIndex`.
- [ ] **Tailored-resume icon (ScrollText)** — `:1082-1087`, `<a href="/resumes?resume={tailored_resume_id}">` — full page nav, not router.
- [ ] **Skip (X) button** — `:1090-1094` → `skipAndAdvance` `:770-780`. Advances selection first, shows Undo toast, then `PATCH /api/jobs/{id}` `{status:'skip'}` (`:777`), then local patch. Failure: `console.error` `:779` — **the optimistic advance and undo toast are not rolled back**.
- [ ] **Score bar hover tooltip** — `:1117-1140`, shows `scoring_report[best_cv].summary`. No API.
- [ ] **Best-CV chip** — `:1143-1150`; when the label is `Tailored` and `tailored_resume_id` exists it becomes a link to `/resumes?resume={id}`.
- [ ] **Report (FileText) buttons** — best-CV `:1152-1156` and per-additional-score `:1174-1178`; open the scoring-report modal. No API.
- [ ] **Additional CV score chips** — `:1161-1181`; `Tailored` again links to `/resumes?resume={id}`.
- [ ] **Save (bookmark) button** — `:1188-1191` → `saveAndAdvance` `:782-792`. `PATCH /api/jobs/{id}` `{saved, status: 'saved'|'new'}` (`:788`); on save with no existing scores registers `watchForScore` (`:789`). Failure: `console.error` `:791`, selection already advanced.
- [ ] **Applied (check) button** — `:1192-1195` → `applyJob` `:794-800`. Shows Undo toast, `updateJob` → `PATCH /api/jobs/{id}` `{status:'applied'}` (`:690`). Failure: `console.error` `:692`. Backend side-effect: auto-creates Application + Company.
- [ ] **Rescore (RotateCw) button** — `:1196-1200` → `openRescoreModal` `:821-845`. Loads `GET /api/resumes?is_base=true`, `GET /api/persona`, `GET /api/settings` in parallel (`:828-832`); persona added as a virtual option `persona` when `resume_content` is populated; preselects `default_resume_id`, else all. Failure: `console.error` `:844` — **modal still opens, with an empty option list**.
- [ ] **Open in new tab (ExternalLink)** — `:1201-1206`, plain `<a target="_blank">`.
- [ ] **Ignore company (Ban) button** — `:1207-1210` → `ignoreCompany` `:802-812`. `window.confirm` gate (`:804`), then `GET /api/settings` (`:806`) + `PATCH /api/settings` `{company_exclude_global: [...]}` (`:809`). Failure: `console.error` `:811` — no UI feedback; the feed is not refreshed either, so the ignore appears to do nothing.
- [ ] **Pagination Prev / Next** — `:1220-1230`; rendered only when `total > limit`; disabled at bounds.

Detail panel (right):

- [ ] **Cached / Live toggle** — `:1245-1252`; only rendered when `selectedJob.has_cached_page`.
- [ ] **Tailor Resume button** — `:1255-1268`; loads `GET /api/resumes?is_base=true` + `GET /api/persona` (`:1257-1260`, persona has its own `.catch`), sets `cvMode='tailor'`, opens modal. Outer failure: bare `catch {}` `:1263` — **modal opens with an empty resume list**.
- [ ] **Copy Resume button** — `:1269-1282`; same two loads, `cvMode='copy'`. Same silent-catch issue (`:1277`).
- [ ] **Cover Letter button** — `:1283-1286`; `navigate('/cover-letters?job={id}')`. No API.
- [ ] **Open (ExternalLink)** — `:1287-1292`.
- [ ] **Close panel (X)** — `:1293-1296`.
- [ ] **Cached-page iframe** — `:1301-1307`, `src=/api/jobs/{id}/cached-page`, sandboxed.
- [ ] **Live job iframe** — `:1309-1315`, `src=job.url`, sandboxed. Falls back to "No URL available" `:1316-1319`.

Modals:

- [ ] **Rescore modal** — `:1325-1367`. Backdrop-click closes (`:1326`). Controls: per-resume checkboxes `:1336-1340`, depth select (light/full) `:1351-1355`, Cancel `:1358`, Score `:1360-1363`. Score → `runRescore` `:847-861`: `POST /api/analyze/{jobId}?depth={depth}` with body `{cv_ids: [...]}` (`:852`), then optimistically marks `analyze_job` in-flight. Failure: `console.error` `:859` — **modal stays open, no message**. Empty-state text at `:1331`.
- [ ] **Scoring report modal** — `:1394-1520`. Backdrop-click closes; per-resume tabs `:1422-1430`; sections: summary, keyword coverage bar, matched/missing keyword chips, requirement-mapping table, hard blockers, ATS tip. Pure client-side render of `job.scoring_report`. No API.
- [ ] **Resume tailor/copy modal** — `:1522-1553`. Base-resume select `:1531-1541` (adds a `persona` option in tailor mode only, `:1538`), Cancel `:1544`, primary button `:1546-1549` → `generateCv` `:728-768`:
  - copy mode: `POST /api/resumes/copy` `{base_resume_id, job_id}` (`:737`) then hard redirect `window.location.href = /resumes?resume={id}`. Failure: `alert()` (`:742`) — the **only** blocking error surface on this screen.
  - tailor mode: `POST /api/resumes/tailor` `{base_resume_id, job_id}` (`:755`), 202 + background. Modal closes *before* the request (`:752`). Failure: pushes a `nok` toast + `console.error` (`:765-766`).

Keyboard shortcuts (`:530-608`, listener attached to `window`, ignored inside INPUT/TEXTAREA/SELECT `:532`, inside an iframe `:533`, or with Ctrl/Meta/Alt `:534`):

- [ ] `f` / `j` / `ArrowDown` → next job — `:538-545`.
- [ ] `g` / `k` / `ArrowUp` → previous job — `:546-553`.
- [ ] `s` → toggle save + advance — `:554-566`; `PATCH /api/jobs/{id}` `{saved, status}`; failure `console.error` `:564`.
- [ ] `x` → skip + advance — `:567-584`; shows Undo toast then `PATCH /api/jobs/{id}` `{status:'skip'}`; failure `console.error` `:582`.
- [ ] `e` / `o` → `window.open(job.url)` — `:585-592`.
- [ ] `Enter` → toggle detail panel — `:593-601`.
- [ ] Note: the left panel calls `window.focus()` on mouse-enter (`:903`) so shortcuts work without an explicit click.
- [ ] Auto-scroll of the selected card — `:611-615`.

Bulk bar / toasts:

- [ ] **Bulk action bar** — `:1370-1377`, visible while `selectedIds.size > 0`; buttons Skip All `:1373`, Save All `:1374`, Clear `:1375`. `bulkAction` `:882-897` → `POST /api/jobs/bulk-update` `{job_ids, updates}` (`:887`), then registers score watches on save and calls `fetchJobs()`. Failure: `console.error` `:896` — **selection is not cleared and no message shown**.
- [ ] **Undo toast** — `:1380-1382` (component `UndoToast` `:30-45`). Shown for skip and apply; auto-dismiss 5000ms (`:715`); hidden while the bulk bar is up. `handleUndo` `:720-726` → `PATCH /api/jobs/{id}` `{status: prevStatus, saved: prevSaved}` then `fetchJobs()`. **No try/catch at all** (`:723`) — a failed undo rejects unhandled and the toast never dismisses.
- [ ] **Tailor / score toasts** — `:1385-1391` (component `ToastItem` `:7-27`), driven by the in-flight poll; phases start / ok / nok; auto-dismiss 2500ms (`:190`); manual close button `:22`.

### 1.4 States

- [ ] Loading — `:1042-1043` "Loading jobs..." (list only; the detail panel and modals have no loading state).
- [ ] Empty — `:1044-1045` "No jobs found."
- [ ] Empty (rescore options) — `:1330-1331` "No base resumes or persona content yet."
- [ ] Empty (detail panel, no URL) — `:1316-1319` "No URL available for this job".
- [ ] **Absent: an error state.** `fetchJobs` failure (`:321-323`) leaves the previous list on screen with no banner; there is no `error` state variable anywhere in the file. Same for the three filter-list loads, the deep-link load, refill, both polls, and every mutation except `generateCv` copy-mode's `alert`.
- [ ] Absent: per-row pending/disabled state on save/skip/apply (optimistic only); absent: retry affordance anywhere.

### 1.5 Backend endpoints this screen depends on

- [ ] `GET /api/jobs`
- [ ] `GET /api/jobs/{id}`
- [ ] `PATCH /api/jobs/{id}`
- [ ] `POST /api/jobs/bulk-update`
- [ ] `GET /api/jobs/{id}/cached-page` (iframe)
- [ ] `GET /api/jobs/companies/list`
- [ ] `GET /api/jobs/sources/list`
- [ ] `GET /api/jobs/verdicts/list`
- [ ] `GET /api/monitor/in-flight`
- [ ] `GET /api/monitor/finished`
- [ ] `POST /api/analyze/{job_id}?depth=`
- [ ] `GET /api/resumes?is_base=true`
- [ ] `POST /api/resumes/copy`
- [ ] `POST /api/resumes/tailor`
- [ ] `GET /api/persona`
- [ ] `GET /api/settings`
- [ ] `PATCH /api/settings`

---

## 2. Application Board — route `/applications` (`frontend/src/components/ApplicationBoard.jsx`)

### 2.1 Route & storage

- [ ] Route `/applications` → `ApplicationBoard` — `App.jsx:174`.
- [ ] **No query params** are read or written on this screen.
- [ ] localStorage `appboard_company_filter` — const `COMPANY_STORAGE_KEY` `:24`; read `:31-36`, written `:48-50`. Stores an array of lowercased company keys plus the sentinel `__rejected_only__`. Both sides try/catch-swallowed.
- [ ] Fixed columns `applied / interview / offer / rejected` — `COLUMNS` `:7-12`. Legacy status remap (`screening→applied`, `phone_screen→interview`, `final_round→interview`) — `STATUS_REMAP` `:18-22`.

### 2.2 Data loads

- [ ] `GET /api/applications?limit=200` — `fetchApps` `:38-44`, on mount `:46`. **Hard cap of 200, no pagination** — applications beyond 200 never appear. Failure: `console.error` `:42`; `loading` is cleared regardless, so a failed load renders as an empty board.
- [ ] Also re-called after a drag failure `:64`, after `updateApp` `:71`, after `deleteApp` `:80`.
- [ ] **No polling on this screen.**

### 2.3 Interactive elements

- [ ] **Company filter chips** — `:169-174`, `toggleCompany` `:111-113`; keys are alias-collapsed lowercase (`company_canonical || company`, `:87-109`); persisted to localStorage.
- [ ] **"Other - Rejected (n)" chip** — `:175-180`; groups companies whose applications are all rejected; filter key `__rejected_only__`.
- [ ] **Clear filter button** — `:181-184`, shown only while a filter is active.
- [ ] **Filter auto-pruning** — `:122-127`; drops selected keys that no longer exist in the loaded data.
- [ ] **Drag and drop** — `DragDropContext`/`Droppable`/`Draggable` from `@hello-pangea/dnd`, `:210`, `:218`, `:234`. `onDragEnd` `:52-66`: no-op without a destination (`:53`); optimistic status update (`:58`); `PATCH /api/applications/{id}` `{status}` (`:61`). Failure: `console.error` + `fetchApps()` to revert (`:63-64`) — **the only revert-on-error path across all three screens**; still no user-visible message.
- [ ] **Card click** — `:240`, toggles the inline edit/detail section for that card.
- [ ] **Notes textarea (save on blur)** — `:261-267` → `updateApp` `:68-74` → `PATCH /api/applications/{id}` `{notes}`, then `fetchApps()` and closes the editor. Failure: `console.error` `:73` — **the typed note is lost from the UI on the next fetch with no warning**.
- [ ] **"Cached" button** — `:273-277`, opens the cached-page modal (only rendered when `app.job_id`). No API on click; the iframe does the fetch.
- [ ] **"Live" link** — `:279-282`, `<a target="_blank" href={app.url}>` (only when `app.url`).
- [ ] **Delete button** — `:283-287`; `window.confirm` gate (`:284`) → `deleteApp` `:76-82` → `DELETE /api/applications/{id}`, then `fetchApps()`. Failure: `console.error` `:81` — **card stays on the board, no message**.
- [ ] **Cached page modal** — `:189-208`; backdrop-click closes (`:190`), X button `:197-199`; iframe `src=/api/jobs/{job_id}/cached-page` (`:201-205`). Note: **no `sandbox` attribute here**, unlike the JobFeed iframes.
- [ ] **InfoTip** — `:156-161`, static help text.
- [ ] Card visual states (not controls): stale >7d yellow border `:230`, rejected red border `:231`, `days ago` label `:254-256`, `short_id` `:246`, `cv_version_used` chip `:251-253`.

### 2.4 States

- [ ] Loading — `:149`, full-screen "Loading applications..." (early return, so the header/filters do not render).
- [ ] Column-level empty — implicit: `min-h-[200px]` empty droppable (`:223`), count badge shows `0` (`:216`). **No "no applications" copy.**
- [ ] Filter bar hidden when there is nothing to filter — `:167`.
- [ ] **Absent: any error state.** No `error` variable; a failed `GET /api/applications` renders as an empty board indistinguishable from a genuinely empty pipeline.
- [ ] Absent: empty-board copy, retry button, per-card saving/pending indicator, drag-disabled state while a PATCH is in flight.

### 2.5 Backend endpoints this screen depends on

- [ ] `GET /api/applications?limit=200`
- [ ] `PATCH /api/applications/{id}`
- [ ] `DELETE /api/applications/{id}`
- [ ] `GET /api/jobs/{job_id}/cached-page` (iframe)

---

## 3. Company Manager — route `/companies` (`frontend/src/components/CompanyManager.jsx`)

### 3.1 Route & storage

- [ ] Route `/companies` → `CompanyManager` — `App.jsx:175`.
- [ ] **No query params** are read or written on this screen.
- [ ] localStorage `company_filter_tiers` — read `:147-149`, written `:179`. Array of `'1' | '2' | '3' | 'none'` strings.
- [ ] **NOT persisted**: add-form open state, edit modal, test-result modal, screenshot toggle.

### 3.2 Data loads

- [ ] `GET /api/companies` — `fetchCompanies` `:155-160`, on mount `:178`; re-called after save/add/toggle/bulk-activate. Failure: `console.error` `:159`.
- [ ] `GET /api/resumes?is_base=true` — `fetchResumes` `:162-167`, on mount `:178`. Failure: `console.error` `:166`.
- [ ] `GET /api/persona` — `fetchPersona` `:169-176`, on mount `:178`; sets `personaPopulated` from `resume_content`. Failure: sets `personaPopulated=false` (`:174`) — a failed load is indistinguishable from an empty persona.
- [ ] `GET /api/health/entities` — failing-scrape map for the warning triangles — `:132-136` (mount-only effect declared above the other state hooks). Failure: `.catch(() => {})` — **silently swallowed**, warnings just never appear.
- [ ] **No polling on this screen** — the test-scrape and run-scrape buttons do not poll for completion (see 3.3).

### 3.3 Interactive elements

Header:

- [ ] **Activate All** — `:281-285` → `bulkActivate(true)` `:235-242` → `POST /api/companies/bulk-activate` `{active: true, tiers?}` — **scoped to the current tier filter** when one is set (`:238`). Failure: `console.error` `:241`.
- [ ] **Deactivate All** — `:286-290` → `bulkActivate(false)`, same endpoint/behaviour.
- [ ] **Tier filter chips** (Tier 1 / 2 / 3 / Untiered) — `:291-300`; client-side filter `:264-266`; persisted; also scopes the two bulk buttons above.
- [ ] **Add Company toggle** — `:301-304`.
- [ ] **InfoTip** — `:273-278`.

Add-company form (`:308-441`, inline, not a modal):

- [ ] Company Name input `:314-316`; Aliases input (comma-separated) `:320-322`; Tier select `:326-332`; Scrape Interval (min) `:336-338`.
- [ ] Title Include Expression `:345-348`; Title Exclude Keywords `:353-356`.
- [ ] Score-Against-Resumes checkboxes `:364-376` + virtual **Persona** checkbox `:377-389` (only when `personaPopulated`).
- [ ] Auto Scoring select (off / light / full) `:396-402`.
- [ ] **Career Page URLs editor** (`UrlListEditor` `:78-119`): per-row ATS-type select `:102-105`, URL input `:106-108` (client-side ATS auto-detection on change via `detectAtsType` `:57-76`), remove-row X `:109-111`, "Add URL" `:114-116`.
- [ ] H-1B Slug `:417-420`; Wait-for Selector `:424-427`; Max Pages `:431-433`.
- [ ] **Save** — `:437` → `addCompany` `:203-228` → `POST /api/companies` with normalised payload (comma-strings split to arrays, editor rows flattened to a URL list via `editorToUrls` `:125-127`, interval/max_pages parsed). On success: closes form, resets state, `fetchCompanies()`. Failure: `console.error` `:227` — **the form stays open with the data still in it and no message; the user cannot tell it failed**.
- [ ] **Cancel** — `:438` (does not clear the entered data).

Table rows (`:790-893`):

- [ ] **Warning triangle** — `:794-798`, shown when the company id is in the `/health/entities` map; `title` carries the reason.
- [ ] **Aliases (Tags) icon** — `:800-804`, `title` lists the aliases.
- [ ] **Scrape URL links** — `:832-835`, `<a target="_blank">`, with an ATS-type chip from `detected_scrape_types` `:824-831`.
- [ ] **Active / Paused status button** — `:865-868` → `toggleActive` `:230-233` → `PATCH /api/companies/{id}` `{active: !active}` then `fetchCompanies()`. **No try/catch at all** (`:231`) — a failure rejects unhandled and the row silently keeps its old state.
- [ ] **Test Scrape (FlaskConical)** — `:879-882` → `runTestScrape` `:244-254` → `POST /api/companies/{id}/test-scrape`; result opens the test modal; spinner via `testing === c.id`. Failure **is** handled: `setTestResult({error})` `:251` renders inside the modal — the best error surface on any of the three screens.
- [ ] **Run Scrape (Play)** — `:883-886` → `runScrape` `:256-262` → `POST /api/scrape/company/{id}` (202 + background). Failure: `console.error` `:260`. The spinner is a **fixed 3000ms `setTimeout`** (`:261`), not tied to actual completion — no polling, no result feedback either way.
- [ ] **Edit (pencil)** — `:887-889`, opens the edit modal and seeds `editData.scrape_urls_editor`.
- [ ] **Absent: a delete-company control.** There is no UI path to `DELETE /api/companies/{id}` on this screen.

Edit modal (`:605-763`):

- [ ] Backdrop-click closes `:606`; header X `:610-612`; Cancel `:756-757`; **Save** `:758-759` → `saveEdit` `:181-201` → `PATCH /api/companies/{id}` then `fetchCompanies()`. Failure: `console.error` `:200` — **the modal is closed unconditionally by the click handler (`:758`) before the result is known, so a failed save looks identical to a successful one**.
- [ ] Fields (all uncontrolled `defaultValue` + `onChange` into `editData`): Name `:620-622`; Aliases `:626-628`; Tier `:636-642`; Scrape Interval `:646-649`; H-1B Slug `:653-656`; Score-Against-Resumes checkboxes `:665-678`; Persona checkbox `:679-692`; Auto Scoring select `:699-705`; URL editor `:712-715`; Title Include `:722-725`; Title Exclude `:730-733`; Wait-for Selector `:741-744`; Max Pages `:748-750`.
- [ ] Note: the resume checkboxes read `editData.selected_resume_ids || editModal.selected_resume_ids` on each toggle (`:670`, `:684`) — the pattern works but is order-sensitive; worth a regression check on multi-toggle.

Test-scrape result modal (`:444-602`):

- [ ] Backdrop-click closes `:445`; X `:458`; footer Close `:598`.
- [ ] **Show/Hide Screenshots toggle** — `:453-456` (only when screenshots present); images are inline base64 `:482-483`.
- [ ] Scrape info block (URLs scraped, include expression, exclude keywords) — `:467-474`.
- [ ] Pagination-debug block with expandable candidate `<details>` — `:490-511`.
- [ ] Results table (kept vs filtered-out rows, reason, per-row external link) — `:513-542`; separate "Rejected by validation" section `:544-569`.
- [ ] Footer summary counts (kept / keyword-filtered / extracted / validation-rejected) — `:578-597`.
- [ ] Error branch — `:462-463`, renders `testResult.error` in red.
- [ ] Empty branch — `:572-574`, "No job links found on this page."

### 3.4 States

- [ ] Empty (per row, no scrape URLs) — `:839` renders `-`.
- [ ] Empty (test-scrape results) — `:572-574`.
- [ ] Error (test-scrape only) — `:462-463`.
- [ ] Loading (per-button spinners only) — test `:881`, run `:885`.
- [ ] **Absent: a page-level loading state.** There is no `loading` variable; before `GET /api/companies` resolves the table renders with zero rows.
- [ ] **Absent: an empty state for the company table** — no companies and a failed load look identical (bare table head).
- [ ] **Absent: a page-level error state** for companies/resumes/persona/health failures.
- [ ] Absent: saving/pending indicator on Add, Edit-Save, and the Active/Paused toggle.

### 3.5 Backend endpoints this screen depends on

- [ ] `GET /api/companies`
- [ ] `POST /api/companies`
- [ ] `PATCH /api/companies/{id}`
- [ ] `POST /api/companies/bulk-activate`
- [ ] `POST /api/companies/{id}/test-scrape`
- [ ] `POST /api/scrape/company/{id}`
- [ ] `GET /api/resumes?is_base=true`
- [ ] `GET /api/persona`
- [ ] `GET /api/health/entities`

---

## Summary

- Controls catalogued: **~110** — Job Feed ~62 (incl. 6 keyboard shortcuts, a 3-button bulk bar, 2 undo/status toast systems, 3 modals), Application Board ~14 (incl. drag-and-drop across 4 columns and 1 modal), Company Manager ~34 (incl. 2 forms, 2 modals, a repeating URL-row editor).
- Endpoints used: **28 distinct method+path pairs** — Job Feed 17, Application Board 4, Company Manager 9 (`GET /api/resumes?is_base=true`, `GET /api/persona` and `GET /api/jobs/{id}/cached-page` are each shared by two screens).
- Uncaught / silently-failing paths: **every mutation on all three screens fails silently except two** — `POST /api/resumes/copy` (`alert`) and `POST /api/companies/{id}/test-scrape` (in-modal error). Two calls have **no `try`/`catch` whatsoever**: the Undo toast's `PATCH /api/jobs/{id}` (`JobFeed.jsx:723`) and the Active/Paused toggle's `PATCH /api/companies/{id}` (`CompanyManager.jsx:231`). Five loads are swallowed with a bare `catch {}` (`JobFeed.jsx:241/253/265/508`, `CompanyManager.jsx:134`). Only `ApplicationBoard.onDragEnd` (`:63-64`) reverts optimistic state on failure; none of the three screens has a page-level error state or a retry affordance.
