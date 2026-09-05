"""Ashby ATS handler: GET api.ashbyhq.com/posting-api/job-board/{company}; host-matched (not substring) to avoid attacker-controlled paths, with department/location/team filters applied client-side by resolving IDs to names from the board HTML since the API doesn't return names itself."""
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


def _resolve_group_names(page_text: str, filter_ids: set) -> set:
    """Resolve department/team filter IDs to their names, including descendants, since Ashby's board
    filters a node and all its children (BFS over parent->children built from the embedded id/name JSON)."""
    if not filter_ids:
        return set()
    name_by_id = dict(re.findall(r'"id"\s*:\s*"([0-9a-f-]{36})"\s*,\s*"name"\s*:\s*"([^"]+)"', page_text))
    children: dict = {}
    for m in re.finditer(r'"id"\s*:\s*"([0-9a-f-]{36})"[^{}]*?"parent(?:Team|Department)Id"\s*:\s*"([0-9a-f-]{36})"', page_text):
        children.setdefault(m.group(2), []).append(m.group(1))
    names, seen, stack = set(), set(), list(filter_ids)
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        if cur in name_by_id:
            names.add(name_by_id[cur])
        stack.extend(children.get(cur, []))
    return names


async def scrape(url: str, debug: bool = False) -> list[dict] | tuple:
    """Fetch jobs from Ashby's public JSON API; departmentId/locationId filtering is applied
    client-side since the API returns all jobs unfiltered."""
    parsed = urlparse(url)
    path_parts = [p for p in parsed.path.strip("/").split("/") if p]
    if not path_parts:
        if debug:
            return [], [{"title": "(none)", "url": url, "selector": "ashby_api", "reason": "No company slug in URL"}]
        return []
    company_slug = path_parts[0]

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
        # Fetch page once to resolve the filter IDs to names.
        group_names = set()  # departmentId is Ashby's generic grouping filter — some boards group by
                              # department, others by team (e.g. Plaid), so it may resolve to either
        loc_names = set()
        if filter_dept_ids or filter_location_ids or filter_team_ids:
            try:
                page_resp = await client.get(url, headers={"Accept": "text/html", "User-Agent": _USER_AGENT})
                page_text = page_resp.text
                group_names = _resolve_group_names(page_text, filter_dept_ids | filter_team_ids)
                for loc_id in filter_location_ids:
                    # Location mapping uses "locationId"/"locationName" in job entries
                    m = re.search(
                        rf'"locationId"\s*:\s*"{re.escape(loc_id)}"[^}}]*?"locationName"\s*:\s*"([^"]+)"',
                        page_text,
                    )
                    if m:
                        loc_names.add(m.group(1))
                logger.info(f"Ashby: resolved groups={group_names}, locs={loc_names}")
            except Exception as e:
                logger.warning(f"Ashby: could not resolve filter names: {e}")

        for posting in data.get("jobs", []):
            if not posting.get("isListed", True):
                continue

            title = (posting.get("title") or "").strip()
            job_url = posting.get("jobUrl") or ""

            # A posting passes if EITHER its department or team is in the resolved group names —
            # boards vary in which field carries the real grouping (e.g. Plaid uses team, not department).
            if group_names:
                job_dept = (posting.get("department") or "").strip()
                job_team = (posting.get("team") or "").strip()
                if job_dept not in group_names and job_team not in group_names:
                    if debug:
                        rejected.append({"title": title, "url": job_url, "selector": "ashby_api", "reason": f"Dept '{job_dept}' / team '{job_team}' not in filter {group_names}"})
                    continue

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
