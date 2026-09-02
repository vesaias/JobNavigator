# v1 (legacy) screen inventory — Resumes / Cover Letters / Persona

Catalogue only — nothing here was run or modified. Source read in full:
`frontend/src/components/ResumeBuilder.jsx` (1587 L), `CoverLetterBuilder.jsx` (460 L),
`Persona.jsx` (457 L), `ResumeContentEditor.jsx` (391 L), plus `frontend/src/api.js`
and `frontend/src/App.jsx` (ClassicShell). `ModelCombobox.jsx` is **not** imported by any
of these three screens (Settings only) and is out of scope.

Shared plumbing that applies to all three screens:

- [ ] `api.js:3-7` — axios instance, `baseURL: '/api'`, `withCredentials: true` (jn_session cookie).
- [ ] `api.js:10-16` — request interceptor injects `X-API-Key` from `localStorage['jobnavigator_api_key']` when present.
- [ ] `api.js:19-27` — response interceptor fires the `jn:unauthorized` window event on any 401; `App.jsx:137-141` opens the LoginModal. Every 401 on these screens is handled globally, not per-call.
- [ ] `App.jsx:172-182` — all three routes live inside `ClassicShell` (sidebar + `HealthBanner` + `WhatsNewBanner` + `<Outlet/>`); no per-screen shell chrome.
- [ ] `App.jsx:106-117` — `localStorage['jobnavigator_dark_mode']` drives the `dark` class on `<html>` for all three screens.
- [ ] **Direct-anchor PDF links bypass the axios interceptor** (`ResumeBuilder.jsx:565`, `CoverLetterBuilder.jsx:221`): plain `<a href>` navigations carry the `jn_session` cookie only — never the `X-API-Key` header. Regression risk when the cookie is absent but the key is set.

---

## 1. ResumeBuilder — route `/resumes`

### 1.1 Route & storage

- [ ] Route `/resumes` → `ResumeBuilder` (`App.jsx:178`).
- [ ] Query param `?resume=<id>` — read in `fetchResumes` (`ResumeBuilder.jsx:309`); if the id is in the list it is auto-selected and the param stripped via `setSearchParams({}, {replace:true})` (`:314`). If the id is **not** found it silently falls back to `data[0]` (`:315-317`) — no "resume not found" feedback.
- [ ] No `?job=` param on this screen — the linked job comes from `resume.job_id` (`:367`).
- [ ] Outbound deep links this screen builds: `/cover-letters?resume=<id>&job=<id>` (`:783`) and `/?job=<id>` (`:796`).
- [ ] localStorage: **none written or read by this component**. Only the shared `jobnavigator_api_key` (`api.js:11`) and `jobnavigator_dark_mode` (`App.jsx:107`).
- [ ] Collapsible-section open/closed state is component-local `useState` (`:51`) — **not** persisted; every section resets to `defaultOpen` on remount.

### 1.2 Data loads

- [ ] `GET /api/resumes/templates` — on mount (`:174`); sets `TEMPLATES`, auto-selects `data[0].id` when no template is set (`:176`). `.catch(() => {})` — silent.
- [ ] `GET /api/resumes` — on mount via `fetchResumes()` (`:178`, impl `:307`); re-run after create/delete/tailor/copy/import and whenever a tailor run finishes (`:260`).
- [ ] `GET /api/persona` — on mount (`:291`); only used to decide whether the "Persona" option appears in the tailor modal (`personaPopulated`, `:292`).
- [ ] `GET /api/resumes/{id}` — on every `selectResume` (`:359`), loads `json_data` into the editor.
- [ ] `GET /api/jobs/{job_id}` — three call sites: enriching pending-tailor titles in the poll (`:203`), `refreshScoreFromJob` (`:332`), and building the Re-tailor modal's context label (`:931`).
- [ ] `GET /api/jobs?limit=50&sort_by=date&status=saved,applied` — `loadRecentJobs()`, called lazily when a tailor/copy/re-tailor modal opens (`:449`). Reads `data.jobs`.
- [ ] `GET /api/resumes/{id}/pdf?template=&format=` (`responseType:'arraybuffer'`) — live preview, **debounced 800 ms**, re-fires on `[previewKey, selectedId, template, pageFormat]` (`:572-588`). Blob URL revoked on replacement (`:579`).
- [ ] `GET /api/resumes/{id}/tracer-stats` — on `[selectedId, previewKey]`, skipped for base resumes (`:590-595`).

**Polling** — `GET /api/monitor/active` every **3000 ms** (`:186`, interval `:286`), one poller covering two job types:

