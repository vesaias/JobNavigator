# v1 (legacy) inventory — Searches / Settings / Stats

Catalogue only — no testing, no fixes. Source of truth read in full:
`frontend/src/components/SearchManager.jsx` (783 lines), `frontend/src/components/Settings.jsx` (1445 lines),
`frontend/src/components/Stats.jsx` (642 lines), plus shared `frontend/src/api.js` and `frontend/src/App.jsx`.

## Shared context (applies to all three screens)

- [ ] Axios instance `frontend/src/api.js:3` — `baseURL: '/api'`, `withCredentials: true` (sends `jn_session` cookie). Every path below is relative to `/api`.
- [ ] Request interceptor `api.js:10-16` — attaches `X-API-Key` from `localStorage['jobnavigator_api_key']` when non-empty.
- [ ] Response interceptor `api.js:19-27` — on HTTP 401 dispatches `window` CustomEvent `jn:unauthorized`; App shows the LoginModal (`App.jsx:137-141`).
- [ ] Shell: all three routes are children of `ClassicShell` (`App.jsx:48-103`, routes registered `App.jsx:172-182`). Shell renders `<HealthBanner/>` + `<WhatsNewBanner/>` above `<Outlet/>` (`App.jsx:97-99`).
- [ ] Shell localStorage: `jobnavigator_dark_mode` (`App.jsx:107,116`); shell also POSTs `/auth/set-session` on boot (`App.jsx:131`). sessionStorage `jn:welcome` (`App.jsx:111`).
- [ ] Shell sidebar state `sidebarOpen` is component-local, NOT persisted (`App.jsx:49`).

---

## 1. Searches — `SearchManager.jsx` (route `/searches`)

### 1.1 Route & storage
- [ ] Route `/searches` → `SearchManager` (`App.jsx:176`); no route params, no `useSearchParams`.
- [ ] Query params read: **none** (no deep-link support on this screen).
- [ ] localStorage keys: **none** (all state is component-local; contrast CompanyManager which persists filters).
- [ ] Unmount guard ref `mountedRef` (`SearchManager.jsx:57-58`) for the long test poll.

### 1.2 Data loads
- [ ] On mount — `GET /health/entities` (`SearchManager.jsx:46`), builds `downMap` (search id → failing-scrape reason) for the amber warning triangle. `.catch(() => {})` — silent swallow (`:48`).
- [ ] On mount — `GET /searches` via `fetchSearches()` (`SearchManager.jsx:62`, effect at `:67`). Catch logs to console only (`:64`).
- [ ] Refetch triggers: after save (`:112`), after delete (`:120`), after toggle active (`:127`), after run (`:135`).
- [ ] Polling: **only** inside the test flow (see 1.4). No background polling of the search list; no auto-refresh of `downMap`.

### 1.3 Extension-search gating (`EXTENSION_MODES`)
- [ ] `const EXTENSION_MODES = ['linkedin_extension', 'extension']` (`SearchManager.jsx:17`); helper `isExtensionMode(mode)` (`:18`).
- [ ] Mode field becomes a **disabled text input** showing "LinkedIn Extension (passive capture)" / "Extension (manual Save-to-Feed)" (`:208-210`) instead of the `<select>` (`:212-227`).
- [ ] Green info callout replaces mode-specific fields (`:230-237`).
- [ ] Scrape-parameter fields (Location / Remote / Job Type / Hours Old / Results Wanted) hidden for extension modes (`:331`).
- [ ] "Run interval (min)" input hidden for extension modes (`:452-460`); Auto Scoring select stays visible (`:442-451`).
- [ ] Test (flask) button hidden (`:753-758`), Run (play) button hidden (`:759-764`), Delete button hidden (`:768-772`). Edit button always shown (`:765-767`).
- [ ] Card badge: `linkedin_extension` → cyan "Extension LI"; `extension` → sky "Extension" (`:708-713`).

