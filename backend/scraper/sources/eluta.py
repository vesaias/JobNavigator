"""eluta.ca source: Canadian jobs from employer career sites, read from the RSS search.

Location is a city with a 50 km radius; without one the search covers Canada. Eluta has no remote
filter. The search is full text over the posting, so the title filter does the narrowing. The
job page names no employer link, so the job stays a Board link.

Eluta refuses with a one-item feed: "Too Many Requests" after a burst, and "Too Many Feeds" once an
address checks more than 10 RSS feeds a day ("You may only check a maximum of 10 RSS feeds each
day", 2026-10-26). So one run reads one feed page and at most 6 job pages, one request every
_GAP seconds, and an Eluta search should run once a day.
"""
import asyncio
import ssl
import time
import weakref
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import httpx

from backend.countries import split_country_suffix
from backend.models.db import Search
from backend.scraper._shared import job_boards
from backend.scraper._shared.job_boards import Board, BoardError, make_row, term_of, too_old
from backend.scraper._shared.html_text import html_to_text

_BASE = "https://www.eluta.ca"
_MAX_PAGES = 1            # 20 items per RSS page
_MAX_DETAILS = 6
_GAP = 3.0
_RADIUS_KM = 50
_pace_state: "weakref.WeakKeyDictionary" = weakref.WeakKeyDictionary()


def _tls() -> ssl.SSLContext:
    """www.eluta.ca offers only TLS 1.2 with RSA key exchange (AES128-GCM-SHA256), which
    OpenSSL 3.5 no longer offers by default (handshake failure, measured 2026-10-26). This
    context adds those ciphers for that host only."""
    ctx = ssl.create_default_context()
    ctx.set_ciphers("DEFAULT:AES128-GCM-SHA256:AES256-GCM-SHA384")
    return ctx


def _mounts() -> dict:
    return {_BASE: httpx.AsyncHTTPTransport(verify=_tls())}


async def _get(client: httpx.AsyncClient, url: str, params=None) -> httpx.Response:
    """One Eluta request at a time per event loop, _GAP apart."""
    loop = asyncio.get_running_loop()
    lock, last = _pace_state.setdefault(loop, (asyncio.Lock(), [0.0]))
    async with lock:
        wait = last[0] + _GAP - time.monotonic()
        if wait > 0:
            await asyncio.sleep(wait)
        try:
            return await client.get(url, params=params)
        finally:
            last[0] = time.monotonic()


def _items(xml_text: bytes) -> list:
    """The feed's items; a refusal comes as one item titled "Too Many …" that links to /contact."""
    items = ET.fromstring(xml_text).findall("./channel/item")
    if len(items) == 1:
        title = (items[0].findtext("title") or "").strip()
        if title.startswith("Too Many") or (items[0].findtext("link") or "").rstrip("/").endswith("/contact"):
            reason = " ".join((items[0].findtext("description") or "").split())[:160]
            raise BoardError(f"Eluta answered {title}" + (f": {reason}" if reason else ""))
    return items


def _row(it) -> dict:
    try:
        posted = parsedate_to_datetime(it.findtext("pubDate") or "").isoformat()
    except (TypeError, ValueError):
        posted = None
    return make_row(
        title=it.findtext("title"), company=(it.findtext("employer") or "").strip(),
        url=(it.findtext("link") or "").split("?")[0], location=(it.findtext("location") or "").strip(),
        description=html_to_text(it.findtext("description") or ""),   # a snippet until the detail fills it
        posted=posted)


async def _list(client: httpx.AsyncClient, search: Search, limit: int) -> list:
    city = split_country_suffix(search.location or "")[0].strip()
    q = f"{term_of(search)} sort:post" + (f" radius:{_RADIUS_KM}" if city else "")
    rows = []
    for page in range(1, _MAX_PAGES + 1):
        resp = await _get(client, f"{_BASE}/rss", {"q": q, "l": city, "pg": page})
        if resp.status_code >= 400:
            raise BoardError(f"HTTP {resp.status_code} from the Eluta feed")
        try:
            items = _items(resp.content)
        except BoardError:
            if rows:
                break               # keep what the earlier pages gave
            raise
        batch = [_row(it) for it in items]
        fresh = [r for r in batch if not too_old(r, search.hours_old)]
        rows += fresh
        if len(items) < 20 or len(fresh) < len(batch) or len(rows) >= limit:
            break
    return rows[:limit]


async def _detail(client: httpx.AsyncClient, row: dict) -> None:
    """The job page carries schema.org JobPosting microdata; its description replaces the snippet."""
    resp = await _get(client, row["url"])
    if resp.status_code >= 400:
        raise BoardError(f"HTTP {resp.status_code} from {row['url']}")
    from bs4 import BeautifulSoup
    page = BeautifulSoup(resp.text, "html.parser")
    # The hiring organisation has its own empty <meta itemprop="description"> before the
    # posting's <div itemprop="description">, so take the longest element that holds text.
    texts = [html_to_text(str(el)) for el in page.select('[itemtype*="JobPosting"] [itemprop="description"]')
             if el.name != "meta"]
    text = max(texts, key=len, default="")
    if text:
        row["description"] = text


BOARDS = {"eluta": Board("Eluta", _list, _detail, max_details=_MAX_DETAILS)}


async def run(search: Search) -> dict:
    return await job_boards.run(search, BOARDS, _mounts())


async def preview(search: Search, db) -> dict:
    return await job_boards.preview(search, db, BOARDS, _mounts())
