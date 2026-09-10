"""Order-agnostic parsing of a job board's location string.

Boards disagree on both order and separator, and one board disagrees with
itself: Workday's `locationsText` is per-tenant, so the same field carries
"US, CA, Santa Clara", "Ireland - Dublin", "California - San Francisco" and
"USA.VA.Reston". Reversing the order is therefore not a fix. This module
classifies each token by what it is and then emits one canonical order.

Two facts drive the rules:

1. US state codes and Canadian province codes do not overlap at all, so a
   two-letter region code identifies its own country with no ambiguity.
2. Twenty-six ISO country codes collide with a US state code - CA is Canada
   and California, but so are DE, GA, IN, LA, MD, ME, MT, NE, PA and VA. A
   blanket "two letters means a country" rule turns "Atlanta, GA" into Gabon.

So a two-letter token is read as a region unless it cannot be one. `CA` is
resolved only from the rest of the string; when the string does not settle it,
the parse is marked ambiguous and the caller keeps the board's own text.
"""
import re
import unicodedata

CA_REGIONS = {
    "alberta": "AB", "british columbia": "BC", "manitoba": "MB",
    "new brunswick": "NB", "newfoundland and labrador": "NL",
    "newfoundland": "NL", "nova scotia": "NS", "ontario": "ON",
    "prince edward island": "PE", "quebec": "QC", "saskatchewan": "SK",
    "northwest territories": "NT", "nunavut": "NU", "yukon": "YT",
}
US_REGIONS = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE",
    "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ",
    "new mexico": "NM", "new york": "NY", "north carolina": "NC",
    "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR",
    "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
    "district of columbia": "DC", "d.c.": "DC", "washington dc": "DC",
    "washington d.c.": "DC",
}
REGION_NAMES = {"CA": CA_REGIONS, "US": US_REGIONS}
REGION_CODES = {cc: set(names.values()) for cc, names in REGION_NAMES.items()}
ALL_REGION_CODES = REGION_CODES["CA"] | REGION_CODES["US"]

