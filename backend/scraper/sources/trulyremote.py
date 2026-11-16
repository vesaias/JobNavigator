"""trulyremotework.com source — the board publishes a machine-readable corpus and invites
ingestion: `llms-full.txt` lists every worldwide-remote job, and each job has a `.md` twin with
its full description and the employer's apply link. So the roster is one request, and only the
kept jobs need a detail fetch. Every role is screened worldwide-remote, so the search needs no
term or URL — the title and company filters do the narrowing.
"""
import asyncio
import copy
import json
import logging
import random
import re
import time
from datetime import datetime, timezone

import httpx
from sqlalchemy.exc import IntegrityError

from backend.models.db import (
    SessionLocal, Job, Search, get_existing_external_ids,
    get_global_title_exclude,
)
from backend.accounts.settings import get_setting
from backend.analyzer import salary_extractor
from backend.scraper._shared.dedup import make_external_id, make_content_hash, mark_ignored
from backend.scraper._shared.posting_links import counts_as_new
from backend.scraper._shared.filters import build_search_exclude_sets, company_included, include_hit
from backend.scraper._shared.analysis import analyze_inline, prefetch_h1b

logger = logging.getLogger("jobnavigator.trulyremote")

BASE = "https://trulyremotework.com"
ROSTER_URL = f"{BASE}/llms-full.txt"
_UA = "JobNavigator/1.0 (+https://github.com/vesaias/JobNavigator)"
_DETAIL_CONCURRENCY = 2              # gentle: the board is small and invites ingestion
_DETAIL_DELAY = (0.8, 1.2)           # seconds between detail fetches (jittered)
_RATE_LIMIT_TRIES = 3
# A Test reads at most this many detail pages, so one click can't fetch the whole corpus.
PREVIEW_DETAIL_LIMIT = 20
# The parsed roster, kept for as long as the board's Cache-Control allows (at most an hour).
_ROSTER_TTL_CAP = 3600
_roster_cache: dict = {"rows": None, "expires": 0.0}
# A job page that answers with one of these is gone; its job is skipped without a warning.
_GONE = (404, 410)


def _get_url(url: str) -> str:
    """The board publishes a `.md` twin for every page; use it for structured content."""
    return url.rstrip("/") + ".md"


def _md_text(value: str) -> str:
    """Strip markdown emphasis/links from a field value: `[Name](url)` → `Name`."""
    value = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", value or "")
    return re.sub(r"[*_`]+", "", value).strip()


def _parse_salary(text: str) -> tuple[int | None, int | None]:
    """The first one or two amounts in a salary string (`$152k - $205k`, `€100K - €125K`)."""
    if not text:
        return None, None
    nums: list[float] = []
    for amount, suffix in re.findall(r"(\d[\d,]*(?:\.\d+)?)\s*([kK])?", text):
        try:
            value = float(amount.replace(",", ""))
        except ValueError:
            continue
        nums.append(value * 1000 if suffix else value)
    nums = [n for n in nums if n >= 1000]
    if not nums:
        return None, None
    if len(nums) == 1:
        return int(nums[0]), None
    return int(min(nums[0], nums[1])), int(max(nums[0], nums[1]))


# The board posts mostly US salaries in bare dollars, so a "$" here is USD; a few postings name
# another currency or a shorter period. `Job` has no currency column, so only an amount that
# says dollars ("$" or "USD") and is annual becomes salary_min/max; anything else is kept as
# text in the description. Other dollars (A$, C$, NZ$, HK$, …), other ISO codes and any other
# currency symbol (€ £ ¥ ₹ …) are not USD; neither is a bare figure with no currency at all.
# A period shorter than a year ("a month", "/m", "pcm", "per wk") is not yearly, and a figure
# with no period under salary_extractor.UNSTATED_PERIOD_FLOOR is taken as monthly.
def _is_usd_annual(text: str, low: int | None = None, high: int | None = None) -> bool:
    """True when a salary string names US dollars and a yearly (or unstated) period."""
    currency = "USD" if salary_extractor.is_usd(text) else "other"
    if low is None:
        low, high = _parse_salary(text)
    return salary_extractor.yearly_usd(low, high, currency, salary_extractor.salary_period(text))[0] is not None


