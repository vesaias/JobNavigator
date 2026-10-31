"""Creative boards source: the board clients, the job_boards.py pipeline and the mode wiring (no network)."""
import json
import time
from types import SimpleNamespace

import httpx
import pytest

from backend.models.db import Job, Search, Setting
from backend.scraper import search_modes as M
from backend.scraper._shared import job_boards
from backend.scraper.sources import creative


def _search(**kw):
    base = dict(name="t", search_mode="creative", search_term="illustrator", location="", is_remote=None,
                hours_old=0, results_wanted=10, sources=["behance", "hollylist", "wanacreate"], company_filter=[])
    base.update(kw)
    return SimpleNamespace(**base)


class FakeSites:
    """One MockTransport handler for the three sites; records what each request asked."""

    def __init__(self):
        self.calls = []
        self.urls = []
        self.behance_pages = {1: [self.be_node(1), self.be_node(2, brief=True)]}
        self.holly = {None: [], "europe": []}
        self.holly_detail = {}
        self.wana_hits = []
        self.fail = set()
        self.behance_apply = None      # job.applicationUrl
        self.feeds = {}                # host -> rss bytes
        self.redirects = {}            # full url -> Location
        self.pages = {}                # full url -> html
        self.artstation = {}           # page -> jobs

    @staticmethod
    def be_node(i, brief=False, company="Acme"):
        return {"id": i, "oid": f"oid{i}", "jobType": "FREELANCE" if brief else "FULLTIME",
                "title": f"Illustrator {i}", "companyName": "" if brief else company,
                "url": f"https://www.behance.net/joblist/x/{i}", "remoteStatus": None if brief else "ONSITE",
                "isRemote": brief, "location": None, "locations": [] if brief else [{"displayName": "Paris, France"}]}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        host, path = request.url.host, request.url.path
        body = json.loads(request.content) if request.content else {}
        self.calls.append((host, path, body, dict(request.headers)))
        self.urls.append(str(request.url))
        if host in self.fail:
            return httpx.Response(503)
        if host == "www.behance.net" and path == "/joblist":
            if "js_challenge_value" not in request.headers.get("cookie", ""):
                return httpx.Response(403, text='document.cookie = "js_challenge_value=abc123; Path=/";')
            return httpx.Response(200, text="<html></html>")
        if host == "www.behance.net" and path == "/v3/graphql":
            v = body["variables"]
            if "combinedJobListings" in body["query"]:
                nodes = self.behance_pages.get(v["page"], [])
                return httpx.Response(200, json={"data": {"combinedJobListings": {
                    "nodes": nodes, "pageInfo": {"hasNextPage": v["page"] + 1 in self.behance_pages}}}})
            if v["isBrief"]:
                return httpx.Response(200, json={"data": {"freelanceBriefPublicInfo": {
                    "description": "Draw a book", "deliverables": "####", "candidateInfo": None,
                    "additionalDetails": "<p>Ten pages</p>", "company": "Brief Co"}}})
            return httpx.Response(200, json={"data": {"job": {
                "description": "<p>Full <b>text</b></p>", "postedOn": int(time.time()) - 3600,
                "applicationUrl": self.behance_apply,
                "company": {"name": "Acme"}, "salaryMin": 70000, "salaryMax": 90000,
                "salaryTimeframe": "ANNUAL", "salaryCurrency": "USD"}}})
        if host == "www.hollylist.com":
            v = body["variables"]
            if "getJobs" in body["query"]:
                jobs = self.holly[v["market"]][v["skip"]:v["skip"] + v["limit"]]
                return httpx.Response(200, json={"data": {"getJobs": {"jobs": jobs}}})
            return httpx.Response(200, json={"data": {"getJob": self.holly_detail.get(v["slug"], {})}})
        if host == "wana-api-server-prod.onrender.com":
            return httpx.Response(200, json={"api_key": "k", "endpoint": "https://search.wanacreate.art"})
        if host == "search.wanacreate.art":
            return httpx.Response(200, json={"found": len(self.wana_hits), "hits": [{"document": d} for d in self.wana_hits]})
        if host in ("dribbble.com", "www.workwithindies.com") and (path.endswith(".rss") or path.endswith("rss.xml")):
            return httpx.Response(200, content=self.feeds.get(host, _feed([])))
        if str(request.url) in self.redirects:
            return httpx.Response(302, headers={"location": self.redirects[str(request.url)]})
        if str(request.url).split("?")[0] in self.pages:
            return httpx.Response(200, text=self.pages[str(request.url).split("?")[0]])
        if host == "www.artstation.com":
            return httpx.Response(200, json={"total_count": 0, "data": self.artstation.get(int(request.url.params.get("page", "1")), [])})
        return httpx.Response(404)

    def to(self, host, path=None):
        return [c for c in self.calls if c[0] == host and (path is None or c[1] == path)]


