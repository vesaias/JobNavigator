"""One pipeline for the boards read from their own JSON API or feed: sources/creative.py (six
boards, picked in `sources`), sources/himalayas.py and sources/eluta.py (one board each).

No login, no browser, no Apify key. A source describes each board as a `Board` and calls `run`
and `preview` here. Each board writes its own row into `source_breakdown`, and its key is the
stored Job.source. Detail queries run only for rows that pass the filters and are not stored
yet, so a scheduled run reads a few pages; a Test reads at most PREVIEW_DETAIL_LIMIT.

A row says how its job is applied to, which sets the job's link kind (link_kinds.py):
- `apply_url`: the employer's link the posting names (`employer_apply`), so the job is Direct and
  dedup can join it to the employer's own posting;
- `easy_apply`: the posting is applied to on the board itself;
- neither: only the board's page is known, and the job stays a Board link.
"""
import asyncio
import json
import logging
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional

import httpx
from sqlalchemy.exc import IntegrityError

from backend.accounts.settings import get_setting
from backend.analyzer.work_arrangement import HYBRID, ONSITE, REMOTE
from backend.countries import normalize_country, split_country_suffix, supported_countries
from backend.models.db import SessionLocal, Job, Search, get_existing_external_ids
from backend.scraper._shared.analysis import analyze_inline, prefetch_h1b
from backend.scraper._shared.dedup import make_external_id, make_content_hash, mark_ignored
from backend.scraper._shared.filters import (build_search_exclude_sets, company_included,
                                             search_title_filters, title_kept)
from backend.scraper._shared.link_kinds import EASY_APPLY, _on_board
from backend.scraper._shared.posting_links import counts_as_new
from backend.scraper._shared.postings import resolve_short_links

logger = logging.getLogger("jobnavigator.job_boards")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/130.0 Safari/537.36")
MAX_RESULTS = 500                # results_wanted per board, the UI's bound
PREVIEW_LIMIT = 20               # listing rows per board on Test
PREVIEW_DETAIL_LIMIT = 20        # detail queries per Test, all boards together
_DETAIL_CONCURRENCY = 3


class BoardError(Exception):
    """A board failure the run history shows as is."""


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
    # One more rule for this board's rows: (row, search) -> why it is dropped, or None.
    check: Optional[Callable[[dict, Search], Optional[str]]] = None


def clamp_results(value) -> int:
    try:
        n = int(value) if value is not None else 50
    except (TypeError, ValueError):
        n = 50
    return min(MAX_RESULTS, max(1, n))


def city_of(search: Search) -> str:
    """"Los Angeles, CA, United States" -> "Los Angeles"."""
    return split_country_suffix(search.location or "")[0].split(",")[0].strip()


def term_of(search: Search) -> str:
    return (search.search_term or "").strip()


def country_name(search: Search) -> str:
    """"canada" -> "Canada": the search's Country as the English name; "" when unknown."""
    return dict(supported_countries()).get(normalize_country(getattr(search, "country", None)) or "", "")


def iso_from_ts(ts) -> Optional[str]:
    if not isinstance(ts, (int, float)) or ts <= 0:
        return None
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


def annual_usd(lo, hi, period, currency) -> tuple:
    """(min, max) of a yearly USD salary, else (None, None). Another currency stays in the
    text, as on caribbeanjobs. A posting can label an hourly rate yearly ("15-20"), so a
    yearly figure below 1,000 is not taken."""
    if (str(currency or "").upper() != "USD" or str(period or "").upper() not in ("ANNUAL", "YEARLY")
            or not isinstance(lo, (int, float)) or lo < 1000):
        return None, None
    return int(lo), int(hi if isinstance(hi, (int, float)) and hi >= lo else lo)


def employer_apply(link) -> Optional[str]:
    """`link` when it leaves the job boards, else None: `apply_url` only ever holds an
    employer's link, so a mailto: or a LinkedIn link stays out of it."""
    return link if link and not _on_board(link) else None


def make_row(**kw) -> dict:
    base = {"title": "", "company": "", "url": "", "location": "", "description": "",
            "salary_min": None, "salary_max": None, "arrangement": None, "posted": None, "ref": None,
            "apply_url": None, "easy_apply": False}
    base.update(kw)
    base["title"] = " ".join((base["title"] or "").split())
    return base


def too_old(r: dict, hours_old) -> Optional[str]:
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


def http_client(mounts=None) -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=httpx.Timeout(30), follow_redirects=True, mounts=mounts,
                             headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})


def _defer_over_budget(fresh: list, breakdown: dict, boards: dict) -> list:
    """The new rows this run reads, with each board's max_details respected; the rest are
    counted as `deferred` in the board's breakdown row and left for a later run."""
    out, used = [], {}
    for r in fresh:
        cap = boards[r["source"]].max_details
        if cap is not None and used.get(r["source"], 0) >= cap:
            breakdown[r["source"]]["deferred"] = breakdown[r["source"]].get("deferred", 0) + 1
            continue
        used[r["source"]] = used.get(r["source"], 0) + 1
        out.append(r)
    return out


