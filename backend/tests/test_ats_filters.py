"""Board-filter defects in the ATS handlers.

Each test here pins one filter that dropped jobs it should have kept (or sent a
malformed request), so the fix cannot quietly regress:

* Greenhouse — a stored URL whose `offices[]` id carries a stray space.
* Rippling — a "United States" `workLocation` filter against labels that never
  spell the country out ("AR", "Remote (Dallas, Texas, US)").
* Ashby — a `locationId` filter against a posting whose match is a secondary
  location.
* Lever — filter values with a space appended raw to the api.lever.co query.

Payload shapes mirror the recorded responses in `fixtures/ats/` (rippling.json
for the workLocation/uuid shape, greenhouse.json for offices[]); the bodies are
trimmed to the fields each filter reads.
"""
import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _response(payload, *, status=200):
    mock = MagicMock()
    mock.status_code = status
    mock.text = payload if isinstance(payload, str) else json.dumps(payload)
    mock.json.return_value = (payload if not isinstance(payload, str) else None)
    return mock


def _client(payload, *, html=None):
    """An httpx.AsyncClient stand-in.

    `html` answers any GET that is not the JSON API — Ashby fetches its board
    page to resolve filter ids to names.
    """
    client = MagicMock()

    async def _get(url, **kwargs):
        if html is not None and "api." not in url:
            return _response(html)
        return _response(payload)

    client.get = AsyncMock(side_effect=_get)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


# ── Greenhouse: unreadable offices[]/departments[] ids ────────────────────────

def test_greenhouse_reads_an_office_id_with_a_stray_space():
    """A user's stored URL has "4030 094003"; the id is still readable."""
    from backend.scraper.ats.greenhouse import _parse_greenhouse_url
    slug, depts, offices = _parse_greenhouse_url(
        "https://job-boards.greenhouse.io/acme/?offices[]=4030 094003")
    assert slug == "acme"
    assert offices == {4030094003}
    assert depts == set()


def test_greenhouse_reads_an_encoded_space_in_a_department_id():
    from backend.scraper.ats.greenhouse import _parse_greenhouse_url
    _, depts, _ = _parse_greenhouse_url(
        "https://job-boards.greenhouse.io/acme/?departments%5B%5D=40%2030")
    assert depts == {4030}


def test_greenhouse_warns_once_per_url_naming_the_url_and_the_values(caplog):
    """Two unreadable values, one warning — the line names the URL and both."""
    from backend.scraper.ats.greenhouse import _parse_greenhouse_url
    url = "https://job-boards.greenhouse.io/acme/?offices[]=abc&offices[]=x-1&departments[]=7"
    with caplog.at_level(logging.WARNING, logger="jobnavigator.scraper.ats.greenhouse"):
        _, depts, offices = _parse_greenhouse_url(url)

    assert depts == {7}
    assert offices == set()
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    message = warnings[0].getMessage()
    assert url in message
    assert "abc" in message and "x-1" in message


def test_greenhouse_says_nothing_when_every_id_reads():
    from backend.scraper.ats.greenhouse import _parse_greenhouse_url
    with patch("backend.scraper.ats.greenhouse.logger") as log:
        _parse_greenhouse_url("https://job-boards.greenhouse.io/acme/?offices[]=12")
    log.warning.assert_not_called()


# ── Rippling: workLocation filter ────────────────────────────────────────────

@pytest.mark.parametrize("label", [
    "AR",                             # a bare US state code
    "LA",
    "Remote (Dallas, Texas, US)",
    "New York, NY",
    "Austin, TX",
    "United States",
])
def test_rippling_united_states_filter_keeps_us_labels(label):
    from backend.scraper.ats.rippling import _loc_matches
    assert _loc_matches(label, "united states")


@pytest.mark.parametrize("label", [
    "London, United Kingdom",
    "Toronto, ON",
    "Bengaluru, Karnataka, India",
])
def test_rippling_united_states_filter_drops_other_countries(label):
    from backend.scraper.ats.rippling import _loc_matches
    assert not _loc_matches(label, "united states")


@pytest.mark.parametrize("value", ["united states", "usa", "us", "u.s."])
def test_rippling_country_filter_spellings_all_resolve(value):
    from backend.scraper.ats.rippling import _loc_matches
    assert _loc_matches("Austin, TX", value)
    assert not _loc_matches("London, United Kingdom", value)


