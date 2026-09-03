"""R3-A-01: the test previews must show the body-exclusion layer.

Both previews used to apply only the *title* layers, so a job whose description
matches a `body_exclusion_phrases` entry looked "kept" — then the real run stored
it as `ignored`. The Companies preview promised 14 kept and the run reported
"+13 new" with nothing anywhere saying which one went missing or why.
"""
import json
import types

import pytest

from backend.models.db import Company, Search, Setting

PHRASE = "sponsorship is not available"
BODY_HIT = "We are a great team. Sponsorship is not available for this role. Apply now."
BODY_CLEAN = "We are a great team and we do sponsor visas. Apply now."


def _phrases(db, phrases=(PHRASE,)):
    db.add(Setting(key="body_exclusion_phrases", value=json.dumps(list(phrases))))
    db.commit()


# ── Searches preview ────────────────────────────────────────────────────────

def _fake_jobspy(rows):
    import sys
    import pandas as pd

    mod = types.ModuleType("jobspy")
    mod.scrape_jobs = lambda **kw: pd.DataFrame(rows)
    sys.modules["jobspy"] = mod


def _jrow(title, description):
    return {"site": "indeed", "title": title, "company": "Acme",
            "job_url": f"https://indeed.test/{title}", "description": description,
            "location": "Remote", "min_amount": None, "max_amount": None}


@pytest.mark.asyncio
async def test_search_preview_marks_the_body_excluded_row(test_db):
    from backend.api.routes_searches import test_search

    _phrases(test_db)
    _fake_jobspy([
        _jrow("Program Manager", BODY_CLEAN),
        _jrow("Delivery Manager", BODY_HIT),
    ])
    search = Search(name="ZZ", search_mode="keyword", sources=["indeed"],
                    title_include_keywords=[], title_exclude_keywords=[],
                    company_filter=[], company_exclude=[])
    test_db.add(search)
    test_db.commit()

    out = await test_search(str(search.id), db=test_db)

    rows = {j["title"]: j for j in out["jobs"]}
    assert rows["Program Manager"]["kept"] is True
    assert rows["Program Manager"]["body_excluded_by"] is None
    assert rows["Program Manager"]["body_checked"] is True

    hit = rows["Delivery Manager"]
    assert hit["kept"] is False
    assert hit["body_excluded_by"] == PHRASE
    assert hit["reason"] == f"Body exclusion: {PHRASE}"

    # footer arithmetic: 1 kept · 0 title-filtered · 1 would be ignored
    assert out["after_filter"] == 1
    assert out["body_excluded_count"] == 1
    assert out["body_unchecked_count"] == 0
    assert out["raw_count"] - out["after_filter"] - out["body_excluded_count"] == 0


@pytest.mark.asyncio
async def test_search_preview_says_when_it_cannot_check(test_db):
    """No description in the row → say so, never silently pass it as clean."""
    from backend.api.routes_searches import test_search

    _phrases(test_db)
    _fake_jobspy([_jrow("Program Manager", "")])
    search = Search(name="ZZ", search_mode="keyword", sources=["indeed"],
                    title_include_keywords=[], title_exclude_keywords=[],
                    company_filter=[], company_exclude=[])
    test_db.add(search)
    test_db.commit()

    out = await test_search(str(search.id), db=test_db)

    assert out["jobs"][0]["kept"] is True
    assert out["jobs"][0]["body_checked"] is False
    assert out["body_unchecked_count"] == 1
    assert out["body_excluded_count"] == 0


@pytest.mark.asyncio
async def test_search_preview_unchanged_with_no_phrases_configured(test_db):
    from backend.api.routes_searches import test_search

    _fake_jobspy([_jrow("Program Manager", BODY_HIT)])
    search = Search(name="ZZ", search_mode="keyword", sources=["indeed"],
                    title_include_keywords=[], title_exclude_keywords=[],
                    company_filter=[], company_exclude=[])
    test_db.add(search)
    test_db.commit()

    out = await test_search(str(search.id), db=test_db)
    assert out["jobs"][0]["kept"] is True
    assert out["body_phrase_count"] == 0
    assert out["body_excluded_count"] == 0
    assert out["body_unchecked_count"] == 0


