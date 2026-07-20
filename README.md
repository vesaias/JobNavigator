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
│   11 ATS endpoints:   │                         │                           │
│   Workday, Greenhouse │  LinkedIn Personal      │  Save any job from        │
│   Lever, Ashby,       │  collections            │  any page                 │
│   Oracle, Phenom,     │                         │                           │
│   TalentBrew, Rippling│  Levels.fyi             │                           │
│   SmartRecruiters,    │                         │                           │
│   + custom            │                         │                           │
│                       │                         │                           │
└───────────────────────┴────────────┬────────────┴───────────────────────────┘
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
│                             AI RESUME SCORING                               │
│                                                                             │
│   Providers ── Claude API, Claude CLI, OpenAI, Ollama, OpenAI-compatible    │
│   Depths ───── Light (scores only) or Full (report + keyword analysis)      │
│   Multi ────── Score against multiple resumes, compare fit per role         │
│                                                                             │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          RESUME + COVER LETTER                              │
│                                                                             │
│   Templates ── 8 resume + 8 cover-letter, auto-discovered (add your own)    │
│   AI Tailor ── Rewrites resume bullets/keywords from the scoring report     │
│   AI Letter ── Job-specific cover letters from resume + JD, voice presets   │
│   Export ───── PDF via Playwright, page count indicator                     │
│                                                                             │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                                  TRACK                                      │
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
| **Multi-Source Discovery** | 6 scraping tiers: career pages (Playwright + 11 ATS), JobSpy (4 boards), LinkedIn Personal, Levels.fyi, Jobright.ai, Chrome Extension |
| **AI Resume Scoring** | Multi-provider (Claude, OpenAI, Ollama), light/full depth, per-resume comparison, keyword analysis, requirement mapping, ATS tips. **Prompt caching** on Anthropic cuts repeat-scoring cost ~50%. |
| **Resume Builder** | 8 templates (auto-discovered - add yours), AI tailoring per job, PDF export, tracer links to track opens (cover letters too) |
| **Cover Letters** | AI-generated per job, grounded in the paired resume + persona; editable voice presets, 8 templates, PDF export, prompt-cached generation |
| **Smart Dedup** | URL-hash dedup with configurable tracking-param stripping; content hash stored per job for cross-source matching |
| **Job Feed** | Filters, sorting, keyboard shortcuts (j/k/s/x/e), scoring reports, bulk operations, in-app job preview |
| **Application Board** | Kanban pipeline with drag-and-drop, status transition history |
| **Chrome Extension** | Passive LinkedIn capture + save any job from any page |
| **Gmail Monitor** | OAuth2 polling, auto-classifies responses, updates application status |
| **Telegram Alerts** | New job alerts, daily digest, scrape health, inline action buttons |
| **H-1B Data** | Company LCA lookups from MyVisaJobs, JD exclusion scanning |
| **Scheduling** | Cron-based: scraping, email checks, backups, cleanup, auto-reject |
| **Realtime 2027 Job Feed Packets** | Checks selected GitHub aggregate lists every 5 minutes, filters US SWE/AI/Data roles, and builds one mapped Persona resume packet per job |
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

1. `chrome://extensions/` → Developer mode → Load unpacked → select `extension/`
2. Toggle LinkedIn capture on, browse job collections
3. Click "Send to JobNavigator" to import

## Optional Integrations

**Telegram** — Create bot via @BotFather, set token in `.env`, enter chat ID in Settings.

**Gmail** — Run `python backend/gmail_oauth_setup.py`, set OAuth credentials in `.env`.

## Realtime 2027 Job Feed Packets

JobNavigator can continuously watch these public aggregate lists:

- [speedyapply/2027-SWE-College-Jobs](https://github.com/speedyapply/2027-SWE-College-Jobs): USA internships and new-grad roles.
- [vanshb03/Summer2027-Internships](https://github.com/vanshb03/Summer2027-Internships): internships.
- [vanshb03/New-Grad-2027](https://github.com/vanshb03/New-Grad-2027): new-grad roles.

The default workflow checks repository commit feeds every 5 minutes, downloads a list only after that repository changes, backfills the first 7 days, and prioritizes newly published jobs over the backlog. It keeps US SWE, AI/ML, and Data roles, rejects explicit citizenship/clearance/no-sponsorship restrictions, and flags ambiguous work-authorization language for review. Provider job IDs and canonical application URLs deduplicate the same posting across repositories.

For every eligible job, the one-minute packet worker fetches the employer JD and creates a fact-constrained, one-page resume from **Persona**. Feed tailoring deliberately disables ATS scoring and speculative bullets: the model may select and reword existing evidence, but packet validation sends unsupported facts, new numeric claims, newly invented skills, or multi-page output to `needs_review`.

### Setup

1. Populate **Persona**, including contact email and the complete resume evidence pool.
2. Configure a working LLM under **Settings > AI**.
3. Re-authorize Gmail so the refresh token includes the new `gmail.send` scope:

   ```bash
   python backend/gmail_oauth_setup.py
   ```

   Copy the refreshed credentials into `.env`, then restart the backend. Without Gmail authorization, jobs and packets continue processing and unsent notifications remain pending for retry.
4. Start the always-on services:

   ```bash
   docker compose up -d --build
   ```

5. Open **Settings > General > Realtime 2027 Job Feeds**. Confirm the sources, role families, notification email, 5-minute poll interval, 1-minute worker interval, and **Automatically tailor resumes**. Use **Run now** for a forced first poll.

The monitor sends one Gmail alert when a candidate job is detected and another when its packet is `ready`, `needs_review`, `ineligible`, or permanently `failed` after three attempts. Emails contain the direct application URL and local packet path; PDFs are not attached.

### Packet mapping and health

Generated files persist on the host under:

```text
application-packets/
  index.csv
  YYYY-MM-DD/<stable-id>_<company>_<role>/
    resume.pdf
    resume.json
    job.md
    metadata.json
```

`application-packets/index.csv` is rebuilt atomically and maps the queue item, canonical Job, tailored Resume, direct application URL, source feeds, and packet directory. The directory is mounted by Docker Compose and ignored by Git.

Operational endpoints:

- `GET /api/job-feeds/status` — source checkpoints, upstream commit state, errors, and queue counts.
- `POST /api/job-feeds/run` — force an immediate poll; this does not submit an application.

Detection latency is bounded by the aggregate repository's own update delay plus the configured polling interval. The backend container must remain running. Authentication, employer questions, attestations, CAPTCHAs, and the final Submit action remain manual.

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

## Security

Found a vulnerability? See [SECURITY.md](SECURITY.md). Please don't open public issues for security bugs.

## Privacy

**JobNavigator is self-hosted — NOT a hosted service.** Your resume, job data, and credentials stay on your machine. Data is sent only to the AI provider you configure. We do not collect, store, or have access to any of your data.

## Disclaimer

Personal and educational use only. Not affiliated with LinkedIn, Indeed, Jobright.ai, or any job platform. Some scraping features are disabled by default and require explicit opt-in. You are responsible for complying with the Terms of Service of any platform you interact with. See [LEGAL_DISCLAIMER.md](LEGAL_DISCLAIMER.md).

## License

[MIT](LICENSE)
