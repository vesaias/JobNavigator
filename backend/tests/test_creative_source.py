"""Creative boards source: the three board clients, the save pipeline and the mode wiring (no network)."""
import json
import time
from types import SimpleNamespace

import httpx
import pytest

from backend.models.db import Job, Search, Setting
from backend.scraper import search_modes as M
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
        self.himalayas = {}            # page -> jobs
        self.eluta_pages = {}          # pg -> rss xml
        self.eluta_pages_html = {}     # path -> html

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
        if host == "himalayas.app":
            page = int(request.url.params.get("page", "1"))
            return httpx.Response(200, json={"totalCount": 0, "jobs": self.himalayas.get(page, [])})
        if host == "www.eluta.ca" and path == "/rss":
            return httpx.Response(200, content=self.eluta_pages.get(int(request.url.params.get("pg", "1")), _rss([])))
        if host == "www.eluta.ca":
            return httpx.Response(200, text=self.eluta_pages_html.get(path, "<html></html>"))
        return httpx.Response(404)

    def to(self, host, path=None):
        return [c for c in self.calls if c[0] == host and (path is None or c[1] == path)]


@pytest.fixture
def sites(monkeypatch):
    fake = FakeSites()
    monkeypatch.setattr(creative, "_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(fake),
                                                                        follow_redirects=True))
    return fake


def _holly(i, public=True, market=None, added="2026-10-20T10:00:00.000Z", org="Studio"):
    return {"_id": f"h{i}", "slugUrl": f"job-h{i}", "title": f"Animator {i}\n  ", "organization": org if public else None,
            "isPublic": public, "dateAdded": added, "location": {"name": "London, UK" if market else "Los Angeles, CA"}}


# ── the board clients ───────────────────────────────────────────────────────

def _rss(items) -> bytes:
    body = "".join(
        f"<item><title>{t}</title><link>https://www.eluta.ca/spl/{slug}?imo=1</link><employer>{e}</employer>"
        f"<location>{loc}</location><description>&lt;span&gt;snippet&lt;/span&gt; text</description>"
        f"<pubDate>{date}</pubDate><guid>{slug}</guid></item>"
        for t, slug, e, loc, date in items)
    return f'<?xml version="1.0"?><rss><channel>{body}</channel></rss>'.encode()


def _him(i, days_old=1, places=("Canada",), salary=None):
    j = {"title": f"Concept Artist {i}", "companyName": "Youtooz", "locationRestrictions": list(places),
         "description": "<p>Draw <b>things</b></p>", "pubDate": int(time.time()) - days_old * 86400,
         "applicationLink": f"https://himalayas.app/companies/youtooz/jobs/c{i}?utm_source=api",
         "guid": f"https://himalayas.app/companies/youtooz/jobs/c{i}", "salaryPeriod": "annual",
         "minSalary": None, "maxSalary": None, "currency": None}
    if salary:
        j.update(minSalary=salary[0], maxSalary=salary[1], currency=salary[2])
    return j


@pytest.fixture
def eluta_now(monkeypatch):
    monkeypatch.setattr(creative, "_ELUTA_GAP", 0)


def test_board_keys_match_the_mode_table():
    assert tuple(creative.BOARDS) == M.CREATIVE_BOARDS


async def test_behance_passes_the_cookie_challenge_and_sends_the_same_token_twice(sites):
    sites.behance_pages[2] = [sites.be_node(3)]
    async with creative._client() as c:
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
    async with creative._client() as c:
        rows = await creative._behance_list(c, _search(), 60)
    assert len(rows) == 60 and len(sites.to("www.behance.net", "/v3/graphql")) == 2
    assert "filter" not in sites.to("www.behance.net", "/v3/graphql")[0][2]["variables"]


async def test_behance_details_fill_text_date_and_usd_salary_and_drop_masked_fields(sites):
    async with creative._client() as c:
        rows = await creative._behance_list(c, _search(), 10)
        for r in rows:
            r["source"] = "behance"          # _collect sets it
        await creative._fill_details(c, rows)
    job, brief = rows
    assert (job["description"], job["salary_min"], job["salary_max"]) == ("Full text", 70000, 90000)
    assert job["posted"] is not None and creative._too_old(job, 2) is None
    assert brief["description"] == "Draw a book\n\nTen pages"          # "####" is a masked field
    assert brief["company"] == "Brief Co" and brief["posted"] is None


