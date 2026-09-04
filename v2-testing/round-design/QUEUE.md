# Work queue (2026-09-05)

Order is fixed; each item builds and gates before the next starts.

1. [ ] **Skins step 1 gate** — S1 vs S0 pixel + style diff (default skin identical), commit.
2. [ ] **Rename Theme/Skin → Appearance/Theme** (Opus) — Settings rows, help texts, section title "Display", `data-theme`→`data-appearance`, `data-skin`→`data-theme`, localStorage keys with one-time migration, `useTheme` fields, `SKINS`→`THEMES`, CSS selectors, boot script, rail toggle, gallery, tools (`--skin`, lint regex), docs. Gate: S2 vs S1 identical.
3. [ ] **Skins step 2** — ui.jsx changes 1–9 from `design-in/Skins handoff.md` §4 + the deferred state rules (pressed, field hover, `aria-disabled`, transitions, reduced-motion with spinner carve-out). Gate: default skin identical except the accepted proposals (P cells).
4. [ ] **Skins step 3** — new primitives (PillXs, ToolbarTrigger, TableRow, FooterRow, Mono, GlyphBadge, Notice, `HeaderRow variant="titlebar"`), migrate their hand-drawn sites, seven palette leaks, gallery rows.
5. [ ] **Skins proof** — shots + crawl per skin × light/dark, contrast table, smoke.
6. [ ] **Cron helper** (Opus) — `describeCron()` + next-run readout in the cron fields' helper line (user timezone, UTC note), preset ▾ menu (Hourly · Every 6 h · Daily 03:00 · Weekdays 09:00 · Weekly Mon · Monthly 1st). Settings + ui.jsx/time.js.

7. [ ] **Bug pass round 4** (final before release) — static gates (lint, suite, S-diff); skin sweep 14 routes × 5 themes × light/dark reviewed by Sonnet + contrast table; text sweep at 1024 px (overflow, ellipsis, wrapped hints, toasts, tooltips); round-3 smoke + flows A/B with real runs + new paths (appearance/theme key migration, cron helper, Persona import, Feed collapse); extension (popup, LinkedIn capture, autofill on one live form); `REPORT-round4.md`; DB restored. ≈1.5–2 M worker tokens.

Release = after item 7. Multitenancy = v3.0 on its own branch, design note first (owner column + RLS vs schema per tenant; what stays global). v2.1 = small items below.

Open decisions: seed `current_company` on Persona import; trim the theme picker to Default/Editorial/Cobalt/SaaS/Win98 (+Alt?); swatch picker instead of Select; `SKIN_LABEL` board names.
