"""Regression: _linkedin_import_progress records per-job analysis errors."""
import pytest
from unittest.mock import MagicMock, AsyncMock


@pytest.mark.asyncio
async def test_progress_records_analysis_error(monkeypatch):
    """When analysis fails for a job, progress dict should include a non-zero 'errors' count."""
    import backend.scraper.sources.linkedin_extension as ext

    ext._linkedin_import_progress.clear()

    # Session present (persisted cookies) so enrich proceeds past the session gate
    monkeypatch.setattr(ext, "_load_session_cookies",
                        lambda: [{"name": "li_at", "value": "x"}])

    # Fake logged-in browser (linkedin_personal._get_linkedin_browser is imported
    # lazily inside enrich, so patch it at its source module).
    fake_page = MagicMock()
    fake_page.goto = AsyncMock()
    fake_page.evaluate = AsyncMock(return_value=200)
    fake_context = MagicMock()
    fake_context.add_cookies = AsyncMock()
    fake_browser = MagicMock(); fake_browser.close = AsyncMock()
    fake_pw = MagicMock(); fake_pw.stop = AsyncMock()

    async def fake_get_browser():
        return fake_pw, fake_browser, fake_context, fake_page

    monkeypatch.setattr(
        "backend.scraper.sources.linkedin_personal._get_linkedin_browser",
        fake_get_browser, raising=False)

    # Voyager fetch returns a valid job (used for both the session probe + the loop)
    async def fake_voyager(page, lid):
        return {"title": "Senior Product Manager", "company": "Acme",
                "location": "San Francisco", "description": "We sponsor visas.",
                "apply_url": ""}

    monkeypatch.setattr(ext, "_voyager_fetch", fake_voyager)

    async def broken_h1b(job, db=None, **kwargs):
        raise RuntimeError("h1b broken")

    monkeypatch.setattr(ext, "check_job_h1b", broken_h1b)

    fake_db = MagicMock()

    def _query_side_effect(model, *args, **kwargs):
        q = MagicMock()
        q.filter.return_value.first.return_value = None
        q.filter.return_value.all.return_value = []
        q.all.return_value = []
        return q

    fake_db.query.side_effect = _query_side_effect
    monkeypatch.setattr(ext, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(ext, "get_existing_external_ids", lambda db: set())
    monkeypatch.setattr(ext, "build_company_lookup", lambda db: {})
    monkeypatch.setattr(
        "backend.models.db.get_global_title_exclude", lambda db: [], raising=False
    )
    monkeypatch.setattr(ext, "apply_salary_to_job", lambda job, median=None: None)

    await ext.enrich(["12345"])

    errs = ext._linkedin_import_progress.get("errors", 0)
    details = ext._linkedin_import_progress.get("error_details", [])
    assert errs > 0 or len(details) > 0, (
        f"Expected progress to record at least one error; got: {ext._linkedin_import_progress}"
    )
