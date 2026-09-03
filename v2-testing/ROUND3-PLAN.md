# v2 verification round 3 — plan

Starts after the round-2 fixes land (two Opus agents in flight on 2026-09-04). Orchestrator: Fable. Workers: Opus (flows), Sonnet (smoke). Resume rule: first unticked box. Outputs in `v2-testing/round3/`, written incrementally.

## Fixed inputs
- Baseline dump `backups/round3_baseline_20260904.dump` (taken after the round-2 fixes at `69d36b1`), restored in R3-4 (same procedure as round 2: stop backend, `pg_restore --clean --if-exists --no-owner`, start backend, verify counts).
- LLM: settings already on Sonnet; no call cap this round ("use LLM as much as needed"), but every call is logged in the flow report.
- Harness, docker commands, commit rules: as in `ROUND2-PLAN.md`.
- Real network allowed (user 2026-09-04): search runs may run for real (JobSpy, all configured searches if useful), company scrapes on public ATS APIs, the Telegram digest trigger (one real message) and one Gmail check. LinkedIn personal and Jobright scrapes stay off (credentials/ToS).

## Stages
- [x] **R3-0 verify round-2 fixes** (Fable) — commit the two agents' work, restart backend, rebuild frontend, full test suite, Playwright check of every round-2 fix (COMP-11, R2-H-02/05/07/15, R2-S-04, COMP-26, R2-A-01/02, R2-H-01/03/04/09/10/12/13/14, R2-S-01/02/06, APPS-20, CL-28, RES-32, R2-A-03, SET-28), statuses updated in `round2/*.md` and `stage3/*.md`. Baseline dump taken. Round-2 fixes committed (`f75f2a1`, `69d36b1`), backend restarted, frontend rebuilt, 646 tests pass; Playwright verification delegated to Sonnet → `round2/verify.md` (running in parallel with R3-1/R3-2; prefixes ZZV / — / ZZA / ZZB keep the agents' rows apart).
- [x] **R3-1 smoke** (Sonnet) → `round3/smoke.md`. Same matrix as round 2 (23 routes × 2 themes × 2 viewports; load, console, controls, overflow, deep links, stubbed 500, Escape, Tab, rail counts). Plus: every modal/drawer/menu opened and closed on each screen; every toast kind observed once via `/v2/toasts`; keyboard shortcuts on the Feed (j/k/s/x/o/Enter/Escape) without mutating (use a scratch job or intercept the PATCH).
- [x] **R3-2 main user flows, deeper** (Opus, two agents in parallel on disjoint data) → `round3/flows-A.md`, `round3/flows-B.md`.
  - **A — the daily loop**: company scrape (public Greenhouse) and search run → new jobs in the Feed → triage with filters, sort, keyboard, bulk select (skip ×N, save ×N) → open detail → Light score, then Full score (report, keyword coverage, requirement mapping, strengths/gaps) → save → Applied → application auto-created with company → undo → Applied again → log a manual application from a URL (reader fills, typed text kept) → duplicate → 409 → stage Interview (row with date/time, edit, delete + undo) → Offer → Rejected → notes → prep pack export → Stats KPIs, funnel, Sankey, run history, activity log all reflect it → Telegram alert path (trigger the digest endpoint, verify 202 and the run) → delete everything created.
  - **B — the document loop**: new base from scratch → import a PDF (real LLM parse) → edit every section type (header contact rows with tracked links, summary, experience with bullets and reorder, skills rename/reorder, education, projects) → tailor to a job (LLM) → toast → copy opens → review changes (decline one, restore) → score Light and Full (LLM) → Tailored chip on the Feed → freeform tailor from pasted text (LLM) → job-less score (LLM) → PDF for base and copy (200, `%PDF`, tracked links rewritten) → cover letter from the copy (LLM) → edit paragraphs (add/remove/reorder, undo) → regenerate with another voice and length (LLM) → PDF → persona edit (contact, preferences, resume_content section, Q&A add through the UI — the round-2 unverified item) → autofill answer for two questions with different length limits (LLM) → save to bank → count → settings: change scoring depth, threshold, an interval, a cron; reload; scheduler shows the new interval; revert → delete everything created.
  - Both: assert via UI and API, `ZZTEST` prefix on every row, delete at the end, final sweep 0. File findings as `R3-A-NN` / `R3-B-NN`.
- [x] **R3-3 fixes** (Opus) — anything P1/P2 found in R3-1/R3-2 fixed, rebuilt, verified; P3/P4 logged.
- [x] **R3-4 close** (Fable) — `v2-testing/REPORT-final.md`: everything still open across rounds 1–3 in one list (P2 → P3 → P4 → text suggestions), with where/what/suggested fix; restore DB from the round-3 baseline; verify counts and 0 `ZZTEST`; commit.

## R3-4 log (2026-09-04)
- Fixes `8804ae3` (+ test marker `ec33983`): 14 items incl. P1 R3-A-02/R3-A-08, P2 R3-A-05/R3-B-03, RES-32 re-fix; 735 tests pass; all 14 verified live (`round3/verify.md`).
- DB restored from `backups/round3_baseline_20260904.dump` (backend stopped during restore). Verified: companies 126 · searches 6 · applications 377 · bases 4 · cover letters 16 · jobs 18843 · 0 `ZZ*` rows · `jk` stripped from the restored `dedup_tracking_params` by the startup migration · `llm_model` claude-sonnet-5.
- Final consolidated report: `v2-testing/REPORT-final.md` (6 open items, 156 text suggestions).

## Post-round fixes (2026-09-04, after the user's decisions)
- `406aebe` + `2946d5b` + `8985b53`: R3-A-01/03/04/06/07 fixed, R3-B-01 Title field, user-reported R3-U-03..06 (row hover, input focus, filter hovers, archived band). Verified live (`round3/verify-final.md` 8/10, then R3-A-03/R3-A-06 re-fixed and re-checked: real run shows the ZipRecruiter 403 per board; Applications renders with an interview and edits inline). 776 tests pass.
- DB restored again from `backups/round3_baseline_20260904.dump`; counts verified (126 / 6 / 377 / 4 / 16 / 18843), 0 `ZZ*` rows.
- Consolidated open-items report (text excluded): `v2-testing/REPORT-open.md` (Opus).

## PAUSED 2026-09-04 (usage limit) — resume here
- Code: HEAD `63790cf` is built and live (OPEN-list fixes `2927bdb` + health/acknowledge `63790cf`); 858 tests pass in the container.
- Verification of the OPEN-list fixes: `round3/verify-open.md` has OPEN-01..06, 08, 10 ✔. **Still to verify live:** OPEN-12 (save-from-extension reason), OPEN-13 (preview tracked links), OPEN-16 (Jobright read-only row), and the HEALTH-ACK checks (inactive entities excluded, acknowledge endpoints/links, 409 on extension searches). The Sonnet verifier was stopped mid-run; re-launch with the same brief (see chat/SendMessage text of 2026-09-04) or verify by hand.
- Then: statuses in `REPORT-open.md`, DB restore from `backups/round3_baseline_20260904.dump` (the DB currently holds no ZZ* rows but may carry runs/logs from verification), commit.
- Then the design pass: `DESIGN-PASS-PLAN.md` D0 (baselines) — the scanner draft `tools/stylescan.py` exists; widen its classifier before showing the D1 table.
