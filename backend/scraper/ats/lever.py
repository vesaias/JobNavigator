"""Lever ATS handler — GET api.lever.co/v0/postings/{company}.

Detection: substring match on `jobs.lever.co/` (the board host + trailing slash
prevents matching attacker-controlled paths like `https://evil.com/?u=lever.co`).
Public interface: is_lever(url), scrape(url, debug=False).

The public Lever API returns all postings for the given company slug. Supported
filters (department, team, location, commitment) are forwarded from the original
URL's query string.
"""
import json
import logging
from urllib.parse import parse_qs, urlparse

import httpx

from backend.scraper._shared.filters import _validate_job

logger = logging.getLogger("jobnavigator.scraper.ats.lever")


def is_lever(url: str) -> bool:
    """Check if URL is a Lever job board (jobs.lever.co/<company>)."""
    return "jobs.lever.co/" in url.lower()


async def scrape(url: str, debug: bool = False) -> list[dict] | tuple:
    """Fetch jobs from Lever's public JSON API.

    Forwards supported filters from the original URL query string:
    department, team, location, commitment.
    """
    parsed = urlparse(url)
    # Extract company slug from path: /plaid or /plaid/
    path_parts = [p for p in parsed.path.strip("/").split("/") if p]
    if not path_parts:
        if debug:
            return [], [{"title": "(none)", "url": url, "selector": "lever_api", "reason": "No company slug in URL"}]
        return []
    company_slug = path_parts[0]

    # Build API URL, forwarding supported Lever filters
    api_url = f"https://api.lever.co/v0/postings/{company_slug}?mode=json"
    qs = parse_qs(parsed.query)
    for param in ("department", "team", "location", "commitment"):
        if param in qs:
            api_url += f"&{param}={qs[param][0]}"

    jobs = []
    rejected = []

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(api_url)
        if resp.status_code != 200:
            logger.warning(f"Lever API returned {resp.status_code} for {company_slug}")
            if debug:
                return [], [{"title": "(none)", "url": api_url, "selector": "lever_api", "reason": f"HTTP {resp.status_code}"}]
            return []

        postings = json.loads(resp.text)
        for p in postings:
            title = (p.get("text") or "").strip()
            job_url = p.get("hostedUrl") or ""
            reason = _validate_job(title, job_url)
            if reason is None:
                jobs.append({"title": title, "url": job_url})
            elif debug:
                rejected.append({"title": title, "url": job_url, "selector": "lever_api", "reason": reason})

    logger.info(f"Lever API: fetched {len(jobs)} jobs for {company_slug}")
    if debug:
        return jobs, rejected
    return jobs
