"""caribbeanjobs source — param forwarding + parsing (no network)."""
from types import SimpleNamespace

import pytest
from bs4 import BeautifulSoup

from backend.scraper.sources import caribbeanjobs


def _card(html):
    return caribbeanjobs._parse_card(BeautifulSoup(html, "html.parser").select_one("div.job-result"))


def test_query_plan_forwards_url_filters_and_splits_keywords_out():
    s = SimpleNamespace(
        direct_url="https://www.caribbeanjobs.com/ShowResults.aspx?Keywords=go&Location=123&Category=3&Page=2",
        search_term="")
    assert caribbeanjobs._query_plan(s) == ({"Location": "123", "Category": "3"}, ["go"])


def test_query_plan_splits_the_term_on_commas_and_overrides_the_url_keywords():
    s = SimpleNamespace(
        direct_url="https://www.caribbeanjobs.com/ShowResults.aspx?Keywords=old&Location=123",
        search_term="software engineer, developer ,, backend")
    assert caribbeanjobs._query_plan(s) == ({"Location": "123"}, ["software engineer", "developer", "backend"])


def test_query_plan_splits_the_url_keywords_on_commas_too():
    """The OR-alternatives rule applies whether the phrases came from the term or the URL."""
    s = SimpleNamespace(
        direct_url="https://www.caribbeanjobs.com/ShowResults.aspx?Keywords=alpha%2C+beta+gamma&Location=123",
        search_term="")
    assert caribbeanjobs._query_plan(s) == ({"Location": "123"}, ["alpha", "beta gamma"])


def test_query_plan_ignores_a_non_caribbeanjobs_url():
    s = SimpleNamespace(direct_url="https://example.com/ShowResults.aspx?Keywords=go", search_term="")
    assert caribbeanjobs._query_plan(s) == ({}, [])


def test_query_plan_with_neither_url_nor_term_is_empty():
    s = SimpleNamespace(direct_url="", search_term="")
    assert caribbeanjobs._query_plan(s) == ({}, [])


@pytest.mark.asyncio
async def test_fetch_listings_merges_queries_and_dedupes(monkeypatch):
    """Comma-separated alternatives become separate board queries whose results are merged and
    deduped, so `software engineer, developer` is a real OR, not the board's all-words AND."""
    calls = []

    async def fake_keyword(client, base, keyword, wanted):
        calls.append((keyword, wanted))
        return {
            "software engineer": [{"url": "u1"}, {"url": "u2"}, {"url": ""}],
            "developer": [{"url": "u2"}, {"url": "u3"}],
        }.get(keyword, [])

    monkeypatch.setattr(caribbeanjobs, "_fetch_keyword", fake_keyword)
    rows = await caribbeanjobs._fetch_listings(object(), {}, ["software engineer", "developer"], 10)
    assert [r["url"] for r in rows] == ["u1", "u2", "u3"]
    assert calls[0] == ("software engineer", 10)
    assert calls[1] == ("developer", 8)   # the second query only needs the remainder


@pytest.mark.asyncio
async def test_fetch_listings_with_no_keywords_queries_the_url_filters_once(monkeypatch):
    calls = []

    async def fake_keyword(client, base, keyword, wanted):
        calls.append(keyword)
        return [{"url": "u1"}]

    monkeypatch.setattr(caribbeanjobs, "_fetch_keyword", fake_keyword)
    rows = await caribbeanjobs._fetch_listings(object(), {"Location": "1"}, [], 5)
    assert calls == [None]
    assert [r["url"] for r in rows] == ["u1"]


def test_clean_url_strips_the_tracking_query():
    assert caribbeanjobs._clean_url("/Electrical-Engineer-Job-238881.aspx?p=1|application_confirmed") == \
        "https://www.caribbeanjobs.com/Electrical-Engineer-Job-238881.aspx"
    assert caribbeanjobs._clean_url("") == ""


def test_parse_salary_reads_a_range_or_a_single_value():
    assert caribbeanjobs._parse_salary("85000 - 95000") == (85000, 95000)
    assert caribbeanjobs._parse_salary("TTD 120,000") == (120000, None)
    assert caribbeanjobs._parse_salary("Competitive") == (None, None)
    assert caribbeanjobs._parse_salary("") == (None, None)


def test_parse_listing_date():
    assert caribbeanjobs._parse_listing_date("Updated 18/09/2026") == "2026-09-18"
    assert caribbeanjobs._parse_listing_date("Updated soon") is None


def test_strip_html_flattens_and_unescapes():
    out = caribbeanjobs._strip_html("<p>Hello <b>world</b></p><ul><li>a</li></ul>")
    assert "<" not in out
    assert "Hello world" in out.replace("\n", " ")
    assert "<" not in caribbeanjobs._strip_html("<p>x &amp; y</p>")
    assert caribbeanjobs._strip_html("") == ""


