"""R5: per-run `meta` — which résumés a score covers, which base a tailor copies.

Covers RunningJob.meta, /api/monitor/in-flight?detail=1, the analyze + tailor
launch sites, and _job_to_dict's in_flight_detail.
"""
import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from backend.tests.r4_support import (  # noqa: F401  (fixtures)
    client, _clear_running_state, _no_outbound,
    make_job, make_resume, set_setting,
)


def _install_fake_running(monkeypatch, entries):
    """Fake in-memory _running. entries = [(key, job_type, target_job_id, meta)]."""
    from backend.job_monitor import RunningJob
    import backend.job_monitor as mon
    fake = {}
    for key, jt, target, meta in entries:
        fake[key] = RunningJob(
            run_id=uuid.uuid4(),
            job_type=jt,
            trigger="manual",
            started_at=datetime.now(timezone.utc),
            scope_key=key,
            target_job_id=target,
            meta=meta,
        )
    monkeypatch.setattr(mon, "_running", fake)


# ── RunningJob.meta ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_launch_background_stores_meta_on_running_job(test_db):
    import backend.job_monitor as mon
    mon._running.clear()
    gate = asyncio.Event()

    async def _slow():
        await gate.wait()

    meta = {"resume_names": ["PM", "Persona"], "depth": "light"}
    try:
        mon.launch_background("analyze_job", _slow, scope_key="s1", meta=meta)
        entry = mon._running["analyze_job:s1"]
        assert entry.meta == meta
    finally:
        gate.set()
        await asyncio.sleep(0)
        mon._running.clear()


@pytest.mark.asyncio
async def test_tracked_run_stores_meta_on_running_job(test_db):
    import backend.job_monitor as mon
    mon._running.clear()
    meta = {"resume_names": ["PM"], "depth": "full"}
    async with mon.tracked_run("analyze_job", scope_key="s2", meta=meta) as run:
        assert run.meta == meta
        assert mon._running["analyze_job:s2"].meta == meta


def test_running_job_meta_defaults_to_none():
    from backend.job_monitor import RunningJob
    r = RunningJob(run_id=uuid.uuid4(), job_type="analyze_job", trigger="manual",
                   started_at=datetime.now(timezone.utc))
    assert r.meta is None


# ── /api/monitor/in-flight ───────────────────────────────────────────────────

def test_in_flight_default_shape_is_unchanged(client, monkeypatch):
    """Without detail=1 the values stay bare job-type strings."""
    job_a = uuid.uuid4()
    _install_fake_running(monkeypatch, [
        (f"analyze_job:{job_a}", "analyze_job", job_a,
         {"resume_names": ["PM"], "depth": "light"}),
    ])
    data = client.get("/api/monitor/in-flight").json()
    assert data[str(job_a)] == ["analyze_job"]


def test_in_flight_detail_returns_job_type_and_meta(client, monkeypatch):
    job_a, job_b = uuid.uuid4(), uuid.uuid4()
    meta = {"resume_names": ["PM", "Persona"], "depth": "full"}
    _install_fake_running(monkeypatch, [
        (f"analyze_job:{job_a}", "analyze_job", job_a, meta),
        (f"tailor_resume:{job_b}", "tailor_resume", job_b, None),
        ("scrape_all", "scrape_all", None, None),  # no target_job_id — omitted
    ])
    data = client.get("/api/monitor/in-flight?detail=1").json()
    assert data[str(job_a)] == [{"job_type": "analyze_job", "meta": meta}]
    assert data[str(job_b)] == [{"job_type": "tailor_resume", "meta": None}]
    assert len(data) == 2


def test_in_flight_detail_respects_job_ids_filter(client, monkeypatch):
    job_a, job_b = uuid.uuid4(), uuid.uuid4()
    _install_fake_running(monkeypatch, [
        (f"analyze_job:{job_a}", "analyze_job", job_a, {"depth": "light"}),
        (f"analyze_job:{job_b}", "analyze_job", job_b, {"depth": "full"}),
    ])
    data = client.get(f"/api/monitor/in-flight?detail=1&job_ids={job_a}").json()
    assert list(data) == [str(job_a)]


