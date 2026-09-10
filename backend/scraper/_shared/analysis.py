"""Shared inline-analysis helpers: consolidates check_job_h1b + apply_salary_to_job + apply_arrangement_to_job with non-fatal error handling so every scraper source calls them consistently."""
import logging
from backend.analyzer.h1b_checker import check_job_h1b
from backend.analyzer.salary_extractor import apply_salary_to_job
from backend.analyzer.work_arrangement import apply_arrangement_to_job
from backend.analyzer.location import apply_location_to_job

logger = logging.getLogger("jobnavigator.scraper.analysis")


async def analyze_inline(job, db=None, h1b_median=None, arrangement=None) -> None:
    """Run h1b check + salary extraction + work-arrangement extraction inline on a Job; non-fatal, each step's errors are logged and swallowed independently. `arrangement` is the source's own structured field, when it has one."""
    try:
        await check_job_h1b(job, db=db)
    except Exception as e:
        logger.warning(
            "analyze_inline: h1b check failed for %s: %s",
            getattr(job, "id", "?"), e,
        )

    # Median salary comes from the VisaCache entry check_job_h1b just resolved and
    # stashed on the job, avoiding an extra lookup.
    if h1b_median is None:
        h1b_median = getattr(job, "_h1b_median", None)

    try:
        apply_salary_to_job(job, h1b_median=h1b_median)
    except Exception as e:
        logger.warning(
            "analyze_inline: salary extraction failed for %s: %s",
            getattr(job, "id", "?"), e,
        )

    try:
        apply_arrangement_to_job(job, structured=arrangement)
    except Exception as e:
        logger.warning(
            "analyze_inline: arrangement extraction failed for %s: %s",
            getattr(job, "id", "?"), e,
        )

    try:
        apply_location_to_job(job)
    except Exception as e:
        logger.warning(
            "analyze_inline: location parsing failed for %s: %s",
            getattr(job, "id", "?"), e,
        )
