"""LinkedIn Extension source — Voyager-API enrichment for job IDs from Chrome extension.

The Chrome extension ("The Navigator") captures LinkedIn job IDs passively as the
user browses /jobs/collections/. The backend receives those IDs via
POST /api/jobs/linkedin-import and enriches each via the LinkedIn Voyager API
(using the linkedin-api pip library) to get title, company, location, apply URL,
description, etc.

This runs as a background task (not blocking the POST response).

Public entry point:
- `enrich(linkedin_ids, db=None)` — background enrichment of a list of LinkedIn
  job IDs. Follows `sources/*` convention. Uses its own DB session via
  `SessionLocal()` internally (the `db` kwarg exists for future flexibility).
"""
import asyncio
import logging

from backend.models.db import (
    SessionLocal, Job,
    build_company_lookup, get_existing_external_ids, find_company_by_name,
)
from backend.scraper._shared.dedup import make_external_id, make_content_hash
from backend.analyzer.salary_extractor import apply_salary_to_job
from backend.analyzer.h1b_checker import check_job_h1b, determine_h1b_verdict

logger = logging.getLogger("jobnavigator.jobs")

# In-memory LinkedIn import progress tracker (shared with routes_jobs for the
# progress-polling endpoint). Import this from routes_jobs via the module path.
_linkedin_import_progress: dict = {}


