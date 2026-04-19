"""Ashby ATS handler — GET api.ashbyhq.com/posting-api/job-board/{company}.

Detection: host match on `jobs.ashbyhq.com` (prevents matching attacker-controlled
paths like `https://evil.com/?u=ashbyhq.com`).
Public interface: is_ashby(url), scrape(url, debug=False).

The public Ashby API returns all postings for a company. Department/location/team
filtering is applied client-side by resolving the filter IDs to names via the
board HTML (Ashby embeds ID→name mappings there, not in the API response).
"""
import json
import logging
import re
from urllib.parse import parse_qs, urlparse

import httpx

from backend.scraper._shared.browser import _USER_AGENT
from backend.scraper._shared.filters import _validate_job
from backend.scraper._shared.urls import host_matches

logger = logging.getLogger("jobnavigator.scraper.ats.ashby")


def is_ashby(url: str) -> bool:
    """Check if URL is an Ashby job board (jobs.ashbyhq.com)."""
    return host_matches(url, "jobs.ashbyhq.com")


async def scrape(url: str, debug: bool = False) -> list[dict] | tuple:
    """Fetch jobs from Ashby's public JSON API.

    API returns all jobs; departmentId/locationId filtering is applied client-side.
    """
    parsed = urlparse(url)
    # Company slug from path: /ramp or /ramp/
    path_parts = [p for p in parsed.path.strip("/").split("/") if p]
    if not path_parts:
        if debug:
            return [], [{"title": "(none)", "url": url, "selector": "ashby_api", "reason": "No company slug in URL"}]
        return []
    company_slug = path_parts[0]

    # Extract filter params from URL query string
    qs = parse_qs(parsed.query)
    filter_dept_ids = set(qs.get("departmentId", []))
    filter_location_ids = set(qs.get("locationId", []))
    filter_team_ids = set(qs.get("teamId", []))

    api_url = f"https://api.ashbyhq.com/posting-api/job-board/{company_slug}"
    logger.info(f"Ashby API: {api_url} dept_filter={len(filter_dept_ids)} loc_filter={len(filter_location_ids)} team_filter={len(filter_team_ids)}")

    jobs = []
    rejected = []

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(api_url)
        if resp.status_code != 200:
            logger.warning(f"Ashby API returned {resp.status_code} for {company_slug}")
            if debug:
                return [], [{"title": "(none)", "url": api_url, "selector": "ashby_api", "reason": f"HTTP {resp.status_code}"}]
            return []

        data = json.loads(resp.text)

        # Ashby embeds ID→name mappings in the page HTML, not in the API response.
        # Fetch page once to resolve both departmentId and locationId filters.
        dept_names = set()
        loc_names = set()
        team_names = set()
        if filter_dept_ids or filter_location_ids or filter_team_ids:
            try:
                page_resp = await client.get(url, headers={"Accept": "text/html", "User-Agent": _USER_AGENT})
                page_text = page_resp.text
                for dept_id in filter_dept_ids:
                    m = re.search(
                        rf'"id"\s*:\s*"{re.escape(dept_id)}"[^}}]*?"name"\s*:\s*"([^"]+)"',
                        page_text,
                    )
                    if m:
                        dept_names.add(m.group(1))
                for loc_id in filter_location_ids:
                    # Location mapping uses "locationId"/"locationName" in job entries
                    m = re.search(
                        rf'"locationId"\s*:\s*"{re.escape(loc_id)}"[^}}]*?"locationName"\s*:\s*"([^"]+)"',
                        page_text,
                    )
                    if m:
                        loc_names.add(m.group(1))
                for team_id in filter_team_ids:
                    m = re.search(
                        rf'"id"\s*:\s*"{re.escape(team_id)}"[^}}]*?"name"\s*:\s*"([^"]+)"',
                        page_text,
                    )
                    if m:
                        team_names.add(m.group(1))
                logger.info(f"Ashby: resolved depts={dept_names}, locs={loc_names}, teams={team_names}")
            except Exception as e:
                logger.warning(f"Ashby: could not resolve filter names: {e}")

        for posting in data.get("jobs", []):
            if not posting.get("isListed", True):
                continue

            title = (posting.get("title") or "").strip()
            job_url = posting.get("jobUrl") or ""

            # Apply department filter if specified
            if dept_names:
                job_dept = (posting.get("department") or "").strip()
                if job_dept not in dept_names:
                    if debug:
                        rejected.append({"title": title, "url": job_url, "selector": "ashby_api", "reason": f"Department '{job_dept}' not in filter {dept_names}"})
                    continue

            # Apply team filter if specified
            if team_names:
                job_team = (posting.get("team") or "").strip()
                if job_team not in team_names:
                    if debug:
                        rejected.append({"title": title, "url": job_url, "selector": "ashby_api", "reason": f"Team '{job_team}' not in filter {team_names}"})
                    continue

            # Apply location filter if specified
            if loc_names:
                job_loc = (posting.get("location") or "").strip()
                if not any(ln.lower() in job_loc.lower() for ln in loc_names):
                    if debug:
                        rejected.append({"title": title, "url": job_url, "selector": "ashby_api", "reason": f"Location '{job_loc}' not in filter {loc_names}"})
                    continue

            reason = _validate_job(title, job_url)
            if reason is None:
                jobs.append({"title": title, "url": job_url})
            elif debug:
                rejected.append({"title": title, "url": job_url, "selector": "ashby_api", "reason": reason})

    logger.info(f"Ashby API: fetched {len(jobs)} jobs for {company_slug}")
    if debug:
        return jobs, rejected
    return jobs
