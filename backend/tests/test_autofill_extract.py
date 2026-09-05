# -*- coding: utf-8 -*-
r"""The JSON envelope must never reach the user as the answer; _extract_answer is pure, so these run without the container or an LLM."""
from backend.api.routes_autofill import _extract_answer


# 1 — clean JSON, the happy path
def test_clean_json_envelope():
    assert _extract_answer('{"answer": "I led the payments launch."}') == "I led the payments launch."


def test_clean_json_with_other_keys_and_whitespace():
    raw = '\n  {"answer": "Nine weeks, one squad.", "confidence": 0.8}\n'
    assert _extract_answer(raw) == "Nine weeks, one squad."


def test_preamble_before_the_object_is_discarded():
    raw = 'Sure — here is the answer:\n{"answer": "Because the mission is the work."}'
    assert _extract_answer(raw) == "Because the mission is the work."


def test_prose_after_the_object_no_longer_breaks_the_parse():
    # the old regex ran to the LAST brace in the reply, so this parsed as nothing
    raw = '{"answer": "Shipped it."}\nLet me know if you want a longer version {smile}'
    assert _extract_answer(raw) == "Shipped it."


def test_escapes_and_braces_inside_the_answer_survive():
    raw = '{"answer": "She said \\"ship it\\" — and the {beta} went out."}'
    assert _extract_answer(raw) == 'She said "ship it" — and the {beta} went out.'


# 2 — fenced JSON
def test_fenced_json():
    assert _extract_answer('```json\n{"answer": "Fenced but fine."}\n```') == "Fenced but fine."


def test_bare_fence_without_a_language_tag():
    assert _extract_answer('```\n{"answer": "Still fine."}\n```') == "Still fine."


def test_fenced_plain_prose():
    assert _extract_answer("```\nJust the prose, no JSON.\n```") == "Just the prose, no JSON."


# 3 — truncated envelope: the exact shape that leaked
def test_truncated_envelope_is_salvaged_not_served():
    raw = ('{"answer": "At additiv I owned a Tier 1 bank platform delivery where 5 '
           'engineering squads had conflicting views')
    out = _extract_answer(raw)
    assert not out.startswith("{")
    assert out.startswith("At additiv I owned")
    assert out.endswith("conflicting views")
    assert '"answer"' not in out


def test_truncated_envelope_with_escapes():
    raw = '{"answer": "First line.\nThen a \\"quoted\\" bit that stops mid-'
    out = _extract_answer(raw)
    assert not out.startswith("{")
    assert out.startswith("First line.\nThen a \"quoted\" bit")


def test_truncated_envelope_closing_quote_but_no_brace():
    raw = '{"answer": "Complete sentence, missing only the brace."'
    assert _extract_answer(raw) == "Complete sentence, missing only the brace."


def test_unsalvageable_envelope_returns_empty_so_the_route_502s():
    # a wrapper with no answer key at all: nothing to hand the user
    assert _extract_answer('{"reasoning": "thinking out loud", "other": 1}') == ""
    assert _extract_answer("{ this is not json and never closes") == ""


# 4 — plain text
def test_plain_prose_passes_through():
    assert _extract_answer("I want to work here because the mission is the work.") == \
        "I want to work here because the mission is the work."


def test_quoted_prose_loses_only_its_quotes():
    assert _extract_answer('"Quoted prose."') == "Quoted prose."


def test_json_string_reply_is_unwrapped():
    assert _extract_answer('"A bare JSON string."') == "A bare JSON string."


def test_empty_and_none():
    assert _extract_answer("") == ""
    assert _extract_answer(None) == ""


# the invariant the whole finding is about
def test_no_output_ever_begins_with_a_brace():
    samples = [
        '{"answer": "ok"}',
        '```json\n{"answer": "ok"}\n```',
        '{"answer": "truncated mid-sen',
        '{"reasoning": "no answer key"}',
        "{ garbage",
        "plain prose",
        '{"answer": ""}',
    ]
    for s in samples:
        assert not _extract_answer(s).startswith("{"), s
