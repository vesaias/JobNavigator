"""Two job-less résumés with the same contact stub must not fight over a token.

(Ids here carry hex letters on purpose: an all-digit UUID hexes to an all-digit
string, which SQLite's numeric affinity reads back as a float.)

With tracer_links_url_style = param_jobid, a résumé that has no linked job falls
back to reserving "0{stub}" — but that is not unique: every job-less owner with a
stub of "l" wants "0l". Rendering the second one reassigned its existing row to
the token the first already held and committed without a guard, so the PDF
endpoint raised IntegrityError and returned 500.

The deterministic token is a preference now: taken only when free, otherwise the
owner keeps (or is given) a token of its own.
"""
import pytest
from sqlalchemy import func

from backend.api.routes_resumes import _rewrite_urls_with_tracers
from backend.models.db import Setting, TracerLink


def _settings(db, style="param_jobid"):
    for k, v in [("tracer_links_enabled", "true"),
                 ("tracer_links_base_url", "https://example.com"),
                 ("tracer_links_url_style", style)]:
        db.add(Setting(key=k, value=v))
    db.commit()


def _header(name):
    return {"header": {"name": name, "contact_items": [
        {"text": "LinkedIn", "url": "linkedin.com/in/x", "stub": "l"},
        {"text": "site", "url": "site.dev", "stub": "d"},
    ]}}


def _tokens(db):
    return sorted(t for (t,) in db.query(TracerLink.token).all())


def test_two_jobless_resumes_with_the_same_stubs(test_db):
    _settings(test_db)
    a = _rewrite_urls_with_tracers(_header("A"), "a1111111-11a1-41a1-8111-1111111111ab", test_db)
    b = _rewrite_urls_with_tracers(_header("B"), "b2222222-22b2-42b2-8222-2222222222cd", test_db)

    # the first owner gets the reserved tokens
    assert {"0l", "0d"} <= set(_tokens(test_db))
    # the second is rewritten too, just not onto the same tokens
    urls_a = [i["url"] for i in a["header"]["contact_items"]]
    urls_b = [i["url"] for i in b["header"]["contact_items"]]
    assert all(u.startswith("https://example.com?cv=") for u in urls_a + urls_b)
    assert not set(urls_a) & set(urls_b), "two résumés must not share a tracer URL"

    dupes = test_db.query(TracerLink.token).group_by(TracerLink.token).having(func.count() > 1).all()
    assert dupes == []


def test_rerender_is_stable(test_db):
    """Rendering the same résumé twice must not churn its tokens."""
    _settings(test_db)
    rid = "c3333333-33c3-43c3-8333-3333333333ef"
    first = _rewrite_urls_with_tracers(_header("A"), rid, test_db)
    before = _tokens(test_db)
    second = _rewrite_urls_with_tracers(_header("A"), rid, test_db)
    assert _tokens(test_db) == before
    assert [i["url"] for i in first["header"]["contact_items"]] == \
           [i["url"] for i in second["header"]["contact_items"]]


def test_second_owner_still_gets_working_links(test_db):
    """The loser of the 0{stub} race must still end up with usable tokens."""
    _settings(test_db)
    _rewrite_urls_with_tracers(_header("A"), "d4444444-44d4-44d4-8444-4444444444ab", test_db)
    out = _rewrite_urls_with_tracers(_header("B"), "e5555555-55e5-45e5-8555-5555555555cd", test_db)
    for item in out["header"]["contact_items"]:
        token = item["url"].split("cv=")[1]
        link = test_db.query(TracerLink).filter(TracerLink.token == token).first()
        assert link is not None, f"{token} resolves to nothing"
        assert str(link.resume_id) == "e5555555-55e5-45e5-8555-5555555555cd"


@pytest.mark.parametrize("style", ["path", "param", "path_jobid", "param_jobid"])
def test_disabled_and_styles_never_raise(test_db, style):
    _settings(test_db, style)
    for rid in ("f6666666-66f6-46f6-8666-6666666666ef", "a7777777-77a7-47a7-8777-7777777777ba"):
        out = _rewrite_urls_with_tracers(_header("X"), rid, test_db)
        assert len(out["header"]["contact_items"]) == 2
