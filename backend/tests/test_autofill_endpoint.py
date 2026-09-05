import pytest
from backend.models.db import Setting, Persona
from backend.seed import DEFAULT_SETTINGS


def _seed(test_db):
    test_db.add(Setting(key="dashboard_api_key", value=""))
    test_db.add(Setting(key="autofill_prompt", value=DEFAULT_SETTINGS["autofill_prompt"][0]))
    test_db.add(Setting(key="autofill_default_length", value=DEFAULT_SETTINGS["autofill_default_length"][0]))
    test_db.add(Persona(id=1, contact={"name": "V"}, preferences={"tone": "plain"},
                        resume_content={"summary": "fintech PM"}, work_auth={},
                        qa_bank=[{"question": "Why fintech?", "answer": "Because payments."}]))
    test_db.commit()


@pytest.fixture(autouse=True)
def _mock_llm(monkeypatch):
    async def fake(prompt, system, max_tokens=400, cached_prefix=None):
        # prompt is the per-question suffix (company/position/question); persona/qa_bank live only in cached_prefix.
        assert "Rogo" in prompt  # company present in suffix
        assert "Why fintech?" in (cached_prefix or "")  # qa_bank present in cached prefix
        assert "Why fintech?" not in prompt  # proves no duplication into the suffix
        return {"text": "Because Rogo is finance and AI.", "usage": {}}
    monkeypatch.setattr("backend.api.routes_autofill.call_autofill_llm", fake, raising=True)


def test_autofill_returns_answer(api_client, test_db):
    _seed(test_db)
    r = api_client.post("/api/autofill/answer",
                        json={"question": "Why are you interested in Rogo?",
                              "company": "Rogo", "position": "PM", "max_chars": 250})
    assert r.status_code == 200
    assert r.json()["answer"] == "Because Rogo is finance and AI."


def test_autofill_requires_question(api_client, test_db):
    _seed(test_db)
    r = api_client.post("/api/autofill/answer", json={"company": "Rogo"})
    assert r.status_code == 400


# These two need the app (api_client → backend.main → apscheduler); pure-function coverage is in test_autofill_extract.py.

def test_truncated_envelope_is_salvaged_end_to_end(api_client, test_db, monkeypatch):
    _seed(test_db)

    async def fake(prompt, system, max_tokens=400, cached_prefix=None):
        # the model hit its token budget mid-sentence: no closing quote, no brace
        return {"text": '{"answer": "Because Rogo is finance and AI', "usage": {}}
    monkeypatch.setattr("backend.api.routes_autofill.call_autofill_llm", fake, raising=True)

    r = api_client.post("/api/autofill/answer",
                        json={"question": "Why are you interested in Rogo?",
                              "company": "Rogo", "position": "PM", "max_chars": 250})
    assert r.status_code == 200
    answer = r.json()["answer"]
    assert not answer.startswith("{")
    assert answer == "Because Rogo is finance and AI"


def test_unusable_envelope_is_a_502_not_an_answer(api_client, test_db, monkeypatch):
    _seed(test_db)

    async def fake(prompt, system, max_tokens=400, cached_prefix=None):
        return {"text": '{"reasoning": "thought about it", "confidence": 0.4}', "usage": {}}
    monkeypatch.setattr("backend.api.routes_autofill.call_autofill_llm", fake, raising=True)

    r = api_client.post("/api/autofill/answer",
                        json={"question": "Why are you interested in Rogo?",
                              "company": "Rogo", "position": "PM", "max_chars": 250})
    assert r.status_code == 502
