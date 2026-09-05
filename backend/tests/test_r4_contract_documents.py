"""R4-T1 · /api/resumes, /api/cover-letters and /api/persona contract.

These three carry the largest free-form JSON blobs in the app (`json_data`,
persona nodes), so wrong-typed and oversized payloads matter most here.
"""
import pytest

from backend.tests.r4_support import (  # noqa: F401
    client, _clear_running_state, _no_outbound, assert_clean, assert_no_leak,
    make_job, make_resume, make_persona, set_setting, big_string, EMOJI, MISSING_UUID,
)

PERSONA_NODES = ["contact", "work_auth", "demographics", "compensation",
                 "preferences", "resume_content", "qa_bank"]


# ══ Resumes ══════════════════════════════════════════════════════════════════

def test_create_resume_requires_a_name(client):
    assert_clean(client.post("/api/resumes", json={}), 400)


@pytest.mark.parametrize("name", ["", "   ", "\t\n"])
def test_create_resume_rejects_a_blank_name(client, name):
    assert_clean(client.post("/api/resumes", json={"name": name}), 400)


@pytest.mark.parametrize("name", [5, None, [], {}])
@pytest.mark.xfail(strict=True, reason="R4-T1-20")
def test_create_resume_wrongly_typed_name_is_400_not_500(client, name):
    """`body.get("name", "").strip()` raises AttributeError on a non-string."""
    assert client.post("/api/resumes", json={"name": name}).status_code in (400, 422)


@pytest.mark.parametrize("name", [5, None, [], {}])
def test_create_resume_wrongly_typed_name_never_leaks_internals(client, name):
    assert_no_leak(client.post("/api/resumes", json={"name": name}))


def test_create_resume_defaults(client):
    r = assert_clean(client.post("/api/resumes", json={"name": "Base"}), 201)
    body = r.json()
    assert body["is_base"] is True
    assert body["page_format"] == "letter"
    assert body["template"]


def test_create_resume_unicode_name(client):
    r = assert_clean(client.post("/api/resumes", json={"name": EMOJI}), 201)
    assert r.json()["name"] == EMOJI


def test_create_resume_ten_megabyte_json_data(client):
    r = client.post("/api/resumes", json={"name": "Big",
                                          "json_data": {"summary": big_string(10)}})
    assert_clean(r, 201, 400, 413, 422)


@pytest.mark.parametrize("bad", ["a string", 5, [1, 2], True])
def test_create_resume_wrongly_typed_json_data_never_500(client, bad):
    assert_clean(client.post("/api/resumes", json={"name": "J", "json_data": bad}), 201, 400, 422)


def test_create_resume_with_a_nonexistent_job_id(client):
    """A dangling job_id is a foreign key violation under Postgres; pinned live."""
    r = client.post("/api/resumes", json={"name": "Orphan", "job_id": MISSING_UUID})
    assert_no_leak(r)


def test_get_resume_missing_id_is_404(client):
    assert_clean(client.get(f"/api/resumes/{MISSING_UUID}"), 404)


def test_patch_resume_missing_id_is_404(client):
    assert_clean(client.patch(f"/api/resumes/{MISSING_UUID}", json={"name": "x"}), 404)


def test_patch_resume_drops_keys_outside_the_allow_list(client, test_db):
    r = make_resume(test_db)
    assert_clean(client.patch(f"/api/resumes/{r.id}",
                              json={"id": MISSING_UUID, "created_at": "2020-01-01",
                                    "name": "kept"}), 200)
    test_db.refresh(r)
    assert r.name == "kept"
    assert str(r.id) != MISSING_UUID


def test_patch_resume_empty_body_is_a_noop_200(client, test_db):
    r = make_resume(test_db)
    assert_clean(client.patch(f"/api/resumes/{r.id}", json={}), 200)


@pytest.mark.parametrize("body", [[1], "x", 3, None])
def test_patch_resume_non_object_body_is_422(client, test_db, body):
    r = make_resume(test_db)
    assert_clean(client.patch(f"/api/resumes/{r.id}", json=body), 422)


def test_patch_resume_reorder_only_json_data_is_persisted(client, test_db):
    """flag_modified guard: a pure reorder must still hit the DB."""
    r = make_resume(test_db, json_data={"skills": ["a", "b"]})
    assert_clean(client.patch(f"/api/resumes/{r.id}",
                              json={"json_data": {"skills": ["b", "a"]}}), 200)
    test_db.expire_all()
    from backend.models.db import Resume
    assert test_db.get(Resume, r.id).json_data["skills"] == ["b", "a"]