# ── Launch sites ─────────────────────────────────────────────────────────────

def _gated_score(gate):
    async def _slow(*a, **kw):
        await gate.wait()
    return _slow


def test_analyze_endpoint_meta_names_the_base_resumes(client, test_db):
    """POST /api/analyze/{id} tags the run with the names it will score under."""
    make_resume(test_db, name="PM")
    make_resume(test_db, name="Platform")
    job = make_job(test_db, description="Looking for a PM")
    gate = asyncio.Event()
    try:
        with patch("backend.analyzer.cv_scorer.score_single_job", _gated_score(gate)):
            assert client.post(f"/api/analyze/{job.id}?depth=light").status_code == 202
            data = client.get(f"/api/monitor/in-flight?detail=1&job_ids={job.id}").json()
            entry = data[str(job.id)][0]
            assert entry["job_type"] == "analyze_job"
            assert entry["meta"]["depth"] == "light"
            assert set(entry["meta"]["resume_names"]) == {"PM", "Platform"}
    finally:
        gate.set()


def test_analyze_endpoint_meta_uses_explicit_cv_ids(client, test_db):
    """With cv_ids the meta names only those résumés."""
    picked = make_resume(test_db, name="PM")
    make_resume(test_db, name="Platform")
    job = make_job(test_db, description="Looking for a PM")
    gate = asyncio.Event()
    try:
        with patch("backend.analyzer.cv_scorer.score_single_job", _gated_score(gate)):
            resp = client.post(f"/api/analyze/{job.id}?depth=full",
                               json={"cv_ids": [str(picked.id)]})
            assert resp.status_code == 202
            data = client.get(f"/api/monitor/in-flight?detail=1&job_ids={job.id}").json()
            meta = data[str(job.id)][0]["meta"]
            assert meta == {"resume_names": ["PM"], "depth": "full"}
    finally:
        gate.set()


def test_on_save_auto_score_meta(client, test_db):
    """PATCH /api/jobs/{id} {saved:true} with on_save_action set tags the run too."""
    set_setting(test_db, "on_save_action", "light")
    make_resume(test_db, name="PM")
    job = make_job(test_db, description="JD text")
    gate = asyncio.Event()
    try:
        with patch("backend.analyzer.cv_scorer.score_single_job", _gated_score(gate)):
            assert client.patch(f"/api/jobs/{job.id}",
                                json={"saved": True}).status_code == 200
            data = client.get(f"/api/monitor/in-flight?detail=1&job_ids={job.id}").json()
            meta = data[str(job.id)][0]["meta"]
            assert meta == {"resume_names": ["PM"], "depth": "light"}
    finally:
        gate.set()


def _patch_tailor(monkeypatch, gate):
    import backend.api.routes_resumes as rr

    async def _slow(**kw):
        await gate.wait()
    monkeypatch.setattr(rr, "_tailor_impl", _slow, raising=False)


def test_tailor_meta_carries_base_name_and_replaces_false(client, test_db, monkeypatch):
    set_setting(test_db, "cv_tailor_prompt", "do it")
    base = make_resume(test_db, name="PM")
    job = make_job(test_db, description="JD")
    gate = asyncio.Event()
    _patch_tailor(monkeypatch, gate)
    try:
        resp = client.post("/api/resumes/tailor",
                           json={"base_resume_id": str(base.id), "job_id": str(job.id)})
        assert resp.status_code == 202
        data = client.get(f"/api/monitor/in-flight?detail=1&job_ids={job.id}").json()
        assert data[str(job.id)][0]["meta"] == {"base_name": "PM", "replaces": False}
    finally:
        gate.set()


