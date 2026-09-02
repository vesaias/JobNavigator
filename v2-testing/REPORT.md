# v2 verification pass — REPORT

Branch `v2-redesign`, 2026-09-01 → 2026-09-02. State files: `PLAN.md` (stages), `FINDINGS.md` (cross-cutting F-nnn), `stage3/<screen>.md` (per-screen findings), `stage4/settings-roundtrip.md`, `stage5/cross-cutting.md`, `stage3/REVERIFY.md` (post-rebuild confirmation), `inventory/` (every route, control, endpoint and settings key), `artifacts/` (gitignored raw JSON + screenshots).

## Totals

| Severity | Total | Fixed | Needs your decision | Logged only |
|---|---|---|---|---|
| P1 | 5 | 5 | 0 | 0 |
| P2 | 70 | 26 | 42 | 2 |
| P3 | 111 | 14 | 94 | 3 |
| P4 | 90 | 3 | 75 | 12 |
| **All** | **276** | **48** | **211** | **17** |

| Area | Findings | P1 | P2 | P3 | P4 | fixed |
|---|---|---|---|---|---|---|
| F-009-linheights.md | 0 | 0 | 0 | 0 | 0 | 0 |
| applications.md | 23 | 0 | 7 | 10 | 6 | 3 |
| companies.md | 37 | 1 | 12 | 16 | 8 | 4 |
| cover-letters.md | 29 | 0 | 7 | 14 | 8 | 6 |
| feed.md | 38 | 0 | 10 | 18 | 10 | 4 |
| persona-stats.md | 45 | 1 | 10 | 13 | 21 | 3 |
| resumes-shelf-recheck.md | 0 | 0 | 0 | 0 | 0 | 0 |
| resumes.md | 31 | 1 | 8 | 13 | 9 | 4 |
| searches.md | 29 | 0 | 6 | 11 | 12 | 7 |
| settings.md | 27 | 2 | 4 | 12 | 9 | 9 |
| shell.md | 6 | 0 | 0 | 2 | 4 | 2 |
| FINDINGS.md | 10 | 0 | 6 | 2 | 2 | 6 |
| cross-cutting.md | 1 | 0 | 0 | 0 | 1 | 0 |

## The five P1s — all fixed and re-verified on the rebuilt bundle
- **COMP-01** — Drawer `Save changes` closes before the PATCH resolves — a failed save loses the edit silently
- **PERS-01** — A non-list `qa_bank` white-screens the whole app
- **RES-01** — A rejected autosave is completely silent — the status line still says "saved just now"
- **SET-01** — Typing after a revealed secret mask saves `••••••<typed>` and destroys the stored secret
- **SET-03** — "Save key" writes the new API key locally and refreshes the session cookie even when the PATCH failed → dashboard lockout

