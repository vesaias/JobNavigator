"""Apify source: actor input, item parsing, the run/poll/abort cycle, the save pipeline and the wiring (no network)."""
import json
import uuid as uuid_mod
from types import SimpleNamespace

import httpx
import pytest

from backend.models.db import Job, Search, Setting
from backend.scraper.sources import apify


@pytest.fixture
def api_client(api_client, test_db):
    """Open access for the route tests: with INITIAL_API_KEY set in the environment the
    middleware wants a key unless the dashboard_api_key row exists and is empty."""
    test_db.add(Setting(key="dashboard_api_key", value=""))
    test_db.commit()
    return api_client


def _search(**kw):
    base = dict(name="t", search_mode="apify", search_term="program manager", location="",
                country="usa", is_remote=None, hours_old=24, results_wanted=30,
                sources=["apify_indeed", "apify_greenhouse"])
    base.update(kw)
    return SimpleNamespace(**base)


def _job(title, company, url, source="apify_indeed", desc="Great role", **kw):
    j = {"title": title, "company": company, "url": url, "location": "Austin, TX",
         "description": desc, "salary_min": None, "salary_max": None,
         "arrangement": None, "posted": None, "source": source}
    j.update(kw)
    return j


# ── actor input ─────────────────────────────────────────────────────────────

def test_indeed_host_matches_jobspy():
    from backend.countries import indeed_host
    assert indeed_host("usa") == "www.indeed.com"
    assert indeed_host("uk") == "uk.indeed.com"
    assert indeed_host("Canada") == "ca.indeed.com"
    assert indeed_host("atlantis") is None


def _indeed_url(**kw):
    body = apify._indeed_input(_search(**kw), 30)
    assert set(body) == {"startUrls", "maxItemsPerSearch", "saveOnlyUniqueItems"}  # no `position`: it would run a second, billed search
    assert body["maxItemsPerSearch"] == 30
    return body["startUrls"][0]["url"]


def test_indeed_input_is_one_search_url():
    assert _indeed_url(location="Toronto, Canada", country="canada", hours_old=24) ==         "https://ca.indeed.com/jobs?q=program+manager&l=Toronto&fromage=1"


def test_indeed_input_remote_without_place_asks_for_remote():
    assert "l=Remote" in _indeed_url(is_remote=True)
    assert "l=" not in _indeed_url()


def test_indeed_input_unknown_country_falls_back_to_the_default():
    assert _indeed_url(country="atlantis").startswith("https://www.indeed.com/jobs?")


@pytest.mark.parametrize("hours,expected", [(None, None), (0, None), (1, 1), (24, 1), (25, 3), (72, 3),
                                            (73, 7), (168, 7), (336, 14), (337, None), (720, None)])
def test_indeed_fromage_rounds_up_and_never_narrows(hours, expected):
    assert apify._indeed_fromage(hours) == expected
    if expected is None:
        assert "fromage" not in _indeed_url(hours_old=hours)


def _gh(search, limit):
    return apify.PRESETS["apify_greenhouse"].build_input(search, limit)


def test_greenhouse_input_filters_ats_and_clamps_limit():
    body = _gh(_search(hours_old=72, is_remote=True), 3)
    assert body["ats"] == ["greenhouse"]
    assert body["titleSearch"] == ["program manager"]
    assert body["timeRange"] == "7d"
    assert body["limit"] == 10                      # the actor refuses less than 10
    assert body["locationSearch"] == ["United States"]
    assert body["aiWorkArrangementFilter"] == ["Remote OK", "Remote Solely"]
    assert _gh(_search(location="Austin"), 9000)["limit"] == 5000
    assert _gh(_search(location="Austin"), 50)["locationSearch"] == ["Austin"]


@pytest.mark.parametrize("key,ats,label", [("apify_greenhouse", "greenhouse", "Greenhouse"), ("apify_lever", "lever.co", "Lever"),
                                           ("apify_ashby", "ashby", "Ashby"), ("apify_workday", "workday", "Workday")])
def test_ats_boards_share_the_career_site_actor(key, ats, label):
    preset = apify.PRESETS[key]
    assert preset.actor == "fantastic-jobs/career-site-job-listing-api"
    assert preset.parse is apify._parse_career_site
    assert preset.label == label and label in preset.hint
    assert preset.build_input(_search(), 20)["ats"] == [ats]   # a value of the actor's `ats` enum


def test_source_label_names_apify_boards():
    from backend.scraper.orchestrator import source_label
    assert source_label("zip_recruiter") == "ZipRecruiter"
    assert source_label("apify_workday") == "Workday"
    assert source_label("apify_lever") == "Lever"
    assert source_label("monster") == "monster"


@pytest.mark.parametrize("hours,expected", [(None, "7d"), (0, "7d"), (1, "1h"), (24, "24h"),
                                            (25, "7d"), (168, "7d"), (720, "6m")])