@pytest.fixture
def sites(monkeypatch):
    fake = FakeSites()
    monkeypatch.setattr(job_boards, "http_client", lambda mounts=None: httpx.AsyncClient(
        transport=httpx.MockTransport(fake), follow_redirects=True))
    return fake


def _holly(i, public=True, market=None, added="2026-10-20T10:00:00.000Z", org="Studio"):
    return {"_id": f"h{i}", "slugUrl": f"job-h{i}", "title": f"Animator {i}\n  ", "organization": org if public else None,
            "isPublic": public, "dateAdded": added, "location": {"name": "London, UK" if market else "Los Angeles, CA"}}


# ── the board clients ───────────────────────────────────────────────────────

def test_board_keys_match_the_mode_table():
    assert tuple(creative.BOARDS) == M.CREATIVE_BOARDS


async def test_behance_passes_the_cookie_challenge_and_sends_the_same_token_twice(sites):
    sites.behance_pages[2] = [sites.be_node(3)]
    async with job_boards.http_client() as c:
        rows = await creative._behance_list(c, _search(is_remote=True), 10)
    assert [r["title"] for r in rows] == ["Illustrator 1", "Illustrator 2", "Illustrator 3"]
    gql = sites.to("www.behance.net", "/v3/graphql")
    assert [g[2]["variables"]["page"] for g in gql] == [1, 2]
    assert gql[0][2]["variables"]["filter"] == {"remoteStatus": "REMOTE"}
    token = gql[0][3]["x-bcp"]
    assert f"bcp={token}" in gql[0][3]["cookie"] and "js_challenge_value=abc123" in gql[0][3]["cookie"]
    assert (rows[0]["location"], rows[0]["arrangement"]) == ("Paris, France", "onsite")
    assert (rows[1]["location"], rows[1]["arrangement"]) == ("Remote", "remote")


async def test_behance_stops_at_the_limit(sites):
    sites.behance_pages = {p: [sites.be_node(p * 10 + i) for i in range(50)] for p in (1, 2, 3)}
    async with job_boards.http_client() as c:
        rows = await creative._behance_list(c, _search(), 60)
    assert len(rows) == 60 and len(sites.to("www.behance.net", "/v3/graphql")) == 2
    assert "filter" not in sites.to("www.behance.net", "/v3/graphql")[0][2]["variables"]


async def test_behance_details_fill_text_date_and_usd_salary_and_drop_masked_fields(sites):
    async with job_boards.http_client() as c:
        rows = await creative._behance_list(c, _search(), 10)
        for r in rows:
            r["source"] = "behance"          # _collect sets it
        await job_boards._fill_details(c, rows, creative.BOARDS)
    job, brief = rows
    assert (job["description"], job["salary_min"], job["salary_max"]) == ("Full text", 70000, 90000)
    assert job["posted"] is not None and job_boards.too_old(job, 2) is None
    assert brief["description"] == "Draw a book\n\nTen pages"          # "####" is a masked field
    assert brief["company"] == "Brief Co" and brief["posted"] is None


def test_annual_usd_refuses_other_currencies_periods_and_hourly_rates():
    assert job_boards.annual_usd(70000, 90000, "ANNUAL", "USD") == (70000, 90000)
    assert job_boards.annual_usd(70000, None, "YEARLY", "usd") == (70000, 70000)
    assert job_boards.annual_usd(35000, 45000, "ANNUAL", "INR") == (None, None)
    assert job_boards.annual_usd(15, 20, "ANNUAL", "USD") == (None, None)
    assert job_boards.annual_usd(5000, 6000, "MONTHLY", "USD") == (None, None)
    assert job_boards.annual_usd(None, None, None, None) == (None, None)