- [ ] `job_type === 'tailor_resume'`, `scope_key = "<base_resume_id>:<job_id|freeform>"` (`:189-197`). Missing job titles are back-filled with `GET /api/jobs/{id}` (`:201-206`). A run disappearing ⇒ `fetchResumes()` (`:260`).
- [ ] `job_type === 'score_resume'`, `scope_key = "<job_id>:resume:<resume_id>"` (`:224-234`). Optimistic local entries (`_optimistic`) are carried for `OPTIMISTIC_GRACE_MS = 7000` (`:220`) then treated as finished; on completion for the selected resume it calls `refreshScoreFromJob(jobIdRef.current)` (`:278-280`).
- [ ] Poll body wrapped in `try {} catch {}` with an empty handler (`:282`) — network failures are invisible; the spinner state simply doesn't advance.

### 1.3 Interactive elements

**Top bar**

- [ ] Resume search input (`:715-722`) — local filter over `resumes`; opens the dropdown on focus/typing. No API call. Click-outside closes it via a document `mousedown` listener on `.resume-picker` (`:296-303`).
- [ ] Resume dropdown rows (`:750-757`) — `selectResume(r)` → `GET /api/resumes/{id}` (+ `GET /api/jobs/{id}` when tailored). Mutates `selectedId`/`editData`/`template`/`pageFormat`/`jobId`. Failure: `console.error` and the editor is filled with `EMPTY_DATA` (`:361-364`) — **a load failure looks like a blank resume**, and the subsequent debounced save can overwrite the real one.
- [ ] Delete (X) inside the search input (`:724-728`) — `deleteResume(selectedId)`, `confirm('Delete this resume?')` (`:434`) → `DELETE /api/resumes/{id}` (`:436`). Failure: `console.error` only (`:442`), no toast.
- [ ] "Download PDF" anchor (`:776-781`) — plain `<a target="_blank">` to `/api/resumes/{id}/pdf?template=&format=` (`:565`). No header auth (see shared note). No failure handling — a failed fetch renders as a broken tab.
- [ ] "Cover Letter" link (`:783-786`) — shown only when `jobId` is set; navigates to `/cover-letters?resume=&job=`. No API call.
- [ ] "Job ▾" menu toggle (`:790-793`), closed by the click-outside handler on `.job-menu` (`:299`).
- [ ] "Open in Job Feed" (`:796-800`) — `<a href="/?job={id}">`, full page navigation.
- [ ] "Open Job Link" (`:802-806`) — external `<a>`, rendered only when `jobUrl` was resolved.
- [ ] "Set as Applied" (`:808-820`) — `PATCH /api/jobs/{id}` `{status:'applied'}`. Mutates the job, not the resume. Failure: `console.error` only (`:816`) — **the button reverts to its idle label and looks successful**.
- [ ] "Saving..." indicator (`:825-829`) — presence-only; disappears whether the PATCH succeeded or failed.
- [ ] "Add Resume" (`:831-834`) — opens the modal, resets `newName`.

**Add Resume modal (`:856-894`)**

- [ ] Name input (`:866-868`), autofocus. Both actions disabled until non-empty.
- [ ] "Create from Scratch" (`:876-886`) — `POST /api/resumes` `{name, json_data: EMPTY_DATA}` then `fetchResumes()` + `selectResume`. **No try/catch (`:876-882`) — a failure is an unhandled promise rejection and the modal stays open with no message.** (The otherwise-identical `createResume` helper at `:421-431` does catch, but is unreferenced by the UI.)
- [ ] "Import Existing" (`:887-890`) — proxies a click to the hidden `<input type=file accept=".pdf">` (`:835`).
- [ ] Hidden PDF file input `onChange` (`:835-852`) — `POST /api/resumes/import-pdf` (multipart) → `POST /api/resumes` with the parsed `json_data` → `fetchResumes()` → select. Failure: `alert('PDF import failed: ' + detail)` (`:848`). Input value reset afterwards (`:851`).
- [ ] Modal close X (`:859-862`), disabled while `importing`.

**Actions bar — tailored resumes only (`:913-996`)**

- [ ] "Re-tailor" (`:915-941`) — sets `tailorMode='retailor'`, pre-selects base = `parent_id` or `'persona'`, pre-fills `tailorJobId`, calls `GET /api/jobs/{job_id}` for the label (`:931`; `catch` clears `jobSearch`, `:934`), `loadRecentJobs()`, opens the modal.
- [ ] "Review Changes" (`:943-946`) — rendered only when `parent_id` exists; `openDiffModal` → `GET /api/resumes/{parent_id}` (`:497`), stores `baseData`, clears `diffDecisions`, opens the diff modal. Failure: `console.error` (`:501`) — **the button appears dead: no modal, no message**.
- [ ] "Quick Score" (`:967-970`) / "Full Score" (`:971-974`) — both call `startScore(depth)` → `POST /api/resumes/{id}/score-check` `{depth:'light'|'full'}` (`:953`). Registers an optimistic `pendingScores` entry so the spinner appears before the next poll tick (`:956-959`). Both disable while any score run is active for the resume (`:967`,`:971`). Failure: `409` silently swallowed ("already running", `:961`); anything else `alert('Score failed: …')` (`:962`).
- [ ] Score-result chip + dismiss X (`:978-993`) — pure local state (`setScoreResult(null)`), no API call. Values derived in `refreshScoreFromJob` (`:329-348`) by diffing `job.cv_scores['Tailored']` against the max of the other numeric entries.

