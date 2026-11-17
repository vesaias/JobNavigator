"""Tests for ats/workday.py — detection + API mock."""
import pytest
from unittest.mock import AsyncMock, MagicMock


def test_is_workday_detects_myworkdayjobs():
    from backend.scraper.ats.workday import is_workday
    assert is_workday("https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite")


def test_is_workday_detects_locale_prefix():
    from backend.scraper.ats.workday import is_workday
    assert is_workday("https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite")


def test_is_workday_rejects_non_workday():
    from backend.scraper.ats.workday import is_workday
    assert not is_workday("https://boards.greenhouse.io/acme")
    assert not is_workday("https://jobs.lever.co/acme")
    assert not is_workday("https://example.com/careers")


def test_is_workday_rejects_path_injection():
    from backend.scraper.ats.workday import is_workday
    assert not is_workday("https://evil.com/?x=myworkdayjobs.com")


def test_parse_workday_url_extracts_components():
    from backend.scraper.ats.workday import _parse_workday_url
    url = "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite"
    origin, company, site, facets = _parse_workday_url(url)
    assert origin == "https://nvidia.wd5.myworkdayjobs.com"
    assert company == "nvidia"
    assert site == "NVIDIAExternalCareerSite"
    assert facets == {}


def test_parse_workday_url_skips_locale_prefix():
    from backend.scraper.ats.workday import _parse_workday_url
    url = "https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite"
    origin, company, site, facets = _parse_workday_url(url)
    assert site == "NVIDIAExternalCareerSite"  # NOT "en-US"


def test_parse_workday_url_captures_facets():
    from backend.scraper.ats.workday import _parse_workday_url
    url = "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite?locations=abc123&timeType=def456"
    origin, company, site, facets = _parse_workday_url(url)
    assert "locations" in facets
    assert "timeType" in facets


@pytest.mark.asyncio
async def test_scrape_workday_calls_api(monkeypatch):
    """scrape() POSTs to /wday/cxs/{company}/{site}/jobs and parses jobPostings."""
    api_response_body = (
        '{"total": 2, "jobPostings": ['
        '{"title": "Senior Product Manager", "externalPath": "/job/123", "locationsText": "San Francisco"},'
        '{"title": "Staff Software Engineer", "externalPath": "/job/456", "locationsText": "Remote"}'
        ']}'
    )

    mock_resp = MagicMock()
    mock_resp.text = api_response_body
    mock_resp.status_code = 200

    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    monkeypatch.setattr("httpx.AsyncClient", lambda **kw: mock_client)

    from backend.scraper.ats.workday import scrape
    jobs = await scrape("https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite")

    assert isinstance(jobs, list)
    assert len(jobs) == 2
    assert jobs[0]["title"] == "Senior Product Manager"
    assert "url" in jobs[0]
    assert "/job/123" in jobs[0]["url"]


@pytest.mark.asyncio
async def test_scrape_workday_handles_http_error(monkeypatch):
    """scrape() returns empty list on HTTP error, doesn't raise."""
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = ""

    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    monkeypatch.setattr("httpx.AsyncClient", lambda **kw: mock_client)

    from backend.scraper.ats.workday import scrape
    jobs = await scrape("https://nvidia.wd5.myworkdayjobs.com/Site")
    assert jobs == []


@pytest.mark.asyncio
async def test_scrape_workday_bad_url(monkeypatch):
    """scrape() returns empty for unparseable URL."""
    from backend.scraper.ats.workday import scrape
    # URL with no site segment
    jobs = await scrape("https://nvidia.wd5.myworkdayjobs.com/")
    assert jobs == []


# ── the 2,000-result ceiling ───────────────────────────────────────────────

