"""Jobright.ai source — personalized recommendations + search via REST API.

Public entry points:
- `run(search)` — full scrape entry point for the scheduler / dispatch.
- `preview(search, db)` — UI dry-run endpoint that returns filtering diagnostics.
"""
import asyncio
import json
import logging
import re
import time
from datetime import datetime, timezone

import httpx

from sqlalchemy.exc import IntegrityError

from backend.models.db import SessionLocal, Job, Search, Setting, get_existing_external_ids
from backend.scraper._shared.dedup import make_external_id, make_content_hash

logger = logging.getLogger("jobnavigator.jobright")


class SessionExpiredError(Exception):
    """Raised when Jobright session is invalid/expired mid-scrape."""
    pass


API_BASE = "https://swan-api.jobright.ai"
SITE_BASE = "https://jobright.ai"

# Delay between pagination requests (seconds) — Jobright does bot/fingerprint checks
DELAY_BETWEEN_PAGES = 7.0
# Retry config for 403/429
MAX_RETRIES = 3
RETRY_BACKOFF = [15, 45, 90]  # seconds to wait on each retry


def _get_setting(db, key, default=""):
    row = db.query(Setting).filter(Setting.key == key).first()
    return row.value if row else default


def _save_setting(db, key, value):
    row = db.query(Setting).filter(Setting.key == key).first()
    if row:
        row.value = value
    else:
        db.add(Setting(key=key, value=value))
    db.commit()