COUNTRY_NAMES = {
    "canada": "CA", "united states": "US", "united states of america": "US",
    "usa": "US", "u.s.": "US", "u.s.a.": "US", "america": "US",
    "united kingdom": "GB", "uk": "GB", "great britain": "GB",
    "england": "GB", "scotland": "GB", "wales": "GB",
    "northern ireland": "GB", "ireland": "IE", "germany": "DE",
    "france": "FR", "spain": "ES", "portugal": "PT", "netherlands": "NL",
    "belgium": "BE", "poland": "PL", "ukraine": "UA", "romania": "RO",
    "czechia": "CZ", "czech republic": "CZ", "switzerland": "CH",
    "austria": "AT", "sweden": "SE", "norway": "NO", "denmark": "DK",
    "finland": "FI", "italy": "IT", "greece": "GR", "india": "IN",
    "israel": "IL", "singapore": "SG", "japan": "JP", "south korea": "KR",
    "korea": "KR", "china": "CN", "taiwan": "TW", "australia": "AU",
    "new zealand": "NZ", "mexico": "MX", "brazil": "BR", "argentina": "AR",
    "costa rica": "CR", "colombia": "CO", "chile": "CL", "peru": "PE",
    "south africa": "ZA", "egypt": "EG", "turkey": "TR",
    "united arab emirates": "AE", "philippines": "PH", "malaysia": "MY",
    "indonesia": "ID", "vietnam": "VN", "thailand": "TH",
    "saudi arabia": "SA", "morocco": "MA", "nigeria": "NG", "kenya": "KE",
    "pakistan": "PK", "bangladesh": "BD", "hungary": "HU", "bulgaria": "BG",
    "serbia": "RS", "croatia": "HR", "lithuania": "LT", "latvia": "LV",
    "estonia": "EE", "slovakia": "SK", "slovenia": "SI", "luxembourg": "LU",
    "iceland": "IS", "hong kong": "HK", "qatar": "QA", "kuwait": "KW",
    "jordan": "JO", "uruguay": "UY", "ecuador": "EC", "panama": "PA",
    "guatemala": "GT", "dominican republic": "DO", "puerto rico": "PR",
    "russia": "RU", "belarus": "BY", "kazakhstan": "KZ", "armenia": "AM",
    "georgia (country)": "GE", "cyprus": "CY", "malta": "MT",
}
# Two-letter codes that are also a region code, so they may not be read as a
# country until the rest of the string settles it.
AMBIGUOUS_CODES = {
    "CA": "CA", "DE": "DE", "IN": "IN", "LA": "LA", "MD": "MD", "ME": "ME",
    "MT": "MT", "NE": "NE", "PA": "PA", "AL": "AL", "AR": "AR", "CO": "CO",
    "GA": "GA", "MO": "MO", "MS": "MS", "SC": "SC", "SD": "SD", "TN": "TN",
    "VA": "VA", "ID": "ID", "IL": "IL", "MN": "MN", "KY": "KY", "NC": "NC",
    "MA": "MA", "SK": "SK", "NU": "NU", "PE": "PE",
}
# Two-letter codes that are no region's code, so they are safe to read as a
# country wherever they appear.
SAFE_COUNTRY_CODES = {
    "US": "US", "GB": "GB", "FR": "FR", "JP": "JP", "UA": "UA", "CN": "CN",
    "BR": "BR", "MX": "MX", "AU": "AU", "NZ": "NZ", "ZA": "ZA", "SG": "SG",
    "KR": "KR", "TW": "TW", "PH": "PH", "MY": "MY", "VN": "VN", "TH": "TH",
    "AE": "AE", "TR": "TR", "EG": "EG", "PL": "PL", "RO": "RO", "CZ": "CZ",
    "CH": "CH", "AT": "AT", "SE": "SE", "NO": "NO", "DK": "DK", "FI": "FI",
    "IT": "IT", "GR": "GR", "ES": "ES", "PT": "PT", "BE": "BE", "IE": "IE",
    "CR": "CR", "CL": "CL",
}
# Workday tenants also write the three-letter form ("VNM, Da Nang", "POL").
ISO3 = {
    "CAN": "CA", "USA": "US", "GBR": "GB", "DEU": "DE", "IND": "IN",
    "AUS": "AU", "MEX": "MX", "BRA": "BR", "FRA": "FR", "JPN": "JP",
    "IRL": "IE", "VNM": "VN", "POL": "PL", "ESP": "ES", "PRT": "PT",
    "NLD": "NL", "BEL": "BE", "CHE": "CH", "AUT": "AT", "SWE": "SE",
    "NOR": "NO", "DNK": "DK", "FIN": "FI", "ITA": "IT", "GRC": "GR",
    "CZE": "CZ", "ROU": "RO", "HUN": "HU", "BGR": "BG", "UKR": "UA",
    "ISR": "IL", "SGP": "SG", "KOR": "KR", "CHN": "CN", "TWN": "TW",
    "NZL": "NZ", "ZAF": "ZA", "EGY": "EG", "TUR": "TR", "ARE": "AE",
    "PHL": "PH", "MYS": "MY", "THA": "TH", "IDN": "ID", "ARG": "AR",
    "CHL": "CL", "COL": "CO", "PER": "PE", "CRI": "CR", "SAU": "SA",
    "MAR": "MA", "NGA": "NG", "KEN": "KE", "PAK": "PK", "BGD": "BD",
    "HKG": "HK", "QAT": "QA", "LUX": "LU", "LTU": "LT", "LVA": "LV",
    "EST": "EE", "SVK": "SK", "SVN": "SI", "HRV": "HR", "SRB": "RS",
}

ARRANGEMENT_WORDS = {"remote": "remote", "hybrid": "hybrid",
                     "on-site": "onsite", "onsite": "onsite",
                     "in office": "onsite", "in-office": "onsite",
                     "work from home": "remote", "wfh": "remote",
                     # A whole-token phrase, never a place: "Fully Remote" and
                     # "Remote - Anywhere" have to leave the city empty, or the
                     # feed grows a city called "Anywhere".
                     "fully remote": "remote", "100% remote": "remote",
                     "anywhere": "remote", "remote anywhere": "remote",
                     "anywhere in the world": "remote", "worldwide": "remote"}