class _FakeBoard:
    """A Workday board that behaves like the live API at the ceiling.

    `total` never exceeds 2,000, and an offset past 2,000 repeats earlier rows.
    Each posting has a category and a list of countries (a posting may be in
    several). Facet counts are computed over the filtered set, the way Workday
    reports them; countries sit nested under locationMainGroup.
    """

    def __init__(self, postings, facets_offered=("jobFamilyGroup", "country")):
        self.postings = postings
        self.facets_offered = facets_offered
        self.calls = []

    def _match(self, p, applied):
        for key, ids in applied.items():
            if key == "jobFamilyGroup" and p["cat"] not in ids:
                return False
            if key == "country" and not set(p["countries"]) & set(ids):
                return False
            if key == "keep" and p["keep"] not in ids:
                return False
        return True

    async def post(self, url, json=None, headers=None):
        import json as _json
        applied, offset, limit = json["appliedFacets"], json["offset"], json["limit"]
        self.calls.append(dict(applied))
        rows = [p for p in self.postings if self._match(p, applied)]
        real = len(rows)
        start = offset if offset < 2000 else offset % 2000
        page = rows[start:start + limit]
        facets = []
        if "jobFamilyGroup" in self.facets_offered:
            cats = {}
            for p in rows:
                cats[p["cat"]] = cats.get(p["cat"], 0) + 1
            facets.append({"facetParameter": "jobFamilyGroup",
                           "values": [{"id": k, "descriptor": k, "count": v} for k, v in cats.items()]})
        if "country" in self.facets_offered:
            ctr = {}
            for p in rows:
                for c in p["countries"]:
                    ctr[c] = ctr.get(c, 0) + 1
            facets.append({"facetParameter": "locationMainGroup", "values": [
                {"facetParameter": "country", "descriptor": "Locations",
                 "values": [{"id": k, "descriptor": k, "count": v} for k, v in ctr.items()]}]})
        resp = MagicMock()
        resp.status_code = 200
        resp.text = _json.dumps({"total": min(real, 2000) if offset == 0 else 0,
                                 "jobPostings": [{"title": f"Engineer {p['n']}",
                                                  "externalPath": f"/job/X/Engineer_{p['n']}",
                                                  "locationsText": "Santa Clara"} for p in page],
                                 "facets": facets if offset == 0 else []})
        return resp


def _board(monkeypatch, postings, **kw):
    board = _FakeBoard(postings, **kw)
    client = MagicMock()
    client.post = board.post
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr("httpx.AsyncClient", lambda **k: client)
    return board


def _postings(spec):
    """spec: [(category, count, countries)] -> numbered postings."""
    out, n = [], 0
    for cat, count, countries in spec:
        for _ in range(count):
            out.append({"n": n, "cat": cat, "countries": countries, "keep": "y"})
            n += 1
    return out


@pytest.mark.asyncio
async def test_board_over_the_ceiling_is_split_and_nothing_is_missed(monkeypatch):
    board = _board(monkeypatch, _postings([("eng", 1700, ["US"]), ("sales", 600, ["US", "DE"]),
                                          ("ops", 400, ["DE"])]))
    from backend.scraper.ats.workday import scrape
    jobs = await scrape("https://nvidia.wd5.myworkdayjobs.com/Site")
    assert len(jobs) == 2700
    assert len({j["url"] for j in jobs}) == 2700
    # split by category (no overlap, fewest requests), not by country
    assert {key for call in board.calls for key in call} == {"jobFamilyGroup"}


@pytest.mark.asyncio
async def test_part_still_at_the_ceiling_is_split_again(monkeypatch):
    # every facet has a part over the ceiling: category first (fewer requests), then country
    board = _board(monkeypatch, _postings([("eng", 1500, ["US"]), ("eng", 1000, ["DE"]),
                                          ("sales", 600, ["US", "DE"])]))
    from backend.scraper.ats.workday import scrape
    jobs = await scrape("https://nvidia.wd5.myworkdayjobs.com/Site")
    assert len({j["url"] for j in jobs}) == 3100
    assert any(set(c) == {"jobFamilyGroup", "country"} for c in board.calls)


@pytest.mark.asyncio
async def test_split_keeps_the_filters_in_the_company_url(monkeypatch):
    postings = _postings([("eng", 1800, ["US"]), ("sales", 900, ["US"])])
    for p in postings[::10]:
        p["keep"] = "n"
    board = _board(monkeypatch, postings)
    from backend.scraper.ats.workday import scrape
    jobs = await scrape("https://nvidia.wd5.myworkdayjobs.com/Site?keep=y")
    assert len(jobs) == 2430
    assert all(c.get("keep") == ["y"] for c in board.calls)


@pytest.mark.asyncio
async def test_board_under_the_ceiling_is_one_walk(monkeypatch):
    board = _board(monkeypatch, _postings([("eng", 1200, ["US"]), ("sales", 300, ["US"])]))
    from backend.scraper.ats.workday import scrape
    jobs = await scrape("https://nvidia.wd5.myworkdayjobs.com/Site")
    assert len(jobs) == 1500
    assert all(c == {} for c in board.calls)
    assert len(board.calls) == 75


