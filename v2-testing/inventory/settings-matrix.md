# Settings matrix — one row per seeded key

Reference table for the settings round-trip pass. Built by reading, not running. Sources:

- `backend/seed.py:11-309` — `DEFAULT_SETTINGS` (78 keys). Live DB has 86 rows: the extra 8 are runtime/legacy rows, not seeded (`llm_seeded_models` written by `seed.py:642-646`, `gmail_processed_ids` by `gmail_client.py:71`, plus whatever `cleanup_removed_settings` (`seed.py:579-607`) has not yet deleted or keys created by PATCH of an unknown key — `routes_settings.py:51-54` creates any key it is sent).
- `backend/api/routes_settings.py` — GET (`:20-35`, redaction `:16-17`), PATCH (`:38-94`, side-effect hooks `:57-92`), `/defaults` (`:97-102`).
- `backend/scheduler.py:23-82` — `configure_scheduler()` reads the 7 timing keys via `get_setting()` (`:15-20`).
- `frontend/src/v2/Settings.jsx` — control lines from `v2-testing/inventory/v2-settings.md`; row specs `:210-338`, generic renderers `:451-499` (box `:452`, select `:454`, switch `:455-458`, pair `:459-467`, llm override `:468-483`, edit `:484-488`, models `:489-499`), `ApiKeyRow :555-576`, `ModelsModal :675-757`.
- `frontend/src/components/Settings.jsx` — v1, yes/no only.

Column key:
- **type**: `str` · `int` · `bool-str` (stored as the strings `"true"`/`"false"`) · `cron` (5-field, empty = disabled) · `json-list` · `json-dict` · `secret` · `enum{…}`.
- **takes effect**: `read per call` (the reader queries the `settings` row every time it runs — no restart, no hook) · `scheduler reconfigure on PATCH` (`routes_settings.py:57-67` → `configure_scheduler()`) · `semaphore reset on PATCH` (`:70-84`) · `cache reload on PATCH` (`:87-92`).
- **redacted on GET**: `_REDACT_SUFFIXES = ("_password", "_api_key", "_session_id", "_secret")` + `_REDACT_KEYS = {"dashboard_api_key", "gmail_refresh_token"}` (`routes_settings.py:16-17`). Redacted values come back as `""` (unset) or `"••••••"` (set); PATCH drops any value that is exactly `"••••••"` (`:44-46`).
- Backend reader refs exclude `backend/seed.py` and `backend/tests/`.

## 1. Seeded keys (78)

- [ ] fit_score_threshold
- [ ] scrape_interval_minutes
- [ ] email_check_interval_minutes
- [ ] telegram_enabled
- [ ] digest_cron
- [ ] telegram_chat_id
- [ ] telegram_webhook_secret
- [ ] body_exclusion_phrases
- [ ] h1b_cron
- [ ] cleanup_cron
- [ ] job_archive_after_days
- [ ] auto_reject_after_days
- [ ] proxy_url
- [ ] dashboard_api_key
- [ ] default_resume_id
- [ ] company_exclude_global
- [ ] title_exclude_global
- [ ] linkedin_email
- [ ] linkedin_password
- [ ] linkedin_mock_email
- [ ] linkedin_mock_password
- [ ] jobright_email
- [ ] jobright_password
- [ ] jobright_session_id
- [ ] reject_cron
- [ ] backup_cron
- [ ] scoring_rubric
- [ ] scoring_output_light
- [ ] scoring_output_full
- [ ] llm_provider
- [ ] llm_model
- [ ] llm_api_key
- [ ] llm_fallback_provider
- [ ] llm_fallback_model
- [ ] llm_fallback_api_key
- [ ] scoring_llm_provider
- [ ] scoring_llm_model
- [ ] scoring_llm_api_key
- [ ] llm_models_list
- [ ] scoring_max_concurrent
- [ ] tailoring_max_concurrent
- [ ] tailor_auto_quick_score
- [ ] prompt_caching_enabled
- [ ] scoring_default_depth
- [ ] on_save_action
- [ ] email_llm_enabled
- [ ] email_llm_provider
- [ ] email_llm_model
- [ ] email_llm_api_key
- [ ] email_llm_confidence_threshold
- [ ] email_llm_prompt
- [ ] email_gmail_query_subjects
- [ ] email_gmail_query_senders
- [ ] email_gmail_query_exclusions
- [ ] cv_tailor_llm_provider
- [ ] cv_tailor_llm_model
- [ ] cv_tailor_llm_api_key
- [ ] cv_tailor_prompt
- [ ] persona_tailor_prompt
- [ ] cover_letter_llm_provider
- [ ] cover_letter_llm_model
- [ ] cover_letter_llm_api_key
- [ ] cover_letter_prompt
- [ ] cover_letter_voice_presets
- [ ] cover_letter_default_voice
- [ ] autofill_field_patterns
- [ ] autofill_option_synonyms
- [ ] tracer_links_enabled
- [ ] tracer_links_base_url
- [ ] tracer_links_url_style
- [ ] dedup_tracking_params
- [ ] autofill_llm_provider
- [ ] autofill_llm_model
- [ ] autofill_llm_api_key
- [ ] autofill_default_length
- [ ] autofill_prompt
- [ ] prep_include
- [ ] prep_ask

