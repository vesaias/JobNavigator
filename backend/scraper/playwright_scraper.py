"""Playwright direct career page scraper + URL mode scraper."""
import asyncio
import json
import logging
import re
import time
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import httpx

from sqlalchemy.exc import IntegrityError

from backend.models.db import SessionLocal, Company, Job, ScrapeLog, Search, get_existing_external_ids
from backend.scraper.deduplicator import make_external_id, make_content_hash

logger = logging.getLogger("jobnavigator.playwright")


# ── Re-exports from _shared (Task 2) ──────────────────────────────────────────
from backend.scraper._shared.urls import (  # noqa: F401
    _get_url_tracking_params, _clean_application_url,
    host_matches, path_contains,
)
# Back-compat aliases for existing callers inside this file
_host_matches = host_matches
_path_contains = path_contains


# ── Re-exports from _shared (Task 3) ──────────────────────────────────────────
from backend.scraper._shared.filters import (  # noqa: F401
    GARBAGE_TITLES, GARBAGE_SUBSTRINGS, _LOCALE_NAMES,
    _tokenize, _parse_expr, _parse_and, _parse_atom, _eval_expr,
    match_title_expr, _validate_job, _apply_company_filters,
)


# ── Re-exports from ats/_descriptions (Task 6) ────────────────────────────────
from backend.scraper.ats._descriptions import (  # noqa: F401
    _fetch_job_description, _fetch_description_ats, _fetch_descriptions_parallel,
)


# ── Re-exports from ats/workday (Task 7) ──────────────────────────────────────
from backend.scraper.ats.workday import (  # noqa: F401
    is_workday, scrape as _scrape_workday, _parse_workday_url, _LOCALE_PATH_RE,
)
_is_workday = is_workday  # back-compat alias


# ── Re-exports from ats/greenhouse (Task 8 follow-up fix) ────────────────────
from backend.scraper.ats.greenhouse import (  # noqa: F401
    is_greenhouse, scrape as _scrape_greenhouse, _parse_greenhouse_url,
)
_is_greenhouse = is_greenhouse  # back-compat alias for internal calls at lines 889, 890, 1110


# ── Re-exports from ats/lever (Task 9) ────────────────────────────────────────
from backend.scraper.ats.lever import (  # noqa: F401
    is_lever, scrape as _scrape_lever,
)
_is_lever = is_lever  # back-compat alias


# ── Re-exports from ats/ashby (Task 10) ───────────────────────────────────────
from backend.scraper.ats.ashby import (  # noqa: F401
    is_ashby, scrape as _scrape_ashby,
)
_is_ashby = is_ashby  # back-compat alias


# ── Re-exports from ats/oracle_hcm (Task 11) ──────────────────────────────────
from backend.scraper.ats.oracle_hcm import (  # noqa: F401
    is_oracle_hcm, scrape as _scrape_oracle_hcm,
    _oracle_hcm_host, _ORACLE_HCM_HOSTS,
)
_is_oracle_hcm = is_oracle_hcm  # back-compat alias


# ── Re-exports from ats/phenom (Task 12) ──────────────────────────────────────
from backend.scraper.ats.phenom import (  # noqa: F401
    is_phenom, scrape as _scrape_phenom, _parse_phenom_url,
)
_is_phenom_post = is_phenom  # back-compat alias (note: old name had _post suffix)


# ── Re-exports from ats/talentbrew (Task 13) ─────────────────────────────────
from backend.scraper.ats.talentbrew import (  # noqa: F401
    is_talentbrew, scrape as _scrape_talentbrew_ajax,
)
_is_talentbrew_ajax = is_talentbrew  # back-compat alias (note: old name had _ajax suffix)


# ── Re-exports from ats/rippling (Task 14) ───────────────────────────────────
from backend.scraper.ats.rippling import (  # noqa: F401
    is_rippling, scrape as _scrape_rippling, _parse_rippling_url,
)
_is_rippling = is_rippling  # back-compat alias


# Back-compat re-exports — Task 1 (migrated to _shared/browser.py)
from backend.scraper._shared.browser import (  # noqa: F401
    _STEALTH_ARGS, _USER_AGENT,
    _get_browser, _new_page, _close_page,
)


# ── Re-exports from ats/generic (Task 16) ────────────────────────────────────
from backend.scraper.ats.generic import (  # noqa: F401
    _setup_route_blocks, _wait_for_content,
    _extract_job_links_from_page, _extract_all_pages, _click_next_page,
)


# ── Re-exports from ats/meta + ats/google (Task 15) ──────────────────────────
from backend.scraper.ats.meta import (  # noqa: F401
    is_meta, scrape as _scrape_meta_careers,
)
_is_meta_careers = is_meta

from backend.scraper.ats.google import (  # noqa: F401
    is_google, scrape as _scrape_google_careers,
)
_is_google_careers = is_google


# ── Re-exports from sources/company_pages (Task 17) ──────────────────────────
from backend.scraper.sources.company_pages import (  # noqa: F401
    scrape_single_career_page, scrape_career_pages, scrape_url_mode,
)


# ── Re-exports from sources/levelsfyi (Task 21) ──────────────────────────────
from backend.scraper.sources.levelsfyi import (  # noqa: F401
    _is_levelsfyi, _parse_levelsfyi_salary,
    _levelsfyi_extract_jobs_from_card, _levelsfyi_extract_detail,
    _scrape_levelsfyi,
    run as scrape_levelsfyi_mode,
)