@pytest.mark.asyncio
async def test_ceiling_without_a_facet_keeps_what_it_has(monkeypatch, caplog):
    _board(monkeypatch, _postings([("eng", 2600, ["US"])]), facets_offered=())
    from backend.scraper.ats.workday import scrape
    with caplog.at_level("WARNING"):
        jobs = await scrape("https://nvidia.wd5.myworkdayjobs.com/Site")
    assert len(jobs) == 2000
    assert "no facet to split by" in caplog.text


def test_facet_options_flattens_nested_location_groups():
    from backend.scraper.ats.workday import _facet_options
    opts = _facet_options([
        {"facetParameter": "jobFamilyGroup", "values": [{"id": "a", "count": 3}, {"id": "b", "count": 0}]},
        {"facetParameter": "locationMainGroup", "values": [
            {"facetParameter": "locationHierarchy2", "values": [{"id": "office", "count": 5}]},
            {"facetParameter": "locationHierarchy1", "values": [{"id": "us", "count": 4}, {"id": "de", "count": 1}]},
        ]},
    ])
    assert opts == [("jobFamilyGroup", [("a", 3)]), ("locationHierarchy2", [("office", 5)]),
                    ("locationHierarchy1", [("us", 4), ("de", 1)])]


@pytest.fixture(autouse=True)
def _no_retry_wait(monkeypatch):
    monkeypatch.setattr("backend.scraper.ats.workday._RETRY_WAITS", (0, 0))


def _client_answering(*answers):
    """An httpx.AsyncClient stand-in whose post() returns (status, text) answers in turn."""
    resps = []
    for status, text in answers:
        r = MagicMock()
        r.status_code, r.text = status, text
        resps.append(r)
    client = MagicMock()
    client.post = AsyncMock(side_effect=resps)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


_ONE_JOB = '{"total": 1, "jobPostings": [{"title": "Senior Product Manager", "externalPath": "/job/1"}]}'


@pytest.mark.asyncio
@pytest.mark.parametrize("blip", [(200, "<html>Workday is down for maintenance</html>"), (503, ""), (429, "")])
async def test_a_maintenance_page_or_busy_answer_is_retried(monkeypatch, blip):
    client = _client_answering(blip, (200, _ONE_JOB))
    monkeypatch.setattr("httpx.AsyncClient", lambda **kw: client)
    from backend.scraper.ats.workday import scrape
    jobs = await scrape("https://visa.wd5.myworkdayjobs.com/Visa")
    assert [j["title"] for j in jobs] == ["Senior Product Manager"]
    assert client.post.await_count == 2


@pytest.mark.asyncio
async def test_a_board_that_keeps_answering_html_fails_with_a_clear_message(monkeypatch):
    client = _client_answering(*[(200, "<html>bot check</html>")] * 3)
    monkeypatch.setattr("httpx.AsyncClient", lambda **kw: client)
    from backend.scraper.ats.workday import WorkdayUnavailable, scrape
    with pytest.raises(WorkdayUnavailable, match="non-JSON page"):
        await scrape("https://visa.wd5.myworkdayjobs.com/Visa")
    assert client.post.await_count == 3


@pytest.mark.real_workday_client
def test_the_workday_client_sends_a_browser_fingerprint():
    # Cloudflare answers 429 to httpx and requests on every Workday host (2026-11-17); curl_cffi
    # impersonating Chrome passes. No request is sent here: only the session that would send it.
    from curl_cffi.requests import AsyncSession
    from backend.scraper.ats.workday import _client
    session = _client(12)
    assert isinstance(session, AsyncSession)
    assert session.impersonate == "chrome"
    assert session.timeout == 12


@pytest.mark.asyncio
async def test_the_still_open_check_reads_workday_through_the_workday_client(monkeypatch):
    from backend.scraper._shared import still_open
    seen = []

    async def fake(url):
        seen.append(url)
        return 200, url, '{"jobPostingInfo": {"title": "Account Executive"}}'

    monkeypatch.setattr(still_open, "_fetch_workday", fake)
    state, _ = await still_open.check_link("https://acme.wd5.myworkdayjobs.com/en-US/Careers/job/Berlin/Account-Executive_R123")
    assert state == still_open.OPEN
    assert seen and "/wday/cxs/acme/Careers/" in seen[0]
