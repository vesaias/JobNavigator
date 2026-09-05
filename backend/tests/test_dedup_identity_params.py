"""A posting's identity param (e.g. Indeed's `jk`) must survive dedup normalization even if the editable tracking-params setting would strip it."""
import json

import pytest

from backend.scraper._shared import dedup
from backend.scraper._shared.dedup import _normalize_url, make_external_id
from backend.models.db import Setting

TEN_JK = ["ec3af3a391951b18", "0a1b2c3d4e5f6071", "1111111111111111", "222222222222aaaa",
          "33333333bbbb3333", "4444cccc44444444", "5555555555555555", "66666666dddd6666",
          "777777777777eeee", "8888ffff88888888"]


@pytest.fixture(autouse=True)
def _defaults(monkeypatch):
    """Pin the tracking list to the hardcoded defaults (no DB round-trip)."""
    monkeypatch.setattr(dedup, "_tracking_params_cache", dedup._DEFAULT_TRACKING_PARAMS)


def test_ten_indeed_postings_get_ten_ids():
    ids = {make_external_id("Acme", "PM", f"https://www.indeed.com/viewjob?jk={k}") for k in TEN_JK}
    assert len(ids) == 10


def test_jk_survives_even_when_the_setting_still_strips_it(monkeypatch):
    """The editable list is not allowed to erase a posting's identity."""
    monkeypatch.setattr(dedup, "_tracking_params_cache", dedup._DEFAULT_TRACKING_PARAMS | {"jk"})
    a = make_external_id("Acme", "PM", "https://www.indeed.com/viewjob?jk=aaa")
    b = make_external_id("Acme", "PM", "https://www.indeed.com/viewjob?jk=bbb")
    assert a != b


def test_tracking_params_are_still_stripped():
    base = "https://www.indeed.com/viewjob?jk=abc"
    noisy = base + "&utm_source=telegram&utm_campaign=x&fbclid=zz&from=serp"
    assert make_external_id("Acme", "PM", noisy) == make_external_id("Acme", "PM", base)
    out = _normalize_url(noisy)
    assert "jk=abc" in out
    for junk in ("utm_source", "utm_campaign", "fbclid", "from="):
        assert junk not in out


def test_subdomains_and_country_hosts_count_as_indeed():
    a = make_external_id("Acme", "PM", "https://uk.indeed.com/viewjob?jk=aaa")
    b = make_external_id("Acme", "PM", "https://uk.indeed.com/viewjob?jk=bbb")
    assert a != b


def test_linkedin_currentjobid_is_kept_only_where_it_is_the_identity():
    # collection/search shape: the id lives in the query, so it must survive
    x = make_external_id("Acme", "PM", "https://www.linkedin.com/jobs/collections/recommended/?currentJobId=1")
    y = make_external_id("Acme", "PM", "https://www.linkedin.com/jobs/collections/recommended/?currentJobId=2")
    assert x != y
    # /jobs/view/<id>: the path already carries the identity, so currentJobId is
    # noise and the two shapes of the same posting must still converge
    p = make_external_id("Acme", "PM", "https://www.linkedin.com/jobs/view/4231/?currentJobId=999")
    q = make_external_id("Acme", "PM", "https://www.linkedin.com/jobs/view/4231/")
    assert p == q


def test_tracking_stripping_on_other_hosts_is_unchanged():
    a = _normalize_url("https://boards.greenhouse.io/acme/jobs/123?utm_source=x&gclid=y&ref=z")
    assert a == "https://boards.greenhouse.io/acme/jobs/123"


def test_jk_is_no_longer_stripped_anywhere():
    """`jk` left the tracking list entirely, not just for Indeed — it is a job key wherever it appears."""
    a = _normalize_url("https://boards.greenhouse.io/acme/jobs/123?jk=aaa")
    assert "jk=aaa" in a


def test_seeded_default_no_longer_lists_jk():
    from backend.seed import DEFAULT_SETTINGS
    seeded = json.loads(DEFAULT_SETTINGS["dedup_tracking_params"][0])
    assert "jk" not in seeded
    assert "utm_source" in seeded, "the rest of the list is untouched"
    assert "jk" not in dedup._DEFAULT_TRACKING_PARAMS


def test_migration_strips_jk_from_a_stored_list(test_db):
    from backend.seed import migrate_dedup_tracking_params
    test_db.add(Setting(key="dedup_tracking_params",
                        value=json.dumps(["utm_source", "jk", "JK", "gclid"])))
    test_db.commit()

    migrate_dedup_tracking_params(test_db)
    stored = json.loads(test_db.query(Setting).one().value)
    assert stored == ["utm_source", "gclid"]

    # idempotent, and a no-op on a list that never had it
    migrate_dedup_tracking_params(test_db)
    assert json.loads(test_db.query(Setting).one().value) == ["utm_source", "gclid"]


def test_migration_tolerates_a_missing_or_malformed_setting(test_db):
    from backend.seed import migrate_dedup_tracking_params
    migrate_dedup_tracking_params(test_db)          # no row at all
    test_db.add(Setting(key="dedup_tracking_params", value="not json"))
    test_db.commit()
    migrate_dedup_tracking_params(test_db)          # must not raise
    assert test_db.query(Setting).one().value == "not json"