### 1.4 Interactive elements
- [ ] **"New Search" button** (`:478-481`) — sets `editing='new'` + `editData = DEFAULT_FORM` (`:31-40`). No API call.
- [ ] **Save (check icon), new card** (`:680-682`) → `saveSearch()` (`:90`) → `POST /searches` (`:106`). Mutates: creates Search row. On error: `console.error` only, form stays open, **no user-facing error** (`:113`).
- [ ] **Save (check icon), edit card** (`:733-735`) → `saveSearch()` → `PATCH /searches/{editing}` (`:108`). Same no-catch-UI behaviour.
- [ ] **Cancel (X), new + edit** (`:683-685`, `:736-738`) — clears `editing`/`editData`. No API call, no confirm on unsaved changes.
- [ ] **Edit (pencil)** (`:765-767`) → `startEdit(s)` (`:69-88`) — hydrates `editData`, joins array fields to comma strings. No API call.
- [ ] **Delete (trash)** (`:769-771`) → `deleteSearch(id)` (`:116`) → `window.confirm('Delete this search config?')` (`:117`) → `DELETE /searches/{id}` (`:119`). Failure: console only (`:121`).
- [ ] **Active/Paused pill** (`:742-745`) → `toggleActive(id, active)` (`:124`) → `PATCH /searches/{id}` body `{active: !active}` (`:126`). Failure: console only (no optimistic revert needed — refetch drives UI).
- [ ] **Run Now (play)** (`:760-763`) → `runSearch(id)` (`:131`) → `POST /searches/{id}/run` (`:134`), then `fetchSearches()`. Spinner is `running === id` only for the duration of the request — the backend job is async, so the spinner clears before the scrape finishes. Failure: console only (`:136`).
- [ ] **Test Search (flask)** (`:754-757`) → `testSearch(id)` (`:140`). Disabled unless mode ∈ `keyword, levels_fyi, linkedin_personal, jobright, freehire` (`:754`).
- [ ] Test flow — `POST /searches/{id}/test` with `timeout: 30000` (`:145`). If `status === 202 && data.run_id` → **poll loop**: `GET /searches/test-result/{run_id}` every 3s, `timeout: 10000`, `MAX_POLLS = 100` (≈5 min) (`:152-175`). 200 → result; 202 → keep polling; 404 → `{error:'Test run expired or not found'}` (`:167-170`); other errors swallowed and retried (`:172`). Exhaustion → `{error:'Test timed out after 5 minutes — check Stats > Run History'}` (`:175`). Sync (keyword) path sets the result directly (`:178`).
- [ ] Test flow error branch (`:180-183`) — surfaces `e.response.data.detail || e.message` into the modal. This is the **only** user-visible error path on the screen.
- [ ] **Test Results modal** (`:485-671`) — backdrop click closes (`:486`), inner click stops propagation (`:487`), X closes (`:493`), footer Close closes (`:667`).
- [ ] **Test filter tabs** All / Kept / Filtered (`:581-588`) → `setTestFilter`, applied in `getFilteredJobs()` (`:187-192`). Counts: All = `jobs.length`, Kept = `after_filter`, Filtered = `raw_count - after_filter`.
- [ ] **"Top companies" `<details>` disclosure** in the breakdown row (`:563-574`) — native, no state.
- [ ] **Per-row external link** (`:637-639`) — `target="_blank" rel="noopener noreferrer"` to `j.url`.
- [ ] Edit form fields (all local `setEd` state, persisted only on Save): Name (`:203`), Mode select (`:212`, resets `sources` per mode `:215-217`), LinkedIn Personal collection checkboxes Recommended/Top Applicant (`:243`, `:251`), Jobright Search Term (`:265`) / Results Wanted (`:270`) / Min Score (`:275`) / Require salary (`:280`), keyword Search Term (`:289`), freehire Search Term (`:296`) / URL (`:302`) / Results Wanted (`:308`), Direct/Levels.fyi URL (`:317`), Levels.fyi Max Pages (`:327`), Location (`:335`), Remote select (`:340`), Job Type select (`:349`), Hours Old (`:358`), Results Wanted (`:363`), Sources checkboxes ×5 (`:376`, list at `:6-12`), Title Include (`:409`), Title Exclude (`:415`), Company Include (`:423`), Company Exclude (`:429`), Exclude active companies checkbox (`:436`), Auto Scoring select off/light/full (`:444`), Run interval minutes (`:455`).
- [ ] **InfoTip** header help (`:470-476`) — shared `components/InfoTip` component, no API.

