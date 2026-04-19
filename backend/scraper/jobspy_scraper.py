"""JobSpy multi-board scraper. Reads all config from DB before each run."""
import asyncio
import json
import logging
import re
import time
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.models.db import SessionLocal, Search, Job, ScrapeLog, Setting, get_existing_external_ids
from backend.scraper.deduplicator import make_external_id, make_content_hash

logger = logging.getLogger("jobnavigator.scraper")


def get_setting_value(db: Session, key: str, default: str = "") -> str:
    row = db.query(Setting).filter(Setting.key == key).first()
    return row.value if row else default


def apply_title_filters(jobs_df, include_keywords: list, exclude_keywords: list):
    """Filter jobs by title include/exclude keywords (whole-word matching).
    Returns (kept_df, rejected_df)."""
    import pandas as pd

    if jobs_df is None or jobs_df.empty:
        return jobs_df, pd.DataFrame()

    mask = pd.Series(True, index=jobs_df.index)

    if include_keywords:
        pattern = "|".join(include_keywords)
        mask &= jobs_df["title"].str.contains(pattern, case=False, na=False)

    if exclude_keywords:
        pattern = "|".join(r'\b' + re.escape(kw) + r'\b' for kw in exclude_keywords)
        mask &= ~jobs_df["title"].str.contains(pattern, case=False, na=False, regex=True)

    return jobs_df[mask], jobs_df[~mask]


def apply_company_filter(jobs_df, company_filter: list):
    """Filter to specific companies if filter is non-empty (exact match, case-insensitive)."""
    if not company_filter or jobs_df is None or jobs_df.empty:
        return jobs_df
    cf_set = {cf.lower() for cf in company_filter}
    return jobs_df[jobs_df["company"].str.lower().isin(cf_set)]



# Back-compat shim — Task 18 (moved to sources/jobspy)
# `run_jobspy_search` is re-exported as the synchronous entry point so existing
# `asyncio.to_thread(run_jobspy_search, ...)` calls in this module continue to work.
from backend.scraper.sources.jobspy import _run_sync as run_jobspy_search  # noqa: F401,E402


# Back-compat shims — Task 23 (moved to orchestrator.py)
from backend.scraper.orchestrator import (  # noqa: F401,E402
    run_all as run_all_searches,
    _run_search_by_id as run_single_search,
)