## Fixed in this pass (source, then verified live or on the rebuilt bundle)
- APPS-03 (P2) — Interview time is stored as UTC and rendered as local — off by the viewer's UTC offset
- APPS-04 (P2) — `POST /applications` upserts by job — re-logging the same posting silently overwrites the earlier application
- APPS-08 (P3) — Every list row lands on a fractional pixel — **fixed in source**
- COMP-01 (P1) — Drawer `Save changes` closes before the PATCH resolves — a failed save loses the edit silently
- COMP-11 (P2) — The alias badge under-reports by one, and a company with exactly one alias shows no badge at all
- COMP-14 (P3) — Every row lands on a half pixel (fractional `getBoundingClientRect().top`)
- COMP-15 (P3) — The sort menu's hover never fires — an inline `background: 'transparent'` beats `.v2-menuitem:hover`
- CL-01 (P2) — Editor autosave silently drops a patch of a different kind — the template you picked is never saved and the header says "saved"
- CL-02 (P2) — Editor gets permanently stuck in "Regenerating…" if the post-run reload fails
- CL-03 (P2) — Regenerate poll waits for *every* cover-letter run in the system, not this letter's
- CL-04 (P2) — `?job=` deep-link silently loses its selection for any job outside the saved/applied window
- CL-09 (P3) — Pending row is 46.75 px tall, so every letter row below it lands on a half pixel
- CL-10 (P3) — Editor: the `text · link · stub` hint is 15.75 px tall and pushes the Recipient and Letter cards onto half pixels
- FEED-01 (P2) — The default view labels every row in the database "open roles"
- FEED-02 (P3) — Every list row lands on a half pixel; 1px borders drop on alternating rows
- FEED-03 (P2) — The filter bar does not wrap; at 1024 px the Sort control is off-screen
- FEED-04 (P2) — Sort-menu items have a dead hover
- PERS-01 (P1) — A non-list `qa_bank` white-screens the whole app
- PERS-02 (P2) — `PATCH /api/persona` silently dropped every order-only write — Skills ▲▼ did nothing
- PERS-11 (P3) — Experience entry headers are 36.75 px tall, putting five rows on a half pixel
- RES-01 (P1) — A rejected autosave is completely silent — the status line still says "saved just now"
- RES-03 (P2) — "Import PDF" creates **two** base résumés
- RES-10 (P3) — Shelf: every other card and row landed on a half pixel — **fixed**
- RES-12 (P3) — The Template and Paper dropdown items had no hover at all — **fixed**
- SRCH-01 (P2) — Test-modal source chips never render — the modal reads `by_source`, every backend path sends `source_breakdown`
- SRCH-02 (P2) — A preview that fails with HTTP 200 + `{"error": …}` is rendered as “No results returned.”
- SRCH-03 (P2) — A 422 from `POST /searches` alerts “[object Object]”
- SRCH-04 (P2) — `Toast.jsx` was never imported — toggleActive, runNow, delete and duplicate failed with zero user-visible feedback
- SRCH-05 (P2) — No loading and no error state for the list — a failed GET renders “No searches yet · 0 configs”
- SRCH-06 (P2) — A 409 from Run clears the spinner although the run really is in flight
- SRCH-07 (P3) — Every card in the list lands on a half pixel
- SET-01 (P1) — Typing after a revealed secret mask saves `••••••<typed>` and destroys the stored secret
- SET-02 (P2) — An unset secret renders as six bullets, identical to a set one
- SET-03 (P1) — "Save key" writes the new API key locally and refreshes the session cookie even when the PATCH failed → dashboard lockout
- SET-04 (P2) — "Reset to default" on a list editor saves a one-element list containing the seed's JSON text
- SET-05 (P2) — "Reset to default" wipes a prompt to `""` when `GET /settings/defaults` is unavailable
- SET-07 (P3) — A failed webhook registration flashes in accent green, reading as success
- SET-09 (P4) — Two saves inside 2.2 s: the first flash's timer clears the second message early
- SET-10 (P3) — "Submit PIN" has no catch — a 401/500/network error is an unhandled rejection with no feedback
- SET-19 (P4) — Two section headers rendered with no subtitle
- SHELL-01 (P3) — Every rail hover is dead (inline colour beats `.v2-navdark:hover`)
- SHELL-03 (P4) — Welcome step rows land on half pixels
- F-001 (P2) — Feed · Tailored-résumé ✦ mark in the list row leaves v2 for the classic UI
- F-002 (P2) — Companies → Feed · "View in feed" passes `?company=` but the Feed never reads it
- F-005 (P2) — Stats (v1 + v2) + backend · Per-search "Run" in the scheduler table posts a path that does not exist
- F-007 (P2) — Backend · Any non-UUID id in a path returns 500 instead of 404
- F-008 (P2) — Backend · Order-only edits to dict-shaped JSON columns were silently dropped (Résumé + Persona skills ▲▼)
- F-010 (P3) — Feed · First-run (empty database) shows the filter-miss copy instead of a first-run state

### Cross-cutting fixes not tied to one finding id
- Toast system mounted on Searches, Companies, Applications, Persona and Stats (every failure there was console-only); Searches' helper used `text:` instead of `msg:` (blank toasts) — fixed.
- Six dead hover rules in `theme.css` hardened with `!important` (rail, menu items, anchors, navlinks, `.v2-hover-accent`), plus a `--rail-hover` token for the footer ◐.
- Backend: `DataError` → 404 handler for malformed ids on every route; `flag_modified` on Résumé and Persona JSON PATCHes; `create_company` persists `aliases` + `auto_scoring_depth`; per-search `trigger_url` pointed at a real endpoint.
- Docs: HANDOVER and CLAUDE.md said the backend hot-reloads — it does not (no `--reload`); corrected.

