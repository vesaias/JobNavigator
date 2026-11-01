"""Creative boards source: Behance, Hollylist, Wana Create, Dribbble, ArtStation and Work With
Indies, read from each site's own JSON API or feed through the job_boards.py pipeline. A search
picks boards in `sources`, the way a keyword search picks JobSpy boards, and each board's key
("behance", "hollylist", "wanacreate", ...) is the stored Job.source. The Apify mode has paid
fallbacks for two of them (apify_behance, apify_hollylist).

| board      | listing                                   | description                         |
| ---------- | ----------------------------------------- | ----------------------------------- |
| behance    | GraphQL combinedJobListings, 50 per page  | one GraphQL query per new job       |
| hollylist  | GraphQL getJobs, US and Europe markets    | one GraphQL query per new job       |
| wanacreate | Typesense search with its public key      | in the listing                      |
| dribbble   | keyword RSS, ~50 newest                   | job page JSON-LD, per new job       |
| artstation | public jobs JSON, 100 per page            | in the listing                      |
| workwithindies | RSS, 100 newest, no search            | job page JSON-LD, per new job       |

Where each board names the employer's apply link, and what a row without one means (the
meaning of `apply_url` and `easy_apply` is in job_boards.py):

| board      | employer's link                  | without it                                      |
| ---------- | -------------------------------- | ----------------------------------------------- |
| behance    | applicationUrl in the detail     | its /joblist/apply/ page or a brief: on the board |
| hollylist  | applyAt in the detail            | no applyAt: on the board                        |
| wanacreate | jobLink, stored as the job's url | no jobLink: on the board                        |
| dribbble   | /apply_now redirects to it       | no redirect: Board link                         |
| artstation | apply_link in the listing        | an e-mail in how_to_apply: Board link           |
| workwithindies | the page's Apply button      | an e-mail, or LinkedIn: Board link              |

What each board applies itself: Remote on Behance, Hollylist and Wana Create; Location on Hollylist
(inside a market) and Wana Create (exact city name). Dribbble, ArtStation and Work With Indies take
no Location, so job_boards._rejection keeps their rows in the city or remote; ArtStation filters
Remote itself. For every board, Remote drops a row the posting calls on-site or hybrid. Hours old
is applied by Wana Create and checked in the pipeline for the others (listing date; Behance:
detail date).

Behance answers the first request with a cookie challenge (`js_challenge_value`, set by an
inline script) and checks a double-submit token: the same random value in the `bcp` cookie
and the `X-BCP` header. Hollylist hides members-only offers (no company, no text, no apply
link); they are dropped.
"""
import asyncio
import html
import json
import re
import time
import uuid
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from typing import Optional

import httpx

from backend.analyzer.work_arrangement import HYBRID, ONSITE, REMOTE
from backend.models.db import Search
from backend.scraper._shared import job_boards
from backend.scraper._shared.html_text import html_to_text
from backend.scraper._shared.job_boards import (Board, BoardError, annual_usd, city_of, country_name,
                                                employer_apply, iso_from_ts, make_row, term_of)
from backend.scraper._shared.urls import host_matches

_ARRANGEMENT = {"REMOTE": REMOTE, "HYBRID": HYBRID, "ONSITE": ONSITE}


async def _gql(client: httpx.AsyncClient, url: str, query: str, variables: dict, headers=None) -> dict:
    resp = await client.post(url, json={"query": query, "variables": variables}, headers=headers)
    if resp.status_code >= 400:
        raise BoardError(f"HTTP {resp.status_code} from {url}")
    body = resp.json()
    if body.get("errors"):
        raise BoardError("GraphQL: " + "; ".join(str(e.get("message"))[:160] for e in body["errors"][:2]))
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
    description postedOn applicationUrl company { name } salaryMin salaryMax salaryTimeframe salaryCurrency
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
        raise BoardError(f"HTTP {resp.status_code}: Behance refused the job list page")
    token = str(uuid.uuid4())
    client.cookies.set("bcp", token, domain=".behance.net")
    return {"X-BCP": token, "X-Requested-With": "XMLHttpRequest",
            "Origin": _BEHANCE, "Referer": f"{_BEHANCE}/joblist"}