**Actions bar — base resumes only (`:997-1010`)**

- [ ] "Tailor" (`:999-1003`) — `tailorMode='tailor'`, `loadRecentJobs()`, opens the modal.
- [ ] "Copy for Job" (`:1004-1008`) — `tailorMode='copy'`, same modal.
- [ ] Tracer-stats strip (`:1011-1019`) — read-only click counts per token; `title` tooltip carries destination + last-clicked.

**Tailor / Copy / Re-tailor modal (`:1326-1414`)**

- [ ] Base `<select>` (retailor mode only, `:1344-1351`) — base resumes plus a "Persona" option when `personaPopulated`.
- [ ] "Tailor from Persona instead" checkbox (tailor mode only, `:1357-1359`).
- [ ] Job search input (`:1366-1372`) — local filter over `recentJobs`; typing clears the chosen `tailorJobId`.
- [ ] Job result rows (`:1381-1387`) — set `tailorJobId`, fill the search box with the label, clear the pasted JD.
- [ ] "Or Paste Job Description" textarea (`:1395-1397`) — rendered only when mode ≠ copy and no job is picked.
- [ ] Cancel (`:1401-1402`) — closes and resets retailor state; does **not** reset `tailorJobId`/`tailorJdText`.
- [ ] Generate / Copy / Re-tailor submit (`:1403-1410`) → `tailorForJob()` (`:454-491`). Copy mode → `POST /api/resumes/copy` `{base_resume_id, job_id}`, **synchronous**, then `fetchResumes()` + `selectResume(resp.data)` (`:467-469`). Tailor/retailor → `POST /api/resumes/tailor` `{base_resume_id, job_id | job_description}` — **202 + background run**, no body to select; the result surfaces only through the `/monitor/active` poll (`:471-478`). Failure: `alert('Tailoring failed: ' + detail)` (`:488`). Disabled while `tailoring` and while required inputs are missing (`:1403`).

**Template / format pickers (`:1022-1055`)**

- [ ] Template buttons (`:1025-1037`) — `changeTemplate(id)` → `triggerSave(editData, id, pageFormat)` → debounced `PATCH /api/resumes/{id}`.
- [ ] Page-format buttons, US Letter / A4 (`:1041-1053`) — `changeFormat(id)`, same path. `PAGE_FORMATS` is hard-coded (`:26-29`), unlike templates which come from the API.

**Save-on-change / save-on-blur**

- [ ] `triggerSave` (`:376-394`) — single 500 ms debounce → `PATCH /api/resumes/{id}` `{json_data, template, page_format}`; on success bumps `previewKey`, which re-fetches the preview PDF. Guarded by `dataLoaded` (`:377`) so loading a new resume can't write back stale data. Failure: `console.error` only (`:389`) — **silent data loss**.
- [ ] `updateField(path, value)` (`:402-419`) — dotted-path setter with a `__proto__`/`constructor`/`prototype` guard (`:400`,`:404`); fires `triggerSave` on **every keystroke** for every `FieldInput`-backed field.
- [ ] `FieldInput` Ctrl/Cmd-B bold toggle (`:71-91`) — wraps/unwraps the selection in `**`, restores the caret via `setTimeout`. Applies to every multiline field (summary, bullets).

**Section editors**

- [ ] Header → contact item ↑ (`:1065-1073`) / ↓ (`:1074-1082`) — swap + `triggerSave`, disabled at the ends.
- [ ] Header → contact `text` (`:1084-1095`), `url` (`:1096-1107`), `stub` (`:1109-1121`, only for non-`mailto:` URLs) — `onChange` updates local state, **`onBlur` triggers the save** (`:1093`,`:1105`,`:1119`).
- [ ] Header → contact delete (`:1123-1128`) — splice + `triggerSave`.
- [ ] Header → "Add Item" (`:1131-1138`) — **pushes a row but never calls `triggerSave`** (`:1135` sets state only). The empty row is not persisted until some other edit fires a save; a reload loses it.
- [ ] Summary textarea (`:1144-1150`) — `updateField('summary')`, saves per keystroke (debounced).
- [ ] Experience: "Add Experience" (`:1192-1194`), per-card delete (`:1157-1163`, no confirm), fields Company/Title/Location/Date/Description (`:1165-1170`), Bullets textarea joined/split on `\n` (`:1171-1178`). **No reorder control.**
- [ ] Experience → "LLM Suggested Bullets" panel (`:1179-1189`) — display only; accept/reject lives in the diff modal.
- [ ] Skills: ↑/↓ reorder (`:1202-1207`), category rename input (`:1209-1215`, **uncontrolled `defaultValue`**, commits `renameSkillKey` on blur, `:1213`), value input (`:1216-1222`, controlled, saves per keystroke), row delete (`:1223-1225`), "Add Skill Row" (`:1228-1230`, key auto-named `Skill N`).
- [ ] Education: add (`:1251-1253`), delete (`:1237-1243`), School/Location/Degree (`:1245-1248`). No reorder.
- [ ] Projects: add (`:1282-1284`), delete (`:1260-1266`), Name/URL/Description/Bullets (`:1268-1279`). No reorder.
- [ ] Publications: add (`:1302-1304`), delete (`:1291-1297`), Title/Description (`:1298-1299`). No reorder.
- [ ] Every `CollapsibleSection` header toggle (`:54-63`) — local only.

