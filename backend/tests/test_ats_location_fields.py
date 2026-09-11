"""Every place a board names, from recorded responses of the boards themselves.

`fixtures/ats/` holds trimmed real responses, captured live on 2026-09-10 from
the boards the active companies are scraped from. Each test asserts the three
fields of the handler contract: `location` (the board's own text, never
rewritten), `locations` (every place it names, primary first) and `arrangement`.
"""
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "ats"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _response(payload):
    mock = MagicMock()
    mock.status_code = 200
    mock.text = payload if isinstance(payload, str) else json.dumps(payload)
    mock.json.return_value = (json.loads(payload) if isinstance(payload, str) else payload)
    return mock


def _client(payload, second=None):
    """An httpx.AsyncClient stand-in answering every call with `payload`.

    `second` answers the second GET, for a handler that pages: it lets a test end
    a loop that would otherwise be handed the same page forever.
    """
    client = MagicMock()
    responses = [_response(payload)] + ([_response(second)] if second is not None else [])
    client.get = AsyncMock(side_effect=responses + [responses[-1]] * 10)
    client.post = AsyncMock(side_effect=responses + [responses[-1]] * 10)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


# ── Greenhouse ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_greenhouse_splits_the_location_line_and_adds_the_offices():
    payload = load("greenhouse.json")
    with patch("httpx.AsyncClient", return_value=_client(payload)):
        from backend.scraper.ats.greenhouse import scrape
        jobs = await scrape("https://job-boards.greenhouse.io/anthropic")

    first = jobs[0]
    # the board's own line, semicolons, pipe and repetition included
    assert first["location"] == "New York City, NY; San Francisco, CA | New York City, NY"
    assert first["locations"] == [
        "New York City, NY", "San Francisco, CA",
        "New York, New York, United States", "San Francisco, California, United States",
    ]


@pytest.mark.asyncio
async def test_greenhouse_keeps_a_single_place_and_its_office():
    payload = load("greenhouse.json")
    with patch("httpx.AsyncClient", return_value=_client(payload)):
        from backend.scraper.ats.greenhouse import scrape
        jobs = await scrape("https://job-boards.greenhouse.io/hightouch")

    remote = jobs[1]
    assert remote["location"] == "Remote (North America)"
    assert remote["locations"] == ["Remote (North America)", "New York, New York, United States"]


def test_greenhouse_locations_of_tolerates_an_empty_posting():
    from backend.scraper.ats.greenhouse import _locations_of
    assert _locations_of({}) == []
    assert _locations_of({"location": None, "offices": None}) == []


# ── Workday ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_workday_keeps_the_board_text_and_reads_remote_type():
    payload = load("workday_listing.json")
    with patch("httpx.AsyncClient", return_value=_client(payload)):
        from backend.scraper.ats.workday import scrape
        jobs = await scrape("https://visa.wd5.myworkdayjobs.com/en-US/Visa")

    # `locationsText` verbatim - the parser's canonical form belongs in the
    # loc_* columns, not in the field the feed shows.
    assert jobs[0]["location"] == "US - San Francisco, CA"
    assert jobs[0]["arrangement"] is None
    assert jobs[1]["location"] == "US - Foster City, CA"
    assert jobs[1]["arrangement"] == "Hybrid"
    # a count names no place, so the primary site comes from the URL segment
    assert jobs[2]["location"] == "Foster City, CA, United States"


@pytest.mark.parametrize("value,expected", [
    ("Flex", "hybrid"), ("flex", "hybrid"),
    ("Remote", "Remote"), ("Onsite", "Onsite"), ("Hybrid", "Hybrid"),
    ("", None), (None, None),
])
def test_workday_flex_is_hybrid(value, expected):
    from backend.scraper.ats.workday import _arrangement_of
    assert _arrangement_of({"remoteType": value}) == expected


def test_workday_detail_names_every_site():
    from backend.scraper.ats.workday import detail_locations
    assert detail_locations(load("workday_detail.json")) == [
        "US - Foster City, CA", "US - San Francisco, CA",
    ]


def test_workday_detail_locations_tolerates_a_bare_document():
    from backend.scraper.ats.workday import detail_locations
    assert detail_locations({}) == []
    assert detail_locations({"jobPostingInfo": {"location": "", "additionalLocations": None}}) == []


