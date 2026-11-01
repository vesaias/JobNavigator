"""The events telemetry sends, built from rows the app already writes (scrape log, LLM call log,
run history, jobs). No I/O beyond the database; values are str / int / bool only, counts are
buckets, errors are categories. See docs/superpowers/specs/2026-10-26-telemetry-design.md."""
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from backend.telemetry.buckets import (accounts_bucket, bucket, duration_bucket, interval_bucket,
                                       median, tokens_bucket)
from backend.telemetry.categories import llm_error_category, scrape_error_category, tally
from backend.telemetry.level import FULL, install_id

from backend.scraper.search_modes import EXTENSION_MODES as _EXTENSION_SOURCES   # job.source of extension jobs
from backend.scraper.search_modes import CREATIVE_BOARDS, SEARCH_MODES

_SEARCH_SOURCES = {m.source for m in SEARCH_MODES.values()}   # ScrapeLog.source of searches
# Searches whose run reads several boards: each board is its own kind (None = any board key)
_BOARD_SPLIT = {"jobspy": None, "creative": frozenset(CREATIVE_BOARDS)}
_LLM_SLOTS = (("primary", "llm"), ("fallback", "llm_fallback"), ("scoring", "scoring_llm"),
              ("tailor", "cv_tailor_llm"), ("letter", "cover_letter_llm"),
              ("autofill", "autofill_llm"), ("email", "email_llm"))


def _now():
    return datetime.now(timezone.utc)


def _url_of(raw: str) -> str:
    """A scrape URL, or the endpoint of a 'POST|https://…|{json}' spec."""
    raw = (raw or "").strip()
    return raw.split("|", 2)[1] if raw.upper().startswith("POST|") else raw


def scraper_kind_for_urls(urls) -> str:
    from backend.api.routes_companies import detect_scrape_type
    for u in urls or []:
        if u and u.strip():
            return detect_scrape_type(u.strip()).split(" ", 1)[0].lower()
    return "none"


def board_host(raw: str):
    host = (urlparse(_url_of(raw)).hostname or "").lower()
    return host or None


# ── heartbeat ────────────────────────────────────────────────────────────────

def heartbeat(db, event: str) -> dict:
    from backend.accounts.settings import get_install_setting
    from backend.models.db import Account, Application, Company, Job, LlmCallLog, Search, Setting
    from backend.version import APP_VERSION
    week = _now() - timedelta(days=7)

    searches = db.query(Search.search_mode, Search.sources).filter(Search.active.is_(True)).all()
    modes = set()
    for mode, sources in searches:
        if mode in _EXTENSION_SOURCES:
            continue
        if mode == "keyword":
            modes.update(f"jobspy:{s}" for s in (sources or []) if isinstance(s, str))
        elif mode == "creative":
            modes.update(f"creative:{s}" for s in (sources or []) if s in CREATIVE_BOARDS)
        else:
            modes.add(mode or "keyword")
    companies = db.query(Company.scrape_urls).filter(Company.active.is_(True)).all()
    kinds = {scraper_kind_for_urls(urls) for (urls,) in companies if urls}

    llm = []
    for slot, base in _LLM_SLOTS:
        provider = str(get_install_setting(db, f"{base}_provider") or "").strip()
        if provider:
            model = str(get_install_setting(db, f"{base}_model") or "").strip()
            llm.append(f"{slot}={provider}:{model}" if model else f"{slot}={provider}")

    def _any_set(key):
        return db.query(Setting.id).filter(Setting.key == key, Setting.value.notin_(("", "false", "0"))).first() is not None

    def _calls(prefix):
        return db.query(LlmCallLog.id).filter(LlmCallLog.purpose.like(f"{prefix}%"),
                                              LlmCallLog.success.is_(True), LlmCallLog.created_at >= week).count()

    interval = get_install_setting(db, "scrape_interval_minutes") or 0
    try:
        interval = int(str(interval).strip())
    except ValueError:
        interval = 0
    return {
        "install_id": install_id(db),
        "version": APP_VERSION,
        "event": event,
        "accounts": accounts_bucket(db.query(Account.id).count()),
        "search_modes": ", ".join(sorted(modes)),
        "companies": bucket(len(companies)),
        "ats_kinds": ", ".join(sorted(kinds)),
        "llm": ", ".join(llm),
        "gmail": _any_set("gmail_refresh_token"),
        "telegram": _any_set("telegram_enabled"),
        "extension_7d": db.query(Job.id).filter(Job.source.in_(_EXTENSION_SOURCES), Job.discovered_at >= week).first() is not None,
        "linkedin_mock": bool(str(get_install_setting(db, "linkedin_mock_email") or "").strip()),
        "jobs_found_7d": bucket(db.query(Job.id).filter(Job.discovered_at >= week).count()),
        "scored_7d": bucket(_calls("score")),
        "tailored_7d": bucket(_calls("tailor")),
        "letters_7d": bucket(_calls("cover_letter")),
        "applications_7d": bucket(db.query(Application.id).filter(Application.applied_at >= week).count()),
        "applications_total": bucket(db.query(Application.id).count()),
        "scrape_interval": interval_bucket(interval),
    }


