"""Is a job's posting still open? Checked where it matters, not on a schedule (direct-links plan, Task 9).

A job is checked when you open it in the feed, open a résumé or cover letter for it, or press
re-check; the answer is kept on the job for a day (`open_state`, `open_reason`, `open_checked_at`).

- Greenhouse, Lever, Workday: their own job APIs (404 = gone).
- LinkedIn: its public job page ("No longer accepting applications"); no session is used.
- Anything else: the job page itself. A 404/410, a redirect off the posting (the posting key is
  lost), or a closed phrase on the page means closed.
- A bot wall, a throttle or an error is `unknown`, never closed: nothing is guessed.

A check never deletes a job or changes its status or an application.
"""
import json
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

from backend.scraper._shared.postings import posting_key
from backend.scraper._shared.urls import host_matches

OPEN, CLOSED, UNKNOWN = "open", "closed", "unknown"
FRESH_FOR = timedelta(hours=24)

# Lower-case phrases a closed posting's page says.
CLOSED_PHRASES = (
    "no longer accepting applications", "this job is no longer available", "job is no longer available",
    "this position has been filled", "position has been filled", "this position is no longer available",
    "position is closed", "this job has expired", "job posting has expired", "this job is closed",
    "the job you are looking for is no longer", "this posting is no longer", "no longer open for applications",
    "job is no longer open", "this requisition is no longer", "job not found",
)
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
# A browser's request headers: Meta answers 400 to a request without Accept-Language and the
# Sec-Fetch-* headers (and 200 / 404 to one with them).
_HEADERS = {"User-Agent": _UA, "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9", "Sec-Fetch-Dest": "document", "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none", "Sec-Fetch-User": "?1", "Upgrade-Insecure-Requests": "1"}
_TAG = re.compile(r"<[^>]+>")
# Scripts, styles and templates hold a site's UI strings (Dayforce ships "This job is no longer
# accepting applications" on every page): only the visible text counts.
_HIDDEN = re.compile(r"<(script|style|template|noscript)\b[^>]*>.*?</\1\s*>", re.S | re.I)


async def _fetch(url):
    """(status, final url, text) through the SSRF-checked fetch, or None when it fails."""
    from backend.scraper._shared.url_safety import safe_get
    try:
        resp = await safe_get(url, timeout=15, headers=_HEADERS)
    except Exception:
        return None
    return resp.status_code, str(resp.url), resp.text[:500_000]


async def _fetch_workday(url):
    """(status, final url, text) of a Workday API URL through workday._client, or None. The URL
    comes from _workday_api, which builds it only for a *.myworkdayjobs.com posting."""
    from backend.scraper.ats import workday as _wd
    try:
        async with _wd._client(15) as client:
            resp = await client.get(url, headers={"Accept": "application/json"})
    except Exception:
        return None
    return resp.status_code, str(resp.url), (resp.text or "")[:500_000]


def _greenhouse_api(url):
    p = urlparse(url)
    seg = [s for s in p.path.split("/") if s]
    key = posting_key(url) or ""
    job_id = key.split(":", 1)[1] if key.startswith("greenhouse:") else None
    board = None
    if host_matches(url, "greenhouse.io"):
        board = (parse_qs(p.query).get("for") or [None])[0]
        if not board and "jobs" in seg and seg.index("jobs") > 0:
            board = seg[seg.index("jobs") - 1]
    api = "boards-api.eu.greenhouse.io" if host_matches(url, "eu.greenhouse.io") else "boards-api.greenhouse.io"
    return f"https://{api}/v1/boards/{board}/jobs/{job_id}" if board and job_id else None


def _lever_api(url):
    if not host_matches(url, "lever.co"):
        return None
    api = "api.eu.lever.co" if host_matches(url, "eu.lever.co") else "api.lever.co"
    seg = [s for s in urlparse(url).path.split("/") if s]
    return f"https://{api}/v0/postings/{seg[0]}/{seg[1]}" if len(seg) >= 2 else None


def _workday_api(url):
    # only a Workday link: a company site that shows Workday numbers (Bank of America, Visa) is
    # keyed workday:<tenant>:<n> but is checked by its own page
    # (wdN.myworkdaysite.com/recruiting/<tenant>/<site>/... is checked by its page: the job API
    # address would be built from the wrong parts)
    if not host_matches(url, "myworkdayjobs.com"):
        return None
    from backend.scraper.ats.workday import _LOCALE_PATH_RE, _parse_workday_url
    try:
        origin, tenant, site, _ = _parse_workday_url(url)
    except Exception:
        return None
    parts = [p for p in urlparse(url).path.strip("/").split("/") if p and not _LOCALE_PATH_RE.match(p)]
    if not (origin and tenant and site) or len(parts) < 2:
        return None
    return f"{origin}/wday/cxs/{tenant}/{site}/" + "/".join(parts[1:])


