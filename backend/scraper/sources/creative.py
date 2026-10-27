"""Creative boards source: Behance, Hollylist, Wana Create, Himalayas, Eluta, Dribbble, ArtStation
and Work With Indies, read from each site's own JSON API or feed.

No login, no browser, no Apify key. A search picks boards in `sources`, the way a keyword
search picks JobSpy boards; each board writes its own row into `source_breakdown`, and its
key ("behance", "hollylist", "wanacreate", "himalayas", "eluta") is the stored Job.source. The
Apify mode has paid fallbacks for two of them (apify_behance, apify_hollylist).

| board      | listing                                   | description                         |
| ---------- | ----------------------------------------- | ----------------------------------- |
| behance    | GraphQL combinedJobListings, 50 per page  | one GraphQL query per new job       |
| hollylist  | GraphQL getJobs, US and Europe markets    | one GraphQL query per new job       |
| wanacreate | Typesense search with its public key      | in the listing                      |
| himalayas  | documented public JSON API, 20 per page   | in the listing                      |
| eluta      | RSS, 20 per page, one request per 3 s     | job page microdata, per new job     |
| dribbble   | keyword RSS, ~50 newest                   | job page JSON-LD, per new job       |
| artstation | public jobs JSON, 100 per page            | in the listing                      |
| workwithindies | RSS, 100 newest, no search            | job page JSON-LD, per new job       |

What each board applies itself: Remote on Behance, Hollylist and Wana Create (Himalayas is
remote only; Eluta has no remote filter); Location on Hollylist (inside a market), Wana Create
(exact city name) and Eluta (city, 50 km). Dribbble, ArtStation and Work With Indies take no
Location, so _rejection keeps their rows in the city or remote; ArtStation filters Remote itself.
For every board, Remote drops a row the posting calls on-site or hybrid. Hours old is applied by
Wana Create and checked here for the others (listing date; Behance: detail date).

Behance answers the first request with a cookie challenge (`js_challenge_value`, set by an
inline script) and checks a double-submit token: the same random value in the `bcp` cookie
and the `X-BCP` header. Hollylist hides members-only offers (no company, no text, no apply
link); they are dropped. Detail queries run only for rows that pass the filters and are not
stored yet, so a scheduled run reads a few pages; a Test reads at most PREVIEW_DETAIL_LIMIT.
"""
import asyncio
import html
import json
import logging
import re
import ssl
import time
import uuid
import weakref
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Awaitable, Callable, Optional

import httpx
from sqlalchemy.exc import IntegrityError

from backend.accounts.settings import get_setting
from backend.analyzer.work_arrangement import HYBRID, ONSITE, REMOTE
from backend.models.db import SessionLocal, Job, Search, get_existing_external_ids
from backend.scraper._shared.analysis import analyze_inline, prefetch_h1b
from backend.scraper._shared.dedup import make_external_id, make_content_hash
from backend.scraper._shared.filters import (build_search_exclude_sets, company_included,
                                             search_title_filters, title_kept)
from backend.scraper._shared.html_text import html_to_text
from backend.countries import normalize_country, split_country_suffix, supported_countries

logger = logging.getLogger("jobnavigator.creative")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/130.0 Safari/537.36")
MAX_RESULTS = 500                # results_wanted per board, the UI's bound
PREVIEW_LIMIT = 20               # listing rows per board on Test
PREVIEW_DETAIL_LIMIT = 20        # detail queries per Test, all boards together
_DETAIL_CONCURRENCY = 3
_ARRANGEMENT = {"REMOTE": REMOTE, "HYBRID": HYBRID, "ONSITE": ONSITE}


class CreativeError(Exception):
    """A board failure the run history shows as is."""


def clamp_results(value) -> int:
    try:
        n = int(value) if value is not None else 50
    except (TypeError, ValueError):
        n = 50
    return min(MAX_RESULTS, max(1, n))


def _city(search: Search) -> str:
    """"Los Angeles, CA, United States" -> "Los Angeles"."""
    return split_country_suffix(search.location or "")[0].split(",")[0].strip()


def _term(search: Search) -> str:
    return (search.search_term or "").strip()


def _iso_from_ts(ts) -> Optional[str]:
    if not isinstance(ts, (int, float)) or ts <= 0:
        return None
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


def _annual_usd(lo, hi, period, currency) -> tuple:
    """(min, max) of a yearly USD salary, else (None, None). Another currency stays in the
    text, as on caribbeanjobs. A posting can label an hourly rate yearly ("15-20"), so a
    yearly figure below 1,000 is not taken."""
    if (str(currency or "").upper() != "USD" or str(period or "").upper() not in ("ANNUAL", "YEARLY")
            or not isinstance(lo, (int, float)) or lo < 1000):
        return None, None
    return int(lo), int(hi if isinstance(hi, (int, float)) and hi >= lo else lo)


def _row(**kw) -> dict:
    base = {"title": "", "company": "", "url": "", "location": "", "description": "",
            "salary_min": None, "salary_max": None, "arrangement": None, "posted": None, "ref": None}
    base.update(kw)
    base["title"] = " ".join((base["title"] or "").split())
    return base


async def _gql(client: httpx.AsyncClient, url: str, query: str, variables: dict, headers=None) -> dict:
    resp = await client.post(url, json={"query": query, "variables": variables}, headers=headers)
    if resp.status_code >= 400:
        raise CreativeError(f"HTTP {resp.status_code} from {url}")
    body = resp.json()
    if body.get("errors"):
        raise CreativeError("GraphQL: " + "; ".join(str(e.get("message"))[:160] for e in body["errors"][:2]))
    return body.get("data") or {}


