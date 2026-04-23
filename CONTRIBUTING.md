# Contributing

Thanks for thinking about contributing! This is a personal project but I welcome any help. No formal process — just open a PR and we'll sort it out.

## Getting started

```bash
git clone https://github.com/vesaias/JobNavigator.git
cd JobNavigator
cp .env.example .env
# Add your Anthropic/OpenAI API key or leave blank
docker compose up --build -d
```

Open http://localhost — sign in with a blank key on first run.

**Backend** auto-reloads (volume mount). **Frontend** does not — re-run `docker compose up frontend -d --build --no-deps` after changes.

## Easy things to contribute

### Add a new ATS scraper

If your favorite company uses an ATS not yet supported, adding it is usually a few hours of work.

Scrapers live under `backend/scraper/` in three layers:

- `ats/` — one file per ATS platform (`lever.py`, `greenhouse.py`, `workday.py`, `ashby.py`, `oracle_hcm.py`, `phenom.py`, `talentbrew.py`, `rippling.py`, `meta.py`, `google.py`, `generic.py`). Each exposes `is_<ats>(url)` and `async def scrape(url, ...)`.
- `sources/` — higher-level sources that fan out across multiple ATSes (`company_pages.py`, `jobspy.py`, `jobright.py`).
- `_shared/` — cross-ATS utilities: `url_safety.py` (SSRF gate), `dedup.py`, `urls.py`, `browser.py`, `filters.py`.
- `orchestrator.py` — `run_all()` entry point used by the scheduler and manual triggers.

Steps:

1. Find the ATS endpoint. Most have a JSON API — check Network tab on their career page. If it's a pure-HTTP ATS, you don't need Playwright.
2. Create `backend/scraper/ats/yourats.py` modeled on `lever.py` or `greenhouse.py`. Two public symbols:
   ```python
   def is_yourats(url: str) -> bool:
       return "yourats.com" in url.lower()

   async def scrape(url: str, debug: bool = False) -> list[dict]:
       # Return jobs as dicts with at minimum: {title, company, url, location, description}
       ...
   ```
3. Wire it into `backend/scraper/sources/company_pages.py` — add an `is_yourats` / `yourats.scrape` branch inside `_dispatch_ats` and, if it needs a browser, add the detector to `_needs_browser`.
4. If your ATS has a dedicated job-description endpoint (vs. scraping the posting page), add a handler in `backend/scraper/ats/_descriptions.py` for SSRF-safe, ATS-specific fetching.
5. Test by adding a company in the dashboard with a URL and clicking "Test scrape".

Examples to crib from: `lever.py` + `greenhouse.py` (pure HTTP), `workday.py` (JSON POST), `rippling.py` (flat JSON + client-side filter), `meta.py` / `google.py` (Playwright DOM).

### Add a resume template

Just drop a folder in `backend/resume_templates/`:

```
backend/resume_templates/yourname/
├── template.html.j2   # Jinja2, required
├── meta.json          # { "name": "Display Name", "description": "..." }
└── fonts/             # optional: .TTF files get auto-embedded as data URIs
```

Templates are auto-discovered at startup. Copy any existing template (e.g. `inter/`) as a starting point. Available Jinja variables: `header`, `summary`, `experience`, `skills`, `education`, `projects`, `publications`, `fonts`, `page_format`.

### Other good contributions

- Fix a bug you hit
- Add a new LLM provider to `backend/analyzer/llm_client.py`
- Improve a scraper that broke
- UI/UX polish
- Documentation
- Translations

## How to contribute

1. Fork the repo
2. Make your change
3. Open a PR — include a short description and a screenshot if it's a UI change

That's it. Don't worry about perfect code — I'll review and we can iterate.

## Stack reminder

- Backend: Python 3.12 / FastAPI / SQLAlchemy / PostgreSQL / Playwright
- Frontend: React 18 / Tailwind / Vite
- Extension: Chrome MV3, vanilla JS
- Docker Compose for everything

## Questions

Open an issue or discussion — happy to help.
