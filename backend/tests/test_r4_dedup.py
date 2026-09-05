"""R4-T1 · URL normalisation / dedup property tests.

Twenty spellings of one posting must collapse onto a single ``external_id``;
distinct postings must not collide; ``content_hash`` must merge the same
company+title arriving from two different sources.

Tests marked xfail(strict=True) pin the CORRECT behaviour for a defect found in
this pass — see v2-testing/round4/T1.md for the finding they belong to.
"""
import pytest

from backend.scraper._shared import dedup
from backend.scraper._shared.dedup import (
    _normalize_url,
    make_content_hash,
    make_external_id,
)


@pytest.fixture(autouse=True)
def _pin_tracking_params(monkeypatch):
    """Pin the tracking list to the hardcoded defaults (no DB round-trip)."""
    monkeypatch.setattr(dedup, "_tracking_params_cache", dedup._DEFAULT_TRACKING_PARAMS)


CO, TITLE = "Acme", "Senior PM"
CANON = "https://boards.greenhouse.io/acme/jobs/4012345"


def _id(url):
    return make_external_id(CO, TITLE, url)


# ── The twenty spellings ─────────────────────────────────────────────────────
# Each entry is (label, url). All twenty describe the same posting.
SPELLINGS = [
    ("plain", CANON),
    ("trailing-slash", CANON + "/"),
    ("scheme-upper", "HTTPS://boards.greenhouse.io/acme/jobs/4012345"),
    ("host-upper", "https://BOARDS.GREENHOUSE.IO/acme/jobs/4012345"),
    ("path-upper", "https://boards.greenhouse.io/ACME/jobs/4012345"),
    ("www-prefix", "https://www.boards.greenhouse.io/acme/jobs/4012345"),
    ("http-scheme", "http://boards.greenhouse.io/acme/jobs/4012345"),
    ("fragment", CANON + "#content"),
    ("fragment-and-slash", CANON + "#apply-now"),
    ("utm-source", CANON + "?utm_source=linkedin"),
    ("utm-bundle", CANON + "?utm_source=li&utm_medium=social&utm_campaign=q3"),
    ("fbclid", CANON + "?fbclid=IwAR0abc"),
    ("gclid", CANON + "?gclid=EAIaIQobChMI"),
    ("gh_src", CANON + "?gh_src=abc123"),
    ("mixed-tracking", CANON + "?utm_term=pm&ref=newsletter&trk=public_jobs"),
    ("apply-suffix", CANON + "/apply"),
    ("application-suffix", CANON + "/application"),
    ("thanks-suffix", CANON + "/thanks"),
    ("apply-suffix-upper", CANON + "/Apply"),
    ("everything", "HTTP://WWW.boards.greenhouse.io/ACME/jobs/4012345/apply/"
                   "?utm_source=li&fbclid=z#top"),
]


def test_twenty_spellings_are_exactly_twenty():
    """Guard the fixture itself — the property below is only meaningful at N=20."""
    assert len(SPELLINGS) == 20
    assert len({u for _, u in SPELLINGS}) == 20


# ── Spellings that already converge (current contract) ───────────────────────

@pytest.mark.parametrize("label", [
    "plain", "scheme-upper", "host-upper", "path-upper", "fragment",
    "fragment-and-slash", "utm-source", "utm-bundle", "fbclid", "gclid",
    "gh_src", "mixed-tracking", "apply-suffix", "application-suffix",
    "thanks-suffix", "apply-suffix-upper",
])
def test_spelling_collapses_onto_canonical_id(label):
    url = dict(SPELLINGS)[label]
    assert _id(url) == _id(CANON), f"{label}: {_normalize_url(url)!r}"


# ── Spellings that do NOT converge — defects pinned to the right behaviour ────

@pytest.mark.xfail(strict=True, reason="R4-T1-01")
def test_trailing_slash_is_the_same_posting():
    """`/jobs/123` and `/jobs/123/` are one posting on every board we scrape."""
    assert _id(CANON + "/") == _id(CANON)


@pytest.mark.xfail(strict=True, reason="R4-T1-02")
def test_www_prefix_is_the_same_host():
    """`www.host` and `host` serve the same posting."""
    assert _id("https://www.example.com/jobs/4012345") == \
           _id("https://example.com/jobs/4012345")


@pytest.mark.xfail(strict=True, reason="R4-T1-03")
def test_http_and_https_are_the_same_posting():
    """A board that upgrades http→https must not mint a second job row."""
    assert _id("http://boards.greenhouse.io/acme/jobs/4012345") == _id(CANON)


@pytest.mark.xfail(strict=True, reason="R4-T1-04")
def test_query_param_order_does_not_change_the_id():
    """_normalize_url claims to 'sort params for stable hashing' — it does not."""
    a = _id("https://job-boards.greenhouse.io/acme/jobs/9?gh_jid=9&location=us")
    b = _id("https://job-boards.greenhouse.io/acme/jobs/9?location=us&gh_jid=9")
    assert a == b


@pytest.mark.xfail(strict=True, reason="R4-T1-05")
def test_percent_encoded_unreserved_chars_are_equivalent():
    """%2D is a hyphen; RFC 3986 says the two spellings are the same resource."""
    assert _id("https://x.com/jobs/senior%2Dpm") == _id("https://x.com/jobs/senior-pm")


@pytest.mark.xfail(strict=True, reason="R4-T1-01")
def test_all_twenty_spellings_share_one_external_id():
    """The whole property: 20 spellings → 1 id."""
    ids = {_id(u) for _, u in SPELLINGS}
    assert len(ids) == 1, f"{len(ids)} distinct ids across 20 spellings"


