"""The Amazon search page's country filter must reach the JSON feed under the key the feed reads."""
from backend.scraper.ats.amazon import _feed_params

PAGE_QUERY = ("offset=0&result_limit=10&sort=recent&category%5B%5D=project-program-product-management-technical"
              "&job_type%5B%5D=Full-Time&country%5B%5D=USA&category_type=Corporate&latitude=&longitude="
              "&loc_query=&base_query=&city=&country=&region=&county=&query_options=&")


def test_country_filter_is_translated_and_blanks_dropped():
    p = _feed_params(PAGE_QUERY)
    assert p["normalized_country_code[]"] == ["USA"]
    assert "country[]" not in p and "country" not in p
    for blank in ("latitude", "loc_query", "city", "region", "county", "query_options"):
        assert blank not in p
    assert p["category[]"] == ["project-program-product-management-technical"]
    assert p["job_type[]"] == ["Full-Time"]


def test_no_country_means_no_filter():
    assert "normalized_country_code[]" not in _feed_params("base_query=pm&sort=recent")