def test_time_range_rounds_up(hours, expected):
    assert apify._time_range(hours) == expected


def test_linkedin_input_passes_exact_age_and_remote_as_url_params():
    body = apify._linkedin_input(_search(location="Austin", hours_old=6, is_remote=True), 2000)
    assert body["keywords"] == "program manager"
    assert body["location"] == "Austin, United States"
    assert body["limit"] == 1000                     # the actor refuses more
    assert body["urlParam"] == [{"key": "f_TPR", "value": "r21600"}, {"key": "f_WT", "value": "2"}]
    assert "urlParam" not in apify._linkedin_input(_search(hours_old=0), 5)
    assert "datePosted" not in body                  # three fixed steps; urlParam is exact


def test_linkedin_hint_says_remote_is_not_applied_by_linkedin():
    """LinkedIn returns the same rows with and without f_WT=2 when not logged in (2026-10-22)."""
    hint = apify.PRESETS["apify_linkedin"].hint
    assert "ignores Remote without login" in hint
    assert "remote filter" not in hint


def test_glassdoor_input_always_has_a_location_and_whole_days():
    body = apify._glassdoor_input(_search(hours_old=25, is_remote=True), 30)
    assert body["location"] == "United States"       # required by the actor
    assert body["daysOld"] == 2
    assert body["remoteWorkType"] is True
    assert body["sortBy"] == "date_desc"
    assert "daysOld" not in apify._glassdoor_input(_search(hours_old=None), 30)


def test_behance_input_maps_city_and_remote():
    body = apify._behance_input(_search(search_term=" illustrator ", location="Los Angeles, CA", is_remote=True), 30)
    assert body == {"search": "illustrator", "maxItems": 30, "jobTypes": ["CONTRACT", "FULLTIME"],
                    "city": "Los Angeles", "isWorldwide": True}
    assert set(apify._behance_input(_search(), 5)) == {"search", "maxItems", "jobTypes"}


def test_hollylist_input_skips_members_only_offers():
    body = apify._hollylist_input(_search(search_term="animator", location="London", is_remote=True), 30)
    assert body == {"searchQueries": ["animator"], "maxResults": 30, "extractFullDetails": True,
                    "includePremiumOffers": False, "locations": ["London"], "workType": ["remote"]}
    assert set(apify._hollylist_input(_search(), 5)) == {"searchQueries", "maxResults", "extractFullDetails",
                                                         "includePremiumOffers"}


# ── item parsing ────────────────────────────────────────────────────────────

def test_parse_behance_maps_the_documented_row():
    j = apify._parse_behance({
        "title": "Senior Experience Designer", "companyName": "HP Inc.",
        "url": "https://www.behance.net/joblist/fulltime/366779/Senior-Experience-Designer",
        "description": "<p>We are seeking a <strong>UX/UI Designer</strong></p>",
        "locationDisplay": "Palo Alto, CA, USA", "remoteStatus": "HYBRID", "postedOn": 1791463395})
    assert (j["company"], j["location"], j["arrangement"]) == ("HP Inc.", "Palo Alto, CA, USA", "hybrid")
    assert j["description"] == "We are seeking a UX/UI Designer"
    assert j["posted"] == "2026-10-08"
    empty = apify._parse_behance({})
    assert (empty["title"], empty["arrangement"], empty["posted"]) == ("", None, None)


def test_parse_hollylist_keeps_yearly_pay_and_the_first_place():
    j = apify._parse_hollylist({
        "title": "Director of Social\n    ", "url": "https://www.hollylist.com/job/director-of-social-x",
        "company": {"name": "Paramount"},
        "locations": [{"city": "London", "region": None, "countryCode": "GB"}],
        "workType": [{"type": "hybrid"}], "description": {"text": "Lead social."},
        "salaries": [{"period": "month", "min": 5000, "max": 6000, "isOriginal": False, "currency": "USD"},
                     {"period": "year", "min": 60000, "max": 72000, "isOriginal": True, "currency": "USD"}],
        "dates": {"posted": "2026-10-23"}})
    assert (j["title"], j["company"], j["location"]) == ("Director of Social", "Paramount", "London, GB")
    assert (j["salary_min"], j["salary_max"], j["arrangement"]) == (60000, 72000, "hybrid")
    assert (j["description"], j["posted"]) == ("Lead social.", "2026-10-23")
    hourly = apify._parse_hollylist({"salaries": [{"period": "hour", "min": 30, "isOriginal": True, "currency": "USD"}]})
    assert (hourly["salary_min"], hourly["salary_max"]) == (None, None)
    pounds = apify._parse_hollylist({"salaries": [{"period": "year", "min": 40000, "isOriginal": True, "currency": "GBP"}]})
    assert (pounds["salary_min"], pounds["salary_max"]) == (None, None)
    empty = apify._parse_hollylist({"company": {}, "description": {}, "dates": {}})
    assert (empty["company"], empty["location"], empty["description"]) == ("", "", "")


