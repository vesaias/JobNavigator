"""R4-T1 · /api/searches and /api/companies contract under bad input.

Both routers share a shape: a Pydantic create model, a PATCH that silently drops
keys outside an allow-list, a DELETE that orphans audit rows, and a 202 trigger
that answers 409 while a run with the same scope key is live.
"""
import pytest

from backend.tests.r4_support import (  # noqa: F401
    client, _clear_running_state, _no_outbound, assert_clean, assert_no_leak,
    make_company, make_search, big_string, EMOJI, MISSING_UUID,
)


# ══ Searches ═════════════════════════════════════════════════════════════════

def test_create_search_requires_a_name(client):
    assert_clean(client.post("/api/searches", json={}), 422)


@pytest.mark.parametrize("bad", [None, 5, [], {}])
def test_create_search_rejects_a_wrongly_typed_name(client, bad):
    assert_clean(client.post("/api/searches", json={"name": bad}), 422)


def test_create_search_accepts_an_empty_name(client):
    """Current contract: `name: str` with no min_length."""
    assert_clean(client.post("/api/searches", json={"name": ""}), 200)


def test_create_search_applies_every_documented_default(client):
    r = assert_clean(client.post("/api/searches", json={"name": "S"}), 200)
    body = r.json()
    assert body["search_mode"] == "keyword"
    assert body["active"] is True
    assert body["title_exclude_keywords"] == ["intern", "junior", "associate"]


def test_create_search_drops_unknown_fields(client):
    """extra='ignore' — a stray key must never reach Search(**model_dump())."""
    assert_clean(client.post("/api/searches",
                             json={"name": "S", "id": MISSING_UUID, "bogus": 1}), 200)


def test_create_search_unicode_name(client):
    r = assert_clean(client.post("/api/searches", json={"name": EMOJI}), 200)
    assert r.json()["name"] == EMOJI


def test_create_search_ten_megabyte_search_term(client):
    r = client.post("/api/searches", json={"name": "Big", "search_term": big_string(10)})
    assert_clean(r, 200, 400, 413, 422)


@pytest.mark.parametrize("field,value", [
    ("max_pages", -1), ("max_pages", 0), ("min_fit_score", -5), ("min_fit_score", 1000),
    ("hours_old", -24), ("results_wanted", -1), ("results_wanted", 10 ** 9),
    ("run_interval_minutes", -1),
])
def test_create_search_stores_out_of_range_numbers_verbatim(client, field, value):
    """Current contract: plain ints with no bounds. Recorded so a later guard is a visible change."""
    r = assert_clean(client.post("/api/searches", json={"name": f"S{field}{value}", field: value}), 200)
    assert r.json().get(field, value) == value


@pytest.mark.xfail(strict=True, reason="R4-T1-17")
def test_create_search_rejects_a_negative_interval(client):
    """A negative run_interval_minutes silently disables the per-search schedule."""
    assert client.post("/api/searches",
                       json={"name": "Neg", "run_interval_minutes": -30}).status_code == 422


@pytest.mark.parametrize("mode", ["keyword", "levels_fyi", "linkedin_personal",
                                  "jobright", "freehire", "banana", ""])
def test_create_search_accepts_any_search_mode_string(client, mode):
    """No enum guard on search_mode today; the orchestrator falls through on unknown ones."""
    assert_clean(client.post("/api/searches", json={"name": f"m-{mode}", "search_mode": mode}), 200)


@pytest.mark.xfail(strict=True, reason="R4-T1-18")
def test_create_search_rejects_an_unknown_search_mode(client):
    assert client.post("/api/searches",
                       json={"name": "M", "search_mode": "banana"}).status_code == 422


def test_patch_search_missing_id_is_404(client):
    assert_clean(client.patch(f"/api/searches/{MISSING_UUID}", json={"name": "x"}), 404)


def test_patch_search_drops_keys_outside_the_allow_list(client, test_db):
    from backend.models.db import Search
    s = make_search(test_db, name="S")
    assert_clean(client.patch(f"/api/searches/{s.id}",
                              json={"id": MISSING_UUID, "last_run_at": "2020-01-01",
                                    "warning_acknowledged_at": "2020-01-01", "name": "kept"}), 200)
    test_db.refresh(s)
    assert s.name == "kept"
    assert str(s.id) != MISSING_UUID
    assert s.last_run_at is None


