"""POST /api/persona/qa-bank — flywheel save."""
from backend.models.db import Setting, Persona


def _seed(test_db):
    test_db.add(Setting(key="dashboard_api_key", value=""))
    test_db.add(Persona(id=1, qa_bank=[{"question": "Why fintech?", "answer": "Payments."}]))
    test_db.commit()


def test_append_qa(api_client, test_db):
    _seed(test_db)
    r = api_client.post("/api/persona/qa-bank",
                        json={"question": "Why Rogo?", "answer": "Finance + AI."})
    assert r.status_code == 200
    assert r.json()["count"] == 2
    from backend.models.db import Persona as P
    p = test_db.query(P).filter(P.id == 1).first()
    test_db.refresh(p)
    assert p.qa_bank[-1] == {"question": "Why Rogo?", "answer": "Finance + AI."}


def test_append_requires_both(api_client, test_db):
    _seed(test_db)
    assert api_client.post("/api/persona/qa-bank", json={"question": "x"}).status_code == 400
