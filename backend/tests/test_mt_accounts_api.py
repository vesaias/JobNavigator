"""MT-11 · Accounts API: list, create (+ copy-from), PATCH (name, colour, PIN), DELETE, export.

`client` (r4_support) acts as the owner through the API path (X-API-Key + X-Account-Token); a
member call swaps the act-as header (r4_support.ACT_AS); the cookie tests go through POST /api/auth/switch.
"""
import io
import json
import uuid
import zipfile

import pytest

from backend.accounts import auth as A
from backend.accounts.context import unscoped, use_account
from backend.models.db import (
    Account, Application, Company, CoverLetter, Job, Persona, Resume, Search, SectionPolicy,
    Setting, TracerClickEvent, TracerLink,
)
from backend.tests.r4_support import _clear_running_state, _no_outbound, client  # noqa: F401 (fixtures)

OWNER_PIN = "4321"


@pytest.fixture
def owner(test_db):
    return test_db.query(Account).filter(Account.role == "owner").one()


@pytest.fixture
def owner_pin(test_db, owner):
    owner.pin_hash = A.hash_pin(OWNER_PIN)
    test_db.commit()
    return OWNER_PIN


@pytest.fixture(autouse=True)
def _backup_stub(monkeypatch):
    """No pg_dump on SQLite: record the calls instead."""
    from backend.api import routes_accounts
    calls = []

    def _fake(account):
        calls.append(account["name"])
        return "pre_remove_test.sql"
    monkeypatch.setattr(routes_accounts, "backup_before_remove", _fake)
    return calls


def _member(db, name="Partner", pin=None, color="#2e9e6b"):
    m = Account(name=name, role="member", color=color, pin_hash=A.hash_pin(pin) if pin else None)
    db.add(m)
    db.commit()
    return m


def _as(c, account_id):
    c.cookies.clear()
    c.headers["X-Test-Act-As"] = str(account_id)
    return c


def _rows(db, model, account_id):
    with unscoped():
        return db.query(model).filter(model.account_id == account_id).all()


def _setting_rows(db, account_id):
    return {r.key: r.value for r in db.query(Setting).filter(Setting.account_id == account_id).all()}


def _install(db, key, value):
    row = db.query(Setting).filter(Setting.key == key, Setting.account_id.is_(None)).first()
    if row is None:
        db.add(Setting(key=key, value=value))
    else:
        row.value = value
    db.commit()


def _fill(db, account_id, tag):
    """One job, application, base résumé, letter, search and company for `account_id`."""
    with use_account(account_id):
        job = Job(external_id=f"ext-{tag}", content_hash=f"h-{tag}", company="Co", title=f"T {tag}",
                  url=f"https://x.example/{tag}", source="test", status="applied")
        db.add(job)
        db.flush()
        res = Resume(name=f"R {tag}", is_base=True, json_data={"header": {"name": tag}})
        db.add_all([Application(job_id=job.id, status="applied"), res,
                    Search(name=f"S {tag}", search_mode="keyword", search_term=tag),
                    Company(name=f"C {tag}", scrape_urls=[f"https://{tag}.example"])])
        db.flush()
        letter = CoverLetter(name=f"L {tag}", job_id=job.id, resume_id=res.id, json_data={})
        db.add(letter)
        db.flush()
        link = TracerLink(token=f"tok{tag}"[:10], resume_id=res.id, destination_url="https://d.example",
                          source_label="x")
        db.add(link)
        db.flush()
        db.add(TracerClickEvent(tracer_link_id=link.id))
        db.commit()
        return job, res


# ── GET /api/accounts ────────────────────────────────────────────────────────

def test_owner_lists_every_account_with_counts(client, test_db, owner):
    m = _member(test_db)
    _fill(test_db, owner.id, "own")
    _fill(test_db, m.id, "mem")
    r = client.get("/api/accounts")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["max_accounts"] == 5 and data["self_id"] == str(owner.id)
    rows = {a["id"]: a for a in data["accounts"]}
    assert list(rows) == [str(owner.id), str(m.id)]               # owner first
    o, mm = rows[str(owner.id)], rows[str(m.id)]
    for a in (o, mm):
        assert set(a) >= {"id", "name", "color", "role", "has_pin", "created_at", "last_active_at",
                          "counts", "is_self"}
        assert a["counts"] == {"jobs": 1, "applications": 1, "resumes": 1, "cover_letters": 1,
                               "searches": 1, "companies": 1}
    assert o["is_self"] and not mm["is_self"] and mm["role"] == "member"
    assert "pin_hash" not in r.text and "scrypt" not in r.text