async def test_hollylist_drops_members_only_and_merges_both_markets_newest_first(sites):
    sites.holly[None] = [_holly(1, added="2026-10-20T10:00:00Z"), _holly(2, public=False)]
    sites.holly["europe"] = [_holly(3, market="europe", added="2026-10-22T10:00:00Z")]
    async with job_boards.http_client() as c:
        rows = await creative._hollylist_list(c, _search(location="London, UK", is_remote=True), 10)
    assert [r["title"] for r in rows] == ["Animator 3", "Animator 1"]
    assert rows[0]["url"] == "https://www.hollylist.com/job/job-h3"
    asked = {c[2]["variables"]["market"]: c[2]["variables"] for c in sites.to("www.hollylist.com")}
    assert set(asked) == {None, "europe"}
    assert (asked[None]["loc"], asked[None]["remote"], asked[None]["term"]) == ("London", True, "illustrator")


async def test_hollylist_pages_by_one_hundred(sites):
    sites.holly[None] = [_holly(i) for i in range(150)]
    async with job_boards.http_client() as c:
        rows = await creative._hollylist_market(c, _search(), None, 500)
    assert len(rows) == 150
    assert [c[2]["variables"]["skip"] for c in sites.to("www.hollylist.com")] == [0, 100]


def test_wana_filter_maps_remote_city_and_age(monkeypatch):
    monkeypatch.setattr(creative.time, "time", lambda: 1_000_000)
    assert creative._wana_filter(_search(is_remote=True, location="London", hours_old=24)) == \
        "workType:=REMOTE && createdAt_ts:>913600"
    assert creative._wana_filter(_search(location="Los Angeles, CA")) == "location.city:=`Los Angeles`"
    assert creative._wana_filter(_search()) == ""


def test_wana_row_prefers_the_original_posting_url():
    copied = creative._wana_row({"id": "a1", "title": "Pixel Artist", "company": {"name": "Conradical"},
                                 "jobLink": "https://www.linkedin.com/jobs/view/1", "workType": "REMOTE",
                                 "description": "<p>Draw</p>", "location": {"name": "Remote"},
                                 "salary": {"min": 60000, "max": 80000, "currency": "USD", "period": "YEARLY"},
                                 "createdAt": "2026-10-20T00:00:00.000Z"})
    assert (copied["url"], copied["arrangement"], copied["description"]) == ("https://www.linkedin.com/jobs/view/1", "remote", "Draw")
    assert (copied["salary_min"], copied["salary_max"]) == (60000, 80000)
    own = creative._wana_row({"id": "a2", "title": "Muralist", "salary": {"min": 35000, "currency": "INR", "period": "MONTHLY"}})
    assert own["url"] == "https://www.wanacreate.art/jobs/a2" and own["salary_min"] is None


def _feed(items) -> bytes:
    body = "".join(f"<item><title>{t}</title><link>{link}</link><description>{d}</description>"
                   f"<pubDate>{date}</pubDate>{extra}</item>" for t, link, d, date, extra in items)
    return (f'<?xml version="1.0"?><rss xmlns:dc="http://purl.org/dc/elements/1.1/"><channel>{body}'
            f'</channel></rss>').encode()


def _ld_page(ld: dict) -> str:
    return f'<html><script type="application/ld+json">{json.dumps(ld)}</script></html>'


NOW_RSS = "Mon, 26 Oct 2026 13:56:27 -0500"


def test_fix_escapes_keeps_valid_escapes_and_doubles_the_rest():
    raw = r'{"d": "target=\_blank \_x \n \"q\" \u00e9"}'
    assert json.loads(creative._fix_escapes(raw), strict=False)["d"] == 'target=\_blank \_x \n "q" é'


def test_jobposting_ld_reads_a_block_with_invalid_escapes():
    page = '<script type="application/ld+json">{"@type": "JobPosting", "description": "&lt;a target=\_blank&gt;x"}</script>'
    assert creative._jobposting_ld(page)["description"] == "&lt;a target=\_blank&gt;x"