@pytest.mark.asyncio
async def test_workday_description_fetch_fills_in_the_other_sites():
    """The detail document is fetched for the description anyway; the places it
    names must arrive on the job dict without a second request."""
    detail = load("workday_detail.json")
    client = _client(detail)
    job = {"title": "Director of Product - Agentic Commerce",
           "url": "https://visa.wd5.myworkdayjobs.com/en-US/Visa/job/US---Foster-City-CA/"
                  "Director-of-Product---Agentic-Commerce_REF085033W",
           "location": "2 Locations"}
    with patch("httpx.AsyncClient", return_value=client):
        from backend.scraper.ats._descriptions import _fetch_description_ats
        desc = await _fetch_description_ats(job["url"], job=job)

    assert desc and "Visa is a world leader" in desc
    assert job["locations"] == ["US - Foster City, CA", "US - San Francisco, CA"]
    assert client.get.await_count == 1


# ── Phenom ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_phenom_reads_multi_location():
    payload = load("phenom.json")
    raw = 'POST|https://careers.circle.com/widgets|{"ddoKey":"refineSearch"}'
    resp = _response(payload)
    # `scrape` now pins the endpoint through safe_post (SSRF-hardened): the
    # preflight DNS gate is stubbed and the pinned POST returns the canned body.
    # Both names are imported inside scrape(), so patch the source module.
    with patch("backend.scraper._shared.url_safety.assert_public_http_url"), \
         patch("backend.scraper._shared.url_safety.safe_post", new=AsyncMock(return_value=resp)):
        from backend.scraper.ats.phenom import scrape
        jobs = await scrape(raw)

    first = jobs[0]
    assert first["location"] == "San Francisco, California"
    # every city the posting is open in, primary first and de-duplicated
    assert first["locations"][0] == "San Francisco, California"
    assert "San Francisco, California, United States of America" in first["locations"]
    assert "Atlanta, Georgia, United States of America" in first["locations"]
    assert len(first["locations"]) == len(set(first["locations"]))


@pytest.mark.parametrize("job,expected", [
    ({"multi_location": ["Austin, TX", "Austin, TX", "Dublin, Ireland"]},
     ["Austin, TX", "Dublin, Ireland"]),
    ({"multi_location_array": [{"location": "Berlin, Germany"}]}, ["Berlin, Germany"]),
    ({"cityState": "Austin, TX", "multi_location": ["Austin, TX"]}, ["Austin, TX"]),
    ({}, []),
])
def test_phenom_locations_of(job, expected):
    from backend.scraper.ats.phenom import _locations_of
    assert _locations_of(job) == expected


@pytest.mark.parametrize("job,expected", [
    ({"RemoteType": "Remote"}, "Remote"),
    ({"remoteType": "Hybrid"}, "Hybrid"),
    ({"remote": True}, "remote"),
    ({"remote": False}, None),
    ({"RemoteType": "  "}, None),
    ({}, None),
])
def test_phenom_arrangement_of(job, expected):
    from backend.scraper.ats.phenom import _arrangement_of
    assert _arrangement_of(job) == expected


# ── TalentBrew ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_talentbrew_reads_the_job_location_span():
    payload = load("talentbrew.json")
    with patch("httpx.AsyncClient", return_value=_client(payload)):
        from backend.scraper.ats.talentbrew import scrape
        jobs = await scrape("https://jobs.intuit.com/search-jobs/results?x=1")

    assert jobs
    places = {j["location"] for j in jobs}
    assert "Mountain View, California" in places
    for job in jobs:
        assert job["locations"] == ([job["location"]] if job["location"] else [])


def test_talentbrew_locations_in_reads_several_spans():
    from backend.scraper.ats.talentbrew import _locations_in
    block = ('<h2>Staff PM</h2><span class="job-location">Mountain View, California</span>'
             '<span class="job-location">San Diego, California</span>')
    assert _locations_in(block) == ["Mountain View, California", "San Diego, California"]
    assert _locations_in("<h2>Staff PM</h2>") == []


