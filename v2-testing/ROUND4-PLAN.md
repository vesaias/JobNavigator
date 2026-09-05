# Round 4 — deep pass before the v2 release

Approved 2026-09-05. Budget 5–7 M worker tokens (Opus for fixes and judgement, Sonnet for sweeps and verification; ≤4 agents at once; stop on API failure and report). Findings go to `v2-testing/round4/<track>.md`, one `**Status**` line per finding (`needs decision` · `fixed` · `decided` · `closed`), user triages, Opus fixes, Sonnet re-verifies live, one regression test per backend fix. Report: `REPORT-round4.md` from `tools/report_gen.py`. DB: `pg_dump` before any destructive step; `backups/round4_baseline_<date>.dump`; restore at the end.

Preconditions: polish pass (DECISIONS.md all decided) built and gated; `stylecrawl.py` hover fix (D-19) applied and a fresh baseline `R4_0` taken with the scheduler paused (`tools/gate.sh`).

## Tracks

**T0 · Fresh install + upgrade (Sonnet, 0.4 M)** — `compose up` on an empty volume in a scratch project name (`-p jn_fresh`, separate ports): seed, welcome modal, API key set, first search created and run, first score, extension pairing against it. Upgrade: restore the oldest dump in `backups/` into the scratch stack, start the new code, walk every screen and every settings section, note missing columns/defaults. Tear the scratch stack down.

**T1 · Backend contract + data robustness (Opus, 1.2 M)** — per router: generated bad input (wrong types, empty, 10 MB bodies, unicode, unknown ids, out-of-order status transitions, duplicate submits, 409 paths), each as a pytest in `backend/tests/test_r4_<router>.py`. Property tests for URL normalisation/dedup (20 spellings of one job, identity params kept, tracking params stripped). Concurrency: scheduler vs manual run on the same scope; container killed mid-run → stale-run recovery on restart. Failure injection: LLM 429/529/timeouts, Gmail token expiry, Telegram down. Backup → wipe → restore drill with count comparison.

**T2 · Frontend state matrix (Opus + Sonnet, 1.5 M)** — every screen × {empty, one row, thousands, error, loading, backend down, throttled network}; every modal, menu, shortcut, undo; refresh mid-run; back/forward; two tabs; pollers surviving navigation; an 8 h session with the scheduler firing (heap + timer counts sampled hourly); widths 1440 → 1024 → 900; **browser zoom 75 % → 110 %** (D-18); the Settings 1024 px breakpoint flake (narrow/wide resolves differently across loads — find the race).

**T3 · Visual across themes (Sonnet, 0.8 M)** — 14 routes × 5 themes (Default, Board, Cobalt, SaaS, Win98) × light/dark × 2 widths; Firefox + WebKit for Default; review sheets for clipping, contrast, focus visibility, bevel/shadow misfires, iframe grounds; contrast table per theme; résumé and letter PDFs page by page. Output also feeds the **post-round design brief**: Cobalt vs SaaS differentiation, Win98 depth (reference https://jdan.github.io/98.css/ — `#c0c0c0` chrome, navy title gradient, real button bevels, system font, window frames).

**T4 · Soak (scripts + Sonnet, ≤0.2 M)** — 3 calendar days with the scheduler on real sources (scrapes, scoring, tailoring, letters, Gmail, Telegram, extension captures). Once a day Sonnet reads backend logs, run history, LLM cost table, DB growth; anything new is a finding. Runs in the background from the day T2 ends.

**T5 · Security + ops (Opus, 0.5 M)** — every route with no key / wrong key / stale cookie; secret redaction in GET settings, logs, dumps; CSP on cached pages and the iframe; tracer links (guessing, replay, rate); `.env` never in a dump; container restarts with a full queue.

**T6 · Test debt (Opus, 0.8 M)** — `pytest-cov` report → tests for uncovered routes/branches touched by T1; Vitest inside the Docker build for `time.js` (describeCron table becomes real tests), `theme.js` migration, `hooks.js`, filter helpers; the Playwright smoke + flows A/B turned into `v2-testing/e2e/` runnable with one command in the backend container.

**Fix loop + close (1.1 M)** — fixes on Opus per triaged finding; Sonnet re-verifies live; round-3 smoke + flows A/B once more; final gate (lint 0, suite green, `R4_final` vs `R4_0` only expected diffs); `REPORT-round4.md`; DB restored.

## Order
T0 → T1 ‖ T2 → T3 → T4 (background) → T5 → T6 → fix loop → close.

## Out of scope
Load beyond the current 18 k jobs; browsers beyond the Firefox/WebKit spot check; multitenancy.