async def test_dribbble_parses_the_feed_title_and_reads_the_page(sites):
    url = "https://dribbble.com/jobs/1-Motion-Designer"
    sites.feeds["dribbble.com"] = _feed([(
        "Acme is hiring for a position of Motion Designer in Remote, Anywhere", url + "?source=feed", "", NOW_RSS,
        "<dc:creator>Acme</dc:creator>")])
    sites.pages[url] = _ld_page({"@type": "JobPosting", "description": "<p>Animate</p>", "jobLocationType": "TELECOMMUTE",
                                 "applicantLocationRequirements": {"@type": "Country", "name": "Canada"}})
    async with job_boards.http_client() as c:
        rows = await creative._dribbble_list(c, _search(search_term="motion designer"), 10)
        for r in rows:
            r["source"] = "dribbble"
        assert (rows[0]["title"], rows[0]["company"], rows[0]["url"], rows[0]["arrangement"]) == (
            "Motion Designer", "Acme", url, "remote")
        await job_boards._fill_details(c, rows, creative.BOARDS)
    assert (rows[0]["description"], rows[0]["location"]) == ("Animate", "Remote: Canada")
    assert "keyword=motion+designer" in [u for u in sites.urls if "dribbble.com/jobs.rss" in u][0]


async def test_artstation_sends_remote_and_maps_localities(sites):
    sites.artstation = {1: [{"hash_id": "ab1", "title": "Concept Artist", "company_name": "EA", "work_remotely": False,
                             "description": "<p>Paint</p>", "how_to_apply": "Email us",
                             "recruitment_localities": [{"locality": {"formatted_name": "Vancouver, BC, Canada"}}],
                             "listing_placement": {"posted_at": "2026-10-26T00:21:54+00:00"}}]}
    async with job_boards.http_client() as c:
        rows = await creative._artstation_list(c, _search(search_term="artist", is_remote=True), 10)
    r = rows[0]
    assert (r["url"], r["location"], r["arrangement"]) == ("https://www.artstation.com/jobs/ab1", "Vancouver, BC, Canada", None)
    assert r["description"] == "Paint\n\nEmail us" and r["posted"].startswith("2026-10-26")
    assert "work_remotely=true" in [u for u in sites.urls if "artstation" in u][0]


async def test_work_with_indies_reads_the_feed_and_time_zone_bands_are_remote(sites):
    url = "https://www.workwithindies.com/careers/3guns-content-creator"
    sites.feeds["www.workwithindies.com"] = _feed([(
        "3Guns is hiring a Content Creator to work from Anywhere", url, "Make videos", NOW_RSS, ""),
        ("lightconstruct is hiring a 3D Environment Artist to work from CET ± 3 hours", url + "-2", "Build", NOW_RSS, "")])
    async with job_boards.http_client() as c:
        rows = await creative._wwi_list(c, _search(), 10)
    assert [(r["title"], r["company"], r["arrangement"]) for r in rows] == [
        ("Content Creator", "3Guns", "remote"), ("3D Environment Artist", "lightconstruct", "remote")]


def test_remote_drops_rows_the_posting_calls_onsite_and_unknown_rows_stay():
    s = _search(is_remote=True)
    assert job_boards._rejection(dict(job_boards.make_row(title="Illustrator", arrangement="onsite"), source="dribbble"),
                               s, creative.BOARDS, [], [], set(), set()) == "Not remote: onsite"
    assert job_boards._rejection(dict(job_boards.make_row(title="Illustrator"), source="dribbble"), s, creative.BOARDS, [], [], set(), set()) is None


@pytest.mark.parametrize("country,location,expected", [
    ("canada", "Toronto, ON, Canada", None),
    ("canada", "USA; Canada", None),
    ("canada", "Anywhere", None),
    ("canada", "Remote", None),                                 # no places listed
    ("canada", "", None),
    ("canada", "Spain; Portugal; Italy", "Not open to Canada"),
    ("canada", "CA, USA; CO, USA", "Not open to Canada"),       # CA is California
    ("usa", "CA, USA; CO, USA", None),
    ("usa", "Philippines", "Not open to United States"),
])
def test_remote_behance_rows_must_be_open_to_the_search_country(country, location, expected):
    row = dict(job_boards.make_row(title="Graphic Designer", location=location, arrangement="remote"), source="behance")
    assert job_boards._rejection(row, _search(is_remote=True, country=country), creative.BOARDS, [], [], set(), set()) == expected