def test_parse_indeed_keeps_annual_salary_only():
    j = apify._parse_indeed({"positionName": "PM", "company": "Acme", "location": "Austin, TX",
                             "url": "https://www.indeed.com/viewjob?jk=abc", "description": "Do things",
                             "salary": "$120,000 - $150,000 a year", "postedAt": "2 days ago"})
    assert (j["title"], j["company"], j["url"]) == ("PM", "Acme", "https://www.indeed.com/viewjob?jk=abc")
    assert (j["salary_min"], j["salary_max"]) == (120000, 150000)
    hourly = apify._parse_indeed({"salary": "$25 - $30 an hour"})
    assert (hourly["salary_min"], hourly["salary_max"]) == (None, None)
    assert apify._parse_indeed({})["title"] == ""


def test_parse_linkedin_builds_the_shared_view_url():
    j = apify._parse_linkedin({
        "id": "4219847745", "url": "https://www.linkedin.com/jobs/view/c%2B%2B-engineer-at-x-4219847745",
        "title": "C++ Engineer", "companyName": "Goliath", "location": "New York, NY",
        "salary": "$250,000.00/yr - $300,000.00/yr", "postedDate": "2026-10-01", "description": "Text"})
    assert j["url"] == "https://www.linkedin.com/jobs/view/4219847745"
    assert (j["company"], j["location"], j["posted"]) == ("Goliath", "New York, NY", "2026-10-01")
    assert (j["salary_min"], j["salary_max"]) == (250000, 300000)
    assert apify._parse_linkedin({"salary": "$45.00/hr - $50.00/hr"})["salary_min"] is None
    assert apify._parse_linkedin({"id": "", "url": "https://x/1"})["url"] == "https://x/1"


def test_linkedin_url_dedups_with_the_other_linkedin_sources():
    from backend.scraper._shared.dedup import make_external_id
    ours = apify._parse_linkedin({"id": "4219847745"})["url"]
    assert make_external_id("a", "b", ours) == make_external_id("a", "b", "https://www.linkedin.com/jobs/view/4219847745/")


def test_parse_glassdoor_maps_nested_fields_and_strips_html():
    j = apify._parse_glassdoor({
        "title": "Senior Engineer", "url": "https://www.glassdoor.com/job-listing/j?jl=1010062906489",
        "employer": {"name": "GEICO"}, "location": {"name": "New York, NY"}, "ageInDays": 0,
        "pay": {"period": "ANNUAL", "min": 100000, "max": 215000, "currency": "USD"},
        "description": "<div><p>Build <b>things</b></p></div>"})
    assert (j["company"], j["location"]) == ("GEICO", "New York, NY")
    assert (j["salary_min"], j["salary_max"]) == (100000, 215000)
    assert "<" not in j["description"] and "Build things" in j["description"]
    assert len(j["posted"]) == 10                    # an ISO date from ageInDays
    hourly = apify._parse_glassdoor({"pay": {"period": "HOURLY", "min": 40, "max": 60}})
    assert (hourly["salary_min"], hourly["salary_max"]) == (None, None)
    assert apify._parse_glassdoor({})["company"] == "" and apify._parse_glassdoor({})["posted"] is None


def test_parse_career_site_maps_fields():
    j = apify._parse_career_site({
        "title": "TPM", "organization": "Stripe", "url": "https://job-boards.greenhouse.io/stripe/jobs/1",
        "locations_derived": ["San Francisco, California, United States"], "description_text": "Text",
        "ai_salary_unit_text": "YEAR", "ai_salary_min_value": 180000, "ai_salary_max_value": 220000,
        "ai_work_arrangement": "Remote Solely", "date_posted": "2026-10-01T00:00:00"})
    assert j["company"] == "Stripe" and j["location"].startswith("San Francisco")
    assert (j["salary_min"], j["salary_max"]) == (180000, 220000)
    assert j["arrangement"] == "remote"


def test_parse_career_site_tolerates_objects_and_hourly_pay():
    j = apify._parse_career_site({"locations_derived": [{"city": "Austin", "admin": "Texas", "country": "United States"}],
                                  "ai_salary_unit_text": "HOUR", "ai_salary_min_value": 60})
    assert j["location"] == "Austin, Texas, United States"
    assert j["salary_min"] is None
    assert apify._parse_career_site({"locations_alt": ["Remote"]})["location"] == "Remote"


# ── Apify REST cycle ────────────────────────────────────────────────────────

