"""Canonical schema for structured application autofill: maps each fixed-answer field the
extension fills to the persona JSONB node/key that holds its value."""

ANSWER_SCHEMA = {
    # EEO self-ID (persona.demographics)
    "gender": {"node": "demographics", "kind": "enum",
               "enum": ["male", "female", "nonbinary", "decline"]},
    "race_ethnicity": {"node": "demographics", "kind": "enum",
                       "enum": ["hispanic_latino", "white", "black", "asian",
                                "native_american", "pacific_islander", "two_or_more", "decline"]},
    "veteran_status": {"node": "demographics", "kind": "enum",
                       "enum": ["protected_veteran", "not_protected_veteran", "decline"]},
    "hispanic_latino": {"node": "demographics", "kind": "enum",
                        "enum": ["yes", "no", "decline"]},
    "disability_status": {"node": "demographics", "kind": "enum",
                          "enum": ["yes", "no", "decline"]},
    # Extended diversity self-ID (persona.demographics). Optional & sensitive — defaults to
    # "decline" when unset; the persona editor can override with a real value.
    "age_range": {"node": "demographics", "kind": "enum",
                  "enum": ["under_30", "30_39", "40_49", "50_59", "60_plus", "decline"]},
    "transgender": {"node": "demographics", "kind": "enum",
                    "enum": ["yes", "no", "decline"]},
    "sexual_orientation": {"node": "demographics", "kind": "enum",
                           "enum": ["heterosexual", "gay", "lesbian", "bisexual",
                                    "queer", "other", "decline"]},
    "decline_demographics": {"node": "demographics", "kind": "bool"},
    # Work authorization (persona.work_auth)
    "authorized_us": {"node": "work_auth", "kind": "bool"},
    "requires_sponsorship_now": {"node": "work_auth", "kind": "bool"},
    "requires_sponsorship_future": {"node": "work_auth", "kind": "bool"},
    "over_18": {"node": "work_auth", "kind": "bool"},
    "work_auth_type": {"node": "work_auth", "kind": "enum",
                       "enum": ["citizen", "permanent_resident", "visa", "other"]},
    # Contact / basics (persona.contact)
    "first_name": {"node": "contact", "kind": "text"},
    "last_name": {"node": "contact", "kind": "text"},
    "email": {"node": "contact", "kind": "text"},
    "phone": {"node": "contact", "kind": "text"},
    "city": {"node": "contact", "kind": "text"},
    "state": {"node": "contact", "kind": "text"},
    "country": {"node": "contact", "kind": "text"},
    "linkedin": {"node": "contact", "kind": "text"},
    "github": {"node": "contact", "kind": "text"},
    "portfolio": {"node": "contact", "kind": "text"},
    "current_company": {"node": "contact", "kind": "text"},
    # Screening defaults (persona.preferences / persona.compensation)
    "willing_to_relocate": {"node": "preferences", "kind": "bool"},
    "willing_remote": {"node": "preferences", "kind": "bool"},
    "notice_period": {"node": "preferences", "kind": "text"},
    "earliest_start": {"node": "preferences", "kind": "text"},
    "referral_source": {"node": "preferences", "kind": "text"},
    "how_did_you_hear": {"node": "preferences", "kind": "text"},
    "desired_salary": {"node": "compensation", "kind": "text"},
}


# Demographic self-ID enum fields. When persona's `decline_demographics` flag is set, every one
# of these is answered "decline" unless the user gave it a specific value.
DEMOGRAPHIC_ENUM_KEYS = (
    "gender", "race_ethnicity", "veteran_status", "hispanic_latino",
    "disability_status", "age_range", "transgender", "sexual_orientation",
)