# ── scrapers ─────────────────────────────────────────────────────────────────

def scraper_health(db, since, level) -> list:
    """One event per scraper kind (company boards) and search type that ran since `since`.
    A shared fetch writes one log row per account: rows of one run are counted once."""
    from backend.models.db import Company, ScrapeLog, Search
    rows = db.query(ScrapeLog).filter(ScrapeLog.ran_at >= since).all()
    companies = {c.id: c for c in db.query(Company).filter(
        Company.id.in_({r.company_id for r in rows if r.company_id})).all()} if rows else {}
    groups, seen = {}, set()

    def add(kind, found, error, duration, hosts=()):
        g = groups.setdefault(kind, {"runs": 0, "ok": 0, "failed": 0, "empty": 0, "errors": [],
                                     "found": 0, "durations": [], "hosts": set()})
        g["runs"] += 1
        cat = scrape_error_category(error)
        if cat:
            g["failed"] += 1
            g["errors"].append(cat)
            g["hosts"].update(h for h in hosts if h)
        elif not found:
            g["empty"] += 1
        else:
            g["ok"] += 1
        g["found"] += found or 0
        g["durations"].append(duration)

    for r in rows:
        if r.company_id:
            company = companies.get(r.company_id)
            if company is None:
                continue
            key = (r.run_id or r.id, tuple(company.scrape_urls or ()))
            if key in seen:
                continue
            seen.add(key)
            add(scraper_kind_for_urls(company.scrape_urls), r.jobs_found, r.error, r.duration_seconds,
                [board_host(u) for u in company.scrape_urls or []])
            continue
        # Only a known search source is a kind: a deleted company's rows keep
        # source "playwright_<name>" with no company_id, and a name must never be sent.
        if r.source not in _SEARCH_SOURCES:
            continue
        key = (r.run_id or r.id, r.source)
        if key in seen:
            continue
        seen.add(key)
        breakdown = r.source_breakdown if isinstance(r.source_breakdown, dict) else None
        prefix = "jobspy" if (r.source or "").startswith("jobspy") else r.source
        if prefix in _BOARD_SPLIT and breakdown:
            # one kind per board; only a board the mode knows is named (never a stray key)
            for board, val in breakdown.items():
                if isinstance(val, dict) and (_BOARD_SPLIT[prefix] is None or board in _BOARD_SPLIT[prefix]):
                    add(f"{prefix}:{board}", val.get("returned") or 0, val.get("error"), r.duration_seconds)
            if r.error:
                add(prefix, 0, r.error, r.duration_seconds)
        else:
            add(r.source or "unknown", r.jobs_found, r.error, r.duration_seconds)

    out = []
    for kind, g in sorted(groups.items()):
        event = {"kind": kind, "runs": g["runs"], "ok": g["ok"], "failed": g["failed"],
                 "empty": g["empty"], "error_types": tally(g["errors"]),
                 "jobs_found": bucket(g["found"]), "duration": duration_bucket(median(g["durations"]))}
        if level == FULL and g["hosts"]:
            event["failing_hosts"] = ", ".join(sorted(g["hosts"]))
        out.append(event)
    return out


