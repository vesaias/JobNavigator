"""_flatten_qa_bank must read both qa_bank shapes.

The canonical entry is {"question": ..., "answer": ...} — what POST /persona/qa-bank
writes and what the Persona editor saves. Hand-written banks used a single-key map
{"<question>": "<answer>"} instead, and the reader only understood the canonical
form, so every such entry flattened to a blank "Q: \nA: " block and the whole bank
silently vanished from the autofill prompt. Both shapes are accepted now.
"""
from backend.api.routes_autofill import _flatten_qa_bank, _qa_pair


def test_canonical_shape():
    out = _flatten_qa_bank([{"question": "Why us?", "answer": "Because."}])
    assert out == "Q: Why us?\nA: Because."


def test_legacy_single_key_shape():
    out = _flatten_qa_bank([{"Why us?": "Because."}])
    assert out == "Q: Why us?\nA: Because."


def test_mixed_bank_keeps_every_entry():
    out = _flatten_qa_bank([
        {"A?": "1"},
        {"question": "B?", "answer": "2"},
    ])
    assert out == "Q: A?\nA: 1\n\nQ: B?\nA: 2"


def test_empty_and_junk_entries_are_dropped():
    assert _flatten_qa_bank([]) == "(empty)"
    assert _flatten_qa_bank(None) == "(empty)"
    # entries that carry no text at all must not pad the prompt with blank pairs
    assert _flatten_qa_bank([{}, None, "nonsense", {"question": "", "answer": ""}]) == "(empty)"


def test_partial_canonical_entry_is_kept():
    assert _flatten_qa_bank([{"question": "Only a question?"}]) == "Q: Only a question?\nA: "


def test_qa_pair_normalisation():
    assert _qa_pair({"question": "q", "answer": "a"}) == ("q", "a")
    assert _qa_pair({"q": "a"}) == ("q", "a")
    assert _qa_pair({}) == ("", "")
    assert _qa_pair(None) == ("", "")
    # a canonical entry with a None side must not become the string "None"
    assert _qa_pair({"question": "q", "answer": None}) == ("q", "")