def test_the_country_rule_is_for_remote_behance_rows_only():
    row = dict(job_boards.make_row(title="Graphic Designer", location="Spain"), source="behance")
    assert job_boards._rejection(row, _search(is_remote=None, country="canada"), creative.BOARDS, [], [], set(), set()) is None
    other = dict(job_boards.make_row(title="Graphic Designer", location="Spain", arrangement="remote"), source="dribbble")
    assert job_boards._rejection(other, _search(is_remote=True, country="canada"), creative.BOARDS, [], [], set(), set()) is None


def test_location_is_checked_here_only_for_boards_that_cannot_filter_it():
    s = _search(location="Vancouver, BC")
    in_city = dict(job_boards.make_row(title="Artist", location="Vancouver, BC, Canada"), source="artstation")
    elsewhere = dict(job_boards.make_row(title="Artist", location="Montreal, QC"), source="artstation")
    remote = dict(job_boards.make_row(title="Artist", location="Remote", arrangement="remote"), source="artstation")
    behance = dict(job_boards.make_row(title="Artist", location="Montreal, QC"), source="behance")
    reasons = [job_boards._rejection(r, s, creative.BOARDS, [], [], set(), set()) for r in (in_city, elsewhere, remote, behance)]
    assert reasons == [None, "Not in Vancouver", None, None]


async def test_collect_keeps_the_other_boards_when_one_fails(sites):
    sites.fail.add("www.hollylist.com")
    sites.wana_hits = [{"id": "w1", "title": "Illustrator 1", "jobLink": "https://www.behance.net/joblist/x/1"}]
    async with job_boards.http_client() as c:
        rows, breakdown = await job_boards._collect(c, _search(), creative._picked(_search()), 10)
    assert breakdown["hollylist"]["error"] == "HTTP 503 from https://www.hollylist.com/graphql"
    assert breakdown["behance"]["returned"] == 2 and breakdown["wanacreate"]["returned"] == 1
    assert len(rows) == 2                    # the Wana row has the same URL as a Behance row


# ── save pipeline ───────────────────────────────────────────────────────────

@pytest.fixture
def quiet(monkeypatch):
    async def fake_analyze(job, db=None, arrangement=None):
        job.work_arrangement = arrangement
    monkeypatch.setattr(job_boards, "analyze_inline", fake_analyze)
    monkeypatch.setattr("backend.activity.log_activity", lambda *a, **k: None)


async def test_run_saves_new_rows_and_reads_details_only_for_them(sites, quiet, test_db):
    search = Search(name="t", search_mode="creative", search_term="illustrator", sources=["behance", "wanacreate"],
                    results_wanted=10, hours_old=0, title_exclude_keywords=["senior"], company_exclude=[])
    test_db.add(search)
    test_db.commit()
    sites.wana_hits = [{"id": "w1", "title": "Senior Illustrator"}, {"id": "w2", "title": "Book Illustrator",
                       "company": {"name": "Pages"}, "description": "Long text"}]

    res = await creative.run(search)
    assert res["error"] is None and (res["new_jobs"], res["jobs_found"]) == (3, 3)
    assert res["source_breakdown"]["wanacreate"] == {"seen": 1, "new": 1, "returned": 2, "filtered": 1}
    assert res["source_breakdown"]["behance"] == {"seen": 2, "new": 2, "returned": 2}
    details = [c for c in sites.to("www.behance.net", "/v3/graphql") if "combinedJobListings" not in c[2]["query"]]
    assert len(details) == 2

    test_db.expire_all()
    saved = {j.title: j for j in test_db.query(Job).all()}
    assert set(saved) == {"Illustrator 1", "Illustrator 2", "Book Illustrator"}
    assert (saved["Illustrator 1"].source, saved["Illustrator 1"].salary_min) == ("behance", 70000)
    assert saved["Illustrator 2"].description == "Draw a book\n\nTen pages"
    assert saved["Book Illustrator"].url == "https://www.wanacreate.art/jobs/w2"

    sites.calls.clear()
    res = await creative.run(search)                   # the same postings again
    assert res["new_jobs"] == 0
    assert all("combinedJobListings" in c[2]["query"] for c in sites.to("www.behance.net", "/v3/graphql"))


