"""Firecrawl source: the search request, the posting rows, the page reads, the key and the
paid-mode wiring (no network)."""
import json
from types import SimpleNamespace

import httpx
import pytest

from backend.models.db import Job, Search
from backend.scraper import search_modes as M
from backend.scraper._shared import job_boards
from backend.scraper.sources import firecrawl
from backend.tests.r4_support import set_setting


def _search(**kw):
    base = dict(name="t", search_mode="firecrawl", search_term="data engineer", location="", country=None,
                is_remote=None, hours_old=0, results_wanted=10, sources=[], company_filter=[])
    base.update(kw)
    return SimpleNamespace(**base)


def _hit(url, title, description=""):
    return {"url": url, "title": title, "description": description}


class FakeFirecrawl:
    def __init__(self):
        self.calls = []                 # (path, json body, auth header)
        self.web = []
        self.pages = {}                 # url -> (markdown, page title)
        self.status = 200

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.calls.append((request.url.path, body, request.headers.get("authorization")))
        if self.status != 200:
            return httpx.Response(self.status, json={"success": False, "error": "nope"})
        if request.url.path == "/v2/search":
            return httpx.Response(200, json={"success": True, "data": {"web": self.web}})
        markdown, title, *code = self.pages.get(body["url"], ("", ""))
        metadata = {"title": title, "statusCode": code[0] if code else 200}
        return httpx.Response(200, json={"success": True, "data": {"markdown": markdown, "metadata": metadata}})


@pytest.fixture
def fc(monkeypatch):
    fake = FakeFirecrawl()
    monkeypatch.setattr(job_boards, "http_client", lambda mounts=None: httpx.AsyncClient(
        transport=httpx.MockTransport(fake), follow_redirects=True))
    monkeypatch.setattr(firecrawl, "_key", lambda: "fc-test")
    return fake


@pytest.mark.asyncio
async def test_search_request_names_the_job_boards_the_filters_and_the_origin(fc):
    async with job_boards.http_client() as c:
        await firecrawl._list(c, _search(location="Berlin, Germany", country="germany", is_remote=True,
                                         hours_old=48, results_wanted=500), 500)
    path, body, auth = fc.calls[0]
    assert path == "/v2/search" and auth == "Bearer fc-test"
    assert body["query"].startswith('"data engineer" Berlin remote (site:job-boards.greenhouse.io OR ')
    assert "site:jobs.lever.co" in body["query"] and "site:apply.workable.com" in body["query"]
    assert (body["limit"], body["tbs"], body["location"], body["origin"]) == (100, "qdr:w", "Germany", "jobnavigator")


@pytest.mark.asyncio
async def test_search_without_hours_old_or_country_sends_neither_and_keeps_user_quotes(fc):
    async with job_boards.http_client() as c:
        await firecrawl._list(c, _search(search_term='"ml engineer" OR "data scientist"'), 10)
    body = fc.calls[0][1]
    assert "tbs" not in body and "location" not in body
    assert body["query"].startswith('"ml engineer" OR "data scientist" (site:')


@pytest.mark.parametrize("hours,tbs", [(1, "qdr:h"), (24, "qdr:d"), (25, "qdr:w"), (720, "qdr:m"), (2000, "qdr:y")])
def test_hours_old_rounds_up_to_the_search_window(hours, tbs):
    assert firecrawl._tbs(hours) == tbs