# ── Behance ─────────────────────────────────────────────────────────────────

_BEHANCE = "https://www.behance.net"
_BEHANCE_PAGE = 50               # the API returns at most 50 nodes per page
_BEHANCE_LIST = """query L($query: query, $first: Int, $page: Int, $filter: CombinedJobListingFilter) {
  combinedJobListings(query: $query, first: $first, page: $page, filter: $filter) {
    nodes { id oid jobType title companyName url remoteStatus isRemote location locations { displayName } }
    pageInfo { hasNextPage }
  }
}"""
_BEHANCE_DETAIL = """query D($oid: JobOID, $briefId: Int!, $isBrief: Boolean!) {
  job(oid: $oid) @skip(if: $isBrief) {
    description postedOn company { name } salaryMin salaryMax salaryTimeframe salaryCurrency
  }
  freelanceBriefPublicInfo(id: $briefId) @include(if: $isBrief) {
    description deliverables candidateInfo additionalDetails company isClosed
  }
}"""


async def _behance_headers(client: httpx.AsyncClient) -> dict:
    """Pass the cookie challenge once per client and return the GraphQL headers."""
    resp = await client.get(f"{_BEHANCE}/joblist")
    m = re.search(r"js_challenge_value=([0-9a-f]+)", resp.text)
    if m:
        client.cookies.set("js_challenge_value", m.group(1), domain="www.behance.net")
        resp = await client.get(f"{_BEHANCE}/joblist")
    if resp.status_code >= 400:
        raise CreativeError(f"HTTP {resp.status_code}: Behance refused the job list page")
    token = str(uuid.uuid4())
    client.cookies.set("bcp", token, domain=".behance.net")
    return {"X-BCP": token, "X-Requested-With": "XMLHttpRequest",
            "Origin": _BEHANCE, "Referer": f"{_BEHANCE}/joblist"}


async def _behance_list(client: httpx.AsyncClient, search: Search, limit: int) -> list:
    headers = await _behance_headers(client)
    variables = {"query": _term(search), "first": _BEHANCE_PAGE}
    if search.is_remote:
        variables["filter"] = {"remoteStatus": "REMOTE"}
    rows, page = [], 1
    while len(rows) < limit:
        data = await _gql(client, f"{_BEHANCE}/v3/graphql", _BEHANCE_LIST, dict(variables, page=page), headers)
        conn = data.get("combinedJobListings") or {}
        for n in conn.get("nodes") or []:
            places = [l.get("displayName") for l in n.get("locations") or [] if l.get("displayName")]
            status = str(n.get("remoteStatus") or ("REMOTE" if n.get("isRemote") else "")).upper()
            rows.append(_row(
                title=n.get("title"), company=n.get("companyName") or "", url=n.get("url") or "",
                location="; ".join(places) or n.get("location") or ("Remote" if status == "REMOTE" else ""),
                arrangement=_ARRANGEMENT.get(status),
                ref={"headers": headers, "oid": n.get("oid"), "id": n.get("id"),
                     "brief": n.get("jobType") == "FREELANCE"}))
        if not (conn.get("pageInfo") or {}).get("hasNextPage"):
            break
        page += 1
    return rows[:limit]


def _behance_text(*parts) -> str:
    """Brief fields that the API masks for visitors come back as "####"."""
    return "\n\n".join(html_to_text(p) for p in parts if p and p.strip("# \n"))


async def _behance_detail(client: httpx.AsyncClient, row: dict) -> None:
    ref = row["ref"]
    data = await _gql(client, f"{_BEHANCE}/v3/graphql", _BEHANCE_DETAIL,
                      {"oid": None if ref["brief"] else ref["oid"], "briefId": ref["id"] if ref["brief"] else 0,
                       "isBrief": ref["brief"]}, ref["headers"])
    if ref["brief"]:
        b = data.get("freelanceBriefPublicInfo") or {}
        row["description"] = _behance_text(b.get("description"), b.get("deliverables"),
                                            b.get("candidateInfo"), b.get("additionalDetails"))
        row["company"] = row["company"] or (b.get("company") or "")
        return
    j = data.get("job") or {}
    row["description"] = html_to_text(j.get("description") or "")
    row["company"] = row["company"] or ((j.get("company") or {}).get("name") or "")
    row["posted"] = _iso_from_ts(j.get("postedOn"))
    row["salary_min"], row["salary_max"] = _annual_usd(j.get("salaryMin"), j.get("salaryMax"),
                                                       j.get("salaryTimeframe"), j.get("salaryCurrency"))


# ── Hollylist ───────────────────────────────────────────────────────────────

_HOLLYLIST = "https://www.hollylist.com"
_HOLLYLIST_PAGE = 100
_HOLLYLIST_MARKETS = (None, "europe")     # None is the US listing (hollylist.com/jobs)
_HOLLYLIST_LIST = """query($skip: Int, $limit: Int, $term: String, $loc: String, $market: String, $remote: Boolean) {
  getJobs(searchTerm: $term, location: $loc, radius: 20, isRemote: $remote, market: $market, skip: $skip, limit: $limit) {
    jobs { _id slugUrl title organization isPublic dateAdded location { name } }
  }
}"""
_HOLLYLIST_DETAIL = """query($slug: String) {
  getJob(slug: $slug) { descMark isRemote }
}"""


