"""The ATS handler contract carries `location` and, where the board has it,
`arrangement`.

Field names come from live probes of each public API, not from guesswork. The
two exceptions are marked in the tests that cover them.

Handlers that scrape the DOM (meta, google, talentbrew, generic) return no
location: their boards do not put one where the handler already looks, and
adding selectors for it is a separate job.
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _response(payload):
    mock = MagicMock()
    mock.status_code = 200
    mock.text = json.dumps(payload)
    mock.json.return_value = payload
    return mock


def _client(payload):
    """An httpx.AsyncClient stand-in whose GET always answers with `payload`."""
    client = MagicMock()
    client.get = AsyncMock(return_value=_response(payload))
    client.post = AsyncMock(return_value=_response(payload))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


# ── Ashby ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ashby_carries_location_and_workplace_type():
    payload = {"jobs": [{
        "title": "Staff Engineer",
        "jobUrl": "https://jobs.ashbyhq.com/acme/1",
        "location": "New York, NY (HQ)",
        "isRemote": True,
        "workplaceType": "Hybrid",
    }]}
    with patch("httpx.AsyncClient", return_value=_client(payload)):
        from backend.scraper.ats.ashby import scrape
        jobs = await scrape("https://jobs.ashbyhq.com/acme")

    assert jobs, "handler returned nothing"
    assert jobs[0]["location"] == "New York, NY (HQ)"
    # `isRemote` is true on this posting and must not win over workplaceType.
    assert jobs[0]["arrangement"] == "Hybrid"


# ── Greenhouse ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_greenhouse_carries_location_name():
    payload = {"jobs": [{
        "id": 1,
        "title": "Staff Engineer",
        "location": {"name": "Remote - US"},
        "absolute_url": "https://boards.greenhouse.io/acme/jobs/1",
        "departments": [],
        "offices": [],
    }]}
    with patch("httpx.AsyncClient", return_value=_client(payload)):
        from backend.scraper.ats.greenhouse import scrape
        jobs = await scrape("https://boards.greenhouse.io/acme")

    assert jobs
    assert jobs[0]["location"] == "Remote - US"


# ── Lever ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_lever_carries_location_and_workplace_type():
    payload = [{
        "text": "Staff Engineer",
        "hostedUrl": "https://jobs.lever.co/acme/1",
        "categories": {"location": "Seoul, South Korea", "team": "Platform"},
        "workplaceType": "hybrid",
    }]
    with patch("httpx.AsyncClient", return_value=_client(payload)):
        from backend.scraper.ats.lever import scrape
        jobs = await scrape("https://jobs.lever.co/acme")

    assert jobs
    assert jobs[0]["location"] == "Seoul, South Korea"
    assert jobs[0]["arrangement"] == "hybrid"


# ── SmartRecruiters ──────────────────────────────────────────────────────────

def test_smartrecruiters_prefers_full_location():
    from backend.scraper.ats.smartrecruiters import _location_fields
    fields = _location_fields({
        "city": "Edinburgh", "region": "Scotland", "country": "gb",
        "fullLocation": "Edinburgh, Scotland, United Kingdom",
        "remote": False, "hybrid": True,
    })
    assert fields["location"] == "Edinburgh, Scotland, United Kingdom"
    assert fields["arrangement"] == "hybrid"


def test_smartrecruiters_builds_a_location_without_full_location():
    from backend.scraper.ats.smartrecruiters import _location_fields
    fields = _location_fields({"city": "Zurich", "region": "ZH", "country": "ch"})
    assert fields["location"] == "Zurich, ZH, ch"
    assert fields["arrangement"] is None


def test_smartrecruiters_hybrid_wins_over_remote():
    """A hybrid posting also reports remote true."""
    from backend.scraper.ats.smartrecruiters import _location_fields
    fields = _location_fields({"city": "Zurich", "remote": True, "hybrid": True})
    assert fields["arrangement"] == "hybrid"


def test_smartrecruiters_tolerates_a_missing_location():
    from backend.scraper.ats.smartrecruiters import _location_fields
    assert _location_fields(None) == {}


# Workday's own tests live in test_location_parser.py: its `locationsText` is
# per-tenant, so the handler runs it through the location parser rather than
# storing it as written.


# ── Oracle HCM ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_oracle_carries_primary_location():
    payload = {"items": [{"requisitionList": [{
        "Title": "Staff Engineer",
        "Id": "REQ1",
        "PrimaryLocation": "Seattle, WA, United States",
        "WorkplaceType": "Hybrid",
    }], "TotalJobsCount": 1}]}
    with patch("httpx.AsyncClient", return_value=_client(payload)):
        from backend.scraper.ats.oracle_hcm import scrape
        jobs = await scrape("https://acme.fa.us2.oraclecloud.com/hcmUI/"
                            "CandidateExperience/en/sites/CX_1/requisitions")

    assert jobs
    assert jobs[0]["location"] == "Seattle, WA, United States"
    assert jobs[0]["arrangement"] == "Hybrid"


def test_oracle_empty_workplace_type_is_none():
    """The live API returns '' rather than null when it has no value."""
    from backend.analyzer.work_arrangement import from_structured
    assert from_structured("") is None


# ── Phenom (field names unverified — see the handler comment) ────────────────

@pytest.mark.parametrize("job,expected", [
    ({"cityState": "Austin, TX"}, "Austin, TX"),
    ({"location": "Dublin, Ireland"}, "Dublin, Ireland"),
    ({"city": "Berlin", "state": "", "country": "Germany"}, "Berlin, Germany"),
    ({}, None),
    ({"cityState": "   "}, None),
])
def test_phenom_location_of(job, expected):
    from backend.scraper.ats.phenom import _location_of
    assert _location_of(job) == expected


# ── LinkedIn Voyager (field names unverified — needs a signed-in probe) ──────

@pytest.mark.parametrize("value,expected", [
    ("1", "onsite"),
    ("2", "remote"),
    ("3", "hybrid"),
    ("", None),
    (None, None),
    ("99", None),
])
def test_voyager_workplace_type_mapping(value, expected):
    from backend.scraper.sources.linkedin_extension import _voyager_arrangement
    assert _voyager_arrangement({"workplace_type": value}) == expected


def test_voyager_js_reads_the_workplace_fields():
    from backend.scraper.sources.linkedin_extension import _VOYAGER_JOB_JS
    assert "workplaceTypes" in _VOYAGER_JOB_JS
    assert "workRemoteAllowed" in _VOYAGER_JOB_JS


# ── the consumer ─────────────────────────────────────────────────────────────

def test_company_pages_reads_the_optional_fields():
    """A handler that supplies neither field must still work."""
    from backend.analyzer.work_arrangement import apply_arrangement_to_job

    class FakeJob:
        id = "j1"
        location = None
        title = "Staff Engineer"
        description = None
        remote = None

    job = FakeJob()
    apply_arrangement_to_job(job, structured={}.get("arrangement"))
    assert job.remote is None