JUNK = {"", "-", "--", "n/a", "na", "none", "unknown", "tbd", "various",
        "multiple", "locations", "multiple locations", "various locations",
        # office labels boards append in brackets: "New York, NY (HQ)"
        "hq", "headquarters", "head office", "office", "corporate", "main office",
        # a region of the world, not a place: "Americas-United States-Boston"
        "americas", "emea", "apac", "latam", "north america", "global",
        "nationwide"}

# "6 Locations" is a count, not a place.
COUNT_ONLY = re.compile(r"^\d+\s+locations?$", re.I)
_ALT = re.compile(r"\s*\+\s*(\d+)\s+more\s*$", re.I)
# A separator is a comma, a spaced dash, a middle dot, a bullet, a pipe, a
# semicolon, or a dot inside a word ("USA.VA.Reston"). A bare dash is not: it
# lives inside "Saint-Jean" and "Wilkes-Barre". The dot rule needs two letters
# on one side of it, so an initialism ("U.S.", "Washington, D.C.") stays whole.
_SPLIT = re.compile(r"\s*[,;·•|()]\s*|\s+[-–—]\s+"
                    r"|(?<=\w\w)\.(?=\w)|(?<=\w)\.(?=\w\w)")
# One string, several places: "New York; London; Tokyo" is three postings'
# worth of filter answers, not a city called "New York, London, Tokyo". The
# "or" is deliberately case-sensitive: "OR" is Oregon, "or" is a separator.
_LIST_SPLIT = re.compile(r"\s*[;|·•]\s*|\s*/\s*|\s+or\s+")
_METRO_TAIL = re.compile(r"\s+(metropolitan\s+area|metro(politan)?\s+area|area)$", re.I)
# A site label a board appends to a city: "Redwood City Office", "Seattle Campus".
_OFFICE_TAIL = re.compile(r"\s+(office|campus|hq|headquarters|site)$", re.I)
# "Washington State", "Florida State" - the region, written the long way.
_STATE_TAIL = re.compile(r"\s+state$", re.I)
# A postcode or a building code carries no place and must not reach a city.
_CODE_ONLY = re.compile(r"\d[\d\- ]*|[A-Z]{1,4}\d[A-Z0-9]*")

# A metro name maps to its anchor city. `None` for the city means the phrase
# names an area too wide for one city - it still answers the country filter,
# and it never becomes a junk city key ("Bay Area" read as a city "Bay").
METROS = {
    "greater vancouver": ("Vancouver", "BC", "CA"),
    "greater toronto": ("Toronto", "ON", "CA"),
    "gta": ("Toronto", "ON", "CA"),
    "greater montreal": ("Montreal", "QC", "CA"),
    "greater ottawa": ("Ottawa", "ON", "CA"),
    "greater calgary": ("Calgary", "AB", "CA"),
    "greater seattle": ("Seattle", "WA", "US"),
    "san francisco bay": ("San Francisco", "CA", "US"),
    "bay area": ("San Francisco", "CA", "US"),
    "sf bay": ("San Francisco", "CA", "US"),
    "sf bay area": ("San Francisco", "CA", "US"),
    "greater new york": ("New York", "NY", "US"),
    "new york city": ("New York", "NY", "US"),
    "nyc": ("New York", "NY", "US"),
    "nyc metro": ("New York", "NY", "US"),
    "tri-state": (None, None, "US"),
    "tri state": (None, None, "US"),
    "greater boston": ("Boston", "MA", "US"),
    "greater chicago": ("Chicago", "IL", "US"),
    "chicago metro": ("Chicago", "IL", "US"),
    "la metro": ("Los Angeles", "CA", "US"),
    "los angeles metro": ("Los Angeles", "CA", "US"),
    "twin cities": ("Minneapolis", "MN", "US"),
    "dmv": ("Washington", "DC", "US"),
    "washington dc-baltimore": ("Washington", "DC", "US"),
    "east coast": (None, None, "US"),
    "west coast": (None, None, "US"),
}

# Georgia is a country and a US state. The state is the overwhelmingly more
# common reading on these boards ("Atlanta, Georgia"), so the country wins only
# when the string also names a city that is unmistakably Georgian.
GEORGIAN_CITIES = {"tbilisi", "batumi", "kutaisi", "rustavi", "zugdidi",
                   "gori", "poti", "telavi"}

