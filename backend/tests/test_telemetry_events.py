"""telemetry/events.py: health events from the scrape log, LLM log, run history and jobs; buckets
and categories only, never names or text."""
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from backend.accounts.context import unscoped
from backend.models.db import Account, Company, JobRun, LlmCallLog, ScrapeLog, Search
from backend.telemetry import buckets as B
from backend.telemetry import categories as C
from backend.telemetry import events as E
from backend.tests.r4_support import set_setting
from backend.tests.test_posting_links import _job

NOW = datetime.now(timezone.utc)
SINCE = NOW - timedelta(days=1)

SCRAPE_ERRORS = {
    "https://job-boards.greenhouse.io/x: BoardNotFoundError: Greenhouse board 'x' not found (HTTP 404)": "board_not_found",
    "https://jobs.apple.com/x: TimeoutError: Page.goto: Timeout 30000ms exceeded.": "timeout",
    "Client error '403 Forbidden' for url 'https://x.wd5.myworkdayjobs.com'": "http_403",
    "HTTP 429 Too Many Requests": "http_429",
    "Server disconnected without sending a response.": "http_5xx",
    "A string literal cannot contain NUL (0x00) characters.": "parse",
    "Just a moment... Cloudflare": "bot_wall",
    "something odd": "other",
}
LLM_ERRORS = {
    "claude-code subprocess failed (rc=1): [claude-code:unrecognized_model] {\"model\":\"gemini-3\"}": "unknown_model",
    "JSON decode: Expecting value: line 1 column 1 (char 0)": "bad_response",
    "The model's reply was not valid JSON — try again": "bad_response",
    "Error code: 401 - invalid x-api-key": "auth",
    "Error code: 429 - rate_limit_error": "rate_limit",
    "Your credit balance is too low": "quota",
    "claude: command not found (rc=127)": "cli_missing",
    "Request timed out": "timeout",
    "claude-code subprocess failed (rc=1): ": "cli_error",
    "something else entirely": "other",
}


@pytest.mark.parametrize("n,expected", [(0, "0"), (1, "1"), (2, "2_5"), (5, "2_5"), (6, "6_20"),
                                        (20, "6_20"), (21, "21_100"), (100, "21_100"), (101, "101_plus")])
def test_bucket_edges(n, expected):
    assert B.bucket(n) == expected


@pytest.mark.parametrize("n,expected", [(0, "1"), (1, "1"), (3, "3"), (5, "5"), (6, "6_plus"), (40, "6_plus")])
def test_accounts_bucket(n, expected):
    assert B.accounts_bucket(n) == expected


def test_duration_and_interval_buckets():
    assert [B.duration_bucket(s) for s in (None, 0.5, 3, 20, 700)] == ["unknown", "lt_1s", "1_5s", "15_30s", "10m_plus"]
    assert [B.interval_bucket(m) for m in (0, 30, 120, 600, 3500)] == ["off", "lt_1h", "1_6h", "6_24h", "daily_plus"]


@pytest.mark.parametrize("text,expected", SCRAPE_ERRORS.items())
def test_scrape_error_categories(text, expected):
    assert C.scrape_error_category(text) == expected


@pytest.mark.parametrize("text,expected", LLM_ERRORS.items())
def test_llm_error_categories(text, expected):
    assert C.llm_error_category(text) == expected


def test_no_error_is_no_category():
    assert C.scrape_error_category(None) is None and C.scrape_error_category("  ") is None
    assert C.tally(["timeout", None, "http_404", "timeout"]) == "timeout=2, http_404=1"


def _company(db, name, urls):
    c = Company(name=name, scrape_urls=urls, active=True)
    db.add(c)
    db.commit()
    return c


def _log(db, company=None, source=None, found=0, error=None, run_id=None, breakdown=None, secs=10.0):
    db.add(ScrapeLog(company_id=company.id if company else None, source=source or f"playwright_{company.name}",
                     jobs_found=found, error=error, run_id=run_id, source_breakdown=breakdown,
                     duration_seconds=secs, ran_at=NOW - timedelta(hours=1)))
    db.commit()


