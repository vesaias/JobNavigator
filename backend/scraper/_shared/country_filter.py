"""Allowed job countries: a new job whose known locations all lie outside the account's
`job_countries_allowed` list is stored as ignored (like any filtered job), from every source.

The list holds ISO country codes as `JobLocation.country` stores them ("US", "GB", "DE", "CH");
"UK" is read as "GB". An empty list keeps every job. A job with no known country (an
unparsed or remote-only location) always passes: the filter only drops what it can place.

Runs in a before_flush listener after the posting-link one, so every scraper is covered
without each source calling it, and only for jobs being inserted as New.
"""
import json
import logging

logger = logging.getLogger("jobnavigator.country_filter")

ALIASES = {"UK": "GB"}


def allowed_countries(db) -> set:
    """The account's allowed codes, upper-cased; empty set = no filter."""
    from backend.accounts.settings import get_setting
    try:
        raw = json.loads(get_setting(db, "job_countries_allowed") or "[]")
    except (ValueError, TypeError):
        return set()
    codes = {str(c).strip().upper() for c in raw if str(c).strip()}
    return {ALIASES.get(c, c) for c in codes}


def outside_allowed(job, allowed: set) -> bool:
    """True when the job's known countries are all outside `allowed` (never for an unplaced job)."""
    if not allowed:
        return False
    countries = {(row.country or "").upper() for row in (job.locations or []) if row.country}
    if not countries and getattr(job, "loc_country", None):
        countries = {job.loc_country.upper()}
    return bool(countries) and not (countries & allowed)


def ignore_outside_countries(session, flush_context, instances) -> None:
    """before_flush: mark new New jobs outside the allowed countries as ignored."""
    from backend.models.db import Job
    from backend.scraper._shared.dedup import mark_ignored
    jobs = [o for o in session.new if isinstance(o, Job) and getattr(o, "status", None) == "new"]
    if not jobs:
        return
    try:
        with session.no_autoflush:
            allowed = allowed_countries(session)
    except Exception as exc:  # no account context (e.g. a maintenance script): leave jobs alone
        logger.debug("country filter skipped: %s", type(exc).__name__)
        return
    for job in jobs:
        if outside_allowed(job, allowed):
            mark_ignored(job)


def install_country_filter() -> None:
    from sqlalchemy import event
    from sqlalchemy.orm import Session
    event.listen(Session, "before_flush", ignore_outside_countries)
