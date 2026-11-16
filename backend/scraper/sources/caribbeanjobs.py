"""caribbeanjobs.com source — plain-HTML job board (no auth). The search page lists 25 jobs per
page with title, company, location, salary and a short blurb; the full description, posting
date and structured salary come from each job's own page, where the board embeds a
schema.org JobPosting (JSON-LD) block.

Configured via the Search's `direct_url` (a ShowResults.aspx URL whose query params — Keywords,
Location, Category, Recruiter, rbet, SortBy — are forwarded verbatim, `Page` ignored since we
paginate) and/or `search_term` (used as `Keywords`, overriding any Keywords in direct_url); at
least one must be set.
"""
import asyncio
import json
import logging
import random
import re
import time
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urljoin, urlparse

import httpx
from sqlalchemy.exc import IntegrityError

from backend.models.db import (
    SessionLocal, Job, Search, get_existing_external_ids,
    get_global_title_exclude,
)
from backend.accounts.settings import get_setting
from backend.analyzer import salary_extractor
from backend.analyzer.salary_extractor import extract_salary
from backend.scraper._shared.dedup import make_external_id, make_content_hash, mark_ignored
from backend.scraper._shared.posting_links import counts_as_new
from backend.scraper._shared.filters import build_search_exclude_sets, company_included, include_hit
from backend.scraper._shared.analysis import analyze_inline, prefetch_h1b
from backend.scraper._shared.bot_wall import is_bot_wall

logger = logging.getLogger("jobnavigator.caribbeanjobs")

BASE = "https://www.caribbeanjobs.com"
LIST_URL = f"{BASE}/ShowResults.aspx"
_MAX_PAGES = 50         # defensive cap: 1250 listing rows / scrape
# Detail pages: two at a time, about a second apart with a little jitter, to stay gentle on a
# small board (a 100-job run takes about a minute, fine for a scheduled scrape).
_DETAIL_CONCURRENCY = 2
_DETAIL_GAP = 1.0
_DETAIL_JITTER = 0.25
# Test previews read at most this many detail pages, so one click can't fetch a hundred.
PREVIEW_DETAIL_LIMIT = 20
_DROP_PARAMS = {"page"}
_UA = "JobNavigator/1.0 (+https://github.com/vesaias/JobNavigator)"

# The run error, Test error and health reason when the board answers with a Cloudflare
# challenge (seen from our install on every request, with any User-Agent). The scraper does
# not try to pass the challenge. The editor shows the same block in
# frontend/src/sourceBlocks.js (`MODE_BLOCKS.caribbeanjobs`); change both places together.
CLOUDFLARE_BLOCKED = ("CaribbeanJobs is behind a Cloudflare challenge from this network; "
                      "the scraper cannot pass it (HTTP {status})")


class CloudflareChallenge(RuntimeError):
    """The board answered with a Cloudflare challenge page instead of content."""

    def __init__(self, status: int):
        super().__init__(CLOUDFLARE_BLOCKED.format(status=status))
        self.status = status


def _is_cloudflare_challenge(resp) -> bool:
    """True if a response is a Cloudflare challenge rather than the page. A 403/503 counts on
    the `cf-mitigated: challenge` header, a challenge marker in the body, or `server:
    cloudflare`; any status counts when the body is the challenge interstitial itself."""
    headers = getattr(resp, "headers", None) or {}
    if (headers.get("cf-mitigated") or "").strip().lower() == "challenge":
        return True
    body = getattr(resp, "text", "") or ""
    if is_bot_wall(body):
        return True
    if resp.status_code in (403, 503):
        low = body.lower()
        if "cf-chl" in low or "challenge-platform" in low:
            return True
        if "cloudflare" in (headers.get("server") or "").lower():
            return True
    return False


def _strip_html(html_str: str) -> str:
    """The board's descriptions are HTML; flatten to plaintext, inserting newlines only at block
    boundaries (</p>, </li>, <br>, …) so inline markup (<b>, <a>) doesn't split words."""
    if not html_str:
        return ""
    try:
        from bs4 import BeautifulSoup
        s = re.sub(r"(?i)<br\s*/?>", "\n", html_str)
        s = re.sub(r"(?i)</(p|div|li|h[1-6]|tr|ul|ol)>", "\n", s)
        text = BeautifulSoup(s, "html.parser").get_text()  # no separator → inline words stay joined
        return re.sub(r"\n{3,}", "\n\n", text).strip()
    except Exception:
        import html as _html
        return _html.unescape(re.sub(r"<[^>]+>", " ", html_str)).strip()