def test_scraper_health_counts(test_db):
    wd = _company(test_db, "Nvidia", ["https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite"])
    _log(test_db, wd, found=12)
    _log(test_db, wd, found=8)
    _log(test_db, wd, error="TimeoutError: Page.goto: Timeout 30000ms exceeded")
    _log(test_db, wd, found=0)
    with unscoped():
        out = E.scraper_health(test_db, SINCE, "essentials")
    assert out == [{"kind": "workday", "runs": 4, "ok": 2, "failed": 1, "empty": 1,
                    "error_types": "timeout=1", "jobs_found": "6_20", "duration": "5_15s"}]


def test_a_shared_fetch_counts_once(test_db):
    gh = _company(test_db, "Acme", ["https://job-boards.greenhouse.io/acme"])
    run = uuid.uuid4()
    _log(test_db, gh, found=3, run_id=run)
    _log(test_db, gh, found=3, run_id=run)
    with unscoped():
        assert E.scraper_health(test_db, SINCE, "essentials")[0]["runs"] == 1


def test_creative_boards_report_each_board(test_db):
    _log(test_db, source="creative", found=5, breakdown={
        "behance": {"returned": 5}, "eluta_typo": {"returned": 1},
        "dribbble": {"returned": 0, "error": "HTTP 403 Forbidden"}})
    with unscoped():
        out = {e["kind"]: e for e in E.scraper_health(test_db, SINCE, "essentials")}
    assert out["creative:behance"]["ok"] == 1 and out["creative:dribbble"]["error_types"] == "http_403=1"
    assert "creative:eluta_typo" not in out and "creative" not in out


def test_jobspy_reports_each_board(test_db):
    _log(test_db, source="jobspy", found=18, breakdown={
        "indeed": {"returned": 18}, "linkedin": {"returned": 0, "error": "HTTP 429 Too Many Requests"}})
    with unscoped():
        out = {e["kind"]: e for e in E.scraper_health(test_db, SINCE, "essentials")}
    assert out["jobspy:indeed"]["ok"] == 1 and out["jobspy:linkedin"]["error_types"] == "http_429=1"


def test_a_deleted_companys_rows_never_send_its_name(test_db):
    """Deleting a company leaves its log rows with company_id NULL and source 'playwright_<name>'."""
    test_db.add(ScrapeLog(company_id=None, source="playwright_Zyxcorp Inc", jobs_found=0,
                          error="timeout", ran_at=NOW - timedelta(hours=1)))
    test_db.commit()
    with unscoped():
        assert "zyxcorp" not in json.dumps(E.scraper_health(test_db, SINCE, "full")).lower()


def test_failing_hosts_only_at_full(test_db):
    gh = _company(test_db, "Zyxcorp", ["https://job-boards.greenhouse.io/zyxcorp"])
    _log(test_db, gh, error="BoardNotFoundError: Greenhouse board 'zyxcorp' not found (HTTP 404)")
    with unscoped():
        assert "failing_hosts" not in E.scraper_health(test_db, SINCE, "essentials")[0]
        assert E.scraper_health(test_db, SINCE, "full")[0]["failing_hosts"] == "job-boards.greenhouse.io"


def test_phenom_post_spec_reads_its_endpoint():
    assert E.board_host('POST|https://careers.circle.com/widgets|{"a":1}') == "careers.circle.com"
    assert E.scraper_kind_for_urls(['POST|https://careers.circle.com/widgets|{"a":1}']) == "phenom"


def test_llm_health_groups_by_provider_model_feature(test_db):
    for ok, err, ms in ((True, None, 4000), (True, None, 6000), (False, "Request timed out", 60000)):
        test_db.add(LlmCallLog(purpose="score_light", provider="claude_code", model="claude-sonnet-5",
                               success=ok, error=err, duration_ms=ms, input_tokens=0, output_tokens=0))
    test_db.add(LlmCallLog(purpose="tailor", provider="openai", model="gpt-5", success=True,
                           duration_ms=20000, input_tokens=3000, output_tokens=900))
    test_db.commit()
    with unscoped():
        out = {e["feature"]: e for e in E.llm_health(test_db, SINCE)}
    assert out["score_light"] == {"provider": "claude_code", "model": "claude-sonnet-5", "feature": "score_light",
                                  "calls": 3, "failed": 1, "error_types": "timeout=1", "latency": "5_15s",
                                  "tokens_in": "0", "tokens_out": "0"}
    assert out["tailor"]["tokens_in"] == "1_10k"


