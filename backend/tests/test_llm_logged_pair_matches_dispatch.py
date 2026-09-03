"""R2-H-15: llm_call_log must record the provider/model that actually dispatched.

Cover-letter generation logged a hardcoded claude_api / claude-sonnet-4-6 while
call_cover_letter_llm dispatched on the primary pair, so the cost report priced
letters against a model that was never called. Every feature now resolves the
pair once, through llm_client.resolve_llm_config().
"""
import pytest

from backend.models.db import Setting, LlmCallLog


PRIMARY = {"llm_provider": "claude_code", "llm_model": "claude-sonnet-5", "llm_api_key": "pk"}


def _seed_primary_only(db):
    """Primary set, every per-feature override empty — the shipped state."""
    for k, v in PRIMARY.items():
        db.add(Setting(key=k, value=v))
    for feature in ("email", "cv_tailor", "cover_letter", "autofill", "scoring"):
        for suffix in ("provider", "model", "api_key"):
            db.add(Setting(key=f"{feature}_llm_{suffix}", value=""))
    db.commit()


@pytest.mark.parametrize("feature", ["", "email", "cv_tailor", "cover_letter", "autofill", "scoring"])
def test_resolve_falls_back_to_primary(test_db, feature):
    from backend.analyzer.llm_client import resolve_llm_config

    _seed_primary_only(test_db)
    cfg = resolve_llm_config(feature)
    assert (cfg["provider"], cfg["model"]) == ("claude_code", "claude-sonnet-5")


def test_resolve_prefers_feature_override(test_db):
    from backend.analyzer.llm_client import resolve_llm_config

    _seed_primary_only(test_db)
    row = test_db.query(Setting).filter(Setting.key == "cover_letter_llm_model").one()
    row.value = "claude-opus-4-1"
    test_db.commit()

    cfg = resolve_llm_config("cover_letter")
    # provider still falls through to primary, model comes from the override
    assert (cfg["provider"], cfg["model"]) == ("claude_code", "claude-opus-4-1")


@pytest.mark.asyncio
@pytest.mark.parametrize("feature,purpose,fn_name", [
    ("", "pdf", "call_llm"),
    ("email", "email", "call_email_llm"),
    ("cv_tailor", "tailor", "call_cv_tailor_llm"),
    ("cover_letter", "cover_letter", "call_cover_letter_llm"),
    ("autofill", "autofill", "call_autofill_llm"),
])
async def test_logged_pair_equals_dispatched_pair(test_db, monkeypatch, feature, purpose, fn_name):
    """With per-feature settings empty and the primary set, the row logged by
    track_llm_call names exactly the pair _dispatch was called with."""
    import backend.analyzer.llm_client as L
    from backend.analyzer.llm_logger import track_llm_call

    _seed_primary_only(test_db)
    dispatched = []

    async def fake_dispatch(provider, model, api_key, prompt, system, max_tokens, cached_prefix=None):
        dispatched.append((provider, model))
        return {"text": "ok", "usage": {"input_tokens": 10, "output_tokens": 2,
                                        "cache_read_tokens": 0, "cache_write_tokens": 0}}

    monkeypatch.setattr(L, "_dispatch", fake_dispatch)

    cfg = L.resolve_llm_config(feature)
    async with track_llm_call(purpose, cfg["provider"], cfg["model"]) as tracker:
        resp = await getattr(L, fn_name)("prompt", "system")
        tracker.record(resp)

    assert dispatched == [("claude_code", "claude-sonnet-5")]
    row = test_db.query(LlmCallLog).filter(LlmCallLog.purpose == purpose).one()
    assert (row.provider, row.model) == dispatched[0]
    assert row.input_tokens == 10


@pytest.mark.asyncio
async def test_logged_pair_follows_fallback_dispatch(test_db, monkeypatch):
    """When call_llm falls back to the secondary pair, that pair is logged."""
    import backend.analyzer.llm_client as L
    from backend.analyzer.llm_logger import track_llm_call

    _seed_primary_only(test_db)
    test_db.add(Setting(key="llm_fallback_provider", value="claude_api"))
    test_db.add(Setting(key="llm_fallback_model", value="claude-opus-4-1"))
    test_db.add(Setting(key="llm_fallback_api_key", value="fk"))
    test_db.commit()
    monkeypatch.setattr(L.asyncio, "sleep", _no_sleep)

    async def fake_dispatch(provider, model, api_key, prompt, system, max_tokens, cached_prefix=None):
        if provider == "claude_code":
            raise RuntimeError("primary down")
        return {"text": "ok", "usage": {}}

    monkeypatch.setattr(L, "_dispatch", fake_dispatch)

    cfg = L.resolve_llm_config("")
    async with track_llm_call("score_full", cfg["provider"], cfg["model"]) as tracker:
        tracker.record(await L.call_llm("p", "s", 100))

    row = test_db.query(LlmCallLog).one()
    assert (row.provider, row.model) == ("claude_api", "claude-opus-4-1")


async def _no_sleep(*_a, **_kw):
    return None


@pytest.mark.asyncio
async def test_cover_letter_body_reports_dispatched_pair(test_db, monkeypatch):
    """generate_cover_letter_body hands the caller the pair that ran, which is
    what routes_cover_letters._generate_inner logs."""
    import backend.analyzer.llm_client as L
    import backend.analyzer.cover_letter_generator as G

    _seed_primary_only(test_db)

    async def fake_dispatch(provider, model, api_key, prompt, system, max_tokens, cached_prefix=None):
        return {"text": '{"greeting":"Dear team,","body_paragraphs":["a"],'
                        '"closing":"Sincerely,","signature":"Me"}',
                "usage": {"input_tokens": 5, "output_tokens": 1}}

    monkeypatch.setattr(L, "_dispatch", fake_dispatch)

    out = await G.generate_cover_letter_body(
        {"summary": "s"}, {}, "JD text", "voice", "standard",
        "{resume}\n{preferences}\n{job_description}\n{voice}\n{length}",
    )
    assert out["_llm"]["provider"] == "claude_code"
    assert out["_llm"]["model"] == "claude-sonnet-5"
