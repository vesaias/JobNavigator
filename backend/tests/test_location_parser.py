"""Tests for analyzer/location.py — order-agnostic location parsing.

Every input marked "live" was taken from a real board response, not invented.

The `CA` cases carry the most weight. California and Canada share the code, so
a careless reader moves a job between two countries. The rule under test: the
code is read only when something else in the string pins the country, and the
parse is marked ambiguous otherwise.
"""
import pytest

from backend.analyzer.location import canonical, parse


# ── Workday, one field per tenant (live) ─────────────────────────────────────

@pytest.mark.parametrize("text,expected", [
    # nvidia: comma, country first
    ("US, CA, Santa Clara", "Santa Clara, CA, United States"),
    ("Japan, Tokyo", "Tokyo, Japan"),
    ("Israel, Yokneam", "Yokneam, Israel"),
    ("Switzerland, Zurich", "Zurich, Switzerland"),
    # salesforce: spaced dash, country OR state first
    ("Ireland - Dublin", "Dublin, Ireland"),
    ("Canada - Toronto", "Toronto, Canada"),
    ("California - San Francisco", "San Francisco, CA, United States"),
    ("United Kingdom - London", "London, United Kingdom"),
    ("Mexico - Mexico City", "Mexico City, Mexico"),
    # workday: dot separator
    ("USA.VA.Reston", "Reston, VA, United States"),
    ("USA, CA, Pleasanton", "Pleasanton, CA, United States"),
    ("USA, GA, Atlanta", "Atlanta, GA, United States"),
    ("Costa Rica", "Costa Rica"),
])
def test_workday_tenant_formats(text, expected):
    assert canonical(text) == expected


def test_the_order_of_the_parts_does_not_matter():
    """The same place, written three ways by three tenants."""
    assert (canonical("US, CA, Santa Clara")
            == canonical("Santa Clara, CA, USA")
            == canonical("California - Santa Clara"))


# ── the CA trap ──────────────────────────────────────────────────────────────

def test_ca_is_california_when_a_country_token_pins_it():
    result = parse("US, CA, Santa Clara")
    assert result["country"] == "US"
    assert result["region"] == "CA"
    assert result["ambiguous"] is False


def test_ca_is_canada_when_a_province_code_pins_it():
    """BC is a Canadian code and no US state's, so the country is settled."""
    result = parse("CA, BC, Vancouver")
    assert result["country"] == "CA"
    assert result["region"] == "BC"
    assert result["city"] == "Vancouver"
    assert result["ambiguous"] is False


@pytest.mark.parametrize("text", [
    "CA",
    # Richmond is a city in California and a city in British Columbia, so the
    # gazetteer refuses it the way it refuses a name it has never seen.
    "Richmond, CA",
    "Petropolis, CA",
    # Ontario is a Canadian province AND a city in California, so the province
    # name alone must not settle the country.
    "Ontario, CA",
])
def test_ca_stays_unread_without_a_strong_signal(text):
    result = parse(text)
    assert result["ambiguous"] is True
    assert "CA" in (result["note"] or "")


def test_a_city_in_only_one_of_the_two_settles_ca():
    """The held-out code yields to a city the gazetteer places: three quarters
    of the "<city>, CA" strings in the database are Californian."""
    assert (parse("San Francisco, CA")["country"], parse("San Francisco, CA")["region"]) \
        == ("US", "CA")
    assert (parse("Burnaby, CA")["country"], parse("Burnaby, CA")["region"]) \
        == ("CA", "BC")


def test_an_ambiguous_parse_keeps_the_board_text():
    """A guess must never replace what the board wrote."""
    assert canonical("Ontario, CA") == "Ontario, CA"
    assert canonical("Richmond, CA") == "Richmond, CA"


def test_a_written_out_country_settles_ca():
    assert canonical("Ontario, Canada") == "ON, Canada"
    assert parse("Ontario, Canada")["ambiguous"] is False


# ── the other twenty-five colliding codes ────────────────────────────────────

