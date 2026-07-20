"""SpeedyApply GitHub source for recent college SWE jobs.

The upstream repository publishes generated Markdown tables.  We read the raw
files (rather than scraping GitHub's rendered HTML), parse rows by their header
names, keep only recent postings, enrich each job from its employer page, and
store it through JobNavigator's normal deduplication path.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Iterable
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from sqlalchemy.exc import IntegrityError

from backend.analyzer.salary_extractor import apply_salary_to_job
from backend.models.db import Job, SessionLocal, Setting
from backend.scraper._shared.dedup import make_content_hash, make_external_id
from backend.scraper._shared.url_safety import safe_get

logger = logging.getLogger("jobnavigator.scraper.sources.speedyapply")

RAW_BASE = "https://raw.githubusercontent.com/speedyapply/2027-SWE-College-Jobs/main"

FEEDS = {
    "intern_usa": f"{RAW_BASE}/README.md",
    "new_grad_usa": f"{RAW_BASE}/NEW_GRAD_USA.md",
    "intern_intl": f"{RAW_BASE}/INTERN_INTL.md",
    "new_grad_intl": f"{RAW_BASE}/NEW_GRAD_INTL.md",
}

DEFAULT_FEEDS = ["intern_usa", "new_grad_usa"]
_TABLE_SEPARATOR_RE = re.compile(r"^:?-{3,}:?$")
_AGE_RE = re.compile(r"(\d+)\s*d", re.IGNORECASE)


@dataclass
class SpeedyApplySyncResult:
    jobs_found: int = 0
    jobs_considered: int = 0
    new_jobs: int = 0
    reused_jobs: int = 0
    queue_candidates: list[dict] = field(default_factory=list)
    feed_errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "jobs_found": self.jobs_found,
            "jobs_considered": self.jobs_considered,
            "new_jobs": self.new_jobs,
            "reused_jobs": self.reused_jobs,
            "queue_candidates": list(self.queue_candidates),
            "feed_errors": list(self.feed_errors),
        }


def _setting(db, key: str, default: str = "") -> str:
    row = db.query(Setting).filter(Setting.key == key).first()
    return row.value if row else default


def configured_feeds(raw_value) -> list[str]:
    """Return a validated, ordered feed ID list from a DB setting value."""
    value = raw_value
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            value = [part.strip() for part in value.split(",") if part.strip()]
    if not isinstance(value, list):
        value = DEFAULT_FEEDS
    result = []
    for feed_id in value:
        if feed_id in FEEDS and feed_id not in result:
            result.append(feed_id)
    return result or list(DEFAULT_FEEDS)


def _split_markdown_row(line: str) -> list[str]:
    """Split an upstream table row.

    A small parser is preferable to adding a Markdown renderer dependency.
    Split only on unescaped pipes so a future title containing ``\\|`` does not
    shift every later column.
    """
    body = line.strip().strip("|")
    return [cell.replace(r"\|", "|").strip() for cell in re.split(r"(?<!\\)\|", body)]


def _plain_text(cell: str) -> str:
    value = cell or ""
    if "<" not in value:
        return value.strip()
    return BeautifulSoup(value, "html.parser").get_text(" ", strip=True)


def _first_http_url(cell: str) -> str | None:
    soup = BeautifulSoup(cell or "", "html.parser")
    anchor = soup.find("a", href=True)
    if not anchor:
        return None
    url = str(anchor.get("href") or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return None
    return url


def _parse_age(cell: str) -> int | None:
    match = _AGE_RE.search(_plain_text(cell))
    return int(match.group(1)) if match else None


def _parse_salary_hint(cell: str) -> tuple[int | None, int | None]:
    """Convert the compact upstream salary hint to an annual range.

    The employer JD remains authoritative.  This hint is used only when the JD
    contains no salary, and hourly rates are annualized with 2,080 hours/year.
    """
    text = _plain_text(cell).replace(",", "")
    if not text or "$" not in text:
        return None, None

    values = [float(v) for v in re.findall(r"\$\s*(\d+(?:\.\d+)?)", text)]
    if not values:
        return None, None

    lower_text = text.lower()
    multiplier = 1
    if "/hr" in lower_text or "hour" in lower_text:
        multiplier = 2080
    elif "k" in lower_text:
        multiplier = 1000

    annual = [int(round(value * multiplier)) for value in values[:2]]
    if len(annual) == 1:
        return annual[0], annual[0]
    return min(annual), max(annual)


def parse_markdown_jobs(markdown: str, feed_id: str) -> list[dict]:
    """Parse every valid job row from one SpeedyApply Markdown document."""
    if feed_id not in FEEDS:
        raise ValueError(f"Unknown SpeedyApply feed: {feed_id}")

    jobs: list[dict] = []
    headers: list[str] | None = None

    for raw_line in (markdown or "").splitlines():
        line = raw_line.strip()
        if not line.startswith("|"):
            headers = None
            continue

        cells = _split_markdown_row(line)
        normalized = [re.sub(r"\s+", "_", _plain_text(cell).strip().lower()) for cell in cells]
        if "company" in normalized and "position" in normalized and "posting" in normalized:
            headers = normalized
            continue
        if not headers or all(_TABLE_SEPARATOR_RE.match(cell or "") for cell in cells):
            continue
        if len(cells) != len(headers):
            continue

        row = dict(zip(headers, cells))
        company = _plain_text(row.get("company", ""))
        title = _plain_text(row.get("position", ""))
        location = _plain_text(row.get("location", ""))
        apply_url = _first_http_url(row.get("posting", ""))
        age_days = _parse_age(row.get("age", ""))
        if not company or not title or not apply_url or age_days is None:
            continue

        salary_min, salary_max = _parse_salary_hint(row.get("salary", ""))
        jobs.append({
            "company": company,
            "title": title,
            "location": location or None,
            "url": apply_url,
            "age_days": age_days,
            "salary_min_hint": salary_min,
            "salary_max_hint": salary_max,
            "feed_id": feed_id,
        })

    return jobs


async def _fetch_feed(feed_id: str) -> str:
    url = FEEDS[feed_id]
    response = await safe_get(
        url,
        timeout=20,
        headers={
            "Accept": "text/plain, text/markdown;q=0.9, */*;q=0.1",
            "User-Agent": "JobNavigator/SpeedyApplySource",
        },
    )
    response.raise_for_status()
    return response.text


async def _fetch_descriptions(rows: list[dict], max_concurrent: int = 5):
    """Lazy bridge to the shared ATS fetcher.

    Importing that module loads Playwright through the shared browser helpers.
    Keeping the import here lets the pure Markdown parser run in lightweight
    environments while production syncs still use the exact existing fetcher.
    """
    from backend.scraper.ats._descriptions import _fetch_descriptions_parallel

    return await _fetch_descriptions_parallel(rows, max_concurrent=max_concurrent)


def _unique_recent_jobs(rows: Iterable[dict], max_age_days: int) -> list[dict]:
    by_external_id: dict[str, dict] = {}
    for row in rows:
        if row["age_days"] > max_age_days:
            continue
        external_id = make_external_id(row["company"], row["title"], row["url"])
        current = by_external_id.get(external_id)
        if current is None or row["age_days"] < current["age_days"]:
            item = dict(row)
            item["external_id"] = external_id
            by_external_id[external_id] = item
    ordered = sorted(
        by_external_id.values(),
        key=lambda item: (item["age_days"], item["company"].lower(), item["title"].lower()),
    )
    return ordered


def _select_unqueued_candidates(db, candidates: list[dict], max_jobs: int) -> list[dict]:
    """Apply the run cap without letting already-queued jobs consume it."""
    from backend.models.db import ApplicationQueueItem

    external_ids = [item["external_id"] for item in candidates]
    existing_by_external_id = {
        job.external_id: job
        for job in db.query(Job).filter(Job.external_id.in_(external_ids)).all()
    } if external_ids else {}
    existing_job_ids = [job.id for job in existing_by_external_id.values()]
    queued_job_ids = {
        row[0]
        for row in db.query(ApplicationQueueItem.job_id).filter(
            ApplicationQueueItem.job_id.in_(existing_job_ids)
        ).all()
    } if existing_job_ids else set()

    selected = []
    for candidate in candidates:
        existing = existing_by_external_id.get(candidate["external_id"])
        if existing and existing.id in queued_job_ids:
            continue
        selected.append(candidate)
        if len(selected) >= max_jobs:
            break
    return selected


async def sync_speedyapply_jobs() -> dict:
    """Fetch configured feeds, enrich recent jobs, and store/reuse Job rows."""
    config_db = SessionLocal()
    try:
        feed_ids = configured_feeds(_setting(config_db, "speedyapply_feeds", json.dumps(DEFAULT_FEEDS)))
        try:
            max_age_days = max(0, int(_setting(config_db, "speedyapply_max_age_days", "1")))
        except (TypeError, ValueError):
            max_age_days = 1
        try:
            max_jobs = max(1, min(100, int(_setting(config_db, "speedyapply_max_jobs_per_run", "25"))))
        except (TypeError, ValueError):
            max_jobs = 25
    finally:
        config_db.close()

    result = SpeedyApplySyncResult()
    parsed_rows: list[dict] = []
    for feed_id in feed_ids:
        try:
            markdown = await _fetch_feed(feed_id)
            rows = parse_markdown_jobs(markdown, feed_id)
            result.jobs_found += len(rows)
            parsed_rows.extend(rows)
        except Exception as exc:
            message = f"{feed_id}: {exc}"
            logger.warning("SpeedyApply feed failed: %s", message)
            result.feed_errors.append(message)

    recent_candidates = _unique_recent_jobs(parsed_rows, max_age_days)
    selection_db = SessionLocal()
    try:
        candidates = _select_unqueued_candidates(selection_db, recent_candidates, max_jobs)
    finally:
        selection_db.close()
    result.jobs_considered = len(candidates)
    if not candidates:
        return result.as_dict()

    description_results = await _fetch_descriptions(candidates, max_concurrent=5)
    for fetch_result in description_results:
        if isinstance(fetch_result, Exception):
            logger.warning("SpeedyApply description worker failed: %s", fetch_result)
            continue
        row, description = fetch_result
        if description:
            row["description"] = description

    db = SessionLocal()
    try:
        for row in candidates:
            job = db.query(Job).filter(Job.external_id == row["external_id"]).first()
            if job:
                result.reused_jobs += 1
                if not (job.description or "").strip() and row.get("description"):
                    job.description = row["description"]
                    apply_salary_to_job(job)
            else:
                job = Job(
                    external_id=row["external_id"],
                    content_hash=make_content_hash(row["company"], row["title"]),
                    company=row["company"],
                    title=row["title"],
                    url=row["url"],
                    source=f"speedyapply_{row['feed_id']}",
                    description=row.get("description"),
                    location=row.get("location"),
                    remote="remote" in (row.get("location") or "").lower(),
                    status="new",
                    seen=False,
                    saved=False,
                )
                apply_salary_to_job(job)
                if job.salary_min is None and row.get("salary_min_hint") is not None:
                    job.salary_min = row["salary_min_hint"]
                    job.salary_max = row["salary_max_hint"]
                    job.salary_source = "speedyapply"
                try:
                    with db.begin_nested():
                        db.add(job)
                        db.flush()
                    result.new_jobs += 1
                except IntegrityError:
                    job = db.query(Job).filter(Job.external_id == row["external_id"]).first()
                    if not job:
                        raise
                    result.reused_jobs += 1

            result.queue_candidates.append({
                "job_id": str(job.id),
                "feed_id": row["feed_id"],
                "application_url": row["url"],
                "description_ready": bool((job.description or "").strip()),
            })

        db.commit()
    finally:
        db.close()

    logger.info(
        "SpeedyApply sync: %s new, %s reused, %s considered, errors=%s",
        result.new_jobs,
        result.reused_jobs,
        result.jobs_considered,
        len(result.feed_errors),
    )
    return result.as_dict()