async def _hollylist_market(client: httpx.AsyncClient, search: Search, market, limit: int) -> list:
    variables = {"term": _term(search) or None, "loc": _city(search) or None, "market": market,
                 "remote": True if search.is_remote else None, "limit": _HOLLYLIST_PAGE}
    rows, skip = [], 0
    while len(rows) < limit:
        data = await _gql(client, f"{_HOLLYLIST}/graphql", _HOLLYLIST_LIST, dict(variables, skip=skip))
        jobs = (data.get("getJobs") or {}).get("jobs") or []
        for j in jobs:
            if not j.get("isPublic") or not j.get("slugUrl"):
                continue             # members-only: no company, no text, no apply link
            rows.append(_row(
                title=j.get("title"), company=j.get("organization") or "",
                url=f"{_HOLLYLIST}/job/{j['slugUrl']}",     # redirects to the market's own path
                location=(j.get("location") or {}).get("name") or "", posted=j.get("dateAdded"),
                ref={"slug": j["slugUrl"]}))
        if len(jobs) < _HOLLYLIST_PAGE:
            break
        skip += _HOLLYLIST_PAGE
    return rows[:limit]


async def _hollylist_list(client: httpx.AsyncClient, search: Search, limit: int) -> list:
    """Both markets, newest first. A Location belongs to one market; the other returns nothing."""
    found = await asyncio.gather(*(_hollylist_market(client, search, m, limit) for m in _HOLLYLIST_MARKETS))
    rows = sorted((r for market in found for r in market), key=lambda r: r["posted"] or "", reverse=True)
    return rows[:limit]


async def _hollylist_detail(client: httpx.AsyncClient, row: dict) -> None:
    j = (await _gql(client, f"{_HOLLYLIST}/graphql", _HOLLYLIST_DETAIL, {"slug": row["ref"]["slug"]})).get("getJob") or {}
    # Pay is a bare rate without a currency across two markets; the JD extractor reads the text.
    row["description"] = html_to_text(j.get("descMark") or "")
    if j.get("isRemote"):
        row["arrangement"] = REMOTE


# ── Wana Create ─────────────────────────────────────────────────────────────

_WANA_CONFIG = "https://wana-api-server-prod.onrender.com/api/v1/typesense/config"
_WANA_PAGE = 100
_WANA_JOB = "https://www.wanacreate.art/jobs/"


def _wana_filter(search: Search) -> str:
    parts = []
    if search.is_remote:
        parts.append("workType:=REMOTE")
    city = _city(search)
    if city and not search.is_remote:
        parts.append(f"location.city:=`{city.replace('`', '')}`")
    if search.hours_old:
        parts.append(f"createdAt_ts:>{int(time.time()) - int(search.hours_old) * 3600}")
    return " && ".join(parts)


def _wana_row(doc: dict) -> dict:
    sal = doc.get("salary") or {}
    sal_min, sal_max = _annual_usd(sal.get("min"), sal.get("max"), sal.get("period"), sal.get("currency"))
    loc = doc.get("location") or {}
    link = doc.get("jobLink") or ""
    return _row(
        title=doc.get("title"), company=(doc.get("company") or {}).get("name") or "",
        # The original posting when Wana Create copied it from another board, so it dedups with that board's row.
        url=link if link.startswith("http") else f"{_WANA_JOB}{doc.get('id')}",
        location=loc.get("name") or loc.get("city") or "",
        description=html_to_text(doc.get("description") or ""),
        salary_min=sal_min, salary_max=sal_max,
        arrangement=_ARRANGEMENT.get(str(doc.get("workType") or "").upper()),
        posted=doc.get("createdAt"))


async def _wana_list(client: httpx.AsyncClient, search: Search, limit: int) -> list:
    # The site's own config call hands every visitor this search-only key; the API host
    # sleeps when idle, so the first answer can take most of a minute.
    cfg = (await client.get(_WANA_CONFIG, timeout=90)).json()
    key, endpoint = cfg.get("api_key"), (cfg.get("endpoint") or "").rstrip("/")
    if not key or not endpoint.startswith("https://"):
        raise CreativeError("Wana Create sent no search key")
    params = {"q": _term(search) or "*", "query_by": "title,keywords", "sort_by": "createdAt_ts:desc",
              "per_page": _WANA_PAGE, "prefix": "false"}
    filt = _wana_filter(search)
    if filt:
        params["filter_by"] = filt
    rows, page = [], 1
    while len(rows) < limit:
        resp = await client.get(f"{endpoint}/collections/jobs/documents/search",
                                params=dict(params, page=page), headers={"X-TYPESENSE-API-KEY": key})
        if resp.status_code >= 400:
            raise CreativeError(f"HTTP {resp.status_code} from the Wana Create search")
        body = resp.json()
        hits = body.get("hits") or []
        rows += [_wana_row(h.get("document") or {}) for h in hits]
        if not hits or page * _WANA_PAGE >= (body.get("found") or 0):
            break
        page += 1
    return rows[:limit]


# ── Himalayas ───────────────────────────────────────────────────────────────

_HIMALAYAS_SEARCH = "https://himalayas.app/jobs/api/search"
_HIMALAYAS_PAGE = 20            # fixed by the API
_HIMALAYAS_MAX_PAGES = 25


def _himalayas_row(j: dict) -> dict:
    places = [p for p in j.get("locationRestrictions") or [] if p]
    period = "ANNUAL" if str(j.get("salaryPeriod") or "").lower() == "annual" else j.get("salaryPeriod")
    sal_min, sal_max = _annual_usd(j.get("minSalary"), j.get("maxSalary"), period, j.get("currency"))
    return _row(
        title=j.get("title"), company=j.get("companyName") or "",
        # The API terms ask to send applicants through applicationLink.
        url=j.get("applicationLink") or j.get("guid") or "",
        location="Remote: " + ", ".join(places) if places else "Remote (worldwide)",
        description=html_to_text(j.get("description") or ""),
        salary_min=sal_min, salary_max=sal_max, arrangement=REMOTE,
        posted=_iso_from_ts(j.get("pubDate")))