**Review Changes (diff) modal (`:1416-1584`)**

- [ ] "Accept All" (`:1423-1434`) / "Reject All" (`:1435-1446`) — bulk-set `diffDecisions` for summary, skills, every bullet and every suggested bullet.
- [ ] Summary Accept / Reject (`:1457-1464`), rendered only when the summary differs (`:1452`).
- [ ] Per-bullet ✓ / ✗ (`:1497-1504`) — only for bullets whose text differs from the base (`:1488`).
- [ ] Suggested-bullet ✓ / ✗ (`:1520-1527`).
- [ ] Skills Accept / Reject (`:1543-1550`), with base-vs-tailored side-by-side (`:1553-1566`).
- [ ] Cancel (`:1573-1576`) — discards decisions, no save.
- [ ] "Apply Decisions" (`:1577-1580`) → `applyDiffDecisions()` (`:506-552`): rejected summary/skills revert to base, rejected bullets revert per index, accepted suggested bullets are appended, and **all `suggested_bullets` are deleted regardless of decision** (`:546`), then `triggerSave` (`:550`). No API call of its own — persistence rides on the debounced PATCH.
- [ ] `InlineDiff` (`:7-22`) — `diffWords` word-level highlight; renders plain text when old === new.

### 1.4 States

Present:

- [ ] Loading — full-page "Loading..." spinner while the initial `/resumes` fetch is in flight (`:701-707`).
- [ ] Empty (no resume selected) — "No resume selected. Create one or import a PDF to get started." (`:896-899`).
- [ ] Empty (dropdown) — "No resumes found" (`:745-747`), suppressed while tailors are pending.
- [ ] Empty (tailor modal job list) — "No jobs found" (`:1379`).
- [ ] Empty (preview pane) — "Select a resume to preview" (`:1318-1320`).
- [ ] In-flight — "Saving..." chip (`:825-829`), per-resume tailoring banner (`:904-910`), inline "Tailoring for …" rows in the dropdown (`:760-768`), per-button "Scoring..." (`:969`,`:973`), "Importing PDF and extracting data..." (`:870-874`), modal button spinners (`:1405-1406`).

Absent:

- [ ] **No error state anywhere** — no error banner, no retry affordance, no toast. Failures are `console.error`, an `alert()`, or nothing.
- [ ] **PDF-preview failure is indistinguishable from "nothing selected"** — the catch sets `pdfPreviewUrl = null` (`:582-584`), which renders the same "Select a resume to preview" panel.
- [ ] No skeleton/placeholder while a *different* resume loads (`dataLoaded` gates saves, not rendering) — the previous resume's fields stay on screen until the new data lands.
- [ ] No "unsaved changes" guard on navigation while the 500 ms debounce is pending.

### 1.5 Backend endpoints this screen depends on

- [ ] `GET /api/resumes/templates`
- [ ] `GET /api/resumes`
- [ ] `POST /api/resumes`
- [ ] `GET /api/resumes/{id}`
- [ ] `PATCH /api/resumes/{id}`
- [ ] `DELETE /api/resumes/{id}`
- [ ] `GET /api/resumes/{id}/pdf`
- [ ] `GET /api/resumes/{id}/tracer-stats`
- [ ] `POST /api/resumes/{id}/score-check`
- [ ] `POST /api/resumes/copy`
- [ ] `POST /api/resumes/tailor`
- [ ] `POST /api/resumes/import-pdf`
- [ ] `GET /api/jobs`
- [ ] `GET /api/jobs/{id}`
- [ ] `PATCH /api/jobs/{id}`
- [ ] `GET /api/persona`
- [ ] `GET /api/monitor/active`

---

## 2. CoverLetterBuilder — route `/cover-letters`

### 2.1 Route & storage

- [ ] Route `/cover-letters` → `CoverLetterBuilder` (`App.jsx:179`).
- [ ] Query param `?resume=<id>` (`CoverLetterBuilder.jsx:110`) — pre-fills the generate panel's resume select; because the list is base-only, the id is additionally fetched with `GET /api/resumes/{id}` and prepended so the `<option>` exists (`:116-118`). Fetch failure is silent → the select shows only the empty option.
- [ ] Query param `?job=<id>` (`:109`) — pre-fills the target-job select. **Not validated against the loaded jobs list**; if the job isn't in the `status=saved` set, the select renders blank while `genJob` holds the id, so Generate can fire for an invisible selection.
- [ ] Query param `?cl=<id>` (`:149`) — selects that cover letter, then strips the param (`:152`). Not in the task brief, but present.
- [ ] localStorage: **none**.
- [ ] Section open/closed state is local `useState` (`:28`); "Generate New" defaults open only when there are zero letters (`:289`).

