# Changelog

All notable changes to JobNavigator are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security
- Harden fresh-install authentication, bind Compose ports to loopback by default, block private and rebinding destinations across browser scrapes, escape résumé and cover-letter previews, isolate PDF and Claude Code execution, and keep extension credentials out of sync storage and cleartext remote HTTP. Structured ATS autofill now always requires an explicit click.

### Added
- **Location and work-arrangement search** (base by @volkotyk, #10): every job gets a parsed country, region and city plus remote / hybrid / on-site flags; the Jobs tab has Location and Work filters with counts that narrow each other, and a badge on the row. A posting open in several places answers every one of them. The board's own location text is never rewritten.
- **Every handler we own now emits location, multi-location and arrangement from what the board returns:** Greenhouse splits multi-location names and reads offices; Workday reads `remoteType` and the detail's additional locations with no extra request; the generic page scraper reads the location line of each job card (Stripe, Coinbase, Brex, Cursor, ServiceNow, Bloomberg, IBM, Databricks, Apple, PayPal); Phenom multi-location and RemoteType; TalentBrew; Oracle HCM and Rippling secondary locations; a small Amazon handler. A normal company pass also fills these fields on postings scraped before, so existing rows catch up without a re-fetch.
- **Location menu** lists the busiest country first and its regions and cities by count; a city that is also its region's name is one entry.
- **Amazon handler:** the search page's `country[]` filter is translated to the key the JSON feed honours (`normalized_country_code[]`), so a US-filtered URL no longer returns the world.
- **Location parser hardened on a corpus of 642 real posting strings** (checked in as a golden-file test): lists, foreign city-region-country triples, hyphen triples, metro names, addresses, office labels, "Washington State", Georgia the country, a city gazetteer for "City, CA"; a held-out code must fit exactly one candidate country, so a cross-border posting never files a US city under Canada.
- **Codex CLI provider** (by @funstuie-bit, #8): use a ChatGPT subscription for scoring, tailoring, letters, autofill and email through `codex exec`. One-time `docker compose exec backend codex login --device-auth`; token usage is logged, cost counts as $0.
- Follow-up hardening: a login pre-check that names the fix instead of a 15-second 401 storm, `turn.failed` surfaced as the error (a usage-limit hit fails over to the fallback provider without retrying), a 5-minute timeout on both subscription CLIs, and at most two concurrent Codex processes on the shared login file.

- **Add a job to the feed from the Log modal** (by @volkotyk, #9): the Applications › Log modal's Status now offers New and Saved beside the stages; those write a feed job only (`POST /jobs/manual`, deduplicated against existing rows), and a ✦ Tailor trigger beside each base résumé saves the row and starts a tailored copy.

### Fixed
- **Auto-scoring and the daily digest on fresh installs** (by @volkotyk, #11): `cv_scores` is created as `json` on a new database, and comparing it with a `jsonb` literal aborted every auto-score pass after a scrape and every digest; both compare as text now. Run errors no longer store or return the failed SQL statement and its parameters.
- **Cover letters for hand-logged jobs** (by @volkotyk, #7): a job logged from Applications has no stored description, and generation refused it. The letter worker now resolves the text the way tailoring does (description, then a live fetch saved to the job, then the cached page); logging an application queues that fetch; the description backfill covers applied jobs.

## [2.0.0] — 2026-09-06

The new dashboard is the app at `http://localhost`; the previous one stays at `/classic` for one more release and old `/v2/…` links redirect. Upgrade: `git pull`, `docker compose up --build -d`.

### Security (extension 2.0.0)
- **Extension 2.0.0:** the header rules that let the Job Feed frame a posting (removing `X-Frame-Options` and `Content-Security-Policy`) applied to every page in the browser. They now apply only to sub-frames opened by the dashboard's own host, never to the dashboard's own responses (its cached-page reader is sandboxed by a CSP header), and follow the server URL set in the popup; top-level pages and frames opened by any other site keep their headers. Remove and reinstall the extension to pick it up.
- **Extension:** a "Posting preview" toggle in the popup (on by default) turns the frame rules off entirely; the feed then falls back to Open and cached snapshots. The presence marker the feed reads is set only on the dashboard's own host.
- **Extension:** messages are accepted only from the extension's own popup and content scripts, and other extensions can no longer connect to it. Structured autofill skips fields the user cannot see (hidden, zero-size or off-screen), so a page cannot collect the Persona through an invisible form.
- **Classic UI:** the cached-page iframes carry a real `sandbox` attribute instead of relying on the response header alone.
- **Compose:** the backend's port 8000 binds to loopback only; everything else goes through Caddy on port 80.

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