### 1.5 States
- [ ] Empty state present: "No search configs yet. Click \"New Search\" to create one." (`:693`) — shown only when `editing !== 'new'`.
- [ ] Empty test results: "No results returned." (`:646-648`).
- [ ] Loading (per-row): flask + play buttons swap to `Loader2` spinner (`:756`, `:762`).
- [ ] Error state present: test-result modal error panel (`:496-497`).
- [ ] **Absent**: no initial page-level loading skeleton — the list renders as empty-state before `GET /searches` resolves (`:692` has no `loading` guard).
- [ ] **Absent**: no error UI for failed list load, save, delete, toggle, or run — all four are `console.error` only (`:64, :113, :121, :128, :136`).
- [ ] **Absent**: no toast/confirmation on successful save or run.
- [ ] **Absent**: `downMap` failure is fully silent (`:48`) — warning triangles simply never appear.

### 1.6 Backend endpoints this screen depends on
- [ ] `GET /api/health/entities`
- [ ] `GET /api/searches`
- [ ] `POST /api/searches`
- [ ] `PATCH /api/searches/{id}`
- [ ] `DELETE /api/searches/{id}`
- [ ] `POST /api/searches/{id}/run`
- [ ] `POST /api/searches/{id}/test`
- [ ] `GET /api/searches/test-result/{run_id}`

---

## 2. Settings — `Settings.jsx` (route `/settings`)

### 2.1 Route & storage
- [ ] Route `/settings` → `SettingsPage` (`App.jsx:177`); no route params.
- [ ] Query params read: **none**.
- [ ] localStorage `settings_tab` — active tab, read at `Settings.jsx:14`, written in `switchTab` (`:15`). Values: `general` | `ai` | `accounts`.
- [ ] localStorage `jobnavigator_api_key` — **written** by `saveApiKey()` (`:73`). Read by the axios interceptor (`api.js:11`), not by this component.

### 2.2 Data loads
- [ ] On mount — `GET /settings` via `fetchAll()` (`:41`, effect `:47`). Catch: console only (`:43`); `loading` still cleared (`:44`) so a failed load renders an empty form.
- [ ] On mount — `GET /resumes?is_base=true` (`:50`) → default-resume dropdown options. Silent catch (`:52`).
- [ ] On mount — `GET /persona` (`:53`) → `personaPopulated` when `resume_content` is non-empty (`:55`); adds the "Persona" option. Catch sets `false` (`:57`).
- [ ] On demand — `GET /llm/models?provider={p}` via `fetchProviderModels()` (`:31`), fired on custom-provider change (`:329`) and on ModelCombobox focus (`:342`). Cached per provider, only for `openrouter, openai, claude_api, claude_code` (`:19, :26-27`). Error stored per provider and rendered inline (`:34`, `:360`).
- [ ] Writes — every field goes through `saveSetting(key, value)` → `PATCH /settings` with a single-key body (`:62`). Optimistic-ish: functional state update after the await (`:65`), toast "Setting saved" for 2s (`:66-67`). Catch: console only (`:68`) — **the toast does not fire on failure but the field keeps the typed value**.
- [ ] Writes — `updatePhrases(key, value)` (`:94-99`) splits a textarea on `\n`, trims, drops empties, then `saveSetting`.
- [ ] Polling: **none** on this screen.

### 2.3 Settings keys bound (flat list, by tab)