# The longest city name the indexed columns hold. `loc_city` is indexed, and a
# board occasionally writes a whole address into the field.
MAX_PART = 120

COUNTRY_LABELS = {code: name.title() for name, code in COUNTRY_NAMES.items()}
COUNTRY_LABELS.update({"CA": "Canada", "US": "United States",
                       "GB": "United Kingdom", "IE": "Ireland", "KR": "South Korea",
                       "AE": "United Arab Emirates", "CZ": "Czechia",
                       "GE": "Georgia"})

# `City, XX` with a US state code is the dominant convention on job boards, so
# an unsettled code is read as that state. CA is held out: California and Canada
# are both first-tier readings in North American postings, and a wrong country
# is the worst error a location filter can make. Extend this set, do not extend
# the assumption.
COUNTRY_FIRST_CODES = {"CA"}


def fold(text: str) -> str:
    """Lower-case, strip accents, collapse whitespace."""
    stripped = unicodedata.normalize("NFKD", text or "")
    ascii_only = stripped.encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", ascii_only).strip().lower()


def _metro_of(token: str):
    """The metro this token names, or None. Runs before anything strips it.

    "Bay Area" has to be looked up whole: dropping the "Area" tail first leaves
    "Bay", which is not a place. A two-letter token is never a metro - "LA" is
    Louisiana far more often than it is a metro label.
    """
    folded = fold(token)
    if len(folded) < 3:
        return None
    trimmed = fold(_OFFICE_TAIL.sub("", _METRO_TAIL.sub("", token.strip())))
    # "LA Metro Area" loses only its "Area" here: "LA" alone is Louisiana.
    area_only = re.sub(r"\s+area$", "", folded)
    for candidate in (folded, area_only, trimmed,
                      re.sub(r"^greater\s+", "", trimmed)):
        if candidate in METROS:
            return METROS[candidate]
    return None


def _core(token: str) -> str:
    """One token with the labels a board appends stripped off."""
    trimmed = _OFFICE_TAIL.sub("", _METRO_TAIL.sub("", token.strip())).strip()
    return trimmed or token.strip()


def _classify(token: str) -> tuple[str, object]:
    """Say what one token is, without looking at the others.

    Returns (kind, value) where kind is one of "arrangement", "country",
    "region", "metro", "ambiguous" or "text". An "ambiguous" token is a
    two-letter code that is both a region code and a country code; `_resolve`
    settles it.
    """
    metro = _metro_of(token)
    if metro:
        return "metro", metro

    token = _core(token)
    folded = fold(token)
    upper = token.strip().upper()

    if folded in ARRANGEMENT_WORDS:
        return "arrangement", ARRANGEMENT_WORDS[folded]
    if folded in COUNTRY_NAMES:
        return "country", COUNTRY_NAMES[folded]
    if upper in ISO3:
        return "country", ISO3[upper]
    for country, names in REGION_NAMES.items():
        if folded in names:
            return "region", (country, names[folded])
    # "Washington State" is the region, spelled the long way. Only a name the
    # gazetteer knows may lose its "State": "Garden State" is not one.
    without_state = fold(_STATE_TAIL.sub("", token))
    if without_state != folded:
        for country, names in REGION_NAMES.items():
            if without_state in names:
                return "region", (country, names[without_state])
    if len(upper) == 2 and upper.isalpha():
        if upper in AMBIGUOUS_CODES:
            return "ambiguous", upper
        if upper in ALL_REGION_CODES:
            country = "CA" if upper in REGION_CODES["CA"] else "US"
            return "region", (country, upper)
        if upper in SAFE_COUNTRY_CODES:
            return "country", SAFE_COUNTRY_CODES[upper]
    # "Greater Indianapolis" is Indianapolis; the qualifier is not part of the
    # name, and keeping it would split the facet in two.
    return "text", re.sub(r"^[Gg]reater\s+", "", token.strip())