### 2.2 Data loads

All on mount, in one effect (`:89-120`):

- [ ] `GET /api/cover-letters` — `fetchLetters()` (`:147`); re-run after every completed generation (`:137`).
- [ ] `GET /api/cover-letters/templates` (`:91`) — `.catch(() => setTemplates([]))`.
- [ ] `GET /api/resumes?is_base=true` (`:93`) — base resumes only, silent catch.
- [ ] `GET /api/persona` (`:95`) — enables the "Persona (full profile)" option when `resume_content` is non-empty; silent catch.
- [ ] `GET /api/jobs?status=saved&limit=200` (`:99`) — reads `r.data.jobs`. The label says "saved/applied" (`:304`) but the query is **saved only**.
- [ ] `GET /api/settings` (`:100`) — pulls `cover_letter_voice_presets` (string or array, JSON-parsed, `:102-104`) and `cover_letter_default_voice` (`:105`). Parse failure → `setVoicePresets([])` (`:106`), leaving the Voice select empty.
- [ ] `GET /api/resumes/{id}` (`:116`) — only when `?resume=` was supplied.
- [ ] `GET /api/cover-letters/{id}` (`:171`) — on `selectLetter`.
- [ ] `GET /api/cover-letters/{id}/pdf` (`responseType:'arraybuffer'`, `:205`) — live preview, **debounced 800 ms**, re-fires on `[previewKey, selectedId, template, pageFormat]` (`:201-215`). Note `template`/`pageFormat` are in the dep array but are **not** sent as query params (unlike the resume PDF), so the preview relies on the PATCH having landed first.

**Polling** — `GET /api/monitor/active` every **3000 ms** (`:127`, interval `:141`):

- [ ] Filters `job_type === 'generate_cover_letter'` (`:128`) and keys **only on `run_id`** — no `scope_key` parsing, so it cannot tell which letter finished. Any run disappearing sets `generating=false` and calls `fetchLetters(true)`, which selects `letters[0]` (`:137`, `:154-155`) — a concurrent generation in another tab would steal the selection.
- [ ] Optimistic entries are pushed on POST (`:239`, `:255`) but have **no grace-window expiry** (contrast `OPTIMISTIC_GRACE_MS` in ResumeBuilder); they are replaced wholesale by the server list on the next tick.
- [ ] Poll body `try {} catch {}` empty (`:138`).

### 2.3 Interactive elements

**Letter picker**

- [ ] Picker toggle (`:270-274`) — local `pickerOpen`. **No click-outside handler** (ResumeBuilder has one); it closes only on selection (`:169`) or a second click.
- [ ] Letter rows (`:279-282`) — `selectLetter(c)` → `GET /api/cover-letters/{id}`; failure falls back to `EMPTY_DATA` with **no `console.error` and no message** (`:173`), so a load failure presents as a blank letter the debounced save can then persist.
- [ ] **No delete control** for cover letters on this screen, though `DELETE /api/cover-letters/{cl_id}` exists in the backend. No rename either — `name` is server-generated.

**Generate panel (`:289-330`)**

- [ ] "Your resume" select (`:292-297`) — `onPickResume` (`:225-229`); picking a tailored resume auto-selects its `job_id`. Includes a `"persona"` sentinel option when available (`:295`).
- [ ] "Target job" select (`:302-306`).
- [ ] "Voice" select (`:312-315`) — options from the `cover_letter_voice_presets` setting.
- [ ] "Length" select (`:319-322`) — hard-coded Concise / Standard / Detailed (`:11-15`).
- [ ] "Generate Cover Letter" (`:325-329`) → `doGenerate()` (`:231-245`): `POST /api/cover-letters/generate` `{resume_id, job_id, voice, length}` — **202 + `run_id`**, result arrives via the poll. Disabled without both resume and job, and while `generating`. Failure: `setGenerating(false)` + `alert(detail || 'Generation failed')` (`:240-244`).
- [ ] **`generating` clears only when the poll sees a run finish (`:137`) or on a POST error.** If the monitor never surfaces the run in a way the diff detects, the button stays disabled indefinitely with no timeout.

**Style section (`:335-357`)**

- [ ] Template select (`:339-342`) → `changeTemplate` → `triggerSave(editData, t, pageFormat)` (`:217`).
- [ ] Format select, US Letter / A4 (`:346-349`) → `changeFormat` (`:218`).
- [ ] "Regenerate (current voice/length)" (`:352-356`) → `regenerate()` (`:247-260`): re-POSTs `/api/cover-letters/generate` with the **selected letter's own** `resume_id`/`job_id` plus the panel's current voice/length. Guard: if the letter has no resume/job link it `alert`s and returns (`:249`). Failure: `alert(detail || 'Regeneration failed')` (`:258`).

