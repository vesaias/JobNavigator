# v2 Settings — screen inventory

Source: `frontend/src/v2/Settings.jsx` (757 lines, read in full). Backend: `backend/api/routes_settings.py`, `backend/seed.py`, `backend/scheduler.py`. Companion: `settings-matrix.md` (one row per seeded key).

Line refs below are `Settings.jsx:NNN` unless another file is named.

---

## 1. Routes & params

- [x] Route `/v2/settings` — registered `frontend/src/App.jsx:163` as child of `<Route path="/v2" element={<V2App/>}>` (`App.jsx:152`). No URL params, no `?query`, no `#hash` navigation.
- [x] v1 `/settings` still mounts `components/Settings.jsx` (`App.jsx:177`); rail link "← Classic UI" (`V2App.jsx:136`) goes to `/`, not `/settings`.
- [x] Rail item "Settings" in group "You" (`V2App.jsx:31`), no count, no warn badge.
- [x] Sections are NOT tabs: single scrolling page with 15 sections and an anchor rail (`:376-385`). Anchor rail `jump(id)` (`:349-356`) sets `active` state and scrolls `[data-sec="sec-{id}"]` into view inside `scrollRef` (`:388`). No scroll-spy — `active` only changes on click; scrolling manually never moves the rail highlight.
- [x] Default `active` = `'models'` (`:108`). Not persisted anywhere; reloading always lands at top with "Models" highlighted.
- [x] Section ids / groups (`:210-338`): `models`(AI) · `scoring` · `tailoring` · `letters` · `autofill` · `prep` · `emailclass` · `scheduler`(PIPELINE) · `exclude` · `dedup` · `notifications`(INTEGRATIONS) · `tracer` · `jobright` · `linkedin` · `advanced`(SYSTEM). Group label rendered only on the first section of each group (`:379`).
- [x] Search box (`:369`) filters sections client-side (`:342-345`): matches section title OR any row `label + help` (case-insensitive). While `q` is non-empty the rail highlight is suppressed (`:381-382`) and `jump()` clears the query (`:350`).
- [x] Search hides rows? NO — a matching section renders ALL its rows (`:390-401`), filtering is per-section only.
- [x] localStorage written by this screen: `jobnavigator_api_key` (`:570`, on "Save key"). Read by `api.js:11` as `X-API-Key` header.
- [x] localStorage read by the shell: `jobnavigator_v2_rail` (`V2App.jsx:48,55`), `jobnavigator_dark_mode` (`V2App.jsx:52,54`). v1's `settings_tab` (`components/Settings.jsx:14-15`) is NOT used by v2.
- [x] `sessionStorage`/cookies: `POST /auth/set-session` sets httpOnly `jn_session` cookie (`main.py:184-207`), `api.js:6` sends it via `withCredentials`.
- [x] Colophon links (`:414-417`): `/docs` (new tab; `/docs` bypasses API-key auth per `main.py`) and `https://github.com/vesaias/JobNavigator`.

## 2. Data loads

- [x] Mount (`:133-138`): `GET /settings` + `GET /settings/defaults` via `Promise.all` (`:122`). `/settings/defaults` failure is swallowed to `{}` (`:122`) — Reset-to-default then resets to empty string (see §7).
- [x] `GET /settings` (`routes_settings.py:20-35`): every row; secrets → `""` if unset else `"••••••"`; other values pass through `json.loads` so `"60"`→`60` (int), `"true"`→`true` (bool), JSON lists/dicts → arrays/objects, crons/prompts stay strings.
- [x] `GET /settings/defaults` (`routes_settings.py:97-102`): `{key: raw_seed_string}` — lists/dicts arrive as JSON **strings** (not parsed), which matters for Reset (§7).
- [!] `load()` failure (`:130`): `console.error` only; `S` stays `null` → page renders an empty `div` forever (`:347`). No retry, no message.  — SET-06
- [x] Mount: `GET /resumes?is_base=true` → `resumes` for the Default résumé dropdown (`:135`); failure silent.
- [x] Mount: `GET /persona` → `personaAvailable = resume_content has keys` (`:136`); failure silent. Adds the "Persona" option to Default résumé (`:198`).
- [x] Mount: `GET /linkedin/session` → `li` (`:137`); failure silent (row shows "Unknown", `:606`).
- [x] `load()` re-run after webhook-secret rotate (`:304`).
- [x] Override-row initial open state derived from `S[`${base}_provider`]` truthiness for the 6 bases (`:126-129`).
- [!] Save path: every control → `save(key, value)` (`:145-149`) → optimistic `setS` then `PATCH /settings {key: value}`. One PATCH per control change; no batching. PATCH response `{updated, warnings}` (`routes_settings.py:94`) — `warnings` are ignored by v2.  — SET-08
- [x] PATCH side effects (`routes_settings.py:57-92`): `configure_scheduler()` for the 7 timing keys; `reset_scoring_semaphore()` for `scoring_max_concurrent`; `reset_tailoring_semaphore()` for `tailoring_max_concurrent`; `reload_tracking_params()` for `dedup_tracking_params`. Each wrapped in try/except → appended to `warnings`.  — SET-27
- [!] PATCH skips any value exactly equal to `"••••••"` (`routes_settings.py:44-46`) so an echoed mask never overwrites a secret. Unknown keys are created (`:51-54`) — no allow-list.  — SET-01
- [~] Polling: only `LinkedInRow` after "Refresh cookie" — `GET /linkedin/session` every 2500 ms (`:587-593`) until `phase ∉ {running, awaiting_pin}`; interval cleared on unmount (`:581`). No `/monitor/active` polling for any trigger.  — LinkedIn session is idle/stale — the refresh poll never starts without a real LinkedIn login
- [x] `ModelsModal`: `GET /llm/models?provider=X` on open and on every provider change when `X ∈ SEARCHABLE` (`:686-695`). Backend caches 1 h per provider (`routes_llm.py:19-20`); 400 when no key for openai/claude (`routes_llm.py:117`); 502 when provider rejects key / unreachable (`:135-143`). Cancelled via `dead` flag on unmount.
- [x] Toast: this screen does NOT use `Toast.jsx` (`useToasts`/`ToastStack` never imported). "Toast" here = header subtitle text swap (`:363-365`) for 2200 ms (`:140-143`).

