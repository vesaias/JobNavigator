"""A free "still open?" signal from company scrapes: a posting missing from the company's board in
two full scrapes in a row is marked closed (open_state); one that comes back is open again.

- Only full scrapes count: every link read by an API that returns the whole board (Greenhouse,
  Lever, Ashby, Rippling, SmartRecruiters, Workday, Oracle HCM, Phenom) and no link failed. Boards
  read page by page up to a cap (Meta, Google, Amazon, Uber, generic pages) never count.
- A scrape that sees less than `MIN_SHARE` of the last full scrape's postings does not count
  either (a page that failed half way); the next one compares with the smaller number.
- New scrape links (another board or filter) start the count again.
- Only the company scrape's own rows (`source == "direct"`) of that company, in the current
  account. The application status never changes.
"""
import hashlib
from datetime import datetime, timezone

MISSING_AFTER = 2
MIN_SHARE = 0.7
REASON = "Not on the company's careers page in the last 2 scrapes"


# Filters that keep only recent postings ("posted in the last 7 days"): a job that ages out of the
# window leaves the list while it is still open, so such a link never reads the whole board.
_DATE_WINDOW_KEYS = {"selectedpostingdatesfacet", "postedwithin", "posted_within", "dateposted",
                     "date_posted", "timeposted", "time_posted", "postingdate", "posteddate", "f_tpr"}


def _date_window(url: str) -> bool:
    import json
    from urllib.parse import parse_qsl, urlsplit
    if url.startswith("POST|"):                # Phenom: POST|<url>|<json body>
        try:
            fields = (json.loads(url.split("|", 2)[2]) or {}).get("selected_fields") or {}
        except (ValueError, IndexError, AttributeError):
            return False
        return any(v and ("date" in k.lower() or "posted" in k.lower()) for k, v in fields.items())
    for part in (urlsplit(url).query, urlsplit(url).fragment.partition("?")[2]):
        if any(v and k.lower() in _DATE_WINDOW_KEYS for k, v in parse_qsl(part)):
            return True
    return False


def _full_board(url: str) -> bool:
    from backend.scraper.ats import (ashby, greenhouse, lever, oracle_hcm, phenom, rippling,
                                     smartrecruiters, workday)
    if _date_window(url):
        return False
    return any(is_(url) for is_ in (greenhouse.is_greenhouse, lever.is_lever, ashby.is_ashby,
                                    rippling.is_rippling, smartrecruiters.is_smartrecruiters,
                                    workday.is_workday, oracle_hcm.is_oracle_hcm, phenom.is_phenom))


def is_full_scrape(target_urls, postings, url_errors) -> bool:
    return bool(target_urls) and bool(postings) and not url_errors and all(_full_board(u) for u in target_urls)


def signature(target_urls) -> str:
    return hashlib.sha256("\n".join(sorted(u.strip() for u in target_urls)).encode()).hexdigest()


def note_scrape(db, company, target_urls, postings, url_errors) -> dict:
    """Count this scrape for the company's direct rows (caller commits). Returns
    {"counted": bool, "closed": n, "reopened": n}."""
    from backend.models.db import Job
    from backend.scraper._shared.dedup import make_external_id
    from backend.scraper._shared.postings import posting_key
    out = {"counted": False, "closed": 0, "reopened": 0}
    if not is_full_scrape(target_urls, postings, url_errors):
        return out
    sig, count = signature(target_urls), len(postings)
    prev_sig, prev_count = company.board_signature, company.board_count
    company.board_signature, company.board_count = sig, count
    rows = (db.query(Job).filter(Job.company == company.name, Job.source == "direct",
                                 Job.status.notin_(("ignored", "duplicate"))).all())
    if prev_sig != sig:                       # first full scrape, or other links: start again
        for job in rows:
            job.missed_scrapes = None
        return out
    if prev_count and count < prev_count * MIN_SHARE:
        return out
    out["counted"] = True
    keys = {k for k in (posting_key(p["url"]) for p in postings) if k}
    ext_ids = {make_external_id(company.name, p["title"], p["url"]) for p in postings}
    now = datetime.now(timezone.utc)
    for job in rows:
        if (job.posting_key and job.posting_key in keys) or job.external_id in ext_ids:
            job.missed_scrapes = None
            if job.open_state == "closed" and job.open_reason == REASON:
                job.open_state, job.open_reason, job.open_checked_at = "open", None, now
                out["reopened"] += 1
            continue
        job.missed_scrapes = (job.missed_scrapes or 0) + 1
        if job.missed_scrapes >= MISSING_AFTER and job.open_state != "closed":
            job.open_state, job.open_reason, job.open_checked_at = "closed", REASON, now
            out["closed"] += 1
    return out