def _country_name(search: Search) -> str:
    """"canada" -> "Canada": the search's Country as the English name; "" when unknown."""
    return dict(supported_countries()).get(normalize_country(getattr(search, "country", None)) or "", "")


async def _himalayas_list(client: httpx.AsyncClient, search: Search, limit: int) -> list:
    """A remote-only board: every job is remote, so Remote and Location do not narrow it.
    Country keeps the jobs open to that country, worldwide ones included (the API takes the
    English name). Results come newest first, so paging stops at the first job older than
    Hours old."""
    params = {"q": _term(search), "sort": "recent"}
    country = _country_name(search)
    if country:
        params["country"] = country
    rows = []
    for page in range(1, _HIMALAYAS_MAX_PAGES + 1):
        resp = await client.get(_HIMALAYAS_SEARCH, params=dict(params, page=page))
        if resp.status_code >= 400:
            raise CreativeError(f"HTTP {resp.status_code} from the Himalayas API")
        jobs = resp.json().get("jobs") or []
        batch = [_himalayas_row(j) for j in jobs]
        fresh = [r for r in batch if not _too_old(r, search.hours_old)]
        rows += fresh
        if len(jobs) < _HIMALAYAS_PAGE or len(fresh) < len(batch) or len(rows) >= limit:
            break
    return rows[:limit]


# ── Eluta ───────────────────────────────────────────────────────────────────

_ELUTA = "https://www.eluta.ca"
# Eluta refuses with a one-item feed: "Too Many Requests" after a burst, and "Too Many Feeds"
# once an address checks more than 10 RSS feeds a day ("You may only check a maximum of 10
# RSS feeds each day", 2026-10-26). So one run reads one feed page and at most 6 job pages,
# one request every _ELUTA_GAP seconds, and an Eluta search should run once a day.
_ELUTA_MAX_PAGES = 1            # 20 items per RSS page
_ELUTA_MAX_DETAILS = 6
_ELUTA_GAP = 3.0
_ELUTA_RADIUS_KM = 50
_eluta_pace_state: "weakref.WeakKeyDictionary" = weakref.WeakKeyDictionary()


def _eluta_tls() -> ssl.SSLContext:
    """www.eluta.ca offers only TLS 1.2 with RSA key exchange (AES128-GCM-SHA256), which
    OpenSSL 3.5 no longer offers by default (handshake failure, measured 2026-10-26). This
    context adds those ciphers for that host only."""
    ctx = ssl.create_default_context()
    ctx.set_ciphers("DEFAULT:AES128-GCM-SHA256:AES256-GCM-SHA384")
    return ctx


async def _eluta_get(client: httpx.AsyncClient, url: str, params=None) -> httpx.Response:
    """One Eluta request at a time per event loop, _ELUTA_GAP apart."""
    loop = asyncio.get_running_loop()
    lock, last = _eluta_pace_state.setdefault(loop, (asyncio.Lock(), [0.0]))
    async with lock:
        wait = last[0] + _ELUTA_GAP - time.monotonic()
        if wait > 0:
            await asyncio.sleep(wait)
        try:
            return await client.get(url, params=params)
        finally:
            last[0] = time.monotonic()


def _eluta_items(xml_text: bytes) -> list:
    """The feed's items; a refusal comes as one item titled "Too Many …" that links to /contact."""
    items = ET.fromstring(xml_text).findall("./channel/item")
    if len(items) == 1:
        title = (items[0].findtext("title") or "").strip()
        if title.startswith("Too Many") or (items[0].findtext("link") or "").rstrip("/").endswith("/contact"):
            reason = " ".join((items[0].findtext("description") or "").split())[:160]
            raise CreativeError(f"Eluta answered {title}" + (f": {reason}" if reason else ""))
    return items


def _eluta_row(it) -> dict:
    try:
        posted = parsedate_to_datetime(it.findtext("pubDate") or "").isoformat()
    except (TypeError, ValueError):
        posted = None
    return _row(
        title=it.findtext("title"), company=(it.findtext("employer") or "").strip(),
        url=(it.findtext("link") or "").split("?")[0], location=(it.findtext("location") or "").strip(),
        description=html_to_text(it.findtext("description") or ""),   # a snippet until the detail fills it
        posted=posted)


async def _eluta_list(client: httpx.AsyncClient, search: Search, limit: int) -> list:
    """Canadian jobs from employer career sites. The search is full text over the posting, so
    the title filter does the narrowing. Location is a city with a 50 km radius; without one
    the search covers Canada. Eluta has no remote filter."""
    city = split_country_suffix(search.location or "")[0].strip()
    q = f"{_term(search)} sort:post" + (f" radius:{_ELUTA_RADIUS_KM}" if city else "")
    rows = []
    for page in range(1, _ELUTA_MAX_PAGES + 1):
        resp = await _eluta_get(client, f"{_ELUTA}/rss", {"q": q, "l": city, "pg": page})
        if resp.status_code >= 400:
            raise CreativeError(f"HTTP {resp.status_code} from the Eluta feed")
        try:
            items = _eluta_items(resp.content)
        except CreativeError:
            if rows:
                break               # keep what the earlier pages gave
            raise
        batch = [_eluta_row(it) for it in items]
        fresh = [r for r in batch if not _too_old(r, search.hours_old)]
        rows += fresh
        if len(items) < 20 or len(fresh) < len(batch) or len(rows) >= limit:
            break
    return rows[:limit]