def _text(node) -> str:
    return node.get_text(" ", strip=True) if node else ""


def _query_plan(search: Search) -> tuple[dict, list[str]]:
    """(base filters, keyword queries) for a search. The URL's own filters are forwarded; its
    Keywords is the fallback query. A non-empty `search_term` overrides it and is split on commas
    — one board query per alternative, merged by the caller, because the board ANDs bare words
    and has no reliable OR of its own. An empty keyword list means the URL's filters alone."""
    base: dict = {}
    url_keywords = ""
    du = (getattr(search, "direct_url", None) or "").strip()
    if du and "caribbeanjobs" in du:
        for k, v in parse_qsl(urlparse(du).query, keep_blank_values=False):
            key = k.lower()
            if key in _DROP_PARAMS:
                continue
            if key == "keywords":
                url_keywords = v.strip()
            else:
                base[k] = v
    term = (getattr(search, "search_term", None) or "").strip()
    if term:
        keywords = [t.strip() for t in term.split(",") if t.strip()]
    else:
        # The URL's own Keywords is a fallback query; split it on commas too, so the same
        # OR-alternatives rule applies whether the phrases came from the term or the URL.
        keywords = [t.strip() for t in url_keywords.split(",") if t.strip()]
    return base, keywords


def _clean_url(href: str) -> str:
    """The listing's job href carries a `?p=…` tracking query; keep only scheme/host/path."""
    if not href:
        return ""
    parsed = urlparse(urljoin(BASE + "/", href))
    if not parsed.path:
        return ""
    return f"{BASE}{parsed.path}"


def _parse_salary(text: str) -> tuple[int | None, int | None]:
    """Pull the first one or two integers out of a salary string like `85000 - 95000`."""
    if not text:
        return None, None
    nums = [int(n.replace(",", "")) for n in re.findall(r"\d[\d,]*", text)]
    nums = [n for n in nums if n >= 1000]   # ignore stray small numbers in prose
    if not nums:
        return None, None
    if len(nums) == 1:
        return nums[0], None
    return min(nums[0], nums[1]), max(nums[0], nums[1])


# The board's salaries are in the local currency of each island (TTD, JMD, BBD, KYD, …) or
# in USD, and a bare "$" is usually local dollars. `Job` has no currency column, so only a
# salary that is explicitly USD and annual becomes salary_min/max; any other is kept as text.
# Currency and period are read by the shared helpers in analyzer/salary_extractor.


def _currency_of(text: str) -> str:
    """The ISO code a salary string names (`TT$ 8,000` → TTD), or "" when it names none."""
    return salary_extractor.currency_code(text or "")


def _unit_of(text: str) -> str:
    """The period a salary string names (`8,000 a month` → MONTH), or "" when it names none."""
    return salary_extractor.salary_period(text or "")


def _usd_annual(j: dict) -> tuple[int | None, int | None]:
    """(min, max) to store as a structured salary: only an explicit-USD, annual amount (or one
    with no period from salary_extractor.UNSTATED_PERIOD_FLOOR up: an unlabelled USD 4,000 on
    this board is monthly pay). Anything else is not comparable with the US salaries the app shows."""
    return salary_extractor.yearly_usd(j.get("salary_min"), j.get("salary_max"),
                                       j.get("salary_currency") or "", j.get("salary_unit") or "")


def _salary_display(j: dict) -> str | None:
    """A readable salary as posted (`TTD 8,000 – 10,000 / month`), or None without one."""
    lo, hi = j.get("salary_min"), j.get("salary_max")
    if not lo:
        return None
    out = f"{j['salary_currency']} " if j.get("salary_currency") else ""
    out += f"{lo:,}"
    if hi and hi != lo:
        out += f" – {hi:,}"
    unit = (j.get("salary_unit") or "").lower()
    if unit:
        out += f" / {unit}"
    return out