## 2. Matrix

`PROVIDER_ENUM` = `claude_api | claude_code | openai | ollama | openrouter` (backend dispatch `llm_client.py:30,202,260,269`; v2 `PROVIDERS` `Settings.jsx:6-12`; seed description at `seed.py:41` still lists only four — `openrouter` is missing from the description text, not from the code). Override-provider keys additionally accept `""` = inherit Primary.

| key | seeded default (`seed.py`) | type | backend reader(s) | takes effect via | bound in v2 `Settings.jsx` | v1 | redacted |
|---|---|---|---|---|---|---|---|
| fit_score_threshold | `"60"` (`:12`) | int | `analyzer/cv_scorer.py:455`; `notifier/telegram.py:266` | read per call | `:295` B "Score threshold" (mono w135) | yes | no |
| scrape_interval_minutes | `"60"` (`:13`) | int (0 = off) | `scheduler.py:29` (via `get_setting`); `scraper/sources/company_pages.py:373` (global interval when company has no override) | scheduler reconfigure on PATCH (`routes_settings.py:59`); company_pages read per run | `:273` B "Scrape all companies" | yes | no |
| email_check_interval_minutes | `"30"` (`:14`) | int (0 = off) | `scheduler.py:30` | scheduler reconfigure on PATCH (`:59`) | `:274` B "Email check" | yes | no |
| telegram_enabled | `"false"` (`:15`) | bool-str | `notifier/telegram.py:30` (`_is_enabled`; missing row → True) | read per call | `:293` SW "Telegram" (saves `'true'`/`'false'`, `:457`) | yes | no |
| digest_cron | `"0 8 * * *"` (`:16`) | cron | `scheduler.py:32` → `_add_cron_job(:79)` | scheduler reconfigure on PATCH (`:60`) | `:280` B "Telegram digest · cron" | yes | no |
| telegram_chat_id | `""` (`:17`) | str | `notifier/telegram.py:20` (`_get_chat_id`) | read per call | `:294` B "Chat ID" (mono w135) | yes | no |
| telegram_webhook_secret | `""` (`:18`; replaced by `secrets.token_urlsafe(32)` at `seed.py:352-355` on first run / when blank) | secret (auto-generated) | `main.py:695` (webhook auth); `notifier/telegram.py:70` (register-webhook), `:112-115` (rotate writes it) | read per call | `:297-305` button "Rotate" (preview text only; value never PATCHed from UI — rotation via `POST /telegram/rotate-webhook-secret`) | yes (preview + rotate only, `components/Settings.jsx:1246`) | yes (`_secret`) |
| body_exclusion_phrases | `json.dumps([])` (`:19`) | json-list | `analyzer/h1b_checker.py:376`; `api/routes_searches.py:292,501`; `scraper/sources/freehire.py:273`; `scraper/sources/jobright.py:630`; `scraper/sources/levelsfyi.py:469`; `scraper/sources/linkedin_personal.py:998` | read per call | `:285` E list "Body phrases" | yes | no |
| h1b_cron | `"0 2 * * 0"` (`:20`) | cron | `scheduler.py:33` → `_add_cron_job(:80)` | scheduler reconfigure on PATCH (`:60`) | `:281` B "H-1B refresh · cron" | yes | no |
| cleanup_cron | `"0 4 * * *"` (`:21`) | cron | `scheduler.py:34` → `_add_cron_job(:81)` | scheduler reconfigure on PATCH (`:60`) | `:282` B "Job cleanup · cron" | yes | no |
| job_archive_after_days | `"90"` (`:22`) | int (0 = disabled) | `scheduler.py:238` (cron cleanup); `main.py:455` (manual `/cleanup` trigger) | read per call (NOT a timing key — no reconfigure) | `:275` B "Cleanup after" | yes | no |
| auto_reject_after_days | `"0"` (`:23`) | int (0 = disabled) | `scheduler.py:203` (cron reject); `main.py:491` (manual trigger) | read per call | `:276-277` B "Auto-reject threshold" | yes | no |
| proxy_url | `""` (`:24`) | str (URL) | `api/routes_searches.py:190` (test scrape); `scraper/orchestrator.py:151,263` | read per call | `:334` B "Proxy URL" (mono w340) | yes | no |
| dashboard_api_key | `""` (`:25`; overwritten with `INITIAL_API_KEY` at startup if empty, `main.py:39-42`) | secret | `main.py:39` (startup), `:141` (auth middleware, every request), `:173`, `:191` (`/auth/set-session`) | read per call (per request) | `:335` kind `apikey` → `ApiKeyRow :555-576` (`save('dashboard_api_key')` `:569`) | yes | yes (`_REDACT_KEYS` + `_api_key`) |
| default_resume_id | `""` (`:26`) | str (Resume UUID · `"persona"` · `""` = all) | `analyzer/cv_scorer.py:171` (`_get_default_resume`, handles `persona`); `api/routes_applications.py:297`; `api/routes_companies.py:263`; `api/routes_jobs.py:592` | read per call | `:227` SEL "Default résumé" (options `:197-199`) | yes | no |
| company_exclude_global | `json.dumps([])` (`:27`) | json-list | `scraper/_shared/filters.py:28`; `scraper/sources/linkedin_personal.py:991` | read per call | `:287` E list "Company exclude" | yes | no |
| title_exclude_global | `json.dumps([])` (`:28`) | json-list | `models/db.py:479`; `scraper/sources/jobspy.py:141` | read per call | `:286` E list "Title exclude" | yes | no |
| linkedin_email | `""` (`:29`) | str | `scraper/sources/linkedin_personal.py:726,937` | read per call | `:326` B "Personal email" (w260) | yes | no |
| linkedin_password | `""` (`:30`) | secret | `scraper/sources/linkedin_personal.py:727,938` | read per call | `:327` B secret "Personal password" | yes | yes (`_password`) |
| linkedin_mock_email | `""` (`:31`) | str | `refresh_linkedin_session.py:46` (invoked by `api/routes_linkedin.py:36,67`) | read per call (per refresh run) | `:329-330` B "Mock account email" | yes | no |
| linkedin_mock_password | `""` (`:32`) | secret | `refresh_linkedin_session.py:46` | read per call | `:331` B secret "Mock account password" | yes | yes (`_password`) |
| jobright_email | `""` (`:33`) | str | `scraper/sources/jobright.py:120` | read per call | `:322` B "Email" (w260) | yes | no |
| jobright_password | `""` (`:34`) | secret | `scraper/sources/jobright.py:121` | read per call | `:323` B secret "Password" | yes | yes (`_password`) |
| jobright_session_id | `""` (`:35`) | secret (auto-managed cookie) | `scraper/sources/jobright.py:95` (read), `:128` (written via `_save_setting :44-49`) | read per call | **NOT BOUND** (documented as such in `v2-settings.md` §3p) | no | yes (`_session_id`) |
| reject_cron | `"0 4 * * *"` (`:36`) | cron | `scheduler.py:35` → `_add_cron_job(:82)` | scheduler reconfigure on PATCH (`:60`) | `:278` B "Auto-reject · cron" | yes | no |
| backup_cron | `"0 3 * * *"` (`:37`) | cron | `scheduler.py:31` → `_add_cron_job(:78)` | scheduler reconfigure on PATCH (`:60`) | `:279` B "DB backup · cron" | yes | no |
| scoring_rubric | `"Score each resume using these c…"` (`:38`) | str (prompt) | `analyzer/cv_scorer.py:279` | read per call | `:236` E plain "Scoring rubric" | yes | no |
| scoring_output_light | `'Return ONLY this JSON:\n{\n  "sc…'` (`:39`) | str (prompt; JSON-shaped text with `CV_NAMES_HERE` token) | `analyzer/cv_scorer.py:281-282` (key chosen by depth) | read per call | `:237` E plain "Light output schema" | yes | no |
| scoring_output_full | `'Return ONLY this JSON:\n{\n  "sc…'` (`:40`) | str (prompt, same shape + `breakdown`) | `analyzer/cv_scorer.py:281-282` | read per call | `:238` E plain "Full output schema" | yes | no |
| llm_provider | `"claude_api"` (`:41`) | enum PROVIDER_ENUM | `analyzer/llm_client.py:30,96,116,142,170,191`; `analyzer/cv_scorer.py:289`; `api/routes_autofill.py:121`; `api/routes_llm.py:24`; `api/routes_resumes.py:861,1125`; `email_monitor/response_parser.py:166` | read per call | `:212-214` pair (`pKey`) → Select `:462` | yes | no |
| llm_model | `"claude-sonnet-5"` (`:42`) | str (model slug; UI constrains to `llm_models_list`) | `analyzer/llm_client.py:32,98,118,144,172,192`; `analyzer/cv_scorer.py:290`; `api/routes_autofill.py:122`; `api/routes_resumes.py:856,1123`; `email_monitor/response_parser.py:161` | read per call | `:212-214` pair (`mKey`) → Select `:463` (options `modelsFor(p)` `:167-171`) | yes | no |
| llm_api_key | `""` (`:43`) | secret | `analyzer/llm_client.py:34,100,120,146,174,193`; `analyzer/cv_scorer.py:291`; `api/routes_llm.py:24` (`_resolve_key`) | read per call | `:215` B secret mono w340 "API key" (hidden when provider ∈ KEYLESS `:17`) | yes | yes (`_api_key`) |
| llm_fallback_provider | `""` (`:44`) | enum PROVIDER_ENUM ∪ `""` (= no fallback) | `analyzer/llm_client.py:35`; `api/routes_llm.py:25` | read per call | `:217-218` LLM base `llm_fallback` → Select `:472` | yes | no |
| llm_fallback_model | `""` (`:45`) | str (model slug) | `analyzer/llm_client.py:36` | read per call | `:217-218` LLM → Select `:473` | yes | no |
| llm_fallback_api_key | `""` (`:46`) | secret | `analyzer/llm_client.py:37`; `api/routes_llm.py:25` | read per call | `:217-218` LLM → TextBox secret w150 `:476` (only when provider non-keyless) | yes | yes (`_api_key`) |
| scoring_llm_provider | `""` (`:47`) | enum PROVIDER_ENUM ∪ `""` (= Primary) | `analyzer/cv_scorer.py:289` | read per call | `:216` LLM base `scoring_llm` → Select `:472`; override-off writes `''` `:483` | yes | no |
| scoring_llm_model | `""` (`:48`) | str (model slug) | `analyzer/cv_scorer.py:290` | read per call | `:216` LLM → Select `:473`; override-off writes `''` `:483` | yes | no |
| scoring_llm_api_key | `""` (`:49`) | secret | `analyzer/cv_scorer.py:291` | read per call | `:216` LLM → TextBox secret `:476` (NOT cleared on override-off) | yes | yes (`_api_key`) |
| llm_models_list | `json.dumps([...45 entries...])` (`:50-98`) — `[{provider, model, label}]`, 5 providers | json-list of `{provider, model, label, custom?}` | **none found** (only `seed.py:641-667` `migrate_llm_settings` merges new defaults at startup, tracked by runtime key `llm_seeded_models`) — frontend-only catalog | n/a (no backend consumer; nothing validates a picked model) | `:223-224` kind `models` → Manage… `:489-499` → `ModelsModal` add `:707` / remove `:712` | yes | no |
| scoring_max_concurrent | `"5"` (`:99`) | int (≥1) | `analyzer/cv_scorer.py:22` (`_get_scoring_semaphore`, lazy module cache `:16-31`) | semaphore reset on PATCH (`routes_settings.py:70-75` → `reset_scoring_semaphore`); otherwise cached until restart | `:228` B mono w135 "Max parallel jobs" | yes | no |
| tailoring_max_concurrent | `"2"` (`:100`) | int (≥1) | `api/routes_resumes.py:164` (`_get_tailoring_semaphore`, lazy module cache `:155-172`) | semaphore reset on PATCH (`:78-84` → `reset_tailoring_semaphore`); otherwise cached until restart | `:243` B mono w135 "Max parallel tailors" | **no** (not in v1) | no |
| tailor_auto_quick_score | `"light"` (`:101`) | enum `off | light | full` (legacy `true/yes/1/""`→light, `false/no/0`→off; `routes_resumes.py:920-925`) | `api/routes_resumes.py:918` | read per call | `:244-245` SEL off/light/full | yes | no |
| prompt_caching_enabled | `"true"` (`:102`) | bool-str | `analyzer/cv_scorer.py:292-293` | read per call | `:234-235` SW "Prompt caching" (dflt true) | yes | no |
| scoring_default_depth | `"light"` (`:103`) | enum `light | full` | `analyzer/cv_scorer.py:453` | read per call | `:229-231` SEL light/full | yes | no |
| on_save_action | `"off"` (`:104`) | enum `off | light | full` | `api/routes_jobs.py:552` | read per call | `:232-233` SEL off/light/full | yes | no |
| email_llm_enabled | `"false"` (`:105`) | bool-str (must equal `"true"`, `response_parser.py:123`) | `email_monitor/response_parser.py:122` | read per call | `:265` SW "LLM classification" (no dflt → off) | yes | no |
| email_llm_provider | `""` (`:106`) | enum PROVIDER_ENUM ∪ `""` | `analyzer/llm_client.py:91`; `api/routes_llm.py:29`; `email_monitor/response_parser.py:163` | read per call | `:222` LLM base `email_llm` → Select `:472` | yes | no |
| email_llm_model | `""` (`:107`) | str (model slug) | `analyzer/llm_client.py:92`; `email_monitor/response_parser.py:158` | read per call | `:222` LLM → Select `:473` | yes | no |
| email_llm_api_key | `""` (`:108`) | secret | `analyzer/llm_client.py:93`; `api/routes_llm.py:29` | read per call | `:222` LLM → TextBox secret `:476` | yes | yes (`_api_key`) |
| email_llm_confidence_threshold | `"70"` (`:109`) | int 0-100 | `email_monitor/gmail_client.py:301` | read per call | `:266` B mono w135 "Confidence threshold" | yes | no |
| email_llm_prompt | `"Classify this email and match i…"` (`:110`) | str (prompt; placeholders `{applications} {from} {subject} {body}`) | `email_monitor/response_parser.py:127` | read per call | `:267` E plain "Classification prompt" | yes | no |
| email_gmail_query_subjects | `json.dumps([26 terms])` (`:111-120`) | json-list | `email_monitor/gmail_client.py:96` | read per call | `:268` E list "Gmail query · subjects" | yes | no |
| email_gmail_query_senders | `json.dumps([15 patterns])` (`:121-127`) | json-list | `email_monitor/gmail_client.py:81` | read per call | `:269` E list "Gmail query · senders" | yes | no |
| email_gmail_query_exclusions | `json.dumps([7 terms])` (`:128-131`) | json-list | `email_monitor/gmail_client.py:106` | read per call | `:270` E list "Gmail query · exclusions" | yes | no |
| cv_tailor_llm_provider | `""` (`:132`) | enum PROVIDER_ENUM ∪ `""` | `analyzer/llm_client.py:112`; `api/routes_llm.py:26`; `api/routes_resumes.py:858` | read per call | `:219` LLM base `cv_tailor_llm` → Select `:472` | yes | no |
| cv_tailor_llm_model | `""` (`:133`) | str (model slug) | `analyzer/llm_client.py:113`; `api/routes_resumes.py:853` | read per call | `:219` LLM → Select `:473` | yes | no |
| cv_tailor_llm_api_key | `""` (`:134`) | secret | `analyzer/llm_client.py:114`; `api/routes_llm.py:26` | read per call | `:219` LLM → TextBox secret `:476` | yes | yes (`_api_key`) |
| cv_tailor_prompt | `"Tailor this resume for the job d…"` (`:135`) | str (prompt; `{job_description} {resume_json}`) | `api/routes_resumes.py:710,822` | read per call | `:241` E plain "Résumé tailoring prompt" | yes | no |
| persona_tailor_prompt | `"Tailor a FOCUSED resume from thi…"` (`:136`) | str (prompt; `{job_description} {persona_json}`) | `api/routes_resumes.py:818` | read per call | `:242` E plain "Persona tailoring prompt" | yes | no |
| cover_letter_llm_provider | `""` (`:137`) | enum PROVIDER_ENUM ∪ `""` | `analyzer/llm_client.py:138`; `api/routes_cover_letters.py:420`; `api/routes_llm.py:27` | read per call | `:220` LLM base `cover_letter_llm` → Select `:472` | yes | no |
| cover_letter_llm_model | `""` (`:138`) | str (model slug) | `analyzer/llm_client.py:139`; `api/routes_cover_letters.py:418` | read per call | `:220` LLM → Select `:473` | yes | no |
| cover_letter_llm_api_key | `""` (`:139`) | secret | `analyzer/llm_client.py:140`; `api/routes_llm.py:27` | read per call | `:220` LLM → TextBox secret `:476` | yes | yes (`_api_key`) |
| cover_letter_prompt | `"Write a cover letter for the can…"` (`:140`) | str (prompt; `{voice_instruction} {length_instruction} {job_description}`) | `api/routes_cover_letters.py:335,414` | read per call | `:250` E plain "Cover letter prompt" | yes | no |
| cover_letter_voice_presets | `json.dumps([5 presets])` (`:141-147`) — `[{id, label, instruction}]` | json-list of `{id, label, instruction}` | `analyzer/cover_letter_generator.py:36` | read per call | `:249` E json "Voice presets" | yes | no |
| cover_letter_default_voice | `"professional"` (`:148`) | enum (ids present in `cover_letter_voice_presets`; falls back to first preset `cover_letter_generator.py:44-48`) | `analyzer/cover_letter_generator.py:44` | read per call | `:248` SEL "Default voice" (options from presets `:204-208`, orphan id kept) | yes | no |
| autofill_field_patterns | `json.dumps({...})` (`:149-181`) — persona field → name-pattern lists | json-dict | `api/routes_autofill.py:79` (`_json_setting`, served to the extension) | read per call | `:255` E json "Field patterns" | yes | no |
| autofill_option_synonyms | `json.dumps({...})` (`:182-246`) — enum key → {value → synonyms}, `_bool` | json-dict | `api/routes_autofill.py:80` | read per call | `:256` E json "Option synonyms" | yes | no |
| tracer_links_enabled | `"false"` (`:247`) | bool-str (must equal `"true"`, `routes_resumes.py:288`) | `api/routes_resumes.py:287` | read per call | `:314-315` SW "Rewrite links" | yes | no |
| tracer_links_base_url | `""` (`:248`) | str (URL; empty = feature inert) | `api/routes_resumes.py:291` | read per call | `:316` B mono w260 "Base URL" | yes | no |
| tracer_links_url_style | `"path"` (`:249`) | enum `path | param | path_jobid | param_jobid` | `api/routes_resumes.py:296` | read per call | `:317-319` SEL "URL style" (4 options) | yes | no |
| dedup_tracking_params | `json.dumps([~80 params])` (`:250-274`) | json-list | `scraper/_shared/dedup.py:49` (`_get_tracking_params`, module cache `:37-59`; also used by `scraper/orchestrator` URL cleaning via `_normalize_url`) | cache reload on PATCH (`routes_settings.py:87-92` → `reload_tracking_params`); otherwise cached until restart | `:290` E list "Stripped params" | yes | no |
| autofill_llm_provider | `""` (`:275`) | enum PROVIDER_ENUM ∪ `""` | `analyzer/llm_client.py:166,191`; `api/routes_autofill.py:121`; `api/routes_llm.py:28` | read per call | `:221` LLM base `autofill_llm` → Select `:472` | yes | no |
| autofill_llm_model | `""` (`:276`) | str (model slug) | `analyzer/llm_client.py:167,192`; `api/routes_autofill.py:122` | read per call | `:221` LLM → Select `:473` | yes | no |
| autofill_llm_api_key | `""` (`:277`) | secret | `analyzer/llm_client.py:168,193`; `api/routes_llm.py:28` | read per call | `:221` LLM → TextBox secret `:476` | **no** (v1 binds only `autofill_llm_provider` `:821` and `autofill_llm_model` `:842`) | yes (`_api_key`) |
| autofill_default_length | `"250"` (`:278`; CLAUDE.md says 120 — code fallback when non-digit is 120, `routes_autofill.py:105,195`) | int | `api/routes_autofill.py:104,194` | read per call | `:253` B mono w135 "Default answer length" | yes | no |
| autofill_prompt | `"You are the candidate, writing a…"` (`:279-295`) | str (prompt; `{persona} {qa_bank} {company} {position} {question} {max_chars}`; 500 if blank `routes_autofill.py:107-108`) | `api/routes_autofill.py:106` | read per call | `:254` E plain "Autofill prompt" | yes | no |
| prep_include | `"resume,posting,notes"` (`:296-297`) | str — comma-separated subset of `resume | posting | notes` (parsed to a set, `routes_applications.py:524-525`; any combination/order accepted) | `api/routes_applications.py:524` | read per call | `:260-262` SEL "Include by default" (5 fixed combos) | **no** (not in v1) | no |
| prep_ask | `"Prepare me for this interview. G…"` (`:298-308`) | str (plain text, no placeholders) | `api/routes_applications.py:592` | read per call | `:259` E plain "\"What I need from you\" section" | yes | no |

