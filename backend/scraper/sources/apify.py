"""Apify source: runs Apify Store actors as job boards, billed to the API key in Settings.

Each PRESETS entry is one board: the actor to run, how a Search becomes that
actor's input, and how one dataset item becomes a job. A search picks presets in
`sources`, the way a keyword search picks JobSpy boards, and every preset writes
its own row into `source_breakdown`. GET /api/searches/apify-boards serves the
list to both UIs, so a new board is one entry here and no frontend change.

| preset           | actor                                       | why it is here                                  |
| ---------------- | ------------------------------------------- | ----------------------------------------------- |
| apify_indeed     | misceres/indeed-scraper, fed one search URL | JobSpy's direct Indeed requests get blocked     |
| apify_linkedin   | valig/linkedin-jobs-scraper                 | JobSpy gets rate-limited on LinkedIn            |
| apify_glassdoor  | valig/glassdoor-jobs-scraper                | JobSpy's Glassdoor path is not offered at all   |
| apify_behance    | piotrv1001/behance-jobs-scraper             | fallback for the creative mode's own clients    |
| apify_hollylist  | datawatcher/hollylist-scraper               | (same)                                          |
| apify_greenhouse | fantastic-jobs/career-site-job-listing-api  | keyword search across every company on that     |
| apify_lever      | with ats=[<that ATS>]                       | ATS; the built-in ATS handlers need a known     |
| apify_ashby      |                                             | company                                         |
| apify_workday    |                                             |                                                 |

The keys carry the `apify_` prefix so they can never collide with a JobSpy board
("indeed", "linkedin", "glassdoor"): a search whose `sources` still holds JobSpy
boards cannot run a paid board by accident. A key is also the stored Job.source.

Apify charges per result. Every run is bounded three ways: `maxItems` (results_wanted,
clamped to MAX_RESULTS; a preview, the Test button, uses PREVIEW_LIMIT), a spend cap
`maxTotalChargeUsd` (charge_cap_usd) and a platform-side `timeout` equal to our own
_MAX_WAIT, so the platform stops the run even when this process dies mid-poll.
"""
import math
import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable
from urllib.parse import urlencode

import httpx
from sqlalchemy.exc import IntegrityError

from backend.countries import (
    DEFAULT_COUNTRY, compose_location, indeed_host, normalize_country, split_country_suffix,
    supported_countries,
)
from backend.accounts.settings import get_setting
from backend.models.db import SessionLocal, Job, Search, get_existing_external_ids
from backend.analyzer.salary_extractor import extract_salary
from backend.analyzer.work_arrangement import HYBRID, ONSITE, REMOTE, extract_arrangement
from backend.scraper._shared.analysis import analyze_inline, prefetch_h1b
from backend.scraper._shared.dedup import make_external_id, make_content_hash
from backend.scraper._shared.posting_links import counts_as_new
from backend.scraper._shared.filters import (build_search_exclude_sets, company_included,
                                             search_title_filters, title_kept)
from backend.scraper._shared.html_text import html_to_text

logger = logging.getLogger("jobnavigator.apify")

API_BASE = "https://api.apify.com/v2"
TOKEN_SETTING = "apify_api_key"
PREVIEW_LIMIT = 20
# results_wanted is clamped to this per board for every Apify search: on create, on
# PATCH and at run time (the API accepts any integer; the UI's field stops here too).
MAX_RESULTS = 200
_WAIT_STEP = 60          # the API holds one status request open for 60 s at most
_MAX_WAIT = 15 * 60      # a run still going after this is aborted, so it stops billing
_TERMINAL = {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}
# Spend cap per run (maxTotalChargeUsd): results × the board's price × a margin for
# start and compute charges, never below a few cents, never above the ceiling.
_CHARGE_MARGIN = 1.5
_MIN_CHARGE_USD = 0.10
_MAX_CHARGE_USD = 5.00


def clamp_results(value) -> int:
    """results_wanted of an Apify search, within 1..MAX_RESULTS (empty = the column default 50)."""
    try:
        n = int(value) if value is not None else 50
    except (TypeError, ValueError):
        n = 50
    return min(MAX_RESULTS, max(1, n))


class ApifyError(Exception):
    """A failure the run history shows as is. The text never carries the API key."""


# ── Search → actor input ────────────────────────────────────────────────────

def _place(search: Search) -> str:
    """The city or region of a search, without a country segment."""
    return split_country_suffix(search.location or "")[0]


def _country_label(search: Search) -> str:
    """"usa" -> "United States", the full English name the career-site actor expects."""
    labels = dict(supported_countries())
    return labels.get(normalize_country(search.country) or "") or labels.get(DEFAULT_COUNTRY, "")


