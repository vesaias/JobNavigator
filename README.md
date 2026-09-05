# JobNavigator

Self-hosted job search automation — scrape any career portal or use job aggregator, AI scoring against your profile, resume tailoring with custom themes, persona-based application auto-fill, Telegram notifications and tracking in one system. 

<p align="center">
  <img src="docs/jobnavigator.gif" alt="JobNavigator Demo" width="100%">
</p>

## How It Works

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                               JOB DISCOVERY                                 │
│                                                                             │
│   Career Pages          │  Aggregators            │  Chrome Extension       │
│                         │                         │                         │
│   Any site via          │  JobSpy: LinkedIn,      │  Passive LinkedIn       │
│   Playwright            │  Indeed, ZipRecruiter,  │  capture while          │
│                         │  Google Jobs            │  browsing               │
│   11 ATS endpoints:     │                         │                         │
│   Workday, Greenhouse   │  LinkedIn Personal      │  Auto-fill based on     │
│   Lever, Ashby,         │  collections            │  your persona input     │
│   Oracle, Phenom,       │                         │  and question bank      │
│   TalentBrew, Rippling  │  Jobright.ai            │                         │
│   SmartRecruiters,      │  Levels.fyi             │  Save any job from      │
│   + custom              │  freehire.me            │  any page               │
│                         │                         │                         │
└─────────────────────────┴───────────┬─────────────┴─────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                                PROCESSING                                   │
│                                                                             │
│   Dedup ────── URL-hash dedup, tracking params stripped                     │
│   Filters ──── Title / company include & exclude, body exclusion phrases    │
│   H-1B ─────── Company LCA data from MyVisaJobs (cached)                    │
│   Salary ───── Extracted from posting, H-1B data, description               │
│                                                                             │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                                 JOB FEED                                    │
│                                                                             │
│   Review ───── Dynamic filters, sorting, detail panel                       │
│   Decide ───── Save promising jobs, skip the rest, score with AI            │
│                                                                             │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              AI RESUME SCORING                              │
│                                                                             │
│   Providers ── Claude API, Claude CLI, OpenAI, Ollama                       │
│   Depths ───── Light (scores only) or Full (report + keyword analysis)      │
│   Multi ────── Score against multiple resumes, compare fit per role         │
│                                                                             │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           RESUME + COVER LETTER                             │
│                                                                             │
│   Templates ── 8 resume + 8 cover-letter, auto-discovered (add your own!)   │
│   AI Tailor ── Rewrites resume bullets/keywords from the scoring report     │
│   AI Letter ── Job-specific cover letters from resume + JD, voice presets   │
│   Export ───── Live-preview PDF via Playwright with export                  │
│                                                                             │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                                   TRACK                                     │
│                                                                             │
│   Tracer ───── Unique links per resume/letter, tracks who opened them       │
│   Gmail ────── Auto-detects responses, updates application status           │
│   Telegram ─── Job alerts, daily digest, scrape health notifications        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Features

| Feature | Description |
|---------|-------------|
| **Multi-Source Discovery** | 7 scraping tiers: career pages (Playwright + 11 ATS), JobSpy (4 boards), LinkedIn Personal, Levels.fyi, Jobright.ai, freehire.me, Chrome Extension |
| **AI Resume Scoring** | Multi-provider (Claude, OpenAI, Ollama), light/full depth, per-resume comparison, keyword analysis, requirement mapping, ATS tips. **Prompt caching** on Anthropic cuts repeat-scoring cost ~50%. |
| **Resume Builder** | 8 templates (auto-discovered - add yours), AI tailoring per job, PDF export, tracer links to track opens (cover letters too) |
| **Cover Letters** | AI-generated per job, grounded in the paired resume + persona; editable voice presets, 8 templates, PDF export, prompt-cached generation |
| **Smart Dedup** | URL-hash dedup with configurable tracking-param stripping; content hash stored per job for cross-source matching |
| **Job Feed** | Filters, sorting, keyboard shortcuts (j/k/s/x/e), scoring reports, bulk operations, in-app job preview |
| **Application Board** | Kanban pipeline with drag-and-drop, status transition history |
| **Chrome Extension** | Passive LinkedIn capture + save any job from any page |
| **Application Autofill** | Generate persona-grounded answers to free-text application questions on any job site, from the extension — review with a length picker, then insert, copy, or save to a reusable Q&A bank |
| **Gmail Monitor** | OAuth2 polling, auto-classifies responses, updates application status |
| **Telegram Alerts** | New job alerts, daily digest, scrape health, inline action buttons |
| **H-1B Data** | Company LCA lookups from MyVisaJobs, JD exclusion scanning |
| **Scheduling** | Cron-based: scraping, email checks, backups, cleanup, auto-reject |
| **Dark Mode** | Full Tailwind dark mode across all pages |

