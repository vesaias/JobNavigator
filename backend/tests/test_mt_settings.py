"""MT-9 · Account-scoped settings and section policies.

A is the owner (its values are the install values), B a member. Until MT-10 a member
cannot be reached over HTTP, so member cases call the route functions inside
`use_account(B)`, exactly what the MT-10 middleware will set.
"""
import json

import pytest
from fastapi import HTTPException

from backend.accounts import settings as S
from backend.accounts.context import unscoped, use_account
from backend.api import routes_settings as R
from backend.models.db import Account, Resume, SectionPolicy, Setting
from backend.tests.r4_support import client, set_setting  # noqa: F401 (fixture)


@pytest.fixture
def accounts(test_db):
    a = test_db.query(Account).filter(Account.role == "owner").one()
    b = Account(name="Partner", role="member")
    test_db.add(b)
    test_db.commit()
    return a.id, b.id


def _own(db, account_id, key, value):
    db.add(Setting(key=key, value=value, account_id=account_id))
    db.commit()


def _policy(db, account_id, section, mode):
    db.add(SectionPolicy(account_id=account_id, section=section, mode=mode))
    db.commit()


# ── the section table ────────────────────────────────────────────────────────

def test_every_known_key_has_exactly_one_section():
    from backend.seed import DEFAULT_SETTINGS, RUNTIME_SETTING_KEYS
    all_keys = [k for sec in S.SETTING_SECTIONS.values() for k in sec["keys"]]
    assert len(all_keys) == len(set(all_keys))
    missing = (set(DEFAULT_SETTINGS) | RUNTIME_SETTING_KEYS) - set(all_keys)
    assert not missing


# The Settings screen's section ids (frontend/src/screens/Settings.jsx), minus 'appearance'
# (Display: per-browser rows plus the feed section's one setting). The backend container does
# not mount the frontend, so the list is kept here and re-read from the source when it is available.
SCREEN_SECTIONS = {"models", "scoring", "tailoring", "letters", "autofill", "prep",
                   "emailclass", "scheduler", "exclude", "dedup", "copies", "notifications", "tracer",
                   "apify", "jobright", "linkedin", "advanced", "updates", "telemetry"}


def test_ui_sections_match_the_settings_screen():
    import pathlib
    import re
    screen = SCREEN_SECTIONS
    src = (pathlib.Path(__file__).resolve().parents[2] / "frontend/src/screens/Settings.jsx")
    if src.exists():
        screen = set(re.findall(r"^\s{6}\['([a-z]+)', '", src.read_text(encoding="utf-8"), re.M))
        screen.discard("appearance")
        assert screen == SCREEN_SECTIONS
    ui = {u for sec in S.SETTING_SECTIONS.values() for u in sec["ui"]}
    assert ui - {"appearance"} == screen
    assert S.SETTING_SECTIONS["feed"]["ui"] == ["appearance"]
    # every screen section that is itself a table section keeps the screen's id
    assert {sid for sid in S.SETTING_SECTIONS if sid in screen} == screen


def test_spec_defaults():
    sec = S.SETTING_SECTIONS
    assert (sec["models"]["scope"], sec["models"]["default"]) == ("policy", "inherit")
    assert "anthropic_api_key" in sec["models"]["keys"]
    for sid in ("scoring", "tailoring", "letters", "scheduler"):
        assert (sec[sid]["scope"], sec[sid]["default"]) == ("policy", "inherit")
    assert (sec["exclude"]["scope"], sec["exclude"]["default"]) == ("policy", "own")
    assert (sec["linkedin"]["scope"], sec["linkedin"]["default"]) == ("policy", "own")
    assert sec["notifications"]["scope"] == "own_always"
    assert sec["gmail"]["scope"] == "own_always"
    for sid in ("dedup", "advanced", "backups", "tracer", "h1b"):
        assert sec[sid]["scope"] == "owner_only"
    assert S.section_of("proxy_url") == "advanced"
    assert S.section_of("no_such_key") == "system"


def test_sections_endpoint(client):
    r = client.get("/api/settings/sections")
    assert r.status_code == 200
    rows = r.json()
    assert rows[0]["id"] == "feed"
    assert {"id", "label", "scope", "default", "ui", "keys"} <= set(rows[0])


