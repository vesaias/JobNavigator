"""Oracle HCM ATS handler — REST API at {host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions.

Detection matches direct `oraclecloud.com/hcmUI/CandidateExperience` URLs and
known custom career subdomains (e.g. careers.oracle.com) that front an Oracle
HCM backend.

Public interface: is_oracle_hcm(url), scrape(url, debug=False).
"""
import json
import logging
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from backend.scraper._shared.filters import _validate_job

logger = logging.getLogger("jobnavigator.scraper.ats.oracle_hcm")


# Map custom career domains to their Oracle HCM API backend
_ORACLE_HCM_HOSTS = {
    "careers.oracle.com": "eeho.fa.us2.oraclecloud.com",
}


def is_oracle_hcm(url: str) -> bool:
    """Check if URL is an Oracle HCM CandidateExperience job board.

    Accepts direct oraclecloud.com CandidateExperience URLs, known custom
    domains from _ORACLE_HCM_HOSTS, and legacy /sites/.../jobs URLs that
    resolve via _oracle_hcm_host.
    """
    if "oraclecloud.com/hcmUI/CandidateExperience" in url:
        return True
    if _oracle_hcm_host(url) is None:
        return False
    # Hostname-mapped custom domain — accept root and job paths
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host in _ORACLE_HCM_HOSTS:
        return True
    # Direct oraclecloud.com host (non-standard path) — require /sites/ + /jobs
    return "/sites/" in url and "/jobs" in url


def _oracle_hcm_host(url: str) -> str | None:
    """Return the Oracle HCM API host for a given URL, or None."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host == "oraclecloud.com" or host.endswith(".oraclecloud.com"):
        return parsed.netloc
    return _ORACLE_HCM_HOSTS.get(host)


async def scrape(url: str, debug: bool = False) -> list[dict] | tuple:
    """Fetch Oracle HCM job listings via REST API."""
    parsed = urlparse(url)
    ui_origin = f"{parsed.scheme}://{parsed.netloc}"
    api_host = _oracle_hcm_host(url)
    api_origin = f"https://{api_host}" if api_host else ui_origin
    params = parse_qs(parsed.query)

    # Extract site number from path: .../sites/CX_1001/jobs
    path_parts = parsed.path.split("/")
    site = ""
    for i, p in enumerate(path_parts):
        if p == "sites" and i + 1 < len(path_parts):
            site = path_parts[i + 1]
            break

    # Detect path prefix: oraclecloud.com URLs need /hcmUI/CandidateExperience,
    # custom domains (e.g. careers.oracle.com) route directly
    job_path_prefix = ""
    if "hcmUI/CandidateExperience" in parsed.path:
        job_path_prefix = "/hcmUI/CandidateExperience"

    # Build facets list
    facets = []
    categories = params.get("selectedCategoriesFacet", [""])[0].replace("%3B", ";")
    location_id = params.get("locationId", [""])[0]
    locations_facet = params.get("selectedLocationsFacet", [""])[0].replace("%3B", ";")
    posting_dates = params.get("selectedPostingDatesFacet", [""])[0]
    flex_fields = unquote(params.get("selectedFlexFieldsFacets", [""])[0])

    if posting_dates:
        facets.append(f"POSTING_DATES;{posting_dates}")
    if categories:
        facets.append(f"CATEGORIES;{categories}")
    if location_id:
        facets.append(f"LOCATIONS;{location_id}")
    elif locations_facet:
        facets.append(f"LOCATIONS;{locations_facet}")
    if flex_fields:
        facets.append(f"FLEX_FIELDS;{flex_fields}")
    facets_str = "|".join(facets)

    last_facet = params.get("lastSelectedFacet", ["POSTING_DATES"])[0]

    jobs = []
    rejected = []
    offset = 0
    limit = 200

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        while True:
            finder_parts = [
                f"siteNumber={site}",
                f"facetsList={facets_str}",
                f"lastSelectedFacet={last_facet}",
            ]
            if categories:
                finder_parts.append(f"selectedCategoriesFacet={categories}")
            if location_id:
                finder_parts.append(f"selectedLocationsFacet={location_id}")
            elif locations_facet:
                finder_parts.append(f"selectedLocationsFacet={locations_facet}")
            if posting_dates:
                finder_parts.append(f"selectedPostingDatesFacet={posting_dates}")
            if flex_fields:
                finder_parts.append(f"selectedFlexFieldsFacets={flex_fields}")
            finder_parts.extend([
                "sortBy=POSTING_DATES_DESC",
                f"limit={limit}",
                f"offset={offset}",
            ])

            api_url = (
                f"{api_origin}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
                f"?onlyData=true&expand=requisitionList.secondaryLocations,flexFieldsFacet.values"
                f"&finder=findReqs;{','.join(finder_parts)}"
            )

            resp = await client.get(api_url)
            if resp.status_code != 200:
                logger.warning(f"Oracle HCM API returned {resp.status_code} for {api_origin}/.../{site}")
                break
            try:
                data = json.loads(resp.text)
            except (ValueError, json.JSONDecodeError):
                logger.warning(f"Oracle HCM: invalid JSON from {api_origin}/.../{site}")
                break

            items = data.get("items", [])
            if not items:
                break

            req_list = items[0].get("requisitionList", [])
            total = items[0].get("TotalJobsCount", 0)

            for req in req_list:
                title = req.get("Title", "").strip()
                req_id = req.get("Id", "")
                job_url = f"{ui_origin}{job_path_prefix}/en/sites/{site}/job/{req_id}"
                reason = _validate_job(title, job_url)
                if reason is None:
                    jobs.append({"title": title, "url": job_url})
                elif debug:
                    rejected.append({"title": title, "url": job_url, "selector": "oracle_hcm_api", "reason": reason})

            offset += len(req_list)
            if offset >= total or len(req_list) == 0:
                break

    logger.info(f"Oracle HCM: fetched {len(jobs)} jobs from {api_origin}/.../{site}")
    if debug:
        return jobs, rejected
    return jobs