async def _by_api(api, name, fetch):
    got = await fetch(api)
    if got is None:
        return None
    status, _final, text = got
    if status in (404, 410):
        return CLOSED, f"{name}: the posting is gone"
    # Workday answers a removed posting with its own JSON error: 403 {"errorCode": "S22",
    # "message": "permission denied"} (an open one answers 200)
    if name == "Workday" and status in (403, 404) and '"errorCode"' in (text or ""):
        return CLOSED, "Workday: the posting is gone"
    if status == 200:
        if name == "Workday":
            try:
                if not json.loads(text or "{}").get("jobPostingInfo"):
                    return CLOSED, "Workday: the posting is gone"
            except ValueError:
                return None
        return OPEN, ""
    return None


async def check_link(url, fetch=None):
    """(open | closed | unknown, reason) for one job link."""
    fetch = fetch or _fetch
    if not url:
        return UNKNOWN, "no link"
    key = posting_key(url) or ""
    kind = key.split(":", 1)[0] if key else ""
    api = {"greenhouse": _greenhouse_api, "lever": _lever_api, "workday": _workday_api}.get(kind)
    if api:
        endpoint = api(url)
        if endpoint:
            # Workday refuses Python's HTTP clients (workday._client); a fetch a test passes in stays.
            api_fetch = _fetch_workday if (kind == "workday" and fetch is _fetch) else fetch
            answer = await _by_api(endpoint, kind.capitalize() if kind != "workday" else "Workday", api_fetch)
            if answer:
                return answer
            if kind == "workday":   # its page is an app shell that always loads: it proves nothing
                return UNKNOWN, "Workday did not answer"
    if kind == "linkedin":
        page = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{key.split(':', 1)[1]}"
        got = await fetch(page)
        if got is None or got[0] not in (200, 404, 410):
            return UNKNOWN, "LinkedIn did not answer"
        if got[0] in (404, 410):
            return CLOSED, "LinkedIn: the listing is gone"
        if "no longer accepting applications" in got[2].lower():
            return CLOSED, "LinkedIn: No longer accepting applications"
        return OPEN, ""
    got = await fetch(url)
    if got is None:
        return UNKNOWN, "the page could not be reached"
    status, final, text = got
    from backend.scraper._shared.bot_wall import is_bot_wall
    if is_bot_wall(text):   # before the status: a bot check can be served with a 404
        return UNKNOWN, "the site shows a bot check"
    if status in (404, 410):
        return CLOSED, f"the page returns {status}"
    if status >= 400:
        return UNKNOWN, f"the page returns {status}"
    posting_id = key.rsplit(":", 1)[-1] if key else ""
    if (key and final and posting_key(final) != key and urlparse(final).path != urlparse(url).path
            and posting_id.lower() not in final.lower()):
        p = urlparse(final)
        return CLOSED, f"redirected to {(p.hostname or '').removeprefix('www.')}{p.path}"
    page = " ".join(_TAG.sub(" ", _HIDDEN.sub(" ", text or "")).lower().split())
    for phrase in CLOSED_PHRASES:
        if phrase in page:
            return CLOSED, f"the page says “{phrase}”"
    return OPEN, ""


def _as_dict(job) -> dict:
    return {"open_state": job.open_state, "open_reason": job.open_reason,
            "open_checked_at": job.open_checked_at.isoformat() if job.open_checked_at else None}


async def ensure_checked(db, job, force: bool = False) -> dict:
    """The job's open state, checked again when the last answer is older than a day (or `force`)."""
    from backend.models.db import LinkedinLookup
    from backend.scraper._shared.link_kinds import job_link
    checked = job.open_checked_at
    if checked is not None and checked.tzinfo is None:
        checked = checked.replace(tzinfo=timezone.utc)
    if not force and checked is not None and datetime.now(timezone.utc) - checked < FRESH_FOR:
        return _as_dict(job)
    state = reason = None
    if (job.posting_key or "").startswith("linkedin:") and not job.apply_url:
        cached = db.get(LinkedinLookup, job.posting_key.split(":", 1)[1])
        if cached is not None and cached.result == "gone":
            state, reason = CLOSED, "LinkedIn: the listing is gone"
    if state is None:
        link = job_link(job)
        db.commit()   # end the transaction: no pooled connection waits on an outside site
        state, reason = await check_link(link)
    job.open_state, job.open_reason, job.open_checked_at = state, reason or None, datetime.now(timezone.utc)
    db.commit()
    return _as_dict(job)
