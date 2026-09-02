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
- [ ] Settings matrix → `inventory/settings-matrix.md`
- [x] Design boards decoded → `design/` (14 boards byte-exact + MAIN.md + github.md). Note: MAIN.md names `Resumes Shelf` canonical for Résumés while HANDOVER names `Resumes Home D`; github.md names `Applications Ops` (split inbox) canonical while MAIN.md lists Applications as open. Testing follows the HANDOVER table.
- [ ] Commit

### Routes
v2 (shell `V2App`, `/v2` → redirect `feed`): `/v2/feed` · `/v2/searches` · `/v2/companies` · `/v2/applications` · `/v2/resumes` · `/v2/resumes/:id` · `/v2/cover-letters` · `/v2/cover-letters/:id` · `/v2/persona` · `/v2/stats` · `/v2/settings` · `/v2/toasts` (ToastLab, temporary, outside the shell)
v1 (`ClassicShell`): `/` · `/applications` · `/companies` · `/searches` · `/settings` · `/resumes` · `/cover-letters` · `/persona` · `/stats`
Backend-served: `/health` · `/docs` · `/redoc` · `/openapi.json` · `/cv/{token}` · `/?cv=`

## Stage 2 — Static sweeps
- [x] Dead links: 46 targets checked; 2 defects → F-001 (v1 route), F-002 (`?company=` unread). `/docs` + GitHub external OK; `/api/...` hrefs rely on the `jn_session` cookie set by App.jsx startup sync
- [ ] No-op handlers (onClick without effect, handlers never attached)
- [x] Colour literals: 0 in v2 JSX. Tokens: 10 unused (F-003), 5 shadows without dark (F-004); every `var(--x)` used in JSX is defined
- [x] Console sweep, 23 routes × 2 themes → `artifacts/sweep1/` (gitignored). Clean except: Feed mounts the posting iframe while the frame-check is still pending (XFO refusals logged; Stage 3 Feed item); PDF blob aborts in headless are expected
- [ ] Commit

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

**PAUSED HERE 2026-09-02 ~14:40 at the user's request.** Next: wave-level frontend rebuild → re-verify every 'fixed in source (rebuild pending)' item → Stage 3b empty-DB sweep → Stage 4.

## Stage 4 — Settings round-trip (every key: API read → type-valid write → read back → UI shows it → takes effect → restore)
- [x] All keys → `stage4/settings-roundtrip.md` (74/74 persist + restore; 7/7 scheduler; 58/58 visible controls show the value)
- [ ] Commit

## Stage 5 — Cross-cutting
- [ ] Counts that must agree (rail vs list vs Stats vs feed header vs company apps)
- [ ] Background jobs: navigate away mid-run, duplicate launch → 409, backend restart mid-run
- [ ] Deep links to missing ids (`?job=`, `?resume=&job=`, `/v2/resumes/:id`, `/v2/cover-letters/:id`)
- [ ] Toasts: error kind at every failure site, never auto-dismiss
- [ ] Keyboard shortcuts
- [ ] Narrow viewports
- [ ] Commit

## Stage 6 — v1 regression
- [ ] Every v1 screen loads, every endpoint it uses still responds with the expected shape
- [ ] Commit

## Stage 7 — Report
- [ ] Totals by severity, fixed vs needs-you, untestable
- [ ] Restore real DB from baseline dump; verify counts
- [ ] Commit