**Tab: General**
- [ ] `default_resume_id` (`:138-139`)
- [ ] `scrape_interval_minutes` (`:169-171`)
- [ ] `email_check_interval_minutes` (`:176-178`)
- [ ] `job_archive_after_days` (`:183-185`)
- [ ] `auto_reject_after_days` (`:190-192`)
- [ ] `backup_cron` (`:201-203`)
- [ ] `digest_cron` (`:209-211`)
- [ ] `h1b_cron` (`:217-219`)
- [ ] `cleanup_cron` (`:225-227`)
- [ ] `reject_cron` (`:233-235`)
- [ ] `tracer_links_enabled` (`:1080-1081`)
- [ ] `tracer_links_base_url` (`:1089-1091`)
- [ ] `tracer_links_url_style` (`:1097-1098`)
- [ ] `company_exclude_global` (`:1129-1130`, newline-split array)
- [ ] `title_exclude_global` (`:1140-1141`, newline-split array)
- [ ] `body_exclusion_phrases` (`:1151-1152`, newline-split array)
- [ ] `dedup_tracking_params` (`:1177-1178`, newline-split array)
- [ ] `proxy_url` (`:1419-1421`)
- [ ] `dashboard_api_key` (`:1428-1429`, saved by the explicit Save button `:1435`)

**Tab: AI**
- [ ] `llm_provider` (`:270-271`)
- [ ] `llm_model` (`:282-283`)
- [ ] `llm_api_key` (`:294-296`)
- [ ] `llm_models_list` (`:319`, `:377` — array of `{provider, model, label, custom}`)
- [ ] `scoring_llm_provider` (`:419-420`)
- [ ] `scoring_llm_model` (`:432-433`)
- [ ] `scoring_llm_api_key` (`:445-447`)
- [ ] `llm_fallback_provider` (`:471-472`)
- [ ] `llm_fallback_model` (`:484-485`)
- [ ] `llm_fallback_api_key` (`:498-500`)
- [ ] `scoring_max_concurrent` (`:516-518`)
- [ ] `prompt_caching_enabled` (`:525-526`, written as string `'true'`/`'false'`)
- [ ] `scoring_default_depth` (`:535-536`)
- [ ] `on_save_action` (`:547-548`)
- [ ] `scoring_rubric` (`:561-562`)
- [ ] `scoring_output_light` (`:571-572`)
- [ ] `scoring_output_full` (`:581-582`)
- [ ] `cv_tailor_llm_provider` (`:607-608`)
- [ ] `cv_tailor_llm_model` (`:627-628`)
- [ ] `cv_tailor_llm_api_key` (`:643-645`)
- [ ] `cv_tailor_prompt` (`:659-660`)
- [ ] `persona_tailor_prompt` (`:673-674`)
- [ ] `tailor_auto_quick_score` (`:685-691`)
- [ ] `cover_letter_llm_provider` (`:720-721`)
- [ ] `cover_letter_llm_model` (`:740-741`)
- [ ] `cover_letter_llm_api_key` (`:756-758`)
- [ ] `cover_letter_default_voice` (`:771-772`)
- [ ] `cover_letter_voice_presets` (`:783-784`, JSON.parse on blur)
- [ ] `cover_letter_prompt` (`:795-796`)
- [ ] `autofill_llm_provider` (`:821-822`)
- [ ] `autofill_llm_model` (`:841-842`)
- [ ] `autofill_default_length` (`:855-857`)
- [ ] `autofill_prompt` (`:867-868`)
- [ ] `prep_ask` (`:887-888`)
- [ ] `autofill_field_patterns` (`:903-904`, JSON.parse on blur)
- [ ] `autofill_option_synonyms` (`:915-916`, JSON.parse on blur)
- [ ] `email_llm_enabled` (`:942-943`)
- [ ] `email_llm_confidence_threshold` (`:951-953`)
- [ ] `email_llm_provider` (`:962-963`)
- [ ] `email_llm_model` (`:982-983`)
- [ ] `email_llm_api_key` (`:998-1000`)
- [ ] `email_llm_prompt` (`:1014-1015`)
- [ ] `email_gmail_query_subjects` (`:1029-1030`, newline-split array)
- [ ] `email_gmail_query_senders` (`:1039-1040`, newline-split array)
- [ ] `email_gmail_query_exclusions` (`:1049-1050`, newline-split array)