def test_patch_search_empty_body_is_a_noop_200(client, test_db):
    s = make_search(test_db)
    assert_clean(client.patch(f"/api/searches/{s.id}", json={}), 200)


@pytest.mark.parametrize("body", [[1], "x", 3, None])
def test_patch_search_non_object_body_is_422(client, test_db, body):
    s = make_search(test_db)
    assert_clean(client.patch(f"/api/searches/{s.id}", json=body), 422)


def test_delete_search_missing_id_is_404(client):
    assert_clean(client.delete(f"/api/searches/{MISSING_UUID}"), 404)


def test_delete_search_twice_is_404_the_second_time(client, test_db):
    s = make_search(test_db)
    assert_clean(client.delete(f"/api/searches/{s.id}"), 200)
    assert_clean(client.delete(f"/api/searches/{s.id}"), 404)


@pytest.mark.parametrize("mode", ["extension", "linkedin_extension"])
def test_extension_searches_refuse_delete_run_and_acknowledge(client, test_db, mode):
    s = make_search(test_db, name=f"Ext {mode}", search_mode=mode)
    assert_clean(client.delete(f"/api/searches/{s.id}"), 409)
    assert_clean(client.post(f"/api/searches/{s.id}/run"), 409)
    assert_clean(client.post(f"/api/searches/{s.id}/acknowledge"), 409)


def test_delete_search_orphans_its_jobs_and_scrape_logs(client, test_db):
    from backend.models.db import Job, ScrapeLog
    from backend.tests.r4_support import make_job
    s = make_search(test_db)
    job = make_job(test_db, search_id=s.id)
    test_db.add(ScrapeLog(search_id=s.id, source="test", jobs_found=1, new_jobs=0))
    test_db.commit()
    assert_clean(client.delete(f"/api/searches/{s.id}"), 200)
    test_db.expire_all()
    assert test_db.get(Job, job.id).search_id is None
    assert test_db.query(ScrapeLog).count() == 1
    assert test_db.query(ScrapeLog).first().search_id is None


def test_run_search_missing_id_is_404(client):
    assert_clean(client.post(f"/api/searches/{MISSING_UUID}/run"), 404)


def test_run_search_second_trigger_on_the_same_scope_is_409(client, test_db, monkeypatch):
    import asyncio
    import backend.scraper.orchestrator as orch
    gate = asyncio.Event()

    async def _slow(search_id, auto_score=None):
        await gate.wait()
        return {}
    monkeypatch.setattr(orch, "_run_search_by_id", _slow, raising=False)

    s = make_search(test_db)
    assert_clean(client.post(f"/api/searches/{s.id}/run"), 202)
    assert_clean(client.post(f"/api/searches/{s.id}/run"), 409)
    gate.set()


def test_run_two_different_searches_at_once_is_allowed(client, test_db, monkeypatch):
    import asyncio
    import backend.scraper.orchestrator as orch
    gate = asyncio.Event()

    async def _slow(search_id, auto_score=None):
        await gate.wait()
        return {}
    monkeypatch.setattr(orch, "_run_search_by_id", _slow, raising=False)

    a = make_search(test_db, name="A")
    b = make_search(test_db, name="B")
    assert_clean(client.post(f"/api/searches/{a.id}/run"), 202)
    assert_clean(client.post(f"/api/searches/{b.id}/run"), 202)
    gate.set()


def test_search_test_result_unknown_run_id_is_404(client):
    assert_clean(client.get("/api/searches/test-result/deadbeef"), 404)


def test_acknowledge_search_missing_id_is_404(client):
    assert_clean(client.post(f"/api/searches/{MISSING_UUID}/acknowledge"), 404)


# ══ Companies ════════════════════════════════════════════════════════════════

def test_create_company_requires_a_name(client):
    assert_clean(client.post("/api/companies", json={}), 422)


def test_create_company_duplicate_name_is_409_case_insensitively(client):
    assert_clean(client.post("/api/companies", json={"name": "Acme"}), 200)
    assert_clean(client.post("/api/companies", json={"name": "ACME"}), 409)
    assert_clean(client.post("/api/companies", json={"name": "acme"}), 409)


