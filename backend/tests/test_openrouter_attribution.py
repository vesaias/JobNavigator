"""OpenRouter calls carry the app-attribution headers; plain OpenAI calls do not."""
from backend.analyzer import llm_client as L


def test_openrouter_client_sends_attribution_headers():
    c = L._openai_client("k", L.OPENROUTER_BASE_URL)
    assert c.default_headers["HTTP-Referer"] == "https://github.com/vesaias/JobNavigator"
    assert c.default_headers["X-Title"] == "JobNavigator"
    assert str(c.base_url).rstrip("/") == L.OPENROUTER_BASE_URL


def test_openai_client_has_no_attribution_headers():
    c = L._openai_client("k", None)
    assert "HTTP-Referer" not in c.default_headers
    assert "X-Title" not in c.default_headers
