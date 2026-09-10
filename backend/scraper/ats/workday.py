"""Workday ATS handler — JSON API via POST /wday/cxs/{company}/{site}/jobs; detected by hostname match on myworkdayjobs.com."""
import json
import logging
import re
from urllib.parse import urlparse, parse_qs

import httpx

from backend.scraper._shared.urls import host_matches
from backend.scraper._shared.filters import _validate_job
from backend.analyzer.location import COUNT_ONLY, canonical, group_pieces

logger = logging.getLogger("jobnavigator.scraper.ats.workday")

_LOCALE_PATH_RE = re.compile(r'^[a-z]{2}(-[A-Z]{2})?$')  # en-US, en, de-DE, etc.


def is_workday(url: str) -> bool:
    """Check if URL is a Workday career site (myworkdayjobs.com)."""
    return host_matches(url, "myworkdayjobs.com")


def _parse_workday_url(url: str) -> tuple[str, str, str, dict]:
    """Parse Workday URL (https://{company}.wd{N}.myworkdayjobs.com/[locale/]{site}/?params) into (origin, company_slug, site, applied_facets); API endpoint is https://{host}/wday/cxs/{company}/{site}/jobs."""
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

    qs = parse_qs(parsed.query)
    applied_facets = {}
    skip_params = {"source", "utm_source", "utm_medium", "utm_campaign", "utm_content"}
    for key, values in qs.items():
        if key.lower() in skip_params:
            continue
        applied_facets[key] = values

    return origin, company_slug, site, applied_facets


_PATH_PLACE = re.compile(r"^/job/([^/]+)/")


def _location_of(posting: dict) -> str | None:
    """Read a Workday posting's location, in the order every other source uses.

    `locationsText` is per-tenant, so this one field carries "US, CA, Santa
    Clara", "Ireland - Dublin", "California - San Francisco" and
    "USA.VA.Reston". `canonical` classifies the parts instead of trusting their
    order, and hands back the board's own text when it cannot.

    A multi-site posting reports a count ("2 Locations") rather than a place. In
    that case the primary site comes from `externalPath`, shaped
    "/job/US-CA-Santa-Clara/Title_JR123".
    """
    text = (posting.get("locationsText") or "").strip()
    if text and not COUNT_ONLY.match(text):
        return canonical(text)

    match = _PATH_PLACE.match(posting.get("externalPath") or "")
    if not match:
        return None
    # The segment separates its parts with dashes and also uses a dash inside a
    # city name, so every piece is classified and the leftovers rejoin with a
    # space: "US-CA-Santa-Clara" -> "Santa Clara, CA, United States".
    pieces = [p for p in match.group(1).split("-") if p.strip()]
    return canonical(", ".join(group_pieces(pieces)), text_joiner=" ")


def _board_location_of(posting: dict) -> str | None:
    """The board's own words, which is what `location` holds everywhere else.

    `locationsText` is kept exactly as printed - the parser's canonical form
    belongs in the loc_* columns, not in the field the feed displays. A count
    ("5 Locations") names no place at all, so that one case falls back to the
    primary site in `externalPath`, which only exists in canonical form.
    """
    text = (posting.get("locationsText") or "").strip()
    if text and not COUNT_ONLY.match(text):
        return text
    return _location_of(posting)


# Workday's own vocabulary for the listing's `remoteType`. "Flex" is a Workday
# tenant's label for a schedule split between an office and home, which is what
# every other board calls hybrid; the other three values map themselves.
_REMOTE_TYPES = {"flex": "hybrid"}


def _arrangement_of(posting: dict) -> str | None:
    """The listing's `remoteType`: Flex, Remote, Onsite or Hybrid."""
    value = (posting.get("remoteType") or "").strip()
    if not value:
        return None
    return _REMOTE_TYPES.get(value.lower(), value)


def detail_locations(detail: dict) -> list[str]:
    """Every place named by one posting's detail JSON, primary first.

    The detail document is already fetched once per new job for its description
    (see ats/_descriptions.py), and it is the only Workday response that lists
    the other sites: a multi-site listing entry says "5 Locations" and nothing
    more. `location` and `additionalLocations` are the board's own strings, in
    the same per-tenant shape as `locationsText`.
    """
    info = detail.get("jobPostingInfo") or {}
    out: list[str] = []
    primary = (info.get("location") or "").strip()
    if primary:
        out.append(primary)
    for extra in info.get("additionalLocations") or []:
        text = extra.strip() if isinstance(extra, str) else ""
        if text and text not in out:
            out.append(text)
    return out


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
                    # `locations` is filled in later, from the detail JSON the
                    # description fetch already downloads for each new job.
                    jobs.append({"title": title, "url": job_url,
                                 "location": _board_location_of(p),
                                 "arrangement": _arrangement_of(p)})
                elif debug:
                    rejected.append({"title": title, "url": job_url, "selector": "workday_api", "reason": reason})

            offset += len(postings)
            if offset >= total:
                break

    logger.info(f"Workday API: fetched {len(jobs)} jobs for {company_slug}/{site}")
    if debug:
        return jobs, rejected
    return jobs