def _transport(statuses, items=None, fail=None):
    """Answer start → one status per poll → dataset items, recording every request."""
    seen = []
    polls = iter(statuses)

    def handler(req: httpx.Request):
        seen.append((req.method, req.url.path, dict(req.url.params)))
        if fail:
            return httpx.Response(fail, json={"error": {"message": "nope"}})
        if req.method == "POST" and req.url.path.endswith("/runs"):
            return httpx.Response(201, json={"data": {"id": "R1", "status": "RUNNING", "defaultDatasetId": "D1"}})
        if req.method == "POST" and req.url.path.endswith("/abort"):
            return httpx.Response(200, json={"data": {"id": "R1", "status": "ABORTED"}})
        if req.url.path == "/v2/actor-runs/R1":
            status = next(polls)
            return httpx.Response(200, json={"data": {"id": "R1", "status": status,
                                                      "defaultDatasetId": "D1", "statusMessage": "boom"}})
        if req.url.path == "/v2/datasets/D1/items":
            return httpx.Response(200, json=items or [])
        return httpx.Response(500)
    return httpx.MockTransport(handler), seen


@pytest.mark.asyncio
async def test_run_actor_polls_until_success_and_reads_the_dataset():
    transport, seen = _transport(["RUNNING", "SUCCEEDED"], items=[{"positionName": "PM"}])
    async with httpx.AsyncClient(transport=transport) as client:
        items = await apify._run_actor(client, "misceres/indeed-scraper", {"position": "pm"}, 7, 0.25)
    assert items == [{"positionName": "PM"}]
    # C1: every start carries the item cap, a spend cap and the platform-side timeout
    assert seen[0][1] == "/v2/acts/misceres~indeed-scraper/runs"
    assert seen[0][2] == {"maxItems": "7", "maxTotalChargeUsd": "0.25", "timeout": str(15 * 60)}
    assert seen[-1][2]["limit"] == "7"


@pytest.mark.asyncio
async def test_run_actor_without_a_cap_still_sends_the_ceiling():
    transport, seen = _transport(["SUCCEEDED"])
    async with httpx.AsyncClient(transport=transport) as client:
        await apify._run_actor(client, "a/b", {}, 5)
    assert float(seen[0][2]["maxTotalChargeUsd"]) == apify._MAX_CHARGE_USD
    assert int(seen[0][2]["timeout"]) == apify._MAX_WAIT


@pytest.mark.parametrize("key,limit,expected", [
    ("apify_greenhouse", 50, 0.90),      # 50 × $12/1k × 1.5
    ("apify_indeed", 200, 1.80),         # 200 × $6/1k × 1.5
    ("apify_linkedin", 20, 0.10),        # cents, raised to the floor
    ("apify_greenhouse", 100000, 5.00),  # never above the ceiling
])
def test_charge_cap_follows_results_and_price(key, limit, expected):
    assert apify.charge_cap_usd(apify.PRESETS[key], limit) == pytest.approx(expected)


@pytest.mark.asyncio
async def test_collect_sends_each_board_its_own_cap(monkeypatch, test_db):
    test_db.add(Setting(key="apify_api_key", value="tok"))
    test_db.commit()
    caps = {}

    async def fake_run_actor(client, actor, body, limit, max_charge_usd=None):
        caps[actor] = (limit, max_charge_usd)
        return []
    monkeypatch.setattr(apify, "_run_actor", fake_run_actor)
    await apify._collect(_search(sources=["apify_indeed", "apify_greenhouse"]), 40)
    assert caps["misceres/indeed-scraper"] == (40, apify.charge_cap_usd(apify.PRESETS["apify_indeed"], 40))
    assert caps["fantastic-jobs/career-site-job-listing-api"] == (
        40, apify.charge_cap_usd(apify.PRESETS["apify_greenhouse"], 40))


@pytest.mark.parametrize("value,expected", [(None, 50), (0, 1), (-5, 1), (30, 30), (200, 200),
                                            (5000, 200), ("x", 50)])
def test_clamp_results(value, expected):
    assert apify.clamp_results(value) == expected


@pytest.mark.asyncio
async def test_run_clamps_results_wanted(monkeypatch, test_db):
    search = Search(name="big", search_mode="apify", search_term="pm", sources=["apify_linkedin"],
                    results_wanted=5000, company_exclude=[])
    test_db.add(search)
    test_db.commit()
    seen = {}

    async def fake_collect(_search, limit):
        seen["limit"] = limit
        return [], {"apify_linkedin": {"seen": 0, "new": 0, "returned": 0}}
    monkeypatch.setattr(apify, "_collect", fake_collect)
    await apify.run(search)
    assert seen["limit"] == apify.MAX_RESULTS


def test_board_keys_never_collide_with_jobspy_boards():
    """C4: a search whose sources still hold JobSpy boards picks no Apify board."""
    from backend.scraper.search_modes import JOBSPY_BOARDS
    jobspy = set(JOBSPY_BOARDS)
    assert all(k.startswith("apify_") for k in apify.PRESETS)
    assert not jobspy & set(apify.PRESETS)
    assert apify.configured_presets(_search(sources=sorted(jobspy))) == []


