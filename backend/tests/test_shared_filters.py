"""Tests for _shared/filters.py — title filtering + expression parser + company filters."""
import pytest


def test_garbage_titles_has_common_entries():
    from backend.scraper._shared.filters import GARBAGE_TITLES
    assert isinstance(GARBAGE_TITLES, set)
    for p in ["apply now", "learn more", "read more", "sign in"]:
        assert p in GARBAGE_TITLES


def test_garbage_substrings_is_list():
    from backend.scraper._shared.filters import GARBAGE_SUBSTRINGS
    assert isinstance(GARBAGE_SUBSTRINGS, list)
    assert any("talent network" in s.lower() for s in GARBAGE_SUBSTRINGS)


def test_locale_names_has_common_languages():
    from backend.scraper._shared.filters import _LOCALE_NAMES
    assert "deutsch" in _LOCALE_NAMES
    assert "español" in _LOCALE_NAMES


def test_match_title_expr_simple_substring():
    from backend.scraper._shared.filters import match_title_expr
    assert match_title_expr("product manager", "Senior Product Manager")
    assert not match_title_expr("data scientist", "Senior Product Manager")


def test_match_title_expr_or():
    from backend.scraper._shared.filters import match_title_expr
    assert match_title_expr("product OR program", "Senior Program Manager")
    assert match_title_expr("product OR program", "Product Lead")
    assert not match_title_expr("product OR program", "Data Scientist")


def test_match_title_expr_and():
    from backend.scraper._shared.filters import match_title_expr
    assert match_title_expr("senior AND product", "Senior Product Manager")
    assert not match_title_expr("senior AND product", "Senior Engineer")


def test_match_title_expr_empty_allows_all():
    from backend.scraper._shared.filters import match_title_expr
    assert match_title_expr("", "Anything Goes")


def test_match_title_expr_quoted_phrase():
    from backend.scraper._shared.filters import match_title_expr
    assert match_title_expr('"product manager"', "Senior Product Manager")


def test_validate_job_rejects_garbage_title():
    from backend.scraper._shared.filters import _validate_job
    # Exact garbage match (>=10 chars to pass the length check first)
    reason = _validate_job("Talent Network", "https://example.com/jobs/123")
    assert reason is not None
    assert "Garbage" in reason or "garbage" in reason.lower()


def test_validate_job_rejects_short_title():
    from backend.scraper._shared.filters import _validate_job
    reason = _validate_job("Hi", "https://example.com/jobs/123")
    assert reason is not None


def test_validate_job_rejects_empty_url():
    from backend.scraper._shared.filters import _validate_job
    reason = _validate_job("Senior Product Manager", "")
    assert reason is not None


def test_validate_job_rejects_mailto():
    from backend.scraper._shared.filters import _validate_job
    reason = _validate_job("Senior Product Manager", "mailto:jobs@example.com")
    assert reason is not None


def test_validate_job_accepts_real_job():
    from backend.scraper._shared.filters import _validate_job
    reason = _validate_job("Senior Product Manager", "https://example.com/jobs/123")
    assert reason is None


def test_apply_company_filters_include_expr():
    from backend.scraper._shared.filters import _apply_company_filters

    class FakeCompany:
        title_include_expr = "product OR program"
        title_exclude_keywords = []

    jobs = [
        {"title": "Product Manager", "url": "https://x.com/1"},
        {"title": "Data Scientist", "url": "https://x.com/2"},
        {"title": "Program Manager", "url": "https://x.com/3"},
    ]
    kept, rejected = _apply_company_filters(jobs, FakeCompany())
    kept_titles = [j["title"] for j in kept]
    assert "Product Manager" in kept_titles
    assert "Program Manager" in kept_titles
    assert "Data Scientist" not in kept_titles


def test_apply_company_filters_exclude_keywords():
    from backend.scraper._shared.filters import _apply_company_filters

    class FakeCompany:
        title_include_expr = ""
        title_exclude_keywords = ["intern"]

    jobs = [
        {"title": "Senior PM", "url": "https://x.com/1"},
        {"title": "PM Intern", "url": "https://x.com/2"},
    ]
    kept, _ = _apply_company_filters(jobs, FakeCompany())
    titles = [j["title"] for j in kept]
    assert "Senior PM" in titles
    assert "PM Intern" not in titles


def test_apply_company_filters_global_exclude():
    from backend.scraper._shared.filters import _apply_company_filters

    class FakeCompany:
        title_include_expr = ""
        title_exclude_keywords = []

    jobs = [
        {"title": "Junior Developer", "url": "https://x.com/1"},
        {"title": "Senior Developer", "url": "https://x.com/2"},
    ]
    kept, _ = _apply_company_filters(jobs, FakeCompany(), global_title_exclude=["junior"])
    titles = [j["title"] for j in kept]
    assert "Junior Developer" not in titles
    assert "Senior Developer" in titles
