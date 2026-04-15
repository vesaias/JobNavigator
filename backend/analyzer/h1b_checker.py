"""H-1B company LCA data checker + JD body scan."""
import json
import logging
import re
from datetime import datetime, timezone

import httpx

from backend.models.db import SessionLocal, Company, Job, Setting

logger = logging.getLogger("jobnavigator.h1b")


async def fetch_company_h1b_data(company_name: str, h1b_slug: str = None) -> dict:
    """Scrape myvisajobs.com for company H-1B LCA data."""
    try:
        # Use explicit slug if provided, otherwise auto-generate from name
        if h1b_slug:
            slug = h1b_slug
        else:
            slug = company_name.lower().replace(" ", "-").replace(".", "").replace(",", "")
        url = f"https://www.myvisajobs.com/employer/{slug}/"

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            resp = await client.get(url, headers=headers)

            # Detect redirect to generic employers page (slug not found)
            if str(resp.url).rstrip("/").endswith("/employers"):
                logger.warning(f"H-1B slug '{slug}' redirected to generic page for {company_name}")
                return {"lca_count": 0, "approval_rate": 0, "median_salary": 0}

            if resp.status_code != 200:
                logger.warning(f"H-1B page returned {resp.status_code} for {company_name}")
                return {"lca_count": 0, "approval_rate": 0, "median_salary": 0}

            text = resp.text

            lca_count = 0
            approval_rate = 0.0
            median_salary = 0

            # LCA count: "LCA for H-1B: 9,362" or "filed 9,362 labor condition applications"
            lca_match = re.search(r'LCA for H-1B:\s*([\d,]+)', text)
            if not lca_match:
                lca_match = re.search(r'filed\s+([\d,]+)\s+labor condition', text, re.IGNORECASE)
            if lca_match:
                lca_count = int(lca_match.group(1).replace(",", ""))

            # Approval rate: compute from certified/total if available
            # Look for "Certified" count in the most recent year row
            certified_match = re.search(r'certified[^>]*>\s*([\d,]+)', text, re.IGNORECASE)
            if certified_match and lca_count > 0:
                certified = int(certified_match.group(1).replace(",", ""))
                approval_rate = round((certified / lca_count) * 100, 1)

            # Salary: "H-1B Salary [$172,325]" or "$172,325" in salary table
            salary_match = re.search(r'H-1B Salary.*?\$([\d,]+)', text, re.IGNORECASE)
            if not salary_match:
                # Fallback: look for dollar amounts near "salary" or "average"
                salary_match = re.search(r'\$([\d]{2,3},\d{3})', text)
            if salary_match:
                median_salary = int(salary_match.group(1).replace(",", ""))

            return {
                "lca_count": lca_count,
                "approval_rate": approval_rate,
                "median_salary": median_salary,
            }

    except Exception as e:
        logger.error(f"H-1B fetch failed for {company_name}: {e}")
        return {"lca_count": 0, "approval_rate": 0, "median_salary": 0}


async def refresh_all_h1b():
    """Refresh H-1B LCA data for all companies. Skips companies checked within 90 days."""
    from datetime import timedelta
    db = SessionLocal()
    try:
        companies = db.query(Company).all()
        cutoff = datetime.now(timezone.utc) - timedelta(days=90)
        to_refresh = [c for c in companies if not c.h1b_last_checked or c.h1b_last_checked < cutoff]
        logger.info(f"Refreshing H-1B data: {len(to_refresh)}/{len(companies)} companies need update (90-day cache)")

        updated = 0
        for company in to_refresh:
            try:
                data = await fetch_company_h1b_data(company.name, h1b_slug=company.h1b_slug)

                # Only update if we got meaningful data (skip zeros that would overwrite good cached data)
                if data["lca_count"] > 0 or (company.h1b_lca_count or 0) == 0:
                    company.h1b_lca_count = data["lca_count"]
                    company.h1b_approval_rate = data["approval_rate"]
                    company.h1b_median_salary = data["median_salary"]
                    company.h1b_last_checked = datetime.now(timezone.utc)
                    updated += 1

                logger.info(
                    f"H-1B {company.name}: LCAs={data['lca_count']}, "
                    f"rate={data['approval_rate']}%, salary=${data['median_salary']}"
                )
            except Exception as e:
                logger.error(f"H-1B refresh failed for {company.name}: {e}")
                continue  # skip, preserve existing data

        db.commit()

        from backend.activity import log_activity
        log_activity("h1b", f"H-1B refresh complete: {updated}/{len(companies)} companies updated", db=db)
        db.commit()

    finally:
        db.close()