@pytest.mark.parametrize("text,region,country", [
    ("Atlanta, GA", "GA", "US"),      # not Gabon
    ("Wilmington, DE", "DE", "US"),   # not Germany
    ("Indianapolis, IN", "IN", "US"),  # not India
    ("New Orleans, LA", "LA", "US"),  # not Laos
    ("Baltimore, MD", "MD", "US"),    # not Moldova
    ("Portland, ME", "ME", "US"),     # not Montenegro
    ("Philadelphia, PA", "PA", "US"),  # not Panama
    ("Richmond, VA", "VA", "US"),     # not the Vatican
])
def test_city_plus_code_reads_as_the_us_state(text, region, country):
    """`City, XX` is the dominant board convention; the country reading of
    these codes is vanishingly rare in that shape."""
    result = parse(text)
    assert (result["region"], result["country"]) == (region, country)
    assert result["ambiguous"] is False
    assert result["assumed"], "the assumption must be reported"


def test_the_us_state_assumption_is_not_applied_to_ca():
    """CA is held out of the assumption on purpose. A city the gazetteer places
    settles it; a city it cannot place leaves it unread, where the "City, XX"
    convention would have made it California."""
    from backend.analyzer.location import COUNTRY_FIRST_CODES
    assert COUNTRY_FIRST_CODES == {"CA"}
    assert parse("Richmond, CA")["ambiguous"] is True


def test_a_written_out_country_beats_the_assumption():
    result = parse("Berlin, DE, Germany")
    assert result["country"] == "DE"
    assert result["city"] == "Berlin"


# ── a city that shares its name with a region ────────────────────────────────

@pytest.mark.parametrize("text,city,region", [
    ("New York, NY", "New York", "NY"),
    ("Washington, DC", "Washington", "DC"),
    ("New York, New York", "New York", "NY"),
])
def test_the_first_of_two_regions_is_the_city(text, city, region):
    """A place sits in one region, so a string naming two puts the city first."""
    result = parse(text)
    assert (result["city"], result["region"]) == (city, region)


def test_a_lone_region_name_stays_a_region():
    result = parse("Georgia, US")
    assert result["region"] == "GA"
    assert result["city"] is None


# ── the formats already in the database ──────────────────────────────────────

@pytest.mark.parametrize("text,expected", [
    ("Vancouver, British Columbia, Canada", "Vancouver, BC, Canada"),
    ("Vancouver,British Columbia,Canada", "Vancouver, BC, Canada"),
    ("Vancouver, British Columbia , Canada", "Vancouver, BC, Canada"),
    ("Greater Vancouver Metropolitan Area", "Vancouver, BC, Canada"),
    ("British Columbia, Canada", "BC, Canada"),
    ("Québec, Quebec, Canada", "Québec, QC, Canada"),
    ("Saint-Jean-sur-Richelieu, Quebec, Canada",
     "Saint-Jean-sur-Richelieu, QC, Canada"),
])
def test_database_formats(text, expected):
    assert canonical(text) == expected


def test_a_bare_dash_inside_a_city_name_is_not_a_separator():
    assert parse("Wilkes-Barre, PA")["city"] == "Wilkes-Barre"


def test_the_extra_location_count_is_kept_apart():
    result = parse("Vancouver, British Columbia, Canada + 21 More")
    assert result["alt"] == 21
    assert result["city"] == "Vancouver"


# ── arrangement and junk ─────────────────────────────────────────────────────

@pytest.mark.parametrize("text,arrangement", [
    ("UK, Remote", "remote"),
    ("Remote - US", "remote"),
    ("Virginia - Washington DC Metro - Remote", "remote"),
    ("Toronto, Ontario, Canada | Hybrid", "hybrid"),
])
def test_arrangement_is_lifted_out(text, arrangement):
    assert parse(text)["arrangement"] == arrangement


@pytest.mark.parametrize("text", ["6 Locations", "2 Locations", "N/A", "-", "", None])
def test_a_count_or_junk_carries_no_place(text):
    result = parse(text)
    assert result["city"] is None
    assert result["country"] is None


def test_the_text_joiner_rejoins_a_split_city_name():
    """A Workday URL segment splits one city name across tokens."""
    assert canonical("US, CA, Santa, Clara", text_joiner=" ") == \
        "Santa Clara, CA, United States"


# ── rejoining dash-split pieces ──────────────────────────────────────────────