# ── Companies preview ───────────────────────────────────────────────────────

@pytest.fixture
def _fake_board(monkeypatch):
    """Route the company preview through a stubbed Greenhouse board + browser."""
    import backend.scraper._shared.browser as browser_mod
    import backend.scraper.ats.greenhouse as gh

    class _FakeBrowser:
        async def close(self):
            return None

    class _FakePw:
        async def stop(self):
            return None

    async def fake_get_browser():
        return _FakePw(), _FakeBrowser()

    monkeypatch.setattr(browser_mod, "_get_browser", fake_get_browser)
    monkeypatch.setattr(gh, "is_greenhouse", lambda url: True)

    def _set_jobs(jobs):
        async def fake_scrape(url, debug=False, **kw):
            return list(jobs), []
        monkeypatch.setattr(gh, "scrape", fake_scrape)

    return _set_jobs


def _cjob(title, description=None):
    j = {"title": title, "url": f"https://boards.test/{title}"}
    if description is not None:
        j["description"] = description
    return j


@pytest.mark.asyncio
async def test_company_preview_marks_the_body_excluded_row(test_db, _fake_board):
    from backend.api.routes_companies import test_scrape_company

    _phrases(test_db)
    _fake_board([_cjob("SOX Manager", BODY_CLEAN), _cjob("Accounting Manager", BODY_HIT)])
    c = Company(name="ZZ Co", active=True,
                scrape_urls=["https://job-boards.greenhouse.io/zz"],
                title_include_expr="manager", title_exclude_keywords=[])
    test_db.add(c)
    test_db.commit()

    out = await test_scrape_company(str(c.id), db=test_db)

    rows = {j["title"]: j for j in out["jobs"]}
    assert rows["SOX Manager"]["kept"] is True
    assert rows["SOX Manager"]["body_excluded_by"] is None

    hit = rows["Accounting Manager"]
    assert hit["kept"] is False
    assert hit["body_excluded_by"] == PHRASE
    assert hit["reason"] == f"Body exclusion: {PHRASE}"

    assert out["after_filter"] == 1              # what would actually save
    assert out["after_company_filter"] == 2      # both pass the title layers
    assert out["body_excluded_count"] == 1
    assert out["body_unchecked_count"] == 0


@pytest.mark.asyncio
async def test_company_preview_says_when_it_cannot_check(test_db, _fake_board):
    """ATS list endpoints carry no description — the preview must admit that."""
    from backend.api.routes_companies import test_scrape_company

    _phrases(test_db)
    _fake_board([_cjob("SOX Manager")])   # no description key at all
    c = Company(name="ZZ Co", active=True,
                scrape_urls=["https://job-boards.greenhouse.io/zz"],
                title_include_expr="manager", title_exclude_keywords=[])
    test_db.add(c)
    test_db.commit()

    out = await test_scrape_company(str(c.id), db=test_db)

    assert out["jobs"][0]["kept"] is True
    assert out["jobs"][0]["body_checked"] is False
    assert out["body_unchecked_count"] == 1
    assert out["body_excluded_count"] == 0
    assert out["after_filter"] == 1


@pytest.mark.asyncio
async def test_company_preview_body_scan_runs_after_the_title_layers(test_db, _fake_board):
    """A title-filtered row is never body-scanned — the run never gets that far."""
    from backend.api.routes_companies import test_scrape_company

    _phrases(test_db)
    _fake_board([_cjob("Software Engineer", BODY_HIT)])
    c = Company(name="ZZ Co", active=True,
                scrape_urls=["https://job-boards.greenhouse.io/zz"],
                title_include_expr="manager", title_exclude_keywords=[])
    test_db.add(c)
    test_db.commit()

    out = await test_scrape_company(str(c.id), db=test_db)

    row = out["jobs"][0]
    assert row["kept"] is False
    assert row["passes_company_filter"] is False
    assert row["body_excluded_by"] is None       # not reached
    assert out["body_excluded_count"] == 0
    assert out["body_unchecked_count"] == 0