## Open P2s that need you (44)
- APPS-01 — No user feedback on any of the nine mutations — 8 console-only failure paths + 1 swallowed catch
- APPS-02 — A failed load is indistinguishable from an empty database
- APPS-05 — "Copied ✓" is shown even when the clipboard write fails
- APPS-06 — The interview draft form is screen-global, not per application
- APPS-07 — Clicking the already-active stage, editing notes, or adding an interview bumps `updated_at` and clears the stale indicator
- COMP-02 — Drawer's `company` object is never refreshed, so the banner / tuning note / subtitle go stale while the drawer is open
- COMP-03 — The list has no loading and no error branch — a failed `GET /companies` renders as "you have no companies matching your search"
- COMP-04 — `Toast.jsx` is never imported — nine of eleven failure paths and every success path are silent
- COMP-05 — `Run` uses a fixed 2600 ms timer instead of `/monitor/active`; the UI reports "done" while the scrape is still going
- COMP-06 — `/health/entities` and `/monitor/active` are fetched once on mount and never refreshed
- COMP-07 — `Needs attention` sort and the header count ignore `last_error`, which the row `▲`, health text and drawer banner all honour
- COMP-08 — `Apps` is name-only while `Open`, `+7d` and `Ø Fit` are alias-summed; and the column means *all* applications
- COMP-09 — `⋯ → View jobs in feed` is a raw `<a href>` that full-page-reloads into an *unfiltered* feed
- COMP-10 — At 1024 px the toolbar overflows and the `Sort` control is pushed off-screen with no way to reach it
- COMP-12 — `Pages to read` and `Scrape interval` accept any integer — the `min`/`max` are HTML-only
- COMP-13 — Résumés cell claims "Selected" while the drawer says "Nothing selected" when the résumé list is unavailable or the ids dangle
- CL-05 — A failed list load is rendered as "No cover letters yet"
- CL-06 — A background generation that fails looks exactly like one that succeeded
- CL-07 — An open Picker popover covers the other Picker's control; clicking the second control picks an option from the first
- FEED-05 — "Unscored jobs stay visible — this only hides low scores" is false
- FEED-06 — "Jobs without a listed salary stay visible" is false
- FEED-07 — Skip / Mark-applied announce success before the PATCH resolves, and stay wrong when it fails
- FEED-08 — "Ignore {company} everywhere" is destructive with no confirm, no toast and no undo
- FEED-09 — A bad `?job=` id silently opens a different job
- FEED-10 — `GET /api/jobs/{non-uuid}` returns 500 (backend)
- FEED-11 — A failed job list is indistinguishable from an empty one
- PERS-03 — The Skills value box is dead for any category containing a dot
- PERS-04 — Renaming a skill category onto an existing name silently destroys that category's value
- PERS-05 — A failed save is completely invisible
- PERS-06 — Any load failure leaves the screen on `Loading…` forever
- PERS-07 — A legacy multi-key `qa_bank` entry loses every key but the first, permanently
- PERS-08 — Navigating away within 500 ms of the last keystroke drops that edit silently
- STAT-01 — A refused or failed trigger is indistinguishable from a successful one
- STAT-02 — "Best open score" renders the literal string `-Infinity`
- STAT-03 — With every endpoint failing, the screen renders a plausible-looking dashboard
- RES-02 — Skills ▲▼ reorder was never persisted — the UI showed the new order until reload, then snapped back
- RES-04 — A skills category containing a "." makes its value field inert
- RES-05 — Renaming a skills category onto an existing one silently destroys a row
- RES-06 — The "one next step" CTA can never get past "Review N changes"
- RES-07 — A failed shelf load is rendered as "No base résumés yet"
- RES-08 — PDF render failure leaves a stale preview with no signal
- RES-09 — A base résumé cannot be deleted anywhere in v2
- SET-06 — A failed `GET /settings` renders a permanently blank pane — no message, no retry
- F-006 — Backend / docs · Backend edits do not hot-reload, but HANDOVER and CLAUDE.md say they do