def test_parse_card_maps_every_listing_field():
    j = _card("""
        <div class="module job-result">
          <div class="module-content">
            <div class="job-result-title">
              <h2 itemprop="title"><a href="/Electrical-Engineer-Job-238881.aspx?p=1|x" jobid="238881">Electrical Engineer</a></h2>
              <h3 itemprop="name"><a href="/Renu-Energy-TCI-Jobs-5900.aspx">Renu Energy TCI</a></h3>
            </div>
            <div class="job-result-overview"><ul class="job-overview">
              <li class="salary" itemprop="baseSalary">85000 - 95000</li>
              <li class="updated-time" itemprop="datePosted">Updated 18/09/2026</li>
              <li class="location" itemprop="jobLocation"><a href="/Other-Caribbean">Turks and Caicos Islands</a></li>
            </ul></div>
            <p itemprop="description"><span>Solar PV design.</span></p>
          </div>
        </div>""")
    assert j["title"] == "Electrical Engineer"
    assert j["company"] == "Renu Energy TCI"
    assert j["url"] == "https://www.caribbeanjobs.com/Electrical-Engineer-Job-238881.aspx"
    assert j["location"] == "Turks and Caicos Islands"
    assert j["posted"] == "2026-09-18"
    assert "Solar PV design." in j["description"]


def test_parse_card_tolerates_a_missing_salary_and_location():
    j = _card("""
        <div class="job-result"><div class="job-result-title">
          <h2><a href="/X-Job-1.aspx">Role</a></h2><h3><a href="/c">Co</a></h3>
        </div></div>""")
    assert j["title"] == "Role" and j["company"] == "Co"
    assert j["location"] == "" and j["salary_min"] is None and j["posted"] is None


def test_parse_detail_prefers_json_ld():
    html = """
        <html><body>
        <script id="jobPostingSchema" type="application/ld+json">
        {"@type": "JobPosting", "title": "Electrical Engineer",
         "description": "<p>Key <b>duties</b></p>",
         "datePosted": "2026-09-18T18:23:50+00:00",
         "employmentType": "Default",
         "baseSalary": {"value": {"minValue": "85000 - 95000", "maxValue": "85000 - 95000"}},
         "hiringOrganization": {"name": "Renu Energy TCI"},
         "jobLocation": {"address": {"addressLocality": "Turks and Caicos Islands"}}}
        </script></body></html>"""
    out = caribbeanjobs._parse_detail(html, {"title": "ignored", "company": "", "location": ""})
    assert out["title"] == "Electrical Engineer"
    assert out["company"] == "Renu Energy TCI"
    assert "duties" in out["description"] and "<" not in out["description"]
    assert out["posted"] == "2026-09-18"
    assert out["location"] == "Turks and Caicos Islands"
    assert (out["salary_min"], out["salary_max"]) == (85000, 95000)
    assert out["expired"] is False


def test_parse_detail_falls_back_to_the_html_description():
    html = """
        <html><body>
        <h1 class="job-details--title">Site Engineer</h1>
        <ul class="job-overview job-details--details">
          <li class="employment-type">Permanent full-time</li>
        </ul>
        <div class="job-details"><p>Build the <b>thing</b>.</p></div>
        </body></html>"""
    out = caribbeanjobs._parse_detail(html, {"title": "Site Engineer", "company": "", "location": ""})
    assert "Build the thing." in out["description"].replace("\n", " ")
    assert out["employment_type"] == "Permanent full-time"


def test_parse_detail_marks_a_past_valid_through_as_expired():
    html = """
        <html><body>
        <script id="jobPostingSchema" type="application/ld+json">
        {"@type": "JobPosting", "title": "Old", "validThrough": "2020-01-01T00:00:00+00:00"}
        </script></body></html>"""
    assert caribbeanjobs._parse_detail(html, {"title": "Old", "company": "", "location": ""})["expired"] is True


def test_parse_detail_ignores_the_always_present_expired_banner():
    """The board keeps `span.alert-expired` in the DOM on every page, hidden by CSS, so only
    validThrough may mark a posting expired."""
    html = '<html><body><span class="alert-expired">This job is expired</span></body></html>'
    assert caribbeanjobs._parse_detail(html, {})["expired"] is False


class _Resp:
    def __init__(self, status, headers=None):
        self.status_code = status
        self.headers = headers or {}


class _FakeClient:
    def __init__(self, statuses):
        self._statuses = list(statuses)
        self.calls = 0

    async def get(self, url, params=None):
        self.calls += 1
        return _Resp(self._statuses.pop(0))


def test_user_agent_identifies_the_project():
    assert "github.com/vesaias/JobNavigator" in caribbeanjobs._UA


def test_retry_after_parses_and_caps():
    assert caribbeanjobs._retry_after(_Resp(429, {"Retry-After": "7"})) == 7.0
    assert caribbeanjobs._retry_after(_Resp(429, {"Retry-After": "999"})) == 60.0
    assert caribbeanjobs._retry_after(_Resp(429, {})) == 0.0


@pytest.mark.asyncio
async def test_get_backs_off_on_429_then_returns(monkeypatch):
    async def _no_sleep(_seconds):
        return None
    monkeypatch.setattr(caribbeanjobs.asyncio, "sleep", _no_sleep)

    client = _FakeClient([429, 429, 200])
    resp = await caribbeanjobs._get(client, "u")
    assert resp.status_code == 200
    assert client.calls == 3


@pytest.mark.asyncio
async def test_get_returns_the_last_429_after_giving_up(monkeypatch):
    async def _no_sleep(_seconds):
        return None
    monkeypatch.setattr(caribbeanjobs.asyncio, "sleep", _no_sleep)

    client = _FakeClient([429, 429, 429])
    resp = await caribbeanjobs._get(client, "u")
    assert resp.status_code == 429   # the caller raises; the run reports the board error
    assert client.calls == 3