def _parse_listing_date(text: str) -> str | None:
    """`Updated 18/09/2026` → `2026-09-18`."""
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", text or "")
    if not m:
        return None
    day, month, year = m.groups()
    return f"{year}-{int(month):02d}-{int(day):02d}"


def _parse_card(card) -> dict:
    """One `div.job-result` from the search page."""
    title_a = card.select_one("div.job-result-title h2 a")
    company_a = card.select_one("div.job-result-title h3 a")
    loc = card.select_one("ul.job-overview li.location")
    sal = card.select_one("ul.job-overview li.salary")
    upd = card.select_one("ul.job-overview li.updated-time")
    desc = card.select_one('p[itemprop="description"]')
    sal_text = _text(sal)
    sal_min, sal_max = _parse_salary(sal_text)
    return {
        "title": _text(title_a),
        "company": _text(company_a),
        "url": _clean_url(title_a.get("href") if title_a else ""),
        "location": _text(loc),
        "description": _strip_html(str(desc)) if desc else "",
        "salary_min": sal_min,
        "salary_max": sal_max,
        "salary_currency": _currency_of(sal_text),
        "salary_unit": _unit_of(sal_text),
        "posted": _parse_listing_date(_text(upd)),
        "employment_type": "",
        "expired": False,
    }


def _job_posting_ld(soup) -> dict:
    """The schema.org JobPosting the detail page embeds, keyed by `#jobPostingSchema` (with a
    fallback to any ld+json JobPosting block)."""
    tag = soup.find("script", id="jobPostingSchema")
    blocks = [tag] if tag else soup.find_all("script", type="application/ld+json")
    for block in blocks:
        try:
            data = json.loads(block.string or "")
        except (ValueError, TypeError):
            continue
        if isinstance(data, dict) and data.get("@type") == "JobPosting":
            return data
    return {}


def _ld_location(ld: dict) -> str:
    addr = ((ld.get("jobLocation") or {}).get("address")) or {}
    parts = [addr.get("addressLocality"), addr.get("addressRegion"), addr.get("addressCountry")]
    return ", ".join(p.strip() for p in parts if isinstance(p, str) and p.strip())


def _parse_detail(html: str, fallback: dict) -> dict:
    """Enrich a listing row with the detail page: full description, posting date, salary and
    employment type. JSON-LD first, HTML selectors as the fallback."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    ld = _job_posting_ld(soup)
    out = dict(fallback)
    # NB: the board renders the "This job is expired" banner in the DOM on every page (CSS hides
    # it until it applies), so its presence says nothing; only validThrough below marks expiry.
    out["expired"] = False

    if ld:
        if ld.get("title"):
            out["title"] = str(ld["title"]).strip()
        org = (ld.get("hiringOrganization") or {}).get("name")
        if org:
            out["company"] = str(org).strip()
        desc = _strip_html(ld.get("description") or "")
        if desc:
            out["description"] = desc
        if ld.get("datePosted"):
            out["posted"] = str(ld["datePosted"])[:10]
        loc = _ld_location(ld)
        if loc:
            out["location"] = loc
        et = ld.get("employmentType")
        if et and str(et).lower() != "default":
            out["employment_type"] = str(et)
        base_salary = ld.get("baseSalary") or {}
        value = (base_salary.get("value") if isinstance(base_salary, dict) else None) or {}
        if not isinstance(value, dict):
            value = {"minValue": value}
        sal_min, sal_max = _parse_salary(str(value.get("minValue") or ""))
        if sal_min is None:
            sal_min, sal_max = _parse_salary(str(value.get("maxValue") or ""))
        elif sal_max is None:
            # schema.org proper: minValue and maxValue as two separate amounts
            top, _ = _parse_salary(str(value.get("maxValue") or ""))
            if top and top > sal_min:
                sal_max = top
        if sal_min:
            out["salary_min"], out["salary_max"] = sal_min, sal_max
            raw = f"{value.get('minValue') or ''} {value.get('maxValue') or ''}"
            currency = str(base_salary.get("currency") or value.get("currency") or "").strip().upper()
            out["salary_currency"] = currency or _currency_of(raw) or fallback.get("salary_currency") or ""
            unit_text = str(value.get("unitText") or base_salary.get("unitText") or "").strip()
            out["salary_unit"] = ((_unit_of(unit_text) or unit_text.upper())
                                  or _unit_of(raw) or fallback.get("salary_unit") or "")
        valid = ld.get("validThrough")
        if valid:
            try:
                if datetime.fromisoformat(str(valid).replace("Z", "+00:00")) < datetime.now(timezone.utc):
                    out["expired"] = True
            except ValueError:
                pass

    if not out.get("description"):
        jd = soup.select_one(".job-details")
        if jd:
            out["description"] = _strip_html(str(jd))
    if not out.get("employment_type"):
        et_node = soup.select_one("ul.job-overview li.employment-type")
        if et_node:
            out["employment_type"] = _text(et_node)
    if not out.get("location"):
        loc_node = soup.select_one("ul.job-overview li.location")
        if loc_node:
            out["location"] = _text(loc_node)
    if out.get("salary_min") is None:
        sal_node = soup.select_one("ul.job-overview li.salary")
        if sal_node:
            sal_text = _text(sal_node)
            out["salary_min"], out["salary_max"] = _parse_salary(sal_text)
            out["salary_currency"] = _currency_of(sal_text)
            out["salary_unit"] = _unit_of(sal_text)
    return out


_RATE_LIMIT_TRIES = 3


def _retry_after(resp) -> float:
    """The board's Retry-After in seconds (capped), or 0 when absent/unparseable."""
    try:
        return min(float(resp.headers.get("Retry-After", "")), 60.0)
    except (TypeError, ValueError):
        return 0.0