## Decisions that close many findings at once
1. **Half-pixel rows (F-009)** — a systematic line-height pass (~40–60 one-line edits) or accept as backlog. Closes the FEED-02 residue, SRCH-07, APPS-08, CL-09/10, PERS-11.
2. **Design-vs-code deviations (~110 P3/P4)** — most look like your deliberate consistency choices (unified accent hovers, lifted rail dim, widened Settings rows, 980 vs 880 px modals). A yes/no per screen report closes them.
3. **`--reload` in the backend Dockerfile (F-006)** — dev convenience vs prod behaviour.
4. **Feed first-run copy (F-010)** and the `open roles` label over an unfiltered list (FEED-01).
5. **Interview time stored as UTC (APPS-03)** — one-line client fix that changes the wire format.
6. **`POST /applications` upsert-by-job (APPS-04)** silently overwrites notes/stage on re-log.

## Verified clean (no finding)
- 587 backend tests green before and after all backend edits.
- Console clean on 23 routes × 2 themes on the real DB and again on an empty DB (46 + 46 loads).
- All 74 mutable settings keys round-trip and bind; 7 timing keys reach the scheduler.
- Every rail/header/Stats count agrees; background jobs return 409 on duplicate, survive navigation, and are marked failed on restart.
- v1 routes load without errors on the shared backend after every backend change (Stage 6).