**Tab: Accounts**
- [ ] `telegram_enabled` (`:1204-1205`)
- [ ] `telegram_chat_id` (`:1213-1215`)
- [ ] `fit_score_threshold` (`:1220-1222`)
- [ ] `telegram_webhook_secret` (`:1246` — **read-only display**, masked as `••••••`; never PATCHed from here, rotated via endpoint)
- [ ] `jobright_email` (`:1296-1298`)
- [ ] `jobright_password` (`:1305-1307`)
- [ ] `linkedin_email` (`:1338-1340`)
- [ ] `linkedin_password` (`:1347-1349`)
- [ ] `linkedin_mock_email` (`:1379-1381`)
- [ ] `linkedin_mock_password` (`:1388-1390`)

Total distinct keys bound: **62** PATCHable + 1 read-only display (`telegram_webhook_secret`).

### 2.4 Manual trigger buttons
- [ ] **"Send Test Telegram"** (`:1227-1232`) → `triggerAction('/telegram/test')` (`:83`) → `POST /telegram/test`. Status machine `running → done → ''` after 3s (`:84-88`); failure sets `'error'` (`:90`) but the label only renders `Sending…` / `Sent!` / default — **the error state has no visible label**.
- [ ] **"Rotate" (webhook secret)** (`:1248-1258`) → `window.confirm` (`:1250`) → `POST /telegram/rotate-webhook-secret` (`:1251`) → shows the new secret via `window.prompt` (`:1253`). **No catch — a rejected promise is unhandled.**
- [ ] **"Register" (webhook)** (`:1259-1268`) → `window.prompt` for the public base URL (`:1261`) → `POST /telegram/register-webhook` body `{public_url}` (`:1263`) → `alert()` with ok/failure text (`:1264`). **No catch.**
- [ ] Note for the regression pass: v1 Settings has **no** other manual triggers. The scrape / email / h1b / analyze / cleanup / backup / digest buttons live on **Stats → Schedules** (`Play` and `RefreshCw` are imported at `Settings.jsx:4` but unused — dead imports).

### 2.5 Other interactive controls
- [ ] **Tab bar** General / AI / Accounts (`:114-127`) → `switchTab` writes `settings_tab`.
- [ ] **Password reveal toggles** (`togglePw`, `:16`) on: `llm_api_key` (`:298`), `scoring_llm_api_key` (`:449`), `llm_fallback_api_key` (`:502`), `cv_tailor_llm_api_key` (`:647`), `cover_letter_llm_api_key` (`:760`), `email_llm_api_key` (`:1002`), `jobright_password` (`:1309`), `linkedin_password` (`:1351`), `linkedin_mock_password` (`:1392`), `dashboard_api_key` (`:1431`).
- [ ] **Custom-model provider select** (`:328-336`) — triggers `fetchProviderModels`.
- [ ] **ModelCombobox / plain input** (`:338-352`) — searchable for the 4 searchable providers, plain text otherwise; Enter triggers `addModel` (`:350`).
- [ ] **"Add" button** (`:354`) → `addModel()` (`:315-323`) → dedups, then `saveSetting('llm_models_list', updated)` → `PATCH /settings`.
- [ ] **Model chip "×" delete** (`:374-378`) → `window.confirm` then `saveSetting('llm_models_list', filtered)`.
- [ ] **"Save" (Dashboard API Key)** (`:1435-1436`) → `saveApiKey()` (`:71-81`): writes localStorage, `PATCH /settings`, then `POST /auth/set-session` `{api_key}` (`:77`) to refresh the httpOnly cookie. Cookie refresh failure → `console.warn` only (`:79`).
- [ ] **JSON textareas** — `cover_letter_voice_presets` (`:784`), `autofill_field_patterns` (`:904`), `autofill_option_synonyms` (`:916`): each wraps `JSON.parse` in try/catch and `alert()`s on invalid JSON; the invalid text stays in the textarea and is **not** saved.

