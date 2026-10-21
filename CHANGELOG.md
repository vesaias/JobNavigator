# Changelog

All notable changes to JobNavigator are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Releases are named major.minor ("3.0"); tags before 3.0 carry a `.0` patch (`v2.2.0`).

## [Unreleased]

### Fixed
- **Subscription CLI timeouts are not retried** (by @volkotyk): when Codex CLI, Claude Code or Antigravity CLI passed its time limit, `call_llm` ran the same prompt on the same model three more times. One stuck scoring or PDF import then took 4 × 300 s and held a CLI slot (two per CLI) the whole time. A timeout now goes straight to the fallback model, or fails at once when there is no fallback. The time limits stay as they are; other errors still get four attempts.
- **Antigravity CLI expired login** (by @volkotyk): `agy` 1.3.3 and later reports an expired or revoked token as "Authentication expired. Please log back in." The adapter now treats it as "not logged in": the call goes straight to the fallback provider and the error names the login command. Before, it was a plain failure that the backend retried.

### Changed
- **Prebuilt images for ARM** (by @volkotyk): the backend and frontend images are published for `linux/arm64` as well as `linux/amd64`, so an ARM host (Apple Silicon, Raspberry Pi, RK35xx boards) runs `docker compose pull` instead of building Chromium from source. The arm64 build runs under QEMU in the same job, so the backend image takes about 12 minutes on a cold cache.
- **Antigravity CLI 1.4.3 in the backend image** (by @volkotyk): `AGY_VERSION` is now 1.4.3, so the next `docker compose build backend` reinstalls the CLI instead of keeping a cached 1.2.13 layer. Flags, the deny list and the result event were checked against 1.4.3.

## [3.0] — 2026-10-17

JobNavigator becomes a household install: one server, up to five accounts, each with its own data. An existing install keeps everything it has: the data becomes the owner's account, and with one account the dashboard looks and behaves as before.

### Upgrading from 2.x
1. **Back up first.** The upgrade migrates the database in place and there is no way back to 2.x except a restore. 3.0 also dumps the database to `backups/pre_upgrade_2.x_to_3.0_<timestamp>.sql` on its first boot, before migrating, and does not start if that dump fails. With 2.x still running: `docker compose exec -T db sh -c 'pg_dump -U $POSTGRES_USER $POSTGRES_DB' > backups/pre-3.0.sql` (restore command in `docs/GETTING-STARTED.md` › Scheduling, backups, upkeep).
2. **Update:** `git pull`, then `docker compose pull && docker compose up -d` (prebuilt images) or `docker compose up --build -d`. If `.env` pins `JN_IMAGE_TAG`, set it to `3.0`. `git pull` alone is not enough — the images must be pulled or rebuilt: the compose file mounts the new backend code into whatever image is there, and a 2.x image lacks packages 3.0 needs (the dashboard and the backend log then say so).
3. **First boot migrates by itself:** it adds an account column to every owned table, creates the owner account (named after your Persona, else "Owner") and gives it every existing job, application, résumé, cover letter, search, company, Persona and log. Settings you already have stay install values and become the owner's (a member later inherits them or keeps its own, section by section); settings new in 3.0 are seeded with their defaults, and existing values are not touched. The install password (dashboard API key), Telegram bot and chat, and `GMAIL_REFRESH_TOKEN` keep working for the owner.
4. **Reload the extension** (`chrome://extensions` › reload): it becomes 3.0; its permissions and URL patterns are unchanged, so no reinstall is needed.
5. **Optional:** to connect Gmail from Settings instead of `.env`, add `<your dashboard address>/api/gmail/callback` as an authorized redirect URI in the OAuth client. To add people, Settings › Accounts › **+ Add account**.