@pytest.mark.asyncio
async def test_rows_read_title_and_company_as_each_board_writes_them(fc):
    fc.web = [
        _hit("https://job-boards.greenhouse.io/figma/jobs/6266479004?gh_jid=6266479004", "Job Application for Product Manager, Billing at Figma"),
        _hit("https://job-boards.greenhouse.io/stripe/jobs/8414351", "Stripe Careers | Product Manager, Stripe Business Network"),
        _hit("https://job-boards.greenhouse.io/thefarmers-dog/jobs/8950356002", "Senior Product Manager 2"),
        _hit("https://jobs.ashbyhq.com/1password/3aad3321-a5fc-48bd-9634-d4c03aa7f173", "Technical Product Manager (Apono) @ 1Password"),
        _hit("https://jobs.ashbyhq.com/5dcfe507-5c82-4b61-a84e-47020a17f7dc/c9d4a88a-9c92-4a7b-9f13-d8e91875c427", "Senior Data Engineer"),
        _hit("https://jobs.lever.co/freedompay/5c8a403f-14be-4fcb-9b7a-12865ddeb440", "FreedomPay - Technical Product Manager, Payments Data ..."),
        _hit("https://jobs.lever.co/findem/1c8a403f-14be-4fcb-9b7a-12865ddeb440", "Principal Product Manager - Findem"),
        _hit("https://jobs.lever.co/zum/2c8a403f-14be-4fcb-9b7a-12865ddeb440", "Senior Product Manager - Zūm"),
        _hit("https://apply.workable.com/islacare/j/8AAA751EED", "Senior Backend Engineer - Data Core - Isla"),
        _hit("https://jobs.lever.co/freedompay", "FreedomPay jobs"),                  # the board, not a posting
        _hit("https://www.example.com/careers/1", "Data Engineer at Example"),         # off the job boards
    ]
    async with job_boards.http_client() as c:
        rows = await firecrawl._list(c, _search(), 10)
    assert [(r["title"], r["company"]) for r in rows] == [
        ("Product Manager, Billing", "Figma"),
        ("Product Manager, Stripe Business Network", "Stripe"),
        ("Senior Product Manager 2", "Thefarmers Dog"),
        ("Technical Product Manager (Apono)", "1Password"),
        ("Senior Data Engineer", ""),
        ("Technical Product Manager, Payments Data", "FreedomPay"),
        ("Principal Product Manager", "Findem"),
        ("Senior Product Manager", "Zūm"),
        ("Senior Backend Engineer - Data Core", "Isla"),
    ]
    assert rows[0]["url"] == "https://job-boards.greenhouse.io/figma/jobs/6266479004?gh_jid=6266479004"


@pytest.mark.asyncio
async def test_page_read_completes_a_cut_title_and_names_the_company(fc):
    url = "https://jobs.ashbyhq.com/5dcfe507-5c82-4b61-a84e-47020a17f7dc/c9d4a88a-9c92-4a7b-9f13-d8e91875c427"
    fc.pages[url] = ("[Back to jobs](x)\n\n# Senior Data Engineer, Growth\n\n## Location\n\nBerlin", "Senior Data Engineer, Growth @ Acme GmbH")
    r = job_boards.make_row(title="Senior Data Engineer", company="", url=url)
    async with job_boards.http_client() as c:
        await firecrawl._detail(c, r)
    assert (r["title"], r["company"]) == ("Senior Data Engineer, Growth", "Acme GmbH")
    assert r["description"].startswith("[Back to jobs]")
    body = fc.calls[0][1]
    assert body == {"url": url, "formats": ["markdown"], "onlyMainContent": True, "origin": "jobnavigator"}


@pytest.mark.asyncio
async def test_page_read_trims_a_padded_title_and_names_a_company_read_from_the_slug(fc):
    url = "https://apply.workable.com/fuseenergy/j/1A2B3C4D5E/"
    fc.pages[url] = ("## Mid-Level Backend Engineer\n\nBuild things.", "Mid-Level Backend Engineer - Fuse Energy")
    async with job_boards.http_client() as c:
        fc.web = [_hit(url, "Mid-Level Backend Engineer Job Available, United States (Remote)")]
        r = (await firecrawl._list(c, _search(), 10))[0]
        assert r["company"] == "Fuseenergy"
        await firecrawl._detail(c, r)
    assert (r["title"], r["company"]) == ("Mid-Level Backend Engineer", "Fuse Energy")