def _salary_fields(text: str) -> dict:
    """Structured salary fields for a roster/`.md` salary string. `salary_usd_annual` gates what
    the run stores as numbers; anything else is kept as `salary_text` for display."""
    text = (text or "").strip()
    lo, hi = _parse_salary(text)
    eligible = lo is not None and _is_usd_annual(text, lo, hi)
    return {
        "salary_min": lo,
        "salary_max": hi,
        "salary_text": text,
        "salary_usd_annual": eligible,
    }


def _block_description(block: str) -> str:
    """Everything after the `- Field:` lines in a roster block."""
    lines = []
    for line in block.splitlines():
        if line.startswith("## "):
            continue
        if re.match(r"^-\s+[A-Za-z][\w /]*:", line):
            continue
        lines.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _parse_roster(text: str) -> list[dict]:
    """The `## <title> at <company>` blocks of `llms-full.txt` (or a category `.md` page)."""
    out = []
    for block in re.split(r"^---\s*$", text, flags=re.M):
        m = re.search(r"^##\s+(.*)\s+at\s+(.*?)\s*$", block, flags=re.M)
        if not m:
            continue
        fields = dict(re.findall(r"^-\s+([A-Za-z][\w /]*):\s*(.*)$", block, flags=re.M))
        out.append({
            "title": _md_text(m.group(1)),
            "company": _md_text(m.group(2)),
            "url": (fields.get("URL") or "").strip(),
            "location": (fields.get("Location") or "").strip(),
            "description": _block_description(block),
            "employment_type": (fields.get("Type") or "").strip(),
            "posted": (fields.get("Posted") or "").strip(),
            **_salary_fields(fields.get("Salary", "")),
        })
    return out


_DETAIL_FIELD_RE = re.compile(r"^\*\*(Company|Location|Category|Posted|Page|Apply|Tags|Salary):\*\*\s*(.*)$", re.M)
_DESCRIPTION_RE = re.compile(r"^##\s+Description\s*$", re.M)
_POSTED_FORMATS = ("%a %b %d %Y", "%b %d %Y", "%B %d %Y", "%d %b %Y", "%d %B %Y")


def _iso_date(value: str) -> str | None:
    """`2026-10-16` or the `.md`'s `Fri Oct 16 2026` as `2026-10-16`; None if it doesn't parse."""
    value = (value or "").strip()
    m = re.match(r"(\d{4}-\d{2}-\d{2})\b", value)
    if m:
        return m.group(1)
    value = " ".join(value.replace(",", " ").split())
    for fmt in _POSTED_FORMATS:
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _parse_detail(text: str, fallback: dict) -> dict:
    """Enrich a roster row with its `.md` twin: full description, apply URL, salary. The
    `**Field:**` lines are read from the header only (the text before the first `## `
    section), so a `**Location:**` or `**Salary:**` line inside the description can't win."""
    out = dict(fallback)
    head = re.split(r"^##\s", text, maxsplit=1, flags=re.M)[0]
    m = re.search(r"^#\s+(.*)$", head, flags=re.M)
    if m:
        out["title"] = _md_text(m.group(1))
    fields = {k: v for k, v in _DETAIL_FIELD_RE.findall(head)}
    if fields.get("Company"):
        out["company"] = _md_text(fields["Company"])
    if fields.get("Location"):
        out["location"] = _md_text(fields["Location"])
    # The roster's ISO date is kept unless the page's own date parses.
    posted = _iso_date(fields.get("Posted"))
    if posted:
        out["posted"] = posted
    if fields.get("Apply"):
        out["apply_url"] = fields["Apply"].strip()
    desc = re.search(r"^##\s+Description\s*$(.*)", text, flags=re.M | re.S)
    if desc:
        out["description"] = desc.group(1).strip()
    if fields.get("Salary"):
        out.update(_salary_fields(fields["Salary"]))
    return out


def _retry_after(resp) -> float:
    try:
        return min(float(resp.headers.get("Retry-After", "")), 60.0)
    except (TypeError, ValueError):
        return 0.0


async def _get(client: httpx.AsyncClient, url: str, params: dict | None = None):
    """GET with a bounded backoff on 429, so a throttling board slows us down instead of failing."""
    resp = await client.get(url, params=params)
    for attempt in range(_RATE_LIMIT_TRIES - 1):
        if resp.status_code != 429:
            return resp
        wait = _retry_after(resp) or 5.0 * (2 ** attempt)
        logger.warning(f"trulyremote rate-limited (429); waiting {wait:.0f}s")
        await asyncio.sleep(wait)
        resp = await client.get(url, params=params)
    return resp