async def _eluta_detail(client: httpx.AsyncClient, row: dict) -> None:
    """The job page carries schema.org JobPosting microdata; its description replaces the snippet."""
    resp = await _eluta_get(client, row["url"])
    if resp.status_code >= 400:
        raise CreativeError(f"HTTP {resp.status_code} from {row['url']}")
    from bs4 import BeautifulSoup
    page = BeautifulSoup(resp.text, "html.parser")
    # The hiring organisation has its own empty <meta itemprop="description"> before the
    # posting's <div itemprop="description">, so take the longest element that holds text.
    texts = [html_to_text(str(el)) for el in page.select('[itemtype*="JobPosting"] [itemprop="description"]')
             if el.name != "meta"]
    text = max(texts, key=len, default="")
    if text:
        row["description"] = text


# ── JSON-LD job pages (Dribbble, Work With Indies) ──────────────────────────

def _fix_escapes(text: str) -> str:
    """Double every backslash that does not start a valid JSON escape, reading pairs left to
    right so an escaped backslash (\\\\) stays one escape."""
    return re.sub(r"\\(.)", lambda m: m.group(0) if m.group(1) in '"\\/bfnrtu' else "\\\\" + m.group(1),
                  text, flags=re.S)


def _jobposting_ld(html_text: str) -> dict:
    """The first schema.org JobPosting in the page's JSON-LD blocks, or {}. Work With Indies
    writes invalid escapes such as `\\_blank`; a block that fails is parsed again with those
    backslashes doubled."""
    for block in re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', html_text, re.S):
        try:
            data = json.loads(block, strict=False)
        except ValueError:
            try:
                data = json.loads(_fix_escapes(block), strict=False)
            except ValueError:
                continue
        for item in data if isinstance(data, list) else [data]:
            if isinstance(item, dict) and "JobPosting" in str(item.get("@type")):
                return item
    return {}


def _ld_place(ld: dict) -> str:
    places = ld.get("jobLocation") or []
    out = []
    for p in places if isinstance(places, list) else [places]:
        addr = (p or {}).get("address") or {}
        parts = [addr.get(k) for k in ("addressLocality", "addressRegion", "addressCountry")]
        out.append(", ".join(dict.fromkeys(x for x in parts if x and x != "null")))
    return "; ".join(x for x in out if x)


def _apply_ld(row: dict, ld: dict) -> None:
    """Description, place and remote flag from a JobPosting; a field the page lacks keeps the feed's value."""
    text = html_to_text(html.unescape(ld.get("description") or ""))
    if text:
        row["description"] = text
    if str(ld.get("jobLocationType") or "").upper() == "TELECOMMUTE":
        row["arrangement"] = REMOTE
        where = (ld.get("applicantLocationRequirements") or {})
        where = where.get("name") if isinstance(where, dict) else ""
        row["location"] = f"Remote: {where}" if where else (row["location"] or "Remote")
    elif _ld_place(ld):
        row["location"] = _ld_place(ld)
    row["company"] = row["company"] or ((ld.get("hiringOrganization") or {}).get("name") or "")


async def _ld_detail(client: httpx.AsyncClient, row: dict) -> None:
    resp = await client.get(row["url"])
    if resp.status_code >= 400:
        raise CreativeError(f"HTTP {resp.status_code} from {row['url']}")
    _apply_ld(row, _jobposting_ld(resp.text))


def _rss_date(text) -> Optional[str]:
    try:
        return parsedate_to_datetime(text or "").isoformat()
    except (TypeError, ValueError):
        return None


# ── Dribbble ────────────────────────────────────────────────────────────────

_DRIBBBLE_RSS = "https://dribbble.com/jobs.rss"
_DRIBBBLE_TITLE = re.compile(r"^(?P<company>.*?) is hiring for a position of (?P<title>.*?)(?: in (?P<place>.*))?$")
_REMOTE_WORDS = re.compile(r"\b(remote|anywhere|worldwide)\b", re.I)


async def _dribbble_list(client: httpx.AsyncClient, search: Search, limit: int) -> list:
    """The keyword feed (about 50 newest). The feed item has no text; the job page's JSON-LD has it."""
    resp = await client.get(_DRIBBBLE_RSS, params={"keyword": _term(search)})
    if resp.status_code >= 400:
        raise CreativeError(f"HTTP {resp.status_code} from the Dribbble feed")
    rows = []
    for it in ET.fromstring(resp.content).findall("./channel/item"):
        m = _DRIBBBLE_TITLE.match(" ".join((it.findtext("title") or "").split()))
        title, place = (m.group("title"), m.group("place") or "") if m else (it.findtext("title"), "")
        rows.append(_row(
            title=title, company=it.findtext("{http://purl.org/dc/elements/1.1/}creator") or (m.group("company") if m else ""),
            url=(it.findtext("link") or "").split("?")[0], location=place,
            arrangement=REMOTE if _REMOTE_WORDS.search(place) else None, posted=_rss_date(it.findtext("pubDate"))))
    return rows[:limit]


# ── ArtStation ──────────────────────────────────────────────────────────────

_ARTSTATION_JOBS = "https://www.artstation.com/api/v2/jobs/public/jobs.json"
_ARTSTATION_PAGE = 100


