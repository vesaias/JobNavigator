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

1. Find the ATS endpoint. Most have a JSON API — check Network tab on their career page.
2. Add a detector function in `backend/scraper/playwright_scraper.py` (search for `_is_workday`, `_is_ashby`, etc. for examples):
   ```python
   def _is_yourats(url: str) -> bool:
       return "yourats.com" in url.lower()
   ```
3. Add a scraper function that returns jobs as dicts with at minimum `{title, company, url, location, description}`.
4. Wire it into `_scrape_url` (search for `_is_workday` to find the dispatch).
5. Test by adding a company in the dashboard with a URL and clicking "Test scrape".

Existing handlers to crib from (in `playwright_scraper.py`): Workday, Greenhouse, Lever, Ashby, Oracle HCM, Phenom, TalentBrew, Rippling, Meta Careers, Google Careers, Apple.

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