### 2.6 States
- [ ] Loading present: full-page "Loading settings..." while `loading` (`:101`).
- [ ] Success feedback present: floating "Setting saved" toast, 2s (`:106-110`, set at `:66`).
- [ ] Validation feedback present: `alert()` on invalid JSON in the three JSON textareas (`:784`, `:904`, `:916`).
- [ ] Model-catalog states present: loading / error / count line (`:356-363`).
- [ ] **Absent**: no error banner when `GET /settings` fails — the page renders with every field empty and every blur would then overwrite real values (`:43-44`).
- [ ] **Absent**: no per-field save-failure indication; `saveSetting` catch is console-only (`:68`).
- [ ] **Absent**: no catch on the two Telegram webhook buttons (`:1251`, `:1263`).
- [ ] **Absent**: `triggerStatus === 'error'` has no rendered label (`:1231` covers only running/done/default).
- [ ] **Absent**: no empty state for the resume dropdown when no base resumes exist (renders just the placeholder option).
- [ ] Mixed control pattern to watch in regression: some fields are **controlled + onBlur save**, others are **uncontrolled `defaultValue` + onBlur save** (all the big textareas: `scoring_rubric` `:561`, `scoring_output_*` `:571`/`:581`, `cv_tailor_prompt` `:659`, `persona_tailor_prompt` `:673`, `cover_letter_*` `:771`/`:783`/`:795`, `autofill_prompt` `:867`, `prep_ask` `:887`, `autofill_field_patterns` `:903`, `autofill_option_synonyms` `:915`, `email_llm_prompt` `:1014`, all Gmail-query and Global-Exclude textareas, `dedup_tracking_params` `:1177`). Uncontrolled ones do **not** re-render after an external change.

### 2.7 Backend endpoints this screen depends on
- [ ] `GET /api/settings`
- [ ] `PATCH /api/settings`
- [ ] `GET /api/resumes?is_base=true`
- [ ] `GET /api/persona`
- [ ] `GET /api/llm/models?provider={provider}`
- [ ] `POST /api/auth/set-session`
- [ ] `POST /api/telegram/test`
- [ ] `POST /api/telegram/rotate-webhook-secret`
- [ ] `POST /api/telegram/register-webhook`

---

## 3. Stats — `Stats.jsx` (route `/stats`)

### 3.1 Route & storage
- [ ] Route `/stats` → `Stats` (`App.jsx:181`); no route params.
- [ ] Query params read: **none**.
- [ ] localStorage keys: **none** — the activity filters, the LLM-cost day window, the flow view toggle, and the cost-table sort are all component-local and reset on navigation (`:202`, `:204-205`, `:85-87`).
- [ ] Dark-mode read: `MutationObserver` on `<html>` class (`:209-214`) to recolour Recharts axes/tooltips.

### 3.2 Data loads
- [ ] On mount (`useEffect :338`) fires five loaders in sequence:
  - [ ] `GET /stats` (`:233`, inside `fetchData` `:230`) → stat cards + Application Flow bar chart. Catch console-only (`:236`).
  - [ ] `GET /scheduler/jobs` (`:223`, `fetchSchedulerJobs`) → Schedules table; also sets `hasRunningRef` (`:226`). Catch console-only (`:227`).
  - [ ] `GET /monitor/history?limit=30` (`:243`, `fetchRunHistory`) → Run History table. Catch console-only (`:245`).
  - [ ] `GET /stats/timeline?days=30` (`:250`, `fetchTimeline`) → Jobs Timeline line chart. Catch console-only (`:252`).
  - [ ] `GET /stats/score-distribution` (`:257`, `fetchScoreDistribution`) → Score Distribution bar chart. Catch console-only (`:259`).
  - [ ] `GET /stats/sankey` (`:264`, `fetchSankey`) → Application Flow "Flow" view. Catch console-only (`:294`).
- [ ] On `[activityType, activityCompany]` change (`useEffect :339`) — `GET /activity-log?limit=50[&type=][&company=]` (`:299-302`). Catch console-only (`:304`). **No debounce** on the free-text company input — one request per keystroke.
- [ ] Nested component `LlmCostPanel` — on mount and on `days` change: `GET /stats/llm-costs?days={days}` (`:90`, effect `:89-93`), initial `days = 0` (all time). Catch substitutes a zeroed object (`:92`) — the only fetch on this screen with a graceful fallback.
- [ ] **Polling** (`:326-336`): self-rescheduling `setTimeout` loop, first tick 3s after mount (`:334`), then **3s while any scheduler job is running, 10s when idle** (`:330`). Each tick calls `fetchSchedulerJobs()` + `fetchRunHistory()` (`:328-329`). Cleared on unmount (`:335`). Note: the timeline / score-distribution / sankey / stats / activity-log calls are **not** polled.

