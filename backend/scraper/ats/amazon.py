"""Amazon Jobs handler — the search page's own JSON feed.

`www.amazon.jobs/en/search?…` renders from `…/en/search.json?…`, the same query
string against the same endpoint. Reading it directly costs one HTTP request
instead of a browser, and it carries the fields the card does not print: every
site of a multi-site posting, and the posting's ONSITE/REMOTE type.
"""
import json
import logging
from urllib.parse import urlparse, parse_qs, urlencode

import httpx

from backend.scraper._shared.urls import host_matches
from backend.scraper._shared.filters import _validate_job

logger = logging.getLogger("jobnavigator.scraper.ats.amazon")

_PAGE = 100          # the feed's own maximum per request
_MAX_PAGES = 5


def is_amazon(url: str) -> bool:
    """True for an amazon.jobs search URL, the only shape this handler reads."""
    return host_matches(url, "amazon.jobs") and "/search" in urlparse(url).path


def _locations_of(posting: dict) -> list[str]:
    """Every place one posting names, primary first.

    `location` is the board's own line ("US, WA, Redmond"). `locations` holds one
    JSON *string* per site, of which `normalizedLocation` ("Redmond, Washington,
    USA") is the readable form.
    """
    out: list[str] = []
    primary = (posting.get("location") or "").strip()
    if primary:
        out.append(primary)
    for entry in posting.get("locations") or []:
        try:
            data = json.loads(entry) if isinstance(entry, str) else entry
        except (ValueError, TypeError):
            continue
        if not isinstance(data, dict):
            continue
        text = (data.get("normalizedLocation")
                or data.get("locationNonStemming") or "").strip()
        if text and text not in out:
            out.append(text)
    return out


def _arrangement_of(posting: dict) -> str | None:
    """The `type` the feed puts on each site: ONSITE, REMOTE, … or nothing."""
    for entry in posting.get("locations") or []:
        try:
            data = json.loads(entry) if isinstance(entry, str) else entry
        except (ValueError, TypeError):
            continue
        value = (data.get("type") or "").strip() if isinstance(data, dict) else ""
        if value:
            return value
    return None


async def scrape(url: str, debug: bool = False) -> list[dict] | tuple:
    """Fetch one amazon.jobs search as JSON, paging on the feed's own offset."""
    parsed = urlparse(url)
    params = {k: v for k, v in parse_qs(parsed.query, keep_blank_values=True).items()}
    api_base = f"{parsed.scheme}://{parsed.netloc}/en/search.json"

    jobs = []
    rejected = []
    offset = 0

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for _ in range(_MAX_PAGES):
            params["offset"] = [str(offset)]
            params["result_limit"] = [str(_PAGE)]
            api_url = f"{api_base}?{urlencode(params, doseq=True)}"
            resp = await client.get(api_url, headers={"Accept": "application/json"})
            if resp.status_code != 200:
                logger.warning(f"Amazon Jobs returned {resp.status_code}")
                if debug:
                    rejected.append({"title": "(none)", "url": api_url,
                                     "selector": "amazon_json", "reason": f"HTTP {resp.status_code}"})
                break
            data = json.loads(resp.text)
            postings = data.get("jobs", [])
            if not postings:
                break

            for p in postings:
                title = (p.get("title") or "").strip()
                path = p.get("job_path") or ""
                job_url = f"{parsed.scheme}://{parsed.netloc}{path}" if path else ""
                reason = _validate_job(title, job_url)
                if reason is None:
                    jobs.append({"title": title, "url": job_url,
                                 "location": (p.get("location") or "").strip() or None,
                                 "locations": _locations_of(p),
                                 "arrangement": _arrangement_of(p)})
                elif debug:
                    rejected.append({"title": title, "url": job_url,
                                     "selector": "amazon_json", "reason": reason})

            offset += len(postings)
            if offset >= data.get("hits", 0) or len(postings) < _PAGE:
                break

    logger.info(f"Amazon Jobs: fetched {len(jobs)} jobs")
    if debug:
        return jobs, rejected
    return jobs