## 3. Findings

### (a) Keys bound in v2 that are NOT in `seed.py`

None. Every `save(key, …)` target in `frontend/src/v2/Settings.jsx` resolves to a seeded key:
- static keys in the row specs `:212-337` (checked one by one against §1);
- the six `LLM` override bases (`:216-222`: `scoring_llm`, `llm_fallback`, `cv_tailor_llm`, `cover_letter_llm`, `autofill_llm`, `email_llm`) expand to `${base}_provider` / `${base}_model` / `${base}_api_key` (`:472,473,476,483`) — all 18 are seeded (`seed.py:44-49,106-108,132-134,137-139,275-277`);
- `ModelsModal` writes only `llm_models_list` (`:707,712`);
- `ApiKeyRow` writes only `dashboard_api_key` (`:569`).

The only non-seeded name the screen touches is the localStorage key `jobnavigator_api_key` (`:570`), which is not a settings row. Note that the backend would happily create any unseeded key (`routes_settings.py:51-54`, no allow-list), so this stays true only as long as the row specs stay in sync with `DEFAULT_SETTINGS`.

### (b) Keys in `seed.py` bound in v1 but NOT in v2

None. v2 binds 77 of 78 seeded keys; the one unbound key, `jobright_session_id`, is unbound in v1 as well (auto-managed by `scraper/sources/jobright.py:128`, redacted on GET, and deliberately has no row — `v2-settings.md` §3p).

