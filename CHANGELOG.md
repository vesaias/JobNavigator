# Changelog

All notable changes to JobNavigator are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.0.0] — 2026-09-06

The new dashboard is the app at `http://localhost`; the previous one stays at `/classic` for one more release and old `/v2/…` links redirect. Upgrade: `git pull`, `docker compose up --build -d`.

### 1 · Dashboard redesign
- **Built from primitives.** Every screen is composed from one layer of ~50 components painted from semantic tokens; a lint blocks any hand-written colour, font, radius or shadow.
- **Jobs** — feed with detail pane and full report, collapsible analysis rail, keyboard shortcuts, bulk actions with undo.
- **Activity states** — a report is never hidden by a run: rescoring and tailoring show in the report band ("Scoring 2 résumés · Tailoring from PM"), on the tabs, as ghost tabs for résumés without a report yet, and as a busy ✦ on the card; a tailored copy appears the moment the tailor ends, before its chained score.
- **Companies** — tiers A/B/C, health with acknowledge, per-company résumés and scoring depth.
- **Applications** — stage stepper, interviews, prep handover for an AI chat.
- **Résumés** — shelf, editor, tailoring review with per-change decline.
- **Cover Letters** — list and editor with voice and length presets.
- **Stats** — funnel, Sankey, timeline, LLM cost, run history.
- **Settings** — grouped sections, validated fields, autosave.
- **Feel** — one-settle rendering (no popping counters), warm-started rail counts, pollers that survive navigation and reload, optimistic lists, plain-language copy throughout.

### 2 · Extension AI-powered redesign
- Structured ATS autofill, field by field, from the Persona and Q&A bank.
- In-field AI drafts for free-text questions from the Navigator button.

### 3 · Themes and appearance
- **Appearance:** Light, Dark or System (follows the OS).
- **Themes:** Paper (default), Green Paper, Stone, V1 Style, Windows 98 — colours, fonts and shapes, both appearances, switched live with no reload or flash.
- **Windows 98** is a full recreation: bevels, title bars with window controls, Explorer-style rail, progress-bar loaders, 98 dropdowns and scrollbars. **Stone** is achromatic with Geist. **V1 Style** brings back the softer type of the old dashboard, with violet AI actions.

### 4 · OpenRouter and model management
- OpenRouter as a provider (every vendor with one key).
- Live model search for OpenAI, Anthropic and OpenRouter; a model catalog you can extend.
- Scoring-only provider/model override with automatic fallback.

### 5 · New aggregator: freehire.me
- Seventh discovery tier over freehire.me's open API; salary from its structured enrichment; preview runs and per-job filter reasons like every other source.

### 6 · Persona import
- Fill the Persona from a base résumé or a PDF in one step: contact details, résumé content and current company (overwrites previous values).

### 7 · Cron helper
- Schedule fields explain themselves as you type ("weekdays at 09:00 UTC · next Mon 07 Sep 09:00 (your time)") with presets: Hourly, Every 6 hours, Daily, Weekdays, Weekly, Monthly.
- Presets use day names so cron and APScheduler agree; the default H-1B refresh now runs on Sunday as intended.

### 8 · First run and shell
- Welcome tour on the first visit; sign-in works before any key is set.
- Rail health dot for "backend unreachable" and "last scrape run failed".
- Only one menu or select open at a time, app-wide.

### 9 · H-1B, health and pricing
- One visa cache with an h1bdata.info fallback.
- Scrape health alerts per company and search.
- Live LLM pricing on the Stats cost table; info popovers on board headers.

### 10 · Backend and reliability
- **Validation everywhere:** types, limits, ids, bulk updates and status transitions on every router; bad input never 500s and never leaks a stack trace.
- **Dedup:** the identity hash folds trailing slash, `www.`, scheme and parameter order; stored URLs untouched; one-shot backfill for existing rows.
- **Runs:** status reflects LLM outages; stale runs recovered on startup; seed migrations isolated per statement; per-source outcomes on search runs.
- **Settings:** validated on save with the scheduler reconfigured in place.
- **Tracked links:** secure tokens; `tel:` / `mailto:` links no longer rewritten.
- **Security:** résumé template names whitelisted; embedded pages sandboxed; auth endpoints rate-limited; `nosniff`, `frame-ancestors` and referrer headers; Telegram token kept out of logs; container log rotation. Backups still contain the settings table (API keys included): local, git-ignored, treat as secrets.
- **PDF export:** print rules stop a last line spilling onto a blank second page.
- **Fixes:** Ashby department filter; blank-key first-run sign-in.

### 11 · Testing
- Backend 2,175 tests (from ~770): contract, dedup property, concurrency, failure-injection and security suites; coverage 79 %.
- Frontend Vitest in Docker (160 tests) and a repeatable Playwright e2e suite (16 cases).
- Pixel and computed-style design gates; every theme step shipped with the default theme proven pixel-identical.

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
