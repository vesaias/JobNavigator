# v2 verification pass — PLAN

Resume rule: read this file, continue from the first unticked box. State lives here and in FINDINGS.md, never in chat.

Conventions: severity P1 broken/data-loss · P2 functional · P3 design deviation · P4 nit. Fix inline only if unambiguous and <50 lines; otherwise log in FINDINGS.md. Commit after every stage, bare messages (no trailers). Never push. Design sources decoded to `v2-testing/design/` (gitignored). Test artifacts to `v2-testing/artifacts/` (gitignored).

Environment: stack via `docker compose` (Docker Desktop). Backend tests run in-container: `docker compose exec -T backend sh -c "cd /app && python -m pytest backend/tests -q"`. Playwright runs in the backend container against `http://caddy/...`, API key `pick-a-password`. Frontend rebuild: `docker compose build frontend && docker compose up -d frontend`, then grep the served bundle for a token from the change.

## Stage 0 — Baseline
- [x] Code context read (HANDOVER.md, V2App.jsx, Toast.jsx, routes, openapi)
- [x] Stack up (backend/frontend/db/caddy all Up)
- [x] Backend suite in container: 587 passed, 1 warning, 22.75s (2026-09-01)
- [x] pg_dump baseline: `backups/v2testing_baseline_20260901_2345.dump` (custom format, 23.6 MB). Counts: jobs 19012 · applications 377 · companies 126 · searches 6 · resumes 349 · cover_letters 16 · settings 86 · personas 1 · job_runs 1585
- [x] Bundle confirmed: rebuilt frontend from HEAD 438d27a; served `index-Dnrx3n0f.js` contains V2App tokens (`jobnavigator_v2_rail`, `No scrape recorded yet`)
- [x] Verified: baseline dump restores into `jobnavigator_restoretest` (jobs 19012 · applications 377 · settings 86 · resumes 349)

## Stage 1 — Inventory
- [x] Routes (v1 + v2) listed below
- [x] Endpoints listed (94 paths / 110 operations) → `inventory/endpoints.md`
- [x] v2 screen inventories: feed (193 boxes) · searches (150) · companies (202) · applications (137) · resumes (292) · cover-letters (230) · settings (207)
- [~] v2 persona-stats inventory → `inventory/v2-persona-stats.md` (Persona complete; Stats through §2.4 — the Stats screen agent finishes it)
- [x] v1 screen inventories → `inventory/v1-*.md` (3 files)
- [x] Settings matrix → `inventory/settings-matrix.md` (78 keys)
- [x] Design boards decoded → `design/` (14 boards byte-exact + MAIN.md + github.md). Note: MAIN.md names `Resumes Shelf` canonical for Résumés while HANDOVER names `Resumes Home D`; github.md names `Applications Ops` (split inbox) canonical while MAIN.md lists Applications as open. Testing follows the HANDOVER table.
- [x] Commit

### Routes
v2 (shell `V2App`, `/v2` → redirect `feed`): `/v2/feed` · `/v2/searches` · `/v2/companies` · `/v2/applications` · `/v2/resumes` · `/v2/resumes/:id` · `/v2/cover-letters` · `/v2/cover-letters/:id` · `/v2/persona` · `/v2/stats` · `/v2/settings` · `/v2/toasts` (ToastLab, temporary, outside the shell)
v1 (`ClassicShell`): `/` · `/applications` · `/companies` · `/searches` · `/settings` · `/resumes` · `/cover-letters` · `/persona` · `/stats`
Backend-served: `/health` · `/docs` · `/redoc` · `/openapi.json` · `/cv/{token}` · `/?cv=`

## Stage 2 — Static sweeps
- [x] Dead links: 46 targets checked; 2 defects → F-001 (v1 route), F-002 (`?company=` unread). `/docs` + GitHub external OK; `/api/...` hrefs rely on the `jn_session` cookie set by App.jsx startup sync
- [x] No-op handlers — catalogued per screen in the inventories' "Suspicious" sections and verified in Stage 3 (dead code items in FEED/SRCH/COMP reports)
- [x] Colour literals: 0 in v2 JSX. Tokens: 10 unused (F-003), 5 shadows without dark (F-004); every `var(--x)` used in JSX is defined
- [x] Console sweep, 23 routes × 2 themes → `artifacts/sweep1/` (gitignored). Clean except: Feed mounts the posting iframe while the frame-check is still pending (XFO refusals logged; Stage 3 Feed item); PDF blob aborts in headless are expected
- [x] Commit

**Backend does NOT hot-reload** (F-006): `docker compose restart backend` after every backend edit; agents ask `main` for restarts between waves.

