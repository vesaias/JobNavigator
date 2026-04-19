"""Tests for _shared/dedup.py — external_id + content_hash stability."""
import pytest


def test_make_external_id_stable_across_tracking_params():
    """Same URL with different tracking params → same hash."""
    from backend.scraper._shared.dedup import make_external_id
    a = make_external_id("Acme", "PM", "https://x.com/jobs/123?utm_source=li")
    b = make_external_id("Acme", "PM", "https://x.com/jobs/123?utm_campaign=z")
    c = make_external_id("Acme", "PM", "https://x.com/jobs/123")
    assert a == b == c


def test_make_external_id_differs_by_url_path():
    """Different URL paths → different hash."""
    from backend.scraper._shared.dedup import make_external_id
    a = make_external_id("Acme", "PM", "https://x.com/jobs/123")
    b = make_external_id("Acme", "PM", "https://x.com/jobs/456")
    assert a != b


def test_make_external_id_falls_back_to_company_title_when_no_url():
    """Empty URL → hash uses company + title."""
    from backend.scraper._shared.dedup import make_external_id
    a = make_external_id("Acme", "PM", "")
    b = make_external_id("Beta", "PM", "")
    assert a != b


def test_make_external_id_strips_apply_suffix():
    """/apply and /application suffixes are normalized away."""
    from backend.scraper._shared.dedup import make_external_id
    a = make_external_id("Acme", "PM", "https://x.com/jobs/123/apply")
    b = make_external_id("Acme", "PM", "https://x.com/jobs/123")
    assert a == b


def test_make_external_id_strips_fragment():
    """URL fragment doesn't affect hash."""
    from backend.scraper._shared.dedup import make_external_id
    a = make_external_id("Acme", "PM", "https://x.com/jobs/123#top")
    b = make_external_id("Acme", "PM", "https://x.com/jobs/123")
    assert a == b


def test_make_content_hash_case_insensitive():
    from backend.scraper._shared.dedup import make_content_hash
    a = make_content_hash("Acme", "Senior PM")
    b = make_content_hash("ACME", "senior pm")
    assert a == b


def test_make_content_hash_differs_by_title():
    from backend.scraper._shared.dedup import make_content_hash
    a = make_content_hash("Acme", "PM")
    b = make_content_hash("Acme", "Engineer")
    assert a != b


def test_make_content_hash_returns_sha256_hex():
    from backend.scraper._shared.dedup import make_content_hash
    h = make_content_hash("Acme", "PM")
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_reload_tracking_params_callable():
    from backend.scraper._shared.dedup import reload_tracking_params
    assert callable(reload_tracking_params)


def test_default_tracking_params_includes_utm():
    from backend.scraper._shared.dedup import _DEFAULT_TRACKING_PARAMS
    assert "utm_source" in _DEFAULT_TRACKING_PARAMS
    assert "utm_medium" in _DEFAULT_TRACKING_PARAMS
