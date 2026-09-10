"""The location parser against a corpus of real board strings.

`fixtures/location_corpus.csv` is every distinct `jobs.location` value in the
live database with its count and one example source - 642 strings written by
Workday, Greenhouse, Ashby, LinkedIn, Jobright, JobSpy and hand entry.
`fixtures/location_golden.csv` is what the parser makes of each of them.

The golden file is not a specification: it is a photograph. Its job is to turn
any change to `analyzer/location.py` into a reviewable diff over real inputs
instead of a silent shift in what the feed's Location filter answers. Change the
parser, look at the diff, and regenerate it deliberately:

    python -m backend.tests.fixtures.generate_location_golden

`test_the_traps` is the specification. Every case in it is a reading the parser
must get right, and no regeneration can paper over one of them.
"""
import csv
import pathlib

import pytest

from backend.analyzer.location import (
    MAX_PART,
    _places_of,
    apply_location_to_job,
    parse,
    split_places,
)
from backend.tests.fixtures.generate_location_golden import FIELDS, golden_row

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def _rows(name: str) -> list:
    with (FIXTURES / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


CORPUS = _rows("location_corpus.csv")
GOLDEN = _rows("location_golden.csv")


# ── the corpus itself ────────────────────────────────────────────────────────

def test_the_corpus_and_the_golden_file_cover_the_same_strings():
    assert [row["raw"] for row in CORPUS] == [row["raw"] for row in GOLDEN]
    assert len(CORPUS) > 500, "the corpus is the whole location column, not a sample"


def test_the_parser_still_reads_the_corpus_the_way_the_golden_file_records():
    """Any drift shows up here as a diff over real strings, one row at a time."""
    wrong = [(row["raw"], {k: row[k] for k in FIELDS}, golden_row(row["raw"]))
             for row in GOLDEN if golden_row(row["raw"]) != row]
    assert not wrong, (
        "%d corpus strings parse differently than the golden file records. "
        "If the change is intended, regenerate it with "
        "`python -m backend.tests.fixtures.generate_location_golden` and review "
        "the diff. First three: %r" % (len(wrong), wrong[:3]))


def test_the_corpus_never_produces_an_over_long_part():
    """`loc_city` and `loc_region` are indexed columns."""
    for row in GOLDEN:
        assert len(row["city"]) <= MAX_PART
        assert len(row["region"]) <= MAX_PART


def test_the_corpus_resolves_at_least_as_much_as_the_pull_request_did():
    """Coverage is a floor, not a target. The reviewed version reached country
    517, region 449, arrangement 10 and left 62 strings unread; the gazetteers
    took the unread ones down to 2 ("Canada, NC" and "New York, New York, CA",
    both genuinely unreadable). No change may fall back below these."""
    resolved = {field: sum(1 for row in GOLDEN if row[field]) for field in FIELDS}
    assert resolved["country"] >= 617
    assert resolved["region"] >= 579
    assert resolved["arrangement"] >= 10
    assert sum(1 for row in GOLDEN if row["ambiguous"]) <= 2


# ── the traps: the readings that have to be right ────────────────────────────

# (input, country, region, city). `...` means "whatever, but do not assert it".
TRAPS = [
    # the CA collision - the reason the module exists
    ("US, CA, Santa Clara", "US", "CA", "Santa Clara"),
    ("CA, BC, Vancouver", "CA", "BC", "Vancouver"),
    ("California - San Francisco", "US", "CA", "San Francisco"),
    # the gazetteers: a city in only one of California and Canada settles "CA"
    ("San Francisco, CA", "US", "CA", "San Francisco"),
    ("Los Angeles, CA", "US", "CA", "Los Angeles"),
    ("Palo Alto, CA", "US", "CA", "Palo Alto"),
    ("Marina del Rey, CA", "US", "CA", "Marina del Rey"),
    ("San Francisco County, CA", "US", "CA", "San Francisco"),
    ("Los Angeles County, CA", "US", "CA", "Los Angeles"),
    ("Toronto, CA", "CA", "ON", "Toronto"),
    ("Burnaby, CA", "CA", "BC", "Burnaby"),
    ("Vancouver, CA", "CA", "BC", "Vancouver"),
    # in both countries, or in neither: still refused
    ("Richmond, CA", None, None, "Richmond"),
    ("Windsor, CA", None, None, "Windsor"),
    ("Ontario, CA", None, None, "Ontario"),
    ("CA", None, None, None),
    # the bare-city table, for a string that is nothing but a city
    ("San Francisco", "US", "CA", "San Francisco"),
    ("Seattle", "US", "WA", "Seattle"),
    ("Washington DC", "US", "DC", "Washington"),
    ("Frankfurt Rhine-Main Metropolitan Area", "DE", None, "Frankfurt"),
    ("Bangalore", "IN", None, "Bengaluru"),
    ("London", "GB", None, "London"),
    ("Tokyo", "JP", None, "Tokyo"),
    ("Atlanta, GA", "US", "GA", "Atlanta"),          # not Gabon
    ("Wilmington, DE", "US", "DE", "Wilmington"),    # not Germany
    ("Indianapolis, IN", "US", "IN", "Indianapolis"),  # not India
    ("New Orleans, LA", "US", "LA", "New Orleans"),  # not Laos
    # a country already fixed forbids the US-state reading
    ("Canada, NC", "CA", None, None),
    # city and region share a name
    ("New York, NY", "US", "NY", "New York"),
    ("Washington, DC", "US", "DC", "Washington"),
    ("Washington, D.C.", "US", "DC", "Washington"),
    ("Ontario, Canada", "CA", "ON", None),
    # Georgia: the state unless the city says otherwise
    ("Atlanta, Georgia", "US", "GA", "Atlanta"),
    ("Georgia, United States", "US", "GA", None),
    ("Georgia", "US", "GA", None),
    ("Tbilisi, Georgia", "GE", None, "Tbilisi"),
    ("Batumi, Georgia", "GE", None, "Batumi"),
    # three parts, foreign: city, region, country
    ("Bengaluru, Karnataka, India", "IN", "Karnataka", "Bengaluru"),
    ("Frankfurt, Hesse, Germany", "DE", "Hesse", "Frankfurt"),
    ("Munich, Bavaria, Germany", "DE", "Bavaria", "Munich"),
    # a region written the long way
    ("Washington State", "US", "WA", None),
    ("Florida State", "US", "FL", None),
    ("New York State", "US", "NY", None),
    # metros and areas: a city or nothing, never a junk key
    ("Bay Area", "US", "CA", "San Francisco"),
    ("SF Bay Area", "US", "CA", "San Francisco"),
    ("Greater Toronto Area", "CA", "ON", "Toronto"),
    ("Greater Vancouver Metropolitan Area", "CA", "BC", "Vancouver"),
    ("NYC Metro Area", "US", "NY", "New York"),
    ("DMV", "US", "DC", "Washington"),
    ("Tri-State Area", "US", None, None),
    ("Greater Indianapolis", None, None, "Indianapolis"),
    ("Redwood City Office", None, None, "Redwood City"),
    # hyphen triples
    ("US-CA-San Jose", "US", "CA", "San Jose"),
    ("US-TX-Austin", "US", "TX", "Austin"),
    ("United States-California-Irvine", "US", "CA", "Irvine"),
    # a hyphen inside one name is not a separator
    ("Wilkes-Barre, PA", "US", "PA", "Wilkes-Barre"),
    ("Saint-Jean-sur-Richelieu, Quebec, Canada", "CA", "QC",
     "Saint-Jean-sur-Richelieu"),
    ("Mörfelden-Walldorf, Hesse, Germany", "DE", "Hesse", "Mörfelden-Walldorf"),
    # remote, with no city invented for it
    ("Fully Remote", None, None, None),
    ("Remote - Anywhere", None, None, None),
    ("Anywhere", None, None, None),
    ("Work from home", None, None, None),
    ("WFH", None, None, None),
    ("Remote, US", "US", None, None),
    # a list of places resolves to the first of them
    ("New York; London; Tokyo", "US", "NY", "New York"),
    ("Boston; London; Tokyo", "US", "MA", "Boston"),
    ("Bellevue, WA / San Francisco, CA", "US", "WA", "Bellevue"),
]


@pytest.mark.parametrize("text,country,region,city", TRAPS)
def test_the_traps(text, country, region, city):
    result = parse(text)
    assert (result["country"], result["region"], result["city"]) == (country, region, city)


@pytest.mark.parametrize("text,arrangement", [
    ("Fully Remote", "remote"),
    ("Remote - Anywhere", "remote"),
    ("Anywhere", "remote"),
    ("Work from home", "remote"),
    ("WFH", "remote"),
    ("100% Remote", "remote"),
    ("New York, NY (Hybrid)", "hybrid"),
    ("Toronto, ON | Hybrid", "hybrid"),
    ("San Francisco / Palo Alto (In-Office)", "onsite"),
])
def test_the_arrangement_survives_the_place(text, arrangement):
    assert parse(text)["arrangement"] == arrangement


# ── a list of places is a list of answers ────────────────────────────────────

def test_a_semicolon_list_is_several_places_not_one_city():
    assert split_places("New York; London; Tokyo") == ["New York", "London", "Tokyo"]
    places = _places_of(["New York; London; Tokyo"])
    assert ("US", "NY", "new york") in places
    assert ("GB", None, "london") in places
    assert ("JP", None, "tokyo") in places


@pytest.mark.parametrize("text", [
    "New York, NY | London | Tokyo",
    "New York, NY • London • Tokyo",
    "New York, NY / London / Tokyo",
])
def test_the_other_list_separators_split_the_same_way(text):
    assert len(_places_of([text])) == 3


def test_a_list_that_names_one_place_and_an_arrangement_stays_one_place():
    assert len(_places_of(["Toronto, Ontario, Canada | Hybrid"])) == 1


# ── a held-out code and the rest of the posting ──────────────────────────────

def test_a_second_place_settles_a_held_out_code():
    """"San Francisco, CA" beside "Miami, FL" is California."""
    places = _places_of(["Miami, FL", "San Francisco, CA"])
    assert ("US", "CA", "san francisco") in places


def test_a_canadian_place_does_not_pull_a_us_city_into_canada():
    """The bug this test exists for: the single-country fallback read the "CA"
    of "San Francisco, CA" as Canada because Vancouver had already fixed it."""
    places = _places_of(["Vancouver, BC", "San Francisco, CA"])
    assert ("CA", "BC", "vancouver") in places
    assert not [p for p in places if p[0] == "CA" and p[2] == "san francisco"]


def test_a_code_that_fits_two_candidate_countries_stays_unread():
    places = _places_of(["Vancouver, BC", "Miami, FL", "San Francisco, CA"])
    assert ("US", "CA", "san francisco") in places, "FL fixes the US reading"


# ── bad input ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("value", [None, 17, 3.5, True, b"x", ["Berlin"], {"a": 1}])
def test_parse_never_raises_on_a_non_string(value):
    assert parse(value) == {"city": None, "region": None, "country": None,
                            "arrangement": None, "alt": 0, "ambiguous": False,
                            "assumed": None, "note": None}


def test_a_whole_address_is_cut_to_what_the_index_holds():
    class FakeJob:
        loc_country = loc_region = loc_city = None
        locations = []

    job = FakeJob()
    job.locations = []
    job.location = ", ".join(["Suite %d Long Building Name" % n for n in range(20)])
    apply_location_to_job(job)
    assert len(job.loc_city or "") <= MAX_PART