def _artstation_row(j: dict) -> dict:
    places = [((l or {}).get("locality") or {}).get("formatted_name") for l in j.get("recruitment_localities") or []]
    places = [p for p in places if p]
    text = "\n\n".join(t for t in (html_to_text(j.get("description") or ""), html_to_text(j.get("how_to_apply") or "")) if t)
    remote = bool(j.get("work_remotely"))
    return _row(
        title=j.get("title"), company=j.get("company_name") or "",
        url=f"https://www.artstation.com/jobs/{j.get('hash_id')}" if j.get("hash_id") else "",
        location=("Remote: " if remote else "") + "; ".join(places) if places else ("Remote" if remote else ""),
        description=text, arrangement=REMOTE if remote else None,
        posted=(j.get("listing_placement") or {}).get("posted_at") or j.get("created_at"))


async def _artstation_list(client: httpx.AsyncClient, search: Search, limit: int) -> list:
    """The whole board is about 100 jobs, two pages; `query` and `work_remotely` narrow it.
    Location is checked here against the job's localities."""
    params = {"per_page": _ARTSTATION_PAGE, "query": _term(search)}
    if search.is_remote:
        params["work_remotely"] = "true"
    rows = []
    for page in range(1, 6):
        resp = await client.get(_ARTSTATION_JOBS, params=dict(params, page=page))
        if resp.status_code >= 400:
            raise CreativeError(f"HTTP {resp.status_code} from the ArtStation jobs API")
        jobs = resp.json().get("data") or []
        rows += [_artstation_row(j) for j in jobs]
        if len(jobs) < _ARTSTATION_PAGE or len(rows) >= limit:
            break
    return rows[:limit]


# ── Work With Indies ────────────────────────────────────────────────────────

_WWI_RSS = "https://www.workwithindies.com/careers/rss.xml"
_WWI_TITLE = re.compile(r"^(?P<company>.*?) is hiring an? (?P<title>.*?)(?: to work (?P<place>.*))?$")


async def _wwi_list(client: httpx.AsyncClient, search: Search, limit: int) -> list:
    """The 100 newest indie game jobs; the feed takes no search, so the title filter narrows it."""
    resp = await client.get(_WWI_RSS)
    if resp.status_code >= 400:
        raise CreativeError(f"HTTP {resp.status_code} from the Work With Indies feed")
    rows = []
    for it in ET.fromstring(resp.content).findall("./channel/item"):
        m = _WWI_TITLE.match(" ".join((it.findtext("title") or "").split()))
        place = (m.group("place") or "") if m else ""
        rows.append(_row(
            title=m.group("title") if m else it.findtext("title"), company=m.group("company") if m else "",
            url=it.findtext("link") or "", location=place,
            description=html_to_text(it.findtext("description") or ""),
            # "to work from CET ± 3 hours": a time-zone band is a remote job
            arrangement=REMOTE if _REMOTE_WORDS.search(place) or place.lower().startswith("from ") else None,
            posted=_rss_date(it.findtext("pubDate"))))
    return rows[:limit]


# ── boards ──────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Board:
    label: str
    listing: Callable[[httpx.AsyncClient, Search, int], Awaitable[list]]
    detail: Optional[Callable[[httpx.AsyncClient, dict], Awaitable[None]]] = None
    # Detail requests one run may make; the new rows past it wait for the next run, unsaved,
    # so each is stored with its full text. None = no cap.
    max_details: Optional[int] = None
    # The board cannot filter by city, so _rejection drops the rows outside the search's
    # Location (remote rows stay).
    local_city: bool = False


BOARDS = {
    "behance": Board("Behance", _behance_list, _behance_detail),
    "hollylist": Board("Hollylist", _hollylist_list, _hollylist_detail),
    "wanacreate": Board("Wana Create", _wana_list),
    "himalayas": Board("Himalayas", _himalayas_list),
    "eluta": Board("Eluta", _eluta_list, _eluta_detail, max_details=_ELUTA_MAX_DETAILS),
    "dribbble": Board("Dribbble", _dribbble_list, _ld_detail, local_city=True),
    "artstation": Board("ArtStation", _artstation_list, local_city=True),
    "workwithindies": Board("Work With Indies", _wwi_list, _ld_detail, local_city=True),
}


def _defer_over_budget(fresh: list, breakdown: dict) -> list:
    """The new rows this run reads, with each board's max_details respected; the rest are
    counted as `deferred` in the board's breakdown row and left for a later run."""
    out, used = [], {}
    for r in fresh:
        cap = BOARDS[r["source"]].max_details
        if cap is not None and used.get(r["source"], 0) >= cap:
            breakdown[r["source"]]["deferred"] = breakdown[r["source"]].get("deferred", 0) + 1
            continue
        used[r["source"]] = used.get(r["source"], 0) + 1
        out.append(r)
    return out


def configured_boards(search: Search) -> list:
    return [s for s in (search.sources or []) if s in BOARDS]


def _client() -> httpx.AsyncClient:
    # Eluta's TLS context applies to its host only; every other host keeps the default one.
    return httpx.AsyncClient(timeout=httpx.Timeout(30), follow_redirects=True,
                             headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"},
                             mounts={_ELUTA: httpx.AsyncHTTPTransport(verify=_eluta_tls())})


def _error_text(e: BaseException) -> str:
    return str(e) if isinstance(e, CreativeError) else f"{type(e).__name__}: {e}"[:200]