@pytest.mark.asyncio
async def test_run_actor_reports_a_failed_run():
    transport, _ = _transport(["FAILED"])
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(apify.ApifyError, match="R1 FAILED: boom"):
            await apify._run_actor(client, "a/b", {}, 5)


@pytest.mark.asyncio
async def test_run_actor_aborts_a_run_past_the_deadline(monkeypatch):
    monkeypatch.setattr(apify, "_MAX_WAIT", -1)
    transport, seen = _transport([])
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(apify.ApifyError, match="aborted"):
            await apify._run_actor(client, "a/b", {}, 5)
    assert ("POST", "/v2/actor-runs/R1/abort", {}) in seen


@pytest.mark.asyncio
async def test_run_actor_names_a_rejected_key():
    transport, _ = _transport([], fail=401)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(apify.ApifyError, match="401: the Apify API key is wrong or revoked; nope"):
            await apify._run_actor(client, "a/b", {}, 5)


@pytest.mark.asyncio
async def test_collect_without_a_key_fails_before_any_request(test_db):
    with pytest.raises(apify.ApifyError, match="not set"):
        await apify._collect(_search(), 5)


@pytest.mark.asyncio
async def test_collect_keeps_the_board_that_worked(monkeypatch, test_db):
    test_db.add(Setting(key="apify_api_key", value="tok"))
    test_db.commit()

    async def fake_run_actor(client, actor, body, limit, max_charge_usd=None):
        if "indeed" in actor:
            raise apify.ApifyError("HTTP 402: the Apify account has no credit left")
        return [{"title": "TPM", "organization": "Stripe", "url": "https://gh/1"},
                {"title": "TPM", "organization": "Stripe", "url": "https://gh/1"}]
    monkeypatch.setattr(apify, "_run_actor", fake_run_actor)

    jobs, breakdown = await apify._collect(_search(), 5)
    assert [j["url"] for j in jobs] == ["https://gh/1"]
    assert breakdown["apify_indeed"]["error"].startswith("HTTP 402")
    assert breakdown["apify_greenhouse"] == {"seen": 0, "new": 0, "returned": 2}


# ── save pipeline ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_saves_dedups_filters_and_counts_per_board(monkeypatch, test_db):
    search = Search(name="t", search_mode="apify", search_term="engineer", sources=["apify_indeed", "apify_greenhouse"],
                    results_wanted=10, title_exclude_keywords=["intern"], company_exclude=[])
    test_db.add(search)
    test_db.commit()

    async def fake_collect(_search, limit):
        return [
            _job("Backend Engineer", "Acme", "https://www.indeed.com/viewjob?jk=1", salary_min=150000, salary_max=180000),
            _job("Data Intern", "Acme", "https://www.indeed.com/viewjob?jk=2"),
            _job("Platform Engineer", "Stripe", "https://gh/1", source="apify_greenhouse", arrangement="remote"),
        ], {"apify_indeed": {"seen": 0, "new": 0, "returned": 2}, "apify_greenhouse": {"seen": 0, "new": 0, "returned": 1}}
    monkeypatch.setattr(apify, "_collect", fake_collect)
    arrangements = []

    async def fake_analyze(job, db=None, arrangement=None):
        arrangements.append(arrangement)
    monkeypatch.setattr(apify, "analyze_inline", fake_analyze)
    monkeypatch.setattr("backend.activity.log_activity", lambda *a, **k: None)

    res = await apify.run(search)
    assert res["error"] is None and res["new_jobs"] == 2 and res["jobs_found"] == 2
    assert res["source_breakdown"]["apify_indeed"] == {"seen": 1, "new": 1, "returned": 2, "filtered": 1}
    assert res["source_breakdown"]["apify_greenhouse"] == {"seen": 1, "new": 1, "returned": 1}
    assert arrangements == [None, "remote"]
    from backend.scraper.orchestrator import summarize_search_run
    assert summarize_search_run("apify", res) == "apify - 2 seen, +2 new, 1 filtered out"

    test_db.expire_all()
    saved = {j.title: j for j in test_db.query(Job).all()}
    assert set(saved) == {"Backend Engineer", "Platform Engineer"}
    assert saved["Backend Engineer"].source == "apify_indeed"
    assert (saved["Backend Engineer"].salary_min, saved["Backend Engineer"].salary_source) == (150000, "posting")
    assert saved["Platform Engineer"].source == "apify_greenhouse"

    res = await apify.run(search)                   # same postings again
    assert res["new_jobs"] == 0