def _time_range(hours_old) -> str:
    """The narrowest actor timeRange that still covers `hours_old` (0/None = the actor default)."""
    if not hours_old:
        return "7d"
    if hours_old <= 1:
        return "1h"
    if hours_old <= 24:
        return "24h"
    if hours_old <= 168:
        return "7d"
    return "6m"


def _indeed_fromage(hours_old) -> int | None:
    """Indeed's `fromage` (posting age in days: 1, 3, 7 or 14) that still covers `hours_old`.

    Past 14 days, or with no age set, the URL carries no filter: a narrower one
    would drop jobs the search asked for.
    """
    if not hours_old:
        return None
    for days in (1, 3, 7, 14):
        if hours_old <= days * 24:
            return days
    return None


def _indeed_input(search: Search, limit: int) -> dict:
    """One Indeed search URL, because the actor's keyword fields take no posting age.

    The actor runs `position` and every start URL as separate searches, each
    billed up to maxItemsPerSearch, so the input holds the URL and nothing else.
    """
    params = {"q": (search.search_term or "").strip()}
    # Indeed reads "Remote" as a place (see countries.compose_location).
    place = _place(search) or ("Remote" if search.is_remote else "")
    if place:
        params["l"] = place
    fromage = _indeed_fromage(search.hours_old)
    if fromage:
        params["fromage"] = fromage
    host = indeed_host(search.country) or indeed_host(DEFAULT_COUNTRY)
    return {
        "startUrls": [{"url": f"https://{host}/jobs?{urlencode(params)}"}],
        "maxItemsPerSearch": limit,
        "saveOnlyUniqueItems": True,
    }


def _linkedin_input(search: Search, limit: int) -> dict:
    """LinkedIn search params pass through `urlParam`, the way JobSpy builds them: `f_TPR`
    takes any age in seconds (the actor's own datePosted has three steps).

    `f_WT=2` is LinkedIn's remote filter, and LinkedIn ignores it without login: on
    2026-10-22 the guest endpoint and the public /jobs/search page returned the same rows
    with and without it. It stays in the input because it costs nothing and a logged-in
    LinkedIn applies it. `_not_remote` is the filter that works: it drops the rows that
    the posting itself calls hybrid or on-site."""
    params = []
    if search.hours_old:
        params.append({"key": "f_TPR", "value": f"r{int(search.hours_old) * 3600}"})
    if search.is_remote:
        params.append({"key": "f_WT", "value": "2"})
    body = {
        "keywords": (search.search_term or "").strip(),
        # The same composed string JobSpy sends LinkedIn (see countries.compose_location).
        "location": compose_location(search.location, search.country),
        "limit": min(limit, 1000),
    }
    if params:
        body["urlParam"] = params
    return body