### 3.3 Charts and their endpoints
- [ ] **Stat cards** ×5 — Total Jobs / New Jobs / Saved Jobs / Total Applications / Active Applications (`:343-354`, rendered `:366-374`). Source: `GET /stats`. "Active" is derived client-side as `total_applications - (rejected + ghosted + withdrawn)` (`:349-353`).
- [ ] **Application Flow — Bar view** (`:402-419`), horizontal bar of `application_statuses.{applied, interview, offer, rejected}`. Source: `GET /stats`. Default view (`flowView='bar'` `:202`).
- [ ] **Application Flow — Sankey view** (`:392-400`), custom `SankeyNode` renderer (`:43-55`), node colours `SANKEY_NODE_COLORS` (`:35-41`). Source: `GET /stats/sankey`. Client-side DAG guard (`:266-292`): drops self-edges and backward edges by `STATUS_RANK` (`:270-273`) to avoid a Recharts infinite-recursion crash; if no forward edges survive, `sankeyData` stays null and the toggle never appears (`:280`).
- [ ] **Bar/Flow toggle** (`:383-390`) — only rendered when `sankeyData` is non-null.
- [ ] **Score Distribution** bar chart (`:427-439`), per-bucket colours `SCORE_COLORS` (`:15`). Source: `GET /stats/score-distribution`.
- [ ] **New Jobs (Last 30 Days)** line chart (`:451-461`), dual Y axes: `total` (left, indigo) + `applied` (right, green). Source: `GET /stats/timeline?days=30`.
- [ ] **LLM Costs panel** (`:126-189`) — totals row (spend / calls / avg per call `:145-162`) + per-purpose table. Source: `GET /stats/llm-costs?days=N`.

### 3.4 Interactive elements
- [ ] **"Refresh" button** (`:360-362`) → re-runs `fetchData()` + `fetchRunHistory()` + `fetchActivityLog()`. **Does not** refresh timeline, score distribution, or sankey. No API of its own; no failure handling beyond the individual loaders' console-only catches.
- [ ] **Flow view "Bar"** (`:385-386`) / **"Flow"** (`:387-388`) → `setFlowView`, local only.
- [ ] **Schedules table → "Manual Run" button** (`:514-525`) → `triggerJob(job.id, job.trigger_url)` (`:307`) → `POST {job.trigger_url}` (`:312`), then `fetchSchedulerJobs()`. Disabled while `job.running || triggering.has(job.id)` (`:516`); optimistic spinner cleared after 4s (`:321`). Failure: **409 → `alert(detail || 'Job is already running')` (`:316`); every other error → console only (`:318`)**. Rows without a `trigger_url` render a dash (`:527`).
- [ ] Trigger URLs served by `GET /scheduler/jobs` (`backend/main.py:783-790`, `:854`, `:879`) — the buttons therefore POST to: `/scrape/run-all`, `/email/check-now`, `/telegram/digest`, `/h1b/refresh`, `/db/backup`, `/db/cleanup`, `/auto-reject/run`, plus per-entity `/scrape/search/{id}` and `/scrape/company/{id}` rows.
- [ ] **Run History table** (`:539-586`) — read-only; columns Time (CET) / Job ID / Trigger / Status / Duration / Result-or-Error. Trigger + status pill colours from `TRIGGER_COLORS` (`:57-60`) and `STATUS_COLORS` (`:62-66`); `running` gets an extra pulse (`:569`). Error text shown red and truncated with a `title` tooltip (`:575-579`).
- [ ] **Activity Log — Type filter select** (`:593-601`) — options: All Types, `scrape`, `h1b`, `cv_score`, `email`, `telegram`. Refetches `/activity-log`.
- [ ] **Activity Log — Company text input** (`:602-604`) — refetches `/activity-log` on every keystroke (no debounce, `:339`).
- [ ] **LLM cost day-window select** (`:134-143`) — 1d / 7d / 30d / All time (`days=0`); refetches `/stats/llm-costs`.
- [ ] **LLM cost table sortable headers** ×6 — purpose / provider / model / calls / cost_usd / cache_hit_ratio (`:116-123`, `:167-172`) → `toggleSort` (`:97-104`), client-side sort (`:106-113`). No API.
- [ ] **InfoTip** on the LLM cost header (`:130-132`) — shared component, no API.
- [ ] **`decodeCron()`** (`:17-33`) — renders raw cron into "Daily at 03:00" style text for the Schedules table (`:496`), with the raw expression as the `title`.