@pytest.mark.parametrize("pieces,expected", [
    (["New", "York", "New", "York"], ["New York", "New York"]),
    (["United", "Kingdom", "London"], ["United Kingdom", "London"]),
    (["Costa", "Rica"], ["Costa Rica"]),
    (["British", "Columbia", "Vancouver"], ["British Columbia", "Vancouver"]),
    (["US", "CA", "Santa", "Clara"], ["US", "CA", "Santa", "Clara"]),
    (["Germany", "Munich"], ["Germany", "Munich"]),
])
def test_group_pieces(pieces, expected):
    from backend.analyzer.location import group_pieces
    assert group_pieces(pieces) == expected


@pytest.mark.parametrize("path,stored,place", [
    # "New-York-New-York" would otherwise read as one city, "New York New York".
    ("/job/New-York-New-York/E_JR1", "New York, NY, United States",
     ("US", "NY", "new york")),
    ("/job/United-Kingdom-London/E_JR2", "London, United Kingdom",
     ("GB", None, "london")),
    ("/job/Costa-Rica/E_JR3", "Costa Rica", ("CR", None, None)),
    ("/job/British-Columbia-Vancouver/E_JR7", "Vancouver, BC, Canada",
     ("CA", "BC", "vancouver")),
])
def test_workday_path_fallback_rejoins_names(path, stored, place):
    """A count carries no place, so the primary site comes from the URL.

    That segment is the one case where `location` is not the board's own words:
    the URL holds the place in pieces and nowhere else does the board write it.
    """
    from backend.analyzer.location import _places_of
    from backend.scraper.ats.workday import _board_location_of
    text = _board_location_of({"locationsText": "2 Locations", "externalPath": path})
    assert text == stored
    assert _places_of([text]) == [place]


@pytest.mark.parametrize("text,expected", [
    ("Saudi Arabia, Riyadh", "Riyadh, Saudi Arabia"),
    ("Morocco, Casablanca", "Casablanca, Morocco"),
    # some tenants write the three-letter form
    ("VNM, Da Nang", "Da Nang, Vietnam"),
    ("POL", "Poland"),
    # "Dockline" is the building, not part of the city; an unknown trailing
    # token is dropped rather than glued onto the city name.
    ("IRL, Dublin, Dockline", "Dublin, Ireland"),
])
def test_countries_seen_on_live_boards(text, expected):
    assert canonical(text) == expected


@pytest.mark.parametrize("text", ["USAVAReston", "USA Remote"])
def test_a_run_together_value_is_returned_as_written(text):
    """Some Workday URL segments carry no separator at all. Splitting them
    would be a guess, so the board's own text is kept."""
    assert canonical(text) == text
    assert parse(text)["country"] is None


# ── the Workday handler uses all of it ───────────────────────────────────────

@pytest.mark.parametrize("posting,stored,place", [
    # The board's own text is stored, whatever order the tenant writes it in.
    ({"locationsText": "US, CA, Santa Clara", "externalPath": "/job/x/y"},
     "US, CA, Santa Clara", ("US", "CA", "santa clara")),
    ({"locationsText": "California - San Francisco", "externalPath": "/job/x/y"},
     "California - San Francisco", ("US", "CA", "san francisco")),
    ({"locationsText": "USA.VA.Reston", "externalPath": "/job/x/y"},
     "USA.VA.Reston", ("US", "VA", "reston")),
    # a count is not a place, so the URL supplies the primary site
    ({"locationsText": "2 Locations", "externalPath": "/job/Germany-Munich/E_JR3"},
     "Munich, Germany", ("DE", None, "munich")),
    ({"locationsText": None, "externalPath": None}, None, None),
])
def test_workday_keeps_the_board_text(posting, stored, place):
    """Workday must not rewrite `location`; the canonical form lives in the
    parsed columns alone, as it does for every other handler. The end-to-end
    shape of this is in `test_ats_location_fields.py`, over a recorded response.
    """
    from backend.analyzer.location import _places_of
    from backend.scraper.ats.workday import _board_location_of
    text = _board_location_of(posting)
    assert text == stored
    assert _places_of([t for t in [text] if t]) == ([place] if place else [])


# ── review findings on PR #10 ────────────────────────────────────────────────