## Stage 3 — Per screen (each: every control · empty/one/many/long/null · light+dark · hovers vs design style-hover · API-failure path · empty DB)
- [x] Feed → `stage3/feed.md` (38 findings: 11 P2 · 17 P3 · 10 P4; 5 fixes)
- [x] Searches → `stage3/searches.md` (29: 6 P2 · 10 P3 · 13 P4; 7 fixes, diff 89 lines — review)
- [x] Companies → `stage3/companies.md` (37: 1 P1 · 12 P2 · 16 P3 · 8 P4; 2 fixes + 3 earlier)
- [x] Applications → `stage3/applications.md` (23: 7 P2 · 10 P3 · 6 P4; 3 fixes)
- [x] Résumés → `stage3/resumes.md` (31: 1 P1 · 8 P2 · 13 P3 · 9 P4; 7 fixes incl. backend flag_modified)
- [x] Cover Letters → `stage3/cover-letters.md` (29: 7 P2 · 14 P3 · 8 P4; 5 fixes)
- [x] Persona + Stats → `stage3/persona-stats.md` (45: 1 P1 · 10 P2 · 13 P3 · 21 P4; 2 fixes incl. backend flag_modified)
- [x] Settings screen → `stage3/settings.md` (27: 2 P1 · 4 P2 · 12 P3 · 9 P4; 9 fixes; design re-diff done: 15/15 sections, 64 vs 68 rows)
- [x] Shell (rail, counts, health line, theme toggle, collapse, overlays, toasts) → `stage3/shell.md` (SHELL-01..06; 1 fixed hover bug, rest decisions)
- [x] Wave-level: theme.css hover hardening, F-007 handler (live), frontend rebuilt (index-ClAeCNUL.js) + re-verified → `stage3/REVERIFY.md` (18 confirmed; residual half-pixel sites → F-009)
- [x] Stage 3b empty-DB sweep: 23 routes × 2 themes on a fresh seed, 0 page errors, empty copy recorded → `artifacts/empty/`; F-010 (Feed first-run copy)
- [x] Committed (5ec8736)

**All stages complete 2026-09-02 ~17:00.** Follow-ups: decisions in REPORT.md; Résumés geometry re-check against `Resumes Shelf`; F-009 line-height pass if approved.

## Stage 4 — Settings round-trip (every key: API read → type-valid write → read back → UI shows it → takes effect → restore)
- [x] All keys → `stage4/settings-roundtrip.md` (74/74 persist + restore; 7/7 scheduler; 58/58 visible controls show the value)
- [x] Commit

## Stage 5 — Cross-cutting
- [x] Counts agree → `stage5/cross-cutting.md`
- [x] Background jobs: 202 → 409 duplicate → survives navigation → restart marks run failed 'Process restarted'
- [x] Deep links to missing ids (empty-DB sweep + F-007; residual UX items in RES/CL reports)
- [x] Toasts: system now mounted on all 9 screens; error kind persists (lab 7.2 s); load-failure sites re-verified after rebuild
- [x] Keyboard shortcuts (FEED report: j/k/s/x/a/e/r work; `o` listed-unhandled, `f`/`g` unlisted)
- [x] Narrow viewports: 1024×700 pass per screen (FEED-03 fixed; APPS-09, CL download button open)
- [x] Commit

## Stage 6 — v1 regression
- [x] v1: 9 routes × 2 themes clean on the real DB after all backend changes; 587 backend tests green; backend changes are additive (404 handler, flag_modified, aliases on create, trigger_url)
- [x] Commit

## Stage 7 — Report
- [x] `v2-testing/REPORT.md` — 276 findings: P1 5 (all fixed) · P2 70 (26 fixed) · P3 111 · P4 90; 44 fixed, 217 need a decision, 15 logged
- [x] Restored from `backups/v2testing_baseline_20260901_2345.dump`: jobs 19012 · applications 377 · companies 126 · searches 6 · resumes 349 · cover_letters 16 · settings 86 · 0 ZZTEST rows
- [x] Commit

## Follow-up round (2026-09-02, after the 7 stages) — how to resume
Workflow the user settled on: they read one screen's open P3/P4 list (`P3-P4.md` / `DECISIONS-design.md`), reply per id (fix / keep / explain / what?); I explain the unclear ones in chat, then an **Opus** subagent applies the clear fixes (source only), I rebuild the frontend (`docker compose build frontend && docker compose up -d frontend`), restart the backend if a `.py` changed, verify each item with a Playwright script in the backend container (harness `v2-testing/tools/h.py` → copy to `/tmp/v2t/h.py`), set each finding's `**Status**` line, regenerate `REPORT.md` with `py v2-testing/tools/report_gen.py`, commit (bare message). Subagents: Opus for fixes, Sonnet for mechanical work, Fable only orchestrates. Never push.
- Closed screens: Feed, Searches, Companies, Applications, Cover Letters, Persona, Stats (all open items fixed or decided).
- Still open for the user's call: Résumés (`stage3/resumes.md` + `stage3/resumes-shelf-recheck.md` RES2-01..12), Settings (`stage3/settings.md`), Shell (`stage3/shell.md` SHELL-02/04/05), plus cross-cutting F-003/F-004 in `FINDINGS.md`.
- Data notes: DB is at the 2026-09-01 baseline plus deliberate changes (5 application histories backfilled with a `→ applied` edge, 105 `applied→applied` self-loops left in place). Scratch rows are always `ZZTEST*` and are cleaned at the end of every script.
- Tools: `tools/h.py` (harness), `tools/console_sweep.py` (all routes × themes), `tools/lh_scan3.py` (fractional-row scan), `tools/report_gen.py` (recount + REPORT.md).

## Data notes
- 2026-09-03: stripped the 105 `applied→applied` self-loop transitions (one per application, 105 applications) on the user's call; dump taken first at `backups/pre_selfloop_strip_20260903.dump`. After: 0 self-loops of any status, Sankey 5 links, KPI 377 applications. The one application with two edges into `applied` (`034999a5…`, an `interview → applied` revert done in the UI) is a real transition and was kept.