async def _collect(client: httpx.AsyncClient, search: Search, limit: int) -> tuple[list, dict]:
    """Every configured board concurrently: (unique rows, breakdown). A failed board writes
    `error` into its breakdown row and the others still count."""
    keys = configured_boards(search)
    if not keys:
        raise CreativeError("no creative board selected")
    outcomes = await asyncio.gather(*(BOARDS[k].listing(client, search, limit) for k in keys),
                                    return_exceptions=True)
    breakdown, rows, seen = {}, [], set()
    for key, outcome in zip(keys, outcomes):
        if isinstance(outcome, BaseException):
            breakdown[key] = {"seen": 0, "new": 0, "error": _error_text(outcome)}
            logger.warning(f"creative {key} for '{search.name}' failed: {breakdown[key]['error']}")
            continue
        breakdown[key] = {"seen": 0, "new": 0, "returned": len(outcome)}
        for r in outcome:
            r["source"] = key
            if r["url"] and r["title"] and r["url"] not in seen:
                seen.add(r["url"])
                rows.append(r)
    return rows, breakdown


async def _fill_details(client: httpx.AsyncClient, rows: list) -> None:
    """Run the board's detail query for each row that needs one. A row whose query fails
    keeps its listing fields and gets `detail_error`."""
    sem = asyncio.Semaphore(_DETAIL_CONCURRENCY)

    async def one(r):
        detail = BOARDS[r["source"]].detail
        if detail is None:
            return
        async with sem:
            try:
                await detail(client, r)
            except Exception as e:
                r["detail_error"] = _error_text(e)
                logger.warning(f"creative {r['source']} detail failed for {r['url']}: {r['detail_error']}")
    await asyncio.gather(*(one(r) for r in rows))


def _too_old(r: dict, hours_old) -> Optional[str]:
    if not hours_old or not r.get("posted"):
        return None
    try:
        posted = datetime.fromisoformat(str(r["posted"]).replace("Z", "+00:00"))
    except ValueError:
        return None
    if posted.tzinfo is None:
        posted = posted.replace(tzinfo=timezone.utc)
    age_h = (datetime.now(timezone.utc) - posted).total_seconds() / 3600
    return f"Older than {hours_old} h" if age_h > hours_old else None


_OPEN_EVERYWHERE = re.compile(r"\b(anywhere|worldwide)\b", re.I)
_BEHANCE_COUNTRY_NAMES = {"United States": ("united states", "usa")}   # Behance writes "CA, USA"


def _behance_not_open_to(r: dict, country: str) -> Optional[str]:
    """A remote Behance job lists the countries it hires from ("Spain; Portugal; Italy").
    It is open to `country` when the list is empty or says Anywhere / Worldwide, or names
    the country in full: "CA" alone is California in "CA, USA"."""
    loc = (r.get("location") or "").lower()
    names = _BEHANCE_COUNTRY_NAMES.get(country, (country.lower(),))
    if not country or loc in ("", "remote") or _OPEN_EVERYWHERE.search(loc) or any(n in loc for n in names):
        return None
    return f"Not open to {country}"


def _rejection(r: dict, search: Search, include_kw, exclude_kw, global_ex: set, search_ex: set) -> Optional[str]:
    ok, reason = title_kept(r["title"], include_kw, exclude_kw)
    if not ok:
        return reason
    ok, reason = company_included(r.get("company"), search.company_filter)
    if not ok:
        return reason
    company = (r.get("company") or "").lower()
    if company and company in global_ex:
        return f"Company excluded (global): {company}"
    if company and company in search_ex:
        return f"Company excluded: {company}"
    # Boards that cannot filter Remote or Location themselves: drop only what the posting
    # itself contradicts; a row the posting says nothing about stays.
    if search.is_remote and r.get("arrangement") in (ONSITE, HYBRID):
        return f"Not remote: {r['arrangement']}"
    if search.is_remote and r.get("source") == "behance":
        reason = _behance_not_open_to(r, _country_name(search))
        if reason:
            return reason
    city = _city(search)
    board = BOARDS.get(r.get("source"))
    if (board and board.local_city and city and r.get("arrangement") != REMOTE
            and city.lower() not in (r.get("location") or "").lower()):
        return f"Not in {city}"
    return _too_old(r, search.hours_old)


def _all_failed(breakdown: dict) -> Optional[str]:
    if breakdown and all(v.get("error") for v in breakdown.values()):
        return " · ".join(f"{BOARDS[k].label if k in BOARDS else k}: {v['error']}" for k, v in breakdown.items())
    return None


# ── entry points ────────────────────────────────────────────────────────────

