"""R4-T6 coverage · routes_autofill: the `_build_autofill_prompt` contract and the SSE path.

`_build_autofill_prompt` and both endpoints open their own `SessionLocal()`, and
the `test_db` fixture rebinds that to the in-memory DB, so these call the
functions directly instead of paying for a TestClient.
"""
import json

import pytest
from fastapi import HTTPException

from backend.api.routes_autofill import (
    _build_autofill_prompt, _extract_answer, autofill_answer_stream,
)
from backend.models.db import Persona, Setting
from backend.seed import DEFAULT_SETTINGS

PROMPT = DEFAULT_SETTINGS["autofill_prompt"][0]


def _seed(db, *, prompt=PROMPT, default_len="250", persona=True):
    if prompt is not None:
        db.add(Setting(key="autofill_prompt", value=prompt))
    if default_len is not None:
        db.add(Setting(key="autofill_default_length", value=default_len))
    if persona:
        db.add(Persona(id=1, contact={"name": "V"}, work_auth={}, demographics={},
                       compensation={}, preferences={"tone": "plain"},
                       resume_content={"summary": "fintech PM"},
                       qa_bank=[{"question": "Why fintech?", "answer": "Because payments."}]))
    db.commit()


BODY = {"question": "Why us?", "company": "Rogo", "position": "PM"}


# ── _extract_answer numeric coercion ────────────────────────────────────────


@pytest.mark.parametrize("raw,expected", [
    ('{"answer": 42}', "42"),
    ('{"answer": 3.5}', "3.5"),
    ('{"answer": -7}', "-7"),
])
def test_numeric_answer_is_coerced_to_a_string(raw, expected):
    """A model that answers with a bare number still yields usable text."""
    assert _extract_answer(raw) == expected


@pytest.mark.parametrize("raw", ['{"answer": true}', '{"answer": false}'])
def test_boolean_answer_is_not_coerced(raw):
    """Booleans are explicitly excluded from the numeric coercion, so nothing is salvaged."""
    assert _extract_answer(raw) == ""


# ── _build_autofill_prompt: question ────────────────────────────────────────


@pytest.mark.parametrize("body", [{}, {"question": ""}, {"question": "   "},
                                  {"question": None, "company": "Rogo"}])
def test_a_missing_or_blank_question_is_a_400(test_db, body):
    """The question is the only truly required field."""
    _seed(test_db)
    with pytest.raises(HTTPException) as e:
        _build_autofill_prompt(body)
    assert e.value.status_code == 400


def test_company_and_position_default_to_placeholders(test_db):
    """Blank company/position are rendered as explicit "(unknown …)" markers, not empties."""
    _seed(test_db)
    built = _build_autofill_prompt({"question": "Why us?"})
    assert "(unknown company)" in built["suffix"]
    assert "(unknown role)" in built["suffix"]


# ── _build_autofill_prompt: the template setting ────────────────────────────


def test_a_missing_autofill_prompt_setting_is_a_500(test_db):
    """Without the editable template there is nothing to send — fail loudly."""
    _seed(test_db, prompt=None)
    with pytest.raises(HTTPException) as e:
        _build_autofill_prompt(BODY)
    assert e.value.status_code == 500


def test_a_blank_autofill_prompt_setting_is_a_500(test_db):
    """A whitespace-only template counts as absent."""
    _seed(test_db, prompt="   \n ")
    with pytest.raises(HTTPException) as e:
        _build_autofill_prompt(BODY)
    assert e.value.status_code == 500


def test_a_template_without_a_company_placeholder_becomes_all_suffix(test_db):
    """No {company} split point → nothing is cacheable and the whole template is the suffix.

    Every placeholder is still expanded there: the split decides what is CACHEABLE,
    not what gets substituted. This used to leave a literal "{persona}" in the
    prompt whenever the template was written without {company} (R4-E2E-04).
    """
    _seed(test_db, prompt="Answer {question} in {max_chars} chars for {persona}.")
    built = _build_autofill_prompt(BODY)
    assert built["cached_prefix"] is None
    assert "{persona}" not in built["suffix"]
    assert built["suffix"].startswith("Answer Why us? in 250 chars for ")
    assert "fintech PM" in built["suffix"]         # the flattened persona, not the token


