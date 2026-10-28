"""levels_jobs.py: a levels.fyi job's text and apply link come from its page data (the visible page
is a cookie banner), and a job whose data names no employer link is applied to on levels.fyi
itself, which counts as Easy Apply."""
import json
from types import SimpleNamespace

import pytest

from backend.scraper._shared import levels_jobs
from backend.scraper._shared.link_kinds import BOARD, EASY_APPLY
from backend.tests.test_posting_links import _job

URL = "https://www.levels.fyi/jobs?jobId=2aqd5gvmeceks"
DESC = "Divergent is hiring a Principal Product Manager to own the design tools. " * 5
BANNER = ("Principal Product Manager (Design) | Divergent 3D | Levels.fyi We value your privacy We use "
          "cookies to enhance your browsing experience ... Levels.fyi Jobs Introducing the most powerful way")


def _page(job):
    data = {"props": {"pageProps": {"initialJobDetails": job, "initialJobId": "2aqd5gvmeceks"}}}
    return f'<html><script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script></html>'


def test_parse_reads_text_link_and_pay():
    got = levels_jobs.parse_job_page(_page({
        "title": "PPM", "description": DESC, "applicationUrl": "https://jobs.lever.co/divergent/abc?utm_source=levels",
        "minBaseSalary": 200000, "maxBaseSalary": 260000, "baseSalaryCurrency": "USD"}))
    assert got["description"] == DESC
    assert got["application_url"].startswith("https://jobs.lever.co/divergent/abc")
    assert (got["salary_min"], got["salary_max"]) == (200000, 260000)


def test_parse_a_job_with_no_apply_link():
    got = levels_jobs.parse_job_page(_page({"title": "PPM", "description": DESC}))
    assert got["description"] == DESC and got["application_url"] is None


@pytest.mark.parametrize("html", ["<html>We value your privacy</html>", _page({}), ""])
def test_parse_a_page_without_job_data(html):
    assert levels_jobs.parse_job_page(html) is None


def test_foreign_pay_is_not_read_as_usd():
    got = levels_jobs.job_fields({"minBaseSalary": 90000, "baseSalaryCurrency": "EUR"})
    assert got["salary_min"] is None


@pytest.mark.parametrize("url,ok", [
    (URL, True),
    ("https://levels.fyi/jobs?jobId=123456789012345678", True),
    ("https://www.levels.fyi/jobs?searchText=pm", False),
    ("https://evil-levels.fyi.example.com/jobs?jobId=abc", False),
])
def test_is_levels_job(url, ok):
    assert levels_jobs.is_levels_job(url) is ok


@pytest.mark.asyncio
async def test_description_fetch_reads_the_page_data_and_never_the_banner(monkeypatch):
    from backend.scraper.ats import _descriptions

    async def fetch(url):
        return {"description": DESC, "application_url": "https://jobs.lever.co/divergent/abc"}
    monkeypatch.setattr(levels_jobs, "fetch_job", fetch)
    job = {}
    assert await _descriptions._fetch_job_description(URL, job=job) == DESC
    assert job["application_url"] == "https://jobs.lever.co/divergent/abc"

    async def none(url):
        return None

    async def banner(*a, **kw):   # the generic page fallback would read the cookie banner
        raise AssertionError("a levels.fyi page is never read as text")
    monkeypatch.setattr(levels_jobs, "fetch_job", none)
    monkeypatch.setattr("backend.scraper._shared.url_safety.safe_get", banner)
    assert await _descriptions._fetch_job_description(URL) is None


def test_scoring_skips_a_cached_levels_banner():
    from backend.analyzer.cv_scorer import _job_text_from_row
    levels = SimpleNamespace(id=1, description=None, cached_page_text=BANNER, url=URL, apply_url=None)
    other = SimpleNamespace(id=2, description=None, cached_page_text=BANNER,
                            url="https://example.com/careers/1", apply_url=None)
    assert _job_text_from_row(levels) is None
    assert _job_text_from_row(other) == BANNER


@pytest.mark.asyncio
async def test_scoring_saves_the_levels_text_and_marks_easy_apply(test_db, monkeypatch):
    from backend.analyzer import cv_scorer
    job = _job(test_db, URL, company="Divergent 3D", title="Principal Product Manager (Design)",
               source="levels_fyi")
    job.cached_page_text = BANNER
    test_db.commit()
    assert job.link_kind == BOARD

    async def fetch(url):
        return {"description": DESC, "application_url": None}
    monkeypatch.setattr("backend.scraper._shared.levels_jobs.fetch_job", fetch)
    assert await cv_scorer._get_job_text(job, db=test_db) == DESC
    test_db.refresh(job)
    assert job.description == DESC and job.link_kind == EASY_APPLY


@pytest.mark.asyncio
async def test_a_levels_job_with_an_employer_link_stays_a_board_link(test_db, monkeypatch):
    from backend.analyzer import cv_scorer
    job = _job(test_db, URL, company="Actalent", title="Project Engineer", source="levels_fyi")

    async def fetch(url):
        return {"description": DESC, "application_url": "https://jobs.actalent.com/job/1"}
    monkeypatch.setattr("backend.scraper._shared.levels_jobs.fetch_job", fetch)
    assert await cv_scorer._get_job_text(job, db=test_db) == DESC
    test_db.refresh(job)
    assert job.link_kind == BOARD


@pytest.mark.asyncio
async def test_no_job_data_scores_nothing(test_db, monkeypatch):
    from backend.analyzer import cv_scorer
    job = _job(test_db, URL, company="Gone", title="Gone PM", source="levels_fyi")
    job.cached_page_text = BANNER
    test_db.commit()

    async def fetch(url):
        return None
    monkeypatch.setattr("backend.scraper._shared.levels_jobs.fetch_job", fetch)
    assert await cv_scorer._get_job_text(job, db=test_db) is None


class _Page:
    """The two Playwright calls _levelsfyi_extract_detail makes."""
    def __init__(self, next_data):
        self.next_data = next_data

    async def goto(self, url, **kw):
        return None

    async def evaluate(self, script):
        return self.next_data


@pytest.mark.asyncio
@pytest.mark.parametrize("job,found,link", [
    ({"title": "PPM", "description": DESC}, True, None),                                   # applied on levels.fyi
    ({"title": "PPM", "description": DESC, "applicationUrl": "https://jobs.lever.co/d/1"}, True, "https://jobs.lever.co/d/1"),
    ({}, False, None),                                                                     # no job data: unknown
])
async def test_scrape_detail_says_whether_the_data_was_read(job, found, link):
    from backend.scraper.sources.levelsfyi import _levelsfyi_extract_detail
    data = {"props": {"pageProps": {"initialJobDetails": job}}}
    got = await _levelsfyi_extract_detail(_Page(data), URL)
    assert got["found"] is found and got["application_url"] == link


def test_a_levels_job_marked_easy_apply_keeps_it_on_insert(test_db):
    from backend.models.db import Job
    from backend.scraper._shared.dedup import make_content_hash, make_external_id
    job = Job(external_id=make_external_id("Divergent 3D", "PPM", URL), content_hash=make_content_hash("Divergent 3D", "PPM"),
              company="Divergent 3D", title="PPM", url=URL, source="levels_fyi", status="new", seen=False,
              saved=False, link_kind=EASY_APPLY)
    test_db.add(job)
    test_db.commit()
    assert job.link_kind == EASY_APPLY