async def test_run_drops_rows_whose_detail_date_is_too_old(sites, quiet, test_db, monkeypatch):
    search = Search(name="t", search_mode="creative", search_term="x", sources=["behance"], results_wanted=10,
                    hours_old=1, company_exclude=[])
    test_db.add(search)
    test_db.commit()
    sites.behance_pages = {1: [sites.be_node(1)]}
    real = creative._behance_detail

    async def stale(client, row):
        await real(client, row)
        row["posted"] = "2026-01-01T00:00:00+00:00"
    monkeypatch.setitem(creative.BOARDS, "behance", creative.Board("Behance", creative._behance_list, stale))

    res = await creative.run(search)
    assert (res["new_jobs"], res["jobs_found"]) == (0, 0)
    assert res["source_breakdown"]["behance"] == {"seen": 0, "new": 0, "returned": 1, "filtered": 1}


async def test_a_row_dropped_after_its_page_is_kept_ignored_and_not_read_again(sites, quiet, test_db, monkeypatch):
    search = Search(name="t", search_mode="creative", search_term="x", sources=["behance"], results_wanted=10,
                    hours_old=1, company_exclude=[])
    test_db.add(search)
    test_db.commit()
    sites.behance_pages = {1: [sites.be_node(1)]}
    real = creative._behance_detail

    async def stale(client, row):
        await real(client, row)
        row["posted"] = "2026-01-01T00:00:00+00:00"
    monkeypatch.setitem(creative.BOARDS, "behance", creative.Board("Behance", creative._behance_list, stale))

    res = await creative.run(search)
    assert (res["new_jobs"], res["ignored_jobs"]) == (0, 1)
    test_db.expire_all()
    row = test_db.query(Job).one()
    assert (row.status, row.content_hash) == ("ignored", None)

    sites.calls.clear()
    await creative.run(search)                         # its page is not read again
    assert all("combinedJobListings" in c[2]["query"] for c in sites.to("www.behance.net", "/v3/graphql"))


async def test_body_exclusion_keeps_the_job_ignored(sites, test_db, monkeypatch):
    search = Search(name="t", search_mode="creative", search_term="x", sources=["wanacreate"], results_wanted=10,
                    hours_old=0, company_exclude=[])
    test_db.add(search)
    test_db.commit()
    sites.wana_hits = [{"id": "w1", "title": "Illustrator", "company": {"name": "Acme"}, "description": "US citizens only"}]

    async def flag(job, db=None, arrangement=None):
        job.h1b_jd_flag = True
    monkeypatch.setattr(job_boards, "analyze_inline", flag)
    monkeypatch.setattr("backend.activity.log_activity", lambda *a, **k: None)
    res = await creative.run(search)
    assert (res["new_jobs"], res["ignored_jobs"]) == (0, 1)
    test_db.expire_all()
    assert test_db.query(Job).one().status == "ignored"


async def test_preview_says_when_it_sampled_the_job_pages(sites, test_db, monkeypatch):
    monkeypatch.setattr(job_boards, "PREVIEW_DETAIL_LIMIT", 1)
    search = Search(name="t", search_mode="creative", search_term="illustrator", sources=["behance"],
                    hours_old=0, company_exclude=[])
    out = await creative.preview(search, test_db)
    assert out["details_sampled"] == 1 and "1 of 2" in out["preview_note"]


async def test_run_reports_an_error_when_every_board_failed(sites, quiet, test_db):
    search = Search(name="t", search_mode="creative", search_term="x", sources=["hollylist"], company_exclude=[])
    test_db.add(search)
    test_db.commit()
    sites.fail.add("www.hollylist.com")
    res = await creative.run(search)
    assert res["error"] == "Hollylist: HTTP 503 from https://www.hollylist.com/graphql"


async def test_preview_reads_details_and_saves_nothing(sites, test_db):
    test_db.add(Setting(key="body_exclusion_phrases", value=json.dumps(["ten pages"])))
    test_db.commit()
    search = Search(name="t", search_mode="creative", search_term="illustrator", sources=["behance"],
                    hours_old=0, company_exclude=[])
    out = await creative.preview(search, test_db)
    assert out["raw_count"] == 2 and out["source_breakdown"] == {"behance": 2}
    by_title = {j["title"]: j for j in out["jobs"]}
    assert by_title["Illustrator 1"]["kept"] and by_title["Illustrator 1"]["salary"] == "70,000 – 90,000"
    assert by_title["Illustrator 2"]["reason"].startswith("Body exclusion")
    assert test_db.query(Job).count() == 0


