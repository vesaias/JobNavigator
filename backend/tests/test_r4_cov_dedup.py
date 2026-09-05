"""R4-T6 coverage · scraper/_shared/dedup.py fallback paths and path folding.

Everything here touches the module-level `_tracking_params_cache`, so the first
fixture snapshots and restores it — a poisoned cache would change the
`external_id` every later test computes.
"""
import json

import pytest


@pytest.fixture(autouse=True)
def _restore_tracking_cache():
    """Snapshot/restore the module-level tracking-param cache around every test."""
    import backend.scraper._shared.dedup as dedup
    saved = dedup._tracking_params_cache
    yield
    dedup._tracking_params_cache = saved


# ── _get_tracking_params ────────────────────────────────────────────────────


def test_db_failure_falls_back_to_the_hardcoded_defaults(monkeypatch):
    """A DB that cannot be opened leaves the hardcoded default set in the cache."""
    import backend.models.db as db_mod
    import backend.scraper._shared.dedup as dedup

    def _explode():
        raise RuntimeError("no database")

    monkeypatch.setattr(db_mod, "SessionLocal", _explode)
    dedup._tracking_params_cache = None

    params = dedup._get_tracking_params()
    assert params is dedup._DEFAULT_TRACKING_PARAMS
    # …and it is cached, so a second call does not retry the dead DB.
    assert dedup._get_tracking_params() is dedup._DEFAULT_TRACKING_PARAMS


def test_a_missing_setting_row_also_yields_the_defaults(test_db):
    """No `dedup_tracking_params` row → defaults (the query succeeds, the row is absent)."""
    import backend.scraper._shared.dedup as dedup

    dedup._tracking_params_cache = None
    assert dedup._get_tracking_params() is dedup._DEFAULT_TRACKING_PARAMS


def test_reload_tracking_params_reads_the_setting_and_lowercases_it(test_db):
    """reload_tracking_params() drops the cache and re-reads the DB, lowercasing every key."""
    from backend.models.db import Setting
    import backend.scraper._shared.dedup as dedup

    test_db.add(Setting(key="dedup_tracking_params",
                        value=json.dumps(["FooBar", "utm_source"])))
    test_db.commit()

    dedup.reload_tracking_params()
    assert dedup._tracking_params_cache == {"foobar", "utm_source"}
    # The loaded set — not the defaults — is what normalisation then uses.
    assert dedup._normalize_url("https://x.com/j/1?FooBar=9") == "https://x.com/j/1"


# ── _normalize_url ──────────────────────────────────────────────────────────


def test_normalize_url_of_empty_string_is_empty():
    """An empty url short-circuits before any parsing."""
    from backend.scraper._shared.dedup import _normalize_url
    assert _normalize_url("") == ""
    assert _normalize_url(None) == ""


def test_normalize_url_returns_the_raw_url_when_parsing_blows_up(monkeypatch):
    """Any parsing failure is swallowed and the caller gets the url back untouched."""
    import backend.scraper._shared.dedup as dedup

    def _explode(_url):
        raise ValueError("unparseable")

    monkeypatch.setattr(dedup, "urlparse", _explode)
    raw = "https://x.com/jobs/1?utm_source=li#frag"
    assert dedup._normalize_url(raw) == raw


# ── _fold_path ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize("path,expected", [
    ("/x/4012345/apply/", "/x/4012345"),   # slash hides the suffix — two passes needed
    ("/x/4012345/apply", "/x/4012345"),
    ("/x/apply/apply", "/x"),              # both passes strip one suffix each
    ("/x/4012345/", "/x/4012345"),
    ("/x/4012345", "/x/4012345"),
    ("/", "/"),                            # a bare root is never emptied
    ("/apply", ""),                        # …but a path that is only a suffix is
    ("/x/application/", "/x"),
    ("/x/thanks", "/x"),
])
def test_fold_path(path, expected):
    """Two-pass folding of a trailing slash plus one ATS apply/thanks suffix."""
    from backend.scraper._shared.dedup import _fold_path
    assert _fold_path(path) == expected


def test_fold_path_stops_after_two_suffixes():
    """Only two passes run, so a third stacked suffix survives (current behaviour)."""
    from backend.scraper._shared.dedup import _fold_path
    assert _fold_path("/x/apply/apply/apply") == "/x/apply"


# ── _canonical_for_hash ─────────────────────────────────────────────────────


def test_canonical_for_hash_of_empty_string_is_empty():
    from backend.scraper._shared.dedup import _canonical_for_hash
    assert _canonical_for_hash("") == ""


def test_canonical_for_hash_falls_back_to_the_normalized_url_on_error(monkeypatch):
    """If the canonical rebuild raises, the normalized url is returned as-is."""
    import backend.scraper._shared.dedup as dedup

    def _explode(_path):
        raise ValueError("nope")

    monkeypatch.setattr(dedup, "_fold_path", _explode)
    # _normalize_url still runs, so the utm param is gone but no folding happened.
    assert dedup._canonical_for_hash("https://X.com/Jobs/1/apply/?utm_source=li") == \
        "https://X.com/Jobs/1/apply/"


def test_canonical_for_hash_folds_scheme_www_case_slash_and_param_order():
    """Twenty spellings of one posting collapse onto one canonical string."""
    from backend.scraper._shared.dedup import _canonical_for_hash
    base = _canonical_for_hash("https://x.com/jobs/1?zone=1&area=2")
    assert _canonical_for_hash("http://WWW.X.com/JOBS/1/?area=2&zone=1") == base


def test_make_external_id_matches_across_the_apply_slash_spelling():
    """The folding is what makes `/4012345/apply/` and `/4012345` one job."""
    from backend.scraper._shared.dedup import make_external_id
    a = make_external_id("Acme", "PM", "https://x.com/jobs/4012345/apply/")
    b = make_external_id("Acme", "PM", "https://x.com/jobs/4012345")
    assert a == b