@pytest.mark.asyncio
async def test_run_reports_an_error_when_every_board_failed(monkeypatch, test_db):
    search = Search(name="t", search_mode="apify", search_term="x", sources=["apify_indeed"], company_exclude=[])
    test_db.add(search)
    test_db.commit()

    async def fake_collect(_search, limit):
        return [], {"apify_indeed": {"seen": 0, "new": 0, "error": "HTTP 401: bad key"}}
    monkeypatch.setattr(apify, "_collect", fake_collect)
    monkeypatch.setattr("backend.activity.log_activity", lambda *a, **k: None)

    res = await apify.run(search)
    assert res["error"] == "Indeed: HTTP 401: bad key"


@pytest.mark.asyncio
async def test_preview_caps_the_fetch_and_explains_rejections(monkeypatch, test_db):
    test_db.add(Setting(key="body_exclusion_phrases", value=json.dumps(["us citizen only"])))
    test_db.commit()
    limits = []

    async def fake_collect(_search, limit):
        limits.append(limit)
        return [_job("Backend Engineer", "Acme", "https://a/1"),
                _job("Data Intern", "Acme", "https://a/2"),
                _job("Senior Engineer", "Acme", "https://a/3", desc="US citizen only please")], \
            {"apify_indeed": {"seen": 0, "new": 0, "returned": 3}, "apify_greenhouse": {"seen": 0, "new": 0, "error": "HTTP 402"}}
    monkeypatch.setattr(apify, "_collect", fake_collect)

    search = Search(name="t", search_mode="apify", search_term="engineer", sources=["apify_indeed", "apify_greenhouse"],
                    results_wanted=400, title_exclude_keywords=["intern"], company_exclude=[])
    r = await apify.preview(search, test_db)

    assert limits == [apify.PREVIEW_LIMIT]
    by = {j["title"]: j for j in r["jobs"]}
    assert by["Backend Engineer"]["kept"] is True
    assert "intern" in by["Data Intern"]["reason"].lower()
    assert by["Senior Engineer"]["reason"].startswith("Body exclusion")
    assert r["source_breakdown"] == {"apify_indeed": 3}
    assert r["source_errors"] == {"apify_greenhouse": "HTTP 402"}


# ── Remote only on LinkedIn ─────────────────────────────────────────────────

_HYBRID_JD = "You work 3 days per week in the office in Austin."
_ONSITE_JD = "This role is fully on-site in Austin."
_REMOTE_JD = "This is a fully remote role across the US."


@pytest.mark.parametrize("source,desc,remote_only,expected", [
    ("apify_linkedin", _HYBRID_JD, True, "Not remote: hybrid"),
    ("apify_linkedin", _ONSITE_JD, True, "Not remote: onsite"),
    ("apify_linkedin", _REMOTE_JD, True, None),
    ("apify_linkedin", "Great role", True, None),        # unknown stays: the cascade never guesses
    ("apify_linkedin", _HYBRID_JD, False, None),         # Any: nothing to enforce
    ("apify_indeed", _HYBRID_JD, True, None),            # Indeed applies Remote itself
])
def test_remote_only_drops_linkedin_rows_the_posting_calls_hybrid_or_onsite(source, desc, remote_only, expected):
    j = _job("SRE", "Acme", "https://www.linkedin.com/jobs/view/1", source=source, desc=desc)
    assert apify._rejection(j, [], [], set(), set(), None, remote_only) == expected


@pytest.mark.asyncio
async def test_remote_only_linkedin_rows_are_filtered_in_run_and_preview(monkeypatch, test_db):
    search = Search(name="t", search_mode="apify", search_term="sre", sources=["apify_linkedin"],
                    is_remote=True, results_wanted=10, company_exclude=[])
    test_db.add(search)
    test_db.commit()

    async def fake_collect(_search, limit):
        return [_job("SRE", "Acme", "https://www.linkedin.com/jobs/view/1", source="apify_linkedin", desc=_REMOTE_JD),
                _job("SRE", "Initech", "https://www.linkedin.com/jobs/view/2", source="apify_linkedin", desc=_HYBRID_JD)],             {"apify_linkedin": {"seen": 0, "new": 0, "returned": 2}}
    monkeypatch.setattr(apify, "_collect", fake_collect)
    monkeypatch.setattr("backend.activity.log_activity", lambda *a, **k: None)

    async def no_analysis(job, db=None, arrangement=None):
        pass
    monkeypatch.setattr(apify, "analyze_inline", no_analysis)

    r = await apify.preview(search, test_db)
    assert {j["company"]: j["reason"] for j in r["jobs"]} == {"Acme": None, "Initech": "Not remote: hybrid"}

    res = await apify.run(search)
    assert res["source_breakdown"]["apify_linkedin"] == {"seen": 1, "new": 1, "returned": 2, "filtered": 1}
    test_db.expire_all()
    assert [j.company for j in test_db.query(Job).all()] == ["Acme"]


# ── wiring ──────────────────────────────────────────────────────────────────