def _cache_ttl(headers) -> int:
    """Seconds the board lets us reuse a response: `max-age`, else `s-maxage` (the corpus sends
    only `s-maxage=3600`), capped at _ROSTER_TTL_CAP; 0 for `no-store`/`no-cache` or none."""
    cc = ((headers or {}).get("Cache-Control") or "").lower()
    if "no-store" in cc or "no-cache" in cc:
        return 0
    m = re.search(r"(?<![\w-])max-age\s*=\s*(\d+)", cc) or re.search(r"\bs-maxage\s*=\s*(\d+)", cc)
    return min(int(m.group(1)), _ROSTER_TTL_CAP) if m else 0


async def _fetch_roster(client: httpx.AsyncClient) -> list[dict]:
    """One request for the whole corpus (`llms-full.txt` lists every open job), reused for as
    long as its Cache-Control allows. llms.txt asks clients to cache and respect that header,
    and the corpus has no ETag or Last-Modified, so a conditional GET is not possible. Runs and
    Tests share the cache; it holds the board's raw rows, the same for every account."""
    now = time.monotonic()
    if _roster_cache["rows"] is not None and now < _roster_cache["expires"]:
        return copy.deepcopy(_roster_cache["rows"])
    resp = await _get(client, ROSTER_URL)
    resp.raise_for_status()
    rows = _parse_roster(resp.text)
    ttl = _cache_ttl(resp.headers)
    _roster_cache.update(rows=rows if ttl else None, expires=now + ttl)
    return copy.deepcopy(rows)


async def _fetch_roster_standalone() -> list[dict]:
    """The roster in a client of its own (a shared fetch runs this once for every subscriber)."""
    async with httpx.AsyncClient(timeout=30, headers={"User-Agent": _UA}) as client:
        return await _fetch_roster(client)


async def _fetch_details(client: httpx.AsyncClient, candidates: list[dict], cache: dict | None = None,
                         halt: dict | None = None) -> dict:
    """Fetch each kept job's `.md` twin (bounded concurrency) for the full description. Keyed by
    URL. Only a page that answered 200 with a `## Description` section is returned: a job
    whose page failed, is gone (404/410) or came back in another shape is left out, and the run
    skips it until a later run reads the page, rather than storing the roster's short blurb.
    Once one page is still answering 429 after its retries, the remaining pages are not
    requested this run (they wait for the next one), so a throttling board can't stretch a
    run by a minute per page.

    `cache` (MT-8): the `.md` pages a shared fetch's earlier subscribers already read, keyed by
    job URL. A page in it is not fetched again; every page parsed here is added to it (a
    failure or a non-200 never is).

    `halt` (R30 S-05): where the throttle stop is recorded. A shared fetch passes one dict from
    its memo to every subscriber, so once one subscriber's reads were stopped the next ones
    request no page this run either. Without it the stop holds for this call only."""
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
                resp = await _get(client, _get_url(job["url"]))
                if resp.status_code == 429:
                    if not halt.get("reason"):
                        logger.warning("trulyremote still rate-limited after retries; "
                                       "the remaining job pages wait for the next run")
                    halt["reason"] = "still rate-limited (429) after retries"
                    return
                if resp.status_code == 200 and _DESCRIPTION_RE.search(resp.text or ""):
                    details[job["url"]] = _parse_detail(resp.text, job)
                    if cache is not None:
                        cache[job["url"]] = dict(details[job["url"]])
                elif resp.status_code in _GONE:
                    logger.debug(f"trulyremote job page gone (HTTP {resp.status_code}): {job['url']}")
                else:
                    logger.info(f"trulyremote job page not read (HTTP {resp.status_code}"
                                f"{', no Description section' if resp.status_code == 200 else ''}): "
                                f"{job['url']}; tried again next run")
                await asyncio.sleep(random.uniform(*_DETAIL_DELAY))
            except Exception as e:
                logger.debug(f"trulyremote detail failed for {job['url']}: {e}")

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