def _error_text(e: BaseException) -> str:
    return str(e) if isinstance(e, BoardError) else f"{type(e).__name__}: {e}"[:200]


async def _collect(client: httpx.AsyncClient, search: Search, boards: dict, limit: int) -> tuple[list, dict]:
    """Every board concurrently: (unique rows, breakdown). A failed board writes `error` into
    its breakdown row and the others still count."""
    if not boards:
        raise BoardError("no board selected")
    keys = list(boards)
    outcomes = await asyncio.gather(*(boards[k].listing(client, search, limit) for k in keys),
                                    return_exceptions=True)
    breakdown, rows, seen = {}, [], set()
    for key, outcome in zip(keys, outcomes):
        if isinstance(outcome, BaseException):
            breakdown[key] = {"seen": 0, "new": 0, "error": _error_text(outcome)}
            logger.warning(f"{key} for '{search.name}' failed: {breakdown[key]['error']}")
            continue
        breakdown[key] = {"seen": 0, "new": 0, "returned": len(outcome)}
        for r in outcome:
            r["source"] = key
            if r["url"] and r["title"] and r["url"] not in seen:
                seen.add(r["url"])
                rows.append(r)
    return rows, breakdown


async def _fill_details(client: httpx.AsyncClient, rows: list, boards: dict) -> None:
    """Run the board's detail query for each row that needs one. A row whose query fails
    keeps its listing fields and gets `detail_error`."""
    sem = asyncio.Semaphore(_DETAIL_CONCURRENCY)

    async def one(r):
        detail = boards[r["source"]].detail
        if detail is None:
            return
        async with sem:
            try:
                await detail(client, r)
            except Exception as e:
                r["detail_error"] = _error_text(e)
                logger.warning(f"{r['source']} detail failed for {r['url']}: {r['detail_error']}")
    await asyncio.gather(*(one(r) for r in rows))


def _rejection(r: dict, search: Search, boards: dict, include_kw, exclude_kw, global_ex: set, search_ex: set) -> Optional[str]:
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
    board = boards.get(r.get("source"))
    reason = board.check(r, search) if board and board.check else None
    if reason:
        return reason
    city = city_of(search)
    if (board and board.local_city and city and r.get("arrangement") != REMOTE
            and city.lower() not in (r.get("location") or "").lower()):
        return f"Not in {city}"
    return too_old(r, search.hours_old)


def _all_failed(breakdown: dict, boards: dict) -> Optional[str]:
    if breakdown and all(v.get("error") for v in breakdown.values()):
        return " · ".join(f"{boards[k].label if k in boards else k}: {v['error']}" for k, v in breakdown.items())
    return None


async def run(search: Search, boards: dict, mounts=None) -> dict:
    """Full scrape: list → filter → details for new rows → filter by date again → save.
    `boards` is the boards to read by key; `mounts` is what http_client takes."""
    start = time.time()
    breakdown = {}
    mode = search.search_mode
    try:
        db = SessionLocal()
        new_jobs = kept = ignored_jobs = 0
        try:
            include_kw, exclude_kw = search_title_filters(search, db)
            global_ex, search_ex = build_search_exclude_sets(db, search)
            existing_ids = get_existing_external_ids(db)

            def rejected(r):
                return _rejection(r, search, boards, include_kw, exclude_kw, global_ex, search_ex)

            async with http_client(mounts) as client:
                rows, breakdown = await _collect(client, search, boards, clamp_results(search.results_wanted))

                def bump(r, field):
                    breakdown[r["source"]][field] = breakdown[r["source"]].get(field, 0) + 1

                fresh = []
                for r in rows:
                    if rejected(r):
                        bump(r, "filtered")
                        continue
                    kept += 1
                    bump(r, "seen")
                    if make_external_id(r["company"], r["title"], r["url"]) not in existing_ids:
                        fresh.append(r)
                fresh = _defer_over_budget(fresh, breakdown, boards)
                await _fill_details(client, fresh, boards)
            # Behance dates and company names arrive with the detail query.
            late = [r for r in fresh if rejected(r)]
            for r in late:
                kept -= 1
                breakdown[r["source"]]["seen"] -= 1
                bump(r, "filtered")
            late_ids = {id(r) for r in late}
            await prefetch_h1b([r.get("company") for r in fresh if id(r) not in late_ids])
            landed = await resolve_short_links([r.get("apply_url") for r in fresh if id(r) not in late_ids])

            for r in fresh:
                ext_id = make_external_id(r["company"], r["title"], r["url"])
                if ext_id in existing_ids:
                    continue
                job = Job(external_id=ext_id, content_hash=make_content_hash(r["company"], r["title"]),
                          company=r["company"], title=r["title"], url=r["url"],
                          apply_url=landed.get(r.get("apply_url"), r.get("apply_url")), source=r["source"],
                          search_id=search.id, location=r.get("location") or None,
                          description=r.get("description") or None, status="new", seen=False, saved=False)
                if r.get("easy_apply"):
                    job.link_kind = EASY_APPLY   # kept on insert: link_kinds.classify
                if id(r) in late_ids:
                    # Dropped after its job page was read (Behance dates arrive there): kept as
                    # "ignored", so the next run's dedup skips it before reading the page again.
                    mark_ignored(job)
                    ignored_jobs += _store(db, job, ext_id, existing_ids, r)
                    continue
                if r.get("salary_min"):
                    job.salary_min = r["salary_min"]
                    job.salary_max = r.get("salary_max") or r["salary_min"]
                    job.salary_source = "posting"
                try:
                    await analyze_inline(job, db=db, arrangement=r.get("arrangement"))
                except Exception as e:
                    logger.warning(f"{mode} inline analysis failed for {r['title']}: {e}")
                if job.h1b_jd_flag:
                    # Kept as "ignored" (as company scrapes do), so its page is read once.
                    logger.info(f"Ignored (body exclusion): {r['title']} @ {r.get('company') or '?'}")
                    mark_ignored(job)
                if not _store(db, job, ext_id, existing_ids, r):
                    continue
                if job.status == "ignored":
                    ignored_jobs += 1
                elif counts_as_new(job):
                    new_jobs += 1
                    breakdown[r["source"]]["new"] += 1

            search_obj = db.query(Search).filter(Search.id == search.id).first()
            if search_obj:
                search_obj.last_run_at = datetime.now(timezone.utc)
            db.commit()
        finally:
            db.close()

        duration = time.time() - start
        from backend.activity import log_activity
        log_activity("scrape", f"{mode} '{search.name}': {new_jobs} new / {kept} kept in {duration:.1f}s"
                     + (f" ({ignored_jobs} filtered out after the job page)" if ignored_jobs else ""))
        return {"jobs_found": kept, "new_jobs": new_jobs, "ignored_jobs": ignored_jobs,
                "error": _all_failed(breakdown, boards), "duration": duration, "source_breakdown": breakdown}
    except Exception as e:
        duration = time.time() - start
        msg = _error_text(e)
        logger.error(f"{mode} scrape failed for '{search.name}': {msg}")
        from backend.activity import log_activity
        log_activity("scrape", f"{mode} '{search.name}' failed: {msg}")
        return {"jobs_found": 0, "new_jobs": 0, "error": msg, "duration": duration,
                "source_breakdown": breakdown}


