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
    """Subject reads auto-reply ('application received'), body reads rejection ('not moving forward') — rejection wins as the more specific signal."""
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


def test_acknowledgment_with_positive_boilerplate_is_auto_reply():
    """A 'thanks for applying' acknowledgment with weak-positive boilerplate ('excited to', 'next steps') and no strong scheduling signal is auto_reply, not positive."""
    from backend.email_monitor.response_parser import classify_email
    result = classify_email(
        subject="Thanks for applying to Amazon",
        body=(
            "Thanks for applying! We're excited to review your background and will "
            "connect with you about next steps if there is a match."
        ),
    )
    assert result["classification"] == "auto_reply"


def test_genuine_advance_stays_positive_despite_applying_phrase():
    """A real interview invite that opens with 'thank you for applying' still classifies as positive — the strong signal wins over the acknowledgment phrase."""
    from backend.email_monitor.response_parser import classify_email
    result = classify_email(
        subject="Interview scheduling — PM role",
        body=(
            "Thank you for applying. We'd like to schedule a call to discuss the role. "
            "Please share your availability for next week."
        ),
    )
    assert result["classification"] == "positive"


def test_thanks_for_applying_variants_are_auto_reply():
    """Both 'thanks for applying' and 'thanks for your application' are acknowledgments."""
    from backend.email_monitor.response_parser import classify_email
    for body in (
        "Thanks for applying to the Product Manager role.",
        "Thanks for your application. Our team will review it shortly.",
    ):
        result = classify_email(subject="Application", body=body)
        assert result["classification"] == "auto_reply", body