def test_every_placeholder_is_substituted_in_both_halves(test_db):
    """No placeholder survives, wherever the {company} split falls (R4-E2E-04)."""
    _seed(test_db, prompt="{persona}|{qa_bank}|{question}|{company}|{position}|{max_chars}")
    built = _build_autofill_prompt(BODY)
    whole = (built["cached_prefix"] or "") + built["suffix"]
    for token in ("{persona}", "{qa_bank}", "{question}", "{company}", "{position}", "{max_chars}"):
        assert token not in whole, token
    assert "Because payments." in whole and "Rogo" in whole and "Why us?" in whole


def test_a_question_placeholder_before_company_is_filled_too(test_db):
    """A template that asks the question before naming the company still reads."""
    _seed(test_db, prompt="Q: {question}\nProfile: {persona}\nAt {company} for {position}.")
    built = _build_autofill_prompt(BODY)
    assert "{question}" not in built["cached_prefix"]
    assert "Why us?" in built["cached_prefix"]
    assert "fintech PM" in built["cached_prefix"]


def test_the_split_puts_persona_and_qa_bank_in_the_cacheable_prefix(test_db):
    """The default template splits at {company}: profile before, question after."""
    _seed(test_db)
    built = _build_autofill_prompt(BODY)
    assert "Because payments." in built["cached_prefix"]
    assert "Because payments." not in built["suffix"]
    assert built["suffix"].startswith("Rogo - PM")
    assert "Why us?" in built["suffix"]


def test_no_persona_row_renders_a_placeholder(test_db):
    """A DB with no Persona still produces a prompt, marked "(no persona)"."""
    _seed(test_db, persona=False)
    built = _build_autofill_prompt(BODY)
    assert "(no persona)" in built["cached_prefix"]


# ── _build_autofill_prompt: max_chars resolution ────────────────────────────


def test_default_length_setting_is_used_when_no_max_chars_is_given(test_db):
    _seed(test_db, default_len="180")
    assert _build_autofill_prompt(BODY)["max_chars"] == 180


@pytest.mark.parametrize("stored", ["abc", "", "12.5", "-40", None])
def test_a_non_digit_default_length_falls_back_to_120(test_db, stored):
    """Anything `str.isdigit()` rejects (including a missing row) → the hardcoded 120."""
    _seed(test_db, default_len=stored)
    assert _build_autofill_prompt(BODY)["max_chars"] == 120


@pytest.mark.parametrize("supplied,expected", [
    ("300", 300),      # digit string from the extension
    (300, 300),        # real int
    ("abc", 250),      # junk → default_len
    ("", 250),
    (-5, 250),         # str(-5).isdigit() is False
    (None, 250),
    (True, 250),       # bool is an int in Python but "True".isdigit() is False
    ([300], 250),      # not int/str at all
])
def test_max_chars_resolution(test_db, supplied, expected):
    """max_chars is honoured only when it spells a plain non-negative integer."""
    _seed(test_db)
    built = _build_autofill_prompt({**BODY, "max_chars": supplied})
    assert built["max_chars"] == expected
    assert str(expected) in built["cached_prefix"]


# ── _build_autofill_prompt: provider resolution ─────────────────────────────


def test_want_provider_false_leaves_provider_and_model_unresolved(test_db):
    """The streaming path does not log an LLM call here, so it skips the resolver."""
    _seed(test_db)
    built = _build_autofill_prompt(BODY)
    assert built["provider"] is None and built["model"] is None


def test_want_provider_true_resolves_the_feature_override(test_db):
    """`autofill_llm_*` wins over the primary `llm_*` settings."""
    _seed(test_db)
    test_db.add(Setting(key="llm_provider", value="claude_api"))
    test_db.add(Setting(key="llm_model", value="claude-sonnet-5"))
    test_db.add(Setting(key="autofill_llm_provider", value="openai"))
    test_db.add(Setting(key="autofill_llm_model", value="gpt-4o-mini"))
    test_db.commit()

    built = _build_autofill_prompt(BODY, want_provider=True)
    assert built["provider"] == "openai"
    assert built["model"] == "gpt-4o-mini"


def test_want_provider_true_falls_back_to_the_primary(test_db):
    """With no per-feature override the primary settings are reported."""
    _seed(test_db)
    test_db.add(Setting(key="llm_provider", value="ollama"))
    test_db.add(Setting(key="llm_model", value="llama3"))
    test_db.commit()

    built = _build_autofill_prompt(BODY, want_provider=True)
    assert built["provider"] == "ollama"
    assert built["model"] == "llama3"