def test_annual_usd_refuses_other_currencies_periods_and_hourly_rates():
    assert creative._annual_usd(70000, 90000, "ANNUAL", "USD") == (70000, 90000)
    assert creative._annual_usd(70000, None, "YEARLY", "usd") == (70000, 70000)
    assert creative._annual_usd(35000, 45000, "ANNUAL", "INR") == (None, None)
    assert creative._annual_usd(15, 20, "ANNUAL", "USD") == (None, None)
    assert creative._annual_usd(5000, 6000, "MONTHLY", "USD") == (None, None)
    assert creative._annual_usd(None, None, None, None) == (None, None)


async def test_hollylist_drops_members_only_and_merges_both_markets_newest_first(sites):
    sites.holly[None] = [_holly(1, added="2026-10-20T10:00:00Z"), _holly(2, public=False)]
    sites.holly["europe"] = [_holly(3, market="europe", added="2026-10-22T10:00:00Z")]
    async with creative._client() as c:
        rows = await creative._hollylist_list(c, _search(location="London, UK", is_remote=True), 10)
    assert [r["title"] for r in rows] == ["Animator 3", "Animator 1"]
    assert rows[0]["url"] == "https://www.hollylist.com/job/job-h3"
    asked = {c[2]["variables"]["market"]: c[2]["variables"] for c in sites.to("www.hollylist.com")}
    assert set(asked) == {None, "europe"}
    assert (asked[None]["loc"], asked[None]["remote"], asked[None]["term"]) == ("London", True, "illustrator")


async def test_hollylist_pages_by_one_hundred(sites):
    sites.holly[None] = [_holly(i) for i in range(150)]
    async with creative._client() as c:
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


async def test_himalayas_sends_the_country_name_and_stops_at_old_jobs(sites):
    sites.himalayas = {1: [_him(i) for i in range(19)] + [_him(99, days_old=30)], 2: [_him(200)]}
    async with creative._client() as c:
        rows = await creative._himalayas_list(c, _search(country="canada", hours_old=168), 100)
    assert len(rows) == 19                     # the 30-day-old job ends the paging
    asked = [u for u in sites.urls if "himalayas.app" in u]
    assert len(asked) == 1
    assert "country=Canada" in asked[0] and "sort=recent" in asked[0] and "page=1" in asked[0]
    r = rows[0]
    assert (r["url"], r["location"], r["arrangement"]) == (
        "https://himalayas.app/companies/youtooz/jobs/c0?utm_source=api", "Remote: Canada", "remote")
    assert r["description"] == "Draw things"


async def test_himalayas_without_a_known_country_sends_none(sites):
    sites.himalayas = {1: [_him(1, places=())]}
    async with creative._client() as c:
        rows = await creative._himalayas_list(c, _search(country="atlantis"), 10)
    assert rows[0]["location"] == "Remote (worldwide)"
    assert "country=" not in [u for u in sites.urls if "himalayas.app" in u][0]


def test_himalayas_salary_is_kept_only_in_usd_per_year():
    assert creative._himalayas_row(_him(1, salary=(90000, 120000, "USD")))["salary_min"] == 90000
    assert creative._himalayas_row(_him(1, salary=(90000, 120000, "EUR")))["salary_min"] is None


async def test_eluta_reads_the_feed_with_a_city_radius_and_fills_text_from_microdata(sites, eluta_now):
    now = "Mon, 26 Oct 2026 13:56:27 GMT"
    sites.eluta_pages = {1: _rss([("2D Animator", "2d-animator-abc", "ICON Creative Studio", "Vancouver, BC", now)])}
    sites.eluta_pages_html = {"/spl/2d-animator-abc": (
        '<div itemscope itemtype="http://schema.org/JobPosting"><span itemprop="title">2D Animator</span>'
        '<div itemprop="description"><p>Animate <b>scenes</b></p><ul><li>Toon Boom</li></ul></div></div>')}
    async with creative._client() as c:
        rows = await creative._eluta_list(c, _search(search_term="animator", location="Vancouver, BC"), 50)
        for r in rows:
            r["source"] = "eluta"
        assert rows[0]["description"] == "snippet text"
        await creative._fill_details(c, rows)
    r = rows[0]
    assert (r["title"], r["company"], r["location"]) == ("2D Animator", "ICON Creative Studio", "Vancouver, BC")
    assert r["url"] == "https://www.eluta.ca/spl/2d-animator-abc"          # ?imo=1 dropped
    assert r["posted"].startswith("2026-10-26T13:56:27")
    assert r["description"] == "Animate scenes\nToon Boom"
    assert len(sites.to("www.eluta.ca", "/rss")) == 1        # one item < 20: no second page


