# Stage 4 — Settings round-trip (every seeded key)
Run 2026-09-02 against the freshly seeded EMPTY database (real DB renamed aside, restored afterwards). Scripts `settings_rt.py`, `settings_ui.py`; raw results `artifacts/settings_rt.json`, `artifacts/settings_ui.json`.

## Method
For each of the 78 keys in `inventory/settings-matrix.md`: read → PATCH a type-valid mutation (int +7, bool flip, cron `7 3 * * 2`, str + marker, list + marker, dict + key, secret → new value, enum → another value) → read back → load `/v2/settings` and look for the value in a control/text (or open the row's editor modal) → for the 7 timing keys read `/api/scheduler/jobs` → PATCH the original → read back. Final `GET /settings` diffed against the starting snapshot.

## Results
| Check | Result |
|---|---|
| Keys in matrix | 78 |
| Mutated + read back correctly | 74 / 74 (4 guarded: `dashboard_api_key`, `telegram_webhook_secret`, `llm_models_list`, `jobright_session_id`) |
| Restored to original | 74 / 74 · final snapshot diff `{}` |
| Timing keys reach the scheduler (`scrape_interval_minutes`, `email_check_interval_minutes`, `digest_cron`, `h1b_cron`, `cleanup_cron`, `reject_cron`, `backup_cron`) | 7 / 7 — new interval/cron visible in `/api/scheduler/jobs` immediately after PATCH |
| UI shows stored value — plain boxes / lists rendered inline | 39 / 39 |
| UI shows stored value — edit-modal rows (prompts, JSON lists/dicts) | 19 / 19 (opened each modal, marker present) |
| Provider picker follows `llm_provider` | yes (OpenAI label shown after PATCH) |
| `tracer_links_url_style` enum | picker reflects `param_jobid` |
| Secrets | `llm_api_key` shows the mask after set; the 5 override keys (`*_llm_api_key`) render only when their override provider is keyed — conditional, verified via SET-01 mechanics instead |
| Toggles (4 bool keys) | value not text-visible; save mechanics verified in Stage 3 Settings (SET) |
| `default_resume_id` | select shows the résumé *name*; UUID not text-visible (expected) |

## Findings
- No round-trip failure. Persistence and binding hold for every key.
- Already logged elsewhere and still open: Reset-to-default on the 7 list editors writes `["<seed JSON string>"]` (SET report); `jobright_session_id` has no control (auto-managed); `llm_models_list` has no backend reader (matrix); backend accepts any value for enum/int/cron keys (no validation — a non-numeric interval raises at scheduler configure, matrix note).
- Observation: `POST /settings` with an unknown key is accepted (no allow-list, `routes_settings.py:51-54`) — the UI cannot produce one today, but the API can; P4, needs decision whether to reject unknown keys.
