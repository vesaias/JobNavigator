"""Regression: _linkedin_import_progress records per-job analysis errors."""
import pytest
from unittest.mock import MagicMock, AsyncMock


@pytest.mark.asyncio
async def test_progress_records_analysis_error(monkeypatch):
    """When analysis fails for a job, progress dict should include a non-zero 'errors' count."""
    import backend.scraper.sources.linkedin_extension as ext

    # Reset progress
    ext._linkedin_import_progress.clear()

    # Stub LinkedIn API
    class FakeLi:
        def __init__(self, *a, **kw): pass
        def get_job(self, lid):
            return {
                "title": "Senior Product Manager",
                "companyDetails": {
                    "com.linkedin.voyager.deco.jobs.web.shared.WebCompactJobPostingCompany": {
                        "companyResolutionResult": {"universalName": "acme", "name": "Acme"}
                    }
                },
                "description": {"text": "We sponsor visas."},
                "formattedLocation": "San Francisco",
                "applyMethod": {},
            }

    monkeypatch.setattr("linkedin_api.Linkedin", FakeLi, raising=False)

    # Break check_job_h1b so the analysis inside the enrich loop raises
    async def broken_h1b(job, db=None):
        raise RuntimeError("h1b broken")

    # linkedin_extension imports check_job_h1b at module load, patch the ref there
    monkeypatch.setattr(ext, "check_job_h1b", broken_h1b)

    # Stub DB session so we don't need real Postgres
    fake_db = MagicMock()
    # Route query(...).filter(...).first() / .all() to sensible defaults.
    # Setting lookups need a truthy .value so credential check passes.
    setting_mock = MagicMock()
    setting_mock.value = "stub"

    def _query_side_effect(model, *args, **kwargs):
        q = MagicMock()
        name = getattr(model, "__name__", str(model))
        if "Setting" in name:
            q.filter.return_value.first.return_value = setting_mock
            q.filter.return_value.all.return_value = []
            q.all.return_value = []
            return q
        # Job / Company / Search / anything else: empty results
        q.filter.return_value.first.return_value = None
        q.filter.return_value.all.return_value = []
        q.all.return_value = []
        return q

    fake_db.query.side_effect = _query_side_effect
    monkeypatch.setattr(ext, "SessionLocal", lambda: fake_db)
    # Neutralize get_existing_external_ids/build_company_lookup/find_company_by_name
    monkeypatch.setattr(ext, "get_existing_external_ids", lambda db: set())
    monkeypatch.setattr(ext, "build_company_lookup", lambda db: {})
    monkeypatch.setattr(ext, "find_company_by_name", lambda db, name: None)
    # Neutralize get_global_title_exclude (imported lazily inside enrich)
    monkeypatch.setattr(
        "backend.models.db.get_global_title_exclude", lambda db: [], raising=False
    )
    # Neutralize salary extractor (imported at module load in enrich)
    monkeypatch.setattr(ext, "apply_salary_to_job", lambda job, median=None: None)

    await ext.enrich(["12345"])

    # After the run, progress dict should reflect the error
    # Accept either an "errors" counter or an "error_details" list
    errs = ext._linkedin_import_progress.get("errors", 0)
    details = ext._linkedin_import_progress.get("error_details", [])
    assert errs > 0 or len(details) > 0, (
        f"Expected progress to record at least one error; got: {ext._linkedin_import_progress}"
    )