def test_member_sees_its_own_row_and_only_names_of_others(client, test_db, owner):
    m = _member(test_db, pin="1111")
    _fill(test_db, owner.id, "own")
    r = _as(client, m.id).get("/api/accounts")
    assert r.status_code == 200, r.text
    rows = {a["id"]: a for a in r.json()["accounts"]}
    assert rows[str(owner.id)] == {"id": str(owner.id), "name": owner.name, "color": owner.color,
                                   "role": "owner"}
    me = rows[str(m.id)]
    assert me["is_self"] and me["has_pin"] is True and me["counts"]["jobs"] == 0
    assert r.json()["self_id"] == str(m.id)
    assert "scrypt" not in r.text


# ── POST /api/accounts ───────────────────────────────────────────────────────

def test_second_account_without_any_pin(client, test_db, owner):
    """QA F2 / D3: no owner PIN needed to add an account, and the new one may have none."""
    assert not owner.pin_hash
    r = client.post("/api/accounts", json={"name": "Partner"})
    assert r.status_code == 201, r.text
    acc = r.json()["account"]
    assert acc["role"] == "member" and acc["has_pin"] is False
    assert test_db.query(Account).count() == 2
    test_db.expire_all()
    assert test_db.query(Account).filter(Account.role == "owner").one().pin_hash is None


def test_second_account_with_pins(client, test_db, owner):
    owner.pin_hash = A.hash_pin(OWNER_PIN)
    test_db.commit()
    r = client.post("/api/accounts", json={"name": "Partner", "pin": "2222"})
    assert r.status_code == 201, r.text
    acc = r.json()["account"]
    assert acc["role"] == "member" and acc["has_pin"] is True and acc["name"] == "Partner"
    assert acc["color"] != owner.color                               # first unused colour
    new_id = uuid.UUID(acc["id"])
    row = test_db.query(Account).filter(Account.id == new_id).one()
    assert A.verify_pin("2222", row.pin_hash)
    # own rows: an empty Persona and the two built-in extension searches
    personas = _rows(test_db, Persona, new_id)
    assert len(personas) == 1 and personas[0].qa_bank == [] and personas[0].contact == {}
    searches = _rows(test_db, Search, new_id)
    assert sorted((s.name, s.search_mode) for s in searches) == [
        ("Extension", "extension"), ("Extension LI", "linkedin_extension")]
    assert r.json()["copied"] == {}


def test_cap_of_five_accounts(client, test_db, owner_pin):
    for i in range(4):
        r = client.post("/api/accounts", json={"name": f"M{i}"})
        assert r.status_code == 201, r.text
    r = client.post("/api/accounts", json={"name": "Sixth"})
    assert r.status_code == 409
    assert r.json()["detail"] == "account_limit" and "5" in r.json()["message"]
    assert test_db.query(Account).count() == 5
    assert test_db.query(Account).filter(Account.role == "owner").count() == 1


def test_create_validation(client, test_db, owner, owner_pin):
    assert client.post("/api/accounts", json={"name": "  "}).status_code == 422
    assert client.post("/api/accounts", json={"name": "X", "color": "red"}).status_code == 422
    assert client.post("/api/accounts", json={"name": "X", "pin": "12"}).status_code == 422
    assert client.post("/api/accounts", json={"name": owner.name.upper()}).json()["detail"] == "name_taken"
    r = client.post("/api/accounts", json={"name": "X", "copy_from": {"account_id": str(owner.id),
                                                                     "items": ["jobs"]}})
    assert r.status_code == 422
    r = client.post("/api/accounts", json={"name": "X", "copy_from": {"account_id": str(uuid.uuid4()),
                                                                     "items": ["persona"]}})
    assert r.status_code == 404
    assert test_db.query(Account).count() == 1
    r = client.post("/api/accounts", json={"name": "X", "color": "#ABCDEF", "role": "owner"})
    assert r.status_code == 201 and r.json()["account"]["role"] == "member"   # role is never taken
    assert r.json()["account"]["color"] == "#abcdef"


