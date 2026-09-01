import json
from backend.models.db import Setting
from backend.seed import DEFAULT_SETTINGS, seed_settings


def test_autofill_settings_present():
    for key in ("autofill_llm_provider", "autofill_llm_model",
                "autofill_default_length", "autofill_prompt"):
        assert key in DEFAULT_SETTINGS, f"missing default: {key}"


def test_autofill_prompt_has_placeholders():
    tmpl = DEFAULT_SETTINGS["autofill_prompt"][0]
    for ph in ("{persona}", "{qa_bank}", "{company}", "{position}", "{question}", "{max_chars}"):
        assert ph in tmpl, f"prompt missing placeholder {ph}"


def test_structured_autofill_settings_present(test_db):
    # The enabled/trigger toggles now live in the extension popup (chrome.storage),
    # not in DB settings. The dictionaries + decline policy are seeded here.
    seed_settings(test_db)
    keys = {s.key: s.value for s in test_db.query(Setting).all()}
    assert "autofill_decline_self_id" not in keys  # retired: Persona owns the decline flag
    patterns = json.loads(keys["autofill_field_patterns"])
    assert "veteran_status" in patterns and "veteran" in patterns["veteran_status"]
    syn = json.loads(keys["autofill_option_synonyms"])
    assert "not a veteran" in syn["veteran_status"]["not_protected_veteran"]
    assert "yes" in syn["_bool"]["true"]