async def enrich(linkedin_ids: list[str], db=None):
    """Background: fetch LinkedIn job data via Voyager API, extract apply URLs, create jobs."""
    import re
    from linkedin_api import Linkedin as LinkedinAPI
    from backend.models.db import Setting, Search

    logger.info(f"LinkedIn import: fetching {len(linkedin_ids)} jobs via Voyager API")

    db = SessionLocal()
    try:
        # Pre-check: skip LinkedIn IDs already in the DB (avoid unnecessary Voyager API calls)
        existing_li_ids = {
            r[0] for r in db.query(Job.linkedin_job_id).filter(Job.linkedin_job_id != None).all()
        }
        pre_dedup = [lid for lid in linkedin_ids if lid not in existing_li_ids]
        pre_skipped = len(linkedin_ids) - len(pre_dedup)
        if pre_skipped:
            logger.info(f"LinkedIn import: {pre_skipped}/{len(linkedin_ids)} already in DB, skipping Voyager calls")

        # Init progress tracker
        _linkedin_import_progress.update({
            "total": len(linkedin_ids),
            "pre_skipped": pre_skipped,
            "processed": 0,
            "imported": 0,
            "skipped": pre_skipped,
            "status": "running",
        })

        if not pre_dedup:
            _linkedin_import_progress["status"] = "done"
            logger.info("LinkedIn import: all IDs already exist, nothing to fetch")
            return

        # Get mock account credentials from settings
        li_email = db.query(Setting).filter(Setting.key == "linkedin_mock_email").first()
        li_pass = db.query(Setting).filter(Setting.key == "linkedin_mock_password").first()
        if not li_email or not li_email.value or not li_pass or not li_pass.value:
            logger.error("LinkedIn import: linkedin_mock_email / linkedin_mock_password not set")
            _linkedin_import_progress["status"] = "error"
            return

        # Load the LinkedIn Extension search for filters + linking
        ext_search = db.query(Search).filter(Search.search_mode == "linkedin_extension").first()

        # Login via Voyager API (sync — offload to thread)
        try:
            api = await asyncio.to_thread(LinkedinAPI, li_email.value, li_pass.value)
        except Exception as e:
            logger.error(f"LinkedIn import: login failed: {e}")
            _linkedin_import_progress["status"] = "error"
            return

        existing_ext_ids = get_existing_external_ids(db)
        company_lookup = build_company_lookup(db)
        imported = 0
        skipped = pre_skipped

        for lid in pre_dedup:
            linkedin_url = f"https://www.linkedin.com/jobs/view/{lid}"
            try:
                # Voyager API call (sync — offload to thread)
                job_data = await asyncio.to_thread(api.get_job, lid)
                if not job_data or not job_data.get("title"):
                    logger.warning(f"LinkedIn {lid}: no data returned, skipping")
                    skipped += 1
                    continue

                title = (job_data.get("title") or "").strip()

                # Company — nested in companyDetails
                company = ""
                for v in (job_data.get("companyDetails") or {}).values():
                    if isinstance(v, dict) and "companyResolutionResult" in v:
                        company = (v["companyResolutionResult"].get("name") or "").strip()
                        break

                if not title or not company:
                    logger.warning(f"LinkedIn {lid}: missing title/company, skipping")
                    skipped += 1
                    continue

                # Apply search filters (title include/exclude, company exclude)
                if ext_search:
                    title_lower = title.lower()
                    # Title include filter
                    include_kw = ext_search.title_include_keywords or []
                    if include_kw and not any(kw.lower() in title_lower for kw in include_kw):
                        logger.info(f"LinkedIn {lid}: title '{title}' doesn't match include filter, skipping")
                        skipped += 1
                        continue
                    # Title exclude filter (merge global)
                    from backend.models.db import get_global_title_exclude
                    _global_te = get_global_title_exclude(db)
                    exclude_kw = list(set((ext_search.title_exclude_keywords or []) + _global_te))
                    if exclude_kw:
                        pattern = "|".join(r'\b' + re.escape(kw) + r'\b' for kw in exclude_kw)
                        if re.search(pattern, title, re.IGNORECASE):
                            logger.info(f"LinkedIn {lid}: title '{title}' matches exclude filter, skipping")
                            skipped += 1
                            continue
                    # Company exclude filter
                    company_excl = ext_search.company_exclude or []
                    if company_excl and company.lower().strip() in {c.lower().strip() for c in company_excl}:
                        logger.info(f"LinkedIn {lid}: company '{company}' excluded, skipping")
                        skipped += 1
                        continue

                # Location
                location = (job_data.get("formattedLocation") or "").strip()

                # Description
                description = (job_data.get("description", {}).get("text") or "").strip()

                # Apply URL from applyMethod
                apply_url = ""
                for v in (job_data.get("applyMethod") or {}).values():
                    if isinstance(v, dict):
                        apply_url = (v.get("companyApplyUrl") or "").strip()
                        break

                # Use apply_url for dedup + display, fall back to linkedin URL
                job_url = apply_url if apply_url else linkedin_url

                ext_id = make_external_id(company, title, job_url)
                c_hash = make_content_hash(company, title)
                alt_ext_id = make_external_id(company, title, linkedin_url) if apply_url else None

                if ext_id in existing_ext_ids:
                    skipped += 1
                    continue
                if alt_ext_id and alt_ext_id in existing_ext_ids:
                    skipped += 1
                    continue

                job = Job(
                    external_id=ext_id,
                    content_hash=c_hash,
                    company=company,
                    title=title,
                    url=job_url,
                    source="linkedin_extension",
                    linkedin_job_id=lid,
                    search_id=ext_search.id if ext_search else None,
                    location=location,
                    description=description,
                    status="new",
                )

                # Salary extraction from description
                comp_obj = find_company_by_name(db, company) or company_lookup.get(company.lower().strip())
                h1b_median = comp_obj.h1b_median_salary if comp_obj else None
                apply_salary_to_job(job, h1b_median)

                # H-1B + language check
                try:
                    await check_job_h1b(job, db)
                    job.h1b_verdict = determine_h1b_verdict(
                        job.h1b_company_lca_count, job.h1b_jd_flag
                    )
                except Exception as e:
                    logger.warning(f"LinkedIn {lid}: analysis error: {e}")
                    _linkedin_import_progress["errors"] = (
                        _linkedin_import_progress.get("errors", 0) + 1
                    )
                    _linkedin_import_progress.setdefault("error_details", []).append({
                        "lid": lid,
                        "stage": "analysis",
                        "error": str(e)[:200],
                    })

                # Skip flagged jobs (same as other scrapers)
                if job.h1b_jd_flag:
                    _phrase = getattr(job, "_h1b_matched_phrase", None) or "?"
                    logger.info(f"LinkedIn {lid} ({job.title!r}): skipping (body exclusion) — matched phrase: {_phrase!r}")
                    skipped += 1
                    continue

                db.add(job)
                db.commit()
                imported += 1
                existing_ext_ids.add(ext_id)
                logger.info(f"LinkedIn {lid}: imported '{title}' at '{company}' -> {job_url[:80]}")

            except Exception as e:
                logger.warning(f"LinkedIn {lid}: failed: {e}")
                db.rollback()
                skipped += 1
                _linkedin_import_progress["errors"] = (
                    _linkedin_import_progress.get("errors", 0) + 1
                )
                _linkedin_import_progress.setdefault("error_details", []).append({
                    "lid": lid,
                    "stage": "fetch",
                    "error": str(e)[:200],
                })

            # Update progress tracker
            _linkedin_import_progress.update({
                "processed": _linkedin_import_progress["processed"] + 1,
                "imported": imported,
                "skipped": skipped,
            })

            await asyncio.sleep(1)  # Rate limit

        _linkedin_import_progress["status"] = "done"
        logger.info(f"LinkedIn import: done — imported {imported}, skipped {skipped}/{len(linkedin_ids)}")

        # Trigger auto CV scoring if enabled on the extension search
        if imported > 0 and ext_search and ext_search.auto_scoring_depth in ("light", "full"):
            try:
                from backend.analyzer.cv_scorer import analyze_unscored_jobs
                await analyze_unscored_jobs(status="new")
                logger.info("LinkedIn import: auto-scoring triggered")
            except Exception as e:
                logger.warning(f"LinkedIn import: auto-scoring failed: {e}")
                _linkedin_import_progress["errors"] = (
                    _linkedin_import_progress.get("errors", 0) + 1
                )
                _linkedin_import_progress.setdefault("error_details", []).append({
                    "lid": None,
                    "stage": "auto_scoring",
                    "error": str(e)[:200],
                })
    finally:
        db.close()