async def _login(email: str, password: str) -> str:
    """Log in to Jobright.ai and return SESSION_ID cookie."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{API_BASE}/swan/auth/login/pwd",
            json={"email": email, "password": password},
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            raise RuntimeError(f"Jobright login failed: {data}")

        # Extract SESSION_ID from set-cookie header
        session_id = None
        for cookie in resp.cookies.jar:
            if cookie.name == "SESSION_ID":
                session_id = cookie.value
                break

        if not session_id:
            # Fallback: parse from raw header
            for val in resp.headers.get_list("set-cookie"):
                if "SESSION_ID=" in val:
                    session_id = val.split("SESSION_ID=")[1].split(";")[0]
                    break

        if not session_id:
            raise RuntimeError("Login succeeded but no SESSION_ID cookie returned")

        logger.info("Jobright login successful")
        return session_id


async def _ensure_session(force_relogin: bool = False) -> str:
    """Get a valid session ID, logging in if needed.

    Args:
        force_relogin: Skip validation and always re-login (used when
                       API returns 200+empty despite session looking valid).
    """
    db = SessionLocal()
    try:
        session_id = _get_setting(db, "jobright_session_id")

        # Validate existing session — just check auth, not job content.
        # Empty jobList with success=true is normal (cache depleted); the
        # scraper handles this by passing refresh=true on the first fetch.
        if session_id and not force_relogin:
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(
                        f"{API_BASE}/swan/recommend/list/jobs?position=0&count=1",
                        cookies={"SESSION_ID": session_id},
                    )
                    if resp.status_code in (401, 403):
                        logger.info(f"Jobright session returned {resp.status_code}, re-logging in")
                    else:
                        data = resp.json()
                        if data.get("success"):
                            return session_id
                        logger.info(f"Jobright session invalid (success=false): {data.get('message', '')}")
            except Exception as e:
                logger.info(f"Jobright session validation failed: {e}")
        elif force_relogin:
            logger.info("Jobright: forced re-login requested")

        # Need to login
        email = _get_setting(db, "jobright_email")
        password = _get_setting(db, "jobright_password")
        if not email or not password:
            raise RuntimeError("Jobright credentials not configured (set jobright_email and jobright_password in Settings)")

        session_id = await _login(email, password)

        # Persist session for reuse across restarts
        _save_setting(db, "jobright_session_id", session_id)
        return session_id
    finally:
        db.close()


async def _fetch_recommendations(session_id: str, position: int, count: int = 20, refresh: bool = False) -> list[dict] | None:
    """Fetch a page of personalized job recommendations.

    Args:
        refresh: Pass True on the first request to force Jobright to regenerate
                 its recommendation pool. Without this, the cache can be empty
                 after prior scrapes exhaust it. Only needed for position=0.

    Returns:
        list[dict] — job list on success
        None — rate-limit exhaustion, caller should stop pagination
        Raises SessionExpiredError on 401 so caller can re-auth and retry.
    """
    params = {"position": position, "count": count}
    if refresh:
        params["refresh"] = "true"
    for attempt in range(MAX_RETRIES + 1):
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{API_BASE}/swan/recommend/list/jobs",
                params=params,
                cookies={"SESSION_ID": session_id},
            )
            if resp.status_code == 401:
                raise SessionExpiredError("Jobright returned 401 — session expired")
            if resp.status_code in (403, 429):
                if attempt < MAX_RETRIES:
                    wait = RETRY_BACKOFF[attempt]
                    logger.warning(f"Jobright {resp.status_code} at position={position}, waiting {wait}s (retry {attempt + 1}/{MAX_RETRIES})")
                    await asyncio.sleep(wait)
                    continue
                else:
                    logger.error(f"Jobright {resp.status_code} at position={position}, retries exhausted — stopping pagination")
                    return None  # signal caller to stop
            resp.raise_for_status()
            data = resp.json()
            if not data.get("success"):
                msg = data.get("message", "")
                # Some auth failures come as success=false with a message
                if "login" in msg.lower() or "auth" in msg.lower() or "session" in msg.lower():
                    raise SessionExpiredError(f"Jobright API auth error: {msg}")
                raise RuntimeError(f"Jobright recommendations API error: {data}")
            return data.get("result", {}).get("jobList", [])
    return None


async def _fetch_search_ssr(keyword: str, location: str = "") -> tuple[list[dict], int]:
    """Fetch jobs via SSR search page (__NEXT_DATA__). Returns (jobs, total_count)."""
    params = {"titleKeyword": keyword, "visit": "search"}
    if location:
        params["location"] = location

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{SITE_BASE}/jobs/search", params=params)
        resp.raise_for_status()

        # Extract __NEXT_DATA__ JSON
        match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', resp.text, re.DOTALL)
        if not match:
            logger.warning("Jobright SSR: __NEXT_DATA__ not found")
            return [], 0

        next_data = json.loads(match.group(1))
        page_props = next_data.get("props", {}).get("pageProps", {})
        job_list = page_props.get("jobList", [])
        total = page_props.get("totalJobs", len(job_list))
        return job_list, total


def _parse_salary(salary_desc: str) -> tuple:
    """Parse salary string like '$120K - $180K/yr' into (min, max) integers."""
    if not salary_desc:
        return None, None

    # Match patterns like $120K, $120,000, $120000
    amounts = re.findall(r'\$[\d,]+(?:\.\d+)?[Kk]?', salary_desc)
    parsed = []
    for a in amounts:
        num_str = a.replace('$', '').replace(',', '')
        if num_str.upper().endswith('K'):
            parsed.append(int(float(num_str[:-1]) * 1000))
        else:
            val = int(float(num_str))
            # If value is small (< 1000), it's probably in K already
            if val < 1000:
                parsed.append(val * 1000)
            else:
                parsed.append(val)

    if len(parsed) >= 2:
        return min(parsed[0], parsed[1]), max(parsed[0], parsed[1])
    elif len(parsed) == 1:
        return parsed[0], parsed[0]
    return None, None


def _build_description(jr: dict) -> str:
    """Assemble description from all available text fields.

    Confirmed API fields (tested across 40+ jobs):
    - jobSummary: always present, ~250-490 chars
    - coreResponsibilities: always present, list of 4-32 items
    - requirements: always present, list of 5-39 items
    - jobDescription: rare fallback for jobSummary
    - skillSummaries: never seen but handled just in case
    """
    parts = []

    summary = jr.get("jobSummary") or jr.get("jobDescription") or ""
    if summary:
        parts.append(summary)

    responsibilities = jr.get("coreResponsibilities") or []
    if responsibilities:
        if isinstance(responsibilities, list):
            parts.append("Responsibilities:\n" + "\n".join(f"- {r}" for r in responsibilities))
        elif isinstance(responsibilities, str):
            parts.append("Responsibilities:\n" + responsibilities)

    requirements = jr.get("requirements") or []
    if requirements:
        if isinstance(requirements, list):
            parts.append("Requirements:\n" + "\n".join(f"- {r}" for r in requirements))
        elif isinstance(requirements, str):
            parts.append("Requirements:\n" + requirements)

    skills = jr.get("skillSummaries") or []
    if skills:
        if isinstance(skills, list):
            parts.append("Skills:\n" + "\n".join(f"- {s}" for s in skills))
        elif isinstance(skills, str):
            parts.append("Skills:\n" + skills)

    return "\n\n".join(parts)


def _parse_job(raw: dict) -> dict:
    """Parse a Jobright API job result into our standard format."""
    jr = raw.get("jobResult", {}) or {}
    cr = raw.get("companyResult", {}) or {}

    job_id = jr.get("jobId", "")
    apply_link = jr.get("applyLink") or ""
    jobright_url = f"{SITE_BASE}/jobs/info/{job_id}" if job_id else ""

    salary_desc = jr.get("salaryDesc") or ""
    salary_min, salary_max = _parse_salary(salary_desc)

    # Glassdoor rating
    grating = cr.get("grating") or {}
    glassdoor_rating = grating.get("rating") if isinstance(grating, dict) else None

    return {
        "title": jr.get("jobTitle", ""),
        "company": cr.get("companyName", ""),
        "url": apply_link or jobright_url,
        "jobright_url": jobright_url,
        "location": jr.get("jobLocation", ""),
        "description": _build_description(jr),
        "salary_text": salary_desc,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "h1b_status": jr.get("h1BStatus"),
        "seniority": jr.get("jobSeniority"),
        "work_model": jr.get("workModel"),
        "applicants": jr.get("applicantsCount"),
        "posted": jr.get("publishTimeDesc"),
        "company_size": cr.get("companySize"),
        "company_funding": cr.get("fundraisingCurrentStage"),
        "glassdoor_rating": glassdoor_rating,
        "display_score": raw.get("displayScore"),
        "job_id": job_id,
    }


async def run(search: Search) -> dict:
    """Main entry point for jobright search mode. Fetch recommendations/search and save to DB."""
    start_time = time.time()

    try:
        session_id = await _ensure_session()

        # Determine mode: keyword search or recommendations
        use_search = bool(search.search_term and search.search_term.strip())
        results_wanted = search.results_wanted or 100

        all_jobs = []
        reauth_attempted = False

        if use_search:
            # SSR search (no pagination beyond first page of 20)
            raw_list, total = await _fetch_search_ssr(
                search.search_term,
                search.location or "",
            )
            all_jobs = [_parse_job(r) for r in raw_list]
            logger.info(f"Jobright search '{search.search_term}': {len(all_jobs)} jobs (total: {total})")
        else:
            # Paginate recommendations with delay between pages.
            # refresh=true on first page forces Jobright to regenerate its
            # recommendation pool (cache empties after prior scrapes).
            position = 0
            page_size = 20
            empty_pages = 0
            while len(all_jobs) < results_wanted:
                if position > 0:
                    await asyncio.sleep(DELAY_BETWEEN_PAGES)
                try:
                    raw_list = await _fetch_recommendations(
                        session_id, position, page_size,
                        refresh=(position == 0),
                    )
                except SessionExpiredError:
                    if reauth_attempted:
                        logger.error("Jobright: session expired again after re-auth — aborting")
                        break
                    logger.warning("Jobright: session expired mid-scrape (401), re-authenticating...")
                    reauth_attempted = True
                    session_id = await _ensure_session(force_relogin=True)
                    continue  # retry same position with new session

                if raw_list is None:
                    # 403/429 retries exhausted — stop gracefully with what we have
                    logger.warning(f"Jobright: stopping pagination at position={position} due to rate limit")
                    break
                if not raw_list:
                    empty_pages += 1
                    if empty_pages >= 2:
                        break
                    position += page_size
                    continue
                empty_pages = 0
                for r in raw_list:
                    all_jobs.append(_parse_job(r))
                position += page_size
                logger.debug(f"Jobright recommendations: fetched {len(all_jobs)} so far (position={position})")

            all_jobs = all_jobs[:results_wanted]
            logger.info(f"Jobright recommendations: {len(all_jobs)} jobs fetched")

        # Deduplicate by job_id within this batch
        seen_ids = set()
        unique_jobs = []
        for j in all_jobs:
            jid = j.get("job_id")
            if jid and jid in seen_ids:
                continue
            if jid:
                seen_ids.add(jid)
            unique_jobs.append(j)

        # Apply search-level + global title filters
        from backend.models.db import get_global_title_exclude
        _gte_db = SessionLocal()
        try:
            _global_title_excl = get_global_title_exclude(_gte_db)
        finally:
            _gte_db.close()
        include_kw = search.title_include_keywords or []
        exclude_kw = list(set((search.title_exclude_keywords or []) + _global_title_excl))
        kept_jobs = []
        for j in unique_jobs:
            title_lower = j["title"].lower()
            if include_kw and not any(kw.lower() in title_lower for kw in include_kw):
                continue
            if exclude_kw and any(re.search(r'\b' + re.escape(kw) + r'\b', title_lower) for kw in exclude_kw):
                continue
            kept_jobs.append(j)

        # Company exclude (global + per-search)
        db_excl = SessionLocal()
        try:
            global_exclude = json.loads(_get_setting(db_excl, "company_exclude_global", "[]"))
            global_exclude_set = {e.lower() for e in global_exclude}
            search_exclude_set = {e.lower() for e in (search.company_exclude or [])}
            if global_exclude_set or search_exclude_set:
                before = len(kept_jobs)
                kept_jobs = [
                    j for j in kept_jobs
                    if (j.get("company") or "").lower() not in global_exclude_set
                    and (j.get("company") or "").lower() not in search_exclude_set
                ]
                if len(kept_jobs) < before:
                    logger.info(f"Jobright: company exclude removed {before - len(kept_jobs)} jobs")
        finally:
            db_excl.close()

        # Jobright-specific filters: salary requirement + score threshold
        min_score = search.min_fit_score or 0
        require_salary = getattr(search, "require_salary", False)
        if require_salary:
            before = len(kept_jobs)
            kept_jobs = [j for j in kept_jobs if j.get("salary_min")]
            if len(kept_jobs) < before:
                logger.info(f"Jobright: salary filter removed {before - len(kept_jobs)} jobs")
        if min_score > 0:
            before = len(kept_jobs)
            kept_jobs = [j for j in kept_jobs if (j.get("display_score") or 0) >= min_score]
            if len(kept_jobs) < before:
                logger.info(f"Jobright: score filter (<{min_score}) removed {before - len(kept_jobs)} jobs")

        jobs_found = len(kept_jobs)

        # Save to DB
        db = SessionLocal()
        new_jobs = 0
        try:
            existing_ids = get_existing_external_ids(db)

            for j in kept_jobs:
                job_url = j["url"]
                ext_id = make_external_id(j["company"], j["title"], job_url)
                if ext_id in existing_ids:
                    continue

                # Also check jobright URL to avoid duplicates
                if j.get("jobright_url") and j["jobright_url"] != job_url:
                    alt_id = make_external_id(j["company"], j["title"], j["jobright_url"])
                    if alt_id in existing_ids:
                        continue

                content_hash = make_content_hash(j["company"], j["title"])

                job = Job(
                    external_id=ext_id,
                    content_hash=content_hash,
                    company=j["company"],
                    title=j["title"],
                    url=job_url,
                    source="jobright",
                    search_id=search.id,
                    location=j.get("location") or None,
                    description=j.get("description") or None,
                    status="new",
                    seen=False,
                    saved=False,
                )

                # Salary from API
                if j.get("salary_min"):
                    job.salary_min = j["salary_min"]
                    job.salary_source = "posting"
                if j.get("salary_max"):
                    job.salary_max = j["salary_max"]
                    job.salary_source = "posting"

                # H-1B check + language check + salary extraction
                try:
                    from backend.analyzer.h1b_checker import check_job_h1b
                    from backend.analyzer.salary_extractor import apply_salary_to_job
                    await check_job_h1b(job, db)
                    from backend.models.db import find_company_by_name
                    company_obj = find_company_by_name(db, j["company"])
                    h1b_median = company_obj.h1b_median_salary if company_obj else None
                    apply_salary_to_job(job, h1b_median)
                except Exception as e:
                    logger.warning(f"Inline analysis failed for {j['title']}: {e}")

                if job.h1b_jd_flag:
                    logger.info(f"Skipping job (body exclusion): {j['title']} — {job.h1b_jd_snippet}")
                    continue

                try:
                    with db.begin_nested():
                        db.add(job)
                        db.flush()
                    new_jobs += 1
                    existing_ids.add(ext_id)
                except IntegrityError:
                    logger.debug(f"Duplicate external_id for '{j['title']}' at {j.get('company')}, skipping")
                    continue

            # Update last_run_at
            search_obj = db.query(Search).filter(Search.id == search.id).first()
            if search_obj:
                search_obj.last_run_at = datetime.now(timezone.utc)

            db.commit()
        finally:
            db.close()

        duration = time.time() - start_time
        from backend.activity import log_activity
        log_activity("scrape", f"Jobright '{search.name}': {new_jobs} new / {jobs_found} found in {duration:.1f}s")

        return {"jobs_found": jobs_found, "new_jobs": new_jobs, "error": None, "duration": duration}

    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Jobright scrape failed for '{search.name}': {e}")
        from backend.activity import log_activity
        log_activity("scrape", f"Jobright '{search.name}' failed: {e}")
        return {"jobs_found": 0, "new_jobs": 0, "error": str(e), "duration": duration}


async def preview(search, db) -> dict:
    """Test endpoint handler — fetch jobs, apply filters, return results without saving."""
    start_time = time.time()

    try:
        session_id = await _ensure_session()

        use_search = bool(search.search_term and search.search_term.strip())
        results_wanted = search.results_wanted or 100

        all_jobs = []
        reauth_attempted = False

        if use_search:
            raw_list, total = await _fetch_search_ssr(
                search.search_term,
                search.location or "",
            )
            all_jobs = [_parse_job(r) for r in raw_list]
        else:
            position = 0
            page_size = 20
            empty_pages = 0
            while len(all_jobs) < results_wanted:
                if position > 0:
                    await asyncio.sleep(DELAY_BETWEEN_PAGES)
                try:
                    raw_list = await _fetch_recommendations(
                        session_id, position, page_size,
                        refresh=(position == 0),
                    )
                except SessionExpiredError:
                    if reauth_attempted:
                        logger.error("Jobright test: session expired again after re-auth — aborting")
                        break
                    logger.warning("Jobright test: session expired (401), re-authenticating...")
                    reauth_attempted = True
                    session_id = await _ensure_session(force_relogin=True)
                    continue

                if raw_list is None:
                    logger.warning(f"Jobright test: stopping at position={position} due to rate limit")
                    break
                if not raw_list:
                    empty_pages += 1
                    if empty_pages >= 2:
                        break
                    position += page_size
                    continue
                empty_pages = 0
                for r in raw_list:
                    all_jobs.append(_parse_job(r))
                position += page_size
            all_jobs = all_jobs[:results_wanted]

        # Deduplicate by job_id
        seen_ids = set()
        unique_jobs = []
        for j in all_jobs:
            jid = j.get("job_id")
            if jid and jid in seen_ids:
                continue
            if jid:
                seen_ids.add(jid)
            unique_jobs.append(j)

        duration = round(time.time() - start_time, 1)
        raw_count = len(unique_jobs)

        if not unique_jobs:
            return {
                "search_name": search.name,
                "duration": duration,
                "raw_count": 0,
                "after_filter": 0,
                "source_breakdown": {"jobright": 0},
                "company_breakdown": {},
                "include_keywords": search.title_include_keywords or [],
                "exclude_keywords": search.title_exclude_keywords or [],
                "company_filter": search.company_filter or [],
                "company_exclude": search.company_exclude or [],
                "jobs": [],
                "config": {
                    "mode": "jobright",
                    "search_term": search.search_term or "",
                    "results_wanted": results_wanted,
                },
            }

        from backend.models.db import get_global_title_exclude
        _global_title_excl = get_global_title_exclude(db)
        include_kw = search.title_include_keywords or []
        exclude_kw = list(set((search.title_exclude_keywords or []) + _global_title_excl))
        min_score = search.min_fit_score or 0
        require_salary = getattr(search, "require_salary", False)

        # Company exclude sets
        global_exclude_row = db.query(Setting).filter(Setting.key == "company_exclude_global").first()
        global_exclude = json.loads(global_exclude_row.value) if global_exclude_row and global_exclude_row.value else []
        global_exclude_set = {e.lower() for e in global_exclude}
        search_exclude = [e.lower() for e in (search.company_exclude or [])]
        search_exclude_set = set(search_exclude)
        all_exclude = list(global_exclude_set | search_exclude_set)

        # Body exclusion phrases (H-1B + language)
        body_row = db.query(Setting).filter(Setting.key == "body_exclusion_phrases").first()
        body_phrases = []
        if body_row and body_row.value:
            try:
                body_phrases = json.loads(body_row.value)
            except json.JSONDecodeError:
                pass

        # Company breakdown
        from collections import Counter
        company_counts = Counter(j["company"] for j in unique_jobs if j.get("company"))
        company_breakdown = dict(company_counts.most_common(20))

        results = []
        for j in unique_jobs:
            title = j["title"]
            title_lower = title.lower()
            kept = True
            reason = None

            # Title filters
            if include_kw and not any(kw.lower() in title_lower for kw in include_kw):
                kept = False
                reason = f"No match for: {', '.join(include_kw)}"
            if kept and exclude_kw:
                matched = [kw for kw in exclude_kw if re.search(r'\b' + re.escape(kw) + r'\b', title_lower)]
                if matched:
                    kept = False
                    reason = f"Excluded by: {', '.join(matched)}"

            # Company exclude
            if kept and (global_exclude_set or search_exclude_set):
                company_lower = (j.get("company") or "").lower()
                if company_lower in global_exclude_set:
                    kept = False
                    reason = f"Company excluded (global): {company_lower}"
                elif company_lower in search_exclude_set:
                    kept = False
                    reason = f"Company excluded: {company_lower}"

            # Body exclusion description check (H-1B + language)
            if kept and body_phrases:
                desc = j.get("description") or ""
                if desc:
                    from backend.analyzer.h1b_checker import scan_jd_for_h1b_flags
                    body_result = scan_jd_for_h1b_flags(desc, body_phrases)
                    if body_result["jd_flag"]:
                        kept = False
                        reason = f"Body exclusion: {body_result['jd_snippet'][:80] if body_result['jd_snippet'] else 'matched'}"

            # Salary requirement
            if kept and require_salary and not j.get("salary_min"):
                kept = False
                reason = "No salary info"

            # Jobright score threshold
            if kept and min_score > 0:
                score = j.get("display_score") or 0
                if score < min_score:
                    kept = False
                    reason = f"Score {score} < {min_score}"

            if not kept and not reason:
                reason = "Filtered"

            salary = None
            if j.get("salary_min"):
                salary = f"${j['salary_min']:,}"
                if j.get("salary_max") and j["salary_max"] != j["salary_min"]:
                    salary += f" – ${j['salary_max']:,}"

            desc = j.get("description") or ""
            has_desc = bool(desc and len(desc) > 50)

            results.append({
                "title": title,
                "company": j.get("company", ""),
                "url": j.get("url", ""),
                "jobright_url": j.get("jobright_url", ""),
                "source": "jobright",
                "location": j.get("location", ""),
                "salary": salary,
                "has_description": has_desc,
                "desc_length": len(desc) if has_desc else 0,
                "kept": kept,
                "reason": reason,
                "seniority": j.get("seniority"),
                "work_model": j.get("work_model"),
                "h1b_status": j.get("h1b_status"),
                "display_score": j.get("display_score"),
                "posted": j.get("posted"),
            })

        after_filter = sum(1 for r in results if r["kept"])

        return {
            "search_name": search.name,
            "duration": duration,
            "raw_count": raw_count,
            "after_filter": after_filter,
            "source_breakdown": {"jobright": raw_count},
            "company_breakdown": company_breakdown,
            "include_keywords": include_kw,
            "exclude_keywords": exclude_kw,
            "company_filter": search.company_filter or [],
            "company_exclude": all_exclude,
            "jobs": results,
            "config": {
                "mode": "jobright",
                "search_term": search.search_term or "",
                "results_wanted": results_wanted,
            },
        }

    except Exception as e:
        duration = round(time.time() - start_time, 1)
        return {
            "search_name": search.name,
            "error": str(e),
            "duration": duration,
            "config": {
                "mode": "jobright",
                "search_term": search.search_term or "",
            },
        }