def _store(db, job: Job, ext_id: str, existing_ids: set, r: dict) -> bool:
    """Insert one job; True when it was written."""
    try:
        with db.begin_nested():
            db.add(job)
            db.flush()
    except IntegrityError:
        logger.debug(f"Duplicate external_id for '{r['title']}' @ {r.get('company')}, skipping")
        return False
    except Exception as e:
        logger.warning(f"Insert failed for '{r['title']}' @ {r.get('company')} ({r['url']}): {e}")
        return False
    existing_ids.add(ext_id)
    return True


def _body_phrases(db) -> list:
    raw = get_setting(db, "body_exclusion_phrases")
    try:
        return json.loads(raw) if raw else []
    except json.JSONDecodeError:
        return []


async def preview(search: Search, db, boards: dict, mounts=None) -> dict:
    """Dry run: PREVIEW_LIMIT listing rows per board, details for the first kept rows, nothing saved."""
    start = time.time()
    config = {"mode": search.search_mode, "search_term": search.search_term or "", "location": search.location or "",
              "sources": list(boards), "results_wanted": PREVIEW_LIMIT}
    try:
        include_kw, exclude_kw = search_title_filters(search, db)
        global_ex, search_ex = build_search_exclude_sets(db, search)

        def rejected(r):
            return _rejection(r, search, boards, include_kw, exclude_kw, global_ex, search_ex)

        async with http_client(mounts) as client:
            rows, breakdown = await _collect(client, search, boards, PREVIEW_LIMIT)
            reasons = [rejected(r) for r in rows]
            survivors = [r for r, why in zip(rows, reasons) if why is None]
            sampled = _defer_over_budget(survivors, breakdown, boards)[:PREVIEW_DETAIL_LIMIT]
            await _fill_details(client, sampled, boards)
        sampled_ids = {id(r) for r in sampled}
        phrases = _body_phrases(db)

        from backend.analyzer.h1b_checker import scan_jd_for_h1b_flags
        results = []
        for r, reason in zip(rows, reasons):
            if reason is None and id(r) in sampled_ids:
                reason = rejected(r)
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
        preview_note = None
        if len(survivors) > len(sampled):
            caps = "".join(f", and {b.label} {b.max_details} per run" for b in boards.values() if b.max_details)
            preview_note = (f"Details sampled: the job pages of {len(sampled)} of {len(survivors)} jobs "
                            f"that passed the filters were read (at most {PREVIEW_DETAIL_LIMIT}{caps}). "
                            f"The rest show the listing's text; a run reads each new job's page.")
        return {
            "search_name": search.name,
            "duration": round(time.time() - start, 1),
            "details_sampled": len(sampled),
            "detail_limit": PREVIEW_DETAIL_LIMIT,
            "preview_note": preview_note,
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