def test_delete_resume_missing_id_is_404(client):
    assert_clean(client.delete(f"/api/resumes/{MISSING_UUID}"), 404)


def test_delete_resume_twice_is_404_the_second_time(client, test_db):
    r = make_resume(test_db)
    assert_clean(client.delete(f"/api/resumes/{r.id}"), 200)
    assert_clean(client.delete(f"/api/resumes/{r.id}"), 404)


def test_delete_base_resume_cascades_to_its_tailored_children(client, test_db):
    from backend.models.db import Resume
    base = make_resume(test_db, name="Base")
    child = make_resume(test_db, name="Tailored", is_base=False, parent_id=base.id)
    child_id = child.id
    r = assert_clean(client.delete(f"/api/resumes/{base.id}"), 200)
    assert r.json()["children_deleted"] == 1
    test_db.expire_all()
    assert test_db.query(Resume).filter(Resume.id == child_id).first() is None


def test_list_resumes_filter_contract(client):
    assert_clean(client.get("/api/resumes"), 200)
    assert_clean(client.get("/api/resumes?is_base=true"), 200)
    assert_clean(client.get("/api/resumes?is_base=false"), 200)
    assert_clean(client.get("/api/resumes?is_base=maybe"), 422)


def test_resume_templates_listing(client):
    r = assert_clean(client.get("/api/resumes/templates"), 200)
    assert isinstance(r.json(), list)


# ── /api/resumes/copy ────────────────────────────────────────────────────────

@pytest.mark.parametrize("body", [{}, {"base_resume_id": MISSING_UUID}, {"job_id": MISSING_UUID}])
def test_copy_resume_requires_both_ids(client, body):
    assert_clean(client.post("/api/resumes/copy", json=body), 400)


def test_copy_resume_unknown_base_is_404(client, test_db):
    job = make_job(test_db)
    assert_clean(client.post("/api/resumes/copy", json={
        "base_resume_id": MISSING_UUID, "job_id": str(job.id)}), 404)


def test_copy_resume_unknown_job_is_404(client, test_db):
    base = make_resume(test_db)
    assert_clean(client.post("/api/resumes/copy", json={
        "base_resume_id": str(base.id), "job_id": MISSING_UUID}), 404)


def test_copy_resume_deep_copies_json_data(client, test_db):
    base = make_resume(test_db, json_data={"skills": ["a"]})
    job = make_job(test_db)
    r = assert_clean(client.post("/api/resumes/copy", json={
        "base_resume_id": str(base.id), "job_id": str(job.id)}), 200)
    assert r.json()["json_data"]["skills"] == ["a"]
    assert r.json()["is_base"] is False


# ── /api/resumes/tailor ──────────────────────────────────────────────────────

def test_tailor_requires_a_base_resume_id(client):
    assert_clean(client.post("/api/resumes/tailor", json={}), 400)


def test_tailor_requires_a_job_or_a_description(client, test_db):
    base = make_resume(test_db)
    assert_clean(client.post("/api/resumes/tailor",
                             json={"base_resume_id": str(base.id)}), 400)


def test_tailor_unknown_base_resume_is_404(client, test_db):
    job = make_job(test_db, description="Some JD")
    assert_clean(client.post("/api/resumes/tailor", json={
        "base_resume_id": MISSING_UUID, "job_id": str(job.id)}), 404)


def test_tailor_unknown_job_is_404(client, test_db):
    base = make_resume(test_db)
    assert_clean(client.post("/api/resumes/tailor", json={
        "base_resume_id": str(base.id), "job_id": MISSING_UUID}), 404)


def test_tailor_job_without_any_text_is_400(client, test_db):
    base = make_resume(test_db)
    job = make_job(test_db, url="")
    assert_clean(client.post("/api/resumes/tailor", json={
        "base_resume_id": str(base.id), "job_id": str(job.id)}), 400)


def test_tailor_empty_persona_is_400(client, test_db):
    make_persona(test_db)
    job = make_job(test_db, description="JD")
    assert_clean(client.post("/api/resumes/tailor", json={
        "base_resume_id": "persona", "job_id": str(job.id)}), 400)