def test_member_is_forbidden_on_owner_endpoints(client, test_db, owner, owner_pin):
    m = _member(test_db)
    other = _member(test_db, name="Other", color="#e0912b")
    c = _as(client, m.id)
    assert c.post("/api/accounts", json={"name": "Sneaky"}).status_code == 403
    assert c.request("DELETE", f"/api/accounts/{other.id}", json={"confirm_name": "Other"}).status_code == 403
    assert c.patch(f"/api/accounts/{other.id}", json={"name": "Renamed"}).status_code == 403
    assert c.patch(f"/api/accounts/{owner.id}", json={"pin": None}).status_code == 403
    assert c.get(f"/api/accounts/{owner.id}/export").status_code == 403
    assert c.get(f"/api/accounts/{other.id}/export").status_code == 403
    test_db.expire_all()
    assert test_db.query(Account).count() == 3
    assert test_db.query(Account).filter(Account.id == other.id).one().name == "Other"


# ── copy_from ────────────────────────────────────────────────────────────────

def _owner_world(db, owner_id):
    with use_account(owner_id):
        p = db.query(Persona).first() or Persona(account_id=owner_id)
        p.contact = {"name": "Jordan", "email": "v@example.com"}
        p.preferences = {"tone": "plain"}
        p.qa_bank = [{"question": "Visa?", "answer": "No"}, {"question": "Start?", "answer": "Now"}]
        db.add(p)
        b1 = Resume(name="Base PM", is_base=True, json_data={"summary": "pm"})
        b2 = Resume(name="Base TPM", is_base=True, json_data={"summary": "tpm"})
        db.add_all([b1, b2])
        db.flush()
        tailored = Resume(name="Tailored", is_base=False, parent_id=b1.id, json_data={"_score": 70})
        db.add(tailored)
        db.flush()
        co = Company(name="Acme", scrape_urls=["https://acme.example/jobs"], aliases=["ACME Inc"],
                     selected_resume_ids=[str(b1.id), str(tailored.id), "persona", str(uuid.uuid4())],
                     title_exclude_keywords=["intern"], auto_scoring_depth="light")
        db.add(co)
        db.add_all([
            Search(name="PM search", search_mode="keyword", search_term="product manager",
                   title_include_keywords=["product"]),
            Search(name="Extension", search_mode="extension", title_exclude_keywords=["owner-only"]),
            Search(name="Extension LI", search_mode="linkedin_extension"),
        ])
        db.flush()
        job = Job(external_id="e1", content_hash="h1", company="Acme", title="PM", url="https://a/1",
                  source="test", status="applied")
        db.add(job)
        db.flush()
        db.add_all([Application(job_id=job.id), CoverLetter(name="L", job_id=job.id, json_data={})])
        db.commit()
    for k, v in {"feed_zoom_floater": "true", "default_resume_id": str(b1.id),
                 "fit_score_threshold": "80", "telegram_chat_id": "999",
                 "cover_letter_voice_presets": '[{"id":"warm"}]', "cover_letter_default_voice": "warm",
                 "title_exclude_global": '["senior"]', "linkedin_email": "v@li.example",
                 "anthropic_api_key": "sk-secret", "proxy_url": "http://proxy"}.items():
        _install(db, k, v)
    return b1, b2, tailored


def _create(c, name, source_id, items, pin=None):
    body = {"name": name, "copy_from": {"account_id": str(source_id), "items": items}}
    if pin:
        body["pin"] = pin
    r = c.post("/api/accounts", json=body)
    assert r.status_code == 201, r.text
    return uuid.UUID(r.json()["account"]["id"]), r.json()["copied"]