## 3. Interactive elements

### 3a. Shared control mechanics

- [!] `TextBox` (`:66-88`): local state; **saves on blur only if `local !== value`** (`:77`). No debounce, no Enter-to-save, no Escape-revert, no validation. `secret` → shows `••••••` until focus or "show" click (`:70,76`); once revealed the editable text is the literal stored value — which after `GET` is the mask string `"••••••"` itself (`:68`), so the user must clear it before typing.  — SET-01, SET-02
- [x] `Select` (`:34-63`): custom dropdown, saves **immediately on pick** (`:54`). Closes on any document click (`:36-41`). Shows `placeholder || 'Select…'` when value not in options (`:47`). Menu max-height 320, z-index 40.
- [x] `Toggle` (`:90-99`): saves immediately; switch rows send the strings `'true'`/`'false'` (`:443`).
- [!] `EditModal` (`:627-672`): textarea, **600 ms debounce per keystroke** (`:634-645`). `list` → split on `\n`, trim, drop blanks → array. `json` → `JSON.parse` else `err` and nothing saved. plain → raw string. Pending timer cleared on unmount (`:632`).  — SET-25
- [x] `ActionBtn` (`:542-550`): states `''` / `running` (spinner + "Running…") / `done` ("Done ✓", 2600 ms then reset `:187`). Guard: ignores clicks while `trig[id]` truthy (`:182`). Keyed by row **label** (`:504`).
- [x] `runAction` (`:181-193`): `await fn()`; on throw → `console.error`, reset state, flash `e.response.data.detail || 'That did not work'` (bad).
- [x] `flash(msg, bad)` (`:140-143`): header line turns `--accent` (ok) or `--bad`; auto-clears after 2200 ms.
- [x] Info "i" button (`:521-528`): toggles an inline explainer panel (`:533-535`) for rows with `info`; only one open at a time (`info === r.label`).
- [x] Rows with `offHelp` swap the help text when the switch is off (`:531`).

### 3b. Header

- [x] Search input "Search settings…" — `:369-370`, `onChange → setQuery`. No API call. Empty result state `:405`.
- [x] Status line — `:363-365`: idle "Saves automatically · everything stays on this machine" / flash message.

### 3c. Anchor rail (15 anchors)

- [x] Rail anchor × 15 — `:380-382`, `onClick → jump(id)`, no API. Group headers AI / PIPELINE / INTEGRATIONS / SYSTEM (`:379`).

### 3d. Section "Models" (AI) — 9 rows (`:211-225`)