### 3.5 States
- [ ] Loading present: full-page "Loading stats..." gated on the `/stats` + `/scheduler/jobs` pair (`:341`, cleared `:238`).
- [ ] Empty states present: Schedules "No scheduled jobs" (`:489`), Run History "No runs yet" (`:557`), Activity Log "No activity yet" (`:619`), Score Distribution "No scored jobs yet" (`:441`), Timeline "No timeline data available" (`:463`).
- [ ] Running state present: per-row pulse pill with elapsed seconds (`:499-503`) and spinner in the Manual Run button (`:523`).
- [ ] Partial-error handling present: `LlmCostPanel` falls back to a zeroed object (`:92`); the panel renders nothing at all while `data` is null (`:95`).
- [ ] Error surfaced to the user: only the 409 `alert()` on Manual Run (`:316`).
- [ ] **Absent**: no error UI for any of the six mount fetches — all `console.error` only (`:227, :236, :245, :252, :259, :294`); a failed `/stats` leaves the loading spinner replaced by a page with **no** stat cards and **no** charts (the `{stats && ...}` guard at `:377` silently drops the whole chart row).
- [ ] **Absent**: no error UI for a failed `/activity-log` (`:304`) — the table just keeps its previous rows.
- [ ] **Absent**: no empty/error state for the LLM cost panel — a zeroed result renders `$0.0000 / 0` with no table and no message (`:163`).
- [ ] **Absent**: no error surface for a failed Manual Run other than 409 (`:318`).
- [ ] **Absent**: no per-chart loading skeletons — charts flash their empty-state text before their fetch resolves.
- [ ] **Absent**: no debounce on the activity-log company filter (`:339`).

### 3.6 Backend endpoints this screen depends on
- [ ] `GET /api/stats`
- [ ] `GET /api/stats/timeline?days=30`
- [ ] `GET /api/stats/score-distribution`
- [ ] `GET /api/stats/sankey`
- [ ] `GET /api/stats/llm-costs?days={n}`
- [ ] `GET /api/scheduler/jobs`
- [ ] `GET /api/monitor/history?limit=30`
- [ ] `GET /api/activity-log?limit=50[&type][&company]`
- [ ] `POST /api/scrape/run-all` (via `trigger_url`)
- [ ] `POST /api/email/check-now` (via `trigger_url`)
- [ ] `POST /api/telegram/digest` (via `trigger_url`)
- [ ] `POST /api/h1b/refresh` (via `trigger_url`)
- [ ] `POST /api/db/backup` (via `trigger_url`)
- [ ] `POST /api/db/cleanup` (via `trigger_url`)
- [ ] `POST /api/auto-reject/run` (via `trigger_url`)
- [ ] `POST /api/scrape/search/{id}` (via per-search `trigger_url`)
- [ ] `POST /api/scrape/company/{id}` (via per-company `trigger_url`)

---

## Summary

- Controls catalogued: **131** — Searches 39, Settings 76 (62 bound setting fields + 3 manual/webhook buttons + 11 other controls), Stats 16 (plus 9 dynamic Manual Run trigger targets).
- Endpoints used: **33 distinct** method+path — Searches 8, Settings 9, Stats 17 (one, `POST /api/auth/set-session`, is shared between Settings and the app shell).
- Settings keys bound in v1: **63** — 19 General, 33 AI, 11 Accounts (of which `telegram_webhook_secret` is read-only display and the other 62 are PATCHed to `/api/settings`).