def test_copy_everything_from_the_owner_remaps_ids(client, test_db, owner, owner_pin):
    b1, b2, tailored = _owner_world(test_db, owner.id)
    new_id, copied = _create(client, "Partner", owner.id, list(
        ["persona", "qa", "resumes", "companies", "searches", "settings", "voices", "excludes"]))
    assert copied["persona"] == 1 and copied["qa"] == 2
    assert copied["resumes"] == 2 and copied["companies"] == 1 and copied["searches"] == 1

    p = _rows(test_db, Persona, new_id)[0]
    assert p.contact == {"name": "Jordan", "email": "v@example.com"} and p.preferences == {"tone": "plain"}
    assert [q["question"] for q in p.qa_bank] == ["Visa?", "Start?"]

    resumes = {r.name: r for r in _rows(test_db, Resume, new_id)}
    assert set(resumes) == {"Base PM", "Base TPM"}                  # base only, no tailored
    assert resumes["Base PM"].id != b1.id and resumes["Base PM"].json_data == {"summary": "pm"}
    assert all(r.is_base and r.parent_id is None for r in resumes.values())

    (co,) = _rows(test_db, Company, new_id)
    assert co.name == "Acme" and co.aliases == ["ACME Inc"] and co.title_exclude_keywords == ["intern"]
    # b1 -> its copy, "persona" kept, the tailored id and the unknown id dropped
    assert co.selected_resume_ids == [str(resumes["Base PM"].id), "persona"]

    searches = sorted((s.name, s.search_mode) for s in _rows(test_db, Search, new_id))
    assert searches == [("Extension", "extension"), ("Extension LI", "linkedin_extension"),
                        ("PM search", "keyword")]
    ext = next(s for s in _rows(test_db, Search, new_id) if s.search_mode == "extension")
    assert ext.title_exclude_keywords == []                          # seeded, not the owner's

    for model in (Job, Application, CoverLetter, TracerLink):
        assert _rows(test_db, model, new_id) == []

    own = _setting_rows(test_db, new_id)
    assert own["feed_zoom_floater"] == "true"
    assert own["default_resume_id"] == str(resumes["Base PM"].id)     # remapped
    assert own["fit_score_threshold"] == "80"
    assert own["cover_letter_voice_presets"] == '[{"id":"warm"}]' and own["cover_letter_default_voice"] == "warm"
    assert own["title_exclude_global"] == '["senior"]'
    for personal in ("telegram_chat_id", "linkedin_email", "anthropic_api_key", "proxy_url", "dashboard_api_key"):
        assert personal not in own
    policy = test_db.query(SectionPolicy).filter(SectionPolicy.account_id == new_id,
                                                 SectionPolicy.section == "letters").one()
    assert policy.mode == "own"

    # the member reads its copies through the normal settings path
    from backend.accounts.settings import get_setting
    with use_account(new_id):
        assert get_setting(test_db, "default_resume_id") == str(resumes["Base PM"].id)
        assert get_setting(test_db, "cover_letter_default_voice") == "warm"
        assert get_setting(test_db, "telegram_chat_id", "") == ""      # own_always, not copied
    # the owner's rows are untouched
    assert len(_rows(test_db, Resume, owner.id)) == 3
    assert len(_rows(test_db, Search, owner.id)) == 3


def test_copy_nothing_selected_gives_a_bare_account(client, test_db, owner, owner_pin):
    _owner_world(test_db, owner.id)
    new_id, copied = _create(client, "Bare", owner.id, [])
    assert copied == {}
    assert _rows(test_db, Resume, new_id) == [] and _rows(test_db, Company, new_id) == []
    assert _rows(test_db, Persona, new_id)[0].contact == {}
    assert _setting_rows(test_db, new_id) == {}


def test_copy_qa_only_and_companies_without_resumes(client, test_db, owner, owner_pin):
    _owner_world(test_db, owner.id)
    new_id, copied = _create(client, "QA", owner.id, ["qa", "companies"])
    p = _rows(test_db, Persona, new_id)[0]
    assert len(p.qa_bank) == 2 and p.contact == {}
    assert "persona" not in copied and copied["qa"] == 2
    (co,) = _rows(test_db, Company, new_id)
    assert co.selected_resume_ids == ["persona"]                      # no résumé was copied


def test_copied_companies_and_searches_are_due_at_once(client, test_db, owner, owner_pin):
    """MT-12 decision on the MT-11 leftover: a copy's last-run time is cleared, so the
    new account's first scheduled pass scrapes it (and the shared fetch feeds every
    subscriber), instead of waiting for the source's next due run. The source keeps its own."""
    from datetime import datetime, timedelta, timezone
    from backend.scraper.targets import company_due, search_due
    _owner_world(test_db, owner.id)
    recent = datetime.now(timezone.utc) - timedelta(minutes=5)
    with use_account(owner.id):
        co = test_db.query(Company).filter(Company.name == "Acme").one()
        co.last_scraped_at, co.scrape_interval_minutes = recent, 720
        s = test_db.query(Search).filter(Search.name == "PM search").one()
        s.last_run_at, s.run_interval_minutes = recent, 720
        test_db.commit()
    now = datetime.now(timezone.utc)
    assert company_due(co, now, 60)[0] is False and search_due(s, now)[0] is False   # source: not due

    new_id, _ = _create(client, "Fresh", owner.id, ["companies", "searches"])
    (nco,) = _rows(test_db, Company, new_id)
    nse = next(x for x in _rows(test_db, Search, new_id) if x.name == "PM search")
    assert nco.last_scraped_at is None and nse.last_run_at is None
    assert nco.scrape_interval_minutes == 720 and nse.run_interval_minutes == 720   # settings kept
    assert company_due(nco, now, 60)[0] is True and search_due(nse, now)[0] is True
    test_db.expire_all()
    with unscoped():
        assert test_db.query(Company).filter(Company.id == co.id).one().last_scraped_at is not None
        assert test_db.query(Search).filter(Search.id == s.id).one().last_run_at is not None