### Added
- **Household accounts:** one owner plus up to four members. The install password still opens the install; with two or more accounts a picker follows, and any account, the owner's included, can carry an optional 4-digit PIN (the owner's PIN opens any member; five wrong tries wait 30 s; an account without one opens in one click). The choice is remembered per browser (`Ctrl + Shift + 1–5` switches, `⌃⇧1–5` on a Mac; a switch saves pending edits to the old account first, and the browser's other tabs show a "switched in another tab" notice and stop saving until reloaded). With one account the only new thing is Settings › Accounts at the top (your own row and **+ Add account**).
- **Separate data per account:** jobs, searches, companies, applications, interviews, résumés, cover letters, Persona, tracer links, activity and LLM logs, runs and scrape logs. Every query is scoped centrally, background work (digest, auto-reject, cleanup, e-mail check, scoring) runs once per account, and a two-account leak test walks every API route.
- **Shared scraping:** two accounts that watch the same company page or run the same keyword search cause one fetch. Each account then ingests the postings through its own filters, excludes, dedup, H-1B and salary checks and auto-scoring. The shortest interval wins; results and age limits are trimmed per account.
- **Settings inherit or own, per section:** the owner decides for each member whether a section (models, notifications, filters, …) follows the owner's values or is the member's own. The owner sets a member's policies from Settings › Accounts: the **Edit policies** switch on the member's row turns on an Inherit / Own control on each section, and it is off again on every load. A member sees a scope tag on each section (Display, which is per browser anyway, carries none), the member's nav groups yours and shared sections, and owner-only sections sit behind a lock card with an inline owner-PIN unlock (15 minutes; a plain Unlock button when the owner has no PIN, which makes it a privacy latch only).
- **Per-account credentials and logins:** provider API keys follow the section policy; Claude Code (token), Codex (`CODEX_HOME`) and Antigravity (state dir) get a login per account (`backend/scripts/cli_login.py` prints the command); LinkedIn, Jobright and Levels sessions and cookie files are per account.
- **Telegram per account:** the household bot routes by chat (link with a 6-digit code and `/start <code>`), or a member brings their own bot with its own webhook. Inline buttons act only on the chat's account; system alerts go to the owner.
- **Gmail per account:** connect from Settings with Google's consent screen instead of `.env` tokens (the OAuth client stays in `.env`; add `http://localhost/api/gmail/callback` as an authorized redirect URI). An existing `GMAIL_REFRESH_TOKEN` keeps working for the owner.
- **Extension "Saves to":** with two or more accounts the popup picks which account captures go to (its PIN, when it has one, to change); the server then issues a signed per-account token that every request carries as `X-Account-Token`, and autofill reads that account's Persona. Scripts get the same token from Settings › Your account › API token. A bare account id never selects an account. Extension 3.0.
- **Copy from… and clone:** a new account can start from a copy of the owner's (or another account's) Persona and Q&A bank, base résumés, companies, searches, settings, voices and excludes; Companies and Searches get a "Copy from…" picker for single rows. Never jobs or applications.
- **OpenCode Go provider** (by @mreid-tt, #25): an OpenCode Go subscription can run scoring, tailoring, letters, autofill and email. Go is an OpenAI-compatible HTTP endpoint with an API key, so there is no CLI and no extra image weight: paste the Go key under Settings › Models (or set `OPENCODE_API_KEY`) and pick **OpenCode Go**; the Model catalog searches Go's live `/models` list. The provider identifies itself with a `JobNavigator/…` user agent and sends an `x-opencode-session` id, as Go asks: one per account and feature, so a feature's prompts cache together and no two accounts share one. The starter list holds models that answer on `/chat/completions`, MiniMax M3 and Qwen 3.8 included (existing lists gain them and keep their own edits). Go's own error payloads decide what is not retried: `ModelProtocolUnsupported` (a model Go serves on another protocol, such as GPT, Grok or Claude), "Model is unavailable." (an unknown model) and a contributor model that trains on request data each fail at once with a readable reason; every other error retries and then falls back. A member on their own Models uses only their own Go key. Cost counts as $0 (subscription).
- **Apify search mode** (by @volkotyk, #28): a new search type that runs Apify Store actors as job boards: Indeed, LinkedIn, Glassdoor, and keyword search across every company on Greenhouse, Lever, Ashby and Workday. A search picks its boards like a keyword search picks JobSpy boards; each board reports its own row in the run summary and the health panel. The board list comes from the backend (`GET /api/searches/apify-boards`), so a new board is one entry in `backend/scraper/sources/apify.py`. Settings › Apify takes the API token; **Check key** proves the token and the plan without running a search. Apify bills the account per result: Results wanted caps every board on every run, and Test fetches 20 jobs per board at most. The actors read LinkedIn, Indeed and Glassdoor under your own Apify account and its terms; see `LEGAL_DISCLAIMER.md`.
  - **The Apify Creator plan does not work.** It runs only Apify's own universal Actors, so Apify refuses every board with `403 public-actor-disabled`. Use the Free plan or a paid plan. Check key and the run summary name the cause when the key is on the Creator plan.
  - The title filters, Company include and the company excludes apply to what the boards return; the run summary counts the jobs they rejected ("N filtered out").
  - The token is per account: a member's Apify section is their own by default (their own token or none, never the owner's); the owner can switch a member to inherit, and then the owner's Apify account pays for that member's runs. Check key then says only that the owner's key works, not the owner's Apify account name. Apify searches are never shared between accounts: each account runs and pays for its own.
  - Cost guards: every run starts with a spend cap (`maxTotalChargeUsd`, from Results wanted × the board's price, $5 at most) and a platform-side 15-minute `timeout`, so a backend restart cannot leave a run billing. Results wanted is capped at 200 per board on create, edit and run. A new Apify search (or a search switched to Apify, or a copy) starts paused. Board keys are `apify_<board>` (`apify_indeed`, `apify_linkedin`, …), and the API refuses an Apify search whose boards are not Apify boards, so JobSpy's default boards can never start a paid run. Test asks first and names the estimated cost. The server runs one Test of a search at a time: a second Test (another tab, a double click) answers 409 and the dashboard follows the one already running, and the search's Run waits for its Test, and its Test for a running Run.
- **CaribbeanJobs.com source** (by @mreid-tt, #26): a new search mode scrapes caribbeanjobs.com's ShowResults pages. Paste a search URL and its filters (Keywords, Location, Category, job type) are forwarded, or set a search term to override the keywords — comma-separated alternatives are searched separately and merged, since the board ANDs bare words. Each listing is followed to its own page for the full description, posting date and structured salary, read from the schema.org JobPosting block the board embeds; job pages are read two at a time, about a second apart. Title, company, body-exclusion and expiry filters apply before a job is saved, and the usual inline H-1B and salary analysis runs on the way in. A job whose page renames it into the title or company filters, or whose description matches a body-exclusion phrase, is kept as ignored in that account, so its page is read once rather than on every run, and it never counts as new. A job ignored for a phrase stays ignored if you later remove the phrase.
  - **Cloudflare:** caribbeanjobs.com answers many networks (ours included) with a Cloudflare challenge. The scraper does not try to pass it: the run, the Test and the health panel say "CaribbeanJobs is behind a Cloudflare challenge from this network; the scraper cannot pass it" instead of a bare 403, and the editor shows the block and a terms notice (also in `LEGAL_DISCLAIMER.md`).
  - Test reads at most 20 detail pages and says when it sampled; the title and company filters are checked again after a detail page renames the job; only a salary posted in USD per year is stored as numbers, any other currency stays as text at the end of the description. Two accounts with the same search share one listing fetch and read each detail page once.
  - A job whose page fails, stays throttled or comes back as a Cloudflare challenge is not stored with the listing's short blurb (which the body-exclusion phrases and the expiry date never saw); its page is read again on the next run. Once a page is still answering 429 after the retries, or is challenged, the run stops reading pages and leaves the rest for the next run, for every account that shares the fetch.
- **TrulyRemoteWork.com source** (by @mreid-tt, #32): a new search mode reads the board's whole corpus of worldwide-remote roles from its machine-readable `llms-full.txt` and follows each new listing to its Markdown twin for the full description and the employer's apply link (the link the feed opens). The search needs no term or URL; the title and company filters (Company include and exclude) narrow it, and **New jobs per run** caps how many new jobs' pages one run opens. Every job is flagged remote. Only a salary in dollars per year is stored as numbers; any other amount (€, A$, a figure with no currency, per hour) stays as text at the end of the description. The board invites this use and asks that its content not be used for training (`Content-Signal: ai-train=no, ai-input=yes`); see `LEGAL_DISCLAIMER.md`.
  - Job pages are read two at a time, about a second apart. A page that fails or comes back in another shape is read again on the next run, rather than storing the listing's short blurb; once the board is still answering 429 after the retries, the run stops reading pages and leaves the rest for the next run, for every account that shares the corpus fetch. The corpus is cached for as long as the board's `Cache-Control` allows (an hour), for runs and Tests alike; Test reads at most 20 job pages and says when it sampled.
  - A job whose page renames it into the title or company filters, or whose description matches a body-exclusion phrase, is kept as ignored, so its page is read once and it never counts as new. A job ignored for a phrase stays ignored if you later remove the phrase.
  - Two accounts (or two searches) share one corpus fetch and read each job page once, then ingest under their own filters. `backend/scripts/backfill_external_id.py` leaves these jobs alone: their id is the board's job URL, their link the employer's.
- **Résumé footer** (by @mrAlishah, #24): an opt-in "name - job title - company" line in small grey type at the foot of every page of a tailored copy's PDF, so a loose page still says whose it is and which role it was written for. Off by default and shown only on a job-linked tailored copy (a Settings section in the résumé editor); base résumés, freeform tailors and existing copies export as before. It sits in the bottom gutter every template already reserves, so page breaks do not move.
- **Word export** (based on work by @mrAlishah): the résumé editor's Download button opens PDF or Word (.docx); the Word file is one plain, editable layout for every template (the PDF's content and section order, Word's own styles, no tables or images), with clickable contact links (phone numbers stay `tel:` links), stray control characters from PDF imports dropped (skill category names included), and the page footer only when the copy's footer switch is on, as for the PDF.
- **Backup before an upgrade:** the first boot of a new release dumps the whole database to `backups/pre_upgrade_<old>_to_<new>_<timestamp>.sql` before anything is migrated (a 2.x database is recognised by its missing `accounts` table; an empty database takes none). The release that last booted is recorded in an install-level `app_meta` row, so later boots of the same release take no backup. If the dump fails the backend logs an ERROR and does not start, leaving the database unmigrated; `JN_SKIP_UPGRADE_BACKUP=1` in `.env` migrates without one. A manual backup before upgrading is still recommended.
- **Image check:** at startup the backend compares its image with the mounted code: every exact pin in `backend/requirements.txt` against the installed packages, python-docx importable, and the release stamped into the image at build time against the code's. A mismatch (typically `git pull` without pulling or rebuilding the images) is one ERROR in the log naming what differs and the fix, `image_outdated` / `image_message` / `image_details` on `/health`, and in the dashboard a "Backend image out of date" health line plus an error toast once per session. The dashboard also warns when its own release differs from the backend's. Word export in an image without python-docx answers a readable 503 instead of a bare 500.
- **Manage accounts:** rename, colour, PIN set/reset, remove (typed name, itemised counts, an automatic database dump first) and "Export my data" (zip of JSON; under Your account for a member, and in the Remove dialog for the owner). Stats are per account; the owner can switch the LLM cost panel to all accounts.

### Changed
- **Unique per account:** company names, job ids and the Persona are unique within an account, not across the install.
- **Settings values** may now live per account (`settings.account_id`; empty = the install value). The `dashboard_api_key` and the other install secrets stay install-wide.
- **LM Studio and Ollama addresses are settings:** Settings › Models shows an LM Studio and an Ollama address while some model uses that provider (owner only; members read the owner's). Empty falls back to `LMSTUDIO_BASE_URL` / `OLLAMA_BASE_URL` from `.env`, then `http://localhost:1234/v1` / `http://localhost:11434`, read at call time; the boxes start empty and show the address in use as their placeholder. An install whose box still holds the address an early 3.0 build filled in (the same one `.env` or the default gives) has it cleared once at startup, so a later `.env` change takes effect; Ollama is no longer hard-coded to localhost, so the containerised backend can reach it at `http://host.docker.internal:11434`.
- **JobSpy 1.3.0** (suggested by @anthony-df-nguyen, #30), from 1.1.82; pandas and numpy are pinned to the versions it brings. A board counts as failed only on the library's error lines, so LinkedIn's "job_type isn't supported" warning no longer marks a LinkedIn run that returned jobs as failed. Google's block reads again ("returned no job data"), and ZipRecruiter's HTTP 307 says the US site redirects this location to a regional site the scraper does not read (1.3.0 no longer logs why ZipRecruiter refused, so a 403 reads as a plain refusal). The markdownify CVE exception in CI is gone.
- **Extension popup:** the Saves to › Change button spans the label and the account name and lines up with API key › Show (the same width).
- **Tooling:** Vitest 4.1.11 (from 2.1.9, Dependabot #11, #12); the GitHub Actions run on their Node 24 majors and on `ubuntu-24.04` instead of `ubuntu-latest`.

### Removed
- **The classic dashboard.** `/classic` and `/classic/…` redirect to the same path without the prefix (`/classic/applications` opens `/applications`), so old bookmarks keep working. The Settings › Display "Classic dashboard" row, the classic upgrade banner and the Tailwind setup that only the v1 screens used are gone; the page reset the redesign relies on is now plain CSS in `frontend/src/base.css`.

### Fixed
- **OpenCode Go returned no text on a reasoning model:** Go serves several models that reason by default and has no reasoning-effort setting, so a scoring call (600 tokens) spent the whole output cap on reasoning and failed with "used the whole output cap on reasoning and returned no text". A Go call now always gets the same output-budget headroom the Claude API calls get; the Go models accept the larger cap. (by @mreid-tt, #33)
- **Two Run alls at once no longer freeze the backend:** when two accounts (or two runs in one account) scraped the same new company at the same time, the first run held an uncommitted H-1B cache row while it waited on the network, and the second run's write of the same row waited for it on the event loop, so every request, run and scheduled job hung until a restart. The H-1B cache is now written in a short session of its own with an upsert, a run never makes a live H-1B lookup while it holds unsaved rows (each scraper looks up its new companies before it writes), and every database connection has a 10 s `lock_timeout`, so a lock wait becomes an error instead of a hang (startup migrations are exempt).
- **Model Catalog for Claude Code without an API key** (by @anthony-df-nguyen, #31): choosing Claude Code (Subscription) in Settings › Model Catalog no longer fails with "No Anthropic API key configured". With no Anthropic key the catalog lists the built-in Claude models; with a key it still loads Anthropic's live list. A member on their own Models never falls back to the owner's key.
- **LinkedIn Personal login no longer treats a live session as logged out** (by @mreid-tt, #27): the session check asks Voyager `/me` first; when `/me` refuses a session that is in fact live, a signed-in surface (`/feed`, `/mynetwork`) reached with the `li_at` auth cookie counts as logged in. A `/login` that redirects to the feed is taken as already signed in, and a login form that never renders because the page went to the feed is treated as a login rather than a timeout. `/jobs` is not a signed-in surface (LinkedIn shows public jobs there), so a revoked cookie still in the jar leads to a fresh login, and a collection that lands on the login wall fails the run with "LinkedIn session expired" instead of reporting 0 jobs. The manual session refresh keeps the 30 s wait for a slow login page.
- **Salary from the job description for freehire.me jobs** (by @volkotyk, #28): the shared inline analysis called the salary extractor with a keyword it does not take, so every job raised a logged and swallowed `TypeError` and no salary came from the description text. Structured salaries were not affected.
- **Hourly, daily, weekly and monthly pay is no longer stored as a yearly salary:** the description extractor read "US$34.32 to $42.13 per hour" as a 34–42 yearly salary, and a yearly figure under 1000 with no "k" is now skipped as well. A tagged amount is left out (as every other source already did) and the text in the description shows it; a yearly range later in the text is still read ("$140k-$220k/year ($67-$105/hour)" gives 140,000–220,000), and an amount tagged yearly itself is read whole even after an hourly figure or a schedule such as "40 hours per week" ("$60–$75 per hour ($124,800–$156,000 annually)" gives 124,800–156,000). An untagged amount under 10,000 is not a yearly salary, and one over 2,000,000 is skipped. An hourly or weekly word inside an aside that closes before the amount ("(exempt or non-exempt hourly rate) role ranges from $140,000 to $160,000") no longer rejects the range. A prefixed or foreign dollar (TT$, J$, HK$, A$, C$, NZ$, "$140,000 AUD") is no longer read as USD, while a "$" glued to a word ("Compensation$102,460 – $141,860") is a missing space and still USD, and on CaribbeanJobs, where a bare "$" is usually the island's dollar, only a figure the description names as USD is stored. JobSpy rows with a non-yearly interval and Jobright, LinkedIn Personal, Levels.fyi, TrulyRemoteWork and CaribbeanJobs salary strings such as "$45/hr" (read as $45K), "$4,000 a month" or "USD 5,000 /mth" follow the same rule. Existing rows are unchanged.
- **A job a scraper filtered out no longer blocks saving it yourself:** an ignored row (kept only so a scraper does not read the same posting again) carries no content hash now, in every source, so saving the same company and title from another site with the extension or adding it by hand reaches the feed instead of answering "already saved earlier and filtered out then". The same URL still gives that answer, and a job already in the feed still catches the same role from another URL. Ignored rows stored with a hash before this are matched by URL only as well.
- **LLM keys go only to their own provider:** a model slot (Scoring, Tailoring, Cover letters, Autofill, Email, the fallback) on another provider than the Primary no longer borrows the Primary's key (an Anthropic key was sent to OpenAI); with no key of its own it uses that provider's `.env` key (owner and inherit only), and a same-provider slot still reuses the Primary's key. OpenAI calls now fall back to `OPENAI_API_KEY` as the model catalog did, and fail at once with "No API key for OpenAI" instead of retrying 401s; OpenRouter, OpenCode Go and LM Studio never receive it. A slot's own key counts only while the slot has its own provider, so a key left in an override that was switched off no longer goes to the Primary's provider; switching an override off in Settings › Models now clears its key as well. Claude API (after `ANTHROPIC_API_KEY`) and OpenRouter with no key fail at once with "No API key for Claude API" / "No API key for OpenRouter" instead of an SDK error retried four times, and an OpenRouter key it rejects is not retried either, so the fallback runs straight away.
- **Résumé and cover-letter PDFs render sandboxed:** the text is printed as HTML, and every account shares the backend's browser, so the page now renders with JavaScript off and no network except Google Fonts (which the templates load). A `<script>` or `<iframe>` in résumé text no longer runs, and an `<img>` or stylesheet pointing at an internal address is blocked and logged. A project link with a `javascript:`, `data:` or `file:` address is left out of the PDF, and the HTML preview (`/api/resumes/{id}/preview`) carries a sandboxing CSP. The templates render exactly as before.
- **Download filenames keep non-Latin names:** the PDF and Word downloads of a résumé and the PDF of a cover letter are named `JoséMüller_…` or `Дана_…` instead of `Jos?M?ller_…` or `____…` (with an ASCII `JoseMuller_…` for older clients).
- **Tracer links no longer break exports on odd résumé data:** with tracer links on, a résumé whose header or contact list is empty (`null`), or whose contact text or address is not plain text (as a PDF import or the API can leave it), no longer fails the PDF, the Word download and the preview with a server error.
- **Work-arrangement detection runs in linear time:** a description with many `<` and no `>` made the tag stripping quadratic (CodeQL py/polynomial-redos); it is now one pass with the same result.
- **Amazon in the company Test scrape and the ATS chip:** testing an amazon.jobs search URL now reads it with the Amazon handler (as the real run does) instead of the generic page reader, and the URL editor, add dialog and row show an Amazon chip.
- **A keyword search with no query says so instead of logging "nothing ran"** (by @mreid-tt, #26): freehire.me and CaribbeanJobs.com need a search term or a URL, so their editor fields say so, Run and Test are blocked with that reason, and the run API answers 409 with it rather than launching an empty run.

## [2.2] — 2026-10-04

Upgrade: `git pull && docker compose pull && docker compose up -d` (or `--build`); reload the extension. The backend image now pins Claude Code 2.1.281 and Codex 0.156.1.

### Added
- **LinkedIn mock account is optional** (by @volkotyk, #20): Settings › LinkedIn gets a "Use a mock account" switch; with it off the session refresh signs in with the personal account. A database that already holds mock credentials keeps using them. A mock login now clears the personal scraper's cookies first, so it can no longer save the personal session as the mock one.
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
- **Multi-page résumé PDFs** (by @funstuie-bit, #19): page gutters live in `@page`, so page 2 onward no longer starts at the paper edge. A résumé that ended within a few lines of a page may now take one more page.
- **Scrape health alerts** (by @volkotyk, #21): only a source that ran in this scrape can alert, so a paused search no longer pages after every run.
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

## [2.1] — 2026-09-16

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
- **Extension** 2.1, same code as 2.0.

### Fixed
- **Auto-scoring and the daily digest on fresh installs** (by @volkotyk, #11): `cv_scores` is created as `json` on a new database, and comparing it with a `jsonb` literal aborted every auto-score pass after a scrape and every digest; both compare as text now. Run errors no longer store or return the failed SQL statement and its parameters.
- **Cover letters for hand-logged jobs** (by @volkotyk, #7): a job logged from Applications has no stored description, and generation refused it. The letter worker now resolves the text the way tailoring does (description, then a live fetch saved to the job, then the cached page); logging an application queues that fetch; the description backfill covers applied jobs.
- **Feed paging under a filter:** a filter change starts a new load generation, so a page still in flight from the old filter is dropped instead of appended; every job sort carries an id tiebreak so pages never overlap.
- **Handler filters:** Greenhouse tolerates spaces in department and office ids and logs what it discards; Rippling compares country and region through the parser; Ashby reads secondary locations; Lever quotes filter values.
- **Cairo and Bengaluru in a US feed:** the Amazon handler honoured no country filter, and country-first strings ("IN, KA, Bengaluru") read as Indiana; both fixed and existing rows re-parsed.
- **Select boxes** in Paper and Green Paper no longer clip descenders.

## [2.0] — 2026-09-06

The new dashboard is the app at `http://localhost`; the previous one stays at `/classic` for one more release and old `/v2/…` links redirect. Upgrade: `git pull`, `docker compose up --build -d`.

### Security (extension 2.0)
- **Extension 2.0:** the header rules that let the Job Feed frame a posting (removing `X-Frame-Options` and `Content-Security-Policy`) applied to every page in the browser. They now apply only to sub-frames opened by the dashboard's own host, never to the dashboard's own responses (its cached-page reader is sandboxed by a CSP header), and follow the server URL set in the popup; top-level pages and frames opened by any other site keep their headers. Remove and reinstall the extension to pick it up.
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

## [1.1] — 2026-08-16

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

## [1.0] — 2026-08-15

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

[Unreleased]: https://github.com/vesaias/JobNavigator/compare/v3.0...HEAD
[3.0]: https://github.com/vesaias/JobNavigator/compare/v2.2.0...v3.0
[2.2]: https://github.com/vesaias/JobNavigator/compare/v2.1.0...v2.2.0
[2.1]: https://github.com/vesaias/JobNavigator/compare/v2.0.0...v2.1.0
[2.0]: https://github.com/vesaias/JobNavigator/compare/v1.1.0...v2.0.0
[1.1]: https://github.com/vesaias/JobNavigator/compare/v1.0.0...v1.1.0
[1.0]: https://github.com/vesaias/JobNavigator/releases/tag/v1.0.0