async def _get(client: httpx.AsyncClient, url: str, params: dict | None = None):
    """GET with a bounded backoff on 429, so a throttling board slows us down instead of failing
    the run. The last response is returned either way; the caller raises for non-200."""
    resp = await client.get(url, params=params)
    for attempt in range(_RATE_LIMIT_TRIES - 1):
        if resp.status_code != 429:
            return resp
        wait = _retry_after(resp) or 5.0 * (2 ** attempt)
        logger.warning(f"caribbeanjobs rate-limited (429); waiting {wait:.0f}s")
        await asyncio.sleep(wait)
        resp = await client.get(url, params=params)
    return resp


async def _fetch_keyword(client: httpx.AsyncClient, base: dict, keyword: str, wanted: int) -> list[dict]:
    """Paginate one keyword query up to `wanted` rows."""
    from bs4 import BeautifulSoup
    out: list[dict] = []
    for page in range(1, _MAX_PAGES + 1):
        if wanted <= 0 or len(out) >= wanted:
            break
        params = dict(base, Page=page)
        if keyword:
            params["Keywords"] = keyword
        resp = await _get(client, LIST_URL, params=params)
        if _is_cloudflare_challenge(resp):
            raise CloudflareChallenge(resp.status_code)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select("div.job-result")
        if not cards:
            break
        out.extend(_parse_card(c) for c in cards)
        if not soup.select_one('link[rel="next"]'):
            break
    return out[:wanted] if wanted > 0 else []


async def _fetch_listings(client: httpx.AsyncClient, base: dict, keywords: list[str], wanted: int) -> list[dict]:
    """Run each keyword query (an OR of comma-separated alternatives — the board ANDs bare words
    and has no reliable OR) and merge them, keeping one row per canonical job URL. An empty
    `keywords` is a single URL-filters-only query."""
    out: list[dict] = []
    seen: set[str] = set()
    for keyword in (keywords or [None]):
        if len(out) >= wanted:
            break
        for job in await _fetch_keyword(client, base, keyword, wanted - len(out)):
            url = job["url"]
            if not url or url in seen:
                continue
            seen.add(url)
            out.append(job)
    return out


def _detail_gap() -> float:
    """Seconds to wait after a detail fetch: _DETAIL_GAP give or take _DETAIL_JITTER."""
    return _DETAIL_GAP + random.uniform(-_DETAIL_JITTER, _DETAIL_JITTER)