**Recipient & Date section (`:360-365`)**

- [ ] Date (`:361`), Company (`:362`), Hiring manager (`:363`), Address (`:364`) — all via `update(mutator)` (`:193-198`), which deep-clones, mutates, and fires the debounced save on every keystroke.

**Letter section (`:368-395`)**

- [ ] Greeting field (`:369`).
- [ ] Per-paragraph move-up (`:375-376`) / move-down (`:377-378`), disabled at the ends.
- [ ] Per-paragraph delete (`:379-380`) — **no confirm**.
- [ ] Paragraph textarea (`:383-384`) — saves per keystroke (debounced 500 ms).
- [ ] "Add paragraph" (`:387-390`).
- [ ] Closing (`:392`) and Signature (`:393`) fields.

**Header section (`:398-428`)**

- [ ] Name field (`:399`).
- [ ] Contact item ↑ (`:406-407`) / ↓ (`:408-409`), disabled at the ends.
- [ ] Contact `text` (`:411-412`), `url` (`:413-414`), `stub` (`:416-418`, only for non-`mailto:` URLs) — these save **per keystroke** (`update`), unlike ResumeBuilder's blur-committed twins. Behavioural divergence worth pinning in the regression pass.
- [ ] Contact delete (`:420`).
- [ ] "Add contact" (`:424-427`) — unlike ResumeBuilder's equivalent, this one **does** persist (goes through `update`).

**Preview pane**

- [ ] "Download PDF" anchor (`:439-444`) → `/api/cover-letters/{id}/pdf` (`:221`). Same header-auth caveat as the resume download.
- [ ] "Preview" header with a `saving` spinner (`:436-438`).
- [ ] `triggerSave` (`:178-191`) — 500 ms debounce → `PATCH /api/cover-letters/{id}` `{json_data, template, page_format}`, bumps `previewKey` on success. Guarded by `dataLoaded && selectedId` (`:179`). Failure: `console.error` only (`:188`) — silent.

### 2.4 States

Present:

- [ ] Loading — spinner in the preview pane while the initial `/cover-letters` fetch is in flight (`:447-448`).
- [ ] Empty (nothing selected) — "Generate or select a cover letter to preview." (`:449-450`).
- [ ] Empty (picker) — "No cover letters yet — generate one below." (`:277`).
- [ ] In-flight — generate/regenerate button spinners (`:327`, `:354`), save spinner (`:437`).

Absent:

- [ ] **No error state**; failures are `alert()` (generate/regenerate only) or silent.
- [ ] **PDF failure renders an infinite spinner** — the catch sets `pdfPreviewUrl = null` (`:211`) and the final branch (`:453-455`) shows `<Loader2 className="animate-spin" />` with no timeout or message. Worse than ResumeBuilder's equivalent, which at least shows text.
- [ ] No empty state for the resume / job / voice selects when their fetches fail — they render with only the placeholder option.
- [ ] No delete or rename affordance for letters (see above).
- [ ] No "unsaved changes" guard while the debounce is pending.

### 2.5 Backend endpoints this screen depends on

- [ ] `GET /api/cover-letters`
- [ ] `GET /api/cover-letters/templates`
- [ ] `GET /api/cover-letters/{id}`
- [ ] `PATCH /api/cover-letters/{id}`
- [ ] `GET /api/cover-letters/{id}/pdf`
- [ ] `POST /api/cover-letters/generate`
- [ ] `GET /api/resumes` (with `?is_base=true`)
- [ ] `GET /api/resumes/{id}`
- [ ] `GET /api/jobs` (with `?status=saved&limit=200`)
- [ ] `GET /api/persona`
- [ ] `GET /api/settings`
- [ ] `GET /api/monitor/active`

---

## 3. Persona — route `/persona`

Includes the imported `ResumeContentEditor.jsx`, which owns the entire left column.

### 3.1 Route & storage

- [ ] Route `/persona` → `Persona` (`App.jsx:180`).
- [ ] **No query params read or written.**
- [ ] localStorage key `persona_open_sections` — read with a JSON-parse fallback to `["contact"]` on mount (`Persona.jsx:83-86`), rewritten on every change of `open` (`:97`). The seeded default `"contact"` no longer matches any rendered section key (the only right-column keys are `application_answers` and `qa_bank`), so a fresh visitor lands with **both right-column cards collapsed**.
- [ ] `ResumeContentEditor`'s per-section open state is local `useState` (`ResumeContentEditor.jsx:20`) and is **not** persisted — the left column always resets to defaults.

### 3.2 Data loads