def test_copy_settings_from_a_member_takes_its_policies_and_own_rows(client, test_db, owner, owner_pin):
    src = _member(test_db, name="Source")
    test_db.add_all([SectionPolicy(account_id=src.id, section="models", mode="own"),
                     Setting(key="llm_model", value="model-x", account_id=src.id),
                     Setting(key="anthropic_api_key", value="sk-member", account_id=src.id),
                     # scoring is 'inherit' for the source: its stray row is not its own value
                     Setting(key="scoring_rubric", value="stale", account_id=src.id)])
    test_db.commit()
    new_id, copied = _create(client, "Copy", src.id, ["settings"])
    modes = {p.section: p.mode for p in test_db.query(SectionPolicy).filter(SectionPolicy.account_id == new_id)}
    assert modes == {"models": "own"}
    own = _setting_rows(test_db, new_id)
    assert own == {"llm_model": "model-x"}                            # secret and inherited rows skipped
    assert copied["settings"] == 2                                    # 1 policy + 1 value


def test_member_extension_search_lookup_is_per_account(client, test_db, owner, owner_pin, monkeypatch):
    """The save-to-feed flow finds the caller's own "Extension" search (MT-4 leftover)."""
    import asyncio
    import backend.analyzer.h1b_checker as h1b

    async def _noop(*a, **k):
        return None
    monkeypatch.setattr(h1b, "check_job_h1b", _noop)
    from backend.api import routes_jobs
    launched = []
    monkeypatch.setattr(routes_jobs, "launch_background", lambda *a, **k: launched.append(a[0]))
    with use_account(owner.id):
        test_db.add(Search(name="Extension", search_mode="extension", title_exclude_keywords=["intern"]))
        test_db.commit()
    new_id, _ = _create(client, "Partner", owner.id, [])
    from backend.api.routes_jobs import save_from_extension
    with use_account(new_id):
        out = asyncio.run(save_from_extension({"title": "Product Intern", "company": "Acme",
                                                "url": "https://acme.test/1", "description": "x"},
                                               db=test_db))
        assert out["saved"] is True                                   # the owner's exclude does not apply
        job = test_db.query(Job).one()
        mine = test_db.query(Search).filter(Search.search_mode == "extension").one()
        assert job.search_id == mine.id and mine.account_id == new_id
    assert launched == ["analyze_job"]                                # the member's search auto-scores (light)


def test_seed_searches_gives_every_member_its_extension_searches(test_db, owner):
    from backend import seed
    m = _member(test_db)
    with unscoped():
        seed.seed_searches(test_db)
        test_db.commit()
        seed.seed_searches(test_db)
        test_db.commit()
    modes = sorted(s.search_mode for s in _rows(test_db, Search, m.id))
    assert modes == ["extension", "linkedin_extension"]
    assert len(_rows(test_db, Search, owner.id)) == len(seed.SEED_SEARCHES)


# ── PATCH /api/accounts/{id} ─────────────────────────────────────────────────

def test_rename_and_colour(client, test_db, owner, owner_pin):
    m = _member(test_db)
    r = client.patch(f"/api/accounts/{m.id}", json={"name": " New  Name ", "color": "#8A5CD6"})
    assert r.status_code == 200, r.text
    assert r.json()["account"]["name"] == "New Name" and r.json()["account"]["color"] == "#8a5cd6"
    r = _as(client, m.id).patch(f"/api/accounts/{m.id}", json={"name": "Mine"})
    assert r.status_code == 200 and r.json()["account"]["name"] == "Mine"
    assert client.patch(f"/api/accounts/{m.id}", json={"name": owner.name}).status_code == 409
    assert client.patch(f"/api/accounts/{m.id}", json={"color": "blue"}).status_code == 422
    assert client.patch(f"/api/accounts/{uuid.uuid4()}", json={"name": "x"}).status_code == 404