async def _fetch_details(client: httpx.AsyncClient, candidates: list[dict], cache: dict | None = None,
                         halt: dict | None = None) -> dict:
    """Fetch each kept job's page (bounded concurrency) and parse the full description. Keyed by
    URL. Only a page that answered 200 is returned: a job whose page failed, was challenged or
    stayed throttled is left out, and the run skips it until a later run reads the page (R30
    S-04, as trulyremote), rather than storing the listing's short blurb.

    Once one page is still answering 429 after its retries, or comes back as a Cloudflare
    challenge, the remaining pages are not requested this run (they wait for the next one), so
    a throttling board can't stretch a run by a minute per page (R30 S-05).

    `cache` (MT-8): the detail pages a shared fetch's earlier subscribers already read, keyed
    by URL. A page in it is not fetched again; every page read here is added to it (a failure,
    a challenge or a non-200 never is).

    `halt` (R30 S-05): where the stop is recorded. A shared fetch passes one dict from its memo
    to every subscriber, so once one subscriber's reads were stopped the next ones request no
    page this run either. Without it the stop holds for this call only."""
    sem = asyncio.Semaphore(_DETAIL_CONCURRENCY)
    details: dict[str, dict] = {}
    halt = {} if halt is None else halt

    async def one(job: dict) -> None:
        if cache is not None and job["url"] in cache:
            details[job["url"]] = dict(cache[job["url"]])
            return
        async with sem:
            if halt.get("reason"):
                return
            try:
                resp = await _get(client, job["url"])
                stop = ("still rate-limited (429) after retries" if resp.status_code == 429
                        else "behind a Cloudflare challenge" if _is_cloudflare_challenge(resp) else None)
                if stop:
                    # Never cached; the job stays out of the dedup set and is read next run.
                    if not halt.get("reason"):
                        logger.warning(f"caribbeanjobs job pages {stop}; "
                                       f"the remaining job pages wait for the next run")
                    halt["reason"] = stop
                    return
                if resp.status_code == 200:
                    details[job["url"]] = _parse_detail(resp.text, job)
                    if cache is not None:
                        cache[job["url"]] = dict(details[job["url"]])
                else:
                    logger.info(f"caribbeanjobs job page not read (HTTP {resp.status_code}): "
                                f"{job['url']}; tried again next run")
                await asyncio.sleep(_detail_gap())   # be polite to a small board
            except Exception as e:
                logger.debug(f"caribbeanjobs detail failed for {job['url']}: {e}")

    await asyncio.gather(*(one(j) for j in candidates))
    return details


def _title_filters(search: Search, db) -> tuple[list, list]:
    include_kw = search.title_include_keywords or []
    exclude_kw = list(set((search.title_exclude_keywords or []) + get_global_title_exclude(db)))
    return include_kw, exclude_kw


def _title_kept(title: str, include_kw: list, exclude_kw: list) -> tuple[bool, str | None]:
    tl = title.lower()
    if include_kw and not any(include_hit(kw, tl) for kw in include_kw):
        return False, f"No match for: {', '.join(include_kw)}"
    if exclude_kw:
        matched = [kw for kw in exclude_kw if re.search(r'\b' + re.escape(kw) + r'\b', tl)]
        if matched:
            return False, f"Excluded by: {', '.join(matched)}"
    return True, None


def _store_ignored(db, search: Search, j: dict, existing_ids: set) -> bool:
    """Write a job the filters dropped after its page was read as status "ignored" (the same
    row JobSpy writes for a title-filtered posting), so its URL is in the dedup set and the
    page is read once. The row belongs to the account the run ingests for. True if written."""
    ext_id = make_external_id(j.get("company") or "", j["title"], j["url"])
    if ext_id in existing_ids:
        return False
    job = Job(
        external_id=ext_id,
        company=j.get("company") or "",
        title=j["title"],
        url=j["url"],
        source="caribbeanjobs",
        search_id=search.id,
        location=j.get("location") or None,
        description=j.get("description") or None,
        status="ignored",
        seen=False,
        saved=False,
    )
    try:
        with db.begin_nested():
            db.add(job)
            db.flush()
    except IntegrityError:
        return False
    except Exception as e:
        logger.warning(f"Insert failed for ignored job '{j['title']}' ({j['url']}): {e}")
        return False
    existing_ids.add(ext_id)
    return True