- [x] **Primary provider · model** (`kind: pair`, `:212-214`, rendered `:445-453`): provider `Select` (5 options `PROVIDERS :6-12`) → `save('llm_provider', v)`; model `Select` (options = `llm_models_list` filtered by provider, `:167-171`) → `save('llm_model', v)`, placeholder "pick model…". Info panel. Success flash "Saved"; failure flash "Could not save — try again".
- [x] **API key** (`B`, `:215`): `TextBox secret mono w340` → `save('llm_api_key')`. **Hidden** when `llm_provider ∈ KEYLESS {claude_code, ollama, ''}` (`:215, :17, :399`). Stored key not cleared when hidden.
- [x] **Scoring** override (`LLM`, `:216`, rendered `:454-476`): Override `Toggle` → `setOvr`; turning OFF saves `scoring_llm_provider=''` AND `scoring_llm_model=''` (two PATCHes, `:471`) but NOT `scoring_llm_api_key`. When ON: provider `Select` → `save('scoring_llm_provider')`; model `Select` (options from override provider, else Primary's, `:460`) → `save('scoring_llm_model')`; API-key `TextBox secret w150` (`:463`) → `save('scoring_llm_api_key')`, only when provider is non-keyless. When OFF: "inherits Primary" pill (`:466`).
- [x] **Scoring fallback** override (`LLM`, `:217-218`, base `llm_fallback`) → keys `llm_fallback_provider / llm_fallback_model / llm_fallback_api_key`. Same mechanics. Info panel.
- [x] **Tailoring** override (`LLM`, `:219`, base `cv_tailor_llm`) → `cv_tailor_llm_provider / _model / _api_key`.
- [x] **Cover letters** override (`LLM`, `:220`, base `cover_letter_llm`) → `cover_letter_llm_provider / _model / _api_key`.
- [x] **Autofill** override (`LLM`, `:221`, base `autofill_llm`) → `autofill_llm_provider / _model / _api_key`.
- [x] **Email classification** override (`LLM`, `:222`, base `email_llm`) → `email_llm_provider / _model / _api_key`.
- [x] **Model catalog** (`kind: models`, `:223-224`, rendered `:489-499`): summary "N models · N seeded · N added by you" + **Manage…** `ActionBtn` → `setModelsOpen(true)`. Info panel.

### 3e. Section "Scoring behavior" — 8 rows (`:226-239`)

- [x] **Default résumé** (`SEL`, `:227`): options `['', '(all bases + Persona)']` + `['persona','Persona']` (only if persona has resume_content) + base resumes `[id, name]` (`:197-199`) → `save('default_resume_id')`. w260.
- [x] **Max parallel jobs** (`B mono w135`, `:228`) → `save('scoring_max_concurrent')` (string; no numeric validation). PATCH resets scoring semaphore.
- [x] **Default depth** (`SEL`, `:229-231`): light/full, `dflt 'light'` → `save('scoring_default_depth')`. Info.
- [x] **On save action** (`SEL`, `:232-233`): off/light/full, `dflt 'off'` → `save('on_save_action')`.
- [x] **Prompt caching** (`SW`, `:234-235`, `dflt true`) → `save('prompt_caching_enabled', 'true'|'false')`. offHelp + info.
- [x] **Scoring rubric** (`E`, `:236`) → Edit modal (plain) → `save('scoring_rubric')`. Preview = whole text single-line ellipsis (`:481,484`).
- [x] **Light output schema** (`E`, `:237`) → `save('scoring_output_light')` (plain text, NOT json-validated).
- [x] **Full output schema** (`E`, `:238`) → `save('scoring_output_full')` (plain text).

### 3f. Section "Tailoring" — 4 rows (`:240-246`)

- [x] **Résumé tailoring prompt** (`E`, `:241`) → `save('cv_tailor_prompt')`.
- [x] **Persona tailoring prompt** (`E`, `:242`) → `save('persona_tailor_prompt')`.
- [x] **Max parallel tailors** (`B mono w135`, `:243`) → `save('tailoring_max_concurrent')`. PATCH resets tailoring semaphore.
- [x] **Auto-score after tailoring** (`SEL`, `:244-245`): off/light/full, `dflt 'light'` → `save('tailor_auto_quick_score')`.

### 3g. Section "Cover letters" — 3 rows (`:247-251`)

- [x] **Default voice** (`SEL`, `:248`): options built from `cover_letter_voice_presets` ids (`:204-208`); a stored id missing from presets is appended as `"<id> — not in presets"` → `save('cover_letter_default_voice')`.
- [x] **Voice presets** (`E json`, `:249`) → Edit modal JSON → `save('cover_letter_voice_presets', parsedArray)`. Invalid JSON → red border + "Not valid JSON — nothing saved yet".
- [x] **Cover letter prompt** (`E`, `:250`) → `save('cover_letter_prompt')`.

### 3h. Section "Autofill" — 4 rows (`:252-257`)

- [x] **Default answer length** (`B mono w135`, `:253`) → `save('autofill_default_length')`.
- [x] **Autofill prompt** (`E`, `:254`) → `save('autofill_prompt')`.
- [x] **Field patterns** (`E json`, `:255`) → `save('autofill_field_patterns', obj)`.
- [x] **Option synonyms** (`E json`, `:256`) → `save('autofill_option_synonyms', obj)`.

### 3i. Section "Interview prep" — 2 rows (`:258-263`)

- [x] **"What I need from you" section** (`E`, `:259`) → `save('prep_ask')`.
- [x] **Include by default** (`SEL`, `:260-262`): 5 fixed combos of `resume,posting,notes`, `dflt 'resume,posting,notes'` → `save('prep_include')`. Any other stored combination renders as "Select…".

### 3j. Section "Email classification" — 6 rows (`:264-271`)

- [x] **LLM classification** (`SW`, `:265`, no dflt → off) → `save('email_llm_enabled')`. offHelp.
- [x] **Confidence threshold** (`B mono w135`, `:266`) → `save('email_llm_confidence_threshold')`.
- [x] **Classification prompt** (`E`, `:267`) → `save('email_llm_prompt')`.
- [x] **Gmail query · subjects** (`E list`, `:268`) → `save('email_gmail_query_subjects', [..])`. Preview joins with " · " (`:479`).
- [x] **Gmail query · senders** (`E list`, `:269`) → `save('email_gmail_query_senders', [..])`.
- [x] **Gmail query · exclusions** (`E list`, `:270`) → `save('email_gmail_query_exclusions', [..])`.

### 3k. Section "Scheduler" (PIPELINE) — 9 rows (`:272-283`)

- [x] **Scrape all companies** (`B mono w135`, `:273`) → `save('scrape_interval_minutes')` → PATCH triggers `configure_scheduler()`.
- [x] **Email check** (`B`, `:274`) → `save('email_check_interval_minutes')` → reconfigure.
- [x] **Cleanup after** (`B`, `:275`) → `save('job_archive_after_days')` (NOT a timing key — no reconfigure; read per cleanup run).
- [x] **Auto-reject threshold** (`B`, `:276-277`) → `save('auto_reject_after_days')` (read per reject run). Info.
- [x] **Auto-reject · cron** (`B`, `:278`) → `save('reject_cron')` → reconfigure.
- [x] **DB backup · cron** (`B`, `:279`, note TAB indentation) → `save('backup_cron')` → reconfigure.
- [x] **Telegram digest · cron** (`B`, `:280`) → `save('digest_cron')` → reconfigure.
- [x] **H-1B refresh · cron** (`B`, `:281`) → `save('h1b_cron')` → reconfigure.
- [x] **Job cleanup · cron** (`B`, `:282`, trailing whitespace) → `save('cleanup_cron')` → reconfigure.
- [~] Cron validation: none client-side; server `_add_cron_job` (`scheduler.py:39-55`) logs a warning and silently skips a bad cron; the PATCH `warnings` array only carries exceptions from `configure_scheduler` as a whole. Non-numeric interval → `int()` raises → warning in PATCH (`routes_settings.py:63-67`), but the same `int()` runs unguarded at startup (`main.py:52` → `scheduler.py:29-30`).  — writing a bad interval risks the user's backend boot — read only

### 3l. Section "Global exclude" — 3 rows (`:284-288`)

- [x] **Body phrases** (`E list`, `:285`) → `save('body_exclusion_phrases', [..])`.
- [x] **Title exclude** (`E list`, `:286`) → `save('title_exclude_global', [..])`.
- [x] **Company exclude** (`E list`, `:287`) → `save('company_exclude_global', [..])`.

### 3m. Section "Dedup tracking params" — 1 row (`:289-291`)

- [x] **Stripped params** (`E list`, `:290`) → `save('dedup_tracking_params', [..])` → PATCH calls `reload_tracking_params()`.

### 3n. Section "Notifications" (INTEGRATIONS) — 6 rows (`:292-312`)

- [x] **Telegram** (`SW`, `:293`) → `save('telegram_enabled')`. offHelp.
- [x] **Chat ID** (`B mono w135`, `:294`) → `save('telegram_chat_id')`.
- [x] **Score threshold** (`B mono w135`, `:295`) → `save('fit_score_threshold')`.
- [x] **Test** → button "Send test message" (`BT`, `:296`): `POST /telegram/test` → 202 `{run_id}` (`main.py:758-773`) → "Done ✓" immediately (does not await the background send; a failed send is invisible here). 409 if already running → flash detail.
- [x] **Webhook secret** → button "Rotate" (`button`, `:297-305`): preview "Set (hidden — rotate to view)" / "Set" / "Not set"; `window.confirm` → `POST /telegram/rotate-webhook-secret` → `window.prompt` shows `data.webhook_secret` once → `load()`. Info. No PATCH.
- [!] **Register webhook** → button "Register…" (`BT`, `:306-311`): `window.prompt` for public URL → `POST /telegram/register-webhook {public_url}` → flash `data.ok === false ? (data.description || 'Registration failed') : 'Webhook registered'`. Backend 400 if not https (`main.py:740-742`) → runAction catch → flash detail. Local failure dicts use key `error`, not `description` (`telegram.py:82,85,102`) → UI shows generic "Registration failed".  — SET-07

### 3o. Section "Tracer links" — 3 rows (`:313-320`)

- [x] **Rewrite links** (`SW`, `:314-315`) → `save('tracer_links_enabled')`. Info + offHelp.
- [x] **Base URL** (`B mono w260`, placeholder `https://yourdomain.com`, `:316`) → `save('tracer_links_base_url')`.
- [x] **URL style** (`SEL`, `:317-319`): path / param / path_jobid / param_jobid, `dflt 'path'` → `save('tracer_links_url_style')`.

### 3p. Section "Jobright.ai" — 2 rows (`:321-324`)

- [x] **Email** (`B w260`, `:322`) → `save('jobright_email')`.
- [x] **Password** (`B secret w260`, `:323`) → `save('jobright_password')`.
- [x] (`jobright_session_id` — seeded, redacted, auto-managed — has NO row.)

### 3q. Section "LinkedIn" — 5 rows (`:325-332`)

- [x] **Personal email** (`B w260`, `:326`) → `save('linkedin_email')`.
- [x] **Personal password** (`B secret w260`, `:327`) → `save('linkedin_password')`.
- [x] **Session cookie** (`kind: linkedin`, `:328`, rendered `LinkedInRow :578-624`): status text coloured by `li.status` (ok→`--good`, stale→`--warn`, else `--muted`, `:599`); phase text (`:604-606`). **Refresh cookie** `ActionBtn` (shown when phase ≠ awaiting_pin, `:621`; state running while busy) → `POST /linkedin/session/refresh` (202; `routes_linkedin.py:64-76`) then 2.5 s poll. Failure → flash detail / "Could not start the refresh" (`:594`).
- [!] **Submit PIN** (`:614-618`, shown only when `phase === 'awaiting_pin'`): PIN `input` (`:611`, `inputMode numeric`) + `ActionBtn` → `POST /linkedin/session/pin {pin}` → `{ok:false, detail}` → flash bad; `{ok:true}` → clear + flash "PIN sent". **No try/catch** — a network/401/500 error is an unhandled rejection with no UI feedback.  — SET-10
- [x] **Mock account email** (`B w260`, `:329-330`) → `save('linkedin_mock_email')`. Info.
- [x] **Mock account password** (`B secret w260`, `:331`) → `save('linkedin_mock_password')`.

### 3r. Section "Advanced" (SYSTEM) — 3 rows (`:333-337`)

- [x] **Proxy URL** (`B mono w340`, placeholder `socks5://127.0.0.1:9050`, `:334`) → `save('proxy_url')`.
- [!] **Dashboard API key** (`kind: apikey`, `:335`, rendered `ApiKeyRow :555-576`): password-type input (never shows stored value), placeholder "Set — type a new key to replace it" / "No key — the dashboard is open" (`:563`), show/hide (`:565`). **Save key** `ActionBtn` (`:567-573`): empty → flash "Type the new key first"; else `await save('dashboard_api_key', key)` → `localStorage.jobnavigator_api_key = key` → `POST /auth/set-session {api_key}` (best-effort, `:571`) → clear input → flash "Key saved". Because `save()` swallows its own PATCH failure (`:148`), the localStorage write, cookie refresh and "Key saved" flash all still happen when the PATCH failed → local key ≠ server key → 401 lockout on the next request.  — SET-03
- [x] **DB backup** → button "Run backup" (`BT`, `:336`): `POST /db/backup` → 202 `{run_id}` (`main.py:567-612`) → "Done ✓" on the 202 (no run polling, no link to Stats › Run history). 409 → flash detail.

### 3s. Edit modal (19 rows open it) — controls (`:627-672`)

- [x] Scrim click / ✕ (`:648,:653`) / **Done** (`:667`) all just `onClose`; none flushes the pending 600 ms commit (unmount clears it, `:632`).
- [x] Textarea (`:657-658`): `onChange → setText + commit(debounced 600ms)`. Border red on `err`.
- [x] Footer status (`:661`): `err || 'Saves automatically as you type'`.
- [!] **Reset to default** (`:662-666`): reads `defaults[spec.key]` (raw seed string), converts with `asList`/`asJson`/`String` and commits. For `list` rows the seed value is a JSON string, so `asList` returns that string unchanged → `commit` splits it as one line → saves `["[\"a\",\"b\"]"]` (a single-element list containing JSON text). For `json` rows the compact JSON string round-trips correctly. If `/settings/defaults` failed at load, `d` is `undefined` → resets to `''`.  — SET-04, SET-05
- [x] Editors by kind — plain (9): scoring_rubric, scoring_output_light, scoring_output_full, cv_tailor_prompt, persona_tailor_prompt, cover_letter_prompt, autofill_prompt, prep_ask, email_llm_prompt. list (7): email_gmail_query_subjects/senders/exclusions, body_exclusion_phrases, title_exclude_global, company_exclude_global, dedup_tracking_params. json (3): cover_letter_voice_presets, autofill_field_patterns, autofill_option_synonyms.

### 3t. Model catalog modal — controls (`:675-757`)

- [x] Provider `Select` (`:724`, local state, default `'openrouter'`) → triggers live catalog fetch for SEARCHABLE providers.
- [x] Search/slug input (`:726-731`): Enter → `add()`. Placeholder varies: loading / "Search N live models, or paste any slug…" / "Enter the local model name…".
- [x] **Add** (`:733`) → `add()`: dedups on `(provider, model)`; `save('llm_models_list', [...list, {provider, model, label:'<model> (custom)', custom:true}])`. Success flash "Saved".
- [!] Suggestion rows (`:739-741`, up to 8 of 60 filtered) → `add(name)`.  — SET-16
- [!] Catalog rows (`:744-752`): provider · model · "seeded"/"added by you" · **×** remove (`:749-750`, `window.confirm`) → `save('llm_models_list', filtered)`. Removing seeded entries is allowed and persists via `llm_seeded_models` (`seed.py:638-667`).  — SET-15, SET-17
- [~] Error line (`:735`) shows `e.response.data.detail` or "Could not reach the catalog".  — would need a real 400/502 from a provider catalog call
- [x] Scrim / ✕ (`:716,:721`) → `onClose`.

## 4. States rendered

- [!] **Loading**: `S === null` → bare `<div style="flex:1;background:var(--bg)">` (`:347`). No spinner, no skeleton, no text. Header does not render either.  — SET-06
- [!] **Load error**: identical to loading, permanently (`:130` only logs).  — SET-06
- [x] **Search no-match**: `No settings match “{query}”.` (`:404-406`); colophon still renders.
- [!] **Redacted secret (TextBox)**: `GET` returns `"••••••"` → `masked` renders the `MASK` constant (`:25,:74`) with "show" link; unset secret renders empty box with "show". On focus/`show`, the input shows the literal stored string — i.e. the six bullets from GET. Blur with no change → no PATCH. Blur after editing → PATCH of whatever text is there (server drops only an exact `••••••`). After a successful save `S[key]` holds the plaintext until the next `load()`.  — SET-01, SET-02
- [!] **Redacted secret (override key box)** `:463`: same as above, w150.  — SET-01, SET-02
- [x] **Dashboard API key**: never echoes; only placeholder differs by `isSet` (`:558,:563`). Sends only what was typed.
- [x] **Webhook secret**: text preview only (`:298`); never displayed; rotation reveals once via `window.prompt`.
- [!] **Empty model options**: model `Select` shows "pick model…" and an empty menu when the provider has no catalog entries.  — SET-23
- [x] **Override off**: "inherits Primary" pill (`:466`); override on with keyless provider: no key box (`:461`).
- [x] **Default voice with orphan id**: extra option "`<id>` — not in presets" (`:208`).
- [x] **Default résumé with deleted id**: shows "Select…" (no orphan handling, unlike voice).
- [x] **Switch help swap**: `offHelp` when off (`:531`).
- [x] **Info panel open**: bordered/accent "i", inline `--surface-2` panel (`:523,:534`).
- [x] **Flash ok / bad**: header subtitle colour `--accent` / `--bad` (`:363`), 2200 ms.
- [x] **ActionBtn running**: spinner `v2-spin` + "Running…" (`:547-548`); **done**: accent border/fill "Done ✓" for 2600 ms.
- [~] **LinkedIn row**: `status` missing/stale/ok → summary text tone muted/warn/good; `phase` running → detail or "Signing in…"; awaiting_pin → PIN box + "Submit PIN" replaces "Refresh cookie"; `li` null → "Unknown".  — only the stale/idle branch was reachable
- [x] **Edit modal JSON error**: red textarea border + red footer text (`:658,:661`).
- [x] **Catalog modal**: loading placeholder; error line; suggestions list only when `term` non-empty; per-row "seeded"/"added by you" in `--edge`/`--accent`.
- [x] **Model catalog summary** (`:493-495`): `"N models · N seeded · N added by you"`.

## 5. Hover styles (from `frontend/src/v2/theme.css`)

- [!] `.v2-menuitem:hover` → `background: var(--surface-2)` (`theme.css:148`) — Select options (`:54`), catalog suggestions (`:740`).  — fixed at 5c6c17a, rebuild pending
- [!] `.v2-anchor:hover` → `color: var(--text)` (`theme.css:168`) — rail anchors (`:380`).  — fixed at 5c6c17a, rebuild pending
- [x] `.v2-bdc:hover` → border + text `var(--accent)` (`theme.css:155`) — Edit pill (`:485`), Reset to default (`:666`).
- [x] `.v2-bd:hover` → border `var(--accent)` (`theme.css:152`) + `.v2-ctl` line-height 1 (`theme.css:160`) — every `ActionBtn` (`:545`).
- [!] `.v2-hover-accent:hover` → bg `--surface-2`, text `--text` (`theme.css:129`) — modal ✕ buttons (`:653,:721`).  — fixed in source, rebuild pending
- [x] `.v2-hover-accent-text:hover` → text `--accent` (`theme.css:173`) — colophon links (`:414,:416`); also matched by `.jn-v2 a:hover {color:var(--text)}` (`theme.css:121`), class rule wins via `!important`.
- [!] `.v2-hover-bad-text:hover` → text `--bad` (`theme.css:174`) — catalog × (`:749`).  — SET-15
- [x] `.v2-ctl` on Add button (`:733`) — no hover rule, line-height only.
- [x] NO hover treatment: Toggle (`:92`), Select box (`:45`, only open-state border), TextBox, show/hide links (`:82,:565`), info "i" (`:522`), Done (`:667`), Add (`:733`), PIN input, rail group labels, section headers, rows themselves (no `.v2-row`).
- [x] Select open state: border `--accent` (`:45`); selected option: text `--accent` on `--accent-soft` (`:56-57`).
- [x] Cursor: `pointer` on all clickable spans/divs (they are not `<button>`s — no keyboard focus/Enter activation anywhere except native inputs).

## 6. Theme + colour literals

- [x] Zero hex / `rgb(` / `hsl(` literals in `Settings.jsx` (grep confirmed). Every colour is `var(--…)`.
- [x] Tokens used: `--bg --surface --surface-2 --edge --line --line-soft --line-strong --text --text-2 --muted --accent --accent-soft --accent-ink --good --warn --bad --knob --scrim --shadow-menu --shadow-modal --sans --mono --serif`.
- [x] Defined in both light (`theme.css:4`) and dark (`theme.css:74`) blocks: all of the above except `--knob`, `--shadow-menu`, `--shadow-modal`, `--sans/--mono/--serif` which are defined once (light block only, inherited in dark) — toggle knob colour and menu/modal shadows do not change with theme.
- [x] Theme switch: `data-theme` attribute on `.jn-v2` root (`V2App.jsx:90`) from `jobnavigator_dark_mode`; no `prefers-color-scheme` fallback.
- [x] Non-colour literals: font sizes 9 / 9.5 / 10 / 10.5 / 11 / 11.5 / 12 / 12.5 / 13 / 18 / 19 / 30; control heights 15 (toggle) / 26 (Edit pill, ✕) / 30 (ActionBtn) / 31 (modal buttons) / 32 (BOX); widths 135 / 150 / 200 / 220 / 260 / 340 px; rail 216 px; label column 340 px; content max-width 980; modal `min(1020px, 94vw)`; catalog modal 600 × ≤620.
- [x] z-index: Select menu 40; modals 60.
- [x] Transitions: toggle knob `left 150ms` (`:95`); flash colour `.15s` (`:363`).
- [x] Unicode glyphs used as icons: `▾ ⌕ ✕ × ✓ ↗ i` (serif italic "i", `:526`).

## 7. Suspicious

- [x] `console.error` × 3: `:130` (load), `:148` (save), `:189` (runAction). No other console output; no TODO/FIXME/debugger.
- [x] `eslint-disable-next-line react-hooks/exhaustive-deps` on `sections` memo (`:339`); deps `[S, resumes, personaAvailable, trig, li]` omit `defaults`, `val`, `save`, `load`, `flash` (closures captured at memo time — `load` and `flash` are stable enough; harmless today).
- [x] Whitespace: TAB-indented row `:279`; trailing spaces `:282`.
- [!] **Flash timer collision** (`:140-143`): every flash pushes an independent `setTimeout(() => setToast(null))`; a second flash within 2200 ms is cleared early by the first flash's timer. Override-off (`:471`) always fires two PATCHes → two "Saved" flashes → visible for less than 2.2 s.  — SET-09
- [x] **Override OFF leaves `<base>_api_key` stored** (`:471`) — key persists invisibly; `routes_llm._resolve_key` (`routes_llm.py:23-42`) only scans keys whose provider slot matches, so it's inert but never cleared.
- [x] **Primary API key row hidden, not cleared**, when a keyless provider is picked (`:215`).
- [!] **Reset to default on list editors saves a one-element list containing the JSON string** (`:663-665` + `:637`; `/settings/defaults` returns raw seed strings, `routes_settings.py:102`). Affects 7 list rows (§3s).  — SET-04
- [!] **Reset to default when `/settings/defaults` failed** → `defaults` is `{}` → text `''` → saves empty string / `[]` / JSON error (`:122,:663-664`).  — SET-05
- [!] **Edit modal drops keystrokes typed within 600 ms of closing** (`:632` clears the pending timer on unmount; Done/✕/scrim don't flush).  — SET-25
- [!] **Submit PIN has no catch** (`:614-618`) — unhandled promise rejection, no feedback.  — SET-10
- [!] **ApiKeyRow false success** (`:567-573`): PATCH failure is swallowed inside `save` → localStorage + cookie + "Key saved" proceed → client/server key mismatch → lockout.  — SET-03
- [!] **Optimistic `setS` never rolled back** on PATCH failure (`:146-148`) — UI keeps showing the unsaved value after "Could not save".  — SET-08
- [!] **PATCH `warnings` ignored** — `configure_scheduler` / semaphore / dedup-reload failures are invisible.  — SET-27
- [!] **No numeric validation** on 9 numeric boxes; a non-numeric `scrape_interval_minutes` / `email_check_interval_minutes` makes `int()` raise in `configure_scheduler` (`scheduler.py:29-30`) — caught at PATCH time as a warning, but unguarded at startup (`main.py:52`) → backend boot failure until the row is fixed by SQL.  — SET-27
- [!] **Invalid cron silently disables the job** (`scheduler.py:53-55`) — UI shows the bad string as saved.  — SET-27
- [x] **"Done ✓" on 202** for Send test message / Run backup — reflects acceptance, not completion; no run_id polling, no link to Stats.
- [!] Register-webhook reads `data.description` (`:310`) but local failure dicts use `error` (`telegram.py:82,85,102`) → generic "Registration failed" hides the cause (missing bot token / missing secret).  — SET-07
- [x] Native `window.confirm` / `window.prompt` × 4 (`:301,:303,:307,:711`) — unstyled, blocks the event loop, not theme-aware.
- [!] Revealed secret box contains the literal `••••••` mask string as editable text (`:68,:74-77`) — typing without clearing saves `••••••<typed>`.  — SET-01
- [x] `llm_models_list` has **no backend reader** (only `seed.py:641-667` migration) — the catalog is frontend-only; nothing validates that a picked model exists.
- [x] `default_resume_id` orphan (deleted resume) shows "Select…" with no hint; contrast with voice orphan handling (`:208`).
- [x] `prep_include` is free text server-side but the Select offers 5 combos only (`:260-262`).
- [x] Switch with stored `''` (not seeded, but possible via API) reads as off regardless of `dflt` (`:155-159`).
- [x] `Row key={r.label}` and `trig[r.label]` / `info === r.label` (`:400,:504,:433`) — labels double as identity; duplicate labels within a section would collide (none today).
- [x] `sections` memo depends on `trig` and `li` though neither is read inside the builder (`:340`) — recomputes the 68-row spec on every spinner tick; harmless.
- [x] Poll (`:587-593`) has no max duration; stops only when phase leaves running/awaiting_pin or on unmount.
- [!] No `<button>`/`<label>` semantics anywhere — all controls are `span`/`div` with `onClick`; no keyboard operability, no `aria-*`, TextBox inputs have no `id`/`label` association.  — SET-12
- [x] `GET` type coercion: numeric strings arrive as numbers, `"true"/"false"` as booleans (`routes_settings.py:31-34`); `isOn` handles both (`:158`), `TextBox` compares `local !== value` across string/number (`:77`).
- [x] Colophon hard-codes "v.2.0" (`:411`) and the GitHub URL (`:416`).
- [x] Removing a seeded model that a picker currently references leaves the picker on "pick model…" while the stored value is unchanged (Select `cur` undefined, `:42,:47`).
- [x] `autofill_default_length` seeded `"250"` (`seed.py:278`) while `CLAUDE.md` documents 120.

## 8. Counts that must agree

- [x] Rail anchors = 15 = section headers rendered with empty search (`:210-338`).
- [x] Group labels = 4 (AI, PIPELINE, INTEGRATIONS, SYSTEM), rendered once each (`:379`).
- [x] Total rows = **68** (Models 9 · Scoring 8 · Tailoring 4 · Letters 3 · Autofill 4 · Prep 2 · Email 6 · Scheduler 9 · Exclude 3 · Dedup 1 · Notifications 6 · Tracer 3 · Jobright 2 · LinkedIn 5 · Advanced 3); 67 visible when Primary provider is keyless (API key row hidden).  — verified: 67 with a keyless primary provider, 68 with openai
- [x] Row kinds: `B` 24 · `SEL` 7 · `SW` 4 · `E` 19 (9 plain / 7 list / 3 json) · `BT`/button 4 · `pair` 1 · `LLM` 6 · `models` 1 · `apikey` 1 · `linkedin` 1 = 68.
- [x] Override rows = 6 (`:216-222`) = `ovr` init keys (`:126`) = 6 × 3 seeded keys (`*_provider/_model/_api_key`) = 18 keys (matrix).
- [x] `PROVIDERS` = 5 (`:6-12`) = distinct providers in seeded `llm_models_list` (claude_api 8, claude_code 8, ollama 8, openai 10, openrouter 11).
- [~] Fresh install catalog summary = "45 models · 45 seeded · 0 added by you" (`seed.py:50-98`) = 45 rows in Manage… modal.  — live DB has 44 entries, not a fresh install
- [x] Voice presets seeded = 5 (professional, warm, formal, confident, storytelling; `seed.py:141-147`) = Default voice options = 5 (+1 orphan row if stored id is missing).
- [x] Scheduler section rows = 9; keys that trigger `configure_scheduler` on PATCH = 7 (`routes_settings.py:58-61`); day-threshold rows (2) do not.
- [x] Secrets redacted by GET = 13 seeded keys (matrix) = mask-bearing controls on screen: `llm_api_key`, 6 override keys (when overrides on), `jobright_password`, `linkedin_password`, `linkedin_mock_password`, webhook-secret preview, dashboard-key placeholder = 12 visible + `jobright_session_id` with no control.
- [~] `GET /settings/defaults` key count = 78 = `DEFAULT_SETTINGS` entries (`seed.py:11-309`). `GET /settings` on a fresh install = 79 rows (78 + `llm_seeded_models` from `seed.py:642-646`), 80 after the first Gmail poll (`gmail_processed_ids`, `gmail_client.py:71`).  — live DB has 86 rows incl. 8 runtime/legacy keys
- [x] Settings keys with a v2 control = 77 of 78 (`jobright_session_id` unbound).
- [x] Edit buttons = 19 = Edit-modal-capable rows; Manage… = 1; ActionBtn instances = 4 triggers + Save key + Refresh cookie/Submit PIN + Manage… = 7 (+1 while awaiting PIN).
- [x] Default résumé options = 1 + (persona ? 1 : 0) + base resume count from `GET /resumes?is_base=true`.
- [x] Manual-trigger endpoints called = 4 (`/telegram/test`, `/telegram/rotate-webhook-secret`, `/telegram/register-webhook`, `/db/backup`); v1 additionally exposes scrape/email/h1b/cleanup/digest/backfill triggers that v2 Settings does not.
- [x] Debounce/timers: TextBox 0 ms (blur) · Select/Toggle 0 ms · EditModal 600 ms · flash 2200 ms · Done state 2600 ms · LinkedIn poll 2500 ms.
