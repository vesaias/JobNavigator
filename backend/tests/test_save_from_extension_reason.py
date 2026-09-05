"""POST /jobs/save-from-extension must say why a job never reached the feed; save_from_extension is a plain async route function taking its Session as a parameter, so tests call it directly (no backend.main, no TestClient)."""
import pytest

from backend.models.db import Job, Search, Setting


@pytest.fixture
def _no_h1b(monkeypatch):
    """The body-exclusion scan does a live MyVisaJobs lookup for unknown companies; stub it since these tests are about the title/company layer."""
    import backend.analyzer.h1b_checker as h1b

    async def _noop(job, db=None, **kw):
        return None

    monkeypatch.setattr(h1b, "check_job_h1b", _noop)


def _ext_search(db, exclude=None, include=None, company_exclude=None):
    s = Search(name="Extension", search_mode="extension", active=True,
               title_include_keywords=include or [],
               title_exclude_keywords=exclude or [],
               company_filter=[], company_exclude=company_exclude or [],
               auto_scoring_depth="off")
    db.add(s)
    db.commit()
    return s


async def _save(db, title="Product Manager", company="Acme",
                url="https://acme.test/jobs/1"):
    from backend.api.routes_jobs import save_from_extension
    return await save_from_extension(
        {"title": title, "company": company, "url": url,
         "description": "An ordinary description."}, db=db)


@pytest.mark.asyncio
async def test_kept_job_reports_saved_true(test_db, _no_h1b):
    _ext_search(test_db)
    out = await _save(test_db)
    assert out["saved"] is True
    assert out["status"] == "new"
    assert "reason" not in out


@pytest.mark.asyncio
async def test_per_search_title_exclude_names_the_keyword(test_db, _no_h1b):
    _ext_search(test_db, exclude=["intern"])
    out = await _save(test_db, title="Product Intern")

    assert out["saved"] is False
    assert out["status"] == "ignored"
    assert out["reason"] == "title excluded by 'intern'"
    # the row is still written — that is what makes the dedup key stick
    assert test_db.query(Job).filter(Job.title == "Product Intern").one().status == "ignored"


@pytest.mark.asyncio
async def test_global_title_exclude_names_the_keyword(test_db, _no_h1b):
    """`title_exclude_global` applies silently, with the search's own list empty."""
    import json
    test_db.add(Setting(key="title_exclude_global", value=json.dumps(["intern", "contract"])))
    test_db.commit()
    _ext_search(test_db)

    out = await _save(test_db, title="Contract Product Manager")
    assert out["saved"] is False
    assert out["reason"] == "title excluded by 'contract'"


@pytest.mark.asyncio
async def test_title_include_miss_is_explained(test_db, _no_h1b):
    _ext_search(test_db, include=["manager", "director"])
    out = await _save(test_db, title="Software Engineer")

    assert out["saved"] is False
    assert out["reason"] == "title matches none of the required keywords (manager, director)"


@pytest.mark.asyncio
async def test_company_exclude_is_explained(test_db, _no_h1b):
    _ext_search(test_db, company_exclude=["Acme"])
    out = await _save(test_db, company="acme")

    assert out["saved"] is False
    assert out["reason"] == "company excluded by 'Acme'"


@pytest.mark.asyncio
async def test_body_exclusion_is_explained(test_db, monkeypatch):
    import backend.analyzer.h1b_checker as h1b

    async def _flag(job, db=None, **kw):
        job.h1b_jd_flag = True
        job._h1b_matched_phrase = "no visa sponsorship"

    monkeypatch.setattr(h1b, "check_job_h1b", _flag)
    _ext_search(test_db)

    out = await _save(test_db)
    assert out["saved"] is False
    assert out["reason"] == "description matched the excluded phrase 'no visa sponsorship'"


@pytest.mark.asyncio
async def test_resaving_a_filtered_job_still_says_it_is_out(test_db, _no_h1b):
    """The second save hits the dedup branch; the response must distinguish it from a job sitting happily in the feed."""
    _ext_search(test_db, exclude=["intern"])
    first = await _save(test_db, title="Product Intern")
    second = await _save(test_db, title="Product Intern")

    assert first["saved"] is False
    assert second == {**second, "new": False, "saved": False, "status": "ignored"}
    assert "filtered out" in second["reason"]


@pytest.mark.asyncio
async def test_resaving_a_kept_job_reports_saved_true(test_db, _no_h1b):
    _ext_search(test_db)
    await _save(test_db)
    second = await _save(test_db)

    assert second["new"] is False
    assert second["saved"] is True
    assert "reason" not in second