# ── /answer/stream ──────────────────────────────────────────────────────────


async def _collect(resp):
    return [chunk.decode() if isinstance(chunk, bytes) else chunk
            async for chunk in resp.body_iterator]


@pytest.mark.asyncio
async def test_stream_emits_deltas_then_done(test_db, monkeypatch):
    """Each non-empty chunk becomes a `data: {"delta": …}` event, closed by [DONE]."""
    _seed(test_db)
    seen = {}

    async def fake_stream(prompt, system, max_tokens=400, cached_prefix=None):
        seen["prompt"] = prompt
        seen["max_tokens"] = max_tokens
        for c in ("Because ", "", "payments."):
            yield c

    monkeypatch.setattr("backend.api.routes_autofill.call_autofill_llm_stream",
                        fake_stream, raising=True)

    events = await _collect(await autofill_answer_stream({**BODY, "max_chars": 200}))
    assert events == [
        'data: {"delta": "Because "}\n\n',
        'data: {"delta": "payments."}\n\n',
        "data: [DONE]\n\n",
    ]
    # ~4 chars/token plus a small buffer, floored at 48.
    assert seen["max_tokens"] == 74
    assert "no JSON, no quotes, no preamble" in seen["prompt"]


@pytest.mark.asyncio
async def test_stream_appends_refinements_in_order(test_db, monkeypatch):
    """Refinements become an ordered bullet list appended to the suffix only."""
    _seed(test_db)
    seen = {}

    async def fake_stream(prompt, system, max_tokens=400, cached_prefix=None):
        seen["prompt"] = prompt
        seen["prefix"] = cached_prefix
        yield "ok"

    monkeypatch.setattr("backend.api.routes_autofill.call_autofill_llm_stream",
                        fake_stream, raising=True)

    await _collect(await autofill_answer_stream(
        {**BODY, "refinements": ["shorter", "  ", "mention fintech work", ""]}))

    assert "Apply these changes the candidate requested, in order:" in seen["prompt"]
    assert "- shorter\n- mention fintech work" in seen["prompt"]
    # the cache prefix must stay identical to /answer's, so it carries no refinements
    assert "shorter" not in (seen["prefix"] or "")


@pytest.mark.parametrize("refinements", [[], ["", "   "], "not a list", None])
@pytest.mark.asyncio
async def test_stream_without_usable_refinements_adds_no_block(test_db, monkeypatch, refinements):
    """Empty, blank-only, missing or non-list refinements add nothing to the prompt."""
    _seed(test_db)
    seen = {}

    async def fake_stream(prompt, system, max_tokens=400, cached_prefix=None):
        seen["prompt"] = prompt
        yield "ok"

    monkeypatch.setattr("backend.api.routes_autofill.call_autofill_llm_stream",
                        fake_stream, raising=True)

    await _collect(await autofill_answer_stream({**BODY, "refinements": refinements}))
    assert "Apply these changes" not in seen["prompt"]


@pytest.mark.asyncio
async def test_stream_reports_a_provider_failure_as_an_error_event(test_db, monkeypatch):
    """A raising provider yields one generic error event — never the exception text."""
    _seed(test_db)

    async def fake_stream(prompt, system, max_tokens=400, cached_prefix=None):
        yield "partial"
        raise RuntimeError("anthropic 529 overloaded: key sk-ant-secret")

    monkeypatch.setattr("backend.api.routes_autofill.call_autofill_llm_stream",
                        fake_stream, raising=True)

    events = await _collect(await autofill_answer_stream(BODY))
    assert events[0] == 'data: {"delta": "partial"}\n\n'
    assert json.loads(events[-1][len("data: "):]) == {"error": "autofill generation failed"}
    assert "sk-ant-secret" not in "".join(events)
    assert "[DONE]" not in "".join(events)


@pytest.mark.asyncio
async def test_stream_rejects_a_missing_question_before_streaming(test_db):
    """The 400 is raised by the endpoint itself, not inside the SSE body."""
    _seed(test_db)
    with pytest.raises(HTTPException) as e:
        await autofill_answer_stream({"company": "Rogo"})
    assert e.value.status_code == 400
