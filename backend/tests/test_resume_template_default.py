"""Settings › Tailoring › Default résumé template (`resume_template`): Last selected (the
default: the template this account last picked in the résumé editor) or a fixed template."""
import pytest

from backend.models.db import Account, Setting


def _seed(db, value=None):
    db.add(Setting(key="dashboard_api_key", value=""))
    if value is not None:
        db.add(Setting(key="resume_template", value=value))
    db.commit()


def _new(api_client, name="New"):
    r = api_client.post("/api/resumes", json={"name": name, "is_base": True, "json_data": {}})
    assert r.status_code == 201
    return r.json()


def _first():
    from backend.api.routes_resumes import _discover_templates
    return _discover_templates()[0]["id"]


@pytest.mark.parametrize("value", [None, "last_selected", ""])
def test_before_any_pick_a_new_resume_gets_the_first_template(api_client, test_db, value):
    _seed(test_db, value)
    assert _new(api_client)["template"] == _first()


def test_last_selected_is_the_template_last_picked_in_the_editor(api_client, test_db):
    _seed(test_db, "last_selected")
    first = _new(api_client)
    assert api_client.patch(f"/api/resumes/{first['id']}", json={"template": "palatino"}).status_code == 200
    assert _new(api_client, "Second")["template"] == "palatino"
    # an edit that is not a template pick changes nothing
    api_client.patch(f"/api/resumes/{first['id']}", json={"name": "Renamed"})
    assert _new(api_client, "Third")["template"] == "palatino"


def test_a_chosen_template_goes_on_every_new_resume(api_client, test_db):
    _seed(test_db, "inter")
    first = _new(api_client)
    assert first["template"] == "inter"
    api_client.patch(f"/api/resumes/{first['id']}", json={"template": "palatino"})
    assert _new(api_client, "Second")["template"] == "inter"


def test_a_template_given_on_create_wins(api_client, test_db):
    _seed(test_db, "inter")
    r = api_client.post("/api/resumes", json={"name": "X", "template": "raleway", "json_data": {}})
    assert r.json()["template"] == "raleway"


def test_a_copy_for_a_job_keeps_its_resume_template(api_client, test_db):
    from backend.tests.test_routes_cover_letters import _make_job
    _seed(test_db, "inter")
    base = api_client.post("/api/resumes", json={"name": "Base", "template": "raleway", "json_data": {}}).json()
    job = _make_job(test_db)
    copy = api_client.post("/api/resumes/copy", json={"base_resume_id": base["id"], "job_id": str(job.id)})
    assert copy.json()["template"] == "raleway"


def test_last_selected_stays_with_the_account_that_picked_it(test_db):
    from backend.accounts.context import use_account
    from backend.api.routes_resumes import _default_template_id, remember_template

    owner = Account(name="Owner", role="owner")
    member = Account(name="Partner", role="member")
    test_db.add_all([owner, member])
    test_db.commit()
    with use_account(owner.id):
        remember_template(test_db, "resume_last_template", "palatino")
        test_db.commit()
        assert _default_template_id(test_db) == "palatino"
    with use_account(member.id):
        assert _default_template_id(test_db) == _first()
        remember_template(test_db, "resume_last_template", "inter")
        test_db.commit()
        assert _default_template_id(test_db) == "inter"
    with use_account(owner.id):
        assert _default_template_id(test_db) == "palatino"


@pytest.mark.parametrize("value,status", [("inter", 200), ("modern", 200), ("", 200), ("last_selected", 200),
                                          ("same_as_resume", 422), ("../x", 422), (5, 422)])
def test_patch_settings_validates_resume_template(api_client, test_db, value, status):
    _seed(test_db)
    assert api_client.patch("/api/settings", json={"resume_template": value}).status_code == status