async def _behance_list(client: httpx.AsyncClient, search: Search, limit: int) -> list:
    headers = await _behance_headers(client)
    variables = {"query": term_of(search), "first": _BEHANCE_PAGE}
    if search.is_remote:
        variables["filter"] = {"remoteStatus": "REMOTE"}
    rows, page = [], 1
    while len(rows) < limit:
        data = await _gql(client, f"{_BEHANCE}/v3/graphql", _BEHANCE_LIST, dict(variables, page=page), headers)
        conn = data.get("combinedJobListings") or {}
        for n in conn.get("nodes") or []:
            places = [l.get("displayName") for l in n.get("locations") or [] if l.get("displayName")]
            status = str(n.get("remoteStatus") or ("REMOTE" if n.get("isRemote") else "")).upper()
            rows.append(make_row(
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
        row["easy_apply"] = True     # a brief is answered on Behance
        return
    j = data.get("job") or {}
    row["description"] = html_to_text(j.get("description") or "")
    row["company"] = row["company"] or ((j.get("company") or {}).get("name") or "")
    row["posted"] = iso_from_ts(j.get("postedOn"))
    link = j.get("applicationUrl")
    row["apply_url"] = employer_apply(link)
    row["easy_apply"] = bool(link) and host_matches(link, "behance.net")
    row["salary_min"], row["salary_max"] = annual_usd(j.get("salaryMin"), j.get("salaryMax"),
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
  getJob(slug: $slug) { descMark isRemote applyAt }
}"""


async def _hollylist_market(client: httpx.AsyncClient, search: Search, market, limit: int) -> list:
    variables = {"term": term_of(search) or None, "loc": city_of(search) or None, "market": market,
                 "remote": True if search.is_remote else None, "limit": _HOLLYLIST_PAGE}
    rows, skip = [], 0
    while len(rows) < limit:
        data = await _gql(client, f"{_HOLLYLIST}/graphql", _HOLLYLIST_LIST, dict(variables, skip=skip))
        jobs = (data.get("getJobs") or {}).get("jobs") or []
        for j in jobs:
            if not j.get("isPublic") or not j.get("slugUrl"):
                continue             # members-only: no company, no text, no apply link
            rows.append(make_row(
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
    link = j.get("applyAt") or ""
    row["apply_url"] = employer_apply(link)
    row["easy_apply"] = bool(j) and (not link or host_matches(link, "hollylist.com"))


# ── Wana Create ─────────────────────────────────────────────────────────────

_WANA_CONFIG = "https://wana-api-server-prod.onrender.com/api/v1/typesense/config"
_WANA_PAGE = 100
_WANA_JOB = "https://www.wanacreate.art/jobs/"


def _wana_filter(search: Search) -> str:
    parts = []
    if search.is_remote:
        parts.append("workType:=REMOTE")
    city = city_of(search)
    if city and not search.is_remote:
        parts.append(f"location.city:=`{city.replace('`', '')}`")
    if search.hours_old:
        parts.append(f"createdAt_ts:>{int(time.time()) - int(search.hours_old) * 3600}")
    return " && ".join(parts)


def _wana_row(doc: dict) -> dict:
    sal = doc.get("salary") or {}
    sal_min, sal_max = annual_usd(sal.get("min"), sal.get("max"), sal.get("period"), sal.get("currency"))
    loc = doc.get("location") or {}
    link = doc.get("jobLink") or ""
    return make_row(
        title=doc.get("title"), company=(doc.get("company") or {}).get("name") or "",
        # The original posting when Wana Create copied it from another board, so it dedups with that board's row.
        url=link if link.startswith("http") else f"{_WANA_JOB}{doc.get('id')}",
        location=loc.get("name") or loc.get("city") or "",
        description=html_to_text(doc.get("description") or ""),
        salary_min=sal_min, salary_max=sal_max,
        arrangement=_ARRANGEMENT.get(str(doc.get("workType") or "").upper()),
        posted=doc.get("createdAt"), easy_apply=not link)


async def _wana_list(client: httpx.AsyncClient, search: Search, limit: int) -> list:
    # The site's own config call hands every visitor this search-only key; the API host
    # sleeps when idle, so the first answer can take most of a minute.
    cfg = (await client.get(_WANA_CONFIG, timeout=90)).json()
    key, endpoint = cfg.get("api_key"), (cfg.get("endpoint") or "").rstrip("/")
    if not key or not endpoint.startswith("https://"):
        raise BoardError("Wana Create sent no search key")
    params = {"q": term_of(search) or "*", "query_by": "title,keywords", "sort_by": "createdAt_ts:desc",
              "per_page": _WANA_PAGE, "prefix": "false"}
    filt = _wana_filter(search)
    if filt:
        params["filter_by"] = filt
    rows, page = [], 1
    while len(rows) < limit:
        resp = await client.get(f"{endpoint}/collections/jobs/documents/search",
                                params=dict(params, page=page), headers={"X-TYPESENSE-API-KEY": key})
        if resp.status_code >= 400:
            raise BoardError(f"HTTP {resp.status_code} from the Wana Create search")
        body = resp.json()
        hits = body.get("hits") or []
        rows += [_wana_row(h.get("document") or {}) for h in hits]
        if not hits or page * _WANA_PAGE >= (body.get("found") or 0):
            break
        page += 1
    return rows[:limit]


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


async def _ld_detail(client: httpx.AsyncClient, row: dict) -> str:
    """Fill `row` from the job page and return the page."""
    resp = await client.get(row["url"])
    if resp.status_code >= 400:
        raise BoardError(f"HTTP {resp.status_code} from {row['url']}")
    _apply_ld(row, _jobposting_ld(resp.text))
    return resp.text


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
    resp = await client.get(_DRIBBBLE_RSS, params={"keyword": term_of(search)})
    if resp.status_code >= 400:
        raise BoardError(f"HTTP {resp.status_code} from the Dribbble feed")
    rows = []
    for it in ET.fromstring(resp.content).findall("./channel/item"):
        m = _DRIBBBLE_TITLE.match(" ".join((it.findtext("title") or "").split()))
        title, place = (m.group("title"), m.group("place") or "") if m else (it.findtext("title"), "")
        rows.append(make_row(
            title=title, company=it.findtext("{http://purl.org/dc/elements/1.1/}creator") or (m.group("company") if m else ""),
            url=(it.findtext("link") or "").split("?")[0], location=place,
            arrangement=REMOTE if _REMOTE_WORDS.search(place) else None, posted=_rss_date(it.findtext("pubDate"))))
    return rows[:limit]


async def _dribbble_detail(client: httpx.AsyncClient, row: dict) -> None:
    """The JSON-LD names no apply link; the page's Apply button, /apply_now, redirects to it."""
    await _ld_detail(client, row)
    resp = await client.get(f"{row['url']}/apply_now", follow_redirects=False)
    row["apply_url"] = employer_apply(resp.headers.get("location"))


# ── ArtStation ──────────────────────────────────────────────────────────────

_ARTSTATION_JOBS = "https://www.artstation.com/api/v2/jobs/public/jobs.json"
_ARTSTATION_PAGE = 100


def _artstation_row(j: dict) -> dict:
    places = [((l or {}).get("locality") or {}).get("formatted_name") for l in j.get("recruitment_localities") or []]
    places = [p for p in places if p]
    text = "\n\n".join(t for t in (html_to_text(j.get("description") or ""), html_to_text(j.get("how_to_apply") or "")) if t)
    remote = bool(j.get("work_remotely"))
    return make_row(
        title=j.get("title"), company=j.get("company_name") or "",
        url=f"https://www.artstation.com/jobs/{j.get('hash_id')}" if j.get("hash_id") else "",
        location=("Remote: " if remote else "") + "; ".join(places) if places else ("Remote" if remote else ""),
        description=text, arrangement=REMOTE if remote else None,
        apply_url=employer_apply(j.get("apply_link")),      # else how_to_apply gives an e-mail address
        posted=(j.get("listing_placement") or {}).get("posted_at") or j.get("created_at"))


async def _artstation_list(client: httpx.AsyncClient, search: Search, limit: int) -> list:
    """The whole board is about 100 jobs, two pages; `query` and `work_remotely` narrow it.
    Location is checked here against the job's localities."""
    params = {"per_page": _ARTSTATION_PAGE, "query": term_of(search)}
    if search.is_remote:
        params["work_remotely"] = "true"
    rows = []
    for page in range(1, 6):
        resp = await client.get(_ARTSTATION_JOBS, params=dict(params, page=page))
        if resp.status_code >= 400:
            raise BoardError(f"HTTP {resp.status_code} from the ArtStation jobs API")
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
        raise BoardError(f"HTTP {resp.status_code} from the Work With Indies feed")
    rows = []
    for it in ET.fromstring(resp.content).findall("./channel/item"):
        m = _WWI_TITLE.match(" ".join((it.findtext("title") or "").split()))
        place = (m.group("place") or "") if m else ""
        rows.append(make_row(
            title=m.group("title") if m else it.findtext("title"), company=m.group("company") if m else "",
            url=it.findtext("link") or "", location=place,
            description=html_to_text(it.findtext("description") or ""),
            # "to work from CET ± 3 hours": a time-zone band is a remote job
            arrangement=REMOTE if _REMOTE_WORDS.search(place) or place.lower().startswith("from ") else None,
            posted=_rss_date(it.findtext("pubDate"))))
    return rows[:limit]


async def _wwi_detail(client: httpx.AsyncClient, row: dict) -> None:
    """The JSON-LD names no apply link; the page's Apply button holds a link or a mailto:."""
    page = await _ld_detail(client, row)
    button = re.search(r'<a\b[^>]*\bid="apply-top"[^>]*>', page)
    href = re.search(r'\bhref="([^"]*)"', button.group(0)) if button else None
    row["apply_url"] = employer_apply(html.unescape(href.group(1))) if href else None


# ── boards ──────────────────────────────────────────────────────────────────

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


def _behance_check(r: dict, search: Search) -> Optional[str]:
    return _behance_not_open_to(r, country_name(search)) if search.is_remote else None


BOARDS = {
    "behance": Board("Behance", _behance_list, _behance_detail, check=_behance_check),
    "hollylist": Board("Hollylist", _hollylist_list, _hollylist_detail),
    "wanacreate": Board("Wana Create", _wana_list),
    "dribbble": Board("Dribbble", _dribbble_list, _dribbble_detail, local_city=True),
    "artstation": Board("ArtStation", _artstation_list, local_city=True),
    "workwithindies": Board("Work With Indies", _wwi_list, _wwi_detail, local_city=True),
}


def _picked(search: Search) -> dict:
    return {s: BOARDS[s] for s in (search.sources or []) if s in BOARDS}


async def run(search: Search) -> dict:
    return await job_boards.run(search, _picked(search))


async def preview(search: Search, db) -> dict:
    return await job_boards.preview(search, db, _picked(search))
