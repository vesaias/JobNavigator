"""SmartRecruiters ATS handler — GET api.smartrecruiters.com/v1/companies/{slug}/postings, paginated via limit/offset (max 100).
Only single-value country/city/q filters are forwarded from the input URL; multi-value forms return 0 from the API, so multiple countries need separate scrape_urls."""
import json
import logging
from urllib.parse import parse_qs, urlparse

import httpx

from backend.scraper._shared.filters import _validate_job
from backend.scraper._shared.urls import host_matches

logger = logging.getLogger("jobnavigator.scraper.ats.smartrecruiters")

_PAGE_LIMIT = 100
_MAX_PAGES = 50  # 5000 postings cap — defensive against runaway pagination

# Query params forwarded to the API; others are dropped to avoid per-tenant customField params the API might reject.
_FORWARDABLE_PARAMS = ("country", "city", "q")


def is_smartrecruiters(url: str) -> bool:
    """Check if URL is a SmartRecruiters job board (strict hostname match, not substring, to resist spoofed paths)."""
    return host_matches(
        url,
        "jobs.smartrecruiters.com",
        "careers.smartrecruiters.com",
        "api.smartrecruiters.com",
    )


def _extract_company_slug(url: str) -> str | None:
    """First non-empty path segment is the company slug, handling all three host shapes (jobs/careers/api)."""
    parsed = urlparse(url)
    parts = [p for p in parsed.path.strip("/").split("/") if p]
    if not parts:
        return None
    if (parsed.hostname or "").lower() == "api.smartrecruiters.com":
        for i, p in enumerate(parts):
            if p == "companies" and i + 1 < len(parts):
                return parts[i + 1]
        return None
    return parts[0]


async def scrape(url: str, debug: bool = False) -> list[dict] | tuple:
    """Fetch jobs from SmartRecruiters' public JSON API, paginating until exhausted."""
    company_slug = _extract_company_slug(url)
    if not company_slug:
        if debug:
            return [], [{"title": "(none)", "url": url, "selector": "smartrecruiters_api",
                         "reason": "No company slug in URL"}]
        return []

    api_base = f"https://api.smartrecruiters.com/v1/companies/{company_slug}/postings"

    # parse_qs returns {key: [values]}; we take the first since the API rejects
    # multi-value filters (see module docstring) — two countries need two scrape_urls.
    qs = parse_qs(urlparse(url).query)
    filter_suffix = ""
    forwarded_filters = {}
    for key in _FORWARDABLE_PARAMS:
        vals = qs.get(key) or []
        if vals and vals[0]:
            filter_suffix += f"&{key}={vals[0]}"
            forwarded_filters[key] = vals[0]

    logger.info(f"SmartRecruiters API: {api_base} filters={forwarded_filters or 'none'}")

    jobs: list[dict] = []
    rejected: list[dict] = []

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        offset = 0
        for page_idx in range(_MAX_PAGES):
            page_url = f"{api_base}?limit={_PAGE_LIMIT}&offset={offset}{filter_suffix}"
            resp = await client.get(page_url)
            if resp.status_code != 200:
                logger.warning(
                    f"SmartRecruiters API returned {resp.status_code} for {company_slug} "
                    f"(offset={offset})"
                )
                # Always surface the failure in debug mode — even mid-pagination, so
                # callers can tell a partial-success result was actually truncated.
                if debug:
                    rejected.append({"title": "(none)", "url": page_url,
                                     "selector": "smartrecruiters_api",
                                     "reason": f"HTTP {resp.status_code} at offset={offset}"})
                break

            try:
                data = json.loads(resp.text)
            except (ValueError, json.JSONDecodeError) as e:
                logger.warning(f"SmartRecruiters API: invalid JSON for {company_slug}: {e}")
                if debug:
                    rejected.append({"title": "(none)", "url": page_url,
                                     "selector": "smartrecruiters_api",
                                     "reason": f"Invalid JSON at offset={offset}: {e}"})
                break

            content = data.get("content") or []
            if not content:
                break

            for posting in content:
                title = (posting.get("name") or "").strip()
                job_id = posting.get("id") or ""
                if not job_id:
                    if debug:
                        rejected.append({"title": title, "url": "",
                                         "selector": "smartrecruiters_api",
                                         "reason": "Missing posting id"})
                    continue
                # Bare-ID URL redirects to canonical "{id}-{slugified-name}" form;
                # used directly so we don't have to slugify and risk drift.
                job_url = f"https://jobs.smartrecruiters.com/{company_slug}/{job_id}"
                reason = _validate_job(title, job_url)
                if reason is None:
                    jobs.append({"title": title, "url": job_url})
                elif debug:
                    rejected.append({"title": title, "url": job_url,
                                     "selector": "smartrecruiters_api",
                                     "reason": reason})

            total = data.get("totalFound")
            offset += _PAGE_LIMIT
            # Stop when we've definitely seen everything: short page OR offset past total.
            if len(content) < _PAGE_LIMIT:
                break
            if isinstance(total, int) and offset >= total:
                break
        else:
            logger.warning(
                f"SmartRecruiters API: hit _MAX_PAGES ({_MAX_PAGES}) for {company_slug}"
            )

    logger.info(f"SmartRecruiters API: fetched {len(jobs)} jobs for {company_slug}")
    if debug:
        return jobs, rejected
    return jobs
