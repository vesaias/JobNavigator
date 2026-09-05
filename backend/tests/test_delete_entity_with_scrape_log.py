"""A scraped company or a run search must still be deletable: the handlers orphan ScrapeLog/Job rows (nulling the FK) rather than raising on delete."""
import pytest
from fastapi import HTTPException

from backend.api.routes_companies import delete_company
from backend.api.routes_searches import delete_search
from backend.models.db import Company, Job, ScrapeLog, Search

CO_ID = "8b888888-88b8-48b8-8888-888888888888"
SE_ID = "9c999999-99c9-49c9-8999-999999999999"
OTHER_SE_ID = "a1aaaaaa-aaa1-4aa1-8aaa-aaaaaaaaaaaa"


def test_company_with_scrape_history_is_deletable(test_db):
    test_db.add(Company(id=CO_ID, name="ZZ Vercel Co"))
    test_db.add(ScrapeLog(company_id=CO_ID, source="playwright_url", jobs_found=13, new_jobs=13))
    test_db.add(ScrapeLog(company_id=CO_ID, source="playwright_url", jobs_found=0, is_warning=True))
    test_db.commit()

    assert delete_company(CO_ID, db=test_db) == {"deleted": True}

    assert test_db.query(Company).count() == 0
    logs = test_db.query(ScrapeLog).all()
    assert len(logs) == 2, "the audit trail is orphaned, not deleted"
    assert all(l.company_id is None for l in logs)
    assert {l.jobs_found for l in logs} == {13, 0}


def test_search_with_runs_and_stored_jobs_is_deletable(test_db):
    test_db.add(Search(id=SE_ID, name="ZZ Search"))
    test_db.add(Search(id=OTHER_SE_ID, name="Keep me"))
    test_db.add(ScrapeLog(search_id=SE_ID, source="jobspy", jobs_found=4))
    test_db.add(ScrapeLog(search_id=OTHER_SE_ID, source="jobspy", jobs_found=9))
    test_db.add(Job(external_id="ext-a08-1", title="TPM", company="Acme",
                    url="https://x.test/1", search_id=SE_ID))
    test_db.add(Job(external_id="ext-a08-2", title="PM", company="Acme",
                    url="https://x.test/2", search_id=OTHER_SE_ID))
    test_db.commit()

    assert delete_search(SE_ID, db=test_db) == {"deleted": True}

    assert [s.name for s in test_db.query(Search).all()] == ["Keep me"]
    # the search's own rows are orphaned; the other search's are untouched
    mine = test_db.query(ScrapeLog).filter(ScrapeLog.jobs_found == 4).one()
    theirs = test_db.query(ScrapeLog).filter(ScrapeLog.jobs_found == 9).one()
    assert mine.search_id is None and str(theirs.search_id) == OTHER_SE_ID
    kept = test_db.query(Job).filter(Job.external_id == "ext-a08-1").one()
    other = test_db.query(Job).filter(Job.external_id == "ext-a08-2").one()
    assert kept.search_id is None, "jobs are kept, just unlinked"
    assert str(other.search_id) == OTHER_SE_ID


def test_missing_entities_still_404(test_db):
    for fn in (delete_company, delete_search):
        with pytest.raises(HTTPException) as exc:
            fn("b2bbbbbb-bbb2-4bb2-8bbb-bbbbbbbbbbbb", db=test_db)
        assert exc.value.status_code == 404


def test_built_in_extension_search_is_still_protected(test_db):
    test_db.add(Search(id=SE_ID, name="Extension LI", search_mode="linkedin_extension"))
    test_db.add(ScrapeLog(search_id=SE_ID, source="linkedin_extension", jobs_found=2))
    test_db.commit()

    with pytest.raises(HTTPException) as exc:
        delete_search(SE_ID, db=test_db)
    assert exc.value.status_code == 409
    # the guard fires before anything is orphaned
    assert str(test_db.query(ScrapeLog).one().search_id) == SE_ID
    assert test_db.query(Search).count() == 1
