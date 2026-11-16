"""Workday ATS handler — JSON API via POST /wday/cxs/{company}/{site}/jobs; detected by hostname match on myworkdayjobs.com."""
import asyncio
import json
import logging
import re
from urllib.parse import urlparse, parse_qs

import httpx

from backend.scraper._shared.urls import host_matches
from backend.scraper._shared.filters import _validate_job
from backend.scraper._shared.errors import raise_if_board_gone
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


# Workday's jobs endpoint never reports or pages past 2,000 results: a bigger
# board says total=2000 and offsets beyond it repeat earlier rows. A search that
# reaches the ceiling is split by a facet (job category, location, ...), whose
# per-value counts come back with the first page, and each part is fetched on its
# own; a part still at the ceiling is split again, up to _MAX_SPLIT_DEPTH levels.
_CEILING = 2000
_MAX_SPLIT_DEPTH = 2
_PAGE = 20  # Workday API max per request
_HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}


def _facet_options(facets: list) -> list[tuple[str, list[tuple[str, int]]]]:
    """(facetParameter, [(value id, count), ...]) for every facet in a response.

    `locationMainGroup` nests further facets, each with its own parameter
    (`locationHierarchy1`, `locations`, ...); those are listed in its place.
    """
    out = []
    for f in facets or []:
        values = f.get("values") or []
        if values and isinstance(values[0], dict) and "facetParameter" in values[0]:
            out.extend(_facet_options(values))
            continue
        param = f.get("facetParameter")
        pairs = [(v.get("id"), int(v.get("count") or 0)) for v in values
                 if isinstance(v, dict) and v.get("id")]
        pairs = [(i, c) for i, c in pairs if c > 0]
        if param and pairs:
            out.append((param, pairs))
    return out


def _split_facet(options, applied: dict, total: int):
    """The facet to split a ceiling-sized search by, or None.

    A facet already applied is left alone. The best one covers the whole search
    (its counts add up to at least `total`) with every part under the ceiling,
    and among those the one that costs the fewest requests: a facet whose values
    overlap (a posting in several locations) fetches the same posting twice.
    """
    candidates = [(param, pairs) for param, pairs in options if param not in applied and len(pairs) > 1]
    if not candidates:
        return None

    def rank(item):
        _, pairs = item
        covered = sum(c for _, c in pairs)
        largest = max(c for _, c in pairs)
        requests = sum(-(-min(c, _CEILING) // _PAGE) for _, c in pairs)
        return (covered < total, largest >= _CEILING, requests)

    return min(candidates, key=rank)


# A Workday tenant sometimes answers with a maintenance or bot-check page (HTML with status 200)
# or a 429/5xx for a minute; one blip used to fail the whole company run with a JSONDecodeError.
_RETRY_WAITS = (2, 5)          # seconds before the 2nd and 3rd attempt
_RETRY_STATUSES = {429, 500, 502, 503, 504}


class WorkdayUnavailable(RuntimeError):
    """The Workday API kept answering with something that is not its JSON."""


async def _post_page(client, api_url: str, payload: dict, label: str):
    """POST one page; retries a non-JSON answer or a 429/5xx. Returns (status, data or None)."""
    for attempt in range(len(_RETRY_WAITS) + 1):
        resp = await client.post(api_url, json=payload, headers=_HEADERS)
        retry = resp.status_code in _RETRY_STATUSES
        data = None
        if resp.status_code == 200:
            try:
                data = json.loads(resp.text)
            except ValueError:
                retry = True
        if not retry:
            return resp.status_code, data
        if attempt < len(_RETRY_WAITS):
            logger.info(f"Workday API: {label} answered {resp.status_code}"
                        f"{' with a non-JSON page' if resp.status_code == 200 else ''}; retrying")
            await asyncio.sleep(_RETRY_WAITS[attempt])
    if resp.status_code == 200:
        raise WorkdayUnavailable(f"Workday returned a non-JSON page for {label} three times "
                                 "(maintenance or a bot check); it should work on the next run")
    return resp.status_code, None


async def _walk(client, api_url: str, facets: dict, label: str, debug: bool, rejected: list):
    """Page through one search. Returns (status of the first page, total, facets, postings)."""
    postings: list[dict] = []
    offset = 0
    total = None  # Capture from first page only (Workday returns 0 on later pages)
    first_facets = []
    while True:
        payload = {"appliedFacets": facets, "limit": _PAGE, "offset": offset, "searchText": ""}
        status, data = await _post_page(client, api_url, payload, label)
        if status != 200:
            logger.warning(f"Workday API returned {status} for {label}")
            if debug:
                rejected.append({"title": "(none)", "url": api_url, "selector": "workday_api",
                                 "reason": f"HTTP {status}"})
            return (status if offset == 0 else 200), total or 0, first_facets, postings
        if total is None:
            total = data.get("total", 0) or 0
            first_facets = data.get("facets") or []
        page = data.get("jobPostings", [])
        if not page:
            break
        postings.extend(page)
        offset += len(page)
        if offset >= total or offset >= _CEILING:
            break
    return 200, total or 0, first_facets, postings


async def _collect(client, api_url, facets, label, debug, rejected, found: dict, depth: int = 0):
    """Fetch one search into `found` (keyed by externalPath); split it when it hits the ceiling."""
    status, total, facet_list, postings = await _walk(client, api_url, facets, label, debug, rejected)
    for p in postings:
        found.setdefault(p.get("externalPath") or id(p), p)
    if total < _CEILING or depth >= _MAX_SPLIT_DEPTH:
        if total >= _CEILING:
            logger.warning(f"Workday API: {label} still at the {_CEILING}-result ceiling after "
                           f"{depth} splits; some jobs may be missing")
        return status, total
    choice = _split_facet(_facet_options(facet_list), facets, total)
    if choice is None:
        logger.warning(f"Workday API: {label} is at the {_CEILING}-result ceiling and offers no facet "
                       f"to split by; some jobs may be missing")
        return status, total
    param, pairs = choice
    logger.info(f"Workday API: {label} hit the {_CEILING}-result ceiling; splitting by {param} "
                f"({len(pairs)} parts)")
    for value_id, _count in pairs:
        await _collect(client, api_url, {**facets, param: [value_id]}, label, debug, rejected,
                       found, depth + 1)
    return status, total


async def scrape(url: str, debug: bool = False) -> list[dict] | tuple:
    """Fetch jobs from Workday's internal JSON API."""
    origin, company_slug, site, applied_facets = _parse_workday_url(url)

    if not company_slug or not site:
        logger.warning(f"Workday: could not parse company/site from {url}")
        if debug:
            return [], [{"title": "(none)", "url": url, "selector": "workday_api", "reason": "Bad URL format"}]
        return []

    api_url = f"{origin}/wday/cxs/{company_slug}/{site}/jobs"
    label = f"{company_slug}/{site}"
    logger.info(f"Workday API: {api_url} facets={list(applied_facets.keys())}")

    jobs = []
    rejected = []
    found: dict = {}

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        status, total = await _collect(client, api_url, applied_facets, label, debug, rejected, found)
    if status != 200 and not found:
        if not debug:
            raise_if_board_gone(status, "Workday", label)
    else:
        logger.info(f"Workday API: total={total}")

    for p in found.values():
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

    logger.info(f"Workday API: fetched {len(jobs)} jobs for {label}")
    if debug:
        return jobs, rejected
    return jobs
