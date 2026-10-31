"""Eluta source: the feed client, its daily limit, its link kind and the mode wiring (no network)."""
from types import SimpleNamespace

import httpx
import pytest

from backend.models.db import Job, Search
from backend.scraper import search_modes as M
from backend.scraper._shared import job_boards
from backend.scraper.sources import eluta


def _search(**kw):
    base = dict(name="t", search_mode="eluta", search_term="illustrator", location="", is_remote=None,
                hours_old=0, results_wanted=10, sources=[], company_filter=[])
    base.update(kw)
    return SimpleNamespace(**base)


def _rss(items) -> bytes:
    body = "".join(
        f"<item><title>{t}</title><link>https://www.eluta.ca/spl/{slug}?imo=1</link><employer>{e}</employer>"
        f"<location>{loc}</location><description>&lt;span&gt;snippet&lt;/span&gt; text</description>"
        f"<pubDate>{date}</pubDate><guid>{slug}</guid></item>"
        for t, slug, e, loc, date in items)
    return f'<?xml version="1.0"?><rss><channel>{body}</channel></rss>'.encode()


class FakeSite:
    def __init__(self):
        self.calls = []
        self.urls = []
        self.eluta_pages = {}          # pg -> rss xml
        self.eluta_pages_html = {}     # path -> html

    def __call__(self, request: httpx.Request) -> httpx.Response:
        host, path = request.url.host, request.url.path
        self.calls.append((host, path))
        self.urls.append(str(request.url))
        if path == "/rss":
            return httpx.Response(200, content=self.eluta_pages.get(int(request.url.params.get("pg", "1")), _rss([])))
        return httpx.Response(200, text=self.eluta_pages_html.get(path, "<html></html>"))

    def to(self, host, path=None):
        return [c for c in self.calls if c[0] == host and (path is None or c[1] == path)]


@pytest.fixture
def sites(monkeypatch):
    fake = FakeSite()
    monkeypatch.setattr(job_boards, "http_client", lambda mounts=None: httpx.AsyncClient(
        transport=httpx.MockTransport(fake), follow_redirects=True))
    return fake


@pytest.fixture
def eluta_now(monkeypatch):
    monkeypatch.setattr(eluta, "_GAP", 0)


@pytest.fixture
def quiet(monkeypatch):
    async def fake_analyze(job, db=None, arrangement=None):
        job.work_arrangement = arrangement
    monkeypatch.setattr(job_boards, "analyze_inline", fake_analyze)
    monkeypatch.setattr("backend.activity.log_activity", lambda *a, **k: None)


async def test_eluta_reads_the_feed_with_a_city_radius_and_fills_text_from_microdata(sites, eluta_now):
    now = "Mon, 26 Oct 2026 13:56:27 GMT"
    sites.eluta_pages = {1: _rss([("2D Animator", "2d-animator-abc", "ICON Creative Studio", "Vancouver, BC", now)])}
    # As on eluta.ca: the hiring organisation's empty <meta itemprop="description"> comes first.
    sites.eluta_pages_html = {"/spl/2d-animator-abc": (
        '<div itemscope itemtype="http://schema.org/JobPosting"><span itemprop="title">2D Animator</span>'
        '<h5 itemprop="hiringOrganization" itemscope><meta itemprop="description" content=""></h5>'
        '<div itemprop="description"><p>Animate <b>scenes</b></p><ul><li>Toon Boom</li></ul></div></div>')}
    async with job_boards.http_client() as c:
        rows = await eluta._list(c, _search(search_term="animator", location="Vancouver, BC"), 50)
        for r in rows:
            r["source"] = "eluta"
        assert rows[0]["description"] == "snippet text"
        await job_boards._fill_details(c, rows, eluta.BOARDS)
    r = rows[0]
    assert (r["title"], r["company"], r["location"]) == ("2D Animator", "ICON Creative Studio", "Vancouver, BC")
    assert r["url"] == "https://www.eluta.ca/spl/2d-animator-abc"          # ?imo=1 dropped
    assert r["posted"].startswith("2026-10-26T13:56:27")
    assert r["description"] == "Animate scenes\nToon Boom"
    assert len(sites.to("www.eluta.ca", "/rss")) == 1        # one item < 20: no second page


async def test_eluta_query_carries_sort_and_radius(sites, eluta_now):
    async with job_boards.http_client() as c:
        await eluta._list(c, _search(search_term="illustrator", location="Vancouver"), 10)
        await eluta._list(c, _search(search_term="illustrator", location=""), 10)
    urls = [u for u in sites.urls if "eluta.ca/rss" in u]
    assert "radius%3A50" in urls[0] and "l=Vancouver" in urls[0] and "sort%3Apost" in urls[0]
    assert "radius" not in urls[1]