For the reverse direction (bound in v2, not in v1) — useful when comparing screens during the round-trip pass: `tailoring_max_concurrent` (v2 `:243`), `autofill_llm_api_key` (v2 `:221`/`:476`), `prep_include` (v2 `:260-262`). `telegram_webhook_secret` is preview-plus-rotate in both UIs (v2 `:297-305`, v1 `components/Settings.jsx:1246`); neither PATCHes the value.

### (c) Keys unread by any backend code

- `llm_models_list` — no reader outside `backend/seed.py` (`migrate_llm_settings`, `seed.py:641-667`, which only reconciles the stored list with the seeded defaults at startup). The model catalog is consumed exclusively by the frontend (v2 `:163-171,493,682`; v1 `components/Settings.jsx:259,309,407,460,621,734,835,976`). Consequence: the backend never validates that `llm_model` / `*_llm_model` names a catalog entry — any string PATCHed into a model key is passed straight to the provider (`llm_client.py:32` etc.).

Every other seeded key has at least one reader (see the matrix). Runtime-only keys observed but not seeded (for completeness, since they will appear in `GET /settings`): `llm_seeded_models` (`seed.py:642-646`, written only), `gmail_processed_ids` (`email_monitor/gmail_client.py:71`), `gmail_refresh_token` (named in `_REDACT_KEYS` `routes_settings.py:17`; no writer found in `backend/` — legacy).

