from backend.models.db import Setting, Persona


def _seed(test_db):
    test_db.add(Setting(key="dashboard_api_key", value=""))
    test_db.commit()
    from backend.seed import seed_settings, seed_persona
    seed_settings(test_db)
    seed_persona(test_db)


def test_config_returns_projected_answers_and_dicts(api_client, test_db):
    _seed(test_db)
    p = test_db.query(Persona).filter(Persona.id == 1).first()
    p.demographics = {"gender": "male", "veteran_status": "not_protected_veteran",
                      "decline_demographics": True}
    p.work_auth = {"authorized_us": True}
    test_db.commit()

    resp = api_client.get("/api/autofill/config")
    assert resp.status_code == 200
    data = resp.json()
    # decline_self_id comes from the Persona's own decline_demographics checkbox, not a separate setting.
    assert data["answers"]["gender"] == "male"
    assert data["answers"]["authorized_us"] is True
    assert data["decline_self_id"] is True
    assert "veteran_status" in data["field_patterns"]
    assert data["option_synonyms"]["_bool"]["true"] == ["yes", "true"]
    assert data["schema"]["gender"]["kind"] == "enum"


def test_decline_flag_follows_persona_checkbox(api_client, test_db):
    _seed(test_db)
    p = test_db.query(Persona).filter(Persona.id == 1).first()
    p.demographics = {"gender": "male"}          # checkbox left off
    test_db.commit()
    assert api_client.get("/api/autofill/config").json()["decline_self_id"] is False

    p.demographics = {"gender": "male", "decline_demographics": True}
    test_db.commit()
    assert api_client.get("/api/autofill/config").json()["decline_self_id"] is True
