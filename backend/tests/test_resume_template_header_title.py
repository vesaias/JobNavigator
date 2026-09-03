"""R3-B-01: `header.title` prints in every résumé template, and only when set.

The field round-tripped through the API and printed in three templates but had no
editor in v2 — invisible and uneditable. Now that the header editor exposes it,
the other templates need the slot too, and an empty value must render nothing so
no layout shifts for the résumés that don't use it.
"""
import re
from pathlib import Path

import pytest

jinja2 = pytest.importorskip("jinja2")

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "resume_templates"
TITLE = "Senior Product Manager"


def _template_names():
    return sorted(p.name for p in TEMPLATES_DIR.iterdir()
                  if (p / "template.html.j2").exists())


def _render(name, header):
    from jinja2 import Environment, FileSystemLoader
    from markupsafe import Markup
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR / name)))
    # the real renderer's only custom filter (routes_resumes._render_html)
    env.filters["bold"] = lambda text: Markup(re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text or ""))
    return env.get_template("template.html.j2").render(
        header=header, summary="A summary.", experience=[], skills={},
        education=[], projects=[], publications=[],
        page_format="letter", fonts_base="", fonts={},
    )


@pytest.mark.parametrize("name", _template_names())
def test_template_prints_the_header_title(name):
    html = _render(name, {"name": "Dana Okonkwo", "title": TITLE, "contact_items": []})
    assert TITLE in html, f"{name} does not render header.title"


@pytest.mark.parametrize("name", _template_names())
def test_template_prints_nothing_when_the_title_is_empty(name):
    """Optional means absent — not an empty element that still takes space."""
    with_title = _render(name, {"name": "Dana Okonkwo", "title": TITLE, "contact_items": []})
    without = _render(name, {"name": "Dana Okonkwo", "contact_items": []})
    blank = _render(name, {"name": "Dana Okonkwo", "title": "", "contact_items": []})

    assert TITLE not in without
    assert without == blank                      # "" behaves exactly like absent
    assert len(without) < len(with_title)        # the slot really is conditional
    assert "title-line" not in without or "title-line" in without.split("<body")[0]
