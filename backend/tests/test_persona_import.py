"""POST /api/persona/import: replaces `contact` and `resume_content`; leaves the five autofill nodes untouched."""
import uuid

import pytest

from backend.models.db import ActivityLog, Persona, Resume, Setting


def _seed(test_db):
    test_db.add(Setting(key="dashboard_api_key", value=""))
    test_db.commit()
    from backend.seed import seed_persona
    seed_persona(test_db)


RESUME_JSON = {
    "header": {
        "name": "Viktor Esadze",
        "title": "Senior Project Manager",
        "contact_items": [
            {"text": "Boston, MA"},
            {"text": "viktor@example.com", "url": "mailto:viktor@example.com"},
            {"text": "+1 (617) 555-0142"},
            {"text": "LinkedIn", "url": "https://linkedin.com/in/vesadze"},
            {"text": "GitHub", "url": "https://github.com/vesadze"},
            {"text": "Portfolio", "url": "https://vesadze.dev"},
        ],
    },
    "summary": "PM with 9 years shipping platform work.",
    "experience": [
        {"company": "Acme Inc.", "title": "Senior PM", "date": "2020–2024",
         "location": "Boston, MA", "bullets": ["Shipped X", "Cut Y by 30%"]},
        {"company": "Globex", "title": "PM", "date": "2017–2020",
         "location": "Remote", "bullets": ["Ran Z"]},
    ],
    "skills": {"Product": ["Roadmapping", "Discovery"], "Tools": ["Jira"]},
    "education": [{"school": "BU", "degree": "BSc", "location": "Boston, MA"}],
    "projects": [{"name": "Sideproject"}],
    "publications": [],
}


def _make_base(test_db, name="Platform PM", json_data=None, is_base=True, parent_id=None):
    r = Resume(name=name, is_base=is_base, parent_id=parent_id,
               template="garamond", page_format="letter",
               json_data=json_data if json_data is not None else RESUME_JSON)
    test_db.add(r)
    test_db.commit()
    test_db.refresh(r)
    return r


# ── from a base résumé ──────────────────────────────────────────────────────

def test_import_from_base_resume_maps_contact_and_content(api_client, test_db):
    _seed(test_db)
    base = _make_base(test_db)

    resp = api_client.post("/api/persona/import", json={"resume_id": str(base.id)})
    assert resp.status_code == 200, resp.text
    data = resp.json()

    contact = data["persona"]["contact"]
    assert contact["first_name"] == "Viktor"
    assert contact["last_name"] == "Esadze"
    assert contact["email"] == "viktor@example.com"
    assert contact["phone"] == "+1 (617) 555-0142"
    assert contact["city"] == "Boston"
    assert contact["state"] == "MA"
    assert contact["linkedin"] == "https://linkedin.com/in/vesadze"
    assert contact["github"] == "https://github.com/vesadze"
    assert contact["portfolio"] == "https://vesadze.dev"

    content = data["persona"]["resume_content"]
    assert content["summary"] == RESUME_JSON["summary"]
    assert content["experience"] == RESUME_JSON["experience"]
    assert content["skills"] == RESUME_JSON["skills"]
    assert content["education"] == RESUME_JSON["education"]
    assert content["projects"] == RESUME_JSON["projects"]
    assert content["publications"] == []
    # header never lands in resume_content — it becomes `contact`
    assert "header" not in content

    assert data["summary"] == {
        "roles": 2, "bullets": 3, "skill_groups": 2, "education": 1,
        "projects": 1, "contact_items": len(contact),
        "source": "resume:Platform PM",
    }


def test_import_overwrites_and_leaves_other_nodes_alone(api_client, test_db):
    """contact + resume_content are replaced wholesale; the five autofill nodes keep every value they had."""
    _seed(test_db)
    p = test_db.query(Persona).filter(Persona.id == 1).first()
    p.contact = {"first_name": "Old", "email": "old@example.com", "current_company": "Nowhere"}
    p.resume_content = {"summary": "old summary", "experience": [{"company": "Old Co", "bullets": []}]}
    p.work_auth = {"authorized_us": True}
    p.demographics = {"gender": "male"}
    p.compensation = {"desired_salary": "180000"}
    p.preferences = {"willing_remote": True, "preferred_locations": ["Boston"]}
    p.qa_bank = [{"question": "Why us?", "answer": "Because."}]
    test_db.commit()

    base = _make_base(test_db)
    resp = api_client.post("/api/persona/import", json={"resume_id": str(base.id)})
    assert resp.status_code == 200, resp.text
    got = resp.json()["persona"]

    # replaced, not merged
    assert got["contact"]["first_name"] == "Viktor"
    assert "current_company" not in got["contact"]
    assert got["resume_content"]["summary"] == RESUME_JSON["summary"]
    assert got["resume_content"]["experience"] == RESUME_JSON["experience"]

    # untouched
    assert got["work_auth"] == {"authorized_us": True}
    assert got["demographics"] == {"gender": "male"}
    assert got["compensation"] == {"desired_salary": "180000"}
    assert got["preferences"] == {"willing_remote": True, "preferred_locations": ["Boston"]}
    assert got["qa_bank"] == [{"question": "Why us?", "answer": "Because."}]


def test_import_persists_and_logs_activity(api_client, test_db):
    _seed(test_db)
    base = _make_base(test_db)

    api_client.post("/api/persona/import", json={"resume_id": str(base.id)})

    test_db.expire_all()
    p = test_db.query(Persona).filter(Persona.id == 1).first()
    assert p.contact["email"] == "viktor@example.com"
    assert len(p.resume_content["experience"]) == 2

    # a second GET sees the same thing (flag_modified actually wrote)
    again = api_client.get("/api/persona").json()
    assert again["resume_content"]["skills"] == RESUME_JSON["skills"]

    rows = test_db.query(ActivityLog).filter(ActivityLog.type == "persona").all()
    assert len(rows) == 1
    assert rows[0].message == "Persona imported from resume:Platform PM"


