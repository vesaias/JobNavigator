# Getting started

A first-run walkthrough, from an empty install to the first scored jobs. It follows the four steps the welcome screen shows, then covers the optional parts. Every setting mentioned lives in the dashboard; only secrets go in `.env`.

## Let an AI assistant drive

The repo is written to be read by coding agents: [CONTRIBUTING.md](../CONTRIBUTING.md) and [DESIGN-SYSTEM.md](../frontend/src/DESIGN-SYSTEM.md) describe the layout and how to run everything, and the settings, scrapers and API routes are all plain Python and JSX. If you use Claude Code, Codex CLI, Cursor or a similar tool, open it in the cloned folder and ask it to walk you through this guide. It can check your backend logs when a scrape or score fails, explain any setting, add a company's career page in the right format, or fix a scraper for a site the handlers do not cover yet. Most of JobNavigator itself was built that way.

## 0. Install

You need Docker (Docker Desktop on Windows/macOS, Docker Engine + Compose on Linux) and about 4 GB of disk for the images.

```bash
git clone https://github.com/vesaias/JobNavigator.git
cd JobNavigator
cp .env.example .env
docker compose pull && docker compose up -d
```

That pulls the release images from GHCR (about 2 GB, Playwright's Chromium is the big part). `docker compose up --build -d` builds the same images from source instead, which takes a few minutes. Then open `http://localhost`.

**Sign in.** The first login asks for an API key. Leave it blank and continue: with no key set, the dashboard is open. Set one right away under **Settings › System › Advanced** (dashboard API key), then sign in again with it. That key is what the Chrome extension will also use.

## 1. Settings › AI: pick a provider

Everything that scores, tailors or writes needs a language model. Choose one primary provider under **Settings › AI › Models**:

| Provider | What you need | Cost |
|---|---|---|
| Claude API | an Anthropic API key | per token |
| OpenAI | an OpenAI API key | per token |
| OpenRouter | an OpenRouter key; hundreds of models, live search | per token |
| Ollama | Ollama running on the host with a pulled model, no key; see the note below | free |
| LM Studio | LM Studio's local server running on the host, no key; see the note below | free |
| Claude Code | a Claude Pro/Max subscription, see below | subscription |
| Codex CLI | a ChatGPT subscription, see below | subscription |
| Antigravity CLI | a Google Antigravity subscription, see below | subscription |
| OpenCode Go | a Go subscription key; OpenAI-compatible endpoint, no login | subscription |

Pick the model from the list (or search the provider's catalog under Model catalog). Save. The API key box under the Primary (and on each override) holds one key per provider: paste the Anthropic key once and every slot on Claude API uses it; switching a slot to OpenAI shows the OpenAI key instead, and switching back brings the Anthropic key back. An empty box uses the provider's variable from `.env` (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, `OPENCODE_API_KEY`) for the owner and for members who inherit Models.

**Ollama or LM Studio on the host, backend in Docker.** Inside the container `localhost` is the container itself, so the default addresses (`http://localhost:11434` for Ollama, `http://localhost:1234/v1` for LM Studio) do not reach your host. Set the address under **Settings › AI › Models** (the Ollama and LM Studio address boxes appear while some model uses that provider), e.g. `http://host.docker.internal:11434` for Ollama and `http://host.docker.internal:1234/v1` for LM Studio, or put `OLLAMA_BASE_URL` / `LMSTUDIO_BASE_URL` in `.env` and run `docker compose up -d backend`. The addresses are install-wide: only the owner edits them.

**Subscriptions instead of API keys.** The Codex, Claude Code and Antigravity CLIs are installed in the backend image, so you log in through the container:

- Codex CLI: `docker compose exec backend codex login --device-auth`, follow the URL, then `docker compose exec backend codex login status` to confirm. The login persists in the `codex_auth` Docker volume.
- Claude Code: `docker compose exec backend claude setup-token`, follow the URL and paste the code; it prints a long-lived token. Put it in `.env` as `CLAUDE_CODE_OAUTH_TOKEN=...` and run `docker compose up -d backend` so the container picks it up (or paste it into Settings › Models › Claude Code token).
  - Several accounts: a member whose Models section is set to Own logs in with its own subscription. `docker compose exec backend python -m backend.scripts.cli_login <codex|agy|claude> "<account name>"` prints the exact command for that account (Codex and Antigravity get their own login folder; for Claude Code the member pastes its `claude setup-token` token into Settings › Models).
- Antigravity CLI: `docker compose exec -it backend agy`. The container has no browser, so the CLI prints a URL and asks for the code it shows. The login persists in the `antigravity_auth` Docker volume.
- OpenCode Go: no container login. It is an OpenAI-compatible endpoint, so just paste the Go API key under **Settings › AI** and pick **OpenCode Go**. A member whose Models section is Own pastes its own Go key there; it never uses the owner's. Go is a coding-agent plan meant for the key holder's own use, so on a household install each member should set their own key rather than inherit the owner's.

When a plan limit is hit, the call fails over to the fallback provider instead of retrying.

Also on this tab:

- **Scoring depth**: Light gives a 0–100 score and one line, cheap. Full adds keyword coverage, requirement mapping and a written report. Every company and search can override this.
- **Fallback provider**: used only when the primary call fails or is rate-limited. Pick a cheap model from a different provider.
- A provider and model per feature (scoring, tailoring, cover letters, email classification, autofill) if you want to mix, otherwise they follow the primary.

Sanity check: open **Stats** later and look at the LLM cost panel; every call is logged there.

## 2. Résumés and Persona: who you are

Scoring compares each job with your **base résumés**, so you need at least one.

**Résumés › New base résumé** opens the structured editor (header, summary, experience, education, skills, projects…). Faster: **Import PDF…** parses an existing résumé with the LLM you just configured. The PDF must contain selectable text, not a scanned image. Check the result, fix what the parser got wrong, save.

You can have several base résumés (say, one for data roles, one for management). Jobs score against each and keep the best.

**Persona** is the single profile behind autofill, cover letters and tailoring: contact details, work authorization, compensation, preferences, the résumé text and a Q&A bank of stock answers ("Why do you want to work here?", "Salary expectations"). Open **Persona**, use the import at the top to fill it from the base résumé you just made, then complete work authorization and the Q&A bank by hand. It autosaves.

## 3. Companies: career pages

**Companies** is your target list. Nothing creates companies for you; you add them (or apply to a job, which creates its company).

A few well-known companies are seeded but switched off so you can see the shape. To add your own: **Add company**, give it a name and paste the career page URL. The ATS is auto-detected (Workday, Greenhouse, Lever, Ashby, SmartRecruiters, Rippling, Oracle HCM, Phenom, TalentBrew, Amazon, Uber, Meta, Google; anything else goes through the generic Playwright reader). Per company you can set:

- **Score new jobs against**: which base résumés, and Off / Light / Full.
- **Title include / exclude** and other import rules so only relevant roles come in.
- **Scrape interval** (empty = the global one from Settings) and a priority tier.
- **Aliases**: other spellings of the name so applications and emails match up.

Turn the company on and press its run button once. The result shows on the row (open roles, last scrape, "needs attention" when a scrape returned nothing).

## 4. Searches: job boards

**Searches** discovers jobs outside your dedicated company list. **New search**, choose a mode:

- **Keyword (JobSpy)**: LinkedIn, Indeed, ZipRecruiter and Google in one go. Search term, location, hours old, results wanted, remote, job type. Results are not deduplicated across boards as tightly as the ATS scrapers, so start with a modest results count.
- **Levels.fyi**, **Jobright.ai**, **freehire.me**, **CaribbeanJobs.com**: paste a URL from the site with your filters applied. CaribbeanJobs.com answers many networks with a Cloudflare challenge that the scraper does not pass; from such a network its runs and Tests fail and say so. Read the terms note in its editor and `LEGAL_DISCLAIMER.md` first.
- **TrulyRemoteWork.com**: reads the board's full corpus of worldwide-remote roles. Every listing is remote with no location restriction, so it needs no term or URL — narrow it with the title filters and Company include / exclude. **New jobs per run** caps how many new jobs' pages one run opens; the first runs work through the board in steps of that size. The board asks that its content not be used for training; see `LEGAL_DISCLAIMER.md`.
- **Creative boards**: illustration, design, art direction, animation and game-art jobs from Behance, Himalayas, Dribbble, ArtStation, Eluta, Wana Create, Hollylist and Work With Indies, read from each site's own API or feed (no login, no Apify key). Tick the boards, enter one search term per search ("illustrator", "motion designer") and narrow with the title filters. Remote applies on every board. Location is one city name (Behance and Himalayas ignore it); Country applies on Himalayas and, on Remote searches, drops the Behance jobs that are not open to that country. Eluta (Canadian employer sites) allows 10 RSS checks a day from one address, so give a search with Eluta a run interval of 1440 minutes. Read the terms note in its editor and `LEGAL_DISCLAIMER.md` first.
- **LinkedIn Personal**: your own LinkedIn session through Playwright. Read the notice in Settings › Integrations › LinkedIn first.
- **Apify**: paid scrapers from the Apify Store for Indeed, LinkedIn, Glassdoor, Behance and Hollylist (fallbacks for the creative boards), and keyword search across every company on Greenhouse, Lever, Ashby and Workday. Put your Apify API token in Settings › Apify and press **Check key**. Apify bills your account for each result, so keep Results wanted low (at most 200 per board) and the run interval long. A new Apify search starts paused; resume it on its card once the boards look right. Every run carries a spend cap and stops after 15 minutes, and Test asks before it runs, with the estimated cost. With several accounts each account uses its own token; the owner can let a member inherit the owner's token (and pay for that member's runs). **The Apify Creator plan does not work:** it cannot run Store actors, and every board fails with `403 public-actor-disabled`. Use the Free plan or a paid plan.

Each search has its own auto-scoring depth, title include/exclude, company include/exclude, minimum score, and a run interval. "Skip my active companies" leaves out companies you already scrape directly. Run it once by hand; afterwards the scheduler runs it on its interval.

Two searches are always present and cannot be run or deleted: **Extension** and **Extension LI**. They are the inboxes for jobs the Chrome extension sends.

## 5. Jobs: the feed

**Jobs** is where everything lands. Filters on the left (status, company, source, location, arrangement, H-1B verdict, score, salary), sorting on top, keyboard shortcuts under `?` (j/k move, s save, x skip, a applied, e/o open the posting).

From a row you can:

- **Score** it by hand (pick résumé and depth), or several at once with the checkboxes.
- **Tailor**: copies a base résumé for this job with a review step. The copy scores itself and shows as ✦.
- **Cover letter**: generated from the paired résumé, your Persona and a voice preset.
- **Save** moves the job into Applications; **Skip** hides it.

One posting is one job, however many sites list it: a copy (the same posting under another link, the same role in another city, or a repost) is listed on the original's row under **Also listed** and kept out of the feed; Settings › Copies of a posting can send any kind to New instead. **Open** and the preview use the employer's own posting whenever one is known; the **Link** filter (Direct, Board link; Easy Apply counts as Direct) shows which jobs have one, and a mock LinkedIn account (step 8) finds it for LinkedIn listings. A job's posting is checked when you open it: a closed one gets a red dot on its card and **Closed posting** in its panel, and the **Posting** filter (Open / Closed) appears once one is found.

The posting preview is an iframe. Sites that refuse framing stay blank unless the extension is installed (see below); **Open** always works.

## 6. Applications

Saved jobs appear in **Applications** with stages (applied, screening, interview, offer, …). Move them along the stepper, add notes and interviews, and read the status history. Stats builds the funnel and Sankey from these transitions. Every stage change has an undo.

## 7. The Chrome extension ("The Navigator")

Install: `chrome://extensions` › Developer mode › **Load unpacked** › the `extension/` folder of the repo. Open the popup, go to its settings and enter the server URL (`http://localhost`) and the dashboard API key from step 0.

It gives you:

- **Posting preview**: lifts the frame-blocking headers only for frames the dashboard opens, so previews of most career pages work.
- **Save any job**: from any page, one click sends title, company, URL and the description to the Extension search.
- **LinkedIn capture**: while you browse `linkedin.com/jobs/collections/*` it collects job ids and imports them with full details through the mock account's session (Settings › LinkedIn, step 8); do not use your real account as the mock.
- **Autofill**: on ATS application forms it fills fields from your Persona and drafts answers to free-text questions with the LLM (toggle in the popup).

If you change the extension's files later, remove and re-add it; a plain reload does not pick up new URL patterns.

## 8. Optional integrations

**Telegram**: create a bot with @BotFather, put the token in `.env` as `TELEGRAM_BOT_TOKEN`, restart, then enter your chat id under Settings › Integrations › Notifications and enable notifications. You get new-job alerts, a daily digest and scrape health, with inline actions.

**Gmail**: create OAuth credentials in Google Cloud (Gmail read-only scope), put client id and secret in `.env` and restart. In the same OAuth client add `<your dashboard address>/api/gmail/callback` (e.g. `http://localhost/api/gmail/callback`) under Authorized redirect URIs. Then each account connects its own mailbox under Settings › Email classification › Gmail › Connect Gmail. The older route still works for the owner: run `py backend/gmail_oauth_setup.py` (or `python`) on your machine once and paste the refresh token it prints into `.env` as `GMAIL_REFRESH_TOKEN`; the owner uses it until they connect in the app. Members never use it. The backend then polls each connected mailbox, classifies replies and updates the matching application.

**LinkedIn**: Settings › LinkedIn has two sessions, each with its own **Sign in** (LinkedIn emails a PIN; the row asks for it). The **Main account** is yours and only LinkedIn Personal searches use it. The **Mock account** is a separate LinkedIn account you create for the tool: the extension's LinkedIn capture uses it, and after every scrape it looks up the employer's own link for LinkedIn listings (one request every 2 seconds, up to 200 per run). It is optional, but without it LinkedIn listings keep their LinkedIn link. Never enter your real account as the mock one; the lookup refuses to run on it.

**H-1B**: Settings › Pipeline holds the global exclude phrases scanned in every description and the cron that refreshes the sponsorship dataset. Ignore it if visa sponsorship is not your concern.

## Accounts

One install can hold up to five accounts, for a household or a couple of friends. Skip this section if it is only you; with one account the account switcher stays out of sight and Settings › Accounts holds just your own row (PIN, API token, name and colour).

- **Adding people.** Settings › Accounts (the first section) › **+ Add account**. Give a name and a colour. PINs are optional for everyone, the owner included: an account without a PIN opens from the picker with one click. Set the owner's 4-digit PIN (Settings › Accounts › Set PIN) if a member should not be able to open the owner's account; the owner's PIN also opens any member's account. The owner can rename and recolour any account there (**Edit**).
- **Copy from.** The Add dialog can start the new account from a copy of an existing one: Persona (or just the Q&A bank), base résumés, companies, searches, settings, cover-letter voices and global excludes. Pick what you want; jobs, applications and letters are never copied. Copied companies and searches are due at once. Later, **Copy from…** on Companies and Searches copies one row from another account.
- **Switching.** The rail footer shows who is signed in; click it, or press Ctrl+Shift+1 to 5 (the Control key on a Mac too: ⌃⇧1–5, since ⌘⇧3–5 take screenshots), to switch. A PIN account asks for its PIN. A fresh browser opens the picker first. Each browser remembers its own account, so a switch moves every open tab of that browser: the other tabs show "This tab was switched to …" and save nothing until they reload. Unsaved edits are saved to the old account before the switch.
- **Shared and own.** Scraping is shared: the same careers page or search is fetched once for everyone who watches it, and each account then filters, de-duplicates and scores for itself. Everything the person works with (jobs, applications, résumés, letters, Persona, searches, companies, Stats, activity) is separate and invisible to the others. Settings are tagged per section: the owner chooses **Inherit** (the member sees the owner's values) or **Own** (the member keeps theirs). Install-wide items (Advanced, backups, scraper limits) stay with the owner; a member can unlock them for 15 minutes by entering the owner's PIN. Without an owner PIN that unlock is a plain **Unlock** button, so the owner sections are only a privacy latch.
- **Telegram.** Each account either uses the household bot or its own bot. Under Settings › Notifications › **Link Telegram** shows a one-time code; send `/start <code>` to the bot and that chat belongs to the account. Alerts, the digest and the inline buttons then go to, and act on, that account only.
- **Gmail.** Each account connects its own mailbox under Settings › Email classification › Gmail › **Connect Gmail** (the OAuth client in `.env` is shared, see step 8).
- **Extension.** With two or more accounts the popup's settings gain a **Saves to** row. Choose the account (a PIN account asks for its PIN); every save, LinkedIn capture and autofill then goes to that account.
- **Logins by subscription.** A member whose Models section is set to Own can use their own Claude, Codex or Antigravity login: `docker compose exec backend python -m backend.scripts.cli_login <codex|agy|claude> "<account name>"` prints the exact command to run.
- **Export and removal.** A member downloads its own data under Settings › Your account › Export my data (a zip). The owner removes an account under Settings › Accounts by typing its name; the Remove dialog offers the same export of that account's data, and a full database backup is taken first.

## 9. Scheduling, backups, upkeep

Settings › Pipeline › Scheduler holds every interval and cron: scraping, email polling, backups, cleanup of old unsaved jobs, auto-reject of stale applications. Each cron field explains itself and offers presets. The scrape interval counts from the last scheduled scrape, so restarts do not reset it; one that is overdue runs two minutes after the backend starts. Crons (backups, cleanup) run only while the machine is on.

**Telemetry.** After the first sign-in the owner is asked once whether the install may send anonymous scraper/AI health (**Essentials**) and app usage (**Yes**) to help the project see what needs maintaining first; Settings › Telemetry changes it and lists what is sent. Nothing is sent before that choice, and `JN_TELEMETRY=off` in `.env` turns it off for good.

Backups are plain-SQL `pg_dump` files (`backups/jobnavigator_<timestamp>.sql`, newest 5 kept) written on the backup cron; you can trigger one from Settings › System. Removing an account takes one first (`backups/pre_remove_<timestamp>_<name>.sql`; the newest 5 are kept, older ones are deleted on the next removal). The files are made restorable on the bundled postgres:16 (the pg17-only `SET transaction_timeout` line is stripped). To restore into an empty database, strict mode:

```bash
docker compose exec -T db sh -c 'psql -U $POSTGRES_USER -d $POSTGRES_DB -v ON_ERROR_STOP=1 -q' < backups/<file>.sql
```

Dumps you take yourself in custom format (`pg_dump -Fc`, `*.dump`) restore with `pg_restore` instead:

```bash
docker compose exec -T db sh -c 'pg_restore -U $POSTGRES_USER -d $POSTGRES_DB --clean --if-exists' < backups/<file>.dump
```

To try a copy of your data elsewhere without it scraping, mailing or backing up as the real install, set `JN_SCHEDULER_DISABLED=1` in that copy's `.env`; the scheduler then does not start (manual runs still work).

Update: `git pull && docker compose pull && docker compose up -d` (or `--build` if you build from source). Tables and settings migrate on startup; nothing to run by hand. `git pull` alone is not enough — the images must be pulled or rebuilt; an image older than the code is reported in the backend log, on `/health` (`image_outdated`) and in the dashboard's health line.
