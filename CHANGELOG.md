# Changelog

All notable changes to JobNavigator are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **OpenCode Go provider:** use an OpenCode Go subscription for scoring, tailoring, letters, autofill and email. OpenCode Go is an HTTP endpoint (`https://opencode.ai/zen/go/v1`) with an API key — no CLI, no binary, no extra image weight. Paste the Go key under Settings › AI and pick **OpenCode Go**; the model picker searches the live `/models` catalog. Go asks clients to identify themselves (the provider sends a `JobNavigator/…` user agent) and to send a stable `x-opencode-session` id per conversation, which it does. The starter list holds only the models Go serves on `/chat/completions`; GPT and Grok (Responses API) and MiniMax/Qwen (Anthropic API) are omitted, and picking one is refused with that reason. Cost counts as $0 (subscription).
- **Modern Professional résumé template** (by @Mohith1-stack, #18): a ninth PDF template, Arial with a ruled header, no external font load.
- **Reasoning effort per model** (by @volkotyk): the Primary, the scoring fallback and every per-feature override take a reasoning effort beside the model. Claude API sends `output_config.effort`, Claude Code `--effort`, Codex CLI `model_reasoning_effort`, OpenAI `reasoning_effort` and OpenRouter `reasoning.effort`; each picker offers only its provider's values (`GET /api/llm/efforts`). Empty keeps the model's default; an override on the Primary's provider inherits the Primary's effort. Antigravity CLI keeps the effort in the model name.
- **Current models** (by @volkotyk): Claude Opus 5.5 and Claude Fable 5.1 (Claude API, Claude Code, OpenRouter); GPT-6 Astra, Sol and Luna (OpenAI, Codex CLI, OpenRouter); GPT-5.6 Sol/Terra/Luna and GPT-5.5 on the OpenAI API; Gemini 3.8 Flash and 3.1 Pro on OpenRouter, with prices for the new API models. For new installs the list drops `gpt-5.3-codex` (Responses API only, so Chat Completions cannot call it), and `o3-mini`, `o4-mini` and `openai/o4-mini-high` (shut down 2026-10-23). An existing model list keeps these models.
- **Indeed country per search** (by @volkotyk, #17): a keyword search picks the Indeed country JobSpy queries (72 supported), and location and country are composed the same way for the scheduled run and the Test preview.
- **Antigravity CLI provider** (by @volkotyk, #14): use a Google Antigravity subscription for scoring, tailoring, letters, autofill and email through `agy`. One-time `docker compose exec -it backend agy`; the OAuth token lands in a file under the `antigravity_auth` volume, because the CLI skips the OS keyring when no D-Bus session bus is present. Token usage is logged, cost counts as $0. The prompt travels as one NDJSON line on stdin, so a long résumé plus job description never meets the argv limit. A shipped deny list holds the agent to plain text: `agy` carries 57 tools and reads files unasked, and its `--sandbox` flag restricts the terminal only. The per-call transcript, which holds the whole prompt, is deleted after each call. Every call carries about 13,000 input tokens of the CLI's own tool preamble: free in money, not in subscription quota. The backend image grows by about 270 MB.
- **LM Studio provider** (by @brycecollison, #15): local inference through LM Studio's OpenAI-compatible endpoint, no key; `LMSTUDIO_BASE_URL` for the containerised backend; thinking models run with reasoning off for these structured calls; cost counts as $0.
- **Posting zoom:** a + / − floater top-right of the posting steps the frame from 50 to 200 %; the level is remembered per browser. Double-click resets. Settings › General › Feed hides it.

### Changed
- **Subscription CLIs in the backend image** (by @volkotyk): Claude Code 2.1.281, which has `--effort`, and Codex CLI 0.156.1, which knows the GPT-6 models. Both are pinned now, so a cached layer cannot keep an older version. Antigravity CLI is whatever the installer serves (1.2.13 at this build). Its installer cannot pin a version, so the `AGY_VERSION` build argument records the version and acts as the cache key. Rebuild the image to get them: `docker compose build backend`.
- **Page text is fenced in every prompt:** the job posting (scoring, tailoring, cover letters) and the application question (autofill) go to the model between `<<<JOB POSTING>>>` markers with a one-line notice that it is data, so a posting that carries instructions is read as a posting. Output for ordinary postings is unchanged.
- **Frontend port 3000 is no longer published**; the dashboard is reached through Caddy on port 80 only (a host port there served nothing and could clash with ranges Windows reserves for Hyper-V).

### Fixed
- **Cover-letter PDFs** get the same fix as résumés in #19: page 2 of a long letter no longer starts at the paper edge; every page carries the template's own gutters.
- **Reasoning headroom only where it is needed:** OpenAI and OpenRouter get the 16,000-token headroom only when an effort is set, so gpt-4o and other small-ceiling models keep working with the default; Claude API keeps it by default. **Scrape health** pages Telegram only when a source failed or found nothing three runs running; one quiet board among several stays in the run summary and the health panel.
- **A Claude model that thinks no longer fails the call:** Sonnet 5, Opus 5.5 and Fable 5.1 can put a thinking block before the answer, and the pinned SDK reads that block as text `None`. The reply is now the text blocks only.
- **The output cap leaves room for reasoning:** Claude API, OpenAI and OpenRouter calls get 16,000 extra tokens under the cap, except at effort `none`. Tokens are billed as used. If a reply uses the whole cap on reasoning, the error says to lower the effort, and the call goes to the fallback without a retry.
- **The OpenAI API gets `max_completion_tokens`:** OpenAI's reasoning models (GPT-5.x, GPT-6, o-series) reject `max_tokens`. OpenRouter and LM Studio still get `max_tokens`.
- **A model that answers in prose no longer fails a run with `Expecting value: line 1 column 1 (char 0)`:** tailoring, scoring and cover letters read the reply with the tolerant parser the PDF import already uses (the first *balanced* JSON object, so a fenced or prose-wrapped answer still parses and a second object cannot swallow the first). A tailor whose reply carries no JSON — a stray instruction-shaped résumé bullet can have the model explain itself instead of tailoring — is asked once more for the object alone, and only then fails, saying "The model's reply was not valid JSON — try again". Claude Code's own error envelope and an empty completion now raise the CLI's reason instead of returning an empty string for someone else to choke on.
- **A blocked board says so, and a bot wall never becomes a job** (by @volkotyk, #17): ZipRecruiter, Google and Indeed blocks surface as readable errors per board instead of a silent empty result; a captcha or "Authenticating…" page is never stored as a description or cached page and never overwrites a good one; LinkedIn descriptions come from the posting's description block instead of the whole page; Indeed URLs dedup on the job key alone; a failed `ADD COLUMN` at startup no longer crash-loops the backend. The location/country check applies to keyword searches only, and block signatures match case-insensitively.
- **PDF résumé import** (by @brycecollison, #15): the reply is parsed from the first balanced JSON object (bare, fenced or wrapped in prose) and the token budget is 8000, so a verbose local model no longer truncates mid-object. "Cambridge, MA USA" style strings split into state and country.
- **Location parser, second pass:** bare Bay Area and Puget Sound cities resolve to their state; "Remote US" / "Remote in Canada" give the country with the remote flag; "Multiple Locations" and a stray "Location:" label never become a city; comma-joined city lists ("New York, San Francisco, Seattle", "IRL, Dublin, Cork") split into one place each. Corpus grown to 706 strings; existing rows re-parsed (unparsed 421 → 124).
- **Google and Meta handlers emit the card's location** (first place plus every listed one), so those jobs answer the Location filter; "USA Remote" and other country-first remote strings parse to the country with the remote flag.
- **Company page cap:** the ATS-dispatch fallback now honours the company's "Pages to read" like every other path.
- **LinkedIn Personal login** (by @volkotyk, #16): the session check asks Voyager `/me` instead of probing feed markup that no longer exists, and the login form is filled by `autocomplete` attribute since LinkedIn's ids are generated per render; the refresh script shares both helpers.

## [2.1.0] — 2026-09-16

The classic dashboard stays at `/classic` for this release too. Upgrade: `git pull`, `docker compose up --build -d`; reload the extension from `extension/`.

### Added
- **Location and work-arrangement search** (base by @volkotyk, #10): every job gets a parsed country, region and city plus remote / hybrid / on-site flags; the Jobs tab has Location and Work filters with counts that narrow each other, and a badge on the row. A posting open in several places answers every one of them. The board's own location text is never rewritten.
- **Every handler we own now emits location, multi-location and arrangement from what the board returns:** Greenhouse splits multi-location names and reads offices; Workday reads `remoteType` and the detail's additional locations with no extra request; the generic page scraper reads the location line of each job card (Stripe, Coinbase, Brex, Cursor, ServiceNow, Bloomberg, IBM, Databricks, Apple, PayPal); Phenom multi-location and RemoteType; TalentBrew; Oracle HCM and Rippling secondary locations; a small Amazon handler. A normal company pass also fills these fields on postings scraped before, so existing rows catch up without a re-fetch.
- **Location menu** lists the busiest country first and its regions and cities by count; a city that is also its region's name is one entry.
- **Amazon handler:** the search page's `country[]` filter is translated to the key the JSON feed honours (`normalized_country_code[]`), so a US-filtered URL no longer returns the world.
- **Location parser hardened on a corpus of 642 real posting strings** (checked in as a golden-file test): lists, foreign city-region-country triples, hyphen triples, metro names, addresses, office labels, "Washington State", Georgia the country, a city gazetteer for "City, CA"; a held-out code must fit exactly one candidate country, so a cross-border posting never files a US city under Canada.
- **Codex CLI provider** (by @funstuie-bit, #8): use a ChatGPT subscription for scoring, tailoring, letters, autofill and email through `codex exec`. One-time `docker compose exec backend codex login --device-auth`; token usage is logged, cost counts as $0.
- Follow-up hardening: a login pre-check that names the fix instead of a 15-second 401 storm, `turn.failed` surfaced as the error (a usage-limit hit fails over to the fallback provider without retrying), a 5-minute timeout on both subscription CLIs, and at most two concurrent Codex processes on the shared login file.

- **Applications: bulk actions**, the Jobs feed's exactly — ⌘/Ctrl-click picks rows, ⇧-click takes a range, and a floating bar moves the whole selection to Applied, Interview, Offer or Rejected (with an undo toast that puts every row back to the stage it came from). A stage the selection is already in is dimmed and does nothing. New `POST /api/applications/bulk-update` and `/bulk-delete`.
- **Add a job to the feed from the Log modal** (by @volkotyk, #9): the Applications › Log modal's Status now offers New and Saved beside the stages; those write a feed job only (`POST /jobs/manual`, deduplicated against existing rows), and a ✦ Tailor trigger beside each base résumé saves the row and starts a tailored copy.
- **Applications: undo on the stage stepper.** Moving one application to another stage shows the same undo toast the bulk bar has; an undo drops the transition it reverses instead of logging a new one, so the Stats funnel stays honest.
- **Getting-started guide** (`docs/GETTING-STARTED.md`): install, provider choice including the Claude Code and Codex CLI subscription logins from inside the container, résumés and Persona, companies, searches, the feed, the extension, Telegram and Gmail. README Quick Start reworked around it.
- **Version** in the Settings colophon comes from the build (the backend's is noted when it differs) and is on `/health`.

### Changed
- **Status filter:** picking nothing shows every status, like the other filters, and the pill's ✕ clears to Any; a browser with no saved filters starts on New.
- **Feed row:** the third line never wraps — salary · arrangement · H-1B · age; when space runs out the H-1B verdict gives way first and the age stays whole. The company name keeps its width; the location line shrinks.
- **Selection:** the first ⌘/Ctrl- or ⇧-click includes the row that is already open, on the Feed and in Applications. The bulk bar's buttons hover in the rail's own tones (Windows 98 gets a raised strip with bevel buttons); the Applications bar has no Delete.
- **Extension** 2.1.0, same code as 2.0.0.

### Fixed
- **Auto-scoring and the daily digest on fresh installs** (by @volkotyk, #11): `cv_scores` is created as `json` on a new database, and comparing it with a `jsonb` literal aborted every auto-score pass after a scrape and every digest; both compare as text now. Run errors no longer store or return the failed SQL statement and its parameters.
- **Cover letters for hand-logged jobs** (by @volkotyk, #7): a job logged from Applications has no stored description, and generation refused it. The letter worker now resolves the text the way tailoring does (description, then a live fetch saved to the job, then the cached page); logging an application queues that fetch; the description backfill covers applied jobs.
- **Feed paging under a filter:** a filter change starts a new load generation, so a page still in flight from the old filter is dropped instead of appended; every job sort carries an id tiebreak so pages never overlap.
- **Handler filters:** Greenhouse tolerates spaces in department and office ids and logs what it discards; Rippling compares country and region through the parser; Ashby reads secondary locations; Lever quotes filter values.
- **Cairo and Bengaluru in a US feed:** the Amazon handler honoured no country filter, and country-first strings ("IN, KA, Bengaluru") read as Indiana; both fixed and existing rows re-parsed.
- **Select boxes** in Paper and Green Paper no longer clip descenders.

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

[Unreleased]: https://github.com/vesaias/JobNavigator/compare/v2.1.0...HEAD
[2.1.0]: https://github.com/vesaias/JobNavigator/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/vesaias/JobNavigator/compare/v1.1.0...v2.0.0
[1.1.0]: https://github.com/vesaias/JobNavigator/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/vesaias/JobNavigator/releases/tag/v1.0.0
