"""freehire.me source — open aggregator REST API (no auth); returns the employer's own apply URL, a full HTML description, location, skills and enrichment in the search response, so no per-hit detail fetch is needed.

Configured via the Search's `direct_url` (a freehire URL whose query params are forwarded verbatim, `limit`/`offset`/`page` ignored since we paginate) and/or `search_term` (used as `q=`, overriding any q in direct_url); at least one must be set.
"""
import logging
import re
import time
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qsl

import httpx
from sqlalchemy.exc import IntegrityError

from backend.models.db import (
    SessionLocal, Job, Search, Setting, get_existing_external_ids,
    get_global_title_exclude, find_company_by_name,
)
from backend.scraper._shared.dedup import make_external_id, make_content_hash
from backend.scraper._shared.filters import build_search_exclude_sets
from backend.scraper._shared.analysis import analyze_inline

logger = logging.getLogger("jobnavigator.freehire")

API_URL = "https://freehire.me/api/v1/jobs/search"
PAGE_SIZE = 100
_MAX_PAGES = 50  # defensive cap: 5000 jobs / scrape
_DROP_PARAMS = {"limit", "offset", "page", "per_page"}


def _strip_html(html_str: str) -> str:
    """freehire descriptions are HTML; flatten to plaintext, inserting newlines only at block boundaries (</p>, </li>, <br>, …) so inline markup (<b>, <a>) doesn't split words."""
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


def _base_params(search: Search) -> dict:
    """Forward the operator's freehire filters (from direct_url) + q from search_term."""
    params = {}
    du = (getattr(search, "direct_url", None) or "").strip()
    if du and "freehire" in du:
        for k, v in parse_qsl(urlparse(du).query, keep_blank_values=False):
            if k.lower() not in _DROP_PARAMS:
                params[k] = v
    term = (getattr(search, "search_term", None) or "").strip()
    if term:
        params["q"] = term
    return params


def _parse_job(raw: dict) -> dict:
    enr = raw.get("enrichment") or {}
    return {
        "title": raw.get("title") or "",
        "company": raw.get("company") or "",
        "url": raw.get("url") or "",  # employer's own ATS apply link
        "location": raw.get("location") or "",
        "description": _strip_html(raw.get("description") or ""),
        "posted": raw.get("posted_at"),
        "public_slug": raw.get("public_slug") or "",
        "seniority": enr.get("seniority"),
        "employment_type": enr.get("employment_type"),
        # Structured salary (present on ~enriched jobs); period is year/month/hour.
        "salary_min": enr.get("salary_min"),
        "salary_max": enr.get("salary_max"),
        "salary_currency": enr.get("salary_currency"),
        "salary_period": enr.get("salary_period"),
        "visa_sponsorship": enr.get("visa_sponsorship"),
    }


def _annual_salary(j: dict) -> tuple:
    """Return (min, max) from freehire enrichment only when the period is annual, skipping month/hour periods rather than mis-storing them as yearly."""
    if not j.get("salary_min"):
        return None, None
    if j.get("salary_period") not in ("year", None):
        return None, None
    return j.get("salary_min"), j.get("salary_max")


async def _fetch_all(search: Search) -> list[dict]:
    """Paginate the freehire search API up to results_wanted (limit/offset)."""
    base = _base_params(search)
    wanted = search.results_wanted or 100
    out: list[dict] = []
    offset = 0
    async with httpx.AsyncClient(timeout=30, headers={"User-Agent": "JobNavigator/1.0 (+freehire source)"}) as client:
        for _ in range(_MAX_PAGES):
            if len(out) >= wanted:
                break
            params = dict(base, limit=PAGE_SIZE, offset=offset)
            resp = await client.get(API_URL, params=params)
            resp.raise_for_status()
            payload = resp.json()
            batch = payload.get("data") or []
            if not batch:
                break
            out.extend(batch)
            total = (payload.get("meta") or {}).get("total", 0)
            offset += PAGE_SIZE
            if offset >= total:
                break
    return out[:wanted]