def test_rippling_other_country_filters_resolve_too():
    from backend.scraper.ats.rippling import _loc_matches
    assert _loc_matches("Toronto, ON", "canada")
    assert not _loc_matches("Austin, TX", "canada")
    assert _loc_matches("London, United Kingdom", "united kingdom")
    assert not _loc_matches("Austin, TX", "united kingdom")


def test_rippling_state_filter_reads_the_state_of_the_label():
    """"Texas" keeps "Austin, TX" — the label never spells the state out."""
    from backend.scraper.ats.rippling import _loc_matches
    assert _loc_matches("Austin, TX", "texas")
    assert _loc_matches("Remote (Dallas, Texas, US)", "texas")
    assert not _loc_matches("Cleveland, OH", "texas")
    # a state filter does not widen to its country
    assert not _loc_matches("New York, NY", "texas")


def test_rippling_city_filter_keeps_the_substring_reading():
    from backend.scraper.ats.rippling import _loc_matches
    assert _loc_matches("Austin, TX", "austin")
    assert not _loc_matches("Cleveland, OH", "austin")


@pytest.mark.asyncio
async def test_rippling_scrape_applies_the_united_states_filter():
    """Same shape as fixtures/ats/rippling.json, trimmed to the filtered fields."""
    payload = [
        {"uuid": "1", "name": "Solutions Engineer",
         "url": "https://ats.rippling.com/acme/jobs/1",
         "department": {"label": "Sales"},
         "workLocation": {"label": "AR", "id": "AR"}},
        {"uuid": "2", "name": "Staff Engineer",
         "url": "https://ats.rippling.com/acme/jobs/2",
         "department": {"label": "Engineering"},
         "workLocation": {"label": "Remote (Dallas, Texas, US)", "id": "dallas"}},
        {"uuid": "3", "name": "Account Executive",
         "url": "https://ats.rippling.com/acme/jobs/3",
         "department": {"label": "Sales"},
         "workLocation": {"label": "Austin, TX", "id": "Austin, TX"}},
        {"uuid": "4", "name": "Product Manager",
         "url": "https://ats.rippling.com/acme/jobs/4",
         "department": {"label": "Product"},
         "workLocation": {"label": "London, United Kingdom", "id": "london"}},
    ]
    with patch("httpx.AsyncClient", return_value=_client(payload)):
        from backend.scraper.ats.rippling import scrape
        jobs = await scrape(
            "https://ats.rippling.com/acme/jobs?workLocation=United%20States")

    assert sorted(j["title"] for j in jobs) == [
        "Account Executive", "Solutions Engineer", "Staff Engineer"]


@pytest.mark.asyncio
async def test_rippling_scrape_applies_a_state_filter():
    payload = [
        {"uuid": "3", "name": "Account Executive",
         "url": "https://ats.rippling.com/acme/jobs/3",
         "department": {"label": "Sales"},
         "workLocation": {"label": "Austin, TX", "id": "Austin, TX"}},
        {"uuid": "2", "name": "Staff Engineer",
         "url": "https://ats.rippling.com/acme/jobs/2",
         "department": {"label": "Engineering"},
         "workLocation": {"label": "Remote (Dallas, Texas, US)", "id": "dallas"}},
        {"uuid": "5", "name": "Recruiter",
         "url": "https://ats.rippling.com/acme/jobs/5",
         "department": {"label": "People"},
         "workLocation": {"label": "Cleveland, OH", "id": "Cleveland, OH"}},
    ]
    with patch("httpx.AsyncClient", return_value=_client(payload)):
        from backend.scraper.ats.rippling import scrape
        jobs = await scrape("https://ats.rippling.com/acme/jobs?workLocation=Texas")

    assert sorted(j["title"] for j in jobs) == ["Account Executive", "Staff Engineer"]


# ── Ashby: locationId filter reads secondaryLocations ────────────────────────

ASHBY_BOARD_HTML = (
    '<script>{"jobPostings":[{"locationId":"loc-ny","locationName":"New York"},'
    '{"locationId":"loc-sf","locationName":"San Francisco"}]}</script>'
)