def test_import_does_not_alias_the_resume_row(api_client, test_db):
    """The persona gets its own deep copy — editing it must not touch the résumé."""
    _seed(test_db)
    base = _make_base(test_db)
    api_client.post("/api/persona/import", json={"resume_id": str(base.id)})

    p = test_db.query(Persona).filter(Persona.id == 1).first()
    p.resume_content["experience"][0]["bullets"].append("added later")
    test_db.commit()
    test_db.expire_all()

    r = test_db.query(Resume).filter(Resume.id == base.id).first()
    assert r.json_data["experience"][0]["bullets"] == ["Shipped X", "Cut Y by 30%"]


def test_import_tailored_copy_rejected(api_client, test_db):
    _seed(test_db)
    base = _make_base(test_db)
    copy = _make_base(test_db, name="Platform PM → Acme", is_base=False, parent_id=base.id)

    resp = api_client.post("/api/persona/import", json={"resume_id": str(copy.id)})
    assert resp.status_code == 400
    assert "tailored copy" in resp.json()["detail"]

    # nothing was written
    p = test_db.query(Persona).filter(Persona.id == 1).first()
    assert (p.contact or {}) == {}


def test_import_unknown_resume_404(api_client, test_db):
    _seed(test_db)
    resp = api_client.post("/api/persona/import", json={"resume_id": str(uuid.uuid4())})
    assert resp.status_code == 404


def test_import_without_resume_id_or_file_400(api_client, test_db):
    _seed(test_db)
    resp = api_client.post("/api/persona/import", json={})
    assert resp.status_code == 400


# ── from a PDF ──────────────────────────────────────────────────────────────

def test_import_pdf_uses_the_resume_parser(api_client, test_db, monkeypatch):
    """The PDF path calls routes_resumes.parse_resume_pdf, the same parser /api/resumes/import-pdf uses, and creates no Resume row."""
    _seed(test_db)

    seen = {}

    async def fake_parse(pdf_bytes, db):
        seen["bytes"] = pdf_bytes
        return RESUME_JSON

    import backend.api.routes_resumes as rr
    monkeypatch.setattr(rr, "parse_resume_pdf", fake_parse)

    resp = api_client.post(
        "/api/persona/import",
        files={"file": ("Viktor_PM_Resume.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert seen["bytes"] == b"%PDF-1.4 fake"
    assert body["summary"]["source"] == "pdf:Viktor_PM_Resume.pdf"
    assert body["summary"]["roles"] == 2
    assert body["persona"]["contact"]["email"] == "viktor@example.com"
    # import never persists a Resume
    assert test_db.query(Resume).count() == 0


def test_import_pdf_rejects_non_pdf(api_client, test_db):
    _seed(test_db)
    resp = api_client.post(
        "/api/persona/import",
        files={"file": ("resume.docx", b"not a pdf", "application/msword")},
    )
    assert resp.status_code == 400
    assert "PDF" in resp.json()["detail"]


def test_import_pdf_rejects_oversized(api_client, test_db):
    _seed(test_db)
    big = b"x" * (10 * 1024 * 1024 + 1)
    resp = api_client.post(
        "/api/persona/import",
        files={"file": ("huge.pdf", big, "application/pdf")},
    )
    assert resp.status_code == 400
    assert "too large" in resp.json()["detail"]


def test_import_pdf_unparseable_is_422(api_client, test_db):
    """No monkeypatch: pdfplumber can't read these bytes → the parser's own 422."""
    _seed(test_db)
    resp = api_client.post(
        "/api/persona/import",
        files={"file": ("broken.pdf", b"not really a pdf at all", "application/pdf")},
    )
    assert resp.status_code == 422


# ── the contact heuristics ──────────────────────────────────────────────────

@pytest.mark.parametrize("text,expect", [
    ("Boston, MA", {"city": "Boston", "state": "MA"}),
    ("Berlin, Germany", {"city": "Berlin", "country": "Germany"}),
    ("Austin, TX, USA", {"city": "Austin", "state": "TX", "country": "USA"}),
    ("Boston, Massachusetts", {"city": "Boston", "state": "Massachusetts"}),
    ("Remote", {"city": "Remote"}),
])
def test_location_split(text, expect):
    from backend.api.routes_persona import _split_location
    assert _split_location(text) == expect


def test_contact_heuristics_without_labels():
    """Bare values with no url and no label word still classify."""
    from backend.api.routes_persona import _contact_from_header
    out = _contact_from_header({
        "name": "Mary Jane Watson",
        "contact_items": [
            {"text": "617-555-0142"},
            {"text": "mary@example.com"},
            {"text": "linkedin.com/in/mjw"},
            {"text": "github.com/mjw"},
            {"text": "New York, NY"},
        ],
    })
    assert out["first_name"] == "Mary"
    assert out["last_name"] == "Jane Watson"
    assert out["phone"] == "617-555-0142"
    assert out["email"] == "mary@example.com"
    assert out["linkedin"] == "linkedin.com/in/mjw"
    assert out["github"] == "github.com/mjw"
    assert out == {**out, "city": "New York", "state": "NY"}


def test_contact_heuristics_ignore_junk():
    from backend.api.routes_persona import _contact_from_header
    out = _contact_from_header({"name": "", "contact_items": ["not-a-dict", {}, None]})
    assert out == {}
