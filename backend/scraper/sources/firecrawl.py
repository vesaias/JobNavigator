"""Firecrawl source: postings on employers' own job boards (Greenhouse, Lever, Ashby, Workable),
found with the Firecrawl Search API and read with its Scrape API.

One search request per run looks for the search term on those job-board hosts, newest first when
Hours old is set; a new job that passes the filters gets its page read once, as markdown. The
links are the employers' own postings, so each job is Direct and joins the same posting from a
company scrape (postings.py already reads all four hosts).

Each run costs Firecrawl credits on the key in Settings › Firecrawl: 2 per 10 search results and
1 per job page read. Only new jobs that pass the filters are read, and Test reads at most
PREVIEW_DETAIL_LIMIT pages.
"""
import logging
import re
import unicodedata
from typing import Optional
from urllib.parse import urlsplit

import httpx

from backend.accounts.settings import get_setting
from backend.models.db import SessionLocal, Search
from backend.scraper._shared import job_boards
from backend.scraper._shared.job_boards import Board, BoardError, city_of, country_name, make_row, term_of

logger = logging.getLogger("jobnavigator.firecrawl")

API_BASE = "https://api.firecrawl.dev/v2"
KEY_SETTING = "firecrawl_api_key"
ORIGIN = "jobnavigator"
MAX_RESULTS = 100           # the Search API's limit per request
PREVIEW_DETAIL_LIMIT = job_boards.PREVIEW_DETAIL_LIMIT
HOSTS = ("job-boards.greenhouse.io", "boards.greenhouse.io", "jobs.lever.co", "jobs.ashbyhq.com",
         "apply.workable.com")
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
_HEADING = re.compile(r"^#{1,3}\s+(.+?)\s*$", re.M)


def _key() -> str:
    db = SessionLocal()
    try:
        key = (get_setting(db, KEY_SETTING) or "").strip()
    finally:
        db.close()
    if not key:
        raise BoardError("the Firecrawl API key is not set (Settings → Firecrawl)")
    return key


def _tbs(hours_old) -> Optional[str]:
    """Hours old as the Search API's time filter: the smallest window that holds it."""
    if not hours_old:
        return None
    for limit, tbs in ((1, "qdr:h"), (24, "qdr:d"), (168, "qdr:w"), (744, "qdr:m")):
        if hours_old <= limit:
            return tbs
    return "qdr:y"


def _query(search: Search) -> str:
    term = term_of(search)
    bits = [term if '"' in term else f'"{term}"']
    city = city_of(search)
    if city:
        bits.append(city)
    if search.is_remote:
        bits.append("remote")
    bits.append("(" + " OR ".join(f"site:{h}" for h in HOSTS) + ")")
    return " ".join(bits)


def _slug_company(url: str) -> str:
    """The board slug as a name: jobs.lever.co/freedom-pay/… -> "Freedom Pay"; "" for an id."""
    parts = [p for p in urlsplit(url).path.split("/") if p]
    if not parts or _UUID.fullmatch(parts[0]) or parts[0].isdigit():
        return ""
    return " ".join(w.capitalize() for w in re.split(r"[-_]+", parts[0]) if w)


def _split_title(text: str, url: str) -> tuple[str, str]:
    """(title, company) from a page title, as each job board writes it; company "" when it
    does not say."""
    text = " ".join((text or "").split())
    m = re.fullmatch(r"Job Application for (.+) at (.+)", text)
    if m:
        return m.group(1), m.group(2)
    m = re.fullmatch(r"(.+) @ (.+)", text)
    if m:
        return m.group(1), m.group(2)
    m = re.fullmatch(r"(.+?) Careers \| (.+)", text)
    if m:
        return m.group(2), m.group(1)
    host = urlsplit(url).hostname
    if host in ("jobs.lever.co", "apply.workable.com") and " - " in text:
        # Lever pages say "Company - Title" and Workable pages "Title - Company", and search
        # results use either order: the end that matches the board slug is the company.
        slug = _squash(([p for p in urlsplit(url).path.split("/") if p] or [""])[0])
        first, rest = text.split(" - ", 1)
        head, last = text.rsplit(" - ", 1)
        if _is_slug(last, slug):
            return head, last
        if _is_slug(first, slug) or host == "jobs.lever.co":
            return rest, first
    return text, ""


