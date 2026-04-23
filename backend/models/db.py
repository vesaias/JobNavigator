"""All SQLAlchemy models for JobNavigator."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text, DateTime, Date,
    LargeBinary, ForeignKey, JSON, Index, create_engine, text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from backend.config import DATABASE_URL

# Pool args are Postgres-specific; SQLite (used in CI tests via DATABASE_URL=sqlite:///:memory:)
# rejects pool_size/max_overflow.
_engine_kwargs = {"pool_pre_ping": True}
if not DATABASE_URL.startswith("sqlite"):
    _engine_kwargs.update(pool_size=10, max_overflow=20)
engine = create_engine(DATABASE_URL, **_engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def utcnow():
    return datetime.now(timezone.utc)


# ── Settings ─────────────────────────────────────────────────────────────────
class Setting(Base):
    __tablename__ = "settings"

    key = Column(String, primary_key=True)
    value = Column(Text, nullable=False)
    description = Column(String, nullable=True)


# ── Searches ─────────────────────────────────────────────────────────────────
class Search(Base):
    __tablename__ = "searches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    active = Column(Boolean, default=True)
    sources = Column(JSON, default=["linkedin", "indeed", "zip_recruiter", "google", "direct"])
    search_mode = Column(String, default="keyword")  # keyword | url
    search_term = Column(String, nullable=True)
    direct_url = Column(String, nullable=True)
    location = Column(String, default="United States")
    is_remote = Column(Boolean, nullable=True)  # null=any
    job_type = Column(String, default="fulltime")
    hours_old = Column(Integer, default=24)
    results_wanted = Column(Integer, default=50)
    title_include_keywords = Column(JSON, default=[])
    title_exclude_keywords = Column(JSON, default=["intern", "junior", "associate"])
    company_filter = Column(JSON, default=[])
    company_exclude = Column(JSON, default=[])
    max_pages = Column(Integer, default=50)
    min_fit_score = Column(Integer, default=0)  # Jobright displayScore threshold (0=disabled)
    require_salary = Column(Boolean, default=False)  # Filter out jobs without salary info
    auto_scoring_depth = Column(String, default="off")  # off | light | full
    run_interval_minutes = Column(Integer, default=0)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)


# ── CVs ──────────────────────────────────────────────────────────────────────
class CV(Base):
    __tablename__ = "cvs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version = Column(String, nullable=False, unique=True)  # user-defined name, max 5
    filename = Column(String, nullable=False)
    pdf_data = Column(LargeBinary, nullable=False)
    extracted_text = Column(Text, nullable=True)
    page_count = Column(Integer, default=0)
    uploaded_at = Column(DateTime(timezone=True), default=utcnow)


# ── Companies ────────────────────────────────────────────────────────────────
class Company(Base):
    __tablename__ = "companies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, unique=True)
    active = Column(Boolean, default=True)
    scrape_urls = Column(JSON, default=[])              # list of career/search URLs
    tier = Column(Integer, nullable=True)
    selected_cv_ids = Column(JSON, default=[])          # list of CV UUIDs (or empty = all)
    playwright_enabled = Column(Boolean, default=True)
    scrape_interval_minutes = Column(Integer, nullable=True)  # NULL = use global default
    title_include_expr = Column(String, nullable=True)  # e.g. (Product OR Project) AND Manager
    title_exclude_keywords = Column(JSON, default=[])   # e.g. ["intern","junior","associate"]
    wait_for_selector = Column(String, nullable=True)   # CSS selector to wait for before extraction
    max_pages = Column(Integer, default=5)              # max pagination pages to scrape
    jobspy_search_term = Column(String, nullable=True)
    aliases = Column(JSON, default=[])               # alternative company names for matching
    auto_scoring_depth = Column(String, default="off")  # off | light | full
    h1b_slug = Column(String, nullable=True)
    h1b_lca_count = Column(Integer, nullable=True)
    h1b_approval_rate = Column(Float, nullable=True)
    h1b_median_salary = Column(Integer, nullable=True)
    h1b_last_checked = Column(DateTime(timezone=True), nullable=True)
    last_scraped_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)


# ── Jobs ─────────────────────────────────────────────────────────────────────
class Job(Base):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    short_id = Column(Integer, unique=True, nullable=True, index=True, server_default=text("nextval('jobs_short_id_seq')"))  # Auto-increment numeric ID for URLs
    external_id = Column(String, unique=True, nullable=False)  # SHA256 dedup key
    content_hash = Column(String, nullable=True, index=True)  # SHA256 of company+title for cross-source dedup
    linkedin_job_id = Column(String, nullable=True, index=True)  # LinkedIn numeric ID for cross-scraper dedup
    company = Column(String, nullable=True)
    title = Column(String, nullable=True)
    url = Column(String, nullable=True)
    source = Column(String, nullable=True)  # jobspy_linkedin | jobspy_indeed | etc.
    search_id = Column(UUID(as_uuid=True), ForeignKey("searches.id"), nullable=True)
    description = Column(Text, nullable=True)
    location = Column(String, nullable=True)
    remote = Column(Boolean, nullable=True)
    salary_min = Column(Integer, nullable=True)
    salary_max = Column(Integer, nullable=True)
    salary_source = Column(String, nullable=True)  # posting | lca_estimate | unknown
    h1b_company_lca_count = Column(Integer, nullable=True)
    h1b_company_approval_rate = Column(Float, nullable=True)
    h1b_jd_flag = Column(Boolean, default=False)
    h1b_jd_snippet = Column(String, nullable=True)
    h1b_verdict = Column(String, nullable=True)  # likely | unlikely | unknown
    cv_scores = Column(JSON, default={})     # {"CV Name": score, ...}
    best_cv_score = Column(Float, nullable=True, index=True)
    best_cv = Column(String, nullable=True)
    scoring_report = Column(JSON, nullable=True)  # Structured report: summary, keywords, requirement mapping
    cached_page_html = Column(Text, nullable=True)
    cached_page_text = Column(Text, nullable=True)
    page_cached_at = Column(DateTime(timezone=True), nullable=True)
    cache_error = Column(Text, nullable=True)
    seen = Column(Boolean, default=False)
    saved = Column(Boolean, default=False)
    status = Column(String, default="new")  # new | saved | applied | skip
    discovered_at = Column(DateTime(timezone=True), default=utcnow)

    search = relationship("Search", backref="jobs")
    applications = relationship("Application", back_populates="job")

    @staticmethod
    def clean_url(url):
        """Strip ATS application/apply suffixes from job URLs."""
        if not url:
            return url
        for suffix in ("/application", "/apply", "/thanks"):
            if url.split("?")[0].endswith(suffix):
                base, *qs = url.split("?", 1)
                url = base[:-len(suffix)] + ("?" + qs[0] if qs else "")
        return url

from sqlalchemy import event

@event.listens_for(Job.url, "set", retval=True)
def _clean_job_url(target, value, oldvalue, initiator):
    return Job.clean_url(value)


# ── Applications ─────────────────────────────────────────────────────────────
class Application(Base):
    __tablename__ = "applications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False)
    status = Column(String, default="applied")
    # applied|interview|offer|rejected — simplified 2026-04-23. The retired
    # screening/phone_screen/final_round values are backfilled to applied or
    # interview in seed.run_migrations; historical status_transitions rows
    # are preserved unchanged.
    applied_at = Column(DateTime(timezone=True), default=utcnow)
    cv_version_used = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    next_action = Column(String, nullable=True)
    next_action_date = Column(Date, nullable=True)
    last_email_received = Column(DateTime(timezone=True), nullable=True)
    last_email_snippet = Column(Text, nullable=True)
    status_transitions = Column(JSON, default=[])  # [{status, changed_at, source}]
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    job = relationship("Job", back_populates="applications")


def record_transition(app, new_status: str, source: str):
    """Record a status transition on an Application. Call BEFORE setting app.status."""
    from datetime import datetime, timezone
    if app.status == new_status:
        return
    transitions = list(app.status_transitions or [])
    transitions.append({
        "from": app.status,
        "to": new_status,
        "at": datetime.now(timezone.utc).isoformat(),
        "source": source,
    })
    app.status_transitions = transitions
    app.status = new_status


# ── Scrape Log ───────────────────────────────────────────────────────────────
class ScrapeLog(Base):
    __tablename__ = "scrape_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    search_id = Column(UUID(as_uuid=True), ForeignKey("searches.id"), nullable=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True)
    source = Column(String, nullable=True)
    jobs_found = Column(Integer, default=0)
    new_jobs = Column(Integer, default=0)
    error = Column(Text, nullable=True)
    is_warning = Column(Boolean, default=False)
    duration_seconds = Column(Float, nullable=True)
    ran_at = Column(DateTime(timezone=True), default=utcnow)


# ── Job Runs (execution tracking) ───────────────────────────────────────────
class JobRun(Base):
    __tablename__ = "job_runs"
    __table_args__ = (
        Index("ix_job_runs_job_type", "job_type"),
        Index("ix_job_runs_started_at", "started_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_type = Column(String, nullable=False)          # scrape_all, email_check, etc.
    trigger = Column(String, nullable=False)            # scheduler | manual
    status = Column(String, nullable=False, default="running")  # running | completed | failed
    started_at = Column(DateTime(timezone=True), default=utcnow)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Float, nullable=True)
    result_summary = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    meta = Column(JSON, nullable=True)


# ── LLM Call Log (observability for prompt caching / cost tracking) ─────────
class LlmCallLog(Base):
    __tablename__ = "llm_call_log"
    __table_args__ = (
        Index("ix_llm_call_log_created_at", "created_at"),
        Index("ix_llm_call_log_purpose", "purpose"),
        Index("ix_llm_call_log_job_id", "job_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    purpose = Column(String, nullable=False)  # score_light, score_full, tailor, email, pdf
    provider = Column(String, nullable=False, default="")  # claude_api, claude_code, openai, ollama, openai_compat
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True)
    model = Column(String, nullable=False, default="")
    input_tokens = Column(Integer, default=0, nullable=False)
    output_tokens = Column(Integer, default=0, nullable=False)
    cache_read_tokens = Column(Integer, default=0, nullable=False)
    cache_write_tokens = Column(Integer, default=0, nullable=False)
    cost_usd = Column(Float, default=0.0, nullable=False)
    duration_ms = Column(Integer, default=0, nullable=False)
    success = Column(Boolean, default=True, nullable=False)
    error = Column(Text, nullable=True)


# ── Activity Log ────────────────────────────────────────────────────────────
class ActivityLog(Base):
    __tablename__ = "activity_log_v2"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type = Column(String, nullable=False)       # scrape | h1b | cv_score | email | telegram
    message = Column(Text, nullable=False)
    company = Column(String, nullable=True)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)


# ── Resumes ─────────────────────────────────────────────────────────────────
class Resume(Base):
    __tablename__ = "resumes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    is_base = Column(Boolean, default=True)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("resumes.id", ondelete="SET NULL"), nullable=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True)
    template = Column(String, default="garamond")
    page_format = Column(String, default="letter")
    json_data = Column(JSON, default={})
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    parent = relationship("Resume", remote_side=[id], backref="tailored_versions")
    job = relationship("Job", backref="resumes")


# ── Tracer Links ───────────────────────────────────────────────────────────
class TracerLink(Base):
    __tablename__ = "tracer_links"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token = Column(String(10), unique=True, nullable=False, index=True)
    resume_id = Column(UUID(as_uuid=True), ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False)
    destination_url = Column(String, nullable=False)
    source_label = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    resume = relationship("Resume", backref="tracer_links")
    click_events = relationship("TracerClickEvent", backref="tracer_link", cascade="all, delete-orphan")


class TracerClickEvent(Base):
    __tablename__ = "tracer_click_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tracer_link_id = Column(UUID(as_uuid=True), ForeignKey("tracer_links.id", ondelete="CASCADE"), nullable=False)
    clicked_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    device_type = Column(String, default="unknown")
    ua_family = Column(String, default="unknown")
    os_family = Column(String, default="unknown")
    referrer_host = Column(String, nullable=True)
    ip_hash = Column(String, nullable=True)
    is_likely_bot = Column(Boolean, default=False)


# ── Helpers ──────────────────────────────────────────────────────────────────
def find_company_by_name(db, name: str):
    """Find a Company by name or alias (case-insensitive)."""
    if not name:
        return None
    from sqlalchemy import func
    nl = name.strip().lower()
    # Try exact name match first
    co = db.query(Company).filter(func.lower(Company.name) == nl).first()
    if co:
        return co
    # Check aliases
    for co in db.query(Company).filter(Company.aliases.isnot(None)).all():
        if any(a.lower() == nl for a in (co.aliases or [])):
            return co
    return None


def get_company_all_names(db) -> dict:
    """Return {lowercase_name: company} for all names + aliases. For bulk matching."""
    result = {}
    for co in db.query(Company).all():
        result[co.name.lower()] = co
        for a in (co.aliases or []):
            result[a.lower()] = co
    return result


def get_global_title_exclude(db) -> list:
    """Load global title exclude keywords from settings."""
    import json as _json
    row = db.query(Setting).filter(Setting.key == "title_exclude_global").first()
    if row and row.value:
        try:
            return _json.loads(row.value)
        except _json.JSONDecodeError:
            pass
    return []


def get_existing_external_ids(db) -> set:
    """Load all external_ids from jobs table into a set for fast dedup checking."""
    rows = db.query(Job.external_id).filter(Job.external_id != None).all()
    return {r[0] for r in rows}



def build_company_lookup(db) -> dict:
    """Build a lowercase name/alias -> Company lookup dict for fast matching."""
    lookup = {}
    for company in db.query(Company).all():
        lookup[company.name.lower()] = company
        if company.aliases:
            for alias in company.aliases:
                lookup[alias.lower()] = company
    return lookup


# ── Table creation ───────────────────────────────────────────────────────────
def create_tables():
    # Create sequence before tables (Job.short_id references it in server_default)
    with engine.connect() as conn:
        conn.execute(text("CREATE SEQUENCE IF NOT EXISTS jobs_short_id_seq"))
        conn.commit()
    Base.metadata.create_all(bind=engine)