def _resolve(code: str, country: str | None, region: str | None) -> tuple[str, object] | None:
    """Settle one ambiguous two-letter code from what the string already fixed.

    | already known        | reading of the code            |
    |----------------------|--------------------------------|
    | country US or CA     | the region of that country     |
    | any other country    | nothing - refuse to guess      |
    | a region, no country | the country, when it is one    |
    | nothing              | nothing - refuse to guess      |
    """
    if country in REGION_CODES and code in REGION_CODES[country]:
        return "region", (country, code)
    if country is not None:
        # "CA, BC, Vancouver": BC already fixed Canada, so CA repeats it.
        if AMBIGUOUS_CODES.get(code) == country:
            return "country", country
        return None
    if region is not None:
        # A region is already fixed, so this code cannot be a second one.
        return ("country", COUNTRY_NAMES.get(fold(code))
                or SAFE_COUNTRY_CODES.get(code)
                or AMBIGUOUS_CODES.get(code)) if code in AMBIGUOUS_CODES else None
    return None


def _empty() -> dict:
    return {"city": None, "region": None, "country": None,
            "arrangement": None, "alt": 0, "ambiguous": False,
            "assumed": None, "note": None}


def _has_place(result: dict) -> bool:
    return bool(result["country"] or result["region"] or result["city"])


def _geo_piece(piece: str) -> bool:
    """True when this dash-separated piece names a country, a region or a label.

    It is what tells "US-CA-San Jose" (three parts of one address) apart from
    "Saint-Jean-sur-Richelieu" and "Wilkes-Barre" (one name each).
    """
    folded = fold(piece)
    upper = piece.strip().upper()
    return bool(folded in COUNTRY_NAMES or upper in ISO3 or folded in JUNK
                or folded in CA_REGIONS or folded in US_REGIONS
                or (len(upper) == 2 and upper.isalpha()
                    and upper in ALL_REGION_CODES))


def _split_dashed(tokens: list) -> list:
    """Split "US-CA-San Jose" into its parts, leaving hyphenated names alone."""
    out = []
    for token in tokens:
        # "In-Office" and "Washington DC-Baltimore Area" are each one token; the
        # dash inside them joins a phrase, it does not separate two places.
        if fold(token) in ARRANGEMENT_WORDS or _metro_of(token):
            out.append(token)
            continue
        pieces = [p.strip() for p in token.split("-") if p.strip()]
        if len(pieces) > 1 and any(_geo_piece(p) for p in pieces):
            out.extend(group_pieces(pieces))
        else:
            out.append(token)
    return out


def split_places(text: str) -> list:
    """One string into the several places it names.

    Boards list places with a semicolon, a pipe, a bullet or a slash. Each of
    those is one more filter the posting has to answer, so they are kept apart
    instead of being joined into a city name no map has.
    """
    if not isinstance(text, str) or not text.strip():
        return []
    cleaned = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).strip()
    if fold(cleaned) in JUNK:
        return []
    segments = [s.strip() for s in _LIST_SPLIT.split(cleaned) if s and s.strip()]
    if len(segments) < 2:
        return [cleaned]
    carrying = [s for s in segments if _has_place(_parse_one(s))]
    return carrying or [cleaned]


def parse(text, text_joiner: str = ", ", country_hint: str = None) -> dict:
    """Read a board's location string into its parts.

    `ambiguous` is True when a two-letter code could not be settled. The caller
    should then keep the board's own text rather than publish a guess.

    `text_joiner` joins the leftover tokens that form the city. Pass " " when
    the tokens came from splitting one word-per-token string, such as a
    Workday URL segment ("US-CA-Santa-Clara" -> "Santa Clara").

    `country_hint` is a country another place on the same posting resolved to.
    It settles a held-out code: "San Francisco, CA" listed beside "Miami, FL"
    is California, since one posting does not span two countries by accident.

    A string naming several places resolves to the first of them, and the
    arrangement is read from any of them ("Toronto, ON | Hybrid"). Use
    `split_places` when every place matters.
    """
    result = _empty()
    if not isinstance(text, str) or not text.strip():
        return result

    cleaned = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).strip()

    alt = _ALT.search(cleaned)
    if alt:
        result["alt"] = int(alt.group(1))
        cleaned = _ALT.sub("", cleaned).strip()

    if COUNT_ONLY.match(cleaned) or fold(cleaned) in JUNK:
        return result

    segments = [s.strip() for s in _LIST_SPLIT.split(cleaned) if s and s.strip()]
    parsed = [_parse_one(s, text_joiner, country_hint) for s in segments]
    # The first place the list settles. A place whose code stayed unread is
    # skipped while another one in the same list can be read: "San Francisco,
    # CA | New York City, NY" answers under New York rather than nothing.
    chosen = next((p for p in parsed if _has_place(p) and not p["ambiguous"]),
                  next((p for p in parsed if _has_place(p)),
                       parsed[0] if parsed else result))
    chosen["alt"] = result["alt"]
    if chosen["arrangement"] is None:
        chosen["arrangement"] = next(
            (p["arrangement"] for p in parsed if p["arrangement"]), None)
    return chosen