@pytest.mark.asyncio
async def test_a_first_heading_that_is_not_the_title_is_left_alone(fc):
    url = "https://jobs.lever.co/acme/5c8a403f-14be-4fcb-9b7a-12865ddeb440"
    fc.pages[url] = ("## About Acme\n\nWe build things.", "Acme - Data Engineer")
    r = job_boards.make_row(title="Data Engineer", company="Acme", url=url)
    async with job_boards.http_client() as c:
        await firecrawl._detail(c, r)
    assert (r["title"], r["company"]) == ("Data Engineer", "Acme")


@pytest.mark.asyncio
async def test_an_empty_page_is_an_error(fc):
    r = job_boards.make_row(title="Data Engineer", url="https://jobs.lever.co/acme/x")
    async with job_boards.http_client() as c:
        with pytest.raises(job_boards.BoardError, match="empty page"):
            await firecrawl._detail(c, r)


@pytest.mark.parametrize("status,text", [(401, "rejected the API key"), (402, "no credits left: nope"),
                                         (429, "rate limit"), (500, "HTTP 500 from the Firecrawl API: nope")])
@pytest.mark.asyncio
async def test_api_errors_say_what_happened(fc, status, text):
    fc.status = status
    async with job_boards.http_client() as c:
        with pytest.raises(job_boards.BoardError, match=text):
            await firecrawl._list(c, _search(), 10)


def test_key_comes_from_settings_and_a_missing_one_says_where_to_set_it(test_db):
    with pytest.raises(job_boards.BoardError, match="Settings → Firecrawl"):
        firecrawl._key()
    set_setting(test_db, "firecrawl_api_key", " fc-abc ")
    assert firecrawl._key() == "fc-abc"


def test_member_keys_follow_the_section_policy(test_db):
    from backend.accounts.context import use_account
    from backend.models.db import Account, SectionPolicy, Setting
    owner = test_db.query(Account).filter(Account.role == "owner").one().id
    member = Account(name="Partner", role="member")
    test_db.add(member)
    test_db.commit()
    set_setting(test_db, "firecrawl_api_key", "fc-owner")
    with use_account(member.id):
        with pytest.raises(job_boards.BoardError, match="not set"):
            firecrawl._key()                                  # own (default): never the owner's key
    test_db.add(Setting(key="firecrawl_api_key", value="fc-member", account_id=member.id))
    test_db.commit()
    with use_account(member.id):
        assert firecrawl._key() == "fc-member"
    with use_account(owner):
        assert firecrawl._key() == "fc-owner"
    test_db.add(SectionPolicy(account_id=member.id, section="firecrawl", mode="inherit"))
    test_db.commit()
    with use_account(member.id):
        assert firecrawl._key() == "fc-owner"


def test_key_is_a_redacted_setting_in_its_own_section(api_client):
    from backend.accounts.settings import SETTING_SECTIONS, section_of
    assert section_of("firecrawl_api_key") == "firecrawl"
    assert (SETTING_SECTIONS["firecrawl"]["scope"], SETTING_SECTIONS["firecrawl"]["default"]) == ("policy", "own")
    assert api_client.patch("/api/settings", json={"firecrawl_api_key": "fc-secret"}).status_code == 200
    assert api_client.get("/api/settings").json()["firecrawl_api_key"] == "•" * 6


