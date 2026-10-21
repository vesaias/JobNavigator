# JobNavigator

<h3 align="center"><a href="https://vesaias.github.io/JobNavigator-demo/">JobNavigator Demo</a></h3>

**Self-hosted, multi-account job-hunt automation.**

Scrape career pages and aggregators, score jobs against your résumés with an LLM, tailor résumés and cover letters, auto-fill applications from your persona, get Telegram alerts, track every application. One install serves one person or a household: up to five accounts, each with its own jobs, résumés, settings and optional PIN, sharing one scrape.

**Updating from 2.x**

Follow steps here manually or ask AI to: [Upgrading from 2.x](CHANGELOG.md#upgrading-from-2x)

<p align="center">
  <img src="docs/demo.gif" alt="JobNavigator — feed, scoring, tailoring, applications" width="100%">
</p>

<p align="center">
  <a href="docs/board.png"><img src="docs/board.png" alt="Green Paper theme" width="24%"></a>
  <a href="docs/slate.png"><img src="docs/slate.png" alt="Stone theme" width="24%"></a>
  <a href="docs/v1like.png"><img src="docs/v1like.png" alt="V1 Style theme" width="24%"></a>
  <a href="docs/win98.png"><img src="docs/win98.png" alt="Windows 98 theme" width="24%"></a>
  <br>
  <sub>Five themes, each in light and dark: Paper (above), Green Paper, Stone, V1 Style, Windows 98.</sub>
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
│   12 ATS endpoints:     │                         │                         │
│   Workday, Greenhouse   │  LinkedIn Personal      │  Auto-fill based on     │
│   Lever, Ashby,         │  collections            │  your persona input     │
│   Oracle, Phenom,       │  Apify (paid boards)    │  and question bank      │
│   TalentBrew, Rippling  │  Jobright.ai            │                         │
│   SmartRecruiters,      │  Levels.fyi             │  Save any job from      │
│   Amazon, Meta, Google  │  freehire.me            │  any page               │
│                         │  CaribbeanJobs.com      │                         │
│                         │  TrulyRemoteWork.com    │                         │
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
│   Providers ── Claude API/CLI, Codex CLI, Antigravity CLI, OpenCode Go,     │
│                OpenAI, OpenRouter, Ollama, LM Studio                        │
│   Depths ───── Light (scores only) or Full (report + keyword analysis)      │
│   Multi ────── Score against multiple resumes, compare fit per role         │
│                                                                             │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           RESUME + COVER LETTER                             │
│                                                                             │
│   Templates ── 8 resume + 7 cover-letter, auto-discovered (add your own!)   │
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
│   Autofill ─── ATS forms + AI answers to free-text questions (Persona)      │
│   Apps ─────── Stages, interviews, notes, prep handover, funnel and Sankey  │
│   Tracer ───── Unique links per resume/letter, tracks who opened them       │
│   Gmail ────── Auto-detects responses, updates application status           │
│   Telegram ─── Job alerts, daily digest, scrape health notifications        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Features

| Feature | Description |
|---------|-------------|
| **Discovery** | Career pages (Playwright + 12 ATS handlers), JobSpy (LinkedIn, Indeed, ZipRecruiter, Google), Apify (Indeed, LinkedIn, Glassdoor, Greenhouse/Lever/Ashby/Workday search; not on the Apify Creator plan), LinkedIn collections, Levels.fyi, Jobright.ai, freehire.me, CaribbeanJobs.com, TrulyRemoteWork.com, the Chrome extension |
| **Scoring** | Claude, OpenAI, OpenRouter, Ollama, LM Studio, Claude Code, Codex CLI, Antigravity CLI or OpenCode Go; live model search, a model per feature; Light (score) or Full (report, keyword coverage, requirement mapping) against every base résumé; prompt caching on Anthropic |
| **Résumés** | Structured base résumés, tailoring per job with a review step, 8 PDF templates (drop in your own) and a Word (.docx) export, an opt-in page footer (name, job title, company) on tailored copies, tracked links that record opens |
| **Cover letters** | Generated from the paired résumé and persona; voice and length presets, 7 templates, PDF |
| **Dedup** | URL identity hash (tracking params stripped) plus company + title hash across sources |
| **Jobs** | Filters, sorting, keyboard shortcuts (`?`), full report, collapsible analysis pane, bulk actions with undo, posting preview |
| **Applications** | Stages, interviews, notes, status history (funnel and Sankey in Stats), a prep handover for any AI chat |
| **Persona** | Contact, work authorization, compensation, preferences, résumé content, Q&A bank; import from a résumé or PDF |
| **Extension** | Passive LinkedIn capture, save any job from any page, ATS form autofill and AI answers to free-text questions from your Persona |
| **Accounts** | Owner + up to four members, each with their own jobs, applications, résumés, letters, Persona, searches and companies; optional 4-digit PINs; settings inherited or own per section; scraping shared (one fetch per page, filtered and scored per account); with one account none of it shows |
| **Gmail** | Polls replies, classifies them, updates the application; each account connects its own mailbox |
| **Telegram** | New-job alerts, daily digest, scrape health, inline actions; per account (household bot or its own) |
| **H-1B** | Company filing lookups, description exclusion phrases |
| **Scheduling** | Intervals and crons for scraping, email, backups, cleanup, auto-reject; every cron field explains itself and offers presets |
| **Themes** | Paper, Green Paper, Stone, V1 Style, Windows 98 × light / dark / system |

> The posting preview is an `iframe`; sites that refuse framing show blank unless the extension (which strips the frame-blocking headers) is installed. "Open" always works, and applied jobs keep a cached snapshot.

## Quick Start

**1. Run it**

```bash
git clone https://github.com/vesaias/JobNavigator.git
cd JobNavigator
cp .env.example .env
docker compose pull && docker compose up -d      # prebuilt images from GHCR
```

Open `http://localhost`. To build from source instead, use `docker compose up --build -d`; every release is also published for `linux/amd64` and `linux/arm64` as `ghcr.io/vesaias/jobnavigator-backend` and `-frontend`, pinnable with `JN_IMAGE_TAG=3.0` in `.env`. On first run sign in with a blank key, then set one in Settings › System › Advanced.

**2. Connect a model**

Any API key goes straight into Settings › AI. A subscription needs one login inside the container first (OpenCode Go needs none):

| Subscription | Once after the containers start |
|---|---|
| Claude Pro / Max | `docker compose exec backend claude setup-token`, put the printed token in `.env` as `CLAUDE_CODE_OAUTH_TOKEN`, then `docker compose up -d backend` |
| ChatGPT | `docker compose exec backend codex login --device-auth` (check with `codex login status`; the login lives in the `codex_auth` volume) |
| Google Antigravity | `docker compose exec -it backend agy` — the container has no browser, so the CLI prints a URL and asks for the code it shows (the login lives in the `antigravity_auth` volume) |
| OpenCode Go | nothing: paste the Go API key under Settings › AI |

No pay-per-token key needed for any of them. A plan limit fails over to the fallback provider without retrying. With several accounts, `docker compose exec backend python -m backend.scripts.cli_login <codex|agy|claude> "<account>"` prints a member's own login command.

**3. First steps**

1. Settings › AI — provider and model
2. Résumés — create a base résumé or import a PDF
3. Persona — import from that résumé, fill the Q&A bank
4. Companies and Searches — add a few, run them

The full walkthrough, screen by screen, is in [docs/GETTING-STARTED.md](docs/GETTING-STARTED.md).

## Chrome Extension ("The Navigator")

- Unblocks the posting preview: frame-blocking headers are lifted only for frames the dashboard itself opens (scoped to your JobNavigator host); every other page keeps its own headers.
- Captures job ids while you browse `linkedin.com/jobs/collections/*` and imports them with full details.
- Fills ATS forms and drafts answers to free-text questions from your Persona and Q&A bank (toggle in the popup; model and prompt in Settings › AI).

- With two or more accounts, **Saves to** in the popup picks the account that captures and autofill use.

Install: `chrome://extensions` › Developer mode › Load unpacked › `extension/`. The LinkedIn import signs in through Settings › Integrations › LinkedIn (a separate mock account is recommended).

## Optional Integrations

| | Server (`.env`) | Per account (Settings) |
|---|---|---|
| **Telegram** | `TELEGRAM_BOT_TOKEN` (the household bot) | Notifications › Link Telegram, or its own bot |
| **Gmail** | `GMAIL_CLIENT_ID` / `GMAIL_CLIENT_SECRET`; add `<dashboard>/api/gmail/callback` as a redirect URI | Email classification › Gmail › Connect Gmail |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI, SQLAlchemy, APScheduler, Playwright |
| Frontend | React 18, Vite, Recharts, a token-based design system ([DESIGN-SYSTEM.md](frontend/src/DESIGN-SYSTEM.md)) |
| Database | PostgreSQL 16 |
| Infrastructure | Docker Compose, Caddy, nginx |
| AI | Anthropic SDK, OpenAI SDK, Ollama, LM Studio, Claude Code CLI, Codex CLI, Antigravity CLI, OpenCode Go endpoint |
| Extension | Chrome Manifest V3 |

## Backups

Scheduled `pg_dump`s land in `backups/` (five kept). They contain the settings table, API keys included: treat them like `.env`. The folder is git-ignored.

## Disclaimer

Self-hosted. Your résumés, jobs and credentials stay on your machine; the only outside party is the AI provider you configure.

Personal use. Not affiliated with any job platform; some scrapers are off by default and you are responsible for the terms of the sites you use. See [LEGAL_DISCLAIMER.md](LEGAL_DISCLAIMER.md).

## License

[MIT](LICENSE)