async def _fetch_listings_for(search: Search, wanted: int) -> list[dict]:
    """The listing rows of one search's query plan, in a client of its own (the shared fetch
    runs this once for every subscriber)."""
    base, keywords = _query_plan(search)
    async with httpx.AsyncClient(timeout=30, headers={"User-Agent": _UA}) as client:
        return await _fetch_listings(client, base, keywords, wanted)


async def run(search: Search, shared=None) -> dict:
    """Full scrape entry point. Fetch listings → filter → fetch details → save to DB.

    `shared` (MT-8 SharedFetch): the listing pages are fetched once, at the largest
    results_wanted among subscribers, and cut to this search's own; detail pages are fetched
    per subscriber (only its own new candidates) but each page at most once per shared
    fetch, through the fetch's `memo`. A throttle or challenge stop on the job pages is kept
    in the memo too, so the later subscribers of the fetch request no page this run."""
    start = time.time()
    wanted = search.results_wanted or 100
    try:
        db = SessionLocal()
        try:
            include_kw, exclude_kw = _title_filters(search, db)
            global_exclude_set, search_exclude_set = build_search_exclude_sets(db, search)
            existing_ids = get_existing_external_ids(db)
            detail_cache = halt = None
            if shared is not None:
                listings = await shared.get(
                    lambda: _fetch_listings_for(search, shared.params.get("results_wanted") or wanted))
                listings = listings[:wanted]
                detail_cache = shared.memo.setdefault("caribbeanjobs_details", {})
                halt = shared.memo.setdefault("caribbeanjobs_halt", {})

            async with httpx.AsyncClient(timeout=30, headers={"User-Agent": _UA}) as client:
                if shared is None:
                    listings = await _fetch_listings_for(search, wanted)
                candidates = []
                seen = 0
                for j in listings:
                    ok, _ = _title_kept(j["title"], include_kw, exclude_kw)
                    if not ok:
                        continue
                    if not company_included(j.get("company"), search.company_filter)[0]:
                        continue
                    company_lower = (j.get("company") or "").lower()
                    if company_lower in global_exclude_set or company_lower in search_exclude_set:
                        continue
                    seen += 1   # rows the board returned that our filters keep, before dedup
                    if make_external_id(j["company"], j["title"], j["url"]) in existing_ids:
                        continue
                    candidates.append(j)
                # A single search calls exactly as before; only a shared fetch passes its cache
                # and its stop.
                extra = {"cache": detail_cache, "halt": halt} if detail_cache is not None else {}
                details = await _fetch_details(client, candidates, **extra)

            logger.info(f"caribbeanjobs '{search.name}': {len(listings)} rows / {seen} seen / {len(candidates)} new to fetch")

            # The loop below writes rows; H-1B lookups happen before it (S2-01).
            await prefetch_h1b([(details[j["url"]].get("company") or j.get("company"))
                                for j in candidates if j["url"] in details])

            new_jobs = 0
            ignored_jobs = 0
            unread = 0
            for j in candidates:
                if j["url"] not in details:
                    # No job page this run (failed, challenged, throttled or not 200): the
                    # listing's blurb is not stored, so the body-exclusion phrases and the
                    # expiry date never miss the real page. The job stays out of the dedup set
                    # and the next run tries its page again (R30 S-04). Not counted as new.
                    unread += 1
                    continue
                j.update(details[j["url"]])
                # The detail page's JSON-LD can rename the job or its company, and the
                # stored row carries those names, so the filters see them too.
                ok, why = _title_kept(j["title"], include_kw, exclude_kw)
                if ok:
                    ok, why = company_included(j.get("company"), search.company_filter)
                company_lower = (j.get("company") or "").lower()
                if ok and (company_lower in global_exclude_set or company_lower in search_exclude_set):
                    ok, why = False, "company excluded"
                if not ok:
                    # Kept as "ignored", as JobSpy keeps a title-filtered row, so the next run
                    # dedups its URL instead of reading the page again. Not a new job.
                    logger.info(f"caribbeanjobs: '{j['title']}' @ {j.get('company')} ignored after the detail page ({why})")
                    if _store_ignored(db, search, j, existing_ids):
                        ignored_jobs += 1
                    continue
                if j.get("expired"):
                    continue
                if not j["company"]:
                    continue

                ext_id = make_external_id(j["company"], j["title"], j["url"])
                # Only an explicit-USD annual salary is stored as numbers; a local-currency
                # (or unstated-currency) one is kept as text at the end of the description.
                usd_min, usd_max = _usd_annual(j)
                local_salary = None if usd_min else _salary_display(j)
                description = j.get("description") or ""
                if local_salary:
                    description = f"{description}\n\nSalary (as posted): {local_salary}".strip()
                job = Job(
                    external_id=ext_id,
                    content_hash=make_content_hash(j["company"], j["title"]),
                    company=j["company"],
                    title=j["title"],
                    url=j["url"],
                    source="caribbeanjobs",
                    search_id=search.id,
                    location=j.get("location") or None,
                    description=description or None,
                    status="new",
                    seen=False,
                    saved=False,
                )

                # Structured salary from the posting — set before analyze_inline so the JD
                # extractor doesn't override it.
                if usd_min:
                    job.salary_min = usd_min
                    if usd_max:
                        job.salary_max = usd_max
                    job.salary_source = "posting"

                try:
                    await analyze_inline(job, db=db)
                except Exception as e:
                    logger.warning(f"caribbeanjobs inline analysis failed for {j['title']}: {e}")

                if not usd_min and job.salary_source == "posting":
                    # The JD extractor reads a bare "$" as USD, but on this board it is usually
                    # the island's own dollar: keep only a figure the description names as USD.
                    found = extract_salary(job.description or "", getattr(job, "_h1b_median", None),
                                           explicit_usd=True)
                    job.salary_min, job.salary_max = found["salary_min"], found["salary_max"]
                    job.salary_source = found["salary_source"]

                if job.h1b_jd_flag:
                    # Kept as "ignored" (as company scrapes do), so its URL is in the dedup set
                    # and the page is read once rather than on every run. Not a new job.
                    logger.info(f"Ignored (body exclusion): {j['title']} @ {j.get('company', '?')}")
                    mark_ignored(job)

                try:
                    with db.begin_nested():
                        db.add(job)
                        db.flush()
                    if job.status == "new":
                        new_jobs += counts_as_new(job)
                    else:
                        ignored_jobs += 1
                    existing_ids.add(ext_id)
                except IntegrityError:
                    logger.debug(f"Duplicate external_id for '{j['title']}' @ {j.get('company')}, skipping")
                    continue
                except Exception as e:
                    logger.warning(f"Insert failed for '{j['title']}' @ {j.get('company')} ({j['url']}): {e}")
                    continue

            search_obj = db.query(Search).filter(Search.id == search.id).first()
            if search_obj:
                search_obj.last_run_at = datetime.now(timezone.utc)
            db.commit()
        finally:
            db.close()

        duration = time.time() - start
        from backend.activity import log_activity
        log_activity("scrape", f"caribbeanjobs '{search.name}': {new_jobs} new / {seen} seen"
                     + (f" ({ignored_jobs} filtered out after the job page)" if ignored_jobs else "")
                     + (f" ({unread} job pages not read; the next run tries them again)" if unread else "")
                     + f" in {duration:.1f}s")
        return {"jobs_found": seen, "new_jobs": new_jobs, "ignored_jobs": ignored_jobs,
                "error": None, "duration": duration}

    except Exception as e:
        duration = time.time() - start
        logger.error(f"caribbeanjobs scrape failed for '{search.name}': {e}")
        from backend.activity import log_activity
        log_activity("scrape", f"caribbeanjobs '{search.name}' failed: {e}")
        return {"jobs_found": 0, "new_jobs": 0, "error": str(e), "duration": duration}


