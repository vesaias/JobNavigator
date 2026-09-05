"""Tests for migrate_llm_settings — model-list refresh + openai_compat removal."""
import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.models.db import Setting
from backend.seed import migrate_llm_settings, DEFAULT_SETTINGS


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Setting.__table__.create(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


def _default_list():
    return json.loads(DEFAULT_SETTINGS["llm_models_list"][0])


def test_stale_list_gains_defaults_and_drops_dead_provider(db):
    """Additive migration: openai_compat is dropped, every current default is present, and pre-existing valid entries are kept."""
    stale = [
        {"provider": "claude_api", "model": "claude-sonnet-4-6"},
        {"provider": "claude_api", "model": "claude-opus-4-6"},
        {"provider": "openai_compat", "model": "anthropic/claude-sonnet-4-6"},
    ]
    db.add(Setting(key="llm_models_list", value=json.dumps(stale)))
    db.commit()

    migrate_llm_settings(db)

    result = json.loads(db.query(Setting).filter(Setting.key == "llm_models_list").first().value)
    # dead provider dropped
    assert not any(m["provider"] == "openai_compat" for m in result)
    # every default present (superset)
    for d in _default_list():
        assert any(m["provider"] == d["provider"] and m["model"] == d["model"] for m in result)
    # pre-existing valid entry kept
    assert any(m["provider"] == "claude_api" and m["model"] == "claude-sonnet-4-6" for m in result)
    # new defaults added
    assert any(m["model"] == "claude-sonnet-5" for m in result)
    assert any(m["model"] == "claude-opus-4-8" for m in result)
    assert any(m["model"] == "claude-fable-5" for m in result)


def test_deleted_default_not_readded_after_seeding(db):
    """Once defaults are seeded (recorded in llm_seeded_models), deleting one keeps it gone across restarts; the migration does not resurrect it."""
    db.add(Setting(key="llm_models_list", value=json.dumps(_default_list())))
    db.commit()
    migrate_llm_settings(db)  # first run records the seen-set

    lst = json.loads(db.query(Setting).filter(Setting.key == "llm_models_list").first().value)
    victim = lst[0]
    row = db.query(Setting).filter(Setting.key == "llm_models_list").first()
    row.value = json.dumps([m for m in lst if m != victim])
    db.commit()

    migrate_llm_settings(db)  # second run must not resurrect the deleted default
    result = json.loads(db.query(Setting).filter(Setting.key == "llm_models_list").first().value)
    assert victim not in result


def test_custom_entries_preserved(db):
    """User-added custom models survive the refresh; custom openai_compat entries don't."""
    stale = _default_list() + [
        {"provider": "ollama", "model": "my-local:13b", "label": "my-local:13b (custom)", "custom": True},
        {"provider": "openai_compat", "model": "x/y", "label": "x/y (custom)", "custom": True},
    ]
    db.add(Setting(key="llm_models_list", value=json.dumps(stale)))
    db.commit()

    migrate_llm_settings(db)

    result = json.loads(db.query(Setting).filter(Setting.key == "llm_models_list").first().value)
    assert {"provider": "ollama", "model": "my-local:13b", "label": "my-local:13b (custom)",
            "custom": True} in result
    assert not any(m["provider"] == "openai_compat" for m in result)


def test_openai_compat_provider_repointed(db):
    db.add(Setting(key="llm_provider", value="openai_compat"))
    db.add(Setting(key="email_llm_provider", value="claude_code"))
    db.commit()

    migrate_llm_settings(db)

    assert db.query(Setting).filter(Setting.key == "llm_provider").first().value == "openai"
    assert db.query(Setting).filter(Setting.key == "email_llm_provider").first().value == "claude_code"


def test_dated_haiku_model_renamed_to_alias(db):
    db.add(Setting(key="llm_fallback_model", value="claude-haiku-4-5-20251001"))
    db.add(Setting(key="email_llm_model", value="claude-haiku-4-5-20251001"))
    db.add(Setting(key="llm_model", value="claude-sonnet-4-6"))
    db.commit()

    migrate_llm_settings(db)

    assert db.query(Setting).filter(Setting.key == "llm_fallback_model").first().value == "claude-haiku-4-5"
    assert db.query(Setting).filter(Setting.key == "email_llm_model").first().value == "claude-haiku-4-5"
    # Non-haiku models untouched
    assert db.query(Setting).filter(Setting.key == "llm_model").first().value == "claude-sonnet-4-6"


def test_idempotent(db):
    db.add(Setting(key="llm_models_list", value=json.dumps(_default_list())))
    db.commit()
    migrate_llm_settings(db)
    first = db.query(Setting).filter(Setting.key == "llm_models_list").first().value
    migrate_llm_settings(db)
    second = db.query(Setting).filter(Setting.key == "llm_models_list").first().value
    assert first == second == json.dumps(_default_list())