def _remember_ignored(db, j: dict, search: Search, existing_ids: set) -> bool:
    """Write a job dropped after its detail page as `ignored`, so the next run's dedup skips it
    before fetching the page again (jobspy and company_pages do the same for filtered rows).
    The row keeps its description and belongs to the account the run ingests for. Like every
    ignored row it has no content_hash (`dedup.mark_ignored`). True if a row was written."""
    ext_id = make_external_id(j["company"], j["title"], j["url"])
    if not ext_id or ext_id in existing_ids:
        return False
    row = Job(
        external_id=ext_id,
        company=j.get("company") or "",
        title=j.get("title") or "",
        url=j.get("apply_url") or j["url"],
        source="trulyremote",
        search_id=search.id,
        location=j.get("location") or "Worldwide",
        description=j.get("description") or None,
        status="ignored",
        seen=False,
        saved=False,
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        return False
    except Exception as e:
        logger.debug(f"trulyremote: could not record ignored job {j.get('url')}: {e}")
        return False
    existing_ids.add(ext_id)
    return True


async def run(search: Search, shared=None) -> dict:
    """Full scrape entry point. Fetch roster → filter → fetch details → save to DB.

    `shared` (MT-8 SharedFetch): the roster is the whole corpus, the same for every search, so
    it is fetched once for all subscribers. Filters, dedup, the results_wanted cap, the `.md`
    reads and the ingest stay per subscriber, but each `.md` page is read at most once per
    shared fetch, through the fetch's `memo`. The roster rows are shared, so they are never
    mutated here (detail merges build new dicts)."""
    start = time.time()
    try:
        db = SessionLocal()
        try:
            include_kw, exclude_kw = _title_filters(search, db)
            global_exclude_set, search_exclude_set = build_search_exclude_sets(db, search)
            existing_ids = get_existing_external_ids(db)
            detail_cache = halt = None
            if shared is not None:
                listings = await shared.get(_fetch_roster_standalone)
                detail_cache = shared.memo.setdefault("trulyremote_details", {})
                # A throttle stop holds for every later subscriber of this fetch (R30 S-05).
                halt = shared.memo.setdefault("trulyremote_halt", {})

            async with httpx.AsyncClient(timeout=30, headers={"User-Agent": _UA}) as client:
                # The roster is the whole corpus and is not query-filtered, so the title and
                # company filters do the narrowing — slice only after they run, or a keyword
                # search could miss its matches entirely.
                if shared is None:
                    listings = await _fetch_roster(client)
                candidates = []
                seen = 0
                for j in listings:
                    if not j["url"]:
                        continue
                    ok, _ = _title_kept(j["title"], include_kw, exclude_kw)
                    if not ok:
                        continue
                    if not company_included(j.get("company"), search.company_filter)[0]:
                        continue
                    company_lower = (j.get("company") or "").lower()
                    if company_lower in global_exclude_set or company_lower in search_exclude_set:
                        continue
                    seen += 1   # rows the board lists that our filters keep, before dedup
                    if make_external_id(j["company"], j["title"], j["url"]) in existing_ids:
                        continue
                    candidates.append(j)
                candidates = candidates[:search.results_wanted or 100]
                # A single search calls exactly as before; only a shared fetch passes its cache
                # and its stop.
                extra = {"cache": detail_cache, "halt": halt} if detail_cache is not None else {}
                details = await _fetch_details(client, candidates, **extra)

            logger.info(f"trulyremote '{search.name}': {len(listings)} rows / {seen} seen / {len(candidates)} new to fetch")

            # The loop below writes rows; H-1B lookups happen before it (S2-01).
            await prefetch_h1b([(details[j["url"]].get("company") or j.get("company"))
                                for j in candidates if j["url"] in details])

            new_jobs = 0
            ignored_jobs = 0
            unread = 0
            for j in candidates:
                if j["url"] not in details:
                    # No job page this run (failed, throttled, gone or another shape): the
                    # roster's blurb is not stored, so the job stays out of the dedup set and
                    # the next run tries its page again. Not counted as new.
                    unread += 1
                    continue
                j = {**j, **details[j["url"]]}
                # The detail page's canonical title can differ from the listing's, so run the
                # filters over it too (preview already does this).
                kept, why = _title_kept(j["title"], include_kw, exclude_kw)
                if kept:
                    kept, why = company_included(j.get("company"), search.company_filter)
                company_lower = (j.get("company") or "").lower()
                if kept and (company_lower in global_exclude_set or company_lower in search_exclude_set):
                    kept, why = False, "company excluded"
                if not kept:
                    logger.info(f"trulyremote: '{j['title']}' @ {j.get('company')} ignored after the detail page ({why})")
                    if _remember_ignored(db, j, search, existing_ids):
                        ignored_jobs += 1
                    continue
                if not j["company"]:
                    continue

                # `url` is the employer's apply link, but external_id hashes the board's job URL:
                # that is the only id known before the `.md` page is read, so dedup can skip a
                # known job without fetching it. backend/scripts/backfill_external_id.py skips
                # this source for that reason (recomputing from `url` would break the dedup).
                ext_id = make_external_id(j["company"], j["title"], j["url"])
                # Only an explicit-USD annual salary is stored as numbers; any other is kept as
                # text at the end of the description.
                usd_min = j["salary_min"] if j.get("salary_usd_annual") else None
                usd_max = j.get("salary_max") if usd_min else None
                local_salary = None if usd_min else (j.get("salary_text") or None)
                description = j.get("description") or ""
                if local_salary:
                    description = f"{description}\n\nSalary (as posted): {local_salary}".strip()
                job = Job(
                    external_id=ext_id,
                    content_hash=make_content_hash(j["company"], j["title"]),
                    company=j["company"],
                    title=j["title"],
                    url=j.get("apply_url") or j["url"],
                    source="trulyremote",
                    search_id=search.id,
                    location=j.get("location") or "Worldwide",
                    description=description or None,
                    status="new",
                    seen=False,
                    saved=False,
                )

                if usd_min:
                    job.salary_min = usd_min
                    if usd_max:
                        job.salary_max = usd_max
                    job.salary_source = "posting"

                try:
                    # Every listing on the board is remote, so the remote flag is the source's
                    # own fact, not left to the location text ("Worldwide (no restrictions)").
                    await analyze_inline(job, db=db, arrangement=True)
                except Exception as e:
                    logger.warning(f"trulyremote inline analysis failed for {j['title']}: {e}")

                if local_salary and job.salary_source == "posting":
                    # The JD extractor reads any "$" as USD; on a posting whose salary is in
                    # another currency or period, drop the figure it inferred.
                    job.salary_min = job.salary_max = None
                    job.salary_source = "unknown"

                if job.h1b_jd_flag:
                    # Kept as "ignored" (as company scrapes do), so its URL is in the dedup set
                    # and its page is read once rather than on every run. Not a new job.
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
        log_activity("scrape", f"trulyremote '{search.name}': {new_jobs} new / {seen} seen"
                     + (f" ({ignored_jobs} filtered out after the job page)" if ignored_jobs else "")
                     + (f" ({unread} job pages not read; the next run tries them again)" if unread else "")
                     + f" in {duration:.1f}s")
        return {"jobs_found": seen, "new_jobs": new_jobs, "ignored_jobs": ignored_jobs,
                "error": None, "duration": duration}

    except Exception as e:
        duration = time.time() - start
        logger.error(f"trulyremote scrape failed for '{search.name}': {e}")
        from backend.activity import log_activity
        log_activity("scrape", f"trulyremote '{search.name}' failed: {e}")
        return {"jobs_found": 0, "new_jobs": 0, "error": str(e), "duration": duration}


async def preview(search: Search, db) -> dict:
    """Dry-run: fetch the roster, apply filters, return per-job diagnostics without saving."""
    start = time.time()
    try:
        include_kw, exclude_kw = _title_filters(search, db)
        global_exclude_set, search_exclude_set = build_search_exclude_sets(db, search)
        all_exclude = list(global_exclude_set | search_exclude_set)

        async with httpx.AsyncClient(timeout=30, headers={"User-Agent": _UA}) as client:
            unique = await _fetch_roster(client)
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
            # Not sampled, or its page could not be read: only the roster's blurb is known.
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
            if kept and body_phrases and j.get("description"):
                from backend.analyzer.h1b_checker import scan_jd_for_h1b_flags
                br = scan_jd_for_h1b_flags(j["description"], body_phrases)
                if br["jd_flag"]:
                    kept = False
                    reason = f"Body exclusion: {(br['jd_snippet'] or 'matched')[:80]}"

            # As posted; the run stores numbers only for a USD annual amount.
            salary = j.get("salary_text") or None

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
                "source": "trulyremote",
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
            "source_breakdown": {"trulyremote": raw_count},
            "company_breakdown": company_breakdown,
            "include_keywords": include_kw,
            "exclude_keywords": exclude_kw,
            "company_filter": search.company_filter or [],
            "company_exclude": all_exclude,
            "jobs": results,
            "config": {
                "mode": "trulyremote",
                "results_wanted": search.results_wanted or 100,
            },
        }
    except Exception as e:
        return {
            "search_name": search.name,
            "error": str(e),
            "duration": round(time.time() - start, 1),
            "config": {"mode": "trulyremote"},
        }