def _parse_one(cleaned: str, text_joiner: str = ", ", country_hint: str = None) -> dict:
    """Read one place - one segment of `parse`'s input."""
    result = _empty()
    tokens = _split_dashed([t.strip() for t in _SPLIT.split(cleaned)
                            if t and t.strip()])
    if not tokens:
        return result

    classified = [(t, _classify(t)) for t in tokens
                  if fold(t) not in JUNK and not _CODE_ONLY.fullmatch(t.strip())]
    if not classified:
        return result

    # A place sits in one region, so a string naming two of them is really
    # "City, Region": "New York, NY" and "Washington, DC" both put the city
    # first. Every region token but the last becomes the city.
    region_slots = [i for i, (_, (k, _v)) in enumerate(classified)
                    if k in ("region", "ambiguous")]
    demote = set(region_slots[:-1]) if len(region_slots) > 1 else set()
    # An ambiguous code is never a city name, so it is never demoted.
    demote = {i for i in demote if classified[i][1][0] == "region"}

    # Pass one: everything that needs no context.
    pending = []
    text_parts = []
    metro_city = None
    region_named = None      # the region token as the board wrote it
    country_slot = -1        # where the country token sat, if there was one
    text_slots = []
    # A hint is another place named by the same posting. "San Francisco, CA"
    # beside "Miami, FL" is California, because one posting sits in one country.
    country_strong = bool(country_hint)
    if country_hint:
        result["country"] = country_hint
        result["assumed"] = "country taken from another place on the same posting"
    for index, (token, (kind, value)) in enumerate(classified):
        if index in demote:
            text_parts.append(token)
            text_slots.append(index)
            continue
        if kind == "arrangement":
            result["arrangement"] = value
        elif kind == "metro":
            city, region, country = value
            metro_city = metro_city or city
            result["region"] = result["region"] or region
            result["country"] = result["country"] or country
            country_strong = country_strong or bool(country)
        elif kind == "country":
            result["country"] = result["country"] or value
            country_slot = index
            country_strong = True
        elif kind == "region":
            country, code = value
            if not result["region"]:
                region_named = token.strip()
            result["region"] = result["region"] or code
            result["country"] = result["country"] or country
            # A region written as a two-letter code is never a city, so it
            # pins the country. A region written out in full may be a city
            # instead: "Ontario" is a province and a city in California.
            if token.strip().upper() == code:
                country_strong = True
        elif kind == "ambiguous":
            pending.append(value)
        else:
            # `value`, not `token`: the classifier hands back the name with the
            # board's labels ("Office", "Greater") already off it.
            text_parts.append(value)
            text_slots.append(index)

    # Pass two: settle the codes that needed the rest of the string.
    for code in pending:
        if code in COUNTRY_FIRST_CODES and not country_strong:
            # Nothing in the string pins the country, so CA stays unread.
            result["ambiguous"] = True
            result["note"] = "%s is both a region code and a country code" % code
            continue
        settled = _resolve(code, result["country"], result["region"])
        if (settled is None and code not in COUNTRY_FIRST_CODES
                and code in REGION_CODES["US"]
                # Only when nothing has fixed another country. "Canada, NC" is
                # not Canada's state of North Carolina.
                and result["country"] in (None, "US")):
            # "Atlanta, GA" - the US convention, not Gabon.
            settled = ("region", ("US", code))
            result["assumed"] = "%s read as a US state" % code
        if settled is None:
            result["ambiguous"] = True
            result["note"] = "%s is both a region code and a country code" % code
            continue
        kind, value = settled
        if kind == "region":
            country, region_code = value
            result["region"] = result["region"] or region_code
            result["country"] = result["country"] or country
        elif value:
            result["country"] = result["country"] or value

    # "Bengaluru, Karnataka, India": a country written last, and two names left
    # over, is city then region. The rule is held to countries whose regions the
    # gazetteer does not know - a US or Canadian region would have been read as
    # one already, and "Whippany Campus, Jefferson Park, US" is not a region.
    if (result["country"] and result["country"] not in REGION_NAMES
            and not result["region"] and len(text_parts) == 2
            and text_slots and country_slot > max(text_slots)):
        result["region"] = text_parts[1][:MAX_PART]
        text_parts = text_parts[:1]

    if text_parts:
        city = _METRO_TAIL.sub("", text_joiner.join(text_parts)).strip()
        folded = fold(city)
        metro = METROS.get(folded) or METROS.get(re.sub(r"^greater\s+", "", folded))
        if metro:
            name, region, country = metro
            result["city"] = name
            result["region"] = result["region"] or region
            result["country"] = result["country"] or country
        else:
            result["city"] = city[:MAX_PART] or None
    elif metro_city:
        result["city"] = metro_city

    # Georgia the country against Georgia the state. The state is what these
    # boards mean nearly every time ("Atlanta, Georgia"), so the country wins
    # only when the city beside it is unmistakably Georgian - "Tbilisi,
    # Georgia". Bare "Georgia" stays the state, on purpose.
    if (result["region"] == "GA" and result["country"] == "US"
            and (region_named or "").strip().lower() == "georgia"
            and fold(result["city"] or "") in GEORGIAN_CITIES):
        result["country"], result["region"] = "GE", None
        result["assumed"] = "Georgia read as the country, from the city beside it"

    return result