async def preview(search: Search, db) -> dict:
    """Dry-run: fetch listings + details, apply filters, return per-job diagnostics without saving."""
    start = time.time()
    try:
        include_kw, exclude_kw = _title_filters(search, db)
        global_exclude_set, search_exclude_set = build_search_exclude_sets(db, search)
        all_exclude = list(global_exclude_set | search_exclude_set)
        base, keywords = _query_plan(search)

        async with httpx.AsyncClient(timeout=30, headers={"User-Agent": _UA}) as client:
            unique = await _fetch_listings(client, base, keywords, search.results_wanted or 100)

            survivors = []
            for j in unique:
                kept, _ = _title_kept(j["title"], include_kw, exclude_kw)
                if kept and company_included(j.get("company"), search.company_filter)[0]:
                    cl = (j.get("company") or "").lower()
                    if cl not in global_exclude_set and cl not in search_exclude_set:
                        survivors.append(j)
            # A Test reads at most PREVIEW_DETAIL_LIMIT detail pages; the rest keep the
            # listing's blurb, and the preview says so.
            sampled = survivors[:PREVIEW_DETAIL_LIMIT]
            details = await _fetch_details(client, sampled)

        raw_count = len(unique)
        from collections import Counter
        company_breakdown = dict(Counter(j["company"] for j in unique if j.get("company")).most_common(20))

        body_raw = get_setting(db, "body_exclusion_phrases")
        body_phrases = []
        if body_raw:
            try:
                body_phrases = json.loads(body_raw)
            except json.JSONDecodeError:
                pass

        results = []
        for j in unique:
            # Not sampled, or its page could not be read: only the listing's blurb is known.
            unread = j["url"] not in details
            j = details.get(j["url"], j)
            kept, reason = _title_kept(j["title"], include_kw, exclude_kw)
            if kept:
                kept, reason = company_included(j.get("company"), search.company_filter)
            if kept:
                cl = (j.get("company") or "").lower()
                if cl in global_exclude_set:
                    kept, reason = False, f"Company excluded (global): {cl}"
                elif cl in search_exclude_set:
                    kept, reason = False, f"Company excluded: {cl}"
            if kept and j.get("expired"):
                kept, reason = False, "Expired posting"
            if kept and body_phrases and j.get("description"):
                from backend.analyzer.h1b_checker import scan_jd_for_h1b_flags
                br = scan_jd_for_h1b_flags(j["description"], body_phrases)
                if br["jd_flag"]:
                    kept = False
                    reason = f"Body exclusion: {(br['jd_snippet'] or 'matched')[:80]}"

            # As posted, with its currency; the run stores numbers only for USD per year.
            salary = _salary_display(j)

            desc = j.get("description") or ""
            row_extra = {}
            if unread and kept and body_phrases:
                # No job page read for this row: the body scan saw only the blurb.
                row_extra["body_checked"] = False
            results.append({
                **row_extra,
                "title": j["title"],
                "company": j.get("company", ""),
                "url": j.get("url", ""),
                "source": "caribbeanjobs",
                "location": j.get("location", ""),
                "salary": salary,
                "has_description": bool(desc and len(desc) > 50),
                "desc_length": len(desc),
                "kept": kept,
                "reason": reason if not kept else None,
                "employment_type": j.get("employment_type") or None,
                "posted": j.get("posted"),
            })

        after_filter = sum(1 for r in results if r["kept"])
        preview_note = None
        if len(survivors) > len(sampled):
            preview_note = (f"Details sampled: the job pages of the first {len(sampled)} of "
                            f"{len(survivors)} jobs that passed the title and company filters were read. "
                            f"The rest show the listing's short blurb; a run reads every new job's page.")
        return {
            "search_name": search.name,
            "duration": round(time.time() - start, 1),
            "raw_count": raw_count,
            "after_filter": after_filter,
            "details_sampled": len(sampled),
            "detail_limit": PREVIEW_DETAIL_LIMIT,
            "preview_note": preview_note,
            "body_phrase_count": len(body_phrases),
            "source_breakdown": {"caribbeanjobs": raw_count},
            "company_breakdown": company_breakdown,
            "include_keywords": include_kw,
            "exclude_keywords": exclude_kw,
            "company_filter": search.company_filter or [],
            "company_exclude": all_exclude,
            "jobs": results,
            "config": {
                "mode": "caribbeanjobs",
                "search_term": search.search_term or "",
                "direct_url": search.direct_url or "",
                "results_wanted": search.results_wanted or 100,
                "keywords": keywords,
            },
        }
    except Exception as e:
        return {
            "search_name": search.name,
            "error": str(e),
            "duration": round(time.time() - start, 1),
            "config": {"mode": "caribbeanjobs", "search_term": search.search_term or ""},
        }