- [ ] `GET /api/persona` — `fetchPersona()` on mount (`:91-96`). **No try/catch** — a failure is an unhandled rejection and `persona` stays `null`, leaving the page permanently on "Loading persona…" (`:144`).
- [ ] Every PATCH response replaces the whole local persona (`:110`, `:123`, `:138`).
- [ ] **No polling** on this screen.

### 3.3 Interactive elements

**Persistence primitives**

- [ ] `saveNode(key, value)` (`:107-113`) — immediate `PATCH /api/persona` `{[key]: value}`; used by the Q&A Bank blur-save. Failure: `alert('Failed to save {key}: …')` (`:112`).
- [ ] `saveNodeDebounced(key, value)` (`:118-128`) — optimistic local merge, **per-key 500 ms debounce timer** (`nodeDebounceRef`, `:89`), then `PATCH /api/persona`. Failure: `console.error` only (`:126`) — **silent data loss on every Application-Answers field**.
- [ ] `saveResumeContentDebounced(next)` (`:132-142`) — same shape for `resume_content`, single shared timer (`:88`). Failure: `console.error` only (`:140`) — **silent**.
- [ ] "Saved" flash toast (`:101-104`, rendered `:148-152`) — 1800 ms, fires on success only.

**Right column — Application Answers card**

- [ ] Card collapse toggle (`:196-204`), key `application_answers`, persisted in localStorage.
- [ ] Contact / Basics — 11 `TextField`s from `APPLICATION_ANSWERS_CONTACT_FIELDS` (`:39-51`, rendered `:382-385`): first_name, last_name, email, phone, city, state, country, linkedin, github, portfolio, current_company. Each writes the whole `contact` node via `setField` (`:368-373`) → `saveNodeDebounced('contact', …)`.
- [ ] Demographics — 8 `SelectField`s + 1 `CheckboxField` writing the `demographics` node (`:394-412`): gender, race_ethnicity, hispanic_latino, veteran_status, disability_status, age_range, transgender, sexual_orientation, decline_demographics. Choosing the blank "—" option passes `undefined` and `setField` **deletes the key** rather than storing `""` (`:311`, `:370`).
- [ ] Work Authorization — 4 `YesNoField`s (authorized_us, requires_sponsorship_now, requires_sponsorship_future, over_18) + 1 `SelectField` (work_auth_type), all writing `work_auth` (`:421-430`). `YesNoField` (`:322-341`) stores real booleans; "—" clears the key.
- [ ] Screening Defaults (`:439-452`) — `willing_to_relocate` / `willing_remote` (YesNo → `preferences`), `notice_period` / `earliest_start` / `referral_source` / `how_did_you_hear` (Text → `preferences`), `desired_salary` (Text → **`compensation` node**).
- [ ] **`TextField` uses `defaultValue` (`:295`) — uncontrolled.** Because every successful PATCH replaces `persona` from the server response (`:123`), a server-side normalisation of a text field is not reflected in the input until remount. `SelectField`/`YesNoField`/`CheckboxField` are controlled, so the column is internally inconsistent.
- [ ] **Each `setField` PATCHes the entire node.** Two fields in the same node edited within one 500 ms window are fine (the merge uses the latest `node` closure), but a field edited from a *stale* render can clobber a concurrent change to a sibling key.

**Right column — Q&A Bank card**

- [ ] Card collapse toggle (`:221-229`), key `qa_bank`; hint text at `:232`.
- [ ] Raw JSON textarea, 12 rows, `defaultValue = JSON.stringify(value, null, 2)` (`:273-281`). **Saves on blur only** (`:275`) via `saveNode('qa_bank', parsed)`. Invalid JSON → `alert('Invalid JSON: …')` (`:277`) and **the edit is silently discarded** (no re-focus, no marker). There is no add/remove/reorder UI — it is a hand-edited JSON blob.
- [ ] `RIGHT_SECTIONS` (`:9-34`) now contains only `qa_bank`; Contact, Work Authorization, Demographics, Compensation and Preferences cards were removed and folded into Application Answers (see the comment block).

**Left column — ResumeContentEditor (`Persona.jsx:170-173`)**

Every control below calls `onChange(next)` → `saveResumeContentDebounced` → debounced `PATCH /api/persona {resume_content}`. There are **no per-control API calls**.