_GAZETTEER_NAMES = None


def _gazetteer_names() -> set:
    """Every multi-word name the parser knows, folded."""
    global _GAZETTEER_NAMES
    if _GAZETTEER_NAMES is None:
        _GAZETTEER_NAMES = set(COUNTRY_NAMES) | set(CA_REGIONS) | set(US_REGIONS)
    return _GAZETTEER_NAMES


def group_pieces(pieces: list, max_span: int = 4) -> list:
    """Rejoin pieces that together name one country or region.

    A Workday URL segment separates its parts with dashes and also uses a dash
    inside a name, so "New-York-New-York" arrives as four pieces. Splitting on
    every dash would leave "New York New York" as one unreadable city. This
    walks left to right and takes the longest run that the gazetteer knows,
    which turns those four pieces back into ["New York", "New York"].
    """
    grouped = []
    index = 0
    while index < len(pieces):
        for span in range(min(max_span, len(pieces) - index), 1, -1):
            run = " ".join(pieces[index:index + span])
            if fold(run) in _gazetteer_names():
                grouped.append(run)
                index += span
                break
        else:
            grouped.append(pieces[index])
            index += 1
    return grouped


def canonical(text: str, text_joiner: str = ", ") -> str | None:
    """Rewrite a board's location string as "City, REGION, Country".

    Returns None when the string carries no place. Returns the board's own text
    unchanged when the parse is ambiguous or resolves nothing, so a guess never
    replaces the source.
    """
    parsed = parse(text, text_joiner=text_joiner)
    if parsed["ambiguous"]:
        return text.strip() or None

    parts = [parsed["city"], parsed["region"]]
    country = parsed["country"]
    if country:
        parts.append(COUNTRY_LABELS.get(country, country))
    parts = [p for p in parts if p]
    if not parts:
        return (text or "").strip() or None
    return ", ".join(parts)


def _place_of(text: str, country_hint: str = None):
    """(country, region, folded city) for one string, or None when unusable."""
    parsed = parse(text or "", country_hint=country_hint)
    if parsed["ambiguous"]:
        return None
    city = fold(parsed["city"]) if parsed["city"] else None
    if not (parsed["country"] or parsed["region"] or city):
        return None
    return parsed["country"], parsed["region"], city