def test_tailor_missing_prompt_setting_is_500_with_a_reason(client, test_db):
    """A deliberate 500 that names the misconfiguration — must not be a bare trace."""
    base = make_resume(test_db)
    job = make_job(test_db, description="JD")
    r = client.post("/api/resumes/tailor",
                    json={"base_resume_id": str(base.id), "job_id": str(job.id)})
    assert r.status_code == 500
    assert_no_leak(r)
    assert "cv_tailor_prompt" in r.text


def test_tailor_second_call_on_the_same_pair_is_409(client, test_db, monkeypatch):
    import asyncio
    import backend.api.routes_resumes as rr
    gate = asyncio.Event()

    async def _slow(**kw):
        await gate.wait()
    monkeypatch.setattr(rr, "_tailor_impl", _slow, raising=False)

    set_setting(test_db, "cv_tailor_prompt", "do it")
    base = make_resume(test_db)
    job = make_job(test_db, description="JD")
    body = {"base_resume_id": str(base.id), "job_id": str(job.id)}
    assert_clean(client.post("/api/resumes/tailor", json=body), 202)
    assert_clean(client.post("/api/resumes/tailor", json=body), 409)
    gate.set()


# ── /api/resumes/{id}/score-check ────────────────────────────────────────────

def test_score_check_missing_resume_is_404(client):
    assert_clean(client.post(f"/api/resumes/{MISSING_UUID}/score-check"), 404)


def test_score_check_thin_resume_is_400(client, test_db):
    r = make_resume(test_db, json_data={"summary": "short"})
    assert_clean(client.post(f"/api/resumes/{r.id}/score-check"), 400)


def test_score_check_job_without_text_is_400(client, test_db):
    job = make_job(test_db)
    r = make_resume(test_db, is_base=False, job_id=job.id,
                    json_data={"summary": "x" * 200})
    assert_clean(client.post(f"/api/resumes/{r.id}/score-check"), 400)


def test_score_check_unknown_depth_falls_back_to_light(client, test_db, monkeypatch):
    import backend.api.routes_resumes as rr

    async def _noop(**kw):
        return None
    monkeypatch.setattr(rr, "_score_resume_impl", _noop, raising=False)
    job = make_job(test_db, description="JD " * 50)
    res = make_resume(test_db, is_base=False, job_id=job.id,
                      json_data={"summary": "x" * 200})
    r = assert_clean(client.post(f"/api/resumes/{res.id}/score-check",
                                json={"depth": "banana"}), 202)
    assert r.json()["depth"] == "light"


# ── PDF / import ─────────────────────────────────────────────────────────────

def test_export_pdf_missing_resume_is_404(client):
    assert_clean(client.get(f"/api/resumes/{MISSING_UUID}/pdf"), 404)


def test_preview_missing_resume_is_404(client):
    assert_clean(client.get(f"/api/resumes/{MISSING_UUID}/preview"), 404)


def test_tracer_stats_missing_resume_is_an_empty_shape(client):
    r = client.get(f"/api/resumes/{MISSING_UUID}/tracer-stats")
    assert_clean(r, 200, 404)


def test_import_pdf_without_a_file_is_422(client):
    assert_clean(client.post("/api/resumes/import-pdf"), 422)


def test_import_pdf_rejects_a_non_pdf_name(client):
    r = client.post("/api/resumes/import-pdf",
                    files={"file": ("evil.exe", b"MZ", "application/octet-stream")})
    assert_clean(r, 400, 415, 422)


def test_import_pdf_rejects_an_oversized_file(client):
    r = client.post("/api/resumes/import-pdf",
                    files={"file": ("big.pdf", b"%PDF-" + b"0" * (11 * 1024 * 1024),
                                    "application/pdf")})
    assert_clean(r, 400, 413, 422)


# ══ Cover letters ════════════════════════════════════════════════════════════

def test_create_cover_letter_requires_a_name(client):
    assert_clean(client.post("/api/cover-letters", json={}), 400)


@pytest.mark.parametrize("name", ["", "  ", None])
def test_create_cover_letter_rejects_a_blank_name(client, name):
    assert_clean(client.post("/api/cover-letters", json={"name": name}), 400)


@pytest.mark.parametrize("name", [5, ["L"], {"n": 1}])
@pytest.mark.xfail(strict=True, reason="R4-T1-20")
def test_create_cover_letter_wrongly_typed_name_is_400_not_500(client, name):
    assert client.post("/api/cover-letters", json={"name": name}).status_code in (400, 422)


def test_create_cover_letter_unicode_and_defaults(client):
    r = assert_clean(client.post("/api/cover-letters", json={"name": EMOJI}), 201)
    assert r.json()["name"] == EMOJI
    assert r.json()["page_format"] == "letter"