# ── reads ────────────────────────────────────────────────────────────────────

def test_owner_reads_install_values_and_ignores_member_rows(test_db, accounts):
    a, b = accounts
    set_setting(test_db, "title_exclude_global", '["intern"]')
    _own(test_db, b, "title_exclude_global", '["senior"]')
    with use_account(a):
        assert S.get_setting(test_db, "title_exclude_global") == '["intern"]'
    with unscoped():
        assert S.get_setting(test_db, "title_exclude_global") == '["intern"]'
    assert S.get_setting(test_db, "missing_key", "dflt") == "dflt"


def test_inherit_reads_install_even_with_an_own_row(test_db, accounts):
    a, b = accounts
    set_setting(test_db, "scoring_rubric", "owner rubric")
    _own(test_db, b, "scoring_rubric", "member rubric")      # left over from an earlier 'own'
    with use_account(b):
        assert S.get_setting(test_db, "scoring_rubric") == "owner rubric"
        assert S.resolve_setting(test_db, "scoring_rubric")[1] == "install"


def test_own_reads_the_member_row_else_the_seeded_default(test_db, accounts):
    # QA F5 (R3-01/T3-06): 'own' never falls back to the owner's install value
    a, b = accounts
    set_setting(test_db, "title_exclude_global", '["intern"]')
    set_setting(test_db, "company_exclude_global", '["Acme"]')
    _own(test_db, b, "title_exclude_global", '["senior"]')
    with use_account(b):
        assert S.get_setting(test_db, "title_exclude_global") == '["senior"]'
        assert S.resolve_setting(test_db, "company_exclude_global") == ("[]", "default")   # no own row yet


def test_policy_flip_switches_the_source(test_db, accounts):
    a, b = accounts
    set_setting(test_db, "scoring_rubric", "owner rubric")
    _own(test_db, b, "scoring_rubric", "member rubric")
    _policy(test_db, b, "scoring", "own")
    with use_account(b):
        assert S.get_setting(test_db, "scoring_rubric") == "member rubric"
    _policy_row = test_db.query(SectionPolicy).filter_by(account_id=b, section="scoring").one()
    _policy_row.mode = "inherit"
    test_db.commit()
    with use_account(b):
        assert S.get_setting(test_db, "scoring_rubric") == "owner rubric"


def test_own_always_never_falls_back_to_the_owner(test_db, accounts):
    a, b = accounts
    set_setting(test_db, "telegram_chat_id", "owner-chat")
    with use_account(b):
        assert S.get_setting(test_db, "telegram_chat_id") == ""        # seeded default, not the owner's
        assert S.resolve_setting(test_db, "telegram_chat_id")[1] == "default"
    _own(test_db, b, "telegram_chat_id", "member-chat")
    with use_account(b):
        assert S.get_setting(test_db, "telegram_chat_id") == "member-chat"
    with use_account(a):
        assert S.get_setting(test_db, "telegram_chat_id") == "owner-chat"


def test_owner_only_ignores_member_rows(test_db, accounts):
    a, b = accounts
    set_setting(test_db, "proxy_url", "socks5://owner")
    _own(test_db, b, "proxy_url", "socks5://member")     # cannot be written via the API; ignored anyway
    with use_account(b):
        assert S.get_setting(test_db, "proxy_url") == "socks5://owner"


# ── writes ───────────────────────────────────────────────────────────────────

def test_owner_patch_writes_install_values(test_db, accounts):
    a, b = accounts
    with use_account(a):
        out = R.update_settings({"title_exclude_global": ["x"]}, db=test_db)
    assert out["updated"] == ["title_exclude_global"]
    rows = test_db.query(Setting).filter(Setting.key == "title_exclude_global").all()
    assert [(r.account_id, r.value) for r in rows] == [(None, '["x"]')]


