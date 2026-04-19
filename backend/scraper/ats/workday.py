"""Workday ATS handler — JSON API via POST /wday/cxs/{company}/{site}/jobs.

Detection: hostname-based match on myworkdayjobs.com.
Public interface: is_workday(url), scrape(url, debug=False).
"""
import json
import logging
import re
from urllib.parse import urlparse, parse_qs

import httpx

from backend.scraper._shared.urls import host_matches
from backend.scraper._shared.filters import _validate_job

logger = logging.getLogger("jobnavigator.scraper.ats.workday")

_LOCALE_PATH_RE = re.compile(r'^[a-z]{2}(-[A-Z]{2})?$')  # en-US, en, de-DE, etc.


def is_workday(url: str) -> bool:
    """Check if URL is a Workday career site (myworkdayjobs.com)."""
    return host_matches(url, "myworkdayjobs.com")


def _parse_workday_url(url: str) -> tuple[str, str, str, dict]:
    """Parse Workday URL into (origin, company_slug, site, applied_facets).

    URL formats:
      https://{company}.wd{N}.myworkdayjobs.com/{site}/?params
      https://{company}.wd{N}.myworkdayjobs.com/en-US/{site}/?params
    API endpoint: https://{host}/wday/cxs/{company}/{site}/jobs
    """
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"

    # Company slug = subdomain before .wdN
    host_parts = parsed.netloc.split(".")
    company_slug = host_parts[0] if host_parts else ""

    # Site = first non-locale path segment (skip en-US, de-DE, etc.)
    path_parts = [p for p in parsed.path.strip("/").split("/") if p]
    site = ""
    for part in path_parts:
        if _LOCALE_PATH_RE.match(part):
            continue
        site = part
        break

    # Convert query params to Workday appliedFacets format
    qs = parse_qs(parsed.query)
    applied_facets = {}
    skip_params = {"source", "utm_source", "utm_medium", "utm_campaign", "utm_content"}
    for key, values in qs.items():
        if key.lower() in skip_params:
            continue
        applied_facets[key] = values

    return origin, company_slug, site, applied_facets


async def scrape(url: str, debug: bool = False) -> list[dict] | tuple:
    """Fetch jobs from Workday's internal JSON API."""
    origin, company_slug, site, applied_facets = _parse_workday_url(url)

    if not company_slug or not site:
        logger.warning(f"Workday: could not parse company/site from {url}")
        if debug:
            return [], [{"title": "(none)", "url": url, "selector": "workday_api", "reason": "Bad URL format"}]
        return []

    api_url = f"{origin}/wday/cxs/{company_slug}/{site}/jobs"
    logger.info(f"Workday API: {api_url} facets={list(applied_facets.keys())}")

    jobs = []
    rejected = []
    offset = 0
    total = None  # Capture from first page only (Workday returns 0 on later pages)
    limit = 20  # Workday API max per request

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        while True:
            payload = {
                "appliedFacets": applied_facets,
                "limit": limit,
                "offset": offset,
                "searchText": "",
            }

            resp = await client.post(api_url, json=payload, headers=headers)
            if resp.status_code != 200:
                logger.warning(f"Workday API returned {resp.status_code} for {company_slug}/{site}")
                if debug:
                    rejected.append({"title": "(none)", "url": api_url, "selector": "workday_api", "reason": f"HTTP {resp.status_code}"})
                break

            data = json.loads(resp.text)
            if total is None:
                total = data.get("total", 0)
            postings = data.get("jobPostings", [])

            if offset == 0:
                logger.info(f"Workday API: total={total}")

            if not postings:
                break

            for p in postings:
                title = (p.get("title") or "").strip()
                ext_path = p.get("externalPath") or ""
                job_url = f"{origin}/en-US/{site}{ext_path}" if ext_path else ""

                reason = _validate_job(title, job_url)
                if reason is None:
                    jobs.append({"title": title, "url": job_url})
                elif debug:
                    rejected.append({"title": title, "url": job_url, "selector": "workday_api", "reason": reason})

            offset += len(postings)
            if offset >= total:
                break

    logger.info(f"Workday API: fetched {len(jobs)} jobs for {company_slug}/{site}")
    if debug:
        return jobs, rejected
    return jobs