def test_tailor_meta_replaces_true_when_a_copy_exists(client, test_db, monkeypatch):
    from backend.models.db import Resume
    set_setting(test_db, "cv_tailor_prompt", "do it")
    base = make_resume(test_db, name="PM")
    job = make_job(test_db, description="JD")
    test_db.add(Resume(name="PM → Acme", is_base=False, job_id=job.id,
                       json_data={"header": {"name": "A"}}))
    test_db.commit()
    gate = asyncio.Event()
    _patch_tailor(monkeypatch, gate)
    try:
        resp = client.post("/api/resumes/tailor",
                           json={"base_resume_id": str(base.id), "job_id": str(job.id)})
        assert resp.status_code == 202
        data = client.get(f"/api/monitor/in-flight?detail=1&job_ids={job.id}").json()
        assert data[str(job.id)][0]["meta"] == {"base_name": "PM", "replaces": True}
    finally:
        gate.set()


def test_tailor_from_persona_meta_base_name(client, test_db, monkeypatch):
    from backend.models.db import Persona
    set_setting(test_db, "cv_tailor_prompt", "do it")
    test_db.add(Persona(id=1, resume_content={"summary": "P"}))
    test_db.commit()
    job = make_job(test_db, description="JD")
    gate = asyncio.Event()
    _patch_tailor(monkeypatch, gate)
    try:
        resp = client.post("/api/resumes/tailor",
                           json={"base_resume_id": "persona", "job_id": str(job.id)})
        assert resp.status_code == 202
        data = client.get(f"/api/monitor/in-flight?detail=1&job_ids={job.id}").json()
        assert data[str(job.id)][0]["meta"]["base_name"] == "Persona"
    finally:
        gate.set()


def test_score_check_meta_labels_a_job_linked_copy_tailored(client, test_db, monkeypatch):
    """POST /api/resumes/{id}/score-check tags the run with the cv_scores label + depth."""
    import backend.api.routes_resumes as rr
    from backend.models.db import Resume
    job = make_job(test_db, description="A long enough job description to score against.")
    copy = Resume(name="PM → Acme", is_base=False, job_id=job.id,
                  json_data={"summary": "A tailored summary that is comfortably "
                                        "longer than the fifty character floor."})
    test_db.add(copy)
    test_db.commit()
    test_db.refresh(copy)

    gate = asyncio.Event()

    async def _slow(**kw):
        await gate.wait()
    monkeypatch.setattr(rr, "_score_resume_impl", _slow, raising=False)

    try:
        resp = client.post(f"/api/resumes/{copy.id}/score-check", json={"depth": "full"})
        assert resp.status_code == 202
        data = client.get(f"/api/monitor/in-flight?detail=1&job_ids={job.id}").json()
        entry = data[str(job.id)][0]
        assert entry["job_type"] == "score_resume"
        assert entry["meta"] == {"resume_names": ["Tailored"], "depth": "full"}
    finally:
        gate.set()


# ── _job_to_dict ─────────────────────────────────────────────────────────────

def test_job_dict_exposes_in_flight_detail(client, test_db, monkeypatch):
    job = make_job(test_db, description="JD")
    meta = {"resume_names": ["PM"], "depth": "light"}
    _install_fake_running(monkeypatch, [
        (f"analyze_job:{job.id}", "analyze_job", job.id, meta),
    ])
    detail = client.get(f"/api/jobs/{job.id}").json()
    assert detail["in_flight"] == ["analyze_job"]
    assert detail["in_flight_detail"] == [{"job_type": "analyze_job", "meta": meta}]

    listed = client.get("/api/jobs").json()["jobs"]
    row = next(j for j in listed if j["id"] == str(job.id))
    assert row["in_flight"] == ["analyze_job"]
    assert row["in_flight_detail"] == [{"job_type": "analyze_job", "meta": meta}]


def test_job_dict_in_flight_detail_is_empty_when_idle(client, test_db, monkeypatch):
    job = make_job(test_db, description="JD")
    _install_fake_running(monkeypatch, [])
    detail = client.get(f"/api/jobs/{job.id}").json()
    assert detail["in_flight"] == []
    assert detail["in_flight_detail"] == []