@pytest.mark.asyncio
async def test_ashby_location_filter_matches_a_secondary_location():
    """Primary says San Francisco, a secondary says New York — the filter keeps it."""
    payload = {"jobs": [
        {"title": "Staff Engineer", "jobUrl": "https://jobs.ashbyhq.com/acme/1",
         "location": "San Francisco", "workplaceType": "Hybrid",
         "secondaryLocations": [{"location": "New York"}, {"location": "Austin"}]},
        {"title": "Designer", "jobUrl": "https://jobs.ashbyhq.com/acme/2",
         "location": "San Francisco", "workplaceType": "Onsite",
         "secondaryLocations": [{"location": "Austin"}]},
    ]}
    with patch("httpx.AsyncClient", return_value=_client(payload, html=ASHBY_BOARD_HTML)):
        from backend.scraper.ats.ashby import scrape
        jobs = await scrape("https://jobs.ashbyhq.com/acme?locationId=loc-ny")

    assert [j["title"] for j in jobs] == ["Staff Engineer"]
    # the kept posting still carries every place it names, primary first
    assert jobs[0]["locations"] == ["San Francisco", "New York", "Austin"]


@pytest.mark.asyncio
async def test_ashby_location_filter_still_matches_the_primary():
    payload = {"jobs": [
        {"title": "Staff Engineer", "jobUrl": "https://jobs.ashbyhq.com/acme/1",
         "location": "New York", "secondaryLocations": []},
        {"title": "Designer", "jobUrl": "https://jobs.ashbyhq.com/acme/2",
         "location": "San Francisco"},
    ]}
    with patch("httpx.AsyncClient", return_value=_client(payload, html=ASHBY_BOARD_HTML)):
        from backend.scraper.ats.ashby import scrape
        jobs = await scrape("https://jobs.ashbyhq.com/acme?locationId=loc-ny")

    assert [j["title"] for j in jobs] == ["Staff Engineer"]


@pytest.mark.asyncio
async def test_ashby_secondary_locations_survive_a_malformed_entry():
    payload = {"jobs": [
        {"title": "Staff Engineer", "jobUrl": "https://jobs.ashbyhq.com/acme/1",
         "location": "San Francisco",
         "secondaryLocations": [None, {}, {"location": None}, {"location": "New York"}]},
    ]}
    with patch("httpx.AsyncClient", return_value=_client(payload, html=ASHBY_BOARD_HTML)):
        from backend.scraper.ats.ashby import scrape
        jobs = await scrape("https://jobs.ashbyhq.com/acme?locationId=loc-ny")

    assert [j["title"] for j in jobs] == ["Staff Engineer"]


# ── Lever: filter values are URL-encoded ─────────────────────────────────────

@pytest.mark.asyncio
async def test_lever_encodes_filter_values_with_spaces():
    client = _client([])
    with patch("httpx.AsyncClient", return_value=client):
        from backend.scraper.ats.lever import scrape
        await scrape("https://jobs.lever.co/acme?location=San%20Francisco&team=Data%20Science")

    requested = client.get.await_args.args[0]
    assert requested == ("https://api.lever.co/v0/postings/acme?mode=json"
                         "&team=Data%20Science&location=San%20Francisco")
    assert " " not in requested


@pytest.mark.asyncio
async def test_lever_encodes_a_plus_encoded_space_too():
    """Lever's own board writes spaces as `+`; parse_qs decodes them the same."""
    client = _client([])
    with patch("httpx.AsyncClient", return_value=client):
        from backend.scraper.ats.lever import scrape
        await scrape("https://jobs.lever.co/acme?location=San+Francisco")

    assert client.get.await_args.args[0] == (
        "https://api.lever.co/v0/postings/acme?mode=json&location=San%20Francisco")


@pytest.mark.asyncio
async def test_lever_leaves_a_plain_value_untouched():
    client = _client([])
    with patch("httpx.AsyncClient", return_value=client):
        from backend.scraper.ats.lever import scrape
        await scrape("https://jobs.lever.co/acme?department=Engineering&commitment=Full-time")

    assert client.get.await_args.args[0] == (
        "https://api.lever.co/v0/postings/acme?mode=json"
        "&department=Engineering&commitment=Full-time")


@pytest.mark.asyncio
async def test_lever_encodes_a_value_that_would_forge_a_query_param():
    """An `&` inside a value must not open a parameter of its own."""
    client = _client([])
    with patch("httpx.AsyncClient", return_value=client):
        from backend.scraper.ats.lever import scrape
        await scrape("https://jobs.lever.co/acme?team=Sales%20%26%20Marketing")

    assert client.get.await_args.args[0] == (
        "https://api.lever.co/v0/postings/acme?mode=json&team=Sales%20%26%20Marketing")