async def test_eluta_page_without_a_description_keeps_the_feed_snippet(sites, eluta_now):
    now = "Mon, 26 Oct 2026 13:56:27 GMT"
    sites.eluta_pages = {1: _rss([("Art Director", "ad-1", "Emily Carr", "Vancouver, BC", now)])}
    sites.eluta_pages_html = {"/spl/ad-1": '<div itemscope itemtype="http://schema.org/JobPosting">'
                                           '<meta itemprop="description" content=""></div>'}
    async with job_boards.http_client() as c:
        rows = await eluta._list(c, _search(), 10)
        await eluta._detail(c, rows[0])
    assert rows[0]["description"] == "snippet text"


@pytest.mark.parametrize("title", ["Too Many Requests", "Too Many Feeds"])
async def test_eluta_refusals_fail_the_board_instead_of_becoming_jobs(sites, eluta_now, title):
    sites.eluta_pages = {1: _rss([(title, "x", "", "", "Mon, 26 Oct 2026 13:56:27 GMT")])}
    async with job_boards.http_client() as c:
        with pytest.raises(job_boards.BoardError, match=title):
            await eluta._list(c, _search(), 50)


def test_eluta_daily_feed_refusal_is_recognised_by_its_contact_link():
    xml = (b'<rss><channel><item><title>Daily limit</title><link>https://www.eluta.ca/contact</link>'
           b'<description>You may only check a maximum of 10 RSS feeds each day.</description></item></channel></rss>')
    with pytest.raises(job_boards.BoardError, match="10 RSS feeds each day"):
        eluta._items(xml)


async def test_eluta_reads_one_feed_page_per_run(sites, eluta_now):
    now = "Mon, 26 Oct 2026 13:56:27 GMT"
    page = _rss([(f"Artist {i}", f"a{i}", "Co", "Vancouver, BC", now) for i in range(20)])
    sites.eluta_pages = {1: page, 2: page}
    async with job_boards.http_client() as c:
        rows = await eluta._list(c, _search(), 50)
    assert len(rows) == 20 and len(sites.to("www.eluta.ca", "/rss")) == 1


def test_rows_past_a_board_detail_budget_wait_for_the_next_run():
    rows = [{"source": "eluta", "i": i} for i in range(eluta._MAX_DETAILS + 3)] + [{"source": "behance"}]
    breakdown = {"eluta": {"seen": 0, "new": 0}, "behance": {"seen": 0, "new": 0}}
    behance = job_boards.Board("Behance", None)
    kept = job_boards._defer_over_budget(rows, breakdown, dict(eluta.BOARDS, behance=behance))
    assert [r.get("i") for r in kept if r["source"] == "eluta"] == list(range(eluta._MAX_DETAILS))
    assert any(r["source"] == "behance" for r in kept)                 # Behance has no cap
    assert breakdown["eluta"]["deferred"] == 3 and "deferred" not in breakdown["behance"]


async def test_run_saves_eluta_rows_up_to_the_budget_and_leaves_the_rest(sites, quiet, test_db, eluta_now, monkeypatch):
    monkeypatch.setitem(eluta.BOARDS, "eluta", job_boards.Board("Eluta", eluta._list, eluta._detail, 2))
    now = "Mon, 26 Oct 2026 13:56:27 GMT"
    sites.eluta_pages = {1: _rss([(f"Animator {i}", f"a{i}", "ICON", "Vancouver, BC", now) for i in range(5)])}
    search = Search(name="t", search_mode="eluta", search_term="animator", location="Vancouver",
                    results_wanted=10, hours_old=0, company_exclude=[])
    test_db.add(search)
    test_db.commit()
    res = await eluta.run(search)
    assert res["source_breakdown"]["eluta"]["new"] == 2 and res["source_breakdown"]["eluta"]["deferred"] == 3
    res = await eluta.run(search)                    # the next run takes the waiting ones
    assert res["source_breakdown"]["eluta"]["new"] == 2


def test_eluta_tls_context_offers_the_rsa_cipher_the_site_needs():
    names = {c["name"] for c in eluta._tls().get_ciphers()}
    assert "AES128-GCM-SHA256" in names


async def test_an_eluta_job_stays_a_board_link(sites, quiet, test_db, eluta_now):
    sites.eluta_pages = {1: _rss([("Animator", "a1", "ICON", "Vancouver, BC", "Mon, 26 Oct 2026 13:56:27 GMT")])}
    search = Search(name="t", search_mode="eluta", search_term="animator", results_wanted=10, hours_old=0, company_exclude=[])
    test_db.add(search)
    test_db.commit()
    assert (await eluta.run(search))["source_breakdown"]["eluta"]["new"] == 1
    test_db.expire_all()
    job = test_db.query(Job).one()
    assert (job.source, job.apply_url, job.link_kind) == ("eluta", None, "board")


def test_config_error_needs_a_term():
    assert M.config_error(Search(search_mode="eluta")) == "Eluta needs a search term before it can run"
    assert M.config_error(Search(search_mode="eluta", search_term="designer")) is None