> **Note on the Job Feed preview pane:** the detail panel renders the live job posting in an `iframe`. Many career sites block being framed (via `X-Frame-Options` / CSP `frame-ancestors`, or cross-origin scripts that fail when embedded), so the in-app preview works best with a browser extension that strips frame-blocking headers (e.g. an "ignore X-Frame-Options" extension). Without one, some postings show blank — use the "Open" button to view them in a new tab. Applied jobs fall back to a cached snapshot that always renders.

## Quick Start

```bash
git clone https://github.com/vesaias/JobNavigator.git
cd JobNavigator
cp .env.example .env
# Edit .env if needed (optional — API keys can be set from dashboard)

docker compose up --build -d
```

Open `http://localhost`. On first run, click "Sign In" with a blank API key to proceed. Set a real key from Settings > General once you've accessed the dashboard.

**First steps:**
1. Settings > AI tab — configure your LLM provider and API key
2. Companies — activate a few seed companies or add your own
3. Searches — configure a keyword search or activate LinkedIn Personal
4. Resumes — create your resume (or import an existing PDF); it powers AI scoring

## Chrome Extension ("The Navigator")

**What it does:**
- **Unblocks the Job Feed preview.** Strips frame-blocking headers (`X-Frame-Options` / CSP `frame-ancestors`) so job postings render in the in-app `iframe` preview pane instead of showing blank.
- **Captures your LinkedIn collections.** As you browse your personalized **Recommended** and **Top Applicant** collections (`linkedin.com/jobs/collections/*`), it passively collects the job IDs, then imports them into the Job Feed with full details (title, company, description, real apply URL).
- **Fills application answers.** On any job site, focus a free-text question and click the Navigator button to generate a first-person answer based on your **Persona** + saved **Q&A bank**. Enable it with the **Application Autofill** toggle in the popup, and fill out your Persona (`/persona`) first so answers have something to ground on. Configure the model/prompt in **Settings → AI**.

**Install:**
1. `chrome://extensions/` → Developer mode → Load unpacked → select `extension/`
2. Toggle LinkedIn capture on, browse your personal job collections
3. Click "Send to JobNavigator" to import

**Make sure it works:** the import fetches each job's full data through LinkedIn's Voyager API using a **mock LinkedIn account** — set its email + password in **Settings → Accounts → LinkedIn Extension** before importing. Without it, capture still collects IDs but the import returns nothing.

## Optional Integrations

**Telegram** — Create bot via @BotFather, set token in `.env`, enter chat ID in Settings.

**Gmail** — Run `python backend/gmail_oauth_setup.py`, set OAuth credentials in `.env`.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI, SQLAlchemy, APScheduler, Playwright |
| Frontend | React 18, Tailwind CSS, Vite, Recharts |
| Database | PostgreSQL 16 |
| Infrastructure | Docker Compose, Caddy, nginx |
| AI | Anthropic SDK, OpenAI SDK, Ollama, Claude Code CLI |
| Extension | Chrome Manifest V3 |

## Contributing

PRs welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). Easy wins: new ATS scrapers, new resume templates, UI polish.

## Backups

The scheduled `db_backup` job writes a `pg_dump` of the whole database into `backups/` (five kept, on the `backup_cron` schedule); you can also trigger one from the dashboard. **Those dumps contain the `settings` table verbatim, and JobNavigator is configured from the dashboard — so the dump holds your LLM API key (`llm_api_key`) and your dashboard key (`dashboard_api_key`) in clear text.** `GET /api/settings` redacts both and no route serves a dump file, so this is an at-rest concern only, but treat a dump exactly as you would treat `.env`: local-only, never committed, never shared. `backups/` is in `.gitignore` for that reason — keep it there, and re-check it if you move the directory or change your backup path.

## Security

Found a vulnerability? See [SECURITY.md](SECURITY.md). Please don't open public issues for security bugs.

## Privacy

**JobNavigator is self-hosted — NOT a hosted service.** Your resume, job data, and credentials stay on your machine. Data is sent only to the AI provider you configure. We do not collect, store, or have access to any of your data.

## Disclaimer

Personal and educational use only. Not affiliated with LinkedIn, Indeed, Jobright.ai, or any job platform. Some scraping features are disabled by default and require explicit opt-in. You are responsible for complying with the Terms of Service of any platform you interact with. See [LEGAL_DISCLAIMER.md](LEGAL_DISCLAIMER.md).

## License

[MIT](LICENSE)
