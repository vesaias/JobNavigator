# v2 verification pass — FINDINGS

Entry format: `### F-NNN · P{1-4} · {screen} · {title}` then **Where** (file:line + route) · **Repro** · **Expected + why** (cite design `.dc.html` or v1 code) · **Actual** (measured) · **Proposed fix** · **Status** (fixed in {commit} | needs decision: {question}).

## Totals
(filled at Stage 7)

## Entries

### F-001 · P2 · Feed · Tailored-résumé ✦ mark in the list row leaves v2 for the classic UI
**Where** `frontend/src/v2/JobFeed.jsx:766`, route `/v2/feed`
**Repro** Open the feed, find a row with the green ✦ (any job with `tailored_resume_id`), click it.
**Expected + why** Opens `/v2/resumes/{id}` in the v2 editor — every other tailored-résumé link in the file (`JobFeed.jsx:381,382,556`) navigates to `/v2/resumes/${id}`; the design's master board has no hand-off to the classic UI.
**Actual** `href="/resumes?resume={id}"` — a full page load into the v1 Résumé Builder.
**Proposed fix** `href="/v2/resumes/{id}"` + `navigate()` on click (keeps middle-click/open-in-new-tab working).
**Status** fixed in Stage 2 commit.

### F-002 · P2 · Companies → Feed · "View in feed" passes `?company=` but the Feed never reads it
**Where** `frontend/src/v2/Companies.jsx:393` (link) → `frontend/src/v2/JobFeed.jsx:110-113` (filter init), routes `/v2/companies` → `/v2/feed`
**Repro** Companies → any row ⋯ → "View in feed".
**Expected + why** Feed opens filtered to that company (the menu item says so; the Companies Ops design's row menu item is "View in feed"). `?search=` from Searches is honoured the same way at `JobFeed.jsx:179`.
**Actual** Feed initialises `filters.company` from localStorage only; the param is ignored and the unfiltered feed shows. Measured: `grep "get('company')"` → 0 hits before the fix.
**Proposed fix** Read `?company=` in the filters initializer and set `company: [name]`. Caveat: `JobFeed.jsx:501` prunes any company not present in `/jobs/companies/list`, so a company with no jobs in the feed silently drops back to "all companies" — worth a "no roles for X" state (logged as a follow-up in Stage 3 Feed).
**Status** fixed in Stage 2 commit.

### F-003 · P4 · theme.css · 10 tokens defined but never used
**Where** `frontend/src/v2/theme.css:60,67-69`
**Repro** For each `--name:` in theme.css, `grep -o "var(--name)"` across `frontend/src` → 0 hits for: `--accent-bg --border --border-lt --danger --danger-bg --ink --panel --stone --warn-bg` (the back-compat aliases) and `--paper` (defined in both light `:60` and dark `:117`).
**Expected + why** HANDOVER lists the 9 aliases as known; `--paper` is new to this sweep. Dead tokens make the "one theme = replace this list" promise wrong by 10 entries.
**Actual** 10 unused.
**Proposed fix** Delete the 9 alias lines and `--paper`, or wire `--paper` to the PDF-preview iframe ground (`--iframe-bg` already does that). Needs a decision only on whether the aliases are kept for the planned skin work.
**Status** needs decision: delete now, or keep until the primitive layer lands?

### F-004 · P4 · theme.css · 5 shadow tokens have no dark variant
**Where** `frontend/src/v2/theme.css:27-29` (light only)
**Repro** `sed -n 74,118p theme.css | grep shadow` → 0 hits.
**Expected + why** Dark surfaces sit on `#1e1c17`; a `rgba(0,0,0,.16)` menu shadow is nearly invisible there, so menus/drawers/modals lose their edge separation in dark mode. HANDOVER flags this as outstanding.
**Actual** Same light shadows in both themes.
**Proposed fix** Add dark overrides with higher alpha (e.g. `.28 → .55`, `.16 → .4`) and verify by measuring the pixel delta at a menu edge in dark.
**Status** needs decision (design choice — I can propose values and measure).

### F-005 · P2 · Stats (v1 + v2) + backend · Per-search "Run" in the scheduler table posts a path that does not exist
**Where** `backend/main.py:854` (`trigger_url`), consumed by `frontend/src/v2/Stats.jsx:162` and `frontend/src/components/Stats.jsx:515`; routes `/v2/stats`, `/stats`
**Repro** Stats → Schedules → any "Search: …" row with a per-search interval → Run.
**Expected + why** Triggers the search (`POST /api/searches/{id}/run`, `routes_searches.py:103`, the endpoint Searches' own Run button uses).
**Actual** `POST /api/scrape/search/{id}` → measured `404` via curl. v2 swallows it (`console.error('trigger', e)`, no toast); v1 shows nothing either.
**Proposed fix** Point `trigger_url` at `/searches/{id}/run`.
**Status** fixed in backend; no search currently has a per-search interval so the row is absent from `/api/scheduler/jobs` — live verification deferred to Stage 3 Searches (set `run_interval_minutes` on a scratch search). The silent-failure UX in v2 Stats is logged separately under Stage 3 Stats.

### F-006 · P2 · Backend / docs · Backend edits do not hot-reload, but HANDOVER and CLAUDE.md say they do
**Where** `Dockerfile.backend:37` (`CMD uvicorn backend.main:app --host 0.0.0.0 --port 8000`, no `--reload`); `HANDOVER.md` "Running things"; `CLAUDE.md` "Backend only (hot-reload via volume mount)"
**Repro** Edit any backend `.py`, call the endpoint: old behaviour. `docker inspect` shows the CMD without `--reload`; no WatchFiles line in the logs.
**Expected + why** Either the docs are right and the CMD carries `--reload`, or the docs say to restart. During this pass two "verified live" backend fixes (F-005 trigger_url, the Companies `create_company` aliases fix) were in fact not live until a manual restart.
**Actual** Measured: POST `/api/companies` with `aliases` after the source fix returned `aliases: []` until `docker compose restart backend`; afterwards the same POST returned the aliases.
**Proposed fix** Docs corrected in this pass (HANDOVER, CLAUDE.md, Stage 3 brief). Optionally add `--reload` for dev (`--reload-dir /app/backend`), but that changes prod behaviour — your call.
**Status** docs fixed; needs decision on `--reload` in the Dockerfile.

### F-007 · P2 · Backend · Any non-UUID id in a path returns 500 instead of 404
**Where** every `/{id}` route: `routes_jobs.py:517` and equivalents in resumes, cover-letters, applications, companies, searches, `main.py` monitor
**Repro** `curl /api/jobs/abc` (also `/api/resumes/abc`, `/api/cover-letters/abc`, `/api/applications/abc/prep`, `/api/monitor/run/abc`, `PATCH /api/companies/abc`, `DELETE /api/searches/abc`).
**Expected + why** 404 — `Job.id` is a UUID column; a malformed id can never match. The v2 editors deep-link by id, so a mistyped URL currently shows a generic failure instead of the "not found" state (FEED-10, RES/CL id checks).
**Actual** Measured `500` on all seven probes; only `/api/searches/test-result/abc` (in-memory dict) returns 404.
**Proposed fix** One `DataError` exception handler in `main.py` mapping Postgres "invalid input syntax for type uuid" to 404 (added; live after the next backend restart).
**Status** fixed + verified after the 14:03 restart: `/api/jobs/abc`, `/api/resumes/abc`, `/api/cover-letters/abc`, `/api/monitor/run/abc` all 404.

### F-008 · P2 · Backend · Order-only edits to dict-shaped JSON columns were silently dropped (Résumé + Persona skills ▲▼)
**Where** `backend/api/routes_resumes.py:972` (`update_resume`), `backend/api/routes_persona.py:66` (`update_persona`); surfaced by the v2 Résumé editor and Persona Skills reorder arrows
**Repro** `PATCH /api/resumes/{id}` with `json_data.skills` keys in a new order → 200, read-back shows the old order. Same for `PATCH /api/persona` `resume_content.skills`.
**Expected + why** The new order persists. SQLAlchemy's JSON type decides dirtiness by `old == new`; two dicts with the same pairs are equal regardless of key order, so no UPDATE is emitted. `POST /persona/qa-bank` in the same file already calls `flag_modified` for this reason.
**Actual** Measured by both screen agents at API level (no browser): order unchanged after PATCH; UI shows the new order until reload, then snaps back.
**Proposed fix** `flag_modified(obj, column)` after `setattr` for the JSON columns. Other PATCH routes (companies, searches, applications, jobs) assign list-shaped JSON, which compares in order and is not affected; `update_cover_letter` already flags `json_data` at `routes_cover_letters.py:460`.
**Status** fixed + verified live after the 14:03 / 14:09 restarts (Résumés and Persona agents re-ran their checks).
