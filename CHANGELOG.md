# Changelog

All notable changes to JobNavigator are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.0.0] — 2026-09-06

The dashboard is rebuilt. The new interface is the app at `http://localhost`; the previous one stays reachable at `/classic` (Settings › Display › Open classic UI) and will be removed in a later release. Old `/v2/…` links redirect. Upgrading is `git pull` and `docker compose up --build -d`; tables and settings are migrated on startup, browser preferences carry over.

### The new dashboard
- **One primitive layer.** Every control on every screen (buttons, pills, fields, selects, rows, cards, menus, modals, drawers, tags, score marks, toasts, dialogs, glyphs) is one of ~50 components in `frontend/src/v2/ui.jsx`, painted from a semantic token layer in `theme.css`. A lint fails the build on any colour, font, radius or shadow written outside those two files. Integer line heights, the app's own focus ring, keyboard access and ARIA are built in.
- **Screens.** Jobs (feed with detail pane, full report, collapsible analysis rail, keyboard shortcuts, bulk actions with undo), Searches, Companies (tiers A/B/C, health, per-company résumés and depth), Applications (stage stepper, interviews, prep handover), Résumés (shelf, editor, tailoring review with per-change decline), Cover Letters (list, editor, voice and length), Persona (autosaving editor, **import from a résumé or a PDF**), Stats (funnel, Sankey, timeline, LLM cost, run history), Settings (grouped, validated, autosaving).
- **Themes.** Appearance = Light / Dark / System (follows the OS). Theme = Paper (default), Green Paper, Stone, V1 Style, Windows 98 — colours, fonts and shapes, each in both appearances, switchable live from Settings or the rail. Windows 98 is a full recreation (bevels, title bars with controls, Explorer-style rail, progress-bar loaders, 98 dropdowns and scrollbars); Stone is achromatic with Geist; V1 Style brings back the softer type of the old dashboard with violet AI actions.
- **First run.** A welcome tour on the first visit, sign-in that works before any key is set, and a health dot in the rail that says when the backend is unreachable or the last scrape run failed.
- **Feel.** Screens paint their chrome in one settle (no popping counters or subtitles), warm-started rail counts, pollers that survive navigation and reload (tailoring, letters, scoring, searches), optimistic list updates, reserved loading shells, no flash on reload in any theme.
- **Copy.** Plain language throughout: scrape run, tracked links, preview run, prep handover, Light/Full depth; twelve vocabulary rules plus 120 rewritten strings.
- **Cron helper.** Every schedule field shows what it means and when it fires next ("weekdays at 09:00 UTC · next Mon 07 Sep 09:00 (your time)") as you type, with a preset menu. Note: the scheduler counts weekdays from Monday = 0, as APScheduler does; presets use names (`mon-fri`) so they read the same either way, and the default H-1B refresh now runs on Sunday as intended.

### Also since 1.1.0 (landed before the redesign)
- **freehire.me** aggregator source (open API, salary from structured enrichment) — seven discovery tiers.
- **OpenRouter** provider, live model search for OpenAI, Anthropic and OpenRouter, a model catalog with your own additions, and a scoring-only provider/model override with fallback.
- **H-1B:** one visa cache with an h1bdata.info fallback; digest and UI fixes.
- **Scrape health alerts** and live LLM pricing on Stats.
- **Extension:** structured ATS autofill and in-field AI drafts; Persona tweaks.
- Info popovers on the board headers; Ashby department filter fix; first-run sign-in with a blank key (#5).

### Backend and robustness
- Input validation across every router (types, limits, ids, bulk updates, status transitions), no 500s on bad input, no stack traces in responses.
- Dedup identity hash folds trailing slash, `www.`, scheme and parameter order (stored URLs untouched); a one-shot backfill script for existing rows.
- Run status reflects LLM outages; stale runs recovered on startup; seed migrations isolated per statement.
- Persona import endpoint; per-source outcomes on search runs; settings validation with scheduler reconfiguration; tracer links no longer rewrite `tel:`/`mailto:`; secure tracer tokens.
- Security: résumé template names whitelisted, embedded pages sandboxed, auth endpoints rate-limited, `nosniff` / `frame-ancestors` / referrer headers, Telegram token kept out of logs, container log rotation. Backups still contain the settings table (including API keys): they are local and git-ignored — treat them as secrets.
- Résumé PDFs: print rules stop a last line spilling onto a blank second page.

### Testing
- Backend: 2,175 tests (from ~770), incl. contract, dedup property, concurrency, failure-injection and security suites; coverage 79 %.
- Frontend: Vitest in Docker (`v2-testing/tools/fe-test.sh`, 160 tests) and a repeatable Playwright e2e suite (`v2-testing/e2e/run.sh`, 16 cases).
- Design gates: pixel and computed-style baselines with a frozen clock and paused scheduler; every theme step shipped with the default theme proven pixel-identical.
- Four verification rounds, a design-consistency pass and a deep pre-release pass are documented under `v2-testing/` with every finding and decision.

### Removed
- The rail's "Classic UI" link (now in Settings › Display). The legacy `url` search mode. Auto-ghost. Ten dead theme tokens.

### Known / deferred to 2.1
Two-tab live sync; layouts under 1000 px; infinite-scroll tiebreaker on the server; Test runs of searches not yet tracked by the run monitor; Win98 desktop gutter and rail-foot variants (open questions); a few P4 validation nits listed in `v2-testing/REPORT-round4.md`.

## [1.1.0] — 2026-08-16

### Added
- **Application Autofill** — generate a first-person answer to any free-text
  application question on any job site, straight from the Chrome extension.
  Focus a textarea, long text input, or rich-text editor and click the Navigator
  button; the answer is grounded in your **Persona** (contact, work
  authorization, preferences, résumé content) plus your saved **Q&A bank** — no
  résumé text is fed in. Review it in a popover with a live character counter and
  a length picker, then **Insert**, **Copy**, or **Save to bank** for reuse. The
  field button morphs pill → loader → check in place as the answer generates.
- Backend: `POST /api/autofill/answer` (persona-grounded, prompt-cached) and
  `POST /api/persona/qa-bank` (append to the reusable Q&A bank).
- Settings → AI: an **Application Autofill** section — LLM provider/model,
  default answer length, and an editable prompt.

## [1.0.0] — 2026-08-15

First stable release. Self-hosted job-hunt automation: scrape boards and career
pages, score jobs against your résumés with Claude, tailor résumés and cover
letters, capture LinkedIn roles via a Chrome extension, monitor Gmail for
replies, and manage it all from a React dashboard.

### Added
- **Discovery:** 6 scraping tiers — JobSpy (LinkedIn/Indeed/ZipRecruiter/Google),
  Levels.fyi, LinkedIn collections, Jobright.ai, direct career pages (auto-detects
  Workday, Greenhouse, Ashby, Lever, Oracle HCM, SmartRecruiters, Rippling, and
  more), and the "Navigator" Chrome extension. Two-layer dedup.
- **AI:** per-résumé scoring (5-criteria rubric, apply recommendations), grounded
  résumé tailoring and cover-letter generation, click-tracking tracer links.
- **Tracking:** Kanban application board, status-transition history, Gmail
  response monitoring, Telegram alerts/digests.
- **Dashboard:** React + Tailwind (dark mode), keyboard-driven Job Feed, editable
  settings (LLM providers/models, rubric, filters) — only secrets live in `.env`.

[Unreleased]: https://github.com/vesaias/JobNavigator/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/vesaias/JobNavigator/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/vesaias/JobNavigator/releases/tag/v1.0.0
