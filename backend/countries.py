"""The country vocabulary for Indeed searches, read from the jobspy library.

jobspy picks the Indeed domain and the `indeed-co` API header from the
`country_indeed` string it receives, and it accepts only the names its own
`Country` enum knows. The project therefore keeps no country list of its own:
every name here comes from `jobspy.model.Country` at call time, so a library
upgrade adds or removes countries without a code change.
"""

from functools import lru_cache
from typing import Optional

# The value a search falls back to when nothing says where to look. It is a
# jobspy alias, so `Country.from_string()` always accepts it.
DEFAULT_COUNTRY = "usa"

# Two enum members are routing values for other boards, not places a user picks:
# US_CANADA belongs to ZipRecruiter and WORLDWIDE to LinkedIn. Neither selects an
# Indeed domain, so both stay out of the list and out of validation.
_INTERNAL_MEMBERS = frozenset({"US_CANADA", "WORLDWIDE"})


def _aliases(member) -> list:
    """The spellings `Country.from_string()` accepts for one enum member.

    jobspy stores each member as a tuple whose first item is a comma-separated
    alias string. The shape is checked, not assumed: on a plain-string value
    `value[0]` would be the first letter, and "usa" would silently become "u".
    """
    value = member.value
    raw = value[0] if isinstance(value, (tuple, list)) and value else value
    return [a.strip() for a in str(raw).split(",") if a.strip()]


@lru_cache(maxsize=1)
def supported_countries() -> tuple:
    """((value, label), ...) for every country Indeed supports, sorted by label.

    `value` is the first alias, which is what the project stores and hands back
    to jobspy. `label` is the longest alias, which reads as the full name of the
    country ("usa" -> "United States", "uk" -> "United Kingdom").
    """
    from jobspy.model import Country

    rows = [
        (_aliases(member)[0], max(_aliases(member), key=len).title())
        for member in Country
        if member.name not in _INTERNAL_MEMBERS
    ]
    return tuple(sorted(rows, key=lambda row: row[1]))


def normalize_country(value) -> Optional[str]:
    """The stored form of a country name, or None when jobspy does not know it.

    The match is case-insensitive and accepts every alias jobspy accepts, so
    "Canada", "canada", "US" and "United States" all resolve.
    """
    from jobspy.model import Country

    try:
        member = Country.from_string(str(value or ""))
    except (ValueError, AttributeError):
        return None
    if member.name in _INTERNAL_MEMBERS:
        return None
    return _aliases(member)[0]


def indeed_host(value) -> Optional[str]:
    """The Indeed host of a country ("usa" -> "www.indeed.com", "uk" -> "uk.indeed.com"), or None.

    jobspy's own Indeed scraper builds its base URL from the same property, so a
    search URL built here reaches the domain a keyword search reaches.
    """
    from jobspy.model import Country

    name = normalize_country(value)
    if name is None:
        return None
    return f"{Country.from_string(name).indeed_domain_value[0]}.indeed.com"


def country_from_location(location) -> str:
    """Read a country out of free location text, or fall back to DEFAULT_COUNTRY.

    `split_country_suffix()` is the one parser: it reads the last comma-separated
    segment ("Toronto, Canada" -> canada), and text with no comma is that segment
    ("Canada" -> canada). Text that names no country gives DEFAULT_COUNTRY.

    This is a one-time guess for the migration backfill, not a runtime substitute
    for the stored field. A caller that must tell a read from a guess calls
    `split_country_suffix()` itself and looks at the second item.
    """
    return split_country_suffix(location)[1] or DEFAULT_COUNTRY


def split_country_suffix(location) -> tuple:
    """(place, country) — free location text without its country, and that country.

    `normalize_country()` decides what a country segment is, so "Toronto, ON"
    keeps its region and "Toronto, Canada" gives ("Toronto", "canada"). Text that
    is only a country name gives an empty place: a country carries no city or
    region. Text with no country segment comes back unchanged, with None.
    """
    text = str(location or "").strip().strip(",").strip()
    if not text:
        return "", None
    head, _, tail = text.rpartition(",")
    name = normalize_country(tail.strip())
    if name is None:
        return text, None
    return head.strip().strip(",").strip(), name


def compose_location(location, country) -> str:
    """The one location string every jobspy board receives.

    `location` holds a city or a region, and `country` is the single country
    source, so the country segment of `location` is dropped and the label of
    `country` replaces it. Indeed reads the country from `country_indeed` only,
    while LinkedIn, ZipRecruiter and Google read no country at all — one string
    with the country spelled out satisfies all four.

    An empty place gives the label alone, because "Canada" is a valid query and
    ", Canada" is not.

    Text that names no place keeps the country too. There is no reliable test for
    "not a place", and "Remote" was measured on both boards with country "usa":

    | board    | "Remote"                         | "Remote, United States"      |
    |----------|----------------------------------|------------------------------|
    | indeed   | 20 rows, all "Remote, US"        | 20 rows, all "Remote, US"    |
    | linkedin | 20 rows in Taiwan, Japan, India, | 20 rows, all in one Oregon   |
    |          | Canada, Ireland and 5 US states  | county (it reads Remote, OR) |

    So the country costs Indeed nothing, and on LinkedIn neither spelling is a
    remote search — but only the composed one honours the country the user
    picked. `is_remote` is the field that works: an empty location with
    `is_remote` on returned 40 US-wide remote rows across both boards. The forms
    say so.
    """
    place, _ = split_country_suffix(location)
    labels = dict(supported_countries())
    # A stored country that jobspy no longer knows falls back the same way
    # `country_indeed` does. The `if not label` branch guards the day jobspy
    # drops DEFAULT_COUNTRY too: the caller gets the place text, never a crash.
    label = labels.get(normalize_country(country) or "") or labels.get(DEFAULT_COUNTRY)
    if not label:
        return place
    return f"{place}, {label}" if place else label
