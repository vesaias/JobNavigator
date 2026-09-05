# Work queue (2026-09-05)

Order is fixed; each item builds and gates before the next starts.

1. [x] **Skins step 1 gate** — S1 vs S0 pixel + style diff (default skin identical), commit.
2. [x] **Rename Theme/Skin → Appearance/Theme** (Opus) — Settings rows, help texts, section title "Display", `data-theme`→`data-appearance`, `data-skin`→`data-theme`, localStorage keys with one-time migration, `useTheme` fields, `SKINS`→`THEMES`, CSS selectors, boot script, rail toggle, gallery, tools (`--skin`, lint regex), docs. Gate: S2 vs S1 identical.
3. [x] **Skins step 2** — ui.jsx changes 1–9 from `design-in/Skins handoff.md` §4 + the deferred state rules (pressed, field hover, `aria-disabled`, transitions, reduced-motion with spinner carve-out). Gate: default skin identical except the accepted proposals (P cells).
4. [x] **Skins step 3** — new primitives (PillXs, ToolbarTrigger, TableRow, FooterRow, Mono, GlyphBadge, Notice, `HeaderRow variant="titlebar"`), migrate their hand-drawn sites, seven palette leaks, gallery rows.
5. [x] **Skins proof** — shots + crawl per skin × light/dark, contrast table, smoke.
6. [ ] **Cron helper** (Opus) — `describeCron()` + next-run readout in the cron fields' helper line (user timezone, UTC note), preset ▾ menu (Hourly · Every 6 h · Daily 03:00 · Weekdays 09:00 · Weekly Mon · Monthly 1st). Settings + ui.jsx/time.js.

6b. [ ] **Comment cleanup** (Sonnet) — strip narrative prose from comments in `frontend/src/v2/*`, `theme.css/js`, `v2-testing/tools/*.py`: keep one-line why-comments, the `// ui: keep — …` / `// lint: allow` annotations (one line) and load-bearing notes; drop finding ids, history, restated code, multi-line essays. Gate: comment-stripped source identical before/after, lint 0, build ok. Backend Python (`backend/**/*.py`, tests included) in the same pass, same rules.

7. [ ] **Round 4 — deep pass before release** (approved 2026-09-05, budget 5–7 M; briefs in `ROUND4-PLAN.md` when written). Tracks: **T0** fresh install + upgrade from the oldest dump (0.4 M) · **T1** backend contract/data robustness: per-router bad input, dedup property tests, scheduler vs manual concurrency, crash/stale-run recovery, LLM/Gmail/Telegram failures, backup-restore drill (1.2 M) · **T2** frontend state matrix: every screen × empty/one/many/error/loading/offline/slow, modals, shortcuts, undo, refresh mid-run, two tabs, 8 h session, widths to 900 (1.5 M) · **T3** visual: 14 routes × 5 themes × light/dark × 2 widths + Firefox/WebKit spot check, contrast tables, PDFs (0.8 M) · **T4** soak: 1–3 days wall-clock with the scheduler on real sources, daily Sonnet log/cost review (≤0.2 M agent) · **T5** security/ops: auth bypass, secret redaction, CSP, tracer abuse, rate limits, dumps (0.5 M) · **T6** test debt: pytest-cov + tests for uncovered paths, one regression test per fix, Vitest in Docker for pure modules, Playwright flows as a repeatable `v2-testing/e2e/` suite (0.8 M) · fix loop + final regression + `REPORT-round4.md` + DB restore (1.1 M). Order: T0 → T1‖T2 → T3 (after skins) → T4 in background → T5 → T6 → fix loop.

Release = after item 7. v2.1 = small items below.

Open decisions: seed `current_company` on Persona import; trim the theme picker to Default/Editorial/Cobalt/SaaS/Win98 (+Alt?); swatch picker instead of Select; `SKIN_LABEL` board names.