# ── apply links: employer's link, on the board, neither ─────────────────────

GREENHOUSE = "https://job-boards.greenhouse.io/acme/jobs/1"


async def _saved(search_kw, test_db):
    search = Search(name="t", search_mode="creative", search_term="illustrator", results_wanted=10, hours_old=0,
                    company_exclude=[], **search_kw)
    test_db.add(search)
    test_db.commit()
    res = await creative.run(search)
    assert res["error"] is None
    test_db.expire_all()
    return {j.title: j for j in test_db.query(Job).all()}


@pytest.mark.parametrize("link,apply_url,kind", [
    (GREENHOUSE, GREENHOUSE, "direct"),                                  # names the employer's posting
    ("https://careerspage.io/acme/designer", "https://careerspage.io/acme/designer", "direct"),   # an employer's site
    ("https://www.behance.net/joblist/apply/1", None, "easy_apply"),     # Behance's own form
    (None, None, "board"),
])
async def test_behance_full_time_job_link_kinds(sites, quiet, test_db, link, apply_url, kind):
    sites.behance_apply = link
    job = (await _saved({"sources": ["behance"]}, test_db))["Illustrator 1"]
    assert (job.apply_url, job.link_kind) == (apply_url, kind)


async def test_behance_brief_is_applied_to_on_behance(sites, quiet, test_db):
    job = (await _saved({"sources": ["behance"]}, test_db))["Illustrator 2"]
    assert (job.apply_url, job.link_kind) == (None, "easy_apply")


@pytest.mark.parametrize("detail,apply_url,kind", [
    ({"descMark": "Text", "applyAt": GREENHOUSE}, GREENHOUSE, "direct"),
    ({"descMark": "Text", "applyAt": None}, None, "easy_apply"),
    ({"descMark": "Text", "applyAt": "https://www.hollylist.com/apply/1"}, None, "easy_apply"),
    ({"descMark": "Text", "applyAt": "https://www.linkedin.com/jobs/view/1"}, None, "board"),
    ({}, None, "board"),                     # the job page gave nothing: the link is not known
])
async def test_hollylist_link_kinds(sites, quiet, test_db, detail, apply_url, kind):
    sites.holly[None] = [_holly(1)]
    sites.holly_detail = {"job-h1": detail}
    job = (await _saved({"sources": ["hollylist"]}, test_db))["Animator 1"]
    assert (job.apply_url, job.link_kind) == (apply_url, kind)


@pytest.mark.parametrize("job_link,url,kind", [
    (GREENHOUSE, GREENHOUSE, "direct"),                             # the job's url is the employer's link
    ("https://www.linkedin.com/jobs/view/1", "https://www.linkedin.com/jobs/view/1", "board"),
    ("", "https://www.wanacreate.art/jobs/w1", "easy_apply"),
])
async def test_wana_create_link_kinds(sites, quiet, test_db, job_link, url, kind):
    sites.wana_hits = [{"id": "w1", "title": "Book Illustrator", "company": {"name": "Pages"}, "jobLink": job_link}]
    job = (await _saved({"sources": ["wanacreate"]}, test_db))["Book Illustrator"]
    assert (job.url, job.apply_url, job.link_kind) == (url, None, kind)


@pytest.mark.parametrize("location,apply_url,kind", [
    (GREENHOUSE, GREENHOUSE, "direct"),
    ("https://apptrkr.com/1", "https://apptrkr.com/1", "direct"),
    (None, None, "board"),                                          # no redirect: not known
    ("https://dribbble.com/session/new", None, "board"),
])
async def test_dribbble_link_kinds(sites, quiet, test_db, location, apply_url, kind):
    url = "https://dribbble.com/jobs/1-Illustrator"
    sites.feeds["dribbble.com"] = _feed([("Acme is hiring for a position of Illustrator in Remote", url + "?source=feed", "", NOW_RSS, "")])
    sites.pages[url] = _ld_page({"@type": "JobPosting", "description": "Draw"})
    if location:
        sites.redirects[url + "/apply_now"] = location
    job = (await _saved({"sources": ["dribbble"]}, test_db))["Illustrator"]
    assert (job.apply_url, job.link_kind) == (apply_url, kind)


