"""Tests gmail_client email→application matching: matching is anchored on the sender (From header/domain/subject), never on job title alone, so a shared title never matches the wrong company."""
from unittest.mock import MagicMock


def _app(company, title, status="applied"):
    app = MagicMock()
    app.status = status
    job = MagicMock()
    job.company = company
    job.title = title
    app.job = job
    return app


def _db_with(apps):
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = apps
    return db


# --- _email_matches_company (pure helper) ---

def test_helper_matches_company_in_sender_domain():
    from backend.email_monitor.gmail_client import _email_matches_company
    assert _email_matches_company(
        "Amazon", "Amazon.jobs <no-reply@amazon.com>", "Your application", "", "amazon.com"
    ) is True


def test_helper_rejects_other_company_sharing_a_title():
    """The bug: an Amazon email must NOT be considered a match for a Kpler application."""
    from backend.email_monitor.gmail_client import _email_matches_company
    assert _email_matches_company(
        "Kpler",
        "Amazon.jobs <no-reply@amazon.com>",
        "Thanks for applying to the Product Manager role",
        "Thank you for applying to the Product Manager position at Amazon.",
        "amazon.com",
    ) is False


def test_helper_matches_company_in_display_name_over_ats_domain():
    """ATS email from greenhouse-mail.io but 'Kpler' is in the From display name."""
    from backend.email_monitor.gmail_client import _email_matches_company
    assert _email_matches_company(
        "Kpler", "Kpler Talent <no-reply@greenhouse-mail.io>", "Update on your application",
        "", "greenhouse-mail.io"
    ) is True


def test_helper_body_fallback_full_name():
    """No company signal in sender, but the full company name is in the body → match."""
    from backend.email_monitor.gmail_client import _email_matches_company
    assert _email_matches_company(
        "Kpler", "no-reply@greenhouse-mail.io", "Application update",
        "We have received your application to Kpler.", "greenhouse-mail.io"
    ) is True


def test_helper_no_signal_anywhere_returns_false():
    from backend.email_monitor.gmail_client import _email_matches_company
    assert _email_matches_company(
        "Kpler", "no-reply@greenhouse-mail.io", "Application update",
        "Your application status has changed.", "greenhouse-mail.io"
    ) is False


def test_helper_short_token_no_substring_false_positive():
    """A short company token must not match inside an unrelated word (e.g. 'Box' vs 'inbox')."""
    from backend.email_monitor.gmail_client import _email_matches_company
    assert _email_matches_company(
        "Box", "Amazon <no-reply@amazon.com>", "Check your inbox for next steps", "", "amazon.com"
    ) is False


# --- _match_email_to_application (keyword-path matcher) ---

def test_amazon_email_does_not_match_kpler_or_docusign_by_shared_title():
    """End to end through the matcher: an Amazon acknowledgment must not match Kpler/DocuSign applications sharing the title 'Product Manager'."""
    from backend.email_monitor.gmail_client import _match_email_to_application
    apps = [_app("Kpler", "Product Manager"), _app("DocuSign", "Product Manager")]
    matched = _match_email_to_application(
        _db_with(apps),
        from_header="Amazon.jobs <no-reply@amazon.com>",
        subject="Thanks for applying to the Product Manager role",
        body="Thank you for applying to the Product Manager position at Amazon.",
        sender_domain="amazon.com",
    )
    assert matched is None


def test_matcher_picks_the_correct_company():
    from backend.email_monitor.gmail_client import _match_email_to_application
    apps = [
        _app("Kpler", "Product Manager"),
        _app("Amazon", "Senior Product Manager - Tech, Prime Video Financial Systems"),
    ]
    matched = _match_email_to_application(
        _db_with(apps),
        from_header="Amazon.jobs <no-reply@amazon.com>",
        subject="Your Amazon application",
        body="Thank you for applying.",
        sender_domain="amazon.com",
    )
    assert matched is not None
    assert matched.job.company == "Amazon"


def test_matcher_returns_none_when_no_company_matches_sender():
    from backend.email_monitor.gmail_client import _match_email_to_application
    apps = [_app("Kpler", "Product Manager")]
    matched = _match_email_to_application(
        _db_with(apps),
        from_header="no-reply@greenhouse-mail.io",
        subject="Application update",
        body="Your application status has changed.",
        sender_domain="greenhouse-mail.io",
    )
    assert matched is None
