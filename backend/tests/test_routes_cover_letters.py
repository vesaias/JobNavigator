"""Tests for /api/cover-letters — CRUD, templates, generate validation."""
import uuid
import pytest

from backend.models.db import Setting, Resume, Job


def _seed_first_run(db):
    db.add(Setting(key="dashboard_api_key", value=""))
    db.add(Setting(key="cover_letter_prompt", value="Voice {voice_instruction} Len {length_instruction} JD {job_description}"))
    db.commit()


def _make_resume(db, name="PM"):
    r = Resume(id=uuid.uuid4(), name=name, is_base=True,
               json_data={"header": {"name": "Viktor"}, "summary": "PM."})
    db.add(r)
    db.commit()
    return r


def _make_job(db, description="We need a fintech PM with roadmapping skills."):
    j = Job(id=uuid.uuid4(), external_id=uuid.uuid4().hex, company="Acme",
            title="Senior PM", url="https://acme.com/jobs/1", status="saved",
            description=description)
    db.add(j)
    db.commit()
    return j


# ── CRUD ─────────────────────────────────────────────────────────────────────

def test_create_and_get(api_client, test_db):
    _seed_first_run(test_db)
    resp = api_client.post("/api/cover-letters", json={
        "name": "Acme letter",
        "json_data": {"greeting": "Dear Team,", "body_paragraphs": ["Hello."]},
    })
    assert resp.status_code == 201
    cid = resp.json()["id"]

    got = api_client.get(f"/api/cover-letters/{cid}")
    assert got.status_code == 200
    assert got.json()["name"] == "Acme letter"
    assert got.json()["json_data"]["greeting"] == "Dear Team,"


def test_create_requires_name(api_client, test_db):
    _seed_first_run(test_db)
    resp = api_client.post("/api/cover-letters", json={"json_data": {}})
    assert resp.status_code == 400


def test_list_and_filter_by_job(api_client, test_db):
    _seed_first_run(test_db)
    job = _make_job(test_db)
    api_client.post("/api/cover-letters", json={"name": "A", "job_id": str(job.id)})
    api_client.post("/api/cover-letters", json={"name": "B"})

    all_rows = api_client.get("/api/cover-letters").json()
    assert len(all_rows) == 2
    filtered = api_client.get(f"/api/cover-letters?job_id={job.id}").json()
    assert len(filtered) == 1
    assert filtered[0]["name"] == "A"


def test_patch_updates_fields(api_client, test_db):
    _seed_first_run(test_db)
    cid = api_client.post("/api/cover-letters", json={"name": "Old"}).json()["id"]
    resp = api_client.patch(f"/api/cover-letters/{cid}", json={
        "name": "New", "json_data": {"greeting": "Hi,"},
    })
    assert resp.status_code == 200
    assert resp.json()["name"] == "New"
    assert resp.json()["json_data"]["greeting"] == "Hi,"


def test_delete(api_client, test_db):
    _seed_first_run(test_db)
    cid = api_client.post("/api/cover-letters", json={"name": "Doomed"}).json()["id"]
    assert api_client.delete(f"/api/cover-letters/{cid}").status_code == 200
    assert api_client.get(f"/api/cover-letters/{cid}").status_code == 404


def test_get_missing_404(api_client, test_db):
    _seed_first_run(test_db)
    assert api_client.get(f"/api/cover-letters/{uuid.uuid4()}").status_code == 404


# ── Templates ────────────────────────────────────────────────────────────────

def test_templates_endpoint(api_client, test_db):
    _seed_first_run(test_db)
    resp = api_client.get("/api/cover-letters/templates")
    assert resp.status_code == 200
    ids = {t["id"] for t in resp.json()}
    assert {"garamond", "inter", "traditional"} <= ids


# ── Generate validation ──────────────────────────────────────────────────────

def test_generate_requires_resume_and_job(api_client, test_db):
    _seed_first_run(test_db)
    assert api_client.post("/api/cover-letters/generate", json={}).status_code == 400
    assert api_client.post("/api/cover-letters/generate", json={"resume_id": str(uuid.uuid4())}).status_code == 400


def test_generate_404_on_missing_resume(api_client, test_db):
    _seed_first_run(test_db)
    job = _make_job(test_db)
    resp = api_client.post("/api/cover-letters/generate",
                           json={"resume_id": str(uuid.uuid4()), "job_id": str(job.id)})
    assert resp.status_code == 404


def test_generate_400_on_job_without_description(api_client, test_db):
    _seed_first_run(test_db)
    resume = _make_resume(test_db)
    job = _make_job(test_db, description="")
    resp = api_client.post("/api/cover-letters/generate",
                           json={"resume_id": str(resume.id), "job_id": str(job.id)})
    assert resp.status_code == 400