## Couldn't test (48 items, from the screen reports)
- BRIEF: item — why
- applications: **"Building the bundle…" loading state** (`:523`) — the prep endpoint returned in <300 ms even on the first call, so the loading text never rendered long enough to sample. Verified by code inspection only.
- applications: **"Posting URL · reading…"** (`:588`) — same: the real extract resolved before the DOM could be sampled, and a route-fulfilled stub is instantaneous. Verified by code inspection only.
- applications: **Empty company popover** (`:243`, "empty 240 px box") — unreachable: 122 companies in the real DB and no way to reach zero without an empty database. Deferred to the empty-DB pass.
- applications: **`ghosted`/`withdrawn` legacy rows** — none exist; the "invisible but counted" behaviour is reasoned from `STAGES` (`:35-40`), not observed.
- applications: **>2000 applications truncation** — 378 rows; latent only.
- applications: **Empty `data.text` from `/prep`** (`:523`) — the endpoint always returns a bundle; unreachable without stubbing.
- applications: **Résumé chip list empty / errored** (`:551`, `:606`) — 4 base résumés exist and the error path is the swallowed `.catch(()=>{})` already logged under APPS-01.
- applications: **Detail eyebrow with no company** (`:362`, no `Unknown Company` fallback) — unreachable: all 378 rows have a company.
- applications: The 404 seen once on `/v2/feed` after the deep-link hop belongs to the Feed screen, not this one.
- companies: **`total_rejected > 0` in the test modal** — `[Validation]` rejects only come from the Playwright DOM extractor (`_extract_all_pages`), not from the ATS API paths. The only companies wired to a generic Playwright board are the user's real ones, and pointing a scratch company at a third-party HTML careers page for a multi-page render was out of scope for a dry run. The summary fix is verified against the backend's contract instead.
- companies: **Tier-only empty state** (`No companies in the selected tiers.`) — all four tier buckets have rows in this database (5 / 21 / 35 / 65), and any search term routes the copy to the query variant instead. Verified by code path only.
- companies: **Empty-database rendering** — out of scope per the brief (separate later pass).
- companies: **`.v2-hover-accent` colour fix** — the correct fix is a one-line `!important` in the shared `theme.css`, which nine screens and several concurrently-running agents are measuring against. Left to the coordinator (COMP-16).
- companies: **Scrollbar-driven layout** — headless Linux uses overlay scrollbars (width 0), so the `.v2-scroll` gutter behaviour on the rows container and the drawer body could not be reproduced (HANDOVER, "Traps in the harness itself").
- companies: **`h1b_approval_rate` scale** — the drawer only prints `{rate}% approved` when the value is truthy, and every company in this database stores either `0.0` or a 0–100 percentage, so a 0–1 fraction (which would print `0.95% approved`) never appeared. Unverified, as the inventory suspected.
- cover-letters: **PDF viewer chrome** (zoom / print / in-viewer download, and the dark-mode seam around the rendered page) — headless Linux has no PDF plug-in; the `<iframe>` is created with a valid blob URL but renders nothing, so the design's paper-vs-`--surface-2` seam could not be judged.
- cover-letters: **`ago()` with a null `updated_at`** (would render `edited  ago` with a double space) — `CoverLetter.updated_at` is server-defaulted and non-null; no way to produce the row without direct SQL.
- cover-letters: **Rail-badge agreement with `/v2/applications` and the Stats KPIs** — cross-screen; only the value produced by this screen's endpoints was checked.
- cover-letters: **Scrollbar-gutter behaviour** of `.v2-gutter`/`.v2-gutter-head` — overlay scrollbars are 0 px wide in this container (HANDOVER).
- cover-letters: **`generate` 400 branches** `Persona has no resume_content` and `cover_letter_prompt setting is empty` — both would require mutating real settings/persona rows; the sibling 400 (`Job has no description` path via a dead job id → `Job not found`) and the 409/500/network branches were exercised instead, and they share the same rendering code (`CL:241` → `CL:320`).
- feed: Row ✦ tailored link and "✦ Open tailored ↗" at runtime — no scratch row could be given a real
- persona-stats: **Rebuild-dependent:** the `ResumeSections.jsx` line-height fix and the two `theme.css` `!important` hover fixes are source-only; the served bundle still has the old behaviour, so PERS-11, PERS-12 and STAT-08 need a re-measure after the wave rebuild.
- persona-stats: **Non-UTC timezone (STAT-15):** the container runs UTC and the harness's `context()` exposes no `timezone_id`, so the UTC-vs-local date-key drift is reasoned from code, not measured.
- persona-stats: **Scrollbar-gutter behaviour** on the LLM cost table (`.v2-gutter` / `.v2-gutter-head`) and `.v2-scroll` styling on both screens: headless Linux uses overlay scrollbars (width 0) — documented harness trap.
- persona-stats: **Real trigger execution:** every `Run now` POST was intercepted by design; the 202 path was verified as a UI state, not as an actual scheduler launch. Live trigger behaviour is Stage 5.
- persona-stats: **A genuinely running scheduler job:** none ran during the pass, so `Running · {n}s` with real `elapsed_seconds`, the 3 s fast-poll cadence and the `now` Next-run cell were exercised through interception and the `triggering` path only.
- persona-stats: **Sankey link hover / Recharts tooltip content:** both tooltips render and are token-styled, but their content was not asserted.
- persona-stats: **Persona tailoring-diff affordances** (`↩` revert on summary/bullet/skill, the `added` tag, the `●` unreviewed marker): Persona deliberately passes no `baseData`, and the live record carries no `suggested_bullets`, so these never render here.
- persona-stats: **Legacy-typed bool/enum values** (a `work_auth` bool holding `'yes'`, an enum outside `options`) and **concurrent-edit / stale-write**: not injected this pass.
- resumes: **Real tailoring / real PDF import** — both are LLM calls. The tailor flow was exercised end-to-end with `POST /resumes/tailor` intercepted (202 + a stubbed `/resumes?is_base=false` row) so the pending watcher, both toasts and "Open ↗" were verified; the review flow was exercised against a hand-crafted diff that reproduces the four change kinds the tailor emits. The import duplicate (RES-03) is proven from the client side (two POSTs) plus the backend's own commit at `routes_resumes.py:1152-1161` — no LLM call was spent. **0 real LLM calls used.**
- resumes: **PDF pixels** — headless Linux has no PDF viewer, so the iframe cannot be read. Verified instead through the API (status, `application/pdf`, `%PDF-` magic, byte length, `Content-Disposition`) and by watching the re-render requests fire with the right query string.
- resumes: **Archived-view-empty branch** — needs an in-flight tailor to finish while the archived list is open and the set drops to zero; not reachable without a real tailor run. Logged from code as RES-29.
- resumes: **Rail badge going stale mid-session** — the rail fetches its counts once (`V2App.jsx:57-72`); after deleting a base the number only corrects on reload. Already logged cross-screen as SRCH-10, not duplicated here.
- searches: **A real preview against a live board.** The Test flow's network half (`levels_fyi`, `jobright`, `linkedin_personal`, `freehire`) is off-limits under the data rules; every Test path was exercised with route interception using payload shapes copied from `routes_searches.py` / the source modules. Sync-200, 202+poll, poll-404, 400 and 500 were all covered.
- searches: **A real search run.** `POST /run` was fired only against a scratch search whose config `_search_mode_is_valid()` rejects (no external work) and against the two extension searches (no-op by the same guard). The spinner lifecycle was driven by intercepting `/monitor/active`.
- searches: **`DELETE` on the seeded extension searches** — explicitly forbidden by the brief, so the backend's missing guard there is inferred from `routes_searches.py:93-100`, not measured.
- searches: **The StrictMode `mounted.current` trap** (inventory §7, `:311-312`) is a dev-server-only behaviour; the Docker bundle is a production build, so it cannot be reproduced here. Confirmed harmless in production by the working 202+poll run.
- searches: **Two concurrent Tests** (SRCH-23) — would need two live previews.
- searches: **Empty-database rendering** — a separate later pass per the brief.
- settings: **`awaiting_pin` PIN entry** (`Settings.jsx:608-620`) — the live LinkedIn session is `status: stale`, `phase: idle`, so the PIN input and its Submit button never render, and driving a real refresh is out of scope (no LinkedIn contact). SET-10 comes from reading the code; the fix is unverified at runtime.
- settings: **The 2.5 s `GET /linkedin/session` poll** (`:587-593`) — same reason: the poll only starts after a refresh that reaches `running`.
- settings: **Non-numeric interval → backend boot failure** (SET-27) — writing `abc` into `scrape_interval_minutes` would leave the user's backend unable to start (`main.py:52` → `scheduler.py:29`, unguarded `int()`). Verified by reading only.
- settings: **A real key rotation** — `POST /telegram/rotate-webhook-secret` and a real `dashboard_api_key` change were intercepted; both would have invalidated live credentials. `md5` of both rows was confirmed identical before and after.
- settings: **Fresh-install counts** (inventory §8: "45 models · 45 seeded · 0 added by you", a 78-key `/settings/defaults`) — the live DB holds 44 catalog entries and 86 settings rows including 8 runtime/legacy keys. Empty-DB rendering is a separate later pass.
- settings: **Live catalog error paths for OpenAI / Claude** (`routes_llm.py:117` 400 when no key, `:135-143` 502) — `llm_api_key` is empty on this install and firing a real provider call to prove a 400 was not worth a request. The OpenRouter path (no key needed) was exercised and returned 421 models.
- shell: Retry action on error toasts at real failure sites (design: "carries Retry when retryable") — per-screen agents check their own failure sites.
- shell: Rail with zero counts / no health history — Stage 3b (empty DB).

## Data
Real DB used throughout; every agent's scratch rows deleted (0 `ZZTEST` rows at each wave end). The overnight scheduled cleanup deleted 69 stale skipped jobs (normal). **Final step: restored from `backups/v2testing_baseline_20260901_2345.dump`** — see PLAN Stage 7.

## Not done / deferred
- Résumés design fidelity was measured against `Resumes Home D`; you named `Resumes Shelf` canonical afterwards — the RES P3 geometry items need a re-check against Shelf (decoded to `design/Resumes Shelf.dc.html`).
- The `/v2/toasts` lab page and route are still present (your call to delete).
- Real LLM runs: 2 accidental scores (Feed) + 1 generation + 1 regenerate (Cover Letters); no tailor run — the tailor pending→review flow was verified with interception only.
