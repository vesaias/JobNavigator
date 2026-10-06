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
import re
import time
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urljoin, urlparse

import httpx
from sqlalchemy.exc import IntegrityError

from backend.models.db import (
    SessionLocal, Job, Search, Setting, get_existing_external_ids,
    get_global_title_exclude,
)
from backend.scraper._shared.dedup import make_external_id, make_content_hash
from backend.scraper._shared.filters import build_search_exclude_sets
from backend.scraper._shared.analysis import analyze_inline

logger = logging.getLogger("jobnavigator.caribbeanjobs")

BASE = "https://www.caribbeanjobs.com"
LIST_URL = f"{BASE}/ShowResults.aspx"
_MAX_PAGES = 50         # defensive cap: 1250 listing rows / scrape
_DETAIL_CONCURRENCY = 4
_DROP_PARAMS = {"page"}
_UA = "JobNavigator/1.0 (+https://github.com/vesaias/JobNavigator)"


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
    sal_min, sal_max = _parse_salary(_text(sal))
    return {
        "title": _text(title_a),
        "company": _text(company_a),
        "url": _clean_url(title_a.get("href") if title_a else ""),
        "location": _text(loc),
        "description": _strip_html(str(desc)) if desc else "",
        "salary_min": sal_min,
        "salary_max": sal_max,
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
        value = ((ld.get("baseSalary") or {}).get("value")) or {}
        sal_min, sal_max = _parse_salary(str(value.get("minValue") or ""))
        if sal_min is None:
            sal_min, sal_max = _parse_salary(str(value.get("maxValue") or ""))
        if sal_min:
            out["salary_min"], out["salary_max"] = sal_min, sal_max
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
            out["salary_min"], out["salary_max"] = _parse_salary(_text(sal_node))
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


async def _fetch_details(client: httpx.AsyncClient, candidates: list[dict]) -> dict:
    """Fetch each kept job's page (bounded concurrency) and parse the full description. Keyed by
    URL; a detail that fails leaves the listing row's short blurb in place."""
    sem = asyncio.Semaphore(_DETAIL_CONCURRENCY)
    details: dict[str, dict] = {}

    async def one(job: dict) -> None:
        async with sem:
            try:
                resp = await _get(client, job["url"])
                if resp.status_code == 200:
                    details[job["url"]] = _parse_detail(resp.text, job)
                await asyncio.sleep(0.15)   # be polite to a small board
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
    if include_kw and not any(kw.lower() in tl for kw in include_kw):
        return False, f"No match for: {', '.join(include_kw)}"
    if exclude_kw:
        matched = [kw for kw in exclude_kw if re.search(r'\b' + re.escape(kw) + r'\b', tl)]
        if matched:
            return False, f"Excluded by: {', '.join(matched)}"
    return True, None


async def run(search: Search) -> dict:
    """Full scrape entry point. Fetch listings → filter → fetch details → save to DB."""
    start = time.time()
    try:
        db = SessionLocal()
        try:
            include_kw, exclude_kw = _title_filters(search, db)
            global_exclude_set, search_exclude_set = build_search_exclude_sets(db, search)
            existing_ids = get_existing_external_ids(db)
            base, keywords = _query_plan(search)

            async with httpx.AsyncClient(timeout=30, headers={"User-Agent": _UA}) as client:
                listings = await _fetch_listings(client, base, keywords, search.results_wanted or 100)
                candidates = []
                seen = 0
                for j in listings:
                    ok, _ = _title_kept(j["title"], include_kw, exclude_kw)
                    if not ok:
                        continue
                    company_lower = (j.get("company") or "").lower()
                    if company_lower in global_exclude_set or company_lower in search_exclude_set:
                        continue
                    seen += 1   # rows the board returned that our filters keep, before dedup
                    if make_external_id(j["company"], j["title"], j["url"]) in existing_ids:
                        continue
                    candidates.append(j)
                details = await _fetch_details(client, candidates)

            logger.info(f"caribbeanjobs '{search.name}': {len(listings)} rows / {seen} seen / {len(candidates)} new to fetch")

            new_jobs = 0
            for j in candidates:
                if j["url"] in details:
                    j.update(details[j["url"]])
                if j.get("expired"):
                    continue
                if not j["company"]:
                    continue

                ext_id = make_external_id(j["company"], j["title"], j["url"])
                job = Job(
                    external_id=ext_id,
                    content_hash=make_content_hash(j["company"], j["title"]),
                    company=j["company"],
                    title=j["title"],
                    url=j["url"],
                    source="caribbeanjobs",
                    search_id=search.id,
                    location=j.get("location") or None,
                    description=j.get("description") or None,
                    status="new",
                    seen=False,
                    saved=False,
                )

                # Structured salary from the detail page — set before analyze_inline so the JD
                # extractor doesn't override it.
                if j.get("salary_min"):
                    job.salary_min = j["salary_min"]
                    if j.get("salary_max"):
                        job.salary_max = j["salary_max"]
                    job.salary_source = "posting"

                try:
                    await analyze_inline(job, db=db)
                except Exception as e:
                    logger.warning(f"caribbeanjobs inline analysis failed for {j['title']}: {e}")

                if job.h1b_jd_flag:
                    logger.info(f"Skipping (body exclusion): {j['title']} @ {j.get('company', '?')}")
                    continue

                try:
                    with db.begin_nested():
                        db.add(job)
                        db.flush()
                    new_jobs += 1
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
        log_activity("scrape", f"caribbeanjobs '{search.name}': {new_jobs} new / {seen} seen in {duration:.1f}s")
        return {"jobs_found": seen, "new_jobs": new_jobs, "error": None, "duration": duration}

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
                if kept:
                    cl = (j.get("company") or "").lower()
                    if cl not in global_exclude_set and cl not in search_exclude_set:
                        survivors.append(j)
            details = await _fetch_details(client, survivors)

        raw_count = len(unique)
        from collections import Counter
        company_breakdown = dict(Counter(j["company"] for j in unique if j.get("company")).most_common(20))

        body_row = db.query(Setting).filter(Setting.key == "body_exclusion_phrases").first()
        body_phrases = []
        if body_row and body_row.value:
            try:
                body_phrases = json.loads(body_row.value)
            except json.JSONDecodeError:
                pass

        results = []
        for j in unique:
            j = details.get(j["url"], j)
            kept, reason = _title_kept(j["title"], include_kw, exclude_kw)
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

            salary = None
            if j.get("salary_min"):
                salary = f"{j['salary_min']:,}"
                if j.get("salary_max") and j["salary_max"] != j["salary_min"]:
                    salary += f" – {j['salary_max']:,}"

            desc = j.get("description") or ""
            results.append({
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
        return {
            "search_name": search.name,
            "duration": round(time.time() - start, 1),
            "raw_count": raw_count,
            "after_filter": after_filter,
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
