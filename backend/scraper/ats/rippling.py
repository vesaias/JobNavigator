"""Rippling ATS handler — GET api.rippling.com/platform/api/ats/v1/board/{slug}/jobs.
Server-side filter params are unreliable, so filtering happens client-side; multi-location jobs repeat under the same UUID and are deduped preferring US locations."""
import json
import logging
import re
from urllib.parse import urlparse, parse_qs

import httpx

from backend.scraper._shared.urls import host_matches, path_contains
from backend.scraper._shared.filters import _validate_job

logger = logging.getLogger("jobnavigator.scraper.ats.rippling")


def is_rippling(url: str) -> bool:
    """Check if URL is a Rippling ATS board (ats.rippling.com or rippling.com/careers)."""
    if host_matches(url, "ats.rippling.com"):
        return True
    return host_matches(url, "rippling.com") and path_contains(url, "/careers")


def _parse_rippling_url(url: str) -> tuple[str, dict]:
    """Parse a Rippling URL into (board_slug, query_filters); defaults to slug 'rippling' when there's no ats.rippling.com path segment."""
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    filters = {}

    if host_matches(url, "ats.rippling.com"):
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        slug = parts[0] if parts else "rippling"
    else:
        slug = "rippling"

    if "department" in qs:
        filters["department"] = qs["department"][0]
    if "workLocation" in qs:
        filters["workLocation"] = qs["workLocation"][0]
    if "searchTerm" in qs:
        filters["searchTerm"] = qs["searchTerm"][0]

    return slug, filters


async def scrape(url: str, debug: bool = False) -> list[dict] | tuple:
    """Fetch jobs from Rippling's public ATS API, filtering and deduping client-side (see module docstring)."""
    slug, filters = _parse_rippling_url(url)
    api_url = f"https://api.rippling.com/platform/api/ats/v1/board/{slug}/jobs"
    filter_dept = filters.get("department", "").lower()
    filter_loc = filters.get("workLocation", "").lower()

    logger.info(f"Rippling API: {api_url} dept_filter='{filter_dept}' loc_filter='{filter_loc}'")

    jobs = []
    rejected = []

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        # Fetch all jobs — don't pass filter params (API ignores them)
        resp = await client.get(api_url)
        if resp.status_code != 200:
            logger.warning(f"Rippling API returned {resp.status_code} for {slug}")
            if debug:
                return [], [{"title": "(none)", "url": api_url, "selector": "rippling_api", "reason": f"HTTP {resp.status_code}"}]
            return []

        postings = json.loads(resp.text)
        logger.info(f"Rippling API: {len(postings)} entries for {slug}")

        # Multi-location jobs repeat under the same UUID; keep the entry that best matches the filter.
        seen_uuids: dict[str, list] = {}
        for posting in postings:
            uuid = posting.get("uuid", "")
            seen_uuids.setdefault(uuid, []).append(posting)

        logger.info(f"Rippling API: {len(seen_uuids)} unique jobs after UUID dedup")

        for uuid, entries in seen_uuids.items():
            # Pick the best location entry: prefer filter match, then US, then first
            best = entries[0]
            all_locs = []
            for e in entries:
                loc = e.get("workLocation", {})
                loc_label = loc.get("label", "") if isinstance(loc, dict) else str(loc)
                all_locs.append(loc_label)
                if filter_loc and filter_loc in loc_label.lower():
                    best = e
                elif not filter_loc and "United States" in loc_label:
                    best = e

            title = (best.get("name") or "").strip()
            job_url = best.get("url") or ""
            dept = best.get("department", {})
            dept_label = dept.get("label", "") if isinstance(dept, dict) else str(dept)
            loc = best.get("workLocation", {})
            loc_label = loc.get("label", "") if isinstance(loc, dict) else str(loc)

            if filter_dept and filter_dept != dept_label.lower():
                if debug:
                    rejected.append({"title": title, "url": job_url, "selector": "rippling_api",
                                     "reason": f"Department '{dept_label}' != '{filters.get('department', '')}'"})
                continue

            if filter_loc:
                def _loc_matches(loc_str: str) -> bool:
                    lower = loc_str.lower()
                    if filter_loc in lower:
                        return True
                    # US filter: match "City, XX" where XX is a US state abbreviation
                    if "united states" in filter_loc:
                        parts = loc_str.rsplit(", ", 1)
                        if len(parts) == 2 and re.match(r'^[A-Z]{2}$', parts[1]):
                            return True
                    return False

                if not any(_loc_matches(loc) for loc in all_locs):
                    if debug:
                        rejected.append({"title": title, "url": job_url, "selector": "rippling_api",
                                         "reason": f"No location matches '{filters.get('workLocation', '')}' (has: {', '.join(all_locs[:3])})"})
                    continue

            reason = _validate_job(title, job_url)
            if reason is None:
                jobs.append({"title": title, "url": job_url})
            elif debug:
                rejected.append({"title": title, "url": job_url, "selector": "rippling_api", "reason": reason})

    logger.info(f"Rippling API: fetched {len(jobs)} jobs for {slug}")
    if debug:
        return jobs, rejected
    return jobs