- [ ] Header → Name (`ResumeContentEditor.jsx:181`).
- [ ] Header → contact item ↑ / ↓ (`:187-192`), disabled at the ends.
- [ ] Header → contact `text` (`:194-200`), `url` (`:201-207`), `stub` (`:209-216`, only for non-`mailto:` URLs) — **controlled, saving per keystroke** (`updateField`), unlike ResumeBuilder's blur-committed twins.
- [ ] Header → contact delete (`:218-220`); "Add Item" (`:223-225`) — this one **does** persist, unlike ResumeBuilder's (`ResumeBuilder.jsx:1131`).
- [ ] Summary textarea (`:231-237`), with the same Ctrl/Cmd-B bold toggle (`:40-59`).
- [ ] Experience: add (`:278-280`), per-card delete (`:244-249`), Company/Title/Location/Date/Description (`:251-256`), Bullets textarea joined/split on `\n` (`:257-264`). Read-only "LLM Suggested Bullets" panel (`:265-275`). No reorder.
- [ ] Skills: ↑ / ↓ (`:288-293`), category rename (`:295-301`, **uncontrolled `defaultValue`**, commits on blur), value (`:302-308`, controlled), delete (`:309-311`), "Add Skill Row" (`:314-316`).
- [ ] Education: add (`:336-338`), delete (`:323-328`), School/Location/Degree (`:330-333`). No reorder.
- [ ] Projects: add (`:366-368`), delete (`:345-350`), Name/URL/Description/Bullets (`:352-362`). No reorder.
- [ ] Publications: add (`:385-387`), delete (`:375-380`), Title/Description (`:381-382`). No reorder.
- [ ] `updateField` prototype-pollution guard (`:17`, `:97`) — silently returns, no warn (ResumeBuilder's equivalent logs, `ResumeBuilder.jsx:405`).
- [ ] Each `CollapsibleSection` toggle (`:23-32`) — local, non-persisted.

### 3.4 States

Present:

- [ ] Loading — "Loading persona…" text, no spinner (`:144`).
- [ ] Save confirmation — fixed "Saved" toast, 1800 ms (`:148-152`, `:101-104`).
- [ ] Per-column "Saves automatically" hint (`:168`, `:188`) and hover info tooltips (`:162-167`, `:182-187`).

Absent:

- [ ] **No error state and no retry.** A failed `GET /api/persona` is an unhandled rejection (`:92`) that leaves the page stuck on "Loading persona…" forever.
- [ ] **No empty state** — the singleton persona is assumed to exist; there is no "create your persona" affordance.
- [ ] No per-field save indicator or failure marker; the only signal is the global toast, whose *absence* is the sole clue that a debounced save failed.
- [ ] No dirty/unsaved guard on navigation while a 500 ms debounce is pending.
- [ ] No validation on any Application-Answers text field (email, phone, URLs are free text).
- [ ] Q&A Bank has no structured editor, no add/remove/reorder, and no `POST /api/persona/qa-bank` usage — that endpoint is exercised only by the Chrome extension.

### 3.5 Backend endpoints this screen depends on

- [ ] `GET /api/persona`
- [ ] `PATCH /api/persona`

---

## Cross-screen notes for the regression pass

- [ ] Three "save" idioms coexist: ResumeBuilder commits header-contact edits **on blur** but everything else per keystroke; CoverLetterBuilder and ResumeContentEditor commit **everything** per keystroke; Persona's Q&A Bank commits **on blur only**.
- [ ] Two monitor-poll designs: ResumeBuilder parses `scope_key` and ages out optimistic entries after 7 s; CoverLetterBuilder matches on `run_id` alone with no expiry.
- [ ] Both PDF preview effects use an 800 ms debounce, but only the resume one forwards `template`/`format` as query params.
- [ ] `GET /api/monitor/active` is polled every 3 s by both builders; the classic router only ever mounts one at a time, so the pollers do not overlap.
- [ ] Backend endpoints that exist but are **unused** by these v1 screens: `GET /api/resumes/{id}/preview`, `GET /api/resumes/shelf`, `POST /api/cover-letters`, `DELETE /api/cover-letters/{id}`, `GET /api/cover-letters/{id}/tracer-stats`, `POST /api/persona/qa-bank`.

---

**Summary**

Controls catalogued: 118 — 62 on ResumeBuilder (including 3 modals), 30 on CoverLetterBuilder, 26 on Persona (20 of them from the shared `ResumeContentEditor`).
Endpoints used: 24 distinct method+path pairs — 17 on ResumeBuilder, 12 on CoverLetterBuilder, 2 on Persona, with `GET /api/persona`, `GET /api/monitor/active`, `GET /api/jobs` and `GET /api/resumes/{id}` shared across screens.
Uncaught failure paths: 17 — the two hard ones are `Persona.fetchPersona` (`Persona.jsx:92`, no catch → permanent "Loading persona…") and the Add-Resume modal's "Create from Scratch" (`ResumeBuilder.jsx:876-882`, no catch → unhandled rejection); the rest are silent `console.error`-only saves (`ResumeBuilder.jsx:389`, `CoverLetterBuilder.jsx:188`, `Persona.jsx:126`,`:140`), silent load fallbacks that can overwrite good data (`ResumeBuilder.jsx:361`, `CoverLetterBuilder.jsx:173`), an empty `catch {}` on score refresh (`ResumeBuilder.jsx:347`), dead-button failures (`ResumeBuilder.jsx:501`,`:816`), and PDF-preview catches that degrade into a misleading empty state (`ResumeBuilder.jsx:582`) or an infinite spinner (`CoverLetterBuilder.jsx:211`).
