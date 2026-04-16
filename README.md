# JobNavigator

Self-hosted job search automation — scrape any career portal or use job aggregator, AI scoring against your profile, resume tailoring with custom themes, Telegram notifications and tracking in one system. 

<p align="center">
  <img src="docs/jobnavigator.gif" alt="JobNavigator Demo" width="100%">
</p>

## How It Works

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              JOB DISCOVERY                                  │
│                                                                             │
│   Career Pages        │  Aggregators            │  Chrome Extension         │
│                       │                         │                           │
│   Any site via        │  JobSpy: LinkedIn,      │  Passive LinkedIn         │
│   Playwright          │  Indeed, ZipRecruiter,  │  capture while            │
│                       │  Google Jobs            │  browsing                 │
│   10 ATS endpoints:   │                         │                           │
│   Workday, Greenhouse │  LinkedIn Personal      │  Save any job from        │
│   Lever, Ashby,       │  collections            │  any page                 │
│   Oracle, Phenom,     │                         │                           │
│   TalentBrew,         │  Levels.fyi             │                           │
│   Rippling, + custom  │                         │                           │
│                       │                         │                           │
└───────────────────────┴────────────┬────────────┴───────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                                PROCESSING                                   │
│                                                                             │
│   Dedup ────── URL hash + cross-source content hash                         │
│   Filters ──── Title / company include & exclude, body exclusion phrases    │
│   H-1B ─────── Company LCA data from MyVisaJobs (cached)                    │
│   Salary ───── Extracted from posting, H-1B data, description               │
│                                                                             │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                                 JOB FEED                                    │
│                                                                             │
│   Review ───── Dynamic filters, sorting, detail panel                       │
│   Decide ───── Save promising jobs, skip the rest, score with AI            │
│                                                                             │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                               AI CV SCORING                                 │
│                                                                             │
│   Providers ── Claude API, Claude CLI, OpenAI, Ollama, OpenAI-compatible    │
│   Depths ───── Light (scores only) or Full (report + keyword analysis)      │
│   Multi-CV ─── Score against multiple CVs, compare fit per role             │
│                                                                             │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              RESUME BUILDER                                 │
│                                                                             │
│   Templates ── 8 built-in, auto-discovered (drop a folder to add yours)     │
│   AI Tailor ── Rewrites bullets and keywords based on scoring report        │
│   Export ───── PDF via Playwright, page count indicator                     │
│                                                                             │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                                  TRACK                                      │
│                                                                             │
│   Tracer ───── Unique links per resume, tracks who opened your CV           │
│   Gmail ────── Auto-detects responses, updates application status           │
│   Telegram ─── Job alerts, daily digest, scrape health notifications        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Features

| Feature | Description |
|---------|-------------|
| **Multi-Source Discovery** | 6 scraping tiers: career pages (Playwright + 10 ATS), JobSpy (4 boards), LinkedIn Personal, Levels.fyi, Jobright.ai, Chrome Extension |
| **AI CV Scoring** | Multi-provider (Claude, OpenAI, Ollama), light/full depth, per-CV comparison, keyword analysis, requirement mapping, ATS tips |
| **Resume Builder** | 8 templates (auto-discovered - add yours), AI tailoring per job, PDF export, tracer links to track opens |
| **Smart Dedup** | Two-layer: URL hash + cross-source content hash. Configurable tracking param stripping |
| **Job Feed** | Filters, sorting, keyboard shortcuts (j/k/s/x/e), scoring reports, bulk operations |
| **Application Board** | Kanban pipeline with drag-and-drop, status transition history |
| **Chrome Extension** | Passive LinkedIn capture + save any job from any page |
| **Gmail Monitor** | OAuth2 polling, auto-classifies responses, updates application status |
| **Telegram Alerts** | New job alerts, daily digest, scrape health, inline action buttons |
| **H-1B Data** | Company LCA lookups from MyVisaJobs, JD exclusion scanning |
| **Scheduling** | Cron-based: scraping, email checks, backups, cleanup, auto-reject |
| **Dark Mode** | Full Tailwind dark mode across all pages |

## Quick Start

```bash
git clone https://github.com/vesaias/JobNavigator.git
cd JobNavigator
cp .env.example .env
# Edit .env if needed (optional — API keys can be set from dashboard)

docker compose up --build -d
```

Open `http://localhost`. No API key required on first run.

**First steps:**
1. Settings > AI tab — configure your LLM provider and API key
2. Companies — activate a few seed companies or add your own
3. Searches — configure a keyword search or activate LinkedIn Personal
4. Upload your CV in Settings for AI scoring

## Chrome Extension ("The Navigator")

1. `chrome://extensions/` → Developer mode → Load unpacked → select `extension/`
2. Toggle LinkedIn capture on, browse job collections
3. Click "Send to JobNavigator" to import

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

## Privacy

**JobNavigator is self-hosted — NOT a hosted service.** Your CV, job data, and credentials stay on your machine. Data is sent only to the AI provider you configure. We do not collect, store, or have access to any of your data.

## Disclaimer

Personal and educational use only. Not affiliated with LinkedIn, Indeed, Jobright.ai, or any job platform. Some scraping features are disabled by default and require explicit opt-in. You are responsible for complying with the Terms of Service of any platform you interact with. See [LEGAL_DISCLAIMER.md](LEGAL_DISCLAIMER.md).

## License

[MIT](LICENSE)