def test_create_cover_letter_ten_megabyte_body(client):
    r = client.post("/api/cover-letters",
                    json={"name": "Big", "json_data": {"body": big_string(10)}})
    assert_clean(r, 201, 400, 413, 422)


def test_get_cover_letter_missing_id_is_404(client):
    assert_clean(client.get(f"/api/cover-letters/{MISSING_UUID}"), 404)


def test_patch_cover_letter_missing_id_is_404(client):
    assert_clean(client.patch(f"/api/cover-letters/{MISSING_UUID}", json={"name": "x"}), 404)


def test_patch_cover_letter_drops_keys_outside_the_allow_list(client):
    cl = client.post("/api/cover-letters", json={"name": "L"}).json()
    assert_clean(client.patch(f"/api/cover-letters/{cl['id']}",
                              json={"id": MISSING_UUID, "created_at": "2020-01-01",
                                    "name": "kept"}), 200)
    r = client.get(f"/api/cover-letters/{cl['id']}").json()
    assert r["name"] == "kept" and r["id"] == cl["id"]


def test_delete_cover_letter_missing_id_is_404(client):
    assert_clean(client.delete(f"/api/cover-letters/{MISSING_UUID}"), 404)


def test_delete_cover_letter_twice_is_404_the_second_time(client):
    cl = client.post("/api/cover-letters", json={"name": "L"}).json()
    assert_clean(client.delete(f"/api/cover-letters/{cl['id']}"), 200)
    assert_clean(client.delete(f"/api/cover-letters/{cl['id']}"), 404)


def test_export_cover_letter_pdf_missing_id_is_404(client):
    assert_clean(client.get(f"/api/cover-letters/{MISSING_UUID}/pdf"), 404)


@pytest.mark.parametrize("body", [{}, {"resume_id": MISSING_UUID}, {"job_id": MISSING_UUID}])
def test_generate_cover_letter_requires_both_ids(client, body):
    assert_clean(client.post("/api/cover-letters/generate", json=body), 400)


def test_generate_cover_letter_unknown_resume_is_404(client, test_db):
    job = make_job(test_db, description="JD")
    assert_clean(client.post("/api/cover-letters/generate", json={
        "resume_id": MISSING_UUID, "job_id": str(job.id)}), 404)


def test_generate_cover_letter_unknown_job_is_404(client, test_db):
    res = make_resume(test_db)
    assert_clean(client.post("/api/cover-letters/generate", json={
        "resume_id": str(res.id), "job_id": MISSING_UUID}), 404)


def test_generate_cover_letter_job_without_description_is_400(client, test_db):
    res = make_resume(test_db)
    job = make_job(test_db)
    assert_clean(client.post("/api/cover-letters/generate", json={
        "resume_id": str(res.id), "job_id": str(job.id)}), 400)


def test_generate_cover_letter_empty_resume_is_400(client, test_db):
    res = make_resume(test_db, json_data={})
    job = make_job(test_db, description="JD")
    assert_clean(client.post("/api/cover-letters/generate", json={
        "resume_id": str(res.id), "job_id": str(job.id)}), 400)


def test_generate_cover_letter_unknown_target_letter_is_404(client, test_db):
    res = make_resume(test_db)
    job = make_job(test_db, description="JD")
    assert_clean(client.post("/api/cover-letters/generate", json={
        "resume_id": str(res.id), "job_id": str(job.id),
        "cover_letter_id": MISSING_UUID}), 404)


def test_generate_cover_letter_second_call_on_the_same_pair_is_409(client, test_db, monkeypatch):
    import asyncio
    import backend.api.routes_cover_letters as rcl
    gate = asyncio.Event()

    async def _slow(**kw):
        await gate.wait()
    monkeypatch.setattr(rcl, "_generate_impl", _slow, raising=False)

    set_setting(test_db, "cover_letter_prompt", "write it")
    res = make_resume(test_db)
    job = make_job(test_db, description="JD")
    body = {"resume_id": str(res.id), "job_id": str(job.id)}
    assert_clean(client.post("/api/cover-letters/generate", json=body), 202)
    assert_clean(client.post("/api/cover-letters/generate", json=body), 409)
    gate.set()


def test_list_cover_letters_by_job(client, test_db):
    job = make_job(test_db)
    assert_clean(client.get(f"/api/cover-letters?job_id={job.id}"), 200)


# ══ Persona ══════════════════════════════════════════════════════════════════

