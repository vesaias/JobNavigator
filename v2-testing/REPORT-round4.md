# Round 4 — deep pass before the v2 release · REPORT

Branch `v2-redesign`, 2026-09-05, one day. Plan: `ROUND4-PLAN.md`. Findings: `round4/T0.md` … `T6.md` (one `**Status**` line each), fix verification `round4/verify-fixes.md`, screenshots under `artifacts/round4/`. Baseline dumps: `backups/round4_baseline_20260905.dump`, `backups/pre_dedup_backfill_20260905.dump`.

## Totals

| track | findings | fixed | closed | deferred (v2.1) |
|---|---:|---:|---:|---:|
| T0 fresh install + upgrade | 2 | 2 | – | – |
| T1 backend contract/robustness | 29 | 19 | 1 | 9 |
| T2a Feed/Searches/Companies/Applications | 19 | 12 | – | 7 |
| T2b Résumés/Letters/Persona/Stats/Settings/shell | 13 | 11 | – | 2 |
| T3 visual, PDFs, browsers | 10 | 7 | 3 | – |
| T4 soak | dropped by decision | | | |
| T5 security/ops | 12 | 9 | 3 | – |
| T6 test debt (e2e findings) | 5 | 5 | – | – |
| **total** | **90** | **65** | **7** | **18** |

No P1 survived. Every `fixed` item was re-verified live on the final build (26 frontend/PDF ids in `verify-fixes.md`; backend ids by their formerly-xfail tests now passing).

## What was found and fixed (highlights)
- **Install/upgrade**: the seed migration list aborted on its first statement on a fresh DB (now per-statement savepoints, `jsonb` cast fixed); the welcome modal could never appear on a keyless first run. Upgrade from the April 2026 dump: clean.
- **Backend**: negative `limit` was a 500 on seven endpoints; one bad id failed a whole bulk update; four endpoints 500ed on non-string fields; linkedin-import iterated a bare string per character; the streaming autofill ignored the editable prompt; an LLM outage still marked the run "completed". Dedup: trailing slash, `www.`, scheme and param order created duplicate jobs — the identity hash now folds them (stored URLs untouched); 6,842 existing rows backfilled after a dump (`round4/dup-report.md`).
- **Frontend**: Feed detail actions clipped at 1024; Applications blank while loading; Settings 1024 layout race (observer never constructed on 1 in 7 loads, now 20/20); reload during a letter regenerate lost the run; a failed load wrote zeros into the warm cache; menus' outside-click fired the control beneath; Searches Test result lost on reload; infinite scroll dropped rows (client dedupe; the backend tiebreaker is deferred); the ⧉ glyph was tofu; rail health dot green with the backend down; invisible focus ring on the dark rail; Escape could not close the welcome modal over the Feed.
- **Visual**: résumé PDFs orphaned a last line onto a blank page (print-only rules: 8 of 23 two-page exports now one page, page 1 unchanged); Win98 `Button` bevel and four uppercase leaks; themed slim scrollbars; Win98 link blue and dark selected-row contrast.
- **Security/ops**: résumé template name was a path-traversal vector (whitelisted); iframes sandboxed without `allow-same-origin`; Telegram token no longer logged by httpx; per-IP throttle on the auth endpoints; `nosniff` / `frame-ancestors 'self'` / referrer policy via Caddy; tracer tokens from `secrets`; `tel:`/`mailto:` links no longer rewritten; log rotation 20 MB × 5 on every container.

## Decided / closed
T1-15 backwards status move stays (stepper is the reopen affordance) · T1-29/T5-05 backups keep secrets, documented in README, local-only · T3-04 Firefox clean, WebKit not runnable in the container · T3-07 selected-row tint kept · T5-10/11 logout without key and public `/docs` by design · T4 soak dropped.

## Deferred to v2.1 (18)
Two-tab live convergence (T2A-06, T2B-12); widths under 1000 px (T2A-03/04, T2B-04 partial); dirty-guard on Escape in Add company (T2A-13); backend sort tiebreaker for infinite scroll (T2A-11 backend half) and registering Searches Test runs with the monitor (T2A-07 backend half); T1 P4 validation nits (05/06/16/17/18/21/25/26/27); T2B-11/13; T2A-10/16–19.

## Test infrastructure now in place
- Backend: **2175 passed, 14 xfail-strict** (deferred ids pinned). Coverage 75.7 % → 78.8 %; round-4 modules at 100 %. `pytest-cov` report `round4/coverage-after.json`.
- Frontend: Vitest in Docker, **160 tests** (`bash v2-testing/tools/fe-test.sh`): cron describer table, storage migration, `useWarm`, helpers.
- E2E: `bash v2-testing/e2e/run.sh` — **16 cases, 14 pass, 2 skip without `JN_E2E_LIVE=1`** (real scrape / real H-1B lookup).
- Gates: lint 0 (67 annotated keeps); frozen pixel + style gate `R4_2` vs `R4_1`: 0 changed style tuples, pixel diffs only data (`tools/gate.sh`); crawler hover artefact fixed (D-19).

## Incident
During e2e development a faulty row locator deleted the user's "JobSpy" search through the UI. Restored from `pre_dedup_backfill_20260905.dump` with the original id and timestamps, verified against the baseline dump; three guards added to the suite (`round4/T6.md`).

## Follow-ups outside this round
- Design round for Cobalt vs SaaS differentiation and Win98 depth (98.css reference): inputs in `round4/T3.md` "Design brief input".
- v2.1 list above plus the open items in `round-design/DECISIONS.md` (all decided; the file is the log).

DB: live throughout (read-only except named `ZZR4…`/`ZZE…` rows, all deleted, and the intended backfill). Nothing pushed.