### (d) v2 control type vs value type mismatches

Strict mismatches (control shape cannot express or over-constrains the stored type):

1. `prep_include` — backend accepts any comma-separated subset of `resume|posting|notes` in any order (`routes_applications.py:525` builds a set); v2 `:260-262` offers exactly 5 fixed combos (`resume,posting,notes` · `resume,posting` · `posting,notes` · `resume` · `posting`). Missing combos (`resume,notes`, `notes`, empty, or a different order such as `posting,resume`) render as "Select…" (`Select :47`) and cannot be chosen. Not a data-loss bug, but the control is narrower than the type.
2. `cover_letter_default_voice` — enum whose domain is derived from another setting (`cover_letter_voice_presets`). v2 handles it correctly (Select from preset ids, orphan kept `:204-208`), but editing the presets JSON and removing the id currently stored leaves the Select showing "`<id> — not in presets`" while the backend silently falls back to the first preset (`cover_letter_generator.py:44-48`). Listed because the two controls are coupled and the UI does not re-validate on preset save.
3. `scoring_output_light` / `scoring_output_full` — JSON-shaped prompt text (`seed.py:39-40`) edited in a **plain** editor (`:237-238`, not `json: true`). This is correct given the `CV_NAMES_HERE` / `0-100` placeholder tokens make the text non-parseable JSON — but the label "JSON shape for … runs" invites JSON edits with no validation.