def test_validity_needs_a_term_and_a_known_board():
    from backend.scraper import orchestrator
    ok = orchestrator._search_mode_is_valid
    assert ok(Search(search_mode="apify", search_term="pm", sources=["apify_indeed"])) is True
    assert ok(Search(search_mode="apify", search_term="pm", sources=["monster"])) is False
    assert ok(Search(search_mode="apify", search_term=" ", sources=["apify_indeed"])) is False


@pytest.mark.asyncio
async def test_dispatch_routes_to_apify(monkeypatch):
    from backend.scraper import orchestrator
    called = {}

    async def fake_run(search, **kw):
        called["ok"] = True
        return {"jobs_found": 0, "new_jobs": 0, "error": None, "duration": 0}
    monkeypatch.setattr(apify, "run", fake_run)
    await orchestrator.run_search(Search(search_mode="apify", search_term="pm", sources=["apify_indeed"]))
    assert called.get("ok") is True
    assert orchestrator._source_for_search(Search(search_mode="apify")) == "apify"


def test_boards_endpoint_lists_every_preset_in_order(api_client):
    boards = api_client.get("/api/searches/apify-boards").json()
    assert [b["value"] for b in boards] == list(apify.PRESETS)
    assert {k: boards[0][k] for k in ("value", "label", "actor")} ==         {"value": "apify_indeed", "label": "Indeed", "actor": "misceres/indeed-scraper"}
    assert boards[0]["price_per_1k"] == 6.0 and boards[0]["preview_limit"] == apify.PREVIEW_LIMIT
    assert boards[0]["test_max_usd"] == apify.charge_cap_usd(apify.PRESETS["apify_indeed"], apify.PREVIEW_LIMIT)
    assert all(b["max_results"] == apify.MAX_RESULTS for b in boards)
    assert all(b["hint"] for b in boards)


def test_key_is_a_known_redacted_setting(api_client):
    assert api_client.patch("/api/settings", json={"apify_api_key": "apify_api_secret"}).status_code == 200
    assert api_client.get("/api/settings").json()["apify_api_key"] == "•" * 6


def _probe_transport(run_status, run_body=None):
    """users/me → 200, then the plan probe answers `run_status`."""
    seen = []

    def handler(req):
        seen.append((req.method, req.url.path, dict(req.url.params), req.content))
        if req.url.path == "/v2/users/me":
            return httpx.Response(200, json={"data": {"username": "jane"}})
        if req.url.path.endswith("/abort"):
            return httpx.Response(200, json={"data": {}})
        return httpx.Response(run_status, json=run_body or {})
    return httpx.MockTransport(handler), seen


@pytest.fixture
def stored_key(monkeypatch):
    monkeypatch.setattr(apify, "_token", lambda: "tok")


def _patch_client(monkeypatch, transport):
    monkeypatch.setattr(apify, "_client", lambda token, read: httpx.AsyncClient(transport=transport))


@pytest.mark.asyncio
async def test_account_name_passes_when_the_plan_rejects_only_the_input(monkeypatch, stored_key):
    transport, seen = _probe_transport(400, {"error": {"type": "invalid-input", "message": "bad"}})
    _patch_client(monkeypatch, transport)
    assert await apify.account_name() == "jane"
    method, path, params, content = seen[1]
    assert (method, path) == ("POST", "/v2/acts/misceres~indeed-scraper/runs")
    assert params == {"timeout": "1", "memory": "128", "maxTotalChargeUsd": "0.001"}
    assert content == b"[]"                       # not an object: the schema refuses it


@pytest.mark.asyncio
async def test_account_name_names_a_creator_plan(monkeypatch, stored_key):
    transport, _ = _probe_transport(403, {"error": {"type": apify.PLAN_BLOCKS_STORE,
                                                    "message": "You cannot run this public Actor."}})
    _patch_client(monkeypatch, transport)
    with pytest.raises(apify.ApifyError, match="Creator plan blocks them.*console.apify.com/billing"):
        await apify.account_name()


@pytest.mark.asyncio
async def test_account_name_aborts_a_probe_run_that_started(monkeypatch, stored_key):
    transport, seen = _probe_transport(201, {"data": {"id": "R9"}})
    _patch_client(monkeypatch, transport)
    assert await apify.account_name() == "jane"
    assert ("POST", "/v2/actor-runs/R9/abort") in [(m, p) for m, p, *_ in seen]


