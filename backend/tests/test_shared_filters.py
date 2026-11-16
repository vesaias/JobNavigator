"""Tests for _shared/filters.py — title filtering + expression parser + company filters."""
import pytest


def test_garbage_titles_has_common_entries():
    from backend.scraper._shared.filters import GARBAGE_TITLES
    assert isinstance(GARBAGE_TITLES, set)
    for p in ["apply now", "learn more", "read more", "sign in"]:
        assert p in GARBAGE_TITLES


def test_job_site_navigation_is_not_a_job():
    """Uber's moved careers site left only "Saved jobs" and its language switcher on the page."""
    from backend.scraper._shared.filters import _validate_job
    for title in ("Saved jobs", "German, Deutsch", "English, English", "French - Français", "Back to search results"):
        assert _validate_job(title, "https://jobs.uber.com/en/jobs/saved-jobs/"), title


def test_titles_that_name_a_language_are_still_jobs():
    from backend.scraper._shared.filters import _validate_job
    for title in ("German Speaking Account Manager", "Product Manager, German Market",
                  "Spanish, Portuguese and English Support Lead", "English Teacher"):
        assert _validate_job(title, "https://jobs.example.com/jobs/12345") is None, title


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


def test_short_include_words_match_whole_words_only():
    from backend.scraper._shared.filters import include_hit, match_title_expr, title_kept
    # PM stands alone: a title word, after "Senior", before a comma or a dash, or as "PM-T"; plural allowed
    for title in ("Senior PM, International Trading", "Staff PM - Growth", "PM", "Sr. PM-T, Payments", "PMs for Ads"):
        assert include_hit("PM", title.lower()), title
    # ... but never inside a longer word
    for title in ("Business Development Lead", "Shipment Coordinator", "Equipment Planner", "Senior TPM", "PMM Lead"):
        assert not include_hit("pm", title.lower()), title
    assert match_title_expr("product OR program OR project OR PM", "Senior PM, International Trading")
    assert not match_title_expr("product OR program OR project OR PM", "Development Manager")
    assert title_kept("Staff PM, Growth", ["product manager", "pm"], [])[0]
    assert not title_kept("Development Lead", ["pm"], [])[0]


def test_longer_include_words_stay_substrings():
    from backend.scraper._shared.filters import include_hit, match_title_expr
    assert include_hit("product manag", "senior product management lead")
    assert include_hit("program", "programme manager")
    assert include_hit("solution", "solutions architect")
    assert match_title_expr('"forward deploy" OR TPM', "Forward Deployed Strategist")
    assert match_title_expr("TPM OR PMO", "Senior TPM, Payments")
    assert match_title_expr("TPM OR PMO", "PMO Lead")


def test_jobspy_include_filter_uses_whole_word_short_keywords():
    import pandas as pd
    from backend.scraper.sources.jobspy import apply_title_filters
    df = pd.DataFrame({"title": ["Senior PM, Payments", "Business Development Manager", "Product Manager (C++)"]})
    kept, _ = apply_title_filters(df, ["pm", "product manager (c++)"], [])
    assert list(kept["title"]) == ["Senior PM, Payments", "Product Manager (C++)"]
