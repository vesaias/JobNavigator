"""Apify source: actor input, item parsing, the run/poll/abort cycle, the save pipeline and the wiring (no network)."""
import json
from types import SimpleNamespace

import httpx
import pytest

from backend.models.db import Job, Search, Setting
from backend.scraper.sources import apify


def _search(**kw):
    base = dict(name="t", search_mode="apify", search_term="program manager", location="",
                country="usa", is_remote=None, hours_old=24, results_wanted=30,
                sources=["indeed", "greenhouse"])
    base.update(kw)
    return SimpleNamespace(**base)


def _job(title, company, url, source="indeed", desc="Great role", **kw):
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
    return apify.PRESETS["greenhouse"].build_input(search, limit)


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


@pytest.mark.parametrize("key,ats,label", [("greenhouse", "greenhouse", "Greenhouse"), ("lever", "lever.co", "Lever"),
                                           ("ashby", "ashby", "Ashby"), ("workday", "workday", "Workday")])
def test_ats_boards_share_the_career_site_actor(key, ats, label):
    preset = apify.PRESETS[key]
    assert preset.actor == "fantastic-jobs/career-site-job-listing-api"
    assert preset.parse is apify._parse_career_site
    assert preset.label == label and label in preset.hint
    assert preset.build_input(_search(), 20)["ats"] == [ats]   # a value of the actor's `ats` enum


def test_source_label_names_apify_boards():
    from backend.scraper.orchestrator import source_label
    assert source_label("zip_recruiter") == "ZipRecruiter"
    assert source_label("workday") == "Workday"
    assert source_label("lever") == "Lever"
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


def test_glassdoor_input_always_has_a_location_and_whole_days():
    body = apify._glassdoor_input(_search(hours_old=25, is_remote=True), 30)
    assert body["location"] == "United States"       # required by the actor
    assert body["daysOld"] == 2
    assert body["remoteWorkType"] is True
    assert body["sortBy"] == "date_desc"
    assert "daysOld" not in apify._glassdoor_input(_search(hours_old=None), 30)


# ── item parsing ────────────────────────────────────────────────────────────

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
        items = await apify._run_actor(client, "misceres/indeed-scraper", {"position": "pm"}, 7)
    assert items == [{"positionName": "PM"}]
    assert seen[0][1] == "/v2/acts/misceres~indeed-scraper/runs" and seen[0][2] == {"maxItems": "7"}
    assert seen[-1][2]["limit"] == "7"


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

    async def fake_run_actor(client, actor, body, limit):
        if "indeed" in actor:
            raise apify.ApifyError("HTTP 402: the Apify account has no credit left")
        return [{"title": "TPM", "organization": "Stripe", "url": "https://gh/1"},
                {"title": "TPM", "organization": "Stripe", "url": "https://gh/1"}]
    monkeypatch.setattr(apify, "_run_actor", fake_run_actor)

    jobs, breakdown = await apify._collect(_search(), 5)
    assert [j["url"] for j in jobs] == ["https://gh/1"]
    assert breakdown["indeed"]["error"].startswith("HTTP 402")
    assert breakdown["greenhouse"] == {"seen": 0, "new": 0, "returned": 2}


# ── save pipeline ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_saves_dedups_filters_and_counts_per_board(monkeypatch, test_db):
    search = Search(name="t", search_mode="apify", search_term="engineer", sources=["indeed", "greenhouse"],
                    results_wanted=10, title_exclude_keywords=["intern"], company_exclude=[])
    test_db.add(search)
    test_db.commit()

    async def fake_collect(_search, limit):
        return [
            _job("Backend Engineer", "Acme", "https://www.indeed.com/viewjob?jk=1", salary_min=150000, salary_max=180000),
            _job("Data Intern", "Acme", "https://www.indeed.com/viewjob?jk=2"),
            _job("Platform Engineer", "Stripe", "https://gh/1", source="greenhouse", arrangement="remote"),
        ], {"indeed": {"seen": 0, "new": 0, "returned": 2}, "greenhouse": {"seen": 0, "new": 0, "returned": 1}}
    monkeypatch.setattr(apify, "_collect", fake_collect)
    arrangements = []

    async def fake_analyze(job, db=None, arrangement=None):
        arrangements.append(arrangement)
    monkeypatch.setattr(apify, "analyze_inline", fake_analyze)
    monkeypatch.setattr("backend.activity.log_activity", lambda *a, **k: None)

    res = await apify.run(search)
    assert res["error"] is None and res["new_jobs"] == 2 and res["jobs_found"] == 2
    assert res["source_breakdown"]["indeed"] == {"seen": 1, "new": 1, "returned": 2, "filtered": 1}
    assert res["source_breakdown"]["greenhouse"] == {"seen": 1, "new": 1, "returned": 1}
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
    search = Search(name="t", search_mode="apify", search_term="x", sources=["indeed"], company_exclude=[])
    test_db.add(search)
    test_db.commit()

    async def fake_collect(_search, limit):
        return [], {"indeed": {"seen": 0, "new": 0, "error": "HTTP 401: bad key"}}
    monkeypatch.setattr(apify, "_collect", fake_collect)
    monkeypatch.setattr("backend.activity.log_activity", lambda *a, **k: None)

    res = await apify.run(search)
    assert res["error"] == "indeed: HTTP 401: bad key"


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
            {"indeed": {"seen": 0, "new": 0, "returned": 3}, "greenhouse": {"seen": 0, "new": 0, "error": "HTTP 402"}}
    monkeypatch.setattr(apify, "_collect", fake_collect)

    search = Search(name="t", search_mode="apify", search_term="engineer", sources=["indeed", "greenhouse"],
                    results_wanted=400, title_exclude_keywords=["intern"], company_exclude=[])
    r = await apify.preview(search, test_db)

    assert limits == [apify.PREVIEW_LIMIT]
    by = {j["title"]: j for j in r["jobs"]}
    assert by["Backend Engineer"]["kept"] is True
    assert "intern" in by["Data Intern"]["reason"].lower()
    assert by["Senior Engineer"]["reason"].startswith("Body exclusion")
    assert r["source_breakdown"] == {"indeed": 3}
    assert r["source_errors"] == {"greenhouse": "HTTP 402"}


# ── wiring ──────────────────────────────────────────────────────────────────

def test_validity_needs_a_term_and_a_known_board():
    from backend.scraper import orchestrator
    ok = orchestrator._search_mode_is_valid
    assert ok(Search(search_mode="apify", search_term="pm", sources=["indeed"])) is True
    assert ok(Search(search_mode="apify", search_term="pm", sources=["monster"])) is False
    assert ok(Search(search_mode="apify", search_term=" ", sources=["indeed"])) is False


@pytest.mark.asyncio
async def test_dispatch_routes_to_apify(monkeypatch):
    from backend.scraper import orchestrator
    called = {}

    async def fake_run(search, **kw):
        called["ok"] = True
        return {"jobs_found": 0, "new_jobs": 0, "error": None, "duration": 0}
    monkeypatch.setattr(apify, "run", fake_run)
    await orchestrator.run_search(Search(search_mode="apify", search_term="pm", sources=["indeed"]))
    assert called.get("ok") is True
    assert orchestrator._source_for_search(Search(search_mode="apify")) == "apify"


def test_boards_endpoint_lists_every_preset_in_order(api_client):
    boards = api_client.get("/api/searches/apify-boards").json()
    assert [b["value"] for b in boards] == list(apify.PRESETS)
    assert {k: boards[0][k] for k in ("value", "label", "actor")} ==         {"value": "indeed", "label": "Indeed", "actor": "misceres/indeed-scraper"}
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