def test_generate_happy_path_returns_202(api_client, test_db, monkeypatch):
    """Valid (resume, job) returns 202 + run_id. launch_background is stubbed so no
    real LLM call / asyncio task runs — generation itself is covered by the
    generator unit tests."""
    _seed_first_run(test_db)
    resume = _make_resume(test_db)
    job = _make_job(test_db)

    import backend.api.routes_cover_letters as rcl
    monkeypatch.setattr(rcl, "launch_background", lambda *a, **kw: "run-123")

    resp = api_client.post("/api/cover-letters/generate",
                           json={"resume_id": str(resume.id), "job_id": str(job.id),
                                 "voice": "warm", "length": "concise"})
    assert resp.status_code == 202
    assert resp.json()["run_id"] == "run-123"


def test_generate_409_on_duplicate(api_client, test_db, monkeypatch):
    _seed_first_run(test_db)
    resume = _make_resume(test_db)
    job = _make_job(test_db)

    import backend.api.routes_cover_letters as rcl
    from backend.job_monitor import JobAlreadyRunningError

    def _raise(*a, **kw):
        raise JobAlreadyRunningError("generate_cover_letter", 5.0)

    monkeypatch.setattr(rcl, "launch_background", _raise)
    resp = api_client.post("/api/cover-letters/generate",
                           json={"resume_id": str(resume.id), "job_id": str(job.id)})
    assert resp.status_code == 409


def test_generate_persona_base_validates_content(api_client, test_db, monkeypatch):
    """resume_id='persona' fails fast when Persona has no resume_content, succeeds when it does."""
    from backend.models.db import Persona
    _seed_first_run(test_db)
    job = _make_job(test_db)
    test_db.add(Persona(id=1, resume_content={}))
    test_db.commit()

    # empty persona → 400
    resp = api_client.post("/api/cover-letters/generate",
                           json={"resume_id": "persona", "job_id": str(job.id)})
    assert resp.status_code == 400

    # fill persona, stub launch_background → 202
    p = test_db.query(Persona).filter(Persona.id == 1).first()
    p.resume_content = {"header": {"name": "Viktor"}, "summary": "PM."}
    test_db.commit()
    import backend.api.routes_cover_letters as rcl
    monkeypatch.setattr(rcl, "launch_background", lambda *a, **kw: "run-1")
    resp = api_client.post("/api/cover-letters/generate",
                           json={"resume_id": "persona", "job_id": str(job.id)})
    assert resp.status_code == 202


# ── Tracer cross-owner isolation (guards the repoint bug) ────────────────────

def test_tracer_repoint_clears_other_owner(test_db):
    """A resume and a cover letter for the same job derive the same {short_id}{stub}
    token. After rewriting both, the shared link must be owned by exactly one —
    never both — so click attribution stays correct."""
    import uuid
    from backend.models.db import Setting, Resume, Job, CoverLetter, TracerLink
    from backend.api.routes_resumes import _rewrite_urls_with_tracers

    test_db.add(Setting(key="tracer_links_enabled", value="true"))
    test_db.add(Setting(key="tracer_links_base_url", value="https://t.example.com"))
    test_db.add(Setting(key="tracer_links_url_style", value="path_jobid"))
    job = Job(id=uuid.uuid4(), external_id=uuid.uuid4().hex, company="Acme", title="PM",
              url="https://acme.com/1", status="saved", short_id=7777)
    test_db.add(job)
    resume = Resume(id=uuid.uuid4(), name="PM", is_base=False, job_id=job.id,
                    json_data={"header": {"name": "V", "contact_items": [{"text": "LinkedIn", "url": "linkedin.com/in/v", "stub": "l"}]}})
    cl = CoverLetter(id=uuid.uuid4(), name="PM CL", job_id=job.id,
                     json_data={"header": {"name": "V", "contact_items": [{"text": "LinkedIn", "url": "linkedin.com/in/v", "stub": "l"}]}})
    test_db.add(resume)
    test_db.add(cl)
    test_db.commit()

    # Rewrite resume → creates link owned by resume, token "7777l"
    _rewrite_urls_with_tracers(resume.json_data, str(resume.id), test_db)
    # Rewrite CL → same token; must repoint to CL and clear resume_id
    _rewrite_urls_with_tracers(cl.json_data, None, test_db, cover_letter_id=str(cl.id), job_id=cl.job_id)

    link = test_db.query(TracerLink).filter(TracerLink.token == "7777l").first()
    assert link is not None
    # Exactly one owner set
    assert (link.resume_id is None) != (link.cover_letter_id is None)
    assert str(link.cover_letter_id) == str(cl.id)
    assert link.resume_id is None