@pytest.mark.parametrize("apply_link,kind", [(GREENHOUSE, "direct"), ("", "board"), (None, "board")])
async def test_artstation_link_kinds(sites, quiet, test_db, apply_link, kind):
    sites.artstation = {1: [{"title": "Illustrator", "company_name": "Acme", "hash_id": "abc", "work_remotely": True,
                             "description": "Draw", "how_to_apply": "<a href='mailto:a@b.co'>mail</a>",
                             "apply_link": apply_link}]}
    job = (await _saved({"sources": ["artstation"]}, test_db))["Illustrator"]
    assert (job.apply_url, job.link_kind) == (apply_link or None, kind)


@pytest.mark.parametrize("button,apply_url,kind", [
    ('<a id="apply-top" href="https://acme.zohorecruit.com/jobs/1" class="apply-button">Apply</a>',
     "https://acme.zohorecruit.com/jobs/1", "direct"),
    ('<a href="https://tally.so/r/abc" id="apply-top">Apply</a>', "https://tally.so/r/abc", "direct"),
    ('<a id="apply-top" href="mailto:jobs@acme.co">Apply</a>', None, "board"),
    ('<a id="apply-top" href="https://www.linkedin.com/jobs/view/1/">Apply</a>', None, "board"),   # a board, not the employer
    ("", None, "board"),
])
async def test_work_with_indies_link_kinds(sites, quiet, test_db, button, apply_url, kind):
    url = "https://www.workwithindies.com/careers/acme-illustrator"
    sites.feeds["www.workwithindies.com"] = _feed([("Acme is hiring an Illustrator to work remotely", url, "Draw", NOW_RSS, "")])
    sites.pages[url] = _ld_page({"@type": "JobPosting", "description": "Draw"}) + button
    job = (await _saved({"sources": ["workwithindies"]}, test_db))["Illustrator"]
    assert (job.apply_url, job.link_kind) == (apply_url, kind)


async def test_a_short_apply_link_is_stored_where_it_lands(sites, quiet, test_db, monkeypatch):
    async def landed(urls):
        return {u: GREENHOUSE for u in urls if u and "grnh.se" in u}
    monkeypatch.setattr(job_boards, "resolve_short_links", landed)
    sites.holly[None] = [_holly(1)]
    sites.holly_detail = {"job-h1": {"descMark": "Text", "applyAt": "https://grnh.se/abc"}}
    job = (await _saved({"sources": ["hollylist"]}, test_db))["Animator 1"]
    assert (job.apply_url, job.link_kind) == (GREENHOUSE, "direct")


def test_employer_apply_keeps_employer_links_only():
    assert job_boards.employer_apply(GREENHOUSE) == GREENHOUSE
    for link in (None, "", "mailto:jobs@acme.co", "https://www.linkedin.com/jobs/view/1", "https://dribbble.com/x"):
        assert job_boards.employer_apply(link) is None


# ── mode wiring ─────────────────────────────────────────────────────────────

def test_config_error_needs_a_term_and_a_board():
    assert M.config_error(Search(search_mode="creative", sources=["behance"])) == \
        "Creative boards needs a search term before it can run"
    assert M.config_error(Search(search_mode="creative", search_term="x", sources=[])) == \
        "Creative boards needs at least one board before it can run"
    assert M.config_error(Search(search_mode="creative", search_term="x", sources=["wanacreate"])) is None
    assert M.config_error(Search(search_mode="creative", search_term="x", sources=["himalayas"])) == \
        "Creative boards needs at least one board before it can run"     # its own mode now


@pytest.fixture
def api_client(api_client, test_db):
    test_db.add(Setting(key="dashboard_api_key", value=""))
    test_db.commit()
    return api_client


def test_a_new_creative_search_gets_every_board_and_refuses_others(api_client):
    r = api_client.post("/api/searches", json={"name": "c", "search_mode": "creative", "search_term": "illustrator"})
    assert r.status_code == 200 and r.json()["sources"] == list(M.CREATIVE_BOARDS)
    r = api_client.post("/api/searches", json={"name": "c2", "search_mode": "creative", "search_term": "x",
                                               "sources": ["behance", "linkedin"]})
    assert r.status_code == 400 and "creative boards" in r.json()["detail"]
