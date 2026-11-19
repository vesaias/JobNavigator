"""missing_postings.py: a posting missing from two full company scrapes in a row is marked closed."""
import pytest

from backend.models.db import Company, Job
from backend.scraper._shared import missing_postings as mp
from backend.tests.test_posting_links import _job

BOARD = ["https://job-boards.greenhouse.io/acme"]
GH = "https://job-boards.greenhouse.io/acme/jobs/{}"


def _company(db, name="Acme"):
    c = Company(name=name, scrape_urls=BOARD)
    db.add(c)
    db.commit()
    return c


def _posting(n, title=None):
    return {"title": title or f"PM {n}", "url": GH.format(4000000 + n)}


FILL = list(range(100, 110))   # the rest of the board, so one posting more or less is no big drop


def _scrape(db, company, ids, urls=BOARD, errors=()):
    out = mp.note_scrape(db, company, urls, [_posting(n) for n in [*ids, *FILL]], list(errors))
    db.commit()
    return out


def _direct(db, n, **kw):
    return _job(db, GH.format(4000000 + n), company="Acme", title=f"PM {n}", source="direct", **kw)


def test_missing_twice_in_a_row_is_closed(test_db):
    c = _company(test_db)
    stays, goes = _direct(test_db, 1), _direct(test_db, 2)
    _scrape(test_db, c, [1, 2])                 # first full scrape: the baseline
    assert _scrape(test_db, c, [1, 3])["counted"]
    test_db.refresh(goes)
    assert goes.missed_scrapes == 1 and goes.open_state is None
    out = _scrape(test_db, c, [1, 3])
    test_db.refresh(goes)
    test_db.refresh(stays)
    assert out["closed"] == 1 and goes.open_state == "closed" and goes.open_reason == mp.REASON
    assert goes.status == "new"                 # the status never changes
    assert stays.open_state is None and not stays.missed_scrapes


def test_a_posting_that_comes_back_is_open_again(test_db):
    c = _company(test_db)
    job = _direct(test_db, 2)
    for ids in ([1, 2], [1], [1]):
        _scrape(test_db, c, ids)
    test_db.refresh(job)
    assert job.open_state == "closed"
    assert _scrape(test_db, c, [1, 2])["reopened"] == 1
    test_db.refresh(job)
    assert job.open_state == "open" and job.open_reason is None and not job.missed_scrapes


def test_a_job_closed_for_another_reason_is_not_reopened(test_db):
    c = _company(test_db)
    job = _direct(test_db, 2)
    job.open_state, job.open_reason = "closed", "Greenhouse: the posting is gone"
    test_db.commit()
    _scrape(test_db, c, [2])
    _scrape(test_db, c, [2])
    test_db.refresh(job)
    assert job.open_state == "closed" and job.open_reason == "Greenhouse: the posting is gone"


def test_one_miss_then_seen_starts_over(test_db):
    c = _company(test_db)
    job = _direct(test_db, 2)
    for ids in ([1, 2], [1], [1, 2], [1]):
        _scrape(test_db, c, ids)
    test_db.refresh(job)
    assert job.missed_scrapes == 1 and job.open_state is None


def test_new_links_start_the_count_again(test_db):
    c = _company(test_db)
    job = _direct(test_db, 2)
    _scrape(test_db, c, [1, 2])
    _scrape(test_db, c, [1])
    other = ["https://job-boards.greenhouse.io/acme?departments%5B%5D=1"]
    assert not _scrape(test_db, c, [1], urls=other)["counted"]
    _scrape(test_db, c, [1], urls=other)
    test_db.refresh(job)
    assert job.missed_scrapes == 1 and job.open_state is None


def test_a_scrape_that_sees_far_fewer_postings_does_not_count(test_db):
    c = _company(test_db)
    job = _direct(test_db, 2)
    _scrape(test_db, c, range(1, 11))
    assert not _scrape(test_db, c, [1, 3, 4])["counted"]       # 13 of 20: part of the board failed
    test_db.refresh(job)
    assert not job.missed_scrapes
    assert _scrape(test_db, c, [1, 3, 4])["counted"]           # the smaller board is the new normal


