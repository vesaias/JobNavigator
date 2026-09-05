"""Tests the Log-application URL reader's employer detection: _company_from_url() pulls the employer from a known ATS board slug, _is_ats_brand() suppresses a brand-looking fallback like "Greenhouse" or "Linkedin"."""
import pytest

from backend.api.routes_applications import (
    _company_from_url,
    _is_ats_brand,
    _title_slug,
)


# ── the five ATS URL shapes ───────────────────────────────────────────────────

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
# ATS brand, and <title> is the SPA shell.
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


@pytest.mark.asyncio
async def test_extract_posting_uses_board_slug_not_ats_brand(_offline_fetch):
    from backend.api.routes_applications import ExtractRequest, extract_posting
    _offline_fetch(_GREENHOUSE_HTML)
    out = await extract_posting(ExtractRequest(
        url="https://job-boards.greenhouse.io/duolingo/jobs/8730683002"))
    assert out["company"] == "Duolingo"


@pytest.mark.asyncio
async def test_extract_posting_leaves_company_empty_when_only_brand_is_known(_offline_fetch):
    """LinkedIn has no employer slug in the URL — better empty than "Linkedin"."""
    from backend.api.routes_applications import ExtractRequest, extract_posting
    _offline_fetch(_LINKEDIN_HTML)
    out = await extract_posting(ExtractRequest(
        url="https://www.linkedin.com/jobs/view/4452146724"))
    assert out["company"] is None


@pytest.mark.asyncio
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


# ── HTML entities in the extracted fields ────────────────────────────────────
# JSON-LD lives inside a <script>, which BeautifulSoup hands back as raw text —
# nothing there decodes an entity like "&amp;", and json.loads has no reason to.

@pytest.mark.parametrize("raw,expected", [
    ("AI Strategy &amp; Health Plan Tech", "AI Strategy & Health Plan Tech"),
    ("R&amp;D Lead &mdash; Remote", "R&D Lead — Remote"),
    ("Caf&eacute; Manager", "Café Manager"),
    ("Double &amp;amp; encoded", "Double & encoded"),
    ("Nothing to decode", "Nothing to decode"),
    ("", ""),
    (None, None),
])
def test_decode_entities(raw, expected):
    from backend.api.routes_applications import _decode_entities
    assert _decode_entities(raw) == expected


@pytest.mark.asyncio
async def test_extract_posting_decodes_entities_in_a_jsonld_title(_offline_fetch):
    """LinkedIn's JSON-LD title carries `&amp;`, which must be decoded."""
    from backend.api.routes_applications import ExtractRequest, extract_posting
    _offline_fetch("""
    <html><head>
    <script type="application/ld+json">
    {"@type":"JobPosting",
     "title":"Lead Technical Product Manager - AI Strategy &amp; Health Plan Tech - Remote Kansas",
     "hiringOrganization":{"@type":"Organization","name":"Optum &amp; Co"}}
    </script></head><body></body></html>
    """)
    out = await extract_posting(ExtractRequest(
        url="https://www.linkedin.com/jobs/view/4460587357"))
    assert out["title"] == ("Lead Technical Product Manager - AI Strategy & "
                            "Health Plan Tech - Remote Kansas")
    assert out["company"] == "Optum & Co"


@pytest.mark.asyncio
async def test_extract_posting_decodes_entities_in_an_og_title(_offline_fetch):
    from backend.api.routes_applications import ExtractRequest, extract_posting
    _offline_fetch("""
    <html><head><meta property="og:title" content="Research &amp;amp; Insights Manager">
    </head><body></body></html>
    """)
    out = await extract_posting(ExtractRequest(
        url="https://job-boards.greenhouse.io/duolingo/jobs/1"))
    assert out["title"] == "Research & Insights Manager"
