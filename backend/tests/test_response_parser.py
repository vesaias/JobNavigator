"""Tests for email_monitor/response_parser.classify_email — category precedence + confidence."""


def test_classify_positive_signal():
    from backend.email_monitor.response_parser import classify_email
    result = classify_email(
        subject="Interview invitation for Senior PM",
        body="We'd like to invite you to a phone interview next week.",
    )
    assert result["classification"] == "positive"
    assert result["confidence"] > 0.5


def test_classify_rejection_signal():
    from backend.email_monitor.response_parser import classify_email
    result = classify_email(
        subject="Regarding your application",
        body="Unfortunately, we will not be moving forward with your candidacy at this time.",
    )
    assert result["classification"] == "rejection"
    assert result["confidence"] > 0.5


def test_classify_auto_reply():
    from backend.email_monitor.response_parser import classify_email
    result = classify_email(
        subject="Application received",
        body="Thank you for applying. We have received your application.",
    )
    assert result["classification"] == "auto_reply"
    assert result["confidence"] > 0.5


def test_classify_rejection_trumps_auto_reply():
    """Subject says 'application received' (auto-reply), body says 'not moving forward' (rejection).

    Rejection wins — more specific signal. This guards against the common case where
    a rejection email contains boilerplate like 'thank you for your interest'.
    """
    from backend.email_monitor.response_parser import classify_email
    result = classify_email(
        subject="Application received",
        body="Unfortunately, we are not moving forward with your candidacy.",
    )
    assert result["classification"] == "rejection"


def test_classify_positive_and_rejection_is_ambiguous():
    """Both positive and rejection signals present → ambiguous with low confidence."""
    from backend.email_monitor.response_parser import classify_email
    result = classify_email(
        subject="Next steps",
        body="We would like to invite you. Unfortunately, the position has been filled.",
    )
    assert result["classification"] == "ambiguous"
    assert result["confidence"] < 0.5


def test_classify_ambiguous_no_signal():
    from backend.email_monitor.response_parser import classify_email
    result = classify_email(
        subject="Question",
        body="Hey do you have a minute to chat?",
    )
    assert result["classification"] == "ambiguous"
    assert result["confidence"] < 0.5


def test_classify_empty_email():
    from backend.email_monitor.response_parser import classify_email
    result = classify_email(subject="", body="")
    assert result["classification"] == "ambiguous"
    assert result["confidence"] < 0.5


def test_classify_confidence_scales_with_signal_count():
    """More positive phrases → higher confidence, capped at 0.95."""
    from backend.email_monitor.response_parser import classify_email
    one_signal = classify_email(
        subject="Hello",
        body="We would like to invite you.",
    )
    many_signals = classify_email(
        subject="Next steps",
        body=(
            "We would like to invite you to schedule an interview. "
            "Please share your availability for a call. We are excited to meet with you."
        ),
    )
    assert one_signal["classification"] == "positive"
    assert many_signals["classification"] == "positive"
    assert many_signals["confidence"] >= one_signal["confidence"]
    assert many_signals["confidence"] <= 0.95