def test_member_patch_writes_an_own_row(test_db, accounts):
    a, b = accounts
    set_setting(test_db, "title_exclude_global", '["intern"]')
    with use_account(b):
        out = R.update_settings({"title_exclude_global": ["senior"], "telegram_chat_id": "42"}, db=test_db)
        assert sorted(out["updated"]) == ["telegram_chat_id", "title_exclude_global"]
        assert S.get_setting(test_db, "title_exclude_global") == '["senior"]'
        # a second write updates the same row
        R.update_settings({"title_exclude_global": ["lead"]}, db=test_db)
    own = test_db.query(Setting).filter(Setting.account_id == b).all()
    assert {r.key: r.value for r in own} == {"title_exclude_global": '["lead"]', "telegram_chat_id": "42"}
    with use_account(a):
        assert S.get_setting(test_db, "title_exclude_global") == '["intern"]'


@pytest.mark.parametrize("key,value", [
    ("scoring_rubric", "mine"),           # policy, default inherit
    ("proxy_url", "socks5://x"),          # owner only
    ("dashboard_api_key", "k"),           # owner only (secret)
    ("tracer_links_base_url", "https://x"),
])
def test_member_patch_denied_outside_own_sections(test_db, accounts, key, value):
    a, b = accounts
    with use_account(b):
        with pytest.raises(HTTPException) as e:
            R.update_settings({"title_exclude_global": ["ok"], key: value}, db=test_db)
    assert e.value.status_code == 403
    assert key in e.value.detail and "owner" in e.value.detail
    # all or nothing: the allowed key was not written either
    assert test_db.query(Setting).filter(Setting.account_id == b).count() == 0


def test_member_patch_allowed_after_owner_flips_policy(test_db, accounts):
    a, b = accounts
    with use_account(a):
        R.update_policy({"account_id": str(b), "section": "scoring", "mode": "own"}, db=test_db)
    with use_account(b):
        R.update_settings({"scoring_rubric": "mine"}, db=test_db)
        assert S.get_setting(test_db, "scoring_rubric") == "mine"


def test_member_patch_still_validates_values(test_db, accounts):
    a, b = accounts
    with use_account(b):
        with pytest.raises(HTTPException) as e:
            R.update_settings({"fit_score_threshold": "-3"}, db=test_db)
    assert e.value.status_code == 400


# ── policies ─────────────────────────────────────────────────────────────────

def test_owner_sets_and_lists_policies(test_db, accounts):
    a, b = accounts
    with use_account(a):
        out = R.update_policy({"account_id": str(b), "section": "models", "mode": "own"}, db=test_db)
        assert out == {"account_id": str(b), "section": "models", "mode": "own"}
        R.update_policy({"account_id": str(b), "section": "models", "mode": "inherit"}, db=test_db)
        listing = R.get_policies(db=test_db)
    assert listing[str(b)]["models"] == "inherit"
    assert listing[str(b)]["exclude"] == "own"            # default
    assert "dedup" not in listing[str(b)]                  # owner only: no policy
    assert test_db.query(SectionPolicy).count() == 1


@pytest.mark.parametrize("body,code", [
    ({"section": "dedup", "mode": "own"}, 400),            # owner-only section
    ({"section": "notifications", "mode": "inherit"}, 400),  # own_always
    ({"section": "nope", "mode": "own"}, 400),
    ({"section": "models", "mode": "sometimes"}, 400),
])
def test_policy_patch_rejects_bad_input(test_db, accounts, body, code):
    a, b = accounts
    with use_account(a):
        with pytest.raises(HTTPException) as e:
            R.update_policy({"account_id": str(b), **body}, db=test_db)
    assert e.value.status_code == code


def test_policy_patch_rejects_the_owner_and_unknown_accounts(test_db, accounts):
    import uuid
    a, b = accounts
    with use_account(a):
        with pytest.raises(HTTPException) as e:
            R.update_policy({"account_id": str(a), "section": "models", "mode": "own"}, db=test_db)
        assert e.value.status_code == 400
        with pytest.raises(HTTPException) as e:
            R.update_policy({"account_id": str(uuid.uuid4()), "section": "models", "mode": "own"}, db=test_db)
        assert e.value.status_code == 404


def test_members_cannot_change_or_list_policies(test_db, accounts):
    a, b = accounts
    with use_account(b):
        with pytest.raises(HTTPException) as e:
            R.update_policy({"account_id": str(b), "section": "models", "mode": "own"}, db=test_db)
        assert e.value.status_code == 403
        with pytest.raises(HTTPException) as e:
            R.get_policies(db=test_db)
        assert e.value.status_code == 403