@pytest.mark.asyncio
async def test_run_saves_new_postings_as_direct_jobs_and_reads_each_page_once(fc, test_db, monkeypatch):
    async def fake_analyze(job, db=None, arrangement=None):
        job.work_arrangement = arrangement
    monkeypatch.setattr(job_boards, "analyze_inline", fake_analyze)
    monkeypatch.setattr("backend.activity.log_activity", lambda *a, **k: None)
    url = "https://job-boards.greenhouse.io/figma/jobs/6266479004"
    fc.web = [_hit(url, "Job Application for Data Engineer at Figma"),
              _hit("https://jobs.lever.co/acme/5c8a403f-14be-4fcb-9b7a-12865ddeb440", "Acme - Sales Lead")]
    fc.pages[url] = ("## Data Engineer\n\nBuild pipelines.", "Job Application for Data Engineer at Figma")
    search = Search(name="t", search_mode="firecrawl", search_term="data engineer", results_wanted=10, hours_old=0,
                    company_exclude=[], title_include_keywords=["engineer"])
    test_db.add(search)
    test_db.commit()
    res = await firecrawl.run(search)
    assert res["error"] is None and res["source_breakdown"]["firecrawl"]["new"] == 1
    assert res["source_breakdown"]["firecrawl"]["filtered"] == 1          # "Sales Lead" fails the title filter
    test_db.expire_all()
    job = test_db.query(Job).one()
    assert (job.source, job.company, job.title, job.url, job.link_kind) == ("firecrawl", "Figma", "Data Engineer", url, "direct")
    assert job.description == "## Data Engineer\n\nBuild pipelines."
    assert [p for p, *_ in fc.calls] == ["/v2/search", "/v2/scrape"]
    await firecrawl.run(search)                                           # known posting: no page read
    assert [p for p, *_ in fc.calls] == ["/v2/search", "/v2/scrape", "/v2/search"]


@pytest.mark.asyncio
async def test_a_closed_posting_is_kept_as_ignored_and_not_read_again(fc, test_db, monkeypatch):
    monkeypatch.setattr("backend.activity.log_activity", lambda *a, **k: None)
    url = "https://jobs.ashbyhq.com/acme/c9d4a88a-9c92-4a7b-9f13-d8e91875c427"
    fc.web = [_hit(url, "Data Engineer @ Acme")]
    fc.pages[url] = ("# Page not found", "Jobs", 404)
    search = Search(name="t", search_mode="firecrawl", search_term="data engineer", results_wanted=10, hours_old=0,
                    company_exclude=[])
    test_db.add(search)
    test_db.commit()
    res = await firecrawl.run(search)
    assert res["error"] is None and res["new_jobs"] == 0 and res["ignored_jobs"] == 1
    test_db.expire_all()
    assert test_db.query(Job).one().status == "ignored"
    await firecrawl.run(search)
    assert [p for p, *_ in fc.calls] == ["/v2/search", "/v2/scrape", "/v2/search"]


@pytest.mark.asyncio
async def test_run_without_a_key_reports_it(test_db, monkeypatch):
    monkeypatch.setattr("backend.activity.log_activity", lambda *a, **k: None)
    search = Search(name="t", search_mode="firecrawl", search_term="pm", results_wanted=10, company_exclude=[])
    test_db.add(search)
    test_db.commit()
    res = await firecrawl.run(search)
    assert "Firecrawl API key is not set" in res["error"]


def test_mode_needs_a_term_and_is_paid():
    mode = M.get_mode("firecrawl")
    assert (mode.module, mode.paid, mode.shareable, mode.background_test) == ("firecrawl", True, False, True)
    assert M.config_error(Search(search_mode="firecrawl")) == "Firecrawl needs a search term before it can run"
    assert M.config_error(Search(search_mode="firecrawl", search_term="pm")) is None


def test_new_firecrawl_search_starts_paused(api_client):
    r = api_client.post("/api/searches", json={"name": "FC", "search_mode": "firecrawl", "search_term": "pm"})
    assert r.status_code == 200 and r.json()["active"] is False


def test_switching_a_search_to_firecrawl_pauses_it(api_client):
    sid = api_client.post("/api/searches", json={"name": "kw", "search_term": "pm"}).json()["id"]
    r = api_client.patch(f"/api/searches/{sid}", json={"search_mode": "firecrawl"})
    assert r.status_code == 200 and (r.json()["active"], r.json()["sources"]) == (False, [])
    api_client.patch(f"/api/searches/{sid}", json={"active": True})
    assert api_client.patch(f"/api/searches/{sid}", json={"search_term": "tpm"}).json()["active"] is True