async def fetch_h1b_for_company_id(company_id: str):
    """Fetch and save H-1B data for a single company by ID. Safe to fire-and-forget."""
    # Read company name/slug, then close DB before the slow HTTP call
    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.id == company_id).first()
        if not company:
            return
        name, slug = company.name, company.h1b_slug
    finally:
        db.close()

    try:
        data = await fetch_company_h1b_data(name, h1b_slug=slug)
        # Reopen DB only to save results (ms-level hold)
        db2 = SessionLocal()
        try:
            comp = db2.query(Company).filter(Company.id == company_id).first()
            if comp:
                comp.h1b_lca_count = data["lca_count"]
                comp.h1b_approval_rate = data["approval_rate"]
                comp.h1b_median_salary = data["median_salary"]
                comp.h1b_last_checked = datetime.now(timezone.utc)
                db2.commit()
                logger.info(f"H-1B auto-fetched for {name}: LCAs={data['lca_count']}, rate={data['approval_rate']}%, salary=${data['median_salary']}")
        finally:
            db2.close()
    except Exception as e:
        logger.error(f"H-1B auto-fetch failed for company {company_id}: {e}")


def scan_jd_for_h1b_flags(description: str, exclusion_phrases: list) -> dict:
    """Scan job description for H-1B exclusion phrases.
    Returns dict with jd_flag, jd_snippet.
    """
    if not description:
        return {"jd_flag": False, "jd_snippet": None}

    desc_lower = description.lower()

    for phrase in exclusion_phrases:
        if phrase.lower() in desc_lower:
            # Extract snippet — find the phrase in context
            idx = desc_lower.index(phrase.lower())
            start = max(0, idx - 50)
            end = min(len(description), idx + len(phrase) + 50)
            snippet = description[start:end].strip()
            return {"jd_flag": True, "jd_snippet": snippet}

    return {"jd_flag": False, "jd_snippet": None}


def determine_h1b_verdict(lca_count: int, jd_flag: bool) -> str:
    """Determine overall H-1B verdict.
    likely (>50 LCAs, no JD flag)
    unlikely (<10 LCAs or JD flag)
    unknown (no data)
    """
    if jd_flag:
        return "unlikely"
    if lca_count > 50:
        return "likely"
    if lca_count >= 10:
        return "possible"
    if lca_count > 0:
        return "unlikely"
    return "unknown"


async def check_job_h1b(job: Job, db) -> None:
    """Run H-1B checks on a single job and update its fields.

    Company H-1B data is cached on the Company record and reused for 90 days.
    Live MyVisaJobs lookups only happen during the dedicated h1b_cron refresh.
    Per-job: only the body exclusion scan runs (no HTTP calls).
    """
    from backend.models.db import find_company_by_name
    from datetime import timedelta
    company = find_company_by_name(db, job.company or "")
    lca_count = 0
    approval_rate = 0.0

    if company:
        # Use cached company H-1B data (refreshed by h1b_cron)
        lca_count = company.h1b_lca_count or 0
        approval_rate = company.h1b_approval_rate or 0.0
        job.h1b_company_lca_count = lca_count
        job.h1b_company_approval_rate = approval_rate
    # No Company record = no H-1B data (skip live lookup — too slow for inline use)

    # Layer 2: JD body scan
    exclusion_setting = db.query(Setting).filter(Setting.key == "body_exclusion_phrases").first()
    phrases = []
    if exclusion_setting:
        try:
            phrases = json.loads(exclusion_setting.value)
        except json.JSONDecodeError:
            phrases = []

    jd_result = scan_jd_for_h1b_flags(job.description or "", phrases)
    job.h1b_jd_flag = jd_result["jd_flag"]
    job.h1b_jd_snippet = jd_result["jd_snippet"]

    # Overall verdict
    job.h1b_verdict = determine_h1b_verdict(lca_count, jd_result["jd_flag"])


