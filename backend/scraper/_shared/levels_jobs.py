"""A levels.fyi job's own data, read from its job page's `__NEXT_DATA__` (server-rendered).

The visible page is a cookie banner and a "Levels.fyi Jobs" blurb: the posting itself is drawn by
script, so a plain page fetch never has the job text. The data has the description and the
employer's apply link (`applicationUrl`). A job whose data names no apply link is applied to on
levels.fyi itself, which counts like LinkedIn's Easy Apply (link kind `easy_apply`, shown as Direct).
"""
import json
import logging
import re

from backend.scraper._shared.urls import _clean_application_url, host_matches

logger = logging.getLogger("jobnavigator.levels_jobs")

# Ids were 18 digits until 2026-10-09 and are base-36 since ("2ci7r6weraiqb").
JOB_ID_RE = re.compile(r"[?&]jobId=([A-Za-z0-9]+)")
_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
MIN_DESCRIPTION = 50


def job_id(url: str) -> str | None:
    """The job id from a levels.fyi link, or None."""
    m = JOB_ID_RE.search(url or "")
    return m.group(1) if m else None


def is_levels_job(url: str) -> bool:
    """A levels.fyi job page (`levels.fyi/jobs?jobId=...`)."""
    return host_matches(url, "levels.fyi") and job_id(url) is not None


def job_fields(job_data: dict) -> dict:
    """{description, application_url, salary_min, salary_max} from a job object of the page data."""
    out = {"description": None, "application_url": None, "salary_min": None, "salary_max": None}
    app_url = job_data.get("applicationUrl") or job_data.get("applyUrl") or ""
    if app_url:
        out["application_url"] = _clean_application_url(app_url) or None
    desc = job_data.get("description") or ""
    if len(desc) > MIN_DESCRIPTION:
        out["description"] = desc[:30000]
    # Salary: base, else total (USD only)
    currency = (job_data.get("baseSalaryCurrency") or job_data.get("currency") or "USD").upper()
    if currency == "USD":
        for key, names in (("salary_min", ("minBaseSalary", "minTotalSalary")),
                           ("salary_max", ("maxBaseSalary", "maxTotalSalary"))):
            val = next((job_data.get(n) for n in names if job_data.get(n)), None)
            if isinstance(val, (int, float)) and val > 0:
                out[key] = int(val)
    return out


def job_object(next_data: dict) -> dict:
    """The job object from a job page's parsed `__NEXT_DATA__` ({} when the page has none)."""
    props = (next_data or {}).get("props", {}).get("pageProps", {})
    return (props.get("initialJobDetails") or props.get("job") or props.get("jobData")
            or props.get("initialJob") or {})


def parse_job_page(html: str) -> dict | None:
    """`job_fields` of a job page's HTML, or None when the page carries no job data."""
    m = _NEXT_DATA_RE.search(html or "")
    if not m:
        return None
    try:
        job = job_object(json.loads(m.group(1)))
    except ValueError:
        return None
    return job_fields(job) if job else None


async def fetch_job(url: str) -> dict | None:
    """`job_fields` of a levels.fyi job, read live; None when the page has no job data (a gone job,
    or Levels.fyi throttling: it then answers 202 with an empty body)."""
    jid = job_id(url)
    if not jid or not host_matches(url, "levels.fyi"):
        return None
    from backend.scraper._shared.url_safety import safe_get
    try:
        resp = await safe_get(f"https://www.levels.fyi/jobs?jobId={jid}", timeout=20,
                              headers={"User-Agent": _UA})
    except Exception as e:  # noqa: BLE001 - None is "unknown"
        logger.info(f"levels.fyi job {jid}: {e}")
        return None
    if resp.status_code != 200:
        logger.info(f"levels.fyi job {jid}: HTTP {resp.status_code}")
        return None
    return parse_job_page(resp.text)