def test_own_pin_change_needs_current_pin_and_reissues_the_cookie(client, test_db, owner):
    m = _member(test_db, pin="1111")
    owner.pin_hash = A.hash_pin(OWNER_PIN)
    test_db.commit()
    browser = client
    browser.headers.pop("X-Test-Act-As", None)
    r = browser.post("/api/auth/switch", json={"account_id": str(m.id), "pin": "1111"})
    assert r.status_code == 200
    old_cookie = browser.cookies.get("jn_account")

    r = browser.patch(f"/api/accounts/{m.id}", json={"pin": "2222"})
    assert r.status_code == 401 and r.json()["detail"] == "pin_required"
    r = browser.patch(f"/api/accounts/{m.id}", json={"pin": "2222", "current_pin": "9999"})
    assert r.status_code == 401 and r.json() == {"detail": "wrong_pin", "tries_left": 4}
    r = browser.patch(f"/api/accounts/{m.id}", json={"pin": "2222", "current_pin": "1111"})
    assert r.status_code == 200, r.text
    assert r.json()["pin_changed"] is True and "scrypt" not in r.text
    assert "jn_account=" in r.headers.get("set-cookie", "")
    new_cookie = browser.cookies.get("jn_account")
    assert new_cookie and new_cookie != old_cookie
    # the new cookie keeps this browser in; the old one is dead
    assert browser.get("/api/auth/me").json()["account"]["id"] == str(m.id)
    # Replace, not add: the jar keys cookies by domain too, and with httpx2 (which the
    # TestClient uses once `mcp` installs it) the server-set new cookie is sent first.
    browser.cookies.delete("jn_account")
    browser.cookies.set("jn_account", old_cookie)
    assert browser.get("/api/jobs").status_code == 401
    test_db.expire_all()
    assert A.verify_pin("2222", test_db.query(Account).filter(Account.id == m.id).one().pin_hash)


def test_member_removes_its_own_pin(client, test_db, owner, owner_pin):
    m = _member(test_db, pin="1111")
    c = _as(client, m.id)
    assert c.patch(f"/api/accounts/{m.id}", json={"pin": None}).status_code == 401
    r = c.patch(f"/api/accounts/{m.id}", json={"pin": None, "current_pin": "1111"})
    assert r.status_code == 200 and r.json()["account"]["has_pin"] is False


def test_owner_resets_a_member_pin_without_it(client, test_db, owner, owner_pin):
    m = _member(test_db, pin="1111")
    r = client.patch(f"/api/accounts/{m.id}", json={"pin": "5555"})
    assert r.status_code == 200, r.text
    assert r.json()["account"]["has_pin"] is True and "5555" not in r.text and "scrypt" not in r.text
    assert "jn_account" not in r.headers.get("set-cookie", "")       # not the caller's own PIN
    test_db.expire_all()
    assert A.verify_pin("5555", test_db.query(Account).filter(Account.id == m.id).one().pin_hash)
    r = client.patch(f"/api/accounts/{m.id}", json={"pin": ""})
    assert r.status_code == 200 and r.json()["account"]["has_pin"] is False


def test_owner_pin_rules(client, test_db, owner):
    # first PIN: no current PIN to give
    r = client.patch(f"/api/accounts/{owner.id}", json={"pin": OWNER_PIN})
    assert r.status_code == 200 and r.json()["account"]["has_pin"] is True
    assert "jn_account=" in r.headers.get("set-cookie", "")
    _member(test_db)
    # removing needs the current PIN ...
    r = client.patch(f"/api/accounts/{owner.id}", json={"pin": None})
    assert r.status_code == 401 and r.json()["detail"] == "pin_required"
    r = client.patch(f"/api/accounts/{owner.id}", json={"pin": "1357", "current_pin": OWNER_PIN})
    assert r.status_code == 200
    # ... and is allowed with members present (QA F2 / D3: no owner_pin_required)
    r = client.patch(f"/api/accounts/{owner.id}", json={"pin": None, "current_pin": "1357"})
    assert r.status_code == 200 and r.json()["account"]["has_pin"] is False
    assert "owner_pin_required" not in r.text


# ── DELETE /api/accounts/{id} ────────────────────────────────────────────────