def test_failed_or_capped_scrapes_never_count(test_db):
    c = _company(test_db)
    job = _direct(test_db, 2)
    _scrape(test_db, c, [1, 2])
    assert not _scrape(test_db, c, [1], errors=["https://job-boards.greenhouse.io/acme: timeout"])["counted"]
    assert not mp.note_scrape(test_db, c, BOARD, [], [])["counted"]
    meta = ["https://www.metacareers.com/jobs?roles[0]=Product"]
    assert not mp.note_scrape(test_db, c, meta, [_posting(1)], [])["counted"]
    assert not mp.note_scrape(test_db, c, ["https://careers.acme.com/jobs"], [_posting(1)], [])["counted"]
    test_db.refresh(job)
    assert not job.missed_scrapes and job.open_state is None


def test_only_this_companys_own_scrape_rows(test_db):
    c = _company(test_db)
    board_copy = _job(test_db, GH.format(4000002), company="Acme", title="PM 2", source="jobright")
    other_co = _job(test_db, GH.format(4000009), company="Other", title="PM 9", source="direct")
    skipped = _direct(test_db, 5, status="ignored")
    for ids in ([1], [1], [1]):
        _scrape(test_db, c, ids)
    for j in (board_copy, other_co, skipped):
        test_db.refresh(j)
        assert j.open_state is None and not j.missed_scrapes


@pytest.mark.asyncio
async def test_a_company_scrape_closes_a_posting_gone_from_its_board(test_db, monkeypatch):
    import backend.analyzer.h1b_checker as h1b
    import backend.scraper._shared.analysis as analysis
    import backend.scraper.sources.company_pages as cp
    board = {"ids": list(range(1, 12))}

    async def dispatch(url, **kw):
        return [{"title": f"Product Manager {n}", "url": f"https://jobs.lever.co/acme/{n}"} for n in board["ids"]]

    async def no_desc(jobs):
        return []

    async def no_h1b(job, db=None, company_lookup=None, phrases=None):
        job.h1b_jd_flag = False

    async def nothing(*a, **k):
        return None
    monkeypatch.setattr(cp, "_dispatch_ats", dispatch)
    monkeypatch.setattr(cp, "_fetch_descriptions_parallel", no_desc)
    monkeypatch.setattr(h1b, "check_job_h1b", no_h1b)
    monkeypatch.setattr(analysis, "prefetch_h1b", nothing)
    c = Company(name="Acme", scrape_urls=["https://jobs.lever.co/acme"], active=True, auto_scoring_depth="off")
    test_db.add(c)
    test_db.commit()

    await cp.scrape_single_career_page(c)          # stores 11 jobs, the baseline
    board["ids"] = list(range(2, 12))
    await cp.scrape_single_career_page(c)
    await cp.scrape_single_career_page(c)
    test_db.expire_all()
    gone = test_db.query(Job).filter(Job.title == "Product Manager 1").one()
    kept = test_db.query(Job).filter(Job.title == "Product Manager 2").one()
    assert gone.open_state == "closed" and gone.open_reason == mp.REASON
    assert kept.open_state is None


def test_full_board_kinds():
    assert mp.is_full_scrape(["https://jobs.lever.co/acme"], [_posting(1)], [])
    assert mp.is_full_scrape(["https://jobs.ashbyhq.com/hex?departmentId=1"], [_posting(1)], [])
    assert mp.is_full_scrape(["https://acme.wd5.myworkdayjobs.com/External"], [_posting(1)], [])
    assert not mp.is_full_scrape(["https://jobs.lever.co/acme", "https://www.google.com/about/careers/applications/jobs/results"],
                                 [_posting(1)], [])
    assert not mp.is_full_scrape(["https://jobs.uber.com/en/search?department=Product"], [_posting(1)], [])
    assert not mp.is_full_scrape(["https://www.amazon.jobs/en/search?base_query=pm"], [_posting(1)], [])


def test_a_posting_date_window_is_not_a_full_board():
    """'Posted in the last 7 days': an open job ages out of the list, so it must not count as gone."""
    oracle = ("https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/jobs?"
              "lastSelectedFacet=POSTING_DATES&locationId=300000000289738&selectedPostingDatesFacet=7")
    assert not mp.is_full_scrape([oracle], [_posting(1)], [])
    assert mp.is_full_scrape([oracle.replace("&selectedPostingDatesFacet=7", "")], [_posting(1)], [])
    phenom = 'POST|https://careers.x.com/widgets|{"sort":{"field":"postedDate"},"selected_fields":{"country":["Germany"]}}'
    assert mp.is_full_scrape([phenom], [_posting(1)], [])          # sorting by date is not a window
    windowed = phenom.replace('"country"', '"postedDate":["Last 7 days"],"country"')
    assert not mp.is_full_scrape([windowed], [_posting(1)], [])
