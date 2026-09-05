"""JobSpy field cleaning: pandas nulls must never be stringified into 'None'/'nan' — `_clean` detects the actual null instead of doing `str(cell)` on a None/NaN DataFrame cell."""


def test_clean_returns_none_for_nulls():
    from backend.scraper.sources.jobspy import _clean
    assert _clean(None) is None
    assert _clean(float("nan")) is None
    assert _clean("") is None
    assert _clean("   ") is None


def test_clean_preserves_real_values():
    from backend.scraper.sources.jobspy import _clean
    assert _clean("Senior PM") == "Senior PM"
    assert _clean("  padded text  ") == "padded text"
    assert _clean(42) == "42"  # non-string scalars still coerce


def test_clean_never_produces_literal_none_or_nan():
    """The exact regression: a null must not become the string 'None' or 'nan'."""
    from backend.scraper.sources.jobspy import _clean
    assert _clean(None) != "None"
    assert _clean(float("nan")) != "nan"