# ── Oracle HCM ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_oracle_adds_the_secondary_locations():
    payload = load("oracle_hcm.json")
    with patch("httpx.AsyncClient", return_value=_client(payload)):
        from backend.scraper.ats.oracle_hcm import scrape
        jobs = await scrape("https://careers.oracle.com/en/sites/jobsearch/jobs")

    assert jobs[0]["location"] == "Seattle, WA, United States"
    assert jobs[0]["locations"] == ["Seattle, WA, United States",
                                    "Santa Clara, CA, United States", "United States"]
    # a single-site posting still answers exactly one place
    assert jobs[1]["locations"] == ["BENGALURU, KARNATAKA, India"]


# ── Rippling ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rippling_keeps_every_entry_of_one_uuid():
    payload = load("rippling.json")
    with patch("httpx.AsyncClient", return_value=_client(payload)):
        from backend.scraper.ats.rippling import scrape
        jobs = await scrape("https://ats.rippling.com/rippling/jobs")

    multi = next(j for j in jobs if "Broker Channel (Pittsburgh" in j["title"])
    assert multi["location"] in ("Pittsburgh, PA", "Cleveland, OH")
    assert sorted(multi["locations"]) == ["Cleveland, OH", "Pittsburgh, PA"]
    single = next(j for j in jobs if "Austin & San Antonio" in j["title"])
    assert single["locations"] == ["Austin, TX"]


# ── Amazon ───────────────────────────────────────────────────────────────────

def test_is_amazon_only_matches_a_search_url():
    from backend.scraper.ats.amazon import is_amazon
    assert is_amazon("https://www.amazon.jobs/en/search?offset=0")
    assert not is_amazon("https://www.amazon.jobs/en/jobs/123/some-role")
    assert not is_amazon("https://example.com/?x=amazon.jobs/en/search")


@pytest.mark.asyncio
async def test_amazon_reads_location_locations_and_type():
    payload = load("amazon.json")
    with patch("httpx.AsyncClient", return_value=_client(payload)):
        from backend.scraper.ats.amazon import scrape
        jobs = await scrape("https://www.amazon.jobs/en/search?offset=0&result_limit=10")

    multi = jobs[0]
    assert multi["location"].startswith("US, ")
    # the board's own line first, then the readable form of each site
    assert multi["locations"][0] == multi["location"]
    assert len(multi["locations"]) > 1
    assert multi["arrangement"] == "ONSITE"
    from backend.analyzer.work_arrangement import from_structured
    assert from_structured(multi["arrangement"]) == "onsite"


def test_amazon_locations_of_survives_a_broken_entry():
    from backend.scraper.ats.amazon import _locations_of, _arrangement_of
    posting = {"location": "US, OR, Boardman", "locations": ["not json", "{\"type\":\"REMOTE\"}"]}
    assert _locations_of(posting) == ["US, OR, Boardman"]
    assert _arrangement_of(posting) == "REMOTE"


# ── Generic (card text) ──────────────────────────────────────────────────────

CARDS = load("generic_cards.json")["cards"]


@pytest.mark.parametrize("card", CARDS, ids=[
    f"{c['board']}-{c['title'][:24]}" for c in CARDS])
def test_generic_reads_the_place_off_a_recorded_card(card):
    from backend.scraper.ats.generic import _card_place
    assert _card_place(card["text"], card["title"], card.get("hint")) == card["expected"]


def test_generic_splits_a_card_that_lists_two_places():
    from backend.scraper.ats.generic import _split_places
    assert _split_places("Mountain View, California; San Francisco, California") == [
        "Mountain View, California", "San Francisco, California"]
    assert _split_places(None) == []


@pytest.mark.parametrize("text", [
    "Staff Engineer\nSave\nFull-time\nApply",          # nothing but furniture
    "Staff Engineer\nEngineering\nPosted 3 days ago",   # a discipline and a date
    "Staff Engineer\nJul 08, 2026",                     # a date carries a comma
    "Staff Engineer\nSales\nMarketing",                 # two disciplines, no place
])
def test_generic_emits_nothing_when_unsure(text):
    from backend.scraper.ats.generic import _card_place
    assert _card_place(text, "Staff Engineer") is None


def test_generic_refuses_a_location_label_as_a_place():
    from backend.scraper.ats.generic import _hint_place
    assert _hint_place("Location") is None
    assert _hint_place("") is None
    assert _hint_place("Location: Sunnyvale") == "Sunnyvale"