def test_lookup_health_reads_the_run_summaries(test_db):
    test_db.add(JobRun(job_type="linkedin_lookup", trigger="after scrape", status="completed",
                       result_summary="200 looked up - 161 employer links - 5 Easy Apply - 30 closed - "
                                      "0 from earlier answers - 2 short links followed"))
    test_db.add(JobRun(job_type="linkedin_lookup", trigger="after scrape", status="completed",
                       result_summary="3 looked up - 0 employer links - 0 Easy Apply - 0 closed - 0 from earlier "
                                      "answers - 0 short links followed - stopped: the LinkedIn mock session is signed out"))
    test_db.commit()
    with unscoped():
        out = E.lookup_health(test_db, SINCE)
    assert out == {"runs": 2, "looked_up": "101_plus", "employer": "101_plus", "easy_apply": "2_5",
                   "closed": "21_100", "short_links": "2_5", "stopped": "signed_out=1"}


def test_heartbeat_fields(test_db):
    set_setting(test_db, "llm_provider", "claude_code")
    set_setting(test_db, "llm_model", "claude-sonnet-5")
    set_setting(test_db, "scrape_interval_minutes", "3500")
    test_db.add(Search(name="S", search_mode="keyword", sources=["indeed", "linkedin"], active=True))
    test_db.add(Search(name="J", search_mode="jobright", active=True))
    _company(test_db, "Acme", ["https://jobs.lever.co/acme"])
    with unscoped():
        hb = E.heartbeat(test_db, "app_started")
    assert hb["accounts"] == "1" and hb["event"] == "app_started" and len(hb["install_id"]) == 36
    assert hb["search_modes"] == "jobright, jobspy:indeed, jobspy:linkedin"
    assert hb["ats_kinds"] == "lever" and hb["companies"] == "1"
    assert hb["llm"] == "primary=claude_code:claude-sonnet-5" and hb["scrape_interval"] == "daily_plus"
    for i in range(6):
        test_db.add(Account(name=f"M{i}", role="member"))
    test_db.commit()
    with unscoped():
        assert E.heartbeat(test_db, "daily_heartbeat")["accounts"] == "6_plus"


def test_values_are_plain(test_db):
    _company(test_db, "Acme", ["https://jobs.lever.co/acme"])
    with unscoped():
        for _name, data in E.daily_events(test_db, "full"):
            assert all(isinstance(v, (str, int, bool)) for v in data.values()), data


def test_no_names_or_text_in_any_event(test_db):
    """A company name, a job title and a search term never reach a payload, even inside errors;
    the only URL part sent is a failing board's host, and only at Full."""
    c = _company(test_db, "Zyxcorp", ["https://job-boards.greenhouse.io/zyxcorp"])
    test_db.add(Search(name="Qqsearchname", search_mode="keyword", search_term="qqsearchterm",
                       sources=["indeed"], active=True))
    _job(test_db, "https://job-boards.greenhouse.io/zyxcorp/jobs/4000001", company="Zyxcorp",
         title="Secret Title Qq", source="direct")
    _log(test_db, c, error="BoardNotFoundError: Greenhouse board 'zyxcorp' Secret Title Qq qqsearchterm (HTTP 404)")
    _log(test_db, source="jobspy", breakdown={"indeed": {"returned": 0, "error": "qqsearchterm Zyxcorp 403"}})
    test_db.add(LlmCallLog(purpose="score_light", provider="claude_code", model="m", success=False,
                           error="Zyxcorp Secret Title Qq qqsearchterm timed out"))
    test_db.commit()
    with unscoped():
        events = E.daily_events(test_db, "full")
    payload = json.dumps(events).lower()
    for secret in ("zyxcorp/", "secret title", "qqsearchterm", "qqsearchname", "/jobs/4000001"):
        assert secret not in payload, secret
    hosts = [d.get("failing_hosts") for n, d in events if n == "scraper_health"]
    assert any(h == "job-boards.greenhouse.io" for h in hosts)   # Full's failing board host