def _places_of(texts) -> list:
    """Every place one posting names, resolving each with the others' help.

    A first pass takes what needs no context. Whatever it settles on one country
    then settles the held-out codes in the rest: "San Francisco, CA" listed
    beside "Miami, FL" is California.
    """
    resolved, leftover = [], []
    for text in [s for t in texts for s in split_places(t)]:
        place = _place_of(text)
        (resolved if place else leftover).append(place or text)

    # Try each country this posting already resolved to. A held-out code belongs
    # to at most one of them - "CA" is a US state and no Canadian province - so
    # a posting spanning both countries still settles "San Francisco, CA".
    # Two candidates that both fit means the code stays unread.
    countries = sorted({place[0] for place in resolved if place[0]})
    for text in leftover:
        fits = [(country, _place_of(text, country_hint=country))
                for country in countries]
        fits = [(country, place) for country, place in fits
                if place and place[1] in REGION_CODES.get(country, set())]
        if len(fits) == 1:
            resolved.append(fits[0][1])
        # No fallback for a code that fits none of them as a region. Reading it
        # as the country instead files "San Francisco, CA" beside "Vancouver,
        # BC" in Canada - the exact error the whole module exists to avoid.
        # "Toronto, CA" beside "Vancouver, BC" is lost with it; a missing row
        # answers one filter too few, a wrong row answers the wrong one.

    out = []
    for place in resolved:
        if place not in out:
            out.append(place)
    return out


def apply_location_to_job(job, extra=None) -> None:
    """Fill the parsed location columns, and one `JobLocation` row per place.

    `job.location` itself is never rewritten - it is what the board wrote, and
    the UI shows it. An ambiguous parse writes nothing, so a job never lands in
    the wrong country: it simply does not answer a territorial filter.

    `extra` is every other place the board named. A posting open in twenty-two
    cities has to answer all twenty-two filters, so each becomes its own row.
    The primary place is denormalised onto `Job` as well, which keeps the feed's
    display and sort free of a join.
    """
    from backend.models.db import JobLocation

    if job.loc_country or job.loc_region or job.loc_city:
        return

    texts = [job.location] + [t for t in (extra or []) if t]
    # Both columns are indexed and a board occasionally writes a whole address
    # into the field, so every part is cut to what the index can hold.
    places = [tuple(p[:MAX_PART] if isinstance(p, str) else p for p in place)
              for place in _places_of([t for t in texts if t])]
    if places:
        job.loc_country, job.loc_region, job.loc_city = places[0]

    known = {(row.country, row.region, row.city) for row in (job.locations or [])}
    for index, (country, region, city) in enumerate(places):
        if (country, region, city) in known:
            continue
        job.locations.append(JobLocation(country=country, region=region, city=city,
                                         is_primary=index == 0))


# Quebec place names keep these lower-case: "Saint-Jean-sur-Richelieu".
_PARTICLES = {"sur", "sous", "le", "la", "les", "de", "du", "des", "aux", "et", "en"}


def _title_case(name: str) -> str:
    """Capitalise a folded city name for display, leaving French particles alone."""
    out = []
    for word_index, word in enumerate(re.split(r"(\s+|-)", name)):
        if not word.strip() or word in ("-",):
            out.append(word)
            continue
        out.append(word if word_index and word in _PARTICLES else word.capitalize())
    return "".join(out)


def label_for(country: str = None, region: str = None, city: str = None) -> str:
    """Human label for one facet entry, coarsest part last."""
    parts = []
    if city:
        parts.append(_title_case(city))
    if region:
        parts.append(region)
    if country:
        parts.append(COUNTRY_LABELS.get(country, country))
    return ", ".join(parts)


def key_for(country: str = None, region: str = None, city: str = None) -> str:
    """Filter key for one facet entry: "CA", "CA:BC", "CA:BC:vancouver"."""
    parts = [country or ""]
    if region or city:
        parts.append(region or "")
    if city:
        parts.append(city)
    return ":".join(parts)


def split_key(key: str) -> tuple:
    """Read a filter key back into (country, region, city); empty parts are None."""
    bits = (key or "").split(":")
    bits += [""] * (3 - len(bits))
    return tuple(b.strip() or None for b in bits[:3])