async def test_eluta_query_carries_sort_and_radius(sites, eluta_now):
    async with creative._client() as c:
        await creative._eluta_list(c, _search(search_term="illustrator", location="Vancouver"), 10)
        await creative._eluta_list(c, _search(search_term="illustrator", location=""), 10)
    urls = [u for u in sites.urls if "eluta.ca/rss" in u]
    assert "radius%3A50" in urls[0] and "l=Vancouver" in urls[0] and "sort%3Apost" in urls[0]
    assert "radius" not in urls[1]


async def test_eluta_too_many_requests_fails_the_first_page_and_ends_later_ones(sites, eluta_now):
    busy = _rss([("Too Many Requests", "x", "", "", "Mon, 26 Oct 2026 13:56:27 GMT")])
    sites.eluta_pages = {1: busy}
    async with creative._client() as c:
        with pytest.raises(creative.CreativeError, match="Too Many Requests"):
            await creative._eluta_list(c, _search(), 50)
    now = "Mon, 26 Oct 2026 13:56:27 GMT"
    sites.eluta_pages = {1: _rss([(f"Artist {i}", f"a{i}", "Co", "Vancouver, BC", now) for i in range(20)]), 2: busy}
    async with creative._client() as c:
        rows = await creative._eluta_list(c, _search(), 50)
    assert len(rows) == 20


def test_rows_past_a_board_detail_budget_wait_for_the_next_run():
    rows = [{"source": "eluta", "i": i} for i in range(creative._ELUTA_MAX_DETAILS + 3)] + [{"source": "behance"}]
    breakdown = {"eluta": {"seen": 0, "new": 0}, "behance": {"seen": 0, "new": 0}}
    kept = creative._defer_over_budget(rows, breakdown)
    assert [r.get("i") for r in kept if r["source"] == "eluta"] == list(range(creative._ELUTA_MAX_DETAILS))
    assert any(r["source"] == "behance" for r in kept)                 # Behance has no cap
    assert breakdown["eluta"]["deferred"] == 3 and "deferred" not in breakdown["behance"]


async def test_run_saves_eluta_rows_up_to_the_budget_and_leaves_the_rest(sites, quiet, test_db, eluta_now, monkeypatch):
    monkeypatch.setattr(creative, "_ELUTA_MAX_DETAILS", 2)
    monkeypatch.setitem(creative.BOARDS, "eluta", creative.Board("Eluta", creative._eluta_list, creative._eluta_detail, 2))
    now = "Mon, 26 Oct 2026 13:56:27 GMT"
    sites.eluta_pages = {1: _rss([(f"Animator {i}", f"a{i}", "ICON", "Vancouver, BC", now) for i in range(5)])}
    search = Search(name="t", search_mode="creative", search_term="animator", sources=["eluta"], location="Vancouver",
                    results_wanted=10, hours_old=0, company_exclude=[])
    test_db.add(search)
    test_db.commit()
    res = await creative.run(search)
    assert res["source_breakdown"]["eluta"]["new"] == 2 and res["source_breakdown"]["eluta"]["deferred"] == 3
    res = await creative.run(search)                    # the next run takes the waiting ones
    assert res["source_breakdown"]["eluta"]["new"] == 2


def test_eluta_tls_context_offers_the_rsa_cipher_the_site_needs():
    names = {c["name"] for c in creative._eluta_tls().get_ciphers()}
    assert "AES128-GCM-SHA256" in names


async def test_collect_keeps_the_other_boards_when_one_fails(sites):
    sites.fail.add("www.hollylist.com")
    sites.wana_hits = [{"id": "w1", "title": "Illustrator 1", "jobLink": "https://www.behance.net/joblist/x/1"}]
    async with creative._client() as c:
        rows, breakdown = await creative._collect(c, _search(), 10)
    assert breakdown["hollylist"]["error"] == "HTTP 503 from https://www.hollylist.com/graphql"
    assert breakdown["behance"]["returned"] == 2 and breakdown["wanacreate"]["returned"] == 1
    assert len(rows) == 2                    # the Wana row has the same URL as a Behance row


# ── save pipeline ───────────────────────────────────────────────────────────

@pytest.fixture
def quiet(monkeypatch):
    async def fake_analyze(job, db=None, arrangement=None):
        job.work_arrangement = arrangement
    monkeypatch.setattr(creative, "analyze_inline", fake_analyze)
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


# ── mode wiring ─────────────────────────────────────────────────────────────

def test_config_error_needs_a_term_and_a_board():
    assert M.config_error(Search(search_mode="creative", sources=["behance"])) == \
        "Creative boards needs a search term before it can run"
    assert M.config_error(Search(search_mode="creative", search_term="x", sources=[])) == \
        "Creative boards needs at least one board before it can run"
    assert M.config_error(Search(search_mode="creative", search_term="x", sources=["wanacreate"])) is None


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
