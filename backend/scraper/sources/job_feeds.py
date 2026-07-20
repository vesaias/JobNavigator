"""Realtime GitHub aggregate feeds for US internship and new-grad jobs.

The module deliberately separates repository polling from job ingestion.  Atom
feeds are a small, unauthenticated change signal; raw Markdown is downloaded
only when the repository commit changes.  Every upstream row is normalized to
``FeedJob`` before filters or persistence are applied.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Iterable
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from sqlalchemy.exc import IntegrityError

from backend.analyzer.salary_extractor import apply_salary_to_job
from backend.models.db import (
    ApplicationQueueItem,
    Job,
    JobFeedCheckpoint,
    JobFeedPosting,
    Persona,
    SessionLocal,
    Setting,
    utcnow,
)
from backend.scraper._shared.dedup import (
    application_identity,
    make_application_external_id,
    make_content_hash,
)
from backend.scraper._shared.url_safety import safe_get

logger = logging.getLogger("jobnavigator.scraper.sources.job_feeds")


@dataclass(frozen=True)
class RepositorySpec:
    id: str
    atom_url: str


@dataclass(frozen=True)
class FeedSpec:
    id: str
    repository_id: str
    raw_url: str
    job_type: str  # intern | new_grad


REPOSITORIES = {
    "speedyapply_2027": RepositorySpec(
        id="speedyapply_2027",
        atom_url="https://github.com/speedyapply/2027-SWE-College-Jobs/commits/main.atom",
    ),
    "vansh_summer_2027": RepositorySpec(
        id="vansh_summer_2027",
        atom_url="https://github.com/vanshb03/Summer2027-Internships/commits/dev.atom",
    ),
    "vansh_new_grad_2027": RepositorySpec(
        id="vansh_new_grad_2027",
        atom_url="https://github.com/vanshb03/New-Grad-2027/commits/dev.atom",
    ),
}

FEEDS = {
    "speedyapply_intern_usa": FeedSpec(
        id="speedyapply_intern_usa",
        repository_id="speedyapply_2027",
        raw_url="https://raw.githubusercontent.com/speedyapply/2027-SWE-College-Jobs/main/README.md",
        job_type="intern",
    ),
    "speedyapply_new_grad_usa": FeedSpec(
        id="speedyapply_new_grad_usa",
        repository_id="speedyapply_2027",
        raw_url="https://raw.githubusercontent.com/speedyapply/2027-SWE-College-Jobs/main/NEW_GRAD_USA.md",
        job_type="new_grad",
    ),
    "vansh_summer_2027": FeedSpec(
        id="vansh_summer_2027",
        repository_id="vansh_summer_2027",
        raw_url="https://raw.githubusercontent.com/vanshb03/Summer2027-Internships/dev/README.md",
        job_type="intern",
    ),
    "vansh_new_grad_2027": FeedSpec(
        id="vansh_new_grad_2027",
        repository_id="vansh_new_grad_2027",
        raw_url="https://raw.githubusercontent.com/vanshb03/New-Grad-2027/dev/README.md",
        job_type="new_grad",
    ),
}

DEFAULT_FEEDS = list(FEEDS)
_TABLE_SEPARATOR_RE = re.compile(r"^:?-{3,}:?$")
_AGE_RE = re.compile(r"(\d+)\s*d", re.IGNORECASE)
_ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
_HEADER_ALIASES = {
    "position": "title",
    "role": "title",
    "posting": "application",
    "application/link": "application",
    "application": "application",
    "date_posted": "date_posted",
    "age": "age",
    "company": "company",
    "location": "location",
    "salary": "salary",
}


@dataclass
class FeedJob:
    source_id: str
    repository_id: str
    job_type: str
    company: str
    title: str
    location: str | None
    url: str
    posted_at: datetime | None
    age_days: int | None
    salary_min_hint: int | None = None
    salary_max_hint: int | None = None
    flags: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        data = asdict(self)
        if self.posted_at:
            data["posted_at"] = self.posted_at.isoformat()
        return data


@dataclass
class PollResult:
    rows: list[FeedJob] = field(default_factory=list)
    changed_repositories: list[str] = field(default_factory=list)
    unchanged_repositories: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "rows": [row.as_dict() for row in self.rows],
            "changed_repositories": self.changed_repositories,
            "unchanged_repositories": self.unchanged_repositories,
            "errors": self.errors,
        }


def _setting(db, key: str, default: str = "") -> str:
    row = db.query(Setting).filter(Setting.key == key).first()
    return row.value if row else default


def configured_feeds(raw_value) -> list[str]:
    value = raw_value
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            value = [part.strip() for part in value.split(",") if part.strip()]
    if not isinstance(value, list):
        value = DEFAULT_FEEDS
    result = []
    for source_id in value:
        if source_id in FEEDS and source_id not in result:
            result.append(source_id)
    return result or list(DEFAULT_FEEDS)


def _split_markdown_row(line: str) -> list[str]:
    body = line.strip().strip("|")
    return [cell.replace(r"\|", "|").strip() for cell in re.split(r"(?<!\\)\|", body)]


def _plain_text(cell: str) -> str:
    value = cell or ""
    if "<" not in value:
        return value.strip().replace("**", "")
    return BeautifulSoup(value, "html.parser").get_text(" ", strip=True).replace("**", "")


def _first_http_url(cell: str) -> str | None:
    soup = BeautifulSoup(cell or "", "html.parser")
    for anchor in soup.find_all("a", href=True):
        url = str(anchor.get("href") or "").strip()
        parsed = urlparse(url)
        if parsed.scheme in ("http", "https") and parsed.hostname:
            return url
    match = re.search(r"https?://[^\s)>\]]+", cell or "")
    return match.group(0) if match else None


def _flags_from_text(*values: str) -> dict:
    text = " ".join(values)
    return {
        "no_sponsorship": "🛂" in text,
        "citizenship_required": "🇺🇸" in text,
        "closed": "🔒" in text,
        "advanced_degree_required": "🎓" in text,
    }


def _parse_salary_hint(cell: str) -> tuple[int | None, int | None]:
    text = _plain_text(cell).replace(",", "")
    if not text or "$" not in text:
        return None, None
    values = [float(value) for value in re.findall(r"\$\s*(\d+(?:\.\d+)?)", text)]
    if not values:
        return None, None
    lower = text.lower()
    multiplier = 2080 if "/hr" in lower or "hour" in lower else (1000 if "k" in lower else 1)
    annual = [int(round(value * multiplier)) for value in values[:2]]
    return (annual[0], annual[0]) if len(annual) == 1 else (min(annual), max(annual))


def _posted_from_cells(age_cell: str, date_cell: str, now: datetime) -> tuple[datetime | None, int | None]:
    age_match = _AGE_RE.search(_plain_text(age_cell))
    if age_match:
        age_days = int(age_match.group(1))
        return now - timedelta(days=age_days), age_days

    raw = _plain_text(date_cell).strip()
    if not raw:
        return None, None
    parsed = None
    # Parse yearless source dates with an explicit year. Python 3.13 warns
    # because strptime("%b %d") otherwise has ambiguous leap-day behavior.
    candidates = [
        (f"{raw}, {now.year}", "%b %d, %Y") if re.fullmatch(r"[A-Za-z]{3}\s+\d{1,2}", raw)
        else (raw, "%b %d, %Y"),
        (raw, "%Y-%m-%d"),
    ]
    for candidate, fmt in candidates:
        try:
            parsed = datetime.strptime(candidate, fmt)
            break
        except ValueError:
            continue
    if parsed is None:
        return None, None
    if parsed.replace(tzinfo=timezone.utc) > now + timedelta(days=2):
        parsed = parsed.replace(year=parsed.year - 1)
    posted = parsed.replace(tzinfo=timezone.utc)
    return posted, max(0, (now.date() - posted.date()).days)


def _normalize_headers(cells: list[str]) -> list[str]:
    normalized = []
    for cell in cells:
        key = re.sub(r"\s+", "_", _plain_text(cell).strip().lower())
        normalized.append(_HEADER_ALIASES.get(key, key))
    return normalized


def parse_feed_document(document: str, source_id: str, now: datetime | None = None) -> list[FeedJob]:
    """Parse Markdown pipe tables or raw HTML tables into normalized jobs."""
    if source_id not in FEEDS:
        raise ValueError(f"Unknown job feed: {source_id}")
    spec = FEEDS[source_id]
    current = now or utcnow()
    if "<table" in (document or "").lower():
        return _parse_html_tables(document, spec, current)

    jobs: list[FeedJob] = []
    headers: list[str] | None = None
    last_company = ""
    for raw_line in (document or "").splitlines():
        line = raw_line.strip()
        if not line.startswith("|"):
            headers = None
            continue
        cells = _split_markdown_row(line)
        candidate_headers = _normalize_headers(cells)
        if {"company", "title", "application"}.issubset(candidate_headers):
            headers = candidate_headers
            continue
        if not headers or all(_TABLE_SEPARATOR_RE.match(cell or "") for cell in cells):
            continue
        if len(cells) != len(headers):
            continue
        row = dict(zip(headers, cells))
        raw_company = _plain_text(row.get("company", ""))
        company = last_company if raw_company in {"↳", ""} else raw_company
        if raw_company not in {"↳", ""}:
            last_company = raw_company
        title = _plain_text(row.get("title", ""))
        location = _plain_text(row.get("location", ""))
        url = _first_http_url(row.get("application", ""))
        posted_at, age_days = _posted_from_cells(row.get("age", ""), row.get("date_posted", ""), current)
        if not company or not title or not url:
            continue
        salary_min, salary_max = _parse_salary_hint(row.get("salary", ""))
        jobs.append(FeedJob(
            source_id=source_id,
            repository_id=spec.repository_id,
            job_type=spec.job_type,
            company=company,
            title=title,
            location=location or None,
            url=url,
            posted_at=posted_at,
            age_days=age_days,
            salary_min_hint=salary_min,
            salary_max_hint=salary_max,
            flags=_flags_from_text(raw_company, title, row.get("application", "")),
        ))
    return jobs


def _parse_html_tables(document: str, spec: FeedSpec, now: datetime) -> list[FeedJob]:
    soup = BeautifulSoup(document or "", "html.parser")
    jobs: list[FeedJob] = []
    last_company = ""
    for table in soup.find_all("table"):
        header_cells = table.find_all("th")
        headers = _normalize_headers([str(cell) for cell in header_cells])
        if not {"company", "title", "application"}.issubset(headers):
            continue
        for tr in table.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) != len(headers):
                continue
            row = dict(zip(headers, [str(cell) for cell in cells]))
            raw_company = _plain_text(row.get("company", ""))
            company = last_company if raw_company in {"↳", ""} else raw_company
            if raw_company not in {"↳", ""}:
                last_company = raw_company
            title = _plain_text(row.get("title", ""))
            location = _plain_text(row.get("location", ""))
            url = _first_http_url(row.get("application", ""))
            posted_at, age_days = _posted_from_cells(row.get("age", ""), row.get("date_posted", ""), now)
            if company and title and url:
                jobs.append(FeedJob(
                    source_id=spec.id,
                    repository_id=spec.repository_id,
                    job_type=spec.job_type,
                    company=company,
                    title=title,
                    location=location or None,
                    url=url,
                    posted_at=posted_at,
                    age_days=age_days,
                    flags=_flags_from_text(raw_company, title, row.get("application", "")),
                ))
    return jobs


async def _fetch_text(url: str, accept: str) -> str:
    response = await safe_get(
        url,
        timeout=20,
        headers={"Accept": accept, "User-Agent": "JobNavigator/RealtimeJobFeeds"},
    )
    response.raise_for_status()
    return response.text


async def _fetch_repository_head(repository: RepositorySpec) -> tuple[str, datetime | None]:
    xml_text = await _fetch_text(repository.atom_url, "application/atom+xml, application/xml;q=0.9")
    root = ET.fromstring(xml_text)
    entry = root.find("atom:entry", _ATOM_NS)
    if entry is None:
        raise ValueError(f"{repository.id} Atom feed has no commit entries")
    entry_id = (entry.findtext("atom:id", default="", namespaces=_ATOM_NS) or "").strip()
    sha = entry_id.rsplit("/", 1)[-1]
    if not re.fullmatch(r"[0-9a-fA-F]{7,64}", sha):
        raise ValueError(f"{repository.id} Atom feed has an invalid commit id")
    updated_raw = entry.findtext("atom:updated", default="", namespaces=_ATOM_NS)
    updated_at = None
    if updated_raw:
        try:
            updated_at = datetime.fromisoformat(updated_raw.replace("Z", "+00:00"))
        except ValueError:
            pass
    return sha, updated_at


def _mark_repository_error(repository_id: str, exc: Exception) -> None:
    db = SessionLocal()
    try:
        checkpoint = db.query(JobFeedCheckpoint).filter(
            JobFeedCheckpoint.repository_id == repository_id
        ).first()
        if checkpoint is None:
            checkpoint = JobFeedCheckpoint(repository_id=repository_id)
            db.add(checkpoint)
        checkpoint.last_checked_at = utcnow()
        checkpoint.consecutive_errors = (checkpoint.consecutive_errors or 0) + 1
        checkpoint.last_error = str(exc)[:2000]
        db.commit()
    finally:
        db.close()


async def poll_feed_documents(*, force: bool = False) -> PollResult:
    """Poll configured repository heads and parse documents that changed."""
    config_db = SessionLocal()
    try:
        source_ids = configured_feeds(_setting(
            config_db, "job_feeds_sources", json.dumps(DEFAULT_FEEDS)
        ))
        existing = {
            row.repository_id: row
            for row in config_db.query(JobFeedCheckpoint).all()
        }
        previous = {
            key: {"sha": value.last_commit_sha, "success": value.last_success_at}
            for key, value in existing.items()
        }
    finally:
        config_db.close()

    by_repository: dict[str, list[FeedSpec]] = {}
    for source_id in source_ids:
        spec = FEEDS[source_id]
        by_repository.setdefault(spec.repository_id, []).append(spec)

    result = PollResult()
    for repository_id, specs in by_repository.items():
        repository = REPOSITORIES[repository_id]
        try:
            sha, upstream_updated_at = await _fetch_repository_head(repository)
            prior = previous.get(repository_id) or {}
            changed = force or not prior.get("success") or prior.get("sha") != sha
            if not changed:
                db = SessionLocal()
                try:
                    checkpoint = db.query(JobFeedCheckpoint).filter(
                        JobFeedCheckpoint.repository_id == repository_id
                    ).first()
                    if checkpoint:
                        checkpoint.last_checked_at = utcnow()
                        checkpoint.last_success_at = utcnow()
                        checkpoint.upstream_updated_at = upstream_updated_at
                        checkpoint.consecutive_errors = 0
                        checkpoint.last_error = None
                        db.commit()
                finally:
                    db.close()
                result.unchanged_repositories.append(repository_id)
                continue

            documents: list[tuple[FeedSpec, str]] = []
            for spec in specs:
                text = await _fetch_text(spec.raw_url, "text/plain, text/markdown;q=0.9")
                documents.append((spec, text))
                result.rows.extend(parse_feed_document(text, spec.id))
            combined_hash = hashlib.sha256(
                "\n".join(text for _, text in documents).encode("utf-8")
            ).hexdigest()
            db = SessionLocal()
            try:
                checkpoint = db.query(JobFeedCheckpoint).filter(
                    JobFeedCheckpoint.repository_id == repository_id
                ).first()
                if checkpoint is None:
                    checkpoint = JobFeedCheckpoint(repository_id=repository_id)
                    db.add(checkpoint)
                now = utcnow()
                checkpoint.last_commit_sha = sha
                checkpoint.content_hash = combined_hash
                checkpoint.last_checked_at = now
                checkpoint.last_changed_at = now
                checkpoint.last_success_at = now
                checkpoint.upstream_updated_at = upstream_updated_at
                checkpoint.consecutive_errors = 0
                checkpoint.last_error = None
                db.commit()
            finally:
                db.close()
            result.changed_repositories.append(repository_id)
        except Exception as exc:
            logger.warning("Job feed repository %s failed: %s", repository_id, exc)
            _mark_repository_error(repository_id, exc)
            result.errors.append(f"{repository_id}: {exc}")
    return result


def rows_within_days(rows: Iterable[FeedJob], days: int, now: datetime | None = None) -> list[FeedJob]:
    current = now or utcnow()
    cutoff = current - timedelta(days=max(0, days))
    return [row for row in rows if row.posted_at is None or row.posted_at >= cutoff]


_ROLE_EXCLUDES = (
    "product manager", "program manager", "project manager", "engineering manager",
    "director", "principal", "staff engineer", "senior engineer", "sr. engineer",
    "hardware engineer", "electrical engineer", "mechanical engineer", "quantitative trader",
    "quant trader", "investment analyst",
)
_AI_TERMS = (
    "machine learning", "artificial intelligence", " ai ", "ai engineer", "applied scientist",
    "research scientist", "research engineer", "computer vision", "deep learning", " nlp",
)
_DATA_TERMS = (
    "data engineer", "data scientist", "data analyst", "analytics engineer", "data platform",
    "business intelligence",
)
_SWE_TERMS = (
    "software", "developer", "development engineer", "backend", "front-end", "frontend",
    "full-stack", "fullstack", "platform engineer", "infrastructure engineer", "cloud engineer",
    "site reliability", "devops", "systems engineer", "security engineer", "firmware",
    "embedded engineer", "mobile engineer", "ios engineer", "android engineer",
)
_NON_US_LOCATION_TERMS = (
    "canada", "toronto", "vancouver", "montreal", "ottawa", "waterloo", "united kingdom",
    "london", "india", "china", "singapore", "australia", "germany", "france", "ireland",
)
_US_LOCATION_RE = re.compile(
    r"\b(?:USA|US|United States|AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC)\b",
    re.IGNORECASE,
)
_NO_SPONSOR_PATTERNS = (
    r"(?:will|does|do|can)\s+not\s+(?:provide|offer|support)\s+(?:employment\s+)?(?:visa\s+)?sponsorship",
    r"not\s+(?:eligible|available)\s+for\s+(?:immigration|visa)\s+sponsorship",
    r"without\s+(?:current\s+or\s+future\s+)?sponsorship",
    r"no\s+(?:visa\s+)?sponsorship",
)
_CITIZEN_PATTERNS = (
    r"must\s+be\s+(?:a\s+)?u\.?s\.?\s+citizen",
    r"u\.?s\.?\s+citizenship\s+(?:is\s+)?required",
    r"security\s+clearance\s+(?:is\s+)?required",
    r"must\s+(?:hold|obtain|maintain)\s+(?:a\s+)?(?:security\s+)?clearance",
)


@dataclass
class EligibilityResult:
    eligible: bool
    role_family: str | None = None
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def classify_role_family(title: str) -> str | None:
    normalized = f" {(title or '').lower()} "
    if any(term in normalized for term in _ROLE_EXCLUDES):
        return None
    if any(term in normalized for term in _AI_TERMS):
        return "ai"
    if any(term in normalized for term in _DATA_TERMS):
        return "data"
    if any(term in normalized for term in _SWE_TERMS):
        return "swe"
    return None


def location_is_us(location: str | None) -> bool:
    value = (location or "").strip()
    lower = value.lower()
    if any(term in lower for term in _NON_US_LOCATION_TERMS):
        return False
    if "remote" in lower:
        return True
    return bool(_US_LOCATION_RE.search(value))


def _persona_has_advanced_degree(db) -> bool:
    persona = db.query(Persona).filter(Persona.id == 1).first()
    text = json.dumps((persona.resume_content if persona else {}) or {}).lower()
    return any(term in text for term in ("master", "m.s.", "ms in", "ph.d", "phd", "doctorate"))


def evaluate_eligibility(
    row: FeedJob,
    *,
    allowed_families: set[str],
    has_advanced_degree: bool,
    description: str | None = None,
) -> EligibilityResult:
    family = classify_role_family(row.title)
    blockers: list[str] = []
    warnings: list[str] = []
    flags = row.flags or {}
    if family not in allowed_families:
        blockers.append("role family is outside SWE/AI/Data")
    if not location_is_us(row.location):
        blockers.append("location is outside the United States")
    if flags.get("closed"):
        blockers.append("upstream marks the application closed")
    if flags.get("no_sponsorship"):
        blockers.append("upstream marks the role as no sponsorship")
    if flags.get("citizenship_required"):
        blockers.append("upstream marks U.S. citizenship as required")
    if flags.get("advanced_degree_required") and not has_advanced_degree:
        blockers.append("advanced degree is required")

    if description:
        normalized = re.sub(r"\s+", " ", description.lower())
        if any(re.search(pattern, normalized, re.IGNORECASE) for pattern in _NO_SPONSOR_PATTERNS):
            blockers.append("job description explicitly excludes sponsorship")
        if any(re.search(pattern, normalized, re.IGNORECASE) for pattern in _CITIZEN_PATTERNS):
            blockers.append("job description requires citizenship or clearance")
        if "sponsorship" in normalized and not any("sponsorship" in blocker for blocker in blockers):
            warnings.append("job description mentions sponsorship; verify the exact policy")
    return EligibilityResult(not blockers, family, blockers, warnings)


async def _fetch_descriptions(rows: list[dict], max_concurrent: int = 5):
    from backend.scraper.ats._descriptions import _fetch_descriptions_parallel

    return await _fetch_descriptions_parallel(rows, max_concurrent=max_concurrent)


def _parse_json_setting(value: str, default):
    try:
        parsed = json.loads(value)
        return parsed
    except (TypeError, json.JSONDecodeError):
        return default


def _same_location(left: str | None, right: str | None) -> bool:
    def normalize(value):
        return re.sub(r"[^a-z0-9]", "", (value or "").lower())
    a, b = normalize(left), normalize(right)
    return bool(a and b and (a == b or a in b or b in a))


def _find_existing_job(db, row: FeedJob, external_id: str) -> Job | None:
    job = db.query(Job).filter(Job.external_id == external_id).first()
    if job:
        return job
    content_hash = make_content_hash(row.company, row.title)
    for candidate in db.query(Job).filter(Job.content_hash == content_hash).all():
        if _same_location(candidate.location, row.location):
            return candidate
    return None


def _upsert_observation(db, row: FeedJob, source_key: str, job: Job) -> None:
    observation = db.query(JobFeedPosting).filter(
        JobFeedPosting.source_id == row.source_id,
        JobFeedPosting.source_key == source_key,
    ).first()
    if observation is None:
        observation = JobFeedPosting(
            source_id=row.source_id,
            repository_id=row.repository_id,
            source_key=source_key,
            job_id=job.id,
            source_url=row.url,
            source_posted_at=row.posted_at,
            flags=row.flags or {},
        )
        db.add(observation)
    else:
        observation.job_id = job.id
        observation.source_url = row.url
        observation.source_posted_at = row.posted_at
        observation.flags = row.flags or {}
        observation.last_seen_at = utcnow()


def _force_repository_retry(repository_ids: set[str]) -> None:
    if not repository_ids:
        return
    db = SessionLocal()
    try:
        for checkpoint in db.query(JobFeedCheckpoint).filter(
            JobFeedCheckpoint.repository_id.in_(repository_ids)
        ).all():
            checkpoint.last_commit_sha = None
        db.commit()
    finally:
        db.close()


async def sync_job_feeds(*, force: bool = False) -> dict:
    """Poll, filter, enrich, persist, and return queue candidates."""
    poll = await poll_feed_documents(force=force)
    config_db = SessionLocal()
    try:
        try:
            backfill_days = max(0, int(_setting(config_db, "job_feeds_backfill_days", "7")))
        except (TypeError, ValueError):
            backfill_days = 7
        try:
            max_jobs = max(1, min(100, int(_setting(config_db, "job_feeds_max_jobs_per_poll", "25"))))
        except (TypeError, ValueError):
            max_jobs = 25
        allowed = set(_parse_json_setting(
            _setting(config_db, "job_feeds_role_families", '["swe","ai","data"]'),
            ["swe", "ai", "data"],
        ))
        has_advanced_degree = _persona_has_advanced_degree(config_db)
    finally:
        config_db.close()

    recent = rows_within_days(poll.rows, backfill_days)
    prelim: list[FeedJob] = []
    filtered = 0
    for row in recent:
        result = evaluate_eligibility(
            row,
            allowed_families=allowed,
            has_advanced_degree=has_advanced_degree,
        )
        if result.eligible:
            prelim.append(row)
        else:
            filtered += 1

    # Merge exact ATS/application identities in-memory while keeping every
    # source occurrence for provenance.
    grouped: dict[str, list[FeedJob]] = {}
    for row in prelim:
        identity = application_identity(row.url) or f"fallback:{row.company}:{row.title}:{row.location}"
        grouped.setdefault(identity, []).append(row)

    candidates: list[tuple[list[FeedJob], Job | None]] = []
    db = SessionLocal()
    try:
        for rows in grouped.values():
            primary = min(rows, key=lambda item: item.age_days if item.age_days is not None else 9999)
            external_id = make_application_external_id(primary.url)
            if not external_id:
                external_id = hashlib.sha256(
                    f"{primary.company}|{primary.title}|{primary.location}".lower().encode()
                ).hexdigest()
            job = _find_existing_job(db, primary, external_id)
            queued = bool(job and db.query(ApplicationQueueItem).filter(
                ApplicationQueueItem.job_id == job.id
            ).first())
            if queued:
                for row in rows:
                    _upsert_observation(db, row, application_identity(row.url), job)
            else:
                candidates.append((rows, job))
        db.commit()
    finally:
        db.close()

    candidates.sort(key=lambda pair: (
        pair[0][0].age_days if pair[0][0].age_days is not None else 9999,
        pair[0][0].company.lower(), pair[0][0].title.lower(),
    ))
    overflow = candidates[max_jobs:]
    selected = candidates[:max_jobs]
    if overflow:
        _force_repository_retry({row.repository_id for rows, _ in overflow for row in rows})

    fetch_rows = []
    for rows, existing_job in selected:
        primary = rows[0]
        fetch_rows.append({
            "company": primary.company,
            "title": primary.title,
            "location": primary.location,
            "url": primary.url,
            "_identity": application_identity(primary.url),
            "_existing_description": (existing_job.description if existing_job else None),
        })
    to_fetch = [row for row in fetch_rows if not (row.get("_existing_description") or "").strip()]
    if to_fetch:
        for fetch_result in await _fetch_descriptions(to_fetch, max_concurrent=5):
            if isinstance(fetch_result, Exception):
                logger.warning("Aggregate feed JD fetch failed: %s", fetch_result)
                continue
            source_row, description = fetch_result
            if description:
                source_row["description"] = description

    descriptions = {
        row["_identity"]: row.get("_existing_description") or row.get("description")
        for row in fetch_rows
    }
    queue_candidates: list[dict] = []
    new_jobs = reused_jobs = ineligible = 0
    db = SessionLocal()
    try:
        for rows, existing_job in selected:
            primary = rows[0]
            identity = application_identity(primary.url)
            external_id = make_application_external_id(primary.url) or hashlib.sha256(
                f"{primary.company}|{primary.title}|{primary.location}".lower().encode()
            ).hexdigest()
            description = descriptions.get(identity)
            eligibility = evaluate_eligibility(
                primary,
                allowed_families=allowed,
                has_advanced_degree=has_advanced_degree,
                description=description,
            )
            job = (
                db.query(Job).filter(Job.id == existing_job.id).first()
                if existing_job else _find_existing_job(db, primary, external_id)
            )
            if job is None:
                job = Job(
                    external_id=external_id,
                    content_hash=make_content_hash(primary.company, primary.title),
                    company=primary.company,
                    title=primary.title,
                    url=primary.url,
                    source=f"job_feed_{primary.source_id}",
                    description=description,
                    location=primary.location,
                    remote="remote" in (primary.location or "").lower(),
                    status="new",
                    seen=False,
                    saved=False,
                )
                apply_salary_to_job(job)
                if job.salary_min is None and primary.salary_min_hint is not None:
                    job.salary_min = primary.salary_min_hint
                    job.salary_max = primary.salary_max_hint
                    job.salary_source = primary.source_id
                try:
                    with db.begin_nested():
                        db.add(job)
                        db.flush()
                    new_jobs += 1
                except IntegrityError:
                    job = _find_existing_job(db, primary, external_id)
                    if not job:
                        raise
                    reused_jobs += 1
            else:
                reused_jobs += 1
                if not (job.description or "").strip() and description:
                    job.description = description
                    apply_salary_to_job(job)

            for row in rows:
                _upsert_observation(db, row, application_identity(row.url), job)

            status = "pending_tailor" if description else "pending_description"
            if not eligibility.eligible:
                status = "ineligible"
                ineligible += 1
            queue_candidates.append({
                "job_id": str(job.id),
                "feed_id": primary.source_id,
                "application_url": primary.url,
                "source_posted_at": primary.posted_at,
                "priority": 100 if (primary.age_days is not None and primary.age_days <= 1) else 10,
                "status": status,
                "eligibility_warnings": eligibility.warnings + eligibility.blockers,
                "description_ready": bool(description),
            })
        db.commit()
    finally:
        db.close()

    return {
        "jobs_found": len(poll.rows),
        "jobs_considered": len(selected),
        "new_jobs": new_jobs,
        "reused_jobs": reused_jobs,
        "filtered": filtered,
        "ineligible": ineligible,
        "overflow": len(overflow),
        "queue_candidates": queue_candidates,
        "feed_errors": poll.errors,
        "changed_repositories": poll.changed_repositories,
        "unchanged_repositories": poll.unchanged_repositories,
    }