def test_create_company_strips_blank_urls_and_aliases(client):
    r = assert_clean(client.post("/api/companies", json={
        "name": "Trim", "scrape_urls": ["", "  ", "https://x.com/careers"],
        "aliases": ["", "  ", "Trim Inc"],
    }), 200)
    assert r.json()["scrape_urls"] == ["https://x.com/careers"]
    assert r.json()["aliases"] == ["Trim Inc"]


@pytest.mark.parametrize("bad", [None, 5, {}, [1, 2]])
def test_create_company_rejects_a_wrongly_typed_name(client, bad):
    assert_clean(client.post("/api/companies", json={"name": bad}), 422)


@pytest.mark.parametrize("field,bad", [
    ("scrape_urls", "https://x.com"), ("scrape_urls", [1, 2]),
    ("selected_resume_ids", "abc"), ("aliases", "x"),
    ("tier", "one"), ("max_pages", "many"), ("scrape_interval_minutes", "soon"),
])
def test_create_company_rejects_wrongly_typed_fields(client, field, bad):
    assert_clean(client.post("/api/companies", json={"name": f"C-{field}", field: bad}), 422)


def test_create_company_unicode_name(client):
    r = assert_clean(client.post("/api/companies", json={"name": EMOJI}), 200)
    assert r.json()["name"] == EMOJI


def test_create_company_ten_megabyte_notes(client):
    r = client.post("/api/companies", json={"name": "Big", "notes": big_string(10)})
    assert_clean(r, 200, 400, 413, 422)


@pytest.mark.parametrize("value", [-1, 0])
def test_create_company_stores_a_non_positive_interval_verbatim(client, value):
    r = assert_clean(client.post("/api/companies",
                                json={"name": f"I{value}", "scrape_interval_minutes": value}), 200)
    assert r.json()["scrape_interval_minutes"] == value


@pytest.mark.xfail(strict=True, reason="R4-T1-17")
def test_create_company_rejects_a_zero_scrape_interval(client):
    """0 means "every 0 minutes" to /api/scheduler/jobs, which is not a schedule."""
    assert client.post("/api/companies",
                       json={"name": "Zero", "scrape_interval_minutes": 0}).status_code == 422


def test_patch_company_missing_id_is_404(client):
    assert_clean(client.patch(f"/api/companies/{MISSING_UUID}", json={"name": "x"}), 404)


def test_patch_company_drops_keys_outside_the_allow_list(client, test_db):
    c = make_company(test_db, name="Acme")
    assert_clean(client.patch(f"/api/companies/{c.id}",
                              json={"id": MISSING_UUID, "last_scraped_at": "2020-01-01",
                                    "notes": "kept"}), 200)
    test_db.refresh(c)
    assert c.notes == "kept"
    assert c.last_scraped_at is None


@pytest.mark.parametrize("body", [[1], "x", 3, None])
def test_patch_company_non_object_body_is_422(client, test_db, body):
    c = make_company(test_db)
    assert_clean(client.patch(f"/api/companies/{c.id}", json=body), 422)


def test_patch_company_to_a_duplicate_name_is_accepted(client, test_db):
    """Current contract: only POST guards the unique name; PATCH does not.

    Under Postgres the unique index turns this into an IntegrityError, so the
    correct behaviour is a 409 — pinned in test_r4_live_contract.py.
    """
    make_company(test_db, name="Acme")
    b = make_company(test_db, name="Beta")
    r = client.patch(f"/api/companies/{b.id}", json={"name": "Acme"})
    assert_no_leak(r)


def test_delete_company_missing_id_is_404(client):
    assert_clean(client.delete(f"/api/companies/{MISSING_UUID}"), 404)


def test_delete_company_orphans_its_scrape_logs(client, test_db):
    from backend.models.db import ScrapeLog
    c = make_company(test_db)
    test_db.add(ScrapeLog(company_id=c.id, source="career_page", jobs_found=0, new_jobs=0))
    test_db.commit()
    assert_clean(client.delete(f"/api/companies/{c.id}"), 200)
    test_db.expire_all()
    assert test_db.query(ScrapeLog).count() == 1
    assert test_db.query(ScrapeLog).first().company_id is None