def test_policy_endpoint_over_http_as_owner(client, test_db, accounts):
    a, b = accounts
    r = client.patch("/api/settings/policies", json={"account_id": str(b), "section": "letters", "mode": "own"})
    assert r.status_code == 200, r.text
    assert client.get("/api/settings/policies").json()[str(b)]["letters"] == "own"


# ── GET /api/settings ────────────────────────────────────────────────────────

def test_owner_get_is_unchanged_and_never_shows_member_rows(client, test_db, accounts):
    a, b = accounts
    set_setting(test_db, "title_exclude_global", '["intern"]')
    set_setting(test_db, "anthropic_api_key", "sk-owner")
    _own(test_db, b, "title_exclude_global", '["senior"]')
    body = client.get("/api/settings").json()
    assert "_meta" not in body
    assert body["title_exclude_global"] == ["intern"]
    assert body["anthropic_api_key"] == "•" * 6
    meta = client.get("/api/settings?meta=1").json()["_meta"]
    assert meta["title_exclude_global"] == {"section": "exclude", "editable": True, "source": "install"}


def test_member_get_returns_effective_values_redacted_with_meta(test_db, accounts):
    a, b = accounts
    set_setting(test_db, "title_exclude_global", '["intern"]')
    set_setting(test_db, "telegram_chat_id", "owner-chat")
    set_setting(test_db, "anthropic_api_key", "sk-owner")
    set_setting(test_db, "linkedin_password", "")
    set_setting(test_db, "proxy_url", "socks5://owner")
    _own(test_db, b, "title_exclude_global", '["senior"]')
    _own(test_db, b, "linkedin_password", "hunter2")
    with use_account(b):
        body = R.get_settings(meta=False, db=test_db)
    meta = body.pop("_meta")
    assert body["title_exclude_global"] == ["senior"]
    assert body["telegram_chat_id"] == ""                       # own_always: not the owner's chat
    assert body["anthropic_api_key"] == "•" * 6                  # inherited, still redacted
    assert body["linkedin_password"] == "•" * 6            # own secret, redacted
    assert meta["title_exclude_global"] == {"section": "exclude", "editable": True, "source": "account"}
    assert meta["anthropic_api_key"] == {"section": "models", "editable": False, "source": "install",
                                   "set_by_owner": True}
    assert meta["telegram_chat_id"]["source"] == "default" and meta["telegram_chat_id"]["editable"]
    assert meta["proxy_url"] == {"section": "advanced", "editable": False, "source": "install"}


# ── consumers ────────────────────────────────────────────────────────────────

def test_resolve_llm_config_honours_a_member_own_model(test_db, accounts):
    from backend.analyzer.llm_client import resolve_llm_config
    a, b = accounts
    set_setting(test_db, "llm_provider", "claude_api")
    set_setting(test_db, "llm_model", "owner-model")
    _own(test_db, b, "llm_model", "member-model")
    with use_account(b):
        assert resolve_llm_config("", db=test_db)["model"] == "owner-model"   # models inherit by default
    _policy(test_db, b, "models", "own")
    with use_account(b):
        assert resolve_llm_config("", db=test_db)["model"] == "member-model"
        assert resolve_llm_config("scoring", db=test_db)["model"] == "member-model"
    with use_account(a):
        assert resolve_llm_config("", db=test_db)["model"] == "owner-model"


def test_title_exclude_filter_uses_the_member_list(test_db, accounts):
    from backend.models.db import get_global_title_exclude
    a, b = accounts
    set_setting(test_db, "title_exclude_global", '["intern"]')
    _own(test_db, b, "title_exclude_global", '["senior"]')
    with use_account(a):
        assert get_global_title_exclude(test_db) == ["intern"]
    with use_account(b):
        assert get_global_title_exclude(test_db) == ["senior"]


def test_runtime_writer_goes_to_the_member_row(test_db, accounts):
    """jobright's session cookie: section 'jobright' is own by default, so a member's
    scrape stores its own session and leaves the owner's alone."""
    from backend.scraper.sources import jobright
    a, b = accounts
    set_setting(test_db, "jobright_session_id", "owner-session")
    with use_account(b):
        jobright._save_setting(test_db, "jobright_session_id", "member-session")
        assert jobright._get_setting(test_db, "jobright_session_id") == "member-session"
    with use_account(a):
        assert jobright._get_setting(test_db, "jobright_session_id") == "owner-session"