# Country name -> international dialing code, for splitting a full phone number
# into the national part when a form has a separate country-code selector.
_DIAL_CODES = {
    "united states": "1", "usa": "1", "us": "1", "canada": "1", "puerto rico": "1",
    "united kingdom": "44", "uk": "44", "great britain": "44", "england": "44",
    "germany": "49", "france": "33", "spain": "34", "italy": "39", "portugal": "351",
    "netherlands": "31", "switzerland": "41", "austria": "43", "belgium": "32",
    "ireland": "353", "poland": "48", "sweden": "46", "norway": "47", "denmark": "45",
    "finland": "358", "iceland": "354", "luxembourg": "352", "greece": "30",
    "czech republic": "420", "czechia": "420", "slovakia": "421", "slovenia": "386",
    "croatia": "385", "serbia": "381", "romania": "40", "bulgaria": "359",
    "hungary": "36", "ukraine": "380", "russia": "7", "turkey": "90", "cyprus": "357",
    "estonia": "372", "latvia": "371", "lithuania": "370", "malta": "356",
    "india": "91", "china": "86", "japan": "81", "south korea": "82", "korea": "82",
    "taiwan": "886", "hong kong": "852", "macau": "853", "singapore": "65",
    "malaysia": "60", "indonesia": "62", "thailand": "66", "vietnam": "84",
    "philippines": "63", "pakistan": "92", "bangladesh": "880", "sri lanka": "94",
    "nepal": "977", "australia": "61", "new zealand": "64",
    "brazil": "55", "mexico": "52", "argentina": "54", "chile": "56", "colombia": "57",
    "peru": "51", "venezuela": "58", "ecuador": "593", "uruguay": "598",
    "bolivia": "591", "paraguay": "595", "costa rica": "506", "panama": "507",
    "guatemala": "502", "dominican republic": "1",
    "israel": "972", "united arab emirates": "971", "uae": "971", "saudi arabia": "966",
    "qatar": "974", "kuwait": "965", "bahrain": "973", "oman": "968", "jordan": "962",
    "lebanon": "961", "egypt": "20", "morocco": "212", "tunisia": "216", "algeria": "213",
    "south africa": "27", "nigeria": "234", "kenya": "254", "ghana": "233",
    "ethiopia": "251", "tanzania": "255", "uganda": "256",
}


def project_answers(persona: dict) -> dict:
    """Flatten persona nodes into {canonical_key: value}, omitting blank (None/whitespace) values;
    explicit booleans (incl. False) are always kept as real answers."""
    out = {}
    for key, spec in ANSWER_SCHEMA.items():
        node = persona.get(spec["node"]) or {}
        if key not in node:
            continue
        val = node[key]
        if val is None:
            continue
        if isinstance(val, str) and not val.strip():
            continue
        out[key] = val
    # The "prefer not to answer demographic questions" checkbox: fill every
    # demographic self-ID field with "decline" unless the user set a specific value.
    demo = persona.get("demographics") or {}
    if demo.get("decline_demographics"):
        for key in DEMOGRAPHIC_ENUM_KEYS:
            out.setdefault(key, "decline")
    # Derived: a combined full name for forms with a single name field (Lever,
    # some Workday) rather than separate first/last inputs.
    if "first_name" in out and "last_name" in out and "full_name" not in out:
        out["full_name"] = f'{out["first_name"]} {out["last_name"]}'.strip()
    # Derived: "Are you Hispanic/Latino?" — a separate Y/N question (Greenhouse
    # splits it from Race). Inferred from race when not answered explicitly.
    if "hispanic_latino" not in out and out.get("race_ethnicity"):
        out["hispanic_latino"] = "yes" if out["race_ethnicity"] == "hispanic_latino" else "no"
    # Derived: the national (local) phone number, for forms that split phone into
    # a separate country-code selector + a number field. Strip the country dial
    # code (resolved from the answer's country) off a leading '+..' number.
    ph = (out.get("phone") or "").strip()
    if ph and "phone_national" not in out:
        cc = _DIAL_CODES.get((out.get("country") or "").strip().lower())
        if ph.startswith("+"):
            digits = "".join(c for c in ph if c.isdigit())
            out["phone_national"] = digits[len(cc):] if (cc and digits.startswith(cc)) else digits
        else:
            out["phone_national"] = ph
    return out