def posting_health(db, since) -> list:
    """Per posting kind: new jobs with / without a description, and open-check outcomes."""
    from backend.models.db import Job
    groups = {}
    for key, has_text in (db.query(Job.posting_key, Job.description.isnot(None))
                          .filter(Job.discovered_at >= since, Job.duplicate_of.is_(None),
                                  Job.status != "ignored").all()):   # filtered out: never fetched
        kind = (key or "none").split(":", 1)[0]
        g = groups.setdefault(kind, {"new_with_text": 0, "new_without_text": 0, "open": 0, "closed": 0, "unknown": 0})
        g["new_with_text" if has_text else "new_without_text"] += 1
    for key, state in (db.query(Job.posting_key, Job.open_state)
                       .filter(Job.open_checked_at >= since, Job.open_state.isnot(None)).all()):
        kind = (key or "none").split(":", 1)[0]
        g = groups.setdefault(kind, {"new_with_text": 0, "new_without_text": 0, "open": 0, "closed": 0, "unknown": 0})
        if state in ("open", "closed", "unknown"):
            g[state] += 1
    return [{"kind": k, **{f: bucket(v) for f, v in g.items()}} for k, g in sorted(groups.items())]


# ── LinkedIn lookup and LLM ──────────────────────────────────────────────────

_LOOKUP_NUMBERS = {"looked_up": r"(\d+) looked up", "employer": r"(\d+) employer links",
                   "easy_apply": r"(\d+) Easy Apply", "closed": r"(\d+) closed",
                   "short_links": r"(\d+) short links followed"}


def _stopped_category(text):
    if not text:
        return "none"
    t = text.lower()
    if "signed out" in t or "sign-in record" in t or "sign it in" in t:
        return "signed_out"
    if "no data" in t:
        return "no_data"
    if "mock" in t:
        return "no_mock"
    return "other"


def lookup_health(db, since):
    from backend.models.db import JobRun
    runs = (db.query(JobRun.result_summary, JobRun.status)
            .filter(JobRun.job_type == "linkedin_lookup", JobRun.started_at >= since).all())
    if not runs:
        return None
    totals = {k: 0 for k in _LOOKUP_NUMBERS}
    stopped = []
    for summary, _status in runs:
        for k, pattern in _LOOKUP_NUMBERS.items():
            m = re.search(pattern, summary or "")
            totals[k] += int(m.group(1)) if m else 0
        m = re.search(r"stopped: (.*)$", summary or "")
        stopped.append(_stopped_category(m.group(1) if m else None))
    return {"runs": len(runs), **{k: bucket(v) for k, v in totals.items()},
            "stopped": tally(s for s in stopped if s != "none") or "none"}


def llm_health(db, since) -> list:
    from backend.models.db import LlmCallLog
    groups = {}
    for c in db.query(LlmCallLog).filter(LlmCallLog.created_at >= since).all():
        g = groups.setdefault((c.provider or "unknown", c.model or "", c.purpose or "unknown"),
                              {"calls": 0, "failed": 0, "errors": [], "ms": [], "in": 0, "out": 0})
        g["calls"] += 1
        if not c.success:
            g["failed"] += 1
            g["errors"].append(llm_error_category(c.error))
        g["ms"].append(c.duration_ms)
        g["in"] += c.input_tokens or 0
        g["out"] += c.output_tokens or 0
    out = []
    for (provider, model, feature), g in sorted(groups.items()):
        ms = median(g["ms"])
        out.append({"provider": provider, "model": model, "feature": feature,
                    "calls": g["calls"], "failed": g["failed"], "error_types": tally(g["errors"]),
                    "latency": duration_bucket(ms / 1000 if ms is not None else None),
                    "tokens_in": tokens_bucket(g["in"]), "tokens_out": tokens_bucket(g["out"])})
    return out


def daily_events(db, level, since=None) -> list:
    """[(event name, data)] for the daily send."""
    since = since or _now() - timedelta(days=1)
    events = [("daily_heartbeat", heartbeat(db, "daily_heartbeat"))]
    events += [("scraper_health", e) for e in scraper_health(db, since, level)]
    events += [("posting_health", e) for e in posting_health(db, since)]
    lookup = lookup_health(db, since)
    if lookup:
        events.append(("linkedin_lookup_health", lookup))
    events += [("llm_health", e) for e in llm_health(db, since)]
    iid = install_id(db)
    return [(name, {**data, "install_id": iid}) for name, data in events]
