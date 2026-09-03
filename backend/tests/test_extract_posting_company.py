"""Tests for the Log-application URL reader's employer detection (R3-A-05).

The reader used to fill Company with the ATS's own brand ("Greenhouse", "Lever",
"Linkedin") because og:site_name / the hostname are the only signals an
ATS-hosted board gives. These cover the two helpers behind the fix:

  - _company_from_url(url)  — employer from a known ATS board slug/subdomain
  - _is_ats_brand(name)     — suppresses a brand-looking fallback

Both are pure functions, so nothing here imports backend.main or hits the network.
"""
import pytest

from backend.api.routes_applications import (
    _company_from_url,
    _is_ats_brand,
    _title_slug,
)


# ── the five ATS URL shapes from the finding ─────────────────────────────────

@pytest.mark.parametrize("url,expected", [
    # Greenhouse — both board hosts, and the embed form.
    ("https://job-boards.greenhouse.io/duolingo/jobs/8730683002", "Duolingo"),
    ("https://boards.greenhouse.io/vercel/jobs/6163585004", "Vercel"),
    ("https://boards.greenhouse.io/embed/job_board?for=duolingo", "Duolingo"),
    # Lever
    ("https://jobs.lever.co/matterport/1a2b3c4d-5e6f", "Matterport"),
    ("https://jobs.lever.co/clear-street/abc123", "Clear Street"),
    # Ashby
    ("https://jobs.ashbyhq.com/openai/8730683002", "Openai"),
    # SmartRecruiters — all three host shapes.
    ("https://jobs.smartrecruiters.com/BoschGroup/743999", "BoschGroup"),
    ("https://careers.smartrecruiters.com/Visa/743999", "Visa"),
    ("https://api.smartrecruiters.com/v1/companies/BoschGroup/postings/74", "BoschGroup"),
    # Workday — tenant subdomain, with and without a locale path segment.
    ("https://duolingo.wd5.myworkdayjobs.com/Duolingo/job/R-123", "Duolingo"),
    ("https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/R-9", "Nvidia"),
    # Rippling (predicate already existed; free to cover)
    ("https://ats.rippling.com/anthropic/jobs/abc", "Anthropic"),
])
def test_company_from_ats_url(url, expected):
    assert _company_from_url(url) == expected


# ── everything else returns None so the user's typed value wins ──────────────

@pytest.mark.parametrize("url", [
    "https://www.linkedin.com/jobs/view/4452146724",     # no employer in the URL
    "https://www.indeed.com/viewjob?jk=abc123",
    "https://careers.duolingo.com/jobs/8730683002",      # own domain → metadata path
    "https://example.com/careers/pm",
    "not-a-url",
    "",
    None,
])
def test_company_from_url_returns_none_for_non_ats(url):
    assert _company_from_url(url) is None


def test_company_from_url_ignores_board_chrome_segments():
    """my.greenhouse.io/users/self must not yield 'Users'."""
    assert _company_from_url("https://my.greenhouse.io/users/self") is None


def test_company_from_url_handles_slugless_board():
    assert _company_from_url("https://jobs.lever.co/") is None


# ── the brand blocklist ──────────────────────────────────────────────────────

@pytest.mark.parametrize("name", [
    "Greenhouse", "greenhouse.io", "Greenhouse Software", "Lever", "Ashby",
    "AshbyHQ", "SmartRecruiters", "Workday", "Linkedin", "LinkedIn Jobs",
    "Indeed.com", "ZipRecruiter", "Glassdoor", "Jobright", "levels.fyi",
    "Jobs", "Careers", "Job Board",
])
def test_is_ats_brand_true(name):
    assert _is_ats_brand(name) is True


@pytest.mark.parametrize("name", [
    "Duolingo", "Duolingo Careers", "Vercel", "Clear Street", "Meta",
    "JPMorgan Chase", "Bosch Group",
])
def test_is_ats_brand_false(name):
    assert _is_ats_brand(name) is False


def test_is_ats_brand_empty_is_not_a_brand():
    # Empty input is "no value", not "a board name" — the caller drops it anyway.
    assert _is_ats_brand("") is False
    assert _is_ats_brand(None) is False


# ── slug prettifying ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("slug,expected", [
    ("duolingo", "Duolingo"),
    ("clear-street", "Clear Street"),
    ("clear_street", "Clear Street"),
    ("BoschGroup", "BoschGroup"),   # already-cased slugs survive intact
    ("", ""),
])
def test_title_slug(slug, expected):
    assert _title_slug(slug) == expected


# ── end-to-end through /extract's handler (no network, no backend.main) ──────

class _FakeResp:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        return None


@pytest.fixture
def _offline_fetch(monkeypatch):
    """Stub the SSRF-guarded fetcher so extract_posting never touches DNS/HTTP."""
    import backend.scraper._shared.url_safety as us

    def _install(html):
        async def _fake_get(url, **kw):
            return _FakeResp(html)
        monkeypatch.setattr(us, "assert_public_http_url", lambda u: None)
        monkeypatch.setattr(us, "safe_get", _fake_get)
    return _install


# A Greenhouse-hosted board: no JSON-LD hiringOrganization, og:site_name is the
# ATS brand, <title> is the SPA shell. Exactly the R3-A-05 repro.
_GREENHOUSE_HTML = """
<html><head><title>Duolingo Careers</title>
<meta property="og:site_name" content="Greenhouse">
<meta property="og:title" content="Senior Product Manager">
</head><body></body></html>
"""

_LINKEDIN_HTML = """
<html><head><title>Veterinary Practice Manager | LinkedIn Jobs</title>
<meta property="og:site_name" content="LinkedIn">
</head><body></body></html>
"""


async def test_extract_posting_uses_board_slug_not_ats_brand(_offline_fetch):
    from backend.api.routes_applications import ExtractRequest, extract_posting
    _offline_fetch(_GREENHOUSE_HTML)
    out = await extract_posting(ExtractRequest(
        url="https://job-boards.greenhouse.io/duolingo/jobs/8730683002"))
    assert out["company"] == "Duolingo"


async def test_extract_posting_leaves_company_empty_when_only_brand_is_known(_offline_fetch):
    """LinkedIn has no employer slug in the URL — better empty than "Linkedin"."""
    from backend.api.routes_applications import ExtractRequest, extract_posting
    _offline_fetch(_LINKEDIN_HTML)
    out = await extract_posting(ExtractRequest(
        url="https://www.linkedin.com/jobs/view/4452146724"))
    assert out["company"] is None


async def test_extract_posting_keeps_jsonld_hiring_organization(_offline_fetch):
    """A real employer in JSON-LD still wins over the slug layer."""
    from backend.api.routes_applications import ExtractRequest, extract_posting
    _offline_fetch("""
    <html><head><meta property="og:site_name" content="Greenhouse">
    <script type="application/ld+json">
    {"@type":"JobPosting","title":"SOX Manager",
     "hiringOrganization":{"@type":"Organization","name":"Vercel Inc."}}
    </script></head><body></body></html>
    """)
    out = await extract_posting(ExtractRequest(
        url="https://job-boards.greenhouse.io/vercel/jobs/6163585004"))
    assert out == {"title": "SOX Manager", "company": "Vercel Inc."}