def test_current_spelling_fanout_is_bounded():
    """Regression guard: today the 20 spellings fan out to exactly 5 ids.

    If a normalisation change lands, this number must move *down*, never up.
    """
    ids = {_id(u) for _, u in SPELLINGS}
    assert len(ids) <= 5


# ── Identity params survive normalisation ────────────────────────────────────

def test_indeed_jk_is_identity_not_tracking():
    a = _id("https://www.indeed.com/viewjob?jk=aaaaaaaaaaaaaaaa")
    b = _id("https://www.indeed.com/viewjob?jk=bbbbbbbbbbbbbbbb")
    assert a != b


def test_indeed_jk_survives_tracking_noise():
    bare = "https://www.indeed.com/viewjob?jk=aaaaaaaaaaaaaaaa"
    noisy = bare + "&utm_source=telegram&fbclid=zz&from=serp&vjs=3"
    assert "jk=aaaaaaaaaaaaaaaa" in _normalize_url(noisy)


def test_indeed_vjk_is_identity():
    assert _id("https://www.indeed.com/jobs?vjk=1111") != \
           _id("https://www.indeed.com/jobs?vjk=2222")


def test_glassdoor_and_dice_and_monster_identity_params():
    pairs = [
        ("https://www.glassdoor.com/job-listing/x?jl={}", "1", "2"),
        ("https://www.dice.com/job-detail?jobId={}", "a", "b"),
        ("https://www.monster.com/job-openings?jobId={}", "a", "b"),
    ]
    for tmpl, one, two in pairs:
        assert _id(tmpl.format(one)) != _id(tmpl.format(two)), tmpl


def test_linkedin_currentjobid_kept_on_search_shape():
    a = _id("https://www.linkedin.com/jobs/collections/recommended?currentJobId=111")
    b = _id("https://www.linkedin.com/jobs/collections/recommended?currentJobId=222")
    assert a != b


def test_linkedin_currentjobid_stripped_when_id_is_in_the_path():
    """On /jobs/view/<id> the param is display noise, not identity."""
    a = _id("https://www.linkedin.com/jobs/view/4012345?currentJobId=999")
    b = _id("https://www.linkedin.com/jobs/view/4012345")
    assert a == b


def test_identity_params_match_subdomains_only_not_lookalikes():
    """uk.indeed.com is Indeed; indeed.com.evil.net is not."""
    real = _normalize_url("https://uk.indeed.com/viewjob?jk=abc")
    fake = _normalize_url("https://indeed.com.evil.net/viewjob?jk=abc")
    assert "jk=abc" in real
    assert "jk=abc" in fake  # jk is not in the tracking list at all
    # …but the identity guard must only fire for the real host.
    from urllib.parse import urlparse
    assert dedup._identity_params_for(urlparse(real)) == {"jk", "vjk"}
    assert dedup._identity_params_for(urlparse(fake)) == set()


# ── Different postings must not collide ──────────────────────────────────────

def test_distinct_postings_get_distinct_ids():
    urls = [
        "https://boards.greenhouse.io/acme/jobs/4012345",
        "https://boards.greenhouse.io/acme/jobs/4012346",
        "https://boards.greenhouse.io/beta/jobs/4012345",
        "https://jobs.lever.co/acme/8f2c-1",
        "https://jobs.lever.co/acme/8f2c-2",
        "https://www.indeed.com/viewjob?jk=aaaaaaaaaaaaaaaa",
        "https://www.indeed.com/viewjob?jk=bbbbbbbbbbbbbbbb",
        "https://careers.example.com/en-us/job/771",
        "https://careers.example.com/en-gb/job/771",
    ]
    ids = [_id(u) for u in urls]
    assert len(set(ids)) == len(urls)


def test_empty_url_falls_back_to_company_plus_title():
    assert make_external_id("Acme", "PM", "") != make_external_id("Acme", "SWE", "")
    assert make_external_id("Acme", "PM", "") == make_external_id("Acme", "PM", None or "")


def test_external_id_is_sha256_hex():
    v = _id(CANON)
    assert len(v) == 64 and all(c in "0123456789abcdef" for c in v)


@pytest.mark.parametrize("bad", [
    "not a url at all",
    "://missing-scheme",
    "https://",
    "javascript:alert(1)",
    "https://x.com/jobs/éèê",
    "https://x.com/jobs/\U0001f600",
    " " * 10,
    "https://x.com/" + "a" * 4000,
])
def test_malformed_urls_never_raise(bad):
    v = make_external_id("Acme", "PM", bad)
    assert isinstance(v, str) and len(v) == 64


# ── content_hash ─────────────────────────────────────────────────────────────

def test_content_hash_merges_two_sources_for_one_posting():
    """The same posting seen on LinkedIn and on the career page → one content hash."""
    from_linkedin = make_content_hash("Acme Corp", "Senior Product Manager")
    from_greenhouse = make_content_hash("acme corp", "  Senior Product Manager  ")
    assert from_linkedin == from_greenhouse


def test_content_hash_ignores_url_entirely():
    a = make_content_hash("Acme", "PM")
    b = make_content_hash("Acme", "PM")
    assert a == b


def test_content_hash_distinguishes_company_and_title():
    assert make_content_hash("Acme", "PM") != make_content_hash("Beta", "PM")
    assert make_content_hash("Acme", "PM") != make_content_hash("Acme", "SWE")


def test_content_hash_handles_none_and_unicode():
    assert len(make_content_hash(None, None)) == 64
    assert make_content_hash("Acéme", "PM \U0001f680") != make_content_hash("Acme", "PM")


@pytest.mark.xfail(strict=True, reason="R4-T1-06")
def test_content_hash_collapses_internal_whitespace():
    """'Senior  PM' (double space) is the same posting as 'Senior PM'."""
    assert make_content_hash("Acme", "Senior  PM") == make_content_hash("Acme", "Senior PM")