Soft mismatches (free-text box for a typed scalar — no `type="number"`, `inputMode`, min/max, or pattern; server does `int()` unguarded at scheduler startup `scheduler.py:29-30`):

- int in `B` TextBox: `fit_score_threshold` (`:295`), `scrape_interval_minutes` (`:273`), `email_check_interval_minutes` (`:274`), `job_archive_after_days` (`:275`), `auto_reject_after_days` (`:276`), `scoring_max_concurrent` (`:228`), `tailoring_max_concurrent` (`:243`), `email_llm_confidence_threshold` (`:266`), `autofill_default_length` (`:253`) — 9 boxes.
- cron in `B` TextBox with no client validation: `reject_cron` (`:278`), `backup_cron` (`:279`), `digest_cron` (`:280`), `h1b_cron` (`:281`), `cleanup_cron` (`:282`) — a bad expression is saved and the job is silently skipped (`scheduler.py:53-55`).
- URL in `B` TextBox: `proxy_url` (`:334`), `tracer_links_base_url` (`:316`) — no URL validation (the backend strips a trailing `/` only, `routes_resumes.py:292`).
- `telegram_chat_id` (`:294`) — numeric Telegram id in a free box.

Correctly typed (for the record): 4 bool-str → `SW` toggles writing `'true'`/`'false'` (`:457`); 5 enums → `SEL`; 7 json-lists → `E list` (newline-split); 3 json-dict/list-of-objects → `E json` (parsed before save); 12 secrets → `secret` TextBox or `ApiKeyRow`; `default_resume_id` → SEL of live resumes + `persona`.

