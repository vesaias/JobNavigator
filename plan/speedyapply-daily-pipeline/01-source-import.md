# Subproblem 1: Import recent SpeedyApply jobs

## 1. Goal
Read configured Markdown lists from the public SpeedyApply repository, parse job rows safely, keep only recent rows, fetch their job descriptions, and store deduplicated `Job` rows.

## 2. Why this step exists
The existing scrapers understand ATS sites and aggregators, but no current source understands SpeedyApply's generated Markdown tables or their posting-age column.

## 3. Files involved
- `backend/scraper/sources/speedyapply.py` - new parser, feed fetcher, age filter, description enrichment, and database importer.
- `backend/scraper/sources/__init__.py` - source package marker; read for package conventions and update only if an export is useful.
- `backend/scraper/ats/_descriptions.py` - reuse the existing SSRF-protected ATS description fetcher without changing its public behavior.
- `backend/scraper/_shared/dedup.py` - reuse URL normalization and hashes.
- `backend/models/db.py` - use the existing `Job` model and queue model introduced in the next subproblem.

## 4. Exact changes
- Add a fixed allowlist mapping feed IDs (`intern_usa`, `new_grad_usa`, `intern_intl`, `new_grad_intl`) to raw GitHub Markdown URLs.
- Add a pure `parse_markdown_jobs` function that detects table headers by column name and extracts company, position, location, optional salary, apply URL, posting age, and feed ID.
- Ignore malformed rows, rows without a public HTTP(S) application URL, and rows older than the configured maximum age.
- Fetch the configured feed files with timeouts and clear per-feed errors.
- Deduplicate with `make_external_id`; if the same job already exists from another source, reuse that `Job` instead of creating a duplicate.
- Fetch descriptions with the existing ATS-aware helper, populate salary/remote fields, and return the imported/reused job IDs for queue preparation.
- Cap candidates per run using a setting so a first run cannot generate hundreds of LLM calls.

## 5. Out of scope
- Do not scrape GitHub's rendered HTML.
- Do not submit applications.
- Do not bypass authentication, CAPTCHA, or anti-bot controls on employer sites.

## 6. Done condition
Given representative SpeedyApply Markdown, the parser returns correct jobs from both salary and non-salary table variants. A sync stores only allowed recent jobs and reuses existing rows on later runs.

## 7. Verification
- Run `python -m pytest backend/tests/test_speedyapply_source.py -q`.
- Confirm tests cover USA/international column variants, age filtering, malformed rows, and deduplication.

## 8. Expected output
A new SpeedyApply source module that produces description-enriched, deduplicated `Job` records and a deterministic list of jobs to prepare.

## 9. Notes for the next step
The application agent can assume every returned job has a stable database ID and may or may not have a fetched description.

## 10. Risks or ambiguity
The upstream repository can change its Markdown layout. Header-driven parsing and focused fixtures reduce this risk. Employer pages can refuse automated reads; those failures must remain visible and retryable instead of fabricating a JD.