def _glassdoor_input(search: Search, limit: int) -> dict:
    """The actor requires a location; compose_location gives at least the country name."""
    body = {
        "keywords": (search.search_term or "").strip(),
        "location": compose_location(search.location, search.country),
        "limit": min(limit, 1000),
        "sortBy": "date_desc",
    }
    if search.hours_old:
        body["daysOld"] = -(-int(search.hours_old) // 24)    # whole days, rounded up
    if search.is_remote:
        body["remoteWorkType"] = True
    return body


def _first_place(search: Search) -> str:
    """"Los Angeles, CA" -> "Los Angeles": the creative-board actors match a bare city name."""
    return _place(search).split(",")[0].strip()


def _behance_input(search: Search, limit: int) -> dict:
    """The actor takes no posting age and no remote filter: its `isWorldwide` switch is not
    one (on 2026-10-24 a Remote run with it returned 15 on-site rows in Asia and Africa, and
    0 remote ones). `_not_remote` drops the on-site rows instead."""
    body = {"search": (search.search_term or "").strip(), "maxItems": limit,
            "jobTypes": ["CONTRACT", "FULLTIME"]}
    city = _first_place(search)
    if city:
        body["city"] = city
    return body


def _hollylist_input(search: Search, limit: int) -> dict:
    """Members-only offers carry no company and no text, so the actor skips them."""
    body = {"searchQueries": [(search.search_term or "").strip()], "maxResults": limit,
            "extractFullDetails": True, "includePremiumOffers": False}
    city = _first_place(search)
    if city:
        body["locations"] = [city]
    if search.is_remote:
        body["workType"] = ["remote"]
    return body


def _career_site_input(ats: str) -> Callable[[Search, int], dict]:
    """Input builder for one ATS on the career-site actor; `ats` is a value of its `ats` enum."""
    return lambda search, limit: _career_site_body(search, limit, ats)


def _career_site_body(search: Search, limit: int, ats: str) -> dict:
    body = {
        "ats": [ats],
        "titleSearch": [(search.search_term or "").strip()],
        "timeRange": _time_range(search.hours_old),
        "limit": min(max(limit, 10), 5000),   # the actor refuses a limit outside 10..5000
        "descriptionType": "text",
    }
    # The actor matches its own derived "City, Region, Country" strings, so a
    # composed "Austin, United States" would miss "Austin, Texas, United States".
    loc = _place(search) or _country_label(search)
    if loc:
        body["locationSearch"] = [loc]
    if search.is_remote:
        body["aiWorkArrangementFilter"] = ["Remote OK", "Remote Solely"]
    return body


# ── Dataset item → job ──────────────────────────────────────────────────────

_NOT_ANNUAL = re.compile(r"\b(hour|hr|day|week|month)\b", re.IGNORECASE)


def _annual_from_text(text: str) -> tuple:
    """(min, max) from a salary line such as "$120,000 - $150,000 a year"; "$25 - $30 an hour" gives (None, None)."""
    if not text or _NOT_ANNUAL.search(text):
        return None, None
    found = extract_salary(text)
    if found["salary_source"] != "posting":
        return None, None
    return found["salary_min"], found["salary_max"]


def _parse_indeed(raw: dict) -> dict:
    sal_min, sal_max = _annual_from_text(str(raw.get("salary") or ""))
    return {
        "title": raw.get("positionName") or "",
        "company": raw.get("company") or "",
        "url": raw.get("url") or "",
        "location": raw.get("location") or "",
        "description": raw.get("description") or "",
        "salary_min": sal_min,
        "salary_max": sal_max,
        "arrangement": None,
        "posted": raw.get("postedAt"),
    }


def _parse_linkedin(raw: dict) -> dict:
    sal_min, sal_max = _annual_from_text(str(raw.get("salary") or ""))
    job_id = str(raw.get("id") or "")
    return {
        "title": raw.get("title") or "",
        "company": raw.get("companyName") or "",
        # The form every other LinkedIn source stores, so the same posting dedups across them.
        "url": f"https://www.linkedin.com/jobs/view/{job_id}" if job_id.isdigit() else (raw.get("url") or ""),
        "location": raw.get("location") or "",
        "description": raw.get("description") or "",
        "salary_min": sal_min,
        "salary_max": sal_max,
        "arrangement": None,
        "posted": raw.get("postedDate"),
    }


def _parse_glassdoor(raw: dict) -> dict:
    pay = raw.get("pay") or {}
    annual = str(pay.get("period") or "").upper() == "ANNUAL"
    sal_min = pay.get("min") if annual else None
    sal_max = (pay.get("max") or sal_min) if annual else None
    return {
        "title": raw.get("title") or "",
        "company": (raw.get("employer") or {}).get("name") or "",
        "url": raw.get("url") or raw.get("seoUrl") or "",
        "location": (raw.get("location") or {}).get("name") or "",
        "description": html_to_text(raw.get("description") or ""),
        "salary_min": int(sal_min) if sal_min else None,
        "salary_max": int(sal_max) if sal_max else None,
        "arrangement": None,
        # Glassdoor gives an age, not a date.
        "posted": ((datetime.now(timezone.utc) - timedelta(days=raw["ageInDays"])).date().isoformat()
                   if isinstance(raw.get("ageInDays"), int) else None),
    }


def _derived_location(raw: dict) -> str:
    """First entry of `locations_derived` (a string or a {city, admin, country} object), else `locations_alt`."""
    for loc in raw.get("locations_derived") or []:
        if isinstance(loc, str) and loc.strip():
            return loc.strip()
        if isinstance(loc, dict):
            parts = [loc.get(k) for k in ("city", "admin", "country") if loc.get(k)]
            if parts:
                return ", ".join(parts)
    alt = raw.get("locations_alt")
    if isinstance(alt, list):
        alt = ", ".join(str(a) for a in alt if a)
    return str(alt or "")


def _parse_career_site(raw: dict) -> dict:
    sal_min = sal_max = None
    if str(raw.get("ai_salary_unit_text") or "").upper() == "YEAR":
        sal_min = raw.get("ai_salary_min_value") or raw.get("ai_salary_value")
        sal_max = raw.get("ai_salary_max_value") or sal_min
    # "Remote OK" / "Remote Solely" / "Hybrid" / "On-site"
    arrangement = str(raw.get("ai_work_arrangement") or "")
    if arrangement.lower().startswith("remote"):
        arrangement = "remote"
    return {
        "title": raw.get("title") or "",
        "company": raw.get("organization") or "",
        "url": raw.get("url") or "",
        "location": _derived_location(raw),
        "description": raw.get("description_text") or "",
        "salary_min": int(sal_min) if sal_min else None,
        "salary_max": int(sal_max) if sal_max else None,
        "arrangement": arrangement or None,
        "posted": raw.get("date_posted"),
    }


_REMOTE_STATUS = {"REMOTE": REMOTE, "HYBRID": HYBRID, "ONSITE": ONSITE}


def _iso_date(ts) -> str | None:
    """Unix seconds -> "YYYY-MM-DD" (UTC); anything else -> None."""
    if not isinstance(ts, (int, float)) or ts <= 0:
        return None
    return datetime.fromtimestamp(ts, timezone.utc).date().isoformat()


def _parse_behance(raw: dict) -> dict:
    """Behance lists no salary on this actor's rows."""
    return {
        "title": raw.get("title") or "",
        "company": raw.get("companyName") or "",
        "url": raw.get("url") or "",
        "location": raw.get("locationDisplay") or "",
        "description": html_to_text(raw.get("description") or ""),
        "salary_min": None,
        "salary_max": None,
        "arrangement": _REMOTE_STATUS.get(str(raw.get("remoteStatus") or "").upper()),
        "posted": _iso_date(raw.get("postedOn")),
    }


def _hollylist_salary(raw: dict) -> tuple:
    """(min, max) of the first salary row that the posting gives per year in USD, else (None, None).
    Another currency stays in the description text, as on caribbeanjobs."""
    for s in raw.get("salaries") or []:
        if (isinstance(s, dict) and s.get("isOriginal") and str(s.get("period") or "").lower() == "year"
                and str(s.get("currency") or "").upper() == "USD"):
            lo, hi = s.get("min"), s.get("max")
            return (int(lo) if lo else None), (int(hi or lo) if (hi or lo) else None)
    return None, None


def _parse_hollylist(raw: dict) -> dict:
    loc = next((l for l in raw.get("locations") or [] if isinstance(l, dict)), {})
    sal_min, sal_max = _hollylist_salary(raw)
    work = next((w.get("type") for w in raw.get("workType") or [] if isinstance(w, dict)), None)
    return {
        "title": (raw.get("title") or "").strip(),
        "company": (raw.get("company") or {}).get("name") or "",
        "url": raw.get("url") or "",
        "location": ", ".join(p for p in (loc.get("city"), loc.get("region"), loc.get("countryCode")) if p),
        "description": (raw.get("description") or {}).get("text") or "",
        "salary_min": sal_min,
        "salary_max": sal_max,
        "arrangement": work if work in (REMOTE, HYBRID, ONSITE) else None,
        "posted": (raw.get("dates") or {}).get("posted"),
    }


@dataclass(frozen=True)
class Preset:
    actor: str                                   # "owner/name" as the Apify Store shows it
    label: str                                   # board name in the UI and in job source labels
    hint: str                                    # one line under the board picker: scope and posting-age steps
    build_input: Callable[[Search, int], dict]
    parse: Callable[[dict], dict]
    # USD per 1,000 results on the Free plan (the Store price when this was written);
    # feeds the per-run spend cap and the Test button's cost estimate.
    price_per_1k: float


def _career_site(ats: str, label: str) -> Preset:
    """A cross-company search on one ATS: same actor and parser, only the `ats` filter differs."""
    return Preset(
        "fantastic-jobs/career-site-job-listing-api", label,
        f"Every company that hires through {label}. Hours old rounds up to 1 h, 24 h, 7 days or 6 months.",
        _career_site_input(ats), _parse_career_site, 12.0)


PRESETS = {
    "apify_indeed": Preset(
        "misceres/indeed-scraper", "Indeed",
        "Indeed in the selected country. Hours old rounds up to 1, 3, 7 or 14 days; past 14 days, no age limit.",
        _indeed_input, _parse_indeed, 6.0),
    "apify_linkedin": Preset(
        "valig/linkedin-jobs-scraper", "LinkedIn",
        "LinkedIn public job search. Hours old is exact. LinkedIn ignores Remote without login, "
        "so Remote only drops the rows that the posting calls hybrid or on-site.",
        _linkedin_input, _parse_linkedin, 0.40),
    "apify_glassdoor": Preset(
        "valig/glassdoor-jobs-scraper", "Glassdoor",
        "Glassdoor, newest first. Hours old rounds up to whole days; empty means the last 30 days.",
        _glassdoor_input, _parse_glassdoor, 0.40),
    # Fallbacks for the creative mode's own Behance and Hollylist clients (sources/creative.py).
    "apify_behance": Preset(
        "piotrv1001/behance-jobs-scraper", "Behance",
        "Behance full-time and contract jobs; freelance briefs are not included. Hours old is not "
        "applied. Location matches the first city name. The actor has no remote filter, so Remote "
        "only drops the rows that Behance marks hybrid or on-site; Apify still bills them.",
        _behance_input, _parse_behance, 1.0),
    "apify_hollylist": Preset(
        "datawatcher/hollylist-scraper", "Hollylist",
        "Hollylist entertainment jobs, with full text. Members-only offers are skipped. Hours old "
        "is not applied. Location matches the first city name. Remote also returns on-site rows, "
        "so Remote drops the rows that the posting calls hybrid or on-site.",
        _hollylist_input, _parse_hollylist, 1.90),
    "apify_greenhouse": _career_site("greenhouse", "Greenhouse"),
    "apify_lever": _career_site("lever.co", "Lever"),
    "apify_ashby": _career_site("ashby", "Ashby"),
    "apify_workday": _career_site("workday", "Workday"),
}


def configured_presets(search: Search) -> list:
    """The preset keys of a search that this module knows, in their stored order."""
    return [s for s in (search.sources or []) if s in PRESETS]


def charge_cap_usd(preset: Preset, limit: int) -> float:
    """The maxTotalChargeUsd a run of `preset` for `limit` results is started with."""
    raw = limit * preset.price_per_1k / 1000 * _CHARGE_MARGIN
    cents = math.ceil(round(raw * 100, 6))     # whole cents, rounded up (float noise removed first)
    return min(_MAX_CHARGE_USD, max(_MIN_CHARGE_USD, cents / 100))


# ── Apify REST API ──────────────────────────────────────────────────────────

# Apify's error.type when the account plan may not run Store actors (the $1 Creator plan).
PLAN_BLOCKS_STORE = "public-actor-disabled"
_PLAN_BLOCKS_STORE_TEXT = ("the Apify plan of this key cannot run Apify Store actors (the Creator plan blocks them); "
                           "switch the account to the Free or a paid plan at https://console.apify.com/billing")


def _api_error(resp: httpx.Response) -> ApifyError:
    """One readable line per HTTP failure; Apify puts the reason in error.message and error.type."""
    try:
        err = resp.json().get("error") or {}
    except ValueError:
        err = {}
    if err.get("type") == PLAN_BLOCKS_STORE:
        return ApifyError(f"HTTP {resp.status_code}: {_PLAN_BLOCKS_STORE_TEXT}")
    message = err.get("message") or ""
    hint = {401: "the Apify API key is wrong or revoked",
            402: "the Apify account has no credit left",
            403: "the Apify API key cannot run this actor",
            404: "the actor or run does not exist"}.get(resp.status_code, "")
    if resp.status_code == 402 and message:
        # R30 S-17: a 402 is also a rented actor without a subscription, a monthly platform
        # limit or a charge cap below the actor's minimum; Apify's own message names which.
        hint = "Apify refused to charge for this run"
    text = "; ".join(t for t in (hint, message[:200]) if t)
    return ApifyError(f"HTTP {resp.status_code}" + (f": {text}" if text else ""))


async def _call(client: httpx.AsyncClient, method: str, path: str, **kw) -> dict:
    resp = await client.request(method, f"{API_BASE}{path}", **kw)
    if resp.status_code >= 400:
        raise _api_error(resp)
    return resp.json()


async def _run_actor(client: httpx.AsyncClient, actor: str, body: dict, limit: int,
                     max_charge_usd: float = _MAX_CHARGE_USD) -> list:
    """Start the actor, wait for it, return its dataset items (at most `limit`)."""
    # maxItems caps what a pay-per-result actor may charge for, whatever its input says;
    # maxTotalChargeUsd caps the money whatever the actor bills for; timeout makes the
    # platform end the run at our own deadline even if this process dies mid-poll.
    run = (await _call(client, "POST", f"/acts/{actor.replace('/', '~')}/runs",
                       params={"maxItems": limit, "maxTotalChargeUsd": max_charge_usd,
                               "timeout": _MAX_WAIT},
                       json=body))["data"]
    deadline = time.monotonic() + _MAX_WAIT
    while run.get("status") not in _TERMINAL:
        if time.monotonic() > deadline:
            try:
                await _call(client, "POST", f"/actor-runs/{run['id']}/abort")
            except (ApifyError, httpx.HTTPError) as e:
                logger.warning(f"Apify abort of run {run['id']} failed: {e}")
            raise ApifyError(f"run {run['id']} took longer than {_MAX_WAIT // 60} min and was aborted")
        run = (await _call(client, "GET", f"/actor-runs/{run['id']}",
                           params={"waitForFinish": _WAIT_STEP}))["data"]
    if run["status"] != "SUCCEEDED":
        detail = run.get("statusMessage") or ""
        raise ApifyError(f"run {run['id']} {run['status']}" + (f": {detail[:200]}" if detail else ""))
    resp = await client.get(f"{API_BASE}/datasets/{run['defaultDatasetId']}/items",
                            params={"clean": "true", "format": "json", "limit": limit})
    if resp.status_code >= 400:
        raise _api_error(resp)
    items = resp.json()
    return items if isinstance(items, list) else []


def _token() -> str:
    db = SessionLocal()
    try:
        token = (get_setting(db, TOKEN_SETTING) or "").strip()
    finally:
        db.close()
    if not token:
        raise ApifyError("the Apify API key is not set (Settings → Apify)")
    return token


def _client(token: str, read_timeout: float) -> httpx.AsyncClient:
    # The key goes in a header, never in the URL, so httpx errors and logs cannot show it.
    return httpx.AsyncClient(
        timeout=httpx.Timeout(30, read=read_timeout),
        headers={"Authorization": f"Bearer {token}", "User-Agent": "JobNavigator/1.0 (+apify source)"},
    )


# Caps on the plan probe, in case the platform starts a run for input that breaks the schema.
_PROBE_LIMITS = {"timeout": 1, "memory": 128, "maxTotalChargeUsd": 0.001}


async def account_name() -> str:
    """The Apify username of the stored key, once the key and its plan both work.

    GET /users/me proves the key. It cannot prove the plan: a Creator-plan key
    passes it and then has every board refused. So the first board's actor is
    started with an input that is not an object. A plan without Store access
    answers 403 PLAN_BLOCKS_STORE, any other plan 400 invalid-input; neither
    creates a run. Should a run start anyway, _PROBE_LIMITS bound it and it is
    aborted at once.
    """
    actor = next(iter(PRESETS.values())).actor.replace("/", "~")
    async with _client(_token(), 30) as client:
        data = (await _call(client, "GET", "/users/me"))["data"]
        resp = await client.post(f"{API_BASE}/acts/{actor}/runs", params=_PROBE_LIMITS, json=[])
        if resp.status_code == 201:
            run_id = (resp.json().get("data") or {}).get("id")
            logger.warning(f"Apify plan probe started run {run_id}; aborting it")
            if run_id:
                try:
                    await _call(client, "POST", f"/actor-runs/{run_id}/abort")
                except (ApifyError, httpx.HTTPError) as e:
                    logger.warning(f"Apify abort of probe run {run_id} failed: {e}")
        elif resp.status_code != 400:
            raise _api_error(resp)
    return data.get("username") or "?"


async def _collect(search: Search, limit: int) -> tuple[list, dict]:
    """Run every configured preset concurrently: (unique jobs, breakdown).

    A preset that fails writes `error` into its breakdown row and the others
    still save their jobs, the same contract the JobSpy boards follow.
    """
    keys = configured_presets(search)
    if not keys:
        raise ApifyError("no Apify board selected")
    # A status request is held open for _WAIT_STEP seconds, so the read timeout must exceed it.
    async with _client(_token(), _WAIT_STEP + 30) as client:
        outcomes = await asyncio.gather(
            *(_run_actor(client, PRESETS[k].actor, PRESETS[k].build_input(search, limit), limit,
                         charge_cap_usd(PRESETS[k], limit))
              for k in keys),
            return_exceptions=True,
        )

    breakdown, jobs, seen = {}, [], set()
    for key, outcome in zip(keys, outcomes):
        if isinstance(outcome, BaseException):
            # httpx errors can echo the request; ApifyError text is ours and key-free.
            msg = str(outcome) if isinstance(outcome, ApifyError) else type(outcome).__name__
            breakdown[key] = {"seen": 0, "new": 0, "error": msg}
            logger.warning(f"Apify {key} for '{search.name}' failed: {msg}")
            continue
        breakdown[key] = {"seen": 0, "new": 0, "returned": len(outcome)}
        for raw in outcome:
            j = PRESETS[key].parse(raw)
            j["source"] = key
            if not j["url"] or j["url"] in seen:
                continue
            seen.add(j["url"])
            jobs.append(j)
    return jobs, breakdown


# Boards that return on-site rows to a Remote-only search (see _linkedin_input,
# _behance_input; the Hollylist actor's workType filter let an on-site Boston row through).
_REMOTE_IGNORED = {"apify_linkedin", "apify_behance", "apify_hollylist"}


def _not_remote(j: dict) -> str | None:
    """The reason to drop a row that the work-arrangement cascade reads as hybrid or on-site
    only. A row that the cascade cannot read stays: the cascade never guesses, and a
    remote posting often says "remote" in words that no pattern matches."""
    found = extract_arrangement(j.get("location"), j.get("title"), j.get("description"),
                                j.get("arrangement"))["arrangements"]
    if not found or REMOTE in found:
        return None
    return "Not remote: " + ", ".join(v for v in (HYBRID, ONSITE) if v in found)


def _rejection(j: dict, include_kw, exclude_kw, global_ex: set, search_ex: set,
               company_filter=None, remote_only: bool = False) -> str | None:
    ok, reason = title_kept(j["title"], include_kw, exclude_kw)
    if not ok:
        return reason
    # The search's Company include (R30 S-06): the boards take no company parameter, so the
    # list narrows what they return, like JobSpy's apply_company_filter.
    ok, reason = company_included(j.get("company"), company_filter)
    if not ok:
        return reason
    company = (j.get("company") or "").lower()
    if company in global_ex:
        return f"Company excluded (global): {company}"
    if company in search_ex:
        return f"Company excluded: {company}"
    if remote_only and j.get("source") in _REMOTE_IGNORED:
        return _not_remote(j)
    return None


def _body_phrases(db) -> list:
    raw = get_setting(db, "body_exclusion_phrases")
    try:
        return json.loads(raw) if raw else []
    except json.JSONDecodeError:
        return []


def _all_failed(breakdown: dict) -> str | None:
    """The run-level error when no board answered, so the run is not recorded as a quiet day."""
    if breakdown and all(v.get("error") for v in breakdown.values()):
        # the board's label, not its key: "Indeed: HTTP 401 ..." reads as the run-history line
        return " · ".join(f"{PRESETS[k].label if k in PRESETS else k}: {v['error']}" for k, v in breakdown.items())
    return None


# ── Entry points ────────────────────────────────────────────────────────────

async def run(search: Search) -> dict:
    """Full scrape entry point. Fetch → filter → save to DB."""
    start = time.time()
    breakdown = {}
    try:
        unique, breakdown = await _collect(search, clamp_results(search.results_wanted))
        logger.info(f"apify '{search.name}': {len(unique)} jobs fetched")

        db = SessionLocal()
        new_jobs = kept = 0
        try:
            include_kw, exclude_kw = search_title_filters(search, db)
            global_ex, search_ex = build_search_exclude_sets(db, search)
            existing_ids = get_existing_external_ids(db)
            remote_only = search.is_remote is True

            # The loop below writes rows; H-1B lookups for the new jobs happen before it (S2-01).
            await prefetch_h1b([
                j.get("company") for j in unique
                if not _rejection(j, include_kw, exclude_kw, global_ex, search_ex,
                                  search.company_filter, remote_only)
                and make_external_id(j["company"], j["title"], j["url"]) not in existing_ids
            ])

            for j in unique:
                if _rejection(j, include_kw, exclude_kw, global_ex, search_ex,
                              search.company_filter, remote_only):
                    # Counted so the Run-history line says "N filtered out" instead of a bare "0 seen".
                    row = breakdown[j["source"]]
                    row["filtered"] = row.get("filtered", 0) + 1
                    continue
                kept += 1
                breakdown[j["source"]]["seen"] += 1
                ext_id = make_external_id(j["company"], j["title"], j["url"])
                if ext_id in existing_ids:
                    continue

                job = Job(
                    external_id=ext_id,
                    content_hash=make_content_hash(j["company"], j["title"]),
                    company=j["company"],
                    title=j["title"],
                    url=j["url"],
                    source=j["source"],             # the board key, already "apify_<board>"
                    search_id=search.id,
                    location=j.get("location") or None,
                    description=j.get("description") or None,
                    status="new",
                    seen=False,
                    saved=False,
                )
                # Structured annual salary first, so the JD extractor in analyze_inline keeps it.
                if j.get("salary_min"):
                    job.salary_min = j["salary_min"]
                    job.salary_max = j.get("salary_max") or j["salary_min"]
                    job.salary_source = "posting"

                try:
                    await analyze_inline(job, db=db, arrangement=j.get("arrangement"))
                except Exception as e:
                    logger.warning(f"apify inline analysis failed for {j['title']}: {e}")
                if job.h1b_jd_flag:
                    logger.info(f"Skipping (body exclusion): {j['title']} @ {j.get('company', '?')}")
                    continue

                try:
                    with db.begin_nested():
                        db.add(job)
                        db.flush()
                    new_jobs += counts_as_new(job)
                    existing_ids.add(ext_id)
                    breakdown[j["source"]]["new"] += 1
                except IntegrityError:
                    logger.debug(f"Duplicate external_id for '{j['title']}' @ {j.get('company')}, skipping")
                except Exception as e:
                    logger.warning(f"Insert failed for '{j['title']}' @ {j.get('company')} ({j['url']}): {e}")

            search_obj = db.query(Search).filter(Search.id == search.id).first()
            if search_obj:
                search_obj.last_run_at = datetime.now(timezone.utc)
            db.commit()
        finally:
            db.close()

        duration = time.time() - start
        from backend.activity import log_activity
        log_activity("scrape", f"apify '{search.name}': {new_jobs} new / {kept} kept in {duration:.1f}s")
        return {"jobs_found": kept, "new_jobs": new_jobs, "error": _all_failed(breakdown),
                "duration": duration, "source_breakdown": breakdown}

    except Exception as e:
        duration = time.time() - start
        msg = str(e) if isinstance(e, ApifyError) else f"{type(e).__name__}: {e}"
        logger.error(f"apify scrape failed for '{search.name}': {msg}")
        from backend.activity import log_activity
        log_activity("scrape", f"apify '{search.name}' failed: {msg}")
        return {"jobs_found": 0, "new_jobs": 0, "error": msg, "duration": duration,
                "source_breakdown": breakdown}


async def preview(search: Search, db) -> dict:
    """Dry run: fetch at most PREVIEW_LIMIT jobs per board, apply filters, save nothing."""
    start = time.time()
    config = {
        "mode": "apify",
        "search_term": search.search_term or "",
        "sources": configured_presets(search),
        "results_wanted": PREVIEW_LIMIT,
    }
    try:
        unique, breakdown = await _collect(search, PREVIEW_LIMIT)
        include_kw, exclude_kw = search_title_filters(search, db)
        global_ex, search_ex = build_search_exclude_sets(db, search)
        phrases = _body_phrases(db)
        remote_only = search.is_remote is True

        from collections import Counter
        from backend.analyzer.h1b_checker import scan_jd_for_h1b_flags
        results = []
        for j in unique:
            reason = _rejection(j, include_kw, exclude_kw, global_ex, search_ex,
                                search.company_filter, remote_only)
            # run() drops these through analyze_inline; the preview names the phrase.
            if reason is None and phrases and j.get("description"):
                hit = scan_jd_for_h1b_flags(j["description"], phrases)
                if hit["jd_flag"]:
                    reason = f"Body exclusion: {(hit['jd_snippet'] or 'matched')[:80]}"
            salary = None
            if j.get("salary_min"):
                salary = f"{j['salary_min']:,}"
                if j.get("salary_max") and j["salary_max"] != j["salary_min"]:
                    salary += f" – {j['salary_max']:,}"
            desc = j.get("description") or ""
            results.append({
                "title": j["title"],
                "company": j.get("company", ""),
                "url": j["url"],
                "source": j["source"],
                "location": j.get("location", ""),
                "salary": salary,
                "has_description": len(desc) > 50,
                "desc_length": len(desc),
                "kept": reason is None,
                "reason": reason,
                "posted": j.get("posted"),
            })

        # Same shape as the keyword preview: counts per board, failures apart.
        return {
            "search_name": search.name,
            "duration": round(time.time() - start, 1),
            "raw_count": len(unique),
            "after_filter": sum(1 for r in results if r["kept"]),
            "source_breakdown": {k: v.get("returned", 0) for k, v in breakdown.items() if not v.get("error")},
            "source_errors": {k: v["error"] for k, v in breakdown.items() if v.get("error")},
            "company_breakdown": dict(Counter(j["company"] for j in unique if j.get("company")).most_common(20)),
            "include_keywords": include_kw,
            "exclude_keywords": exclude_kw,
            "company_filter": search.company_filter or [],
            "company_exclude": list(global_ex | search_ex),
            "jobs": results,
            "config": config,
        }
    except Exception as e:
        msg = str(e) if isinstance(e, ApifyError) else f"{type(e).__name__}: {e}"
        return {"search_name": search.name, "error": msg,
                "duration": round(time.time() - start, 1), "config": config}