def test_a_sibling_never_files_a_place_in_the_wrong_country():
    """The hint may only settle a code the hinted country actually owns.

    Applying it without that check once filed San Francisco under Canada,
    because Vancouver was the only sibling and "CA" then read as the country.
    The gazetteer settles it the other way now - San Francisco is a city in
    California and in no province - so both places resolve, each in its own
    country.
    """
    from backend.analyzer.location import _places_of
    assert _places_of(["Vancouver, BC", "San Francisco, CA"]) == [
        ("CA", "BC", "vancouver"), ("US", "CA", "san francisco")]
    # the US sibling still settles it, because CA is a US region code
    assert _places_of(["Miami, FL", "San Francisco, CA"]) == [
        ("US", "FL", "miami"), ("US", "CA", "san francisco")]


@pytest.mark.parametrize("text,country,region", [
    ("Tbilisi, Georgia", "GE", None),   # the country, from the city beside it
    ("Batumi, Georgia", "GE", None),
    ("Atlanta, Georgia", "US", "GA"),   # the state, which is what boards mean
    ("Atlanta, Georgia, United States", "US", "GA"),
    ("Georgia, US", "US", "GA"),
    ("Georgia", "US", "GA"),            # bare, and still the state
    ("Atlanta, GA", "US", "GA"),        # the code form is unaffected
])
def test_georgia_is_read_from_the_city_beside_it(text, country, region):
    """Georgia is both a country and a US state, and both readings are ordinary
    on a job board. The state is what these boards mean nearly every time, so it
    is the default; a city only Georgia the country has - Tbilisi, Batumi,
    Kutaisi - is what moves the reading, the same way a city settles "CA"."""
    result = parse(text)
    assert (result["country"], result["region"]) == (country, region)
    assert result["ambiguous"] is False


def test_a_us_sibling_settles_georgia():
    from backend.analyzer.location import _places_of
    assert _places_of(["Miami, FL", "Atlanta, Georgia"]) == [
        ("US", "FL", "miami"), ("US", "GA", "atlanta")]


@pytest.mark.parametrize("text,expected", [
    ("San Francisco, CA; New York, NY", [("US", "CA", "san francisco"),
                                         ("US", "NY", "new york")]),
    ("Vancouver, BC; Toronto, ON", [("CA", "BC", "vancouver"), ("CA", "ON", "toronto")]),
])
def test_a_semicolon_separates_places_not_the_parts_of_one(text, expected):
    """Greenhouse writes several places into one field. Treating the semicolon
    as an inner separator merged three cities into one."""
    from backend.analyzer.location import _places_of
    assert sorted(_places_of([text])) == sorted(expected)


@pytest.mark.parametrize("text", [123, 1.5, ["Vancouver"], {"city": "x"}, object()])
def test_a_non_string_carries_no_place_and_does_not_raise(text):
    """A parser that raises on its input is a trap for every caller."""
    result = parse(text)
    assert result["city"] is None and result["country"] is None


@pytest.mark.parametrize("text,arrangement", [
    ("Fully Remote", "remote"),
    ("Anywhere", "remote"),
    ("Global", "remote"),
    ("Remote First", "remote"),
])
def test_a_written_out_arrangement_is_not_a_city(text, arrangement):
    """These reached the facet menu as cities named "Fully Remote"."""
    result = parse(text)
    assert result["city"] is None
    assert result["arrangement"] == arrangement


def test_a_metro_alias_is_not_a_city():
    assert parse("SF Bay Area")["city"] == "San Francisco"


@pytest.mark.parametrize("text,city,country", [
    ("Bengaluru, Karnataka, India", "Bengaluru", "IN"),
    ("Sao Paulo, Sao Paulo, Brazil", "Sao Paulo", "BR"),
])
def test_a_region_outside_the_gazetteer_is_dropped_not_glued_to_the_city(
        text, city, country):
    """The city was becoming "Bengaluru, Karnataka"."""
    result = parse(text)
    assert (result["city"], result["country"]) == (city, country)


def test_a_city_too_long_for_the_index_is_cut_not_dropped():
    """The column is indexed, and Postgres refuses an oversized btree entry, so
    an absurd value would fail on insert rather than on read. It is cut to the
    limit rather than refused: the country and region it names are still worth
    filtering on, and a job with a truncated city still answers its country."""
    from backend.analyzer.location import MAX_CITY, MAX_PART, _place_of
    assert MAX_CITY == MAX_PART == 120
    country, region, city = _place_of("%s, Ontario, Canada" % ("x" * (MAX_CITY + 50)))
    assert (country, region) == ("CA", "ON")
    assert len(city) == MAX_CITY