def test_delete_company_twice_is_404_the_second_time(client, test_db):
    c = make_company(test_db)
    assert_clean(client.delete(f"/api/companies/{c.id}"), 200)
    assert_clean(client.delete(f"/api/companies/{c.id}"), 404)


def test_acknowledge_company_missing_id_is_404(client):
    assert_clean(client.post(f"/api/companies/{MISSING_UUID}/acknowledge"), 404)


def test_bulk_activate_requires_the_active_flag(client):
    assert_clean(client.post("/api/companies/bulk-activate", json={}), 422)


@pytest.mark.parametrize("body", [{"active": None}, {"active": [True]}, {"active": "maybe"}])
def test_bulk_activate_rejects_a_wrongly_typed_flag(client, body):
    assert_clean(client.post("/api/companies/bulk-activate", json=body), 422)


def test_bulk_activate_coerces_boolish_strings(client):
    """Pydantic accepts "yes"/"no" for a bool — recorded, not a defect."""
    r = assert_clean(client.post("/api/companies/bulk-activate", json={"active": "yes"}), 200)
    assert r.json()["active"] is True


@pytest.mark.parametrize("tiers", [["banana"], ["1", "x"], [""]])
def test_bulk_activate_rejects_a_non_numeric_tier(client, test_db, tiers):
    """`int(t)` on a free-text tier is an unguarded ValueError -> 500."""
    make_company(test_db, name="Acme", tier=1)
    assert client.post("/api/companies/bulk-activate",
                       json={"active": False, "tiers": tiers}).status_code in (400, 422)


def test_bulk_activate_non_numeric_tier_never_leaks_internals(client, test_db):
    make_company(test_db, name="Acme", tier=1)
    assert_no_leak(client.post("/api/companies/bulk-activate",
                               json={"active": False, "tiers": ["banana"]}))


def test_bulk_activate_none_tier_selects_untiered_companies(client, test_db):
    make_company(test_db, name="Acme", tier=None)
    make_company(test_db, name="Beta", tier=1)
    r = assert_clean(client.post("/api/companies/bulk-activate",
                                json={"active": False, "tiers": ["none"]}), 200)
    assert r.json()["updated"] == 1


@pytest.mark.parametrize("qs,expected", [
    ("", 200), ("active=true", 200), ("active=false", 200),
    ("tier=1", 200), ("tier=99", 200), ("tier=abc", 422), ("active=maybe", 422),
])
def test_list_companies_query_contract(client, qs, expected):
    assert_clean(client.get(f"/api/companies?{qs}"), expected)


def test_scrape_company_missing_id_is_404(client):
    assert_clean(client.post(f"/api/scrape/company/{MISSING_UUID}"), 404)


def test_scrape_company_second_trigger_on_the_same_scope_is_409(client, test_db, monkeypatch):
    import asyncio
    import backend.scraper.sources.company_pages as cp
    gate = asyncio.Event()

    async def _slow(company):
        await gate.wait()
        return {}
    monkeypatch.setattr(cp, "scrape_single_career_page", _slow, raising=False)
    monkeypatch.setattr(cp, "record_company_scrape_log", lambda *a, **k: None, raising=False)

    c = make_company(test_db)
    assert_clean(client.post(f"/api/scrape/company/{c.id}"), 202)
    assert_clean(client.post(f"/api/scrape/company/{c.id}"), 409)
    gate.set()


# ── R4 fix-loop regression (R4-T1-19) ────────────────────────────────────────

@pytest.mark.parametrize("tiers", [["banana"], ["1", "x"], [""], ["1.5"], ["none", "x"]])
def test_bulk_activate_rejects_every_non_numeric_tier(client, test_db, tiers):
    make_company(test_db, name="Acme", tier=1)
    assert_clean(client.post("/api/companies/bulk-activate",
                             json={"active": False, "tiers": tiers}), 422)


@pytest.mark.parametrize("tiers", [["1"], ["1", "2"], ["none"], ["none", "1"]])
def test_bulk_activate_still_accepts_real_tiers(client, test_db, tiers):
    make_company(test_db, name="Acme", tier=1)
    assert_clean(client.post("/api/companies/bulk-activate",
                             json={"active": True, "tiers": tiers}), 200)