async def _collect(search: Search) -> list[dict]:
    """Fetch + parse + dedup-within-batch (by apply URL, then slug)."""
    raw_list = await _fetch_all(search)
    seen = set()
    unique = []
    for r in raw_list:
        j = _parse_job(r)
        key = j["url"] or j["public_slug"]
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        unique.append(j)
    return unique


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
    """Full scrape entry point. Fetch → filter → save to DB."""
    start = time.time()
    try:
        unique = await _collect(search)
        logger.info(f"freehire '{search.name}': {len(unique)} jobs fetched")

        db = SessionLocal()
        new_jobs = 0
        try:
            include_kw, exclude_kw = _title_filters(search, db)
            global_exclude_set, search_exclude_set = build_search_exclude_sets(db, search)
            existing_ids = get_existing_external_ids(db)

            kept = 0
            for j in unique:
                ok, _ = _title_kept(j["title"], include_kw, exclude_kw)
                if not ok:
                    continue
                company_lower = (j.get("company") or "").lower()
                if company_lower in global_exclude_set or company_lower in search_exclude_set:
                    continue
                kept += 1

                job_url = j["url"]
                if not job_url:
                    continue
                ext_id = make_external_id(j["company"], j["title"], job_url)
                if ext_id in existing_ids:
                    continue

                job = Job(
                    external_id=ext_id,
                    content_hash=make_content_hash(j["company"], j["title"]),
                    company=j["company"],
                    title=j["title"],
                    url=job_url,
                    source="freehire",
                    search_id=search.id,
                    location=j.get("location") or None,
                    description=j.get("description") or None,
                    status="new",
                    seen=False,
                    saved=False,
                )

                # Structured salary from freehire enrichment (annual only) — set before analyze_inline so the JD extractor doesn't override it.
                sal_min, sal_max = _annual_salary(j)
                if sal_min:
                    job.salary_min = sal_min
                    if sal_max:
                        job.salary_max = sal_max
                    job.salary_source = "posting"

                # Inline body-exclusion (H-1B/language) + salary extraction from JD.
                try:
                    await analyze_inline(job, db=db)
                except Exception as e:
                    logger.warning(f"freehire inline analysis failed for {j['title']}: {e}")

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

            search_obj = db.query(Search).filter(Search.id == search.id).first()
            if search_obj:
                search_obj.last_run_at = datetime.now(timezone.utc)
            db.commit()
        finally:
            db.close()

        duration = time.time() - start
        from backend.activity import log_activity
        log_activity("scrape", f"freehire '{search.name}': {new_jobs} new / {kept} kept in {duration:.1f}s")
        return {"jobs_found": kept, "new_jobs": new_jobs, "error": None, "duration": duration}

    except Exception as e:
        duration = time.time() - start
        logger.error(f"freehire scrape failed for '{search.name}': {e}")
        from backend.activity import log_activity
        log_activity("scrape", f"freehire '{search.name}' failed: {e}")
        return {"jobs_found": 0, "new_jobs": 0, "error": str(e), "duration": duration}


async def preview(search: Search, db) -> dict:
    """Dry-run: fetch + apply filters, return per-job diagnostics without saving."""
    start = time.time()
    try:
        unique = await _collect(search)
        raw_count = len(unique)
        include_kw, exclude_kw = _title_filters(search, db)
        global_exclude_set, search_exclude_set = build_search_exclude_sets(db, search)
        all_exclude = list(global_exclude_set | search_exclude_set)

        import json
        body_row = db.query(Setting).filter(Setting.key == "body_exclusion_phrases").first()
        body_phrases = []
        if body_row and body_row.value:
            try:
                body_phrases = json.loads(body_row.value)
            except json.JSONDecodeError:
                pass

        from collections import Counter
        company_breakdown = dict(Counter(j["company"] for j in unique if j.get("company")).most_common(20))

        results = []
        for j in unique:
            kept, reason = _title_kept(j["title"], include_kw, exclude_kw)
            if kept:
                cl = (j.get("company") or "").lower()
                if cl in global_exclude_set:
                    kept, reason = False, f"Company excluded (global): {cl}"
                elif cl in search_exclude_set:
                    kept, reason = False, f"Company excluded: {cl}"
            if kept and body_phrases and j.get("description"):
                from backend.analyzer.h1b_checker import scan_jd_for_h1b_flags
                br = scan_jd_for_h1b_flags(j["description"], body_phrases)
                if br["jd_flag"]:
                    kept = False
                    reason = f"Body exclusion: {(br['jd_snippet'] or 'matched')[:80]}"

            sal_min, sal_max = _annual_salary(j)
            salary = None
            if sal_min:
                cur = (j.get("salary_currency") or "").upper()
                salary = f"{cur} {sal_min:,}".strip()
                if sal_max and sal_max != sal_min:
                    salary += f" – {sal_max:,}"

            desc = j.get("description") or ""
            results.append({
                "title": j["title"],
                "company": j.get("company", ""),
                "url": j.get("url", ""),
                "source": "freehire",
                "location": j.get("location", ""),
                "salary": salary,  # structured salary from enrichment (annual); else JD extractor at save
                "has_description": bool(desc and len(desc) > 50),
                "desc_length": len(desc),
                "kept": kept,
                "reason": reason if not kept else None,
                "seniority": j.get("seniority"),
                "posted": j.get("posted"),
            })

        after_filter = sum(1 for r in results if r["kept"])
        return {
            "search_name": search.name,
            "duration": round(time.time() - start, 1),
            "raw_count": raw_count,
            "after_filter": after_filter,
            "source_breakdown": {"freehire": raw_count},
            "company_breakdown": company_breakdown,
            "include_keywords": include_kw,
            "exclude_keywords": exclude_kw,
            "company_filter": search.company_filter or [],
            "company_exclude": all_exclude,
            "jobs": results,
            "config": {
                "mode": "freehire",
                "search_term": search.search_term or "",
                "direct_url": search.direct_url or "",
                "results_wanted": search.results_wanted or 100,
            },
        }
    except Exception as e:
        return {
            "search_name": search.name,
            "error": str(e),
            "duration": round(time.time() - start, 1),
            "config": {"mode": "freehire", "search_term": search.search_term or ""},
        }