def test_get_persona_returns_the_singleton(client, test_db):
    make_persona(test_db)
    r = assert_clean(client.get("/api/persona"), 200)
    assert r.json()["id"] == 1


@pytest.mark.parametrize("key", ["bogus", "id", "created_at", "updated_at", "CONTACT", ""])
def test_patch_persona_rejects_unknown_nodes(client, test_db, key):
    make_persona(test_db)
    r = assert_clean(client.patch("/api/persona", json={key: {}}), 400)
    assert "Unknown persona node" in r.text


def test_patch_persona_rejects_a_mixed_known_and_unknown_batch(client, test_db):
    """All-or-nothing: one bad key rejects the whole PATCH, including the good one."""
    make_persona(test_db)
    assert_clean(client.patch("/api/persona",
                              json={"contact": {"name": "A"}, "bogus": 1}), 400)
    assert client.get("/api/persona").json()["contact"] == {}


@pytest.mark.parametrize("node", PERSONA_NODES)
def test_patch_persona_replaces_a_node_wholesale(client, test_db, node):
    make_persona(test_db)
    value = [{"question": "q", "answer": "a"}] if node == "qa_bank" else {"k": "v"}
    r = assert_clean(client.patch("/api/persona", json={node: value}), 200)
    assert r.json()[node] == value


@pytest.mark.parametrize("bad", ["a string", 5, True])
def test_patch_persona_wrongly_typed_node_never_500(client, test_db, bad):
    make_persona(test_db)
    assert_clean(client.patch("/api/persona", json={"contact": bad}), 200, 400, 422)


def test_patch_persona_empty_body_is_a_noop_200(client, test_db):
    make_persona(test_db)
    assert_clean(client.patch("/api/persona", json={}), 200)


@pytest.mark.parametrize("body", [[1], "x", 3, None])
def test_patch_persona_non_object_body_is_422(client, test_db, body):
    make_persona(test_db)
    assert_clean(client.patch("/api/persona", json=body), 422)


def test_patch_persona_ten_megabyte_node(client, test_db):
    make_persona(test_db)
    r = client.patch("/api/persona", json={"resume_content": {"summary": big_string(10)}})
    assert_clean(r, 200, 400, 413, 422)


def test_patch_persona_unicode_round_trips(client, test_db):
    make_persona(test_db)
    r = assert_clean(client.patch("/api/persona", json={"contact": {"name": EMOJI}}), 200)
    assert r.json()["contact"]["name"] == EMOJI


@pytest.mark.parametrize("body", [{}, {"question": "q"}, {"answer": "a"},
                                  {"question": "", "answer": "a"},
                                  {"question": "q", "answer": "  "}])
def test_qa_bank_requires_both_fields(client, test_db, body):
    make_persona(test_db)
    assert_clean(client.post("/api/persona/qa-bank", json=body), 400)


def test_qa_bank_appends_and_counts(client, test_db):
    make_persona(test_db)
    r1 = assert_clean(client.post("/api/persona/qa-bank",
                                 json={"question": "q1", "answer": "a1"}), 200)
    r2 = assert_clean(client.post("/api/persona/qa-bank",
                                 json={"question": "q2", "answer": EMOJI}), 200)
    assert r1.json()["count"] == 1 and r2.json()["count"] == 2


@pytest.mark.parametrize("bad", [5, ["q"], {"a": 1}])
@pytest.mark.xfail(strict=True, reason="R4-T1-20")
def test_qa_bank_wrongly_typed_fields_are_400_not_500(client, test_db, bad):
    make_persona(test_db)
    assert client.post("/api/persona/qa-bank",
                       json={"question": bad, "answer": "a"}).status_code in (400, 422)


@pytest.mark.parametrize("bad", [5, ["q"], {"a": 1}])
def test_qa_bank_wrongly_typed_fields_never_leak_internals(client, test_db, bad):
    make_persona(test_db)
    assert_no_leak(client.post("/api/persona/qa-bank", json={"question": bad, "answer": "a"}))


def test_qa_bank_ten_megabyte_answer(client, test_db):
    make_persona(test_db)
    r = client.post("/api/persona/qa-bank",
                    json={"question": "q", "answer": big_string(10)})
    assert_clean(r, 200, 400, 413, 422)


def test_persona_import_without_a_file_or_body_is_400(client, test_db):
    make_persona(test_db)
    r = client.post("/api/persona/import")
    assert_clean(r, 400, 415, 422)
