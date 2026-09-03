"""R3-B-04: `max_chars` is enforced server-side, not just suggested to the model.

Measured before the fix: a 120-char ask came back at 137, a 600-char ask at 714.
The extension only capped answers for fields that declare a `maxLength`, which the
usual Greenhouse/Lever/Ashby textarea does not — so the picked length was ignored
on exactly the fields it was picked for.
"""
import pytest

from backend.api.routes_autofill import _trim_to_chars


def test_short_answers_are_untouched():
    assert _trim_to_chars("Short enough.", 120) == ("Short enough.", False)
    assert _trim_to_chars("Exactly ten", 11) == ("Exactly ten", False)


def test_cuts_at_the_last_sentence_inside_the_budget():
    text = "I led the payments launch. It shipped in nine weeks and cleared review."
    out, trimmed = _trim_to_chars(text, 40)
    assert trimmed is True
    assert out == "I led the payments launch."
    assert len(out) <= 40


def test_falls_back_to_a_word_boundary_when_no_sentence_ends_in_range():
    text = "aligning several engineering teams around one shared roadmap and a single metric"
    out, trimmed = _trim_to_chars(text, 30)
    assert trimmed is True
    assert len(out) <= 30
    assert not out.endswith(" ")
    assert text.startswith(out)          # never invents or reorders text
    assert text[len(out)] == " "         # the cut landed on a word boundary


def test_trailing_punctuation_is_cleaned_off_a_word_cut():
    out, trimmed = _trim_to_chars("one, two, three, four, five", 12)
    assert trimmed is True
    assert out == "one, two"


def test_hard_cut_when_there_is_no_boundary_at_all():
    out, trimmed = _trim_to_chars("x" * 300, 120)
    assert trimmed is True and len(out) == 120


@pytest.mark.parametrize("budget", [120, 250, 600, 1200])
def test_never_exceeds_the_budget(budget):
    text = ("I aligned four engineering teams on one roadmap, cut the review cycle "
            "from three weeks to four days, and shipped the platform launch. ") * 20
    out, trimmed = _trim_to_chars(text, budget)
    assert trimmed is True
    assert len(out) <= budget


def test_zero_or_negative_budget_is_a_no_op():
    assert _trim_to_chars("anything", 0) == ("anything", False)
    assert _trim_to_chars("anything", -5) == ("anything", False)
    assert _trim_to_chars("", 100) == ("", False)