def test_webhook_secret_rotation_stays_install(test_db, accounts, monkeypatch):
    from backend.notifier import telegram
    a, b = accounts
    set_setting(test_db, "telegram_webhook_secret", "old")
    with use_account(b):
        new = telegram.rotate_webhook_secret()
    test_db.expire_all()
    rows = test_db.query(Setting).filter(Setting.key == "telegram_webhook_secret").all()
    assert [(r.account_id, r.value) for r in rows] == [(None, new)]


# ── default résumé (MT-4 leftover) ───────────────────────────────────────────

def test_default_resume_never_hands_another_accounts_resume(test_db, accounts):
    a, b = accounts
    with use_account(a):
        r = Resume(name="Owner base", is_base=True, json_data={})
        test_db.add(r)
        test_db.commit()
        rid = str(r.id)
    set_setting(test_db, "default_resume_id", rid)
    with use_account(a):
        assert S.default_resume_ids(test_db) == [rid]
    with use_account(b):
        assert S.get_setting(test_db, "default_resume_id") == ""   # own_always, seeded default
        assert S.default_resume_ids(test_db) == []
        # even a member row pointing at the owner's résumé is dropped
        _own(test_db, b, "default_resume_id", rid)
        assert S.default_resume_ids(test_db) == []
        mine = Resume(name="Member base", is_base=True, json_data={})
        test_db.add(mine)
        test_db.commit()
        test_db.query(Setting).filter(Setting.account_id == b).one().value = str(mine.id)
        test_db.commit()
        assert S.default_resume_ids(test_db) == [str(mine.id)]


def test_auto_created_company_never_gets_the_owners_resume(test_db, accounts):
    """POST /companies/auto-create-from-jobs as a member: the new company's résumé list
    comes from the member's own default, not the owner's install value."""
    from unittest.mock import MagicMock
    from backend.api.routes_companies import auto_create_from_jobs
    from backend.models.db import Company
    from backend.tests.r4_support import make_job
    a, b = accounts
    with use_account(a):
        r = Resume(name="Owner base", is_base=True, json_data={})
        test_db.add(r)
        test_db.commit()
    set_setting(test_db, "default_resume_id", str(r.id))
    with use_account(b):
        make_job(test_db, company="Member Co")
        out = auto_create_from_jobs(MagicMock(), db=test_db)
        assert out["created"] == 1
        co = test_db.query(Company).filter(Company.name == "Member Co").one()
        assert co.selected_resume_ids == []
    with use_account(a):
        make_job(test_db, company="Owner Co")
        auto_create_from_jobs(MagicMock(), db=test_db)
        co = test_db.query(Company).filter(Company.name == "Owner Co").one()
        assert co.selected_resume_ids == [str(r.id)]


# ── schema ───────────────────────────────────────────────────────────────────

def test_one_install_row_and_one_row_per_account_per_key(test_db, accounts):
    from sqlalchemy.exc import IntegrityError
    a, b = accounts
    set_setting(test_db, "proxy_url", "x")
    _own(test_db, b, "proxy_url", "y")
    test_db.add(Setting(key="proxy_url", value="dup"))
    with pytest.raises(IntegrityError):
        test_db.commit()
    test_db.rollback()
    test_db.add(Setting(key="proxy_url", value="dup", account_id=b))
    with pytest.raises(IntegrityError):
        test_db.commit()
    test_db.rollback()


def test_member_rows_cascade_with_the_account():
    fk = list(Setting.__table__.c.account_id.foreign_keys)[0]
    assert fk.ondelete == "CASCADE"
    assert list(SectionPolicy.__table__.c.account_id.foreign_keys)[0].ondelete == "CASCADE"


def test_migration_statements_are_postgres_only(test_db):
    from backend.seed import SETTINGS_SCOPING_STATEMENTS, _migrate_settings_scoping
    assert any("uq_settings_install_key" in s for s in SETTINGS_SCOPING_STATEMENTS)
    _migrate_settings_scoping(test_db)   # SQLite: no-op, no warnings