def test_delete_rules_and_itemised_counts(client, test_db, owner, owner_pin, _backup_stub):
    m = _member(test_db, name="Partner")
    _fill(test_db, owner.id, "own")
    _fill(test_db, m.id, "mem")
    test_db.add_all([Setting(key="feed_zoom_floater", value="true", account_id=m.id),
                     SectionPolicy(account_id=m.id, section="models", mode="own")])
    test_db.commit()

    assert client.request("DELETE", f"/api/accounts/{owner.id}",
                          json={"confirm_name": owner.name}).json()["detail"] == "cannot_remove_owner"
    r = client.request("DELETE", f"/api/accounts/{m.id}", json={"confirm_name": "partner"})
    assert r.status_code == 400 and r.json()["detail"] == "confirm_name_mismatch"
    assert client.request("DELETE", f"/api/accounts/{m.id}").status_code == 400
    assert _backup_stub == []                                         # no backup before the checks pass

    r = client.request("DELETE", f"/api/accounts/{m.id}", json={"confirm_name": "Partner"})
    assert r.status_code == 200, r.text
    assert _backup_stub == ["Partner"] and r.json()["backup"] == "pre_remove_test.sql"
    d = r.json()["deleted"]
    for key in ("jobs", "applications", "resumes", "cover_letters", "searches", "companies",
                "tracer_links", "tracer_clicks"):
        assert d[key] == 1, (key, d)
    assert d["settings"] == 1 and d["section_policies"] == 1 and d["files"] == 0
    assert test_db.query(Account).filter(Account.id == m.id).first() is None
    for model in (Job, Application, Resume, CoverLetter, Search, Company, TracerLink):
        assert _rows(test_db, model, m.id) == []
        assert len(_rows(test_db, model, owner.id)) == 1               # the owner's rows stay
    assert test_db.query(Setting).filter(Setting.account_id == m.id).count() == 0
    assert client.request("DELETE", f"/api/accounts/{m.id}",
                          json={"confirm_name": "Partner"}).status_code == 404


def test_delete_aborts_when_the_backup_fails(client, test_db, owner, owner_pin, monkeypatch):
    from backend.api import routes_accounts
    m = _member(test_db, name="Partner")
    _fill(test_db, m.id, "mem")

    def _boom(account):
        raise RuntimeError("pg_dump failed: disk full")
    monkeypatch.setattr(routes_accounts, "backup_before_remove", _boom)
    r = client.request("DELETE", f"/api/accounts/{m.id}", json={"confirm_name": "Partner"})
    assert r.status_code == 503 and r.json()["detail"] == "backup_failed"
    assert "disk full" not in r.text
    assert test_db.query(Account).filter(Account.id == m.id).count() == 1
    assert len(_rows(test_db, Job, m.id)) == 1


def test_delete_refused_while_the_account_has_running_work(client, test_db, owner, owner_pin):
    from datetime import datetime, timezone
    import backend.job_monitor as jm
    m = _member(test_db, name="Partner")
    jm._running["x@" + str(m.id)] = jm.RunningJob(
        run_id=uuid.uuid4(), job_type="scrape_all", trigger="manual",
        started_at=datetime.now(timezone.utc), account_id=m.id)
    r = client.request("DELETE", f"/api/accounts/{m.id}", json={"confirm_name": "Partner"})
    assert r.status_code == 409 and r.json()["detail"] == "account_busy"


def test_deleted_account_cookie_stops_working(client, test_db, owner, owner_pin):
    m = _member(test_db, name="Partner")
    client.headers.pop("X-Test-Act-As", None)
    assert client.post("/api/auth/switch", json={"account_id": str(m.id)}).status_code == 200
    cookie = client.cookies.get("jn_account")
    client.cookies.clear()
    client.headers["X-Test-Act-As"] = str(owner.id)
    assert client.request("DELETE", f"/api/accounts/{m.id}", json={"confirm_name": "Partner"}).status_code == 200
    client.headers.pop("X-Test-Act-As", None)
    client.cookies.set("jn_account", cookie)
    # QA F3 / R2-03: one account left, but this browser presented a stale cookie, so it
    # gets the picker (owner PIN), never the owner and never the removed member
    r = client.get("/api/auth/me")
    assert (r.status_code, r.json()) == (401, {"detail": "account_required"})


# ── GET /api/accounts/{id}/export ────────────────────────────────────────────

def _zip(resp):
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/zip"
    assert "attachment" in resp.headers["content-disposition"]
    return zipfile.ZipFile(io.BytesIO(resp.content))


