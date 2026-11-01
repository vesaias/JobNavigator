"""Himalayas source: the API client, its link kinds and the mode wiring (no network)."""
import time
from types import SimpleNamespace

import httpx
import pytest

from backend.models.db import Job, Search
from backend.scraper import search_modes as M
from backend.scraper._shared import job_boards
from backend.scraper.sources import himalayas


def _search(**kw):
    base = dict(name="t", search_mode="himalayas", search_term="artist", location="", is_remote=None,
                hours_old=0, results_wanted=10, sources=[], company_filter=[])
    base.update(kw)
    return SimpleNamespace(**base)


class FakeSite:
    def __init__(self):
        self.urls = []
        self.himalayas = {}            # page -> jobs

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.urls.append(str(request.url))
        page = int(request.url.params.get("page", "1"))
        return httpx.Response(200, json={"totalCount": 0, "jobs": self.himalayas.get(page, [])})


@pytest.fixture
def sites(monkeypatch):
    fake = FakeSite()
    monkeypatch.setattr(job_boards, "http_client", lambda mounts=None: httpx.AsyncClient(
        transport=httpx.MockTransport(fake), follow_redirects=True))
    return fake


def _him(i, days_old=1, places=("Canada",), salary=None):
    j = {"title": f"Concept Artist {i}", "companyName": "Youtooz", "locationRestrictions": list(places),
         "description": "<p>Draw <b>things</b></p>", "pubDate": int(time.time()) - days_old * 86400,
         "applicationLink": f"https://himalayas.app/companies/youtooz/jobs/c{i}?utm_source=api",
         "guid": f"https://himalayas.app/companies/youtooz/jobs/c{i}", "salaryPeriod": "annual",
         "minSalary": None, "maxSalary": None, "currency": None}
    if salary:
        j.update(minSalary=salary[0], maxSalary=salary[1], currency=salary[2])
    return j


@pytest.mark.asyncio
async def test_himalayas_sends_the_country_name_and_stops_at_old_jobs(sites):
    sites.himalayas = {1: [_him(i) for i in range(19)] + [_him(99, days_old=30)], 2: [_him(200)]}
    async with job_boards.http_client() as c:
        rows = await himalayas._list(c, _search(country="canada", hours_old=168), 100)
    assert len(rows) == 19                     # the 30-day-old job ends the paging
    asked = [u for u in sites.urls if "himalayas.app" in u]
    assert len(asked) == 1
    assert "country=Canada" in asked[0] and "sort=recent" in asked[0] and "page=1" in asked[0]
    r = rows[0]
    assert (r["url"], r["location"], r["arrangement"]) == (
        "https://himalayas.app/companies/youtooz/jobs/c0?utm_source=api", "Remote: Canada", "remote")
    assert r["description"] == "Draw things"


@pytest.mark.asyncio
async def test_himalayas_without_a_known_country_sends_none(sites):
    sites.himalayas = {1: [_him(1, places=())]}
    async with job_boards.http_client() as c:
        rows = await himalayas._list(c, _search(country="atlantis"), 10)
    assert rows[0]["location"] == "Remote (worldwide)"
    assert "country=" not in [u for u in sites.urls if "himalayas.app" in u][0]


def test_himalayas_salary_is_kept_only_in_usd_per_year():
    assert himalayas._row(_him(1, salary=(90000, 120000, "USD")))["salary_min"] == 90000
    assert himalayas._row(_him(1, salary=(90000, 120000, "EUR")))["salary_min"] is None


@pytest.mark.parametrize("link,kind", [
    ("https://himalayas.app/companies/youtooz/jobs/c1?utm_source=api", "board"),     # every job sampled
    ("https://job-boards.greenhouse.io/youtooz/jobs/1", "direct"),                   # `url` holds the employer's link
])
@pytest.mark.asyncio
async def test_himalayas_link_kinds(sites, test_db, monkeypatch, link, kind):
    async def fake_analyze(job, db=None, arrangement=None):
        job.work_arrangement = arrangement
    monkeypatch.setattr(job_boards, "analyze_inline", fake_analyze)
    monkeypatch.setattr("backend.activity.log_activity", lambda *a, **k: None)
    sites.himalayas = {1: [dict(_him(1), applicationLink=link)]}
    search = Search(name="t", search_mode="himalayas", search_term="artist", results_wanted=10, hours_old=0,
                    company_exclude=[])
    test_db.add(search)
    test_db.commit()
    res = await himalayas.run(search)
    assert res["error"] is None and res["source_breakdown"]["himalayas"]["new"] == 1
    test_db.expire_all()
    job = test_db.query(Job).one()
    assert (job.source, job.url, job.link_kind) == ("himalayas", link, kind)


def test_config_error_needs_a_term():
    assert M.config_error(Search(search_mode="himalayas")) == "Himalayas needs a search term before it can run"
    assert M.config_error(Search(search_mode="himalayas", search_term="designer")) is None
