"""Greenhouse ATS handler — GET boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true.

Detection: hostname-based match on greenhouse.io (covers boards.greenhouse.io,
job-boards.greenhouse.io, boards-api.greenhouse.io, etc.).
Public interface: is_greenhouse(url), scrape(url, debug=False).

The API ignores department[]/offices[] query params, so filtering is done client-side.
Department and office IDs in the URL may be parents — children are expanded by
scanning parent_id across all postings. Office dedup uses location.name to avoid
multi-location duplicate postings.
"""
import json
import logging
from urllib.parse import urlparse, parse_qs

import httpx

from backend.scraper._shared.urls import host_matches
from backend.scraper._shared.filters import _validate_job

logger = logging.getLogger("jobnavigator.scraper.ats.greenhouse")


def is_greenhouse(url: str) -> bool:
    """Check if URL is a Greenhouse job board."""
    return host_matches(url, "greenhouse.io", "boards.greenhouse.io")


def _parse_greenhouse_url(url: str) -> tuple[str, set[int], set[int]]:
    """Parse Greenhouse URL into (company_slug, department_ids, office_ids).

    URL format: https://job-boards.greenhouse.io/{company}/?departments[]=ID&offices[]=ID
    or: https://boards.greenhouse.io/{company}/?...
    """
    parsed = urlparse(url)
    path_parts = [p for p in parsed.path.strip("/").split("/") if p]
    company_slug = path_parts[0] if path_parts else ""

    qs = parse_qs(parsed.query)
    dept_ids = set()
    office_ids = set()
    for key in ("departments[]", "departments%5B%5D"):
        for v in qs.get(key, []):
            try:
                dept_ids.add(int(v))
            except ValueError:
                pass
    for key in ("offices[]", "offices%5B%5D"):
        for v in qs.get(key, []):
            try:
                office_ids.add(int(v))
            except ValueError:
                pass

    return company_slug, dept_ids, office_ids


async def scrape(url: str, debug: bool = False) -> list[dict] | tuple:
    """Fetch jobs from Greenhouse's public JSON API.

    The API ignores department/office query params, so we filter client-side.
    Department IDs in the URL may be parents — we expand to include children.
    Office filtering uses location.name to avoid multi-office duplicates.
    """
    company_slug, filter_dept_ids, filter_office_ids = _parse_greenhouse_url(url)

    if not company_slug:
        if debug:
            return [], [{"title": "(none)", "url": url, "selector": "greenhouse_api", "reason": "No company slug"}]
        return []

    api_url = f"https://boards-api.greenhouse.io/v1/boards/{company_slug}/jobs?content=true"
    logger.info(f"Greenhouse API: {api_url} depts={filter_dept_ids} offices={filter_office_ids}")

    jobs = []
    rejected = []

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(api_url)
        if resp.status_code != 200:
            logger.warning(f"Greenhouse API returned {resp.status_code} for {company_slug}")
            if debug:
                return [], [{"title": "(none)", "url": api_url, "selector": "greenhouse_api", "reason": f"HTTP {resp.status_code}"}]
            return []

        data = json.loads(resp.text)
        all_postings = data.get("jobs", [])
        logger.info(f"Greenhouse API: {len(all_postings)} total postings for {company_slug}")

        # Expand parent department IDs to include their children
        match_dept_ids = set()
        if filter_dept_ids:
            for posting in all_postings:
                for d in posting.get("departments", []):
                    did = d.get("id")
                    pid = d.get("parent_id")
                    if did in filter_dept_ids or pid in filter_dept_ids:
                        match_dept_ids.add(did)
            logger.info(f"Greenhouse: expanded dept filter {filter_dept_ids} -> {match_dept_ids}")
            if not match_dept_ids:
                logger.warning(f"Greenhouse: department IDs {filter_dept_ids} not found in API data — URL may use stale IDs. Visit the board page, re-select filters, and copy the new URL.")

        # Expand parent office IDs to include children (same pattern as departments).
        # Also collect matched office names for location.name dedup filtering.
        match_office_ids = set()
        match_office_names = set()
        if filter_office_ids:
            for posting in all_postings:
                for o in posting.get("offices", []):
                    oid = o.get("id")
                    pid = o.get("parent_id")
                    if oid in filter_office_ids or pid in filter_office_ids:
                        match_office_ids.add(oid)
                        name = o.get("name", "")
                        if name:
                            match_office_names.add(name)
            logger.info(f"Greenhouse: expanded office filter {filter_office_ids} -> {match_office_ids} names={match_office_names}")
            if not match_office_ids:
                logger.warning(f"Greenhouse: office IDs {filter_office_ids} not found in API data — URL may use stale IDs. Visit the board page, re-select filters, and copy the new URL.")

        # Build set of ALL known office names across every posting — used to detect
        # when a location.name is itself an office (like "Remote Canada") vs. a city
        # under a matching parent office (like "New York, NY" under "United States").
        all_known_office_names = set()
        for posting in all_postings:
            for o in posting.get("offices", []):
                name = o.get("name", "")
                if name:
                    all_known_office_names.add(name)

        for posting in all_postings:
            title = (posting.get("title") or "").strip()
            job_url = posting.get("absolute_url") or ""

            # Department filter
            if match_dept_ids:
                job_dept_ids = {d.get("id") for d in posting.get("departments", [])}
                if not job_dept_ids.intersection(match_dept_ids):
                    if debug:
                        rejected.append({"title": title, "url": job_url, "selector": "greenhouse_api", "reason": "Department not in filter"})
                    continue

            # Office filter — Greenhouse creates separate postings per location but
            # may assign the same office IDs to all of them. Use location.name as
            # primary match against expanded office names; fall back to office ID
            # intersection only for jobs where location.name is a child (e.g.
            # "New York, NY" under parent office "United States").
            if match_office_ids:
                loc_name = posting.get("location", {}).get("name", "")
                if loc_name in match_office_names:
                    pass  # Direct match — keep
                else:
                    job_office_ids = {o.get("id") for o in posting.get("offices", [])}
                    if not job_office_ids.intersection(match_office_ids):
                        if debug:
                            rejected.append({"title": title, "url": job_url, "selector": "greenhouse_api", "reason": f"Office not in filter"})
                        continue
                    # Office matches but location.name doesn't — only keep if
                    # location.name isn't a known office name (meaning it's a
                    # city under a matching parent like "United States")
                    if loc_name in all_known_office_names:
                        if debug:
                            rejected.append({"title": title, "url": job_url, "selector": "greenhouse_api", "reason": f"Location '{loc_name}' is a non-matching office"})
                        continue

            reason = _validate_job(title, job_url)
            if reason is None:
                jobs.append({"title": title, "url": job_url})
            elif debug:
                rejected.append({"title": title, "url": job_url, "selector": "greenhouse_api", "reason": reason})

    logger.info(f"Greenhouse API: fetched {len(jobs)} jobs for {company_slug}")
    if debug:
        return jobs, rejected
    return jobs