async def run(search: Search) -> dict:
    """Full scrape: list → filter → details for new rows → filter by date again → save."""
    start = time.time()
    breakdown = {}
    try:
        db = SessionLocal()
        new_jobs = kept = 0
        try:
            include_kw, exclude_kw = search_title_filters(search, db)
            global_ex, search_ex = build_search_exclude_sets(db, search)
            existing_ids = get_existing_external_ids(db)
            async with _client() as client:
                rows, breakdown = await _collect(client, search, clamp_results(search.results_wanted))

                def bump(r, field):
                    breakdown[r["source"]][field] = breakdown[r["source"]].get(field, 0) + 1

                fresh = []
                for r in rows:
                    if _rejection(r, search, include_kw, exclude_kw, global_ex, search_ex):
                        bump(r, "filtered")
                        continue
                    kept += 1
                    bump(r, "seen")
                    if make_external_id(r["company"], r["title"], r["url"]) not in existing_ids:
                        fresh.append(r)
                fresh = _defer_over_budget(fresh, breakdown)
                await _fill_details(client, fresh)
            # Behance dates and company names arrive with the detail query.
            late = [r for r in fresh if _rejection(r, search, include_kw, exclude_kw, global_ex, search_ex)]
            for r in late:
                kept -= 1
                breakdown[r["source"]]["seen"] -= 1
                bump(r, "filtered")
            late_ids = {id(r) for r in late}
            fresh = [r for r in fresh if id(r) not in late_ids]
            await prefetch_h1b([r.get("company") for r in fresh])

            for r in fresh:
                ext_id = make_external_id(r["company"], r["title"], r["url"])
                if ext_id in existing_ids:
                    continue
                job = Job(external_id=ext_id, content_hash=make_content_hash(r["company"], r["title"]),
                          company=r["company"], title=r["title"], url=r["url"], source=r["source"],
                          search_id=search.id, location=r.get("location") or None,
                          description=r.get("description") or None, status="new", seen=False, saved=False)
                if r.get("salary_min"):
                    job.salary_min = r["salary_min"]
                    job.salary_max = r.get("salary_max") or r["salary_min"]
                    job.salary_source = "posting"
                try:
                    await analyze_inline(job, db=db, arrangement=r.get("arrangement"))
                except Exception as e:
                    logger.warning(f"creative inline analysis failed for {r['title']}: {e}")
                if job.h1b_jd_flag:
                    logger.info(f"Skipping (body exclusion): {r['title']} @ {r.get('company') or '?'}")
                    continue
                try:
                    with db.begin_nested():
                        db.add(job)
                        db.flush()
                    new_jobs += 1
                    existing_ids.add(ext_id)
                    breakdown[r["source"]]["new"] += 1
                except IntegrityError:
                    logger.debug(f"Duplicate external_id for '{r['title']}' @ {r.get('company')}, skipping")
                except Exception as e:
                    logger.warning(f"Insert failed for '{r['title']}' @ {r.get('company')} ({r['url']}): {e}")

            search_obj = db.query(Search).filter(Search.id == search.id).first()
            if search_obj:
                search_obj.last_run_at = datetime.now(timezone.utc)
            db.commit()
        finally:
            db.close()

        duration = time.time() - start
        from backend.activity import log_activity
        log_activity("scrape", f"creative '{search.name}': {new_jobs} new / {kept} kept in {duration:.1f}s")
        return {"jobs_found": kept, "new_jobs": new_jobs, "error": _all_failed(breakdown),
                "duration": duration, "source_breakdown": breakdown}
    except Exception as e:
        duration = time.time() - start
        msg = _error_text(e)
        logger.error(f"creative scrape failed for '{search.name}': {msg}")
        from backend.activity import log_activity
        log_activity("scrape", f"creative '{search.name}' failed: {msg}")
        return {"jobs_found": 0, "new_jobs": 0, "error": msg, "duration": duration,
                "source_breakdown": breakdown}


def _body_phrases(db) -> list:
    raw = get_setting(db, "body_exclusion_phrases")
    try:
        return json.loads(raw) if raw else []
    except json.JSONDecodeError:
        return []


async def preview(search: Search, db) -> dict:
    """Dry run: PREVIEW_LIMIT listing rows per board, details for the first kept rows, nothing saved."""
    start = time.time()
    config = {"mode": "creative", "search_term": search.search_term or "",
              "sources": configured_boards(search), "results_wanted": PREVIEW_LIMIT}
    try:
        include_kw, exclude_kw = search_title_filters(search, db)
        global_ex, search_ex = build_search_exclude_sets(db, search)
        async with _client() as client:
            rows, breakdown = await _collect(client, search, PREVIEW_LIMIT)
            reasons = [_rejection(r, search, include_kw, exclude_kw, global_ex, search_ex) for r in rows]
            sampled = _defer_over_budget([r for r, why in zip(rows, reasons) if why is None],
                                         breakdown)[:PREVIEW_DETAIL_LIMIT]
            await _fill_details(client, sampled)
        sampled_ids = {id(r) for r in sampled}
        phrases = _body_phrases(db)

        from collections import Counter
        from backend.analyzer.h1b_checker import scan_jd_for_h1b_flags
        results = []
        for r, reason in zip(rows, reasons):
            if reason is None and id(r) in sampled_ids:
                reason = _rejection(r, search, include_kw, exclude_kw, global_ex, search_ex)
            if reason is None and phrases and r.get("description"):
                hit = scan_jd_for_h1b_flags(r["description"], phrases)
                if hit["jd_flag"]:
                    reason = f"Body exclusion: {(hit['jd_snippet'] or 'matched')[:80]}"
            salary = None
            if r.get("salary_min"):
                salary = f"{r['salary_min']:,}"
                if r.get("salary_max") and r["salary_max"] != r["salary_min"]:
                    salary += f" – {r['salary_max']:,}"
            desc = r.get("description") or ""
            results.append({
                "title": r["title"], "company": r.get("company", ""), "url": r["url"],
                "source": r["source"], "location": r.get("location", ""), "salary": salary,
                "has_description": len(desc) > 50, "desc_length": len(desc),
                "kept": reason is None, "reason": reason, "posted": r.get("posted"),
            })
        return {
            "search_name": search.name,
            "duration": round(time.time() - start, 1),
            "raw_count": len(rows),
            "after_filter": sum(1 for x in results if x["kept"]),
            "source_breakdown": {k: v.get("returned", 0) for k, v in breakdown.items() if not v.get("error")},
            "source_errors": {k: v["error"] for k, v in breakdown.items() if v.get("error")},
            "company_breakdown": dict(Counter(r["company"] for r in rows if r.get("company")).most_common(20)),
            "include_keywords": include_kw,
            "exclude_keywords": exclude_kw,
            "company_filter": search.company_filter or [],
            "company_exclude": list(global_ex | search_ex),
            "jobs": results,
            "config": config,
        }
    except Exception as e:
        return {"search_name": search.name, "error": _error_text(e),
                "duration": round(time.time() - start, 1), "config": config}
