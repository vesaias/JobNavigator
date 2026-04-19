"""Shared inline-analysis helpers for scraped jobs.

Every source (company_pages, jobspy, linkedin_personal, linkedin_extension,
jobright, levelsfyi) calls check_job_h1b + apply_salary_to_job after extracting
a Job record. This wrapper consolidates both calls with non-fatal error handling
so one analyzer bug doesn't prevent a scrape batch from completing.
"""
import logging
from backend.analyzer.h1b_checker import check_job_h1b
from backend.analyzer.salary_extractor import apply_salary_to_job

logger = logging.getLogger("jobnavigator.scraper.analysis")


async def analyze_inline(job, db=None, h1b_median=None) -> None:
    """Run h1b check + salary extraction inline on a Job object.

    Non-fatal — errors are logged per-step and swallowed so one failure doesn't
    prevent the other from running and doesn't abort the scrape batch.
    """
    try:
        await check_job_h1b(job, db=db)
    except Exception as e:
        logger.warning(
            "analyze_inline: h1b check failed for %s: %s",
            getattr(job, "id", "?"), e,
        )

    try:
        apply_salary_to_job(job, h1b_median=h1b_median)
    except Exception as e:
        logger.warning(
            "analyze_inline: salary extraction failed for %s: %s",
            getattr(job, "id", "?"), e,
        )