def _squash(name: str) -> str:
    """"Zūm" -> "zum": letters and digits only, accents dropped, as a board slug spells them."""
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", name).lower())


def _is_slug(name: str, slug: str) -> bool:
    """"Isla" is the board "islacare", "Fuse Energy" the board "fuseenergy"."""
    name = _squash(name)
    return bool(name and slug) and (slug.startswith(name) or name.startswith(slug))


def _row(result: dict) -> dict:
    url = result.get("url") or ""
    title, company = _split_title(result.get("title") or "", url)
    title = title.removesuffix("...").removesuffix("…").strip()
    # A company read from the board slug ("Fuseenergy") gives way to the page's own name.
    return make_row(title=title, company=company or _slug_company(url), url=url, slug_company=not company)


def _api_error(resp: httpx.Response) -> BoardError:
    try:
        detail = str(resp.json().get("error") or "")[:200]
    except ValueError:
        detail = ""
    if resp.status_code == 401:
        return BoardError("Firecrawl rejected the API key (Settings → Firecrawl)")
    if resp.status_code == 402:
        return BoardError("the Firecrawl account has no credits left" + (f": {detail}" if detail else ""))
    if resp.status_code == 429:
        return BoardError("Firecrawl rate limit reached; the next run tries again")
    return BoardError(f"HTTP {resp.status_code} from the Firecrawl API" + (f": {detail}" if detail else ""))


def _on_a_board(url: str) -> bool:
    host = urlsplit(url).hostname or ""
    return host in HOSTS and len([p for p in urlsplit(url).path.split("/") if p]) >= 2


async def _list(client: httpx.AsyncClient, search: Search, limit: int) -> list:
    """One search request; only links to a single posting on one of HOSTS are kept."""
    body = {"query": _query(search), "limit": min(limit, MAX_RESULTS), "sources": ["web"], "origin": ORIGIN}
    tbs = _tbs(search.hours_old)
    if tbs:
        body["tbs"] = tbs
    country = country_name(search)
    if country:
        body["location"] = country
    resp = await client.post(f"{API_BASE}/search", json=body, headers={"Authorization": f"Bearer {_key()}"},
                             timeout=httpx.Timeout(60))
    if resp.status_code >= 400:
        raise _api_error(resp)
    data = resp.json().get("data") or {}
    results = data.get("web") if isinstance(data, dict) else data
    return [_row(r) for r in results or [] if _on_a_board(r.get("url") or "")]


async def _detail(client: httpx.AsyncClient, r: dict) -> None:
    """The posting's page as markdown. Its first heading completes a title the search result
    cut short or trims one it padded ("… Job Available, United States"), and the page title
    names the company when the listing did not."""
    resp = await client.post(f"{API_BASE}/scrape", headers={"Authorization": f"Bearer {_key()}"},
                             json={"url": r["url"], "formats": ["markdown"], "onlyMainContent": True,
                                   "origin": ORIGIN},
                             timeout=httpx.Timeout(90))
    if resp.status_code >= 400:
        raise _api_error(resp)
    data = resp.json().get("data") or {}
    status = (data.get("metadata") or {}).get("statusCode")
    if isinstance(status, int) and status >= 400:
        # A closed posting: the job is kept as ignored, so its page is not read again.
        r["gone"] = f"The posting is gone (HTTP {status})"
        return
    markdown = (data.get("markdown") or "").strip()
    if not markdown:
        raise BoardError("Firecrawl returned an empty page")
    r["description"] = markdown
    heading = _HEADING.search(markdown)
    full = " ".join(heading.group(1).replace("*", "").split()) if heading else ""
    if full and (full.lower().startswith(r["title"].lower()) or r["title"].lower().startswith(full.lower())):
        r["title"] = full
    if r.get("slug_company") or not r.get("company"):
        r["company"] = _split_title((data.get("metadata") or {}).get("title") or "", r["url"])[1] or r.get("company", "")


BOARDS = {"firecrawl": Board("Firecrawl", _list, detail=_detail, check=lambda r, search: r.get("gone"))}


async def run(search: Search) -> dict:
    return await job_boards.run(search, BOARDS)


async def preview(search: Search, db) -> dict:
    return await job_boards.preview(search, db, BOARDS)