Related round-trip hazard (not a type mismatch, but affects list keys): **Reset to default** in the edit modal for `list` rows saves a one-element list containing the seed's JSON string (`:663-665` + `:637`, because `/settings/defaults` returns raw seed strings `routes_settings.py:102`). Affects all 7 list keys: `email_gmail_query_subjects`, `email_gmail_query_senders`, `email_gmail_query_exclusions`, `body_exclusion_phrases`, `title_exclude_global`, `company_exclude_global`, `dedup_tracking_params`.

## 4. Totals

- Seeded keys: **78** (`seed.py:11-309`).
- Bound in v2: **77**; NOT bound in v2: **1** (`jobright_session_id`).
- Bound in v1: **74** of 78; not in v1: `jobright_session_id`, `tailoring_max_concurrent`, `autofill_llm_api_key`, `prep_include`.
- Redacted on GET: **13** (`telegram_webhook_secret`, `dashboard_api_key`, `linkedin_password`, `linkedin_mock_password`, `jobright_password`, `jobright_session_id`, `llm_api_key`, `llm_fallback_api_key`, `scoring_llm_api_key`, `email_llm_api_key`, `cv_tailor_llm_api_key`, `cover_letter_llm_api_key`, `autofill_llm_api_key`).
- Unread by backend: **1** (`llm_models_list`).
- Bound in v2 but unseeded: **0**.
- Type mismatches: **3 strict** (`prep_include`, `cover_letter_default_voice` coupling, `scoring_output_light/full` as plain text) + **17 soft** (9 int boxes, 5 cron boxes, 2 URL boxes, 1 chat-id box).
- Takes effect: 7 keys via scheduler reconfigure on PATCH; 2 via semaphore reset on PATCH; 1 via cache reload on PATCH; 1 n/a (`llm_models_list`); remaining 67 read per call. **No seeded key is cached at import / needs a restart.**