def test_export_contents(client, test_db, owner, owner_pin):
    m = _member(test_db, name="Partner", pin="1111")
    _fill(test_db, m.id, "mem")
    _fill(test_db, owner.id, "own")
    test_db.add_all([Setting(key="feed_zoom_floater", value="true", account_id=m.id),
                     Setting(key="anthropic_api_key", value="sk-very-secret", account_id=m.id)])
    test_db.commit()

    z = _zip(client.get(f"/api/accounts/{m.id}/export"))
    names = set(z.namelist())
    assert {"manifest.json", "account.json", "persona.json", "resumes.json", "cover_letters.json",
            "jobs.json", "applications.json", "searches.json", "companies.json", "settings.json",
            "section_policies.json", "tracer_links.json", "tracer_click_events.json"} <= names
    manifest = json.loads(z.read("manifest.json"))
    assert manifest["account"]["id"] == str(m.id)
    assert manifest["counts"]["jobs"] == 1 and manifest["counts"]["tracer_click_events"] == 1
    assert any("PDF" in n for n in manifest["notes"])
    jobs = json.loads(z.read("jobs.json"))
    assert [j["title"] for j in jobs] == ["T mem"]                   # the owner's job is not there
    assert json.loads(z.read("resumes.json"))[0]["name"] == "R mem"
    account = json.loads(z.read("account.json"))
    assert "pin_hash" not in account and account["has_pin"] is True
    settings = {s["key"]: s["value"] for s in json.loads(z.read("settings.json"))}
    assert settings["feed_zoom_floater"] == "true" and settings["anthropic_api_key"] == "•" * 6
    blob = b"".join(z.read(n) for n in names)
    assert b"sk-very-secret" not in blob and b"scrypt" not in blob and b"T own" not in blob
    policies = {p["section"]: p["mode"] for p in json.loads(z.read("section_policies.json"))}
    assert policies["exclude"] == "own" and policies["models"] == "inherit"


def test_member_exports_itself(client, test_db, owner, owner_pin):
    m = _member(test_db)
    _fill(test_db, m.id, "mem")
    z = _zip(_as(client, m.id).get(f"/api/accounts/{m.id}/export"))
    assert json.loads(z.read("manifest.json"))["counts"]["jobs"] == 1


def test_owner_export_settings_are_install_values_without_hidden_keys(client, test_db, owner):
    _install(test_db, "account_cookie_secret", "hmac-key")
    _install(test_db, "feed_zoom_floater", "false")
    z = _zip(client.get(f"/api/accounts/{owner.id}/export"))
    settings = {s["key"]: s["value"] for s in json.loads(z.read("settings.json"))}
    assert "account_cookie_secret" not in settings and settings["feed_zoom_floater"] == "false"
    assert settings["dashboard_api_key"] == "•" * 6
    assert json.loads(z.read("section_policies.json")) == []


# ── last_active_at ───────────────────────────────────────────────────────────

def test_last_active_at_is_stamped_at_most_once_a_minute(client, test_db, owner, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(A, "_mono", lambda: clock[0])

    def stamp():
        test_db.expire_all()
        return test_db.query(Account).filter(Account.id == owner.id).one().last_active_at

    assert client.get("/api/jobs").status_code == 200
    first = stamp()
    assert first is not None
    with unscoped():
        test_db.query(Account).filter(Account.id == owner.id).update({"last_active_at": None})
        test_db.commit()
    clock[0] += 30
    client.get("/api/jobs")
    assert stamp() is None                                            # throttled
    clock[0] += 31
    client.get("/api/jobs")
    assert stamp() is not None


def test_adding_the_second_account_pins_the_owners_browser(client, test_db, owner, owner_pin):
    """MT-13: the owner's browser had no jn_account cookie (one account = the owner); after
    adding a member it keeps acting as the owner instead of landing on the picker."""
    client.headers.pop("X-Test-Act-As", None)
    client.cookies.clear()
    assert client.get("/api/auth/me").json()["account"]["id"] == str(owner.id)
    r = client.post("/api/accounts", json={"name": "Alex"})
    assert r.status_code == 201
    assert any(c.startswith(A.COOKIE_NAME + "=") for c in r.headers.get_list("set-cookie"))
    me = client.get("/api/auth/me")
    assert me.status_code == 200 and me.json()["account"]["id"] == str(owner.id)
    assert me.json()["accounts_count"] == 2