@pytest.mark.asyncio
async def test_a_board_refused_by_the_plan_says_what_to_do():
    transport, _ = _transport([], fail=403)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(apify.ApifyError, match="HTTP 403: the Apify API key cannot run this actor"):
            await apify._run_actor(client, "a/b", {}, 5)

    def creator(req):
        return httpx.Response(403, json={"error": {"type": apify.PLAN_BLOCKS_STORE, "message": "x"}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(creator)) as client:
        with pytest.raises(apify.ApifyError, match="cannot run Apify Store actors"):
            await apify._run_actor(client, "a/b", {}, 5)


def test_key_check_names_the_account(monkeypatch, api_client):
    async def fake_account():
        return "jane"
    monkeypatch.setattr(apify, "account_name", fake_account)
    assert api_client.post("/api/settings/apify/check").json() == {"ok": True, "username": "jane"}


def test_key_check_without_a_key_is_400(api_client):
    r = api_client.post("/api/settings/apify/check")
    assert r.status_code == 400 and "not set" in r.json()["detail"]


# ── cost guards on the search routes (C2, C3, C4) ───────────────────────────

def _new_apify(api_client, **kw):
    body = {"name": "Apify PM", "search_mode": "apify", "search_term": "pm",
            "sources": ["apify_linkedin"], **kw}
    return api_client.post("/api/searches", json=body)


def test_new_apify_search_starts_paused(api_client):
    r = _new_apify(api_client)
    assert r.status_code == 200 and r.json()["active"] is False


def test_new_apify_search_active_when_asked(api_client):
    assert _new_apify(api_client, active=True).json()["active"] is True


def test_new_keyword_search_still_starts_active(api_client):
    r = api_client.post("/api/searches", json={"name": "kw", "search_term": "pm"})
    assert r.status_code == 200 and r.json()["active"] is True


def test_apify_results_wanted_is_clamped_on_create_and_patch(api_client):
    r = _new_apify(api_client, results_wanted=5000)
    assert r.json()["results_wanted"] == apify.MAX_RESULTS
    sid = r.json()["id"]
    assert api_client.patch(f"/api/searches/{sid}", json={"results_wanted": 900}).json()["results_wanted"] == apify.MAX_RESULTS
    assert api_client.patch(f"/api/searches/{sid}", json={"results_wanted": 30}).json()["results_wanted"] == 30


def test_apify_search_without_apify_boards_is_400(api_client):
    # no `sources`: nothing reaches the paid source (an Apify search has no default board)
    r = api_client.post("/api/searches", json={"name": "x", "search_mode": "apify", "search_term": "pm"})
    assert r.status_code == 400 and "needs at least one Apify board" in r.json()["detail"]
    r = api_client.post("/api/searches", json={"name": "x", "search_mode": "apify", "search_term": "pm",
                                               "sources": ["linkedin", "indeed"]})
    assert r.status_code == 400 and "not Apify boards: linkedin, indeed" in r.json()["detail"]
    assert _new_apify(api_client, sources=[]).status_code == 400
    assert _new_apify(api_client, sources=["apify_indeed", "indeed"]).status_code == 400


def test_patching_a_keyword_search_to_apify_needs_boards_and_pauses_it(api_client):
    sid = api_client.post("/api/searches", json={"name": "kw", "search_term": "pm",
                                                 "results_wanted": 400}).json()["id"]
    r = api_client.patch(f"/api/searches/{sid}", json={"search_mode": "apify"})
    assert r.status_code == 400                     # stored sources are JobSpy boards
    assert api_client.get("/api/searches").json()[-1]["search_mode"] == "keyword"   # row untouched
    r = api_client.patch(f"/api/searches/{sid}", json={"search_mode": "apify", "sources": ["apify_glassdoor"]})
    assert r.status_code == 200
    assert (r.json()["active"], r.json()["results_wanted"], r.json()["sources"]) == (False, apify.MAX_RESULTS, ["apify_glassdoor"])


def test_patching_an_apify_search_keeps_active_when_not_switching(api_client):
    sid = _new_apify(api_client, active=True).json()["id"]
    r = api_client.patch(f"/api/searches/{sid}", json={"search_term": "tpm"})
    assert r.status_code == 200 and r.json()["active"] is True
    assert api_client.patch(f"/api/searches/{sid}", json={"sources": ["linkedin"]}).status_code == 400


def test_copied_apify_search_is_paused():
    from backend.accounts.admin import _search_copy
    import uuid
    src = Search(name="a", search_mode="apify", active=True, sources=["apify_indeed"])
    assert _search_copy(src, Search, uuid.uuid4()).active is False
    kw = Search(name="k", search_mode="keyword", active=True, sources=["indeed"])
    assert _search_copy(kw, Search, uuid.uuid4()).active is True


def test_apify_searches_are_never_a_shared_target():
    """M3 (deferred): each account runs and pays separately, so no shared key."""
    from backend.scraper import targets
    a = Search(id=uuid_mod.uuid4(), search_mode="apify", search_term="pm", sources=["apify_indeed"])
    b = Search(id=uuid_mod.uuid4(), search_mode="apify", search_term="pm", sources=["apify_indeed"])
    assert targets.is_shareable_search(a) is False
    assert targets.search_key(a) == ("apify", "own", str(a.id))
    assert targets.search_key(a) != targets.search_key(b)
