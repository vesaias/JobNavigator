"""_flatten_resume must include all sections (header, summary, experience, skills,
education, projects, publications) with section headers for readability by the LLM."""
from backend.analyzer.cv_scorer import _flatten_resume


def test_flatten_includes_section_headers():
    out = _flatten_resume({
        "summary": "Senior PM",
        "experience": [{"title": "PM", "company": "Acme", "dates": "2020-2024",
                        "bullets": ["Shipped X"]}],
    })
    assert "## Summary" in out
    assert "## Experience" in out
    assert "Senior PM" in out
    assert "Shipped X" in out


def test_flatten_includes_header_when_present():
    out = _flatten_resume({
        "header": {"name": "Jane Doe", "email": "jane@example.com",
                   "phone": "+1-555-0100", "linkedin": "linkedin.com/in/jane"},
        "summary": "S",
    })
    assert "Jane Doe" in out
    assert "jane@example.com" in out
    assert out.index("Jane Doe") < out.index("S")


def test_flatten_includes_projects_section():
    out = _flatten_resume({
        "summary": "S",
        "projects": [
            {"name": "Tracker", "description": "Open-source job tracker", "url": "https://github.com/x"},
        ],
    })
    assert "## Projects" in out
    assert "Tracker" in out
    assert "Open-source job tracker" in out


def test_flatten_includes_publications_section():
    out = _flatten_resume({
        "summary": "S",
        "publications": [
            {"title": "AI in PM", "venue": "Medium", "year": "2024"},
        ],
    })
    assert "## Publications" in out
    assert "AI in PM" in out
    assert "Medium" in out


def test_flatten_omits_empty_sections():
    out = _flatten_resume({"summary": "Just a summary"})
    assert "## Summary" in out
    assert "## Experience" not in out
    assert "## Projects" not in out
    assert "## Publications" not in out
    assert "## Education" not in out


def test_flatten_empty_input_returns_empty_string():
    assert _flatten_resume({}) == ""
    assert _flatten_resume(None) == ""


def test_flatten_full_resume_contains_all_six_sections():
    out = _flatten_resume({
        "header": {"name": "Jane"},
        "summary": "Summary text",
        "experience": [{"title": "PM", "company": "X", "dates": "2020-2024", "bullets": ["b1"]}],
        "skills": {"languages": ["Python", "JS"]},
        "education": [{"degree": "BS", "school": "MIT", "year": "2018"}],
        "projects": [{"name": "P1", "description": "d1"}],
        "publications": [{"title": "T1", "venue": "V1"}],
    })
    for header in ["## Summary", "## Experience", "## Skills", "## Education", "## Projects", "## Publications"]:
        assert header in out, f"Missing section header: {header}"


def test_score_prompt_uses_resume_version_label():
    """The cached prefix sent to the LLM should say 'Resume Version' not 'CV VERSION'."""
    from backend.analyzer import cv_scorer
    import inspect
    src = inspect.getsource(cv_scorer)
    assert "CV VERSION" not in src, "Prompt still uses 'CV VERSION' — should be 'Resume Version'"
    assert "Resume Version" in src or "RESUME VERSION" in src
