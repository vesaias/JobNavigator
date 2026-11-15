"""A run records the ids of what it created in JobRun.meta["created"]; the résumé list
filters by job, creation time and count; the job list keeps only the asked `fields`."""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from backend.models.db import Job, JobRun, Resume, Setting
from backend.tests.r4_support import client, make_job  # noqa: F401 — client is a fixture


def _run(db, run_id):
    db.expire_all()
    return db.query(JobRun).filter(JobRun.id == uuid.UUID(run_id)).one()


# ── JobRun.meta["created"] ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_keeps_created_ids_beside_its_launch_meta(test_db):
    import backend.job_monitor as mon
    mon._running.clear()

    async def _worker():
        mon.note_run_created(resume_id=uuid.UUID(int=7), chained_run_id=None)
        mon.note_run_created(cover_letter_id="c-1")
        return "done"

    run_id = mon.launch_background("tailor_resume", _worker, scope_key="k1", meta={"base_name": "Base"})
    await mon._running["tailor_resume:k1"].task
    run = _run(test_db, run_id)
    assert run.status == "completed" and run.result_summary == "done"
    assert run.meta == {"base_name": "Base",
                        "created": {"resume_id": str(uuid.UUID(int=7)), "cover_letter_id": "c-1"}}


@pytest.mark.asyncio
async def test_a_chained_run_does_not_inherit_its_parents_created_ids(test_db):
    import backend.job_monitor as mon
    mon._running.clear()
    child = {}

    async def _child():
        return "child"

    async def _parent():
        mon.note_run_created(resume_id="r-1")           # before the launch: the child copies this context
        child["id"] = mon.launch_background("analyze_job", _child, scope_key="k3")
        child["task"] = mon._running["analyze_job:k3"].task
        mon.note_run_created(chained_run_id=child["id"])

    parent_id = mon.launch_background("tailor_resume", _parent, scope_key="k2")
    await mon._running["tailor_resume:k2"].task
    await child["task"]
    assert _run(test_db, parent_id).meta == {"created": {"resume_id": "r-1", "chained_run_id": child["id"]}}
    assert _run(test_db, child["id"]).meta is None


@pytest.mark.asyncio
async def test_a_failed_run_has_no_created_ids_of_an_earlier_run(test_db):
    import backend.job_monitor as mon
    mon._running.clear()

    async def _ok():
        mon.note_run_created(resume_id="r-1")

    async def _boom():
        raise RuntimeError("no")

    first = mon.launch_background("tailor_resume", _ok, scope_key="k4")
    await mon._running["tailor_resume:k4"].task
    second = mon.launch_background("tailor_resume", _boom, scope_key="k5")
    await mon._running["tailor_resume:k5"].task
    assert _run(test_db, first).meta == {"created": {"resume_id": "r-1"}}
    assert _run(test_db, second).status == "failed" and _run(test_db, second).meta is None


@pytest.mark.asyncio
async def test_tailor_notes_the_copy_and_the_chained_score_run(test_db, monkeypatch):
    import backend.api.routes_resumes as rr
    import backend.job_monitor as mon
    test_db.add(Setting(key="cv_tailor_prompt", value="p {resume_json} {job_description}"))
    test_db.add(Setting(key="tailor_auto_quick_score", value="light"))
    job = Job(external_id="created1", content_hash="cr1", company="Acme", title="PM", description="jd")
    base = Resume(name="Base", is_base=True, template="inter",
                  json_data={"summary": "s", "experience": [], "skills": {}})
    test_db.add_all([job, base])
    test_db.commit()

    async def fake_call(prompt, system, max_tokens):
        return {"text": '{"summary":"tailored"}', "usage": {}}
    monkeypatch.setattr("backend.analyzer.llm_client.call_cv_tailor_llm", fake_call)
    monkeypatch.setattr(rr, "launch_background", lambda *a, **kw: "chained-run", raising=False)
    monkeypatch.setattr(rr, "_tailoring_semaphore", None, raising=False)

    mon._run_created.set(None)
    await rr._tailor_impl(str(base.id), str(job.id), None)
    copy = test_db.query(Resume).filter(Resume.job_id == job.id, Resume.is_base == False).one()  # noqa: E712
    assert mon._take_run_created() == {"resume_id": str(copy.id), "chained_run_id": "chained-run"}


# ── GET /api/resumes filters ─────────────────────────────────────────────────

def test_resume_list_filters_by_job_time_and_count(client, test_db):
    job_a, job_b = make_job(test_db), make_job(test_db)
    now = datetime.now(timezone.utc)
    base = Resume(name="Base", is_base=True, json_data={})
    old = Resume(name="old", is_base=False, job_id=job_a.id, json_data={}, created_at=now - timedelta(days=2))
    new = Resume(name="new", is_base=False, job_id=job_a.id, json_data={}, created_at=now)
    other = Resume(name="other", is_base=False, job_id=job_b.id, json_data={}, created_at=now)
    test_db.add_all([base, old, new, other])
    test_db.commit()

    def names(query):
        resp = client.get(f"/api/resumes?{query}")
        assert resp.status_code == 200, resp.text
        return sorted(r["name"] for r in resp.json())

    assert names(f"job_id={job_a.id}") == ["new", "old"]
    since = (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert names(f"job_id={job_a.id}&created_after={since}") == ["new"]
    assert names(f"is_base=false&created_after={since}") == ["new", "other"]
    assert len(client.get("/api/resumes?limit=2").json()) == 2
    assert len(client.get("/api/resumes").json()) == 4
    assert client.get("/api/resumes?job_id=not-a-uuid").status_code == 422
    assert client.get("/api/resumes?limit=0").status_code == 422


# ── GET /api/jobs?fields= ────────────────────────────────────────────────────

def test_job_list_keeps_only_the_asked_fields(client, test_db):
    make_job(test_db, title="Art Director", company="Acme")
    rows = client.get("/api/jobs?fields=id,title, company").json()["jobs"]
    assert [set(r) for r in rows] == [{"id", "title", "company"}]
    assert rows[0]["title"] == "Art Director"
    assert "status" in client.get("/api/jobs").json()["jobs"][0]


def test_job_update_reply_names_the_tailored_copy(client, test_db):
    job = make_job(test_db)
    copy = Resume(name="copy", is_base=False, job_id=job.id, json_data={})
    test_db.add(copy)
    test_db.commit()
    out = client.patch(f"/api/jobs/{job.id}", json={"seen": True}).json()
    assert out["has_tailored_resume"] is True and out["tailored_resume_id"] == str(copy.id)


def test_job_list_rejects_an_unknown_field(client, test_db):
    make_job(test_db)
    resp = client.get("/api/jobs?fields=id,nope")
    assert resp.status_code == 422 and "nope" in resp.json()["detail"]


# ── Compact forms of the search and scheduler lists ──────────────────────────

def test_search_list_brief_drops_the_filter_lists(client, test_db):
    from backend.tests.r4_support import make_search
    make_search(test_db, name="SRE", title_include_keywords=["sre"], title_exclude_keywords=["intern"])
    full = client.get("/api/searches").json()[0]
    brief = client.get("/api/searches?brief=1").json()[0]
    assert full["title_include_keywords"] == ["sre"]
    assert set(full) - set(brief) == {"title_include_keywords", "title_exclude_keywords",
                                      "company_filter", "company_exclude"}
    assert brief["name"] == "SRE"


def test_scheduler_list_without_overrides_has_no_company_or_search_rows(client, test_db):
    from backend.tests.r4_support import make_company, make_search
    make_company(test_db, name="Acme", active=True, scrape_interval_minutes=60)
    make_search(test_db, name="SRE", active=True, run_interval_minutes=60)
    names = lambda q: {r["name"] for r in client.get(f"/api/scheduler/jobs{q}").json()}  # noqa: E731
    assert {"Scrape: Acme", "Search: SRE"} <= names("")
    assert not {"Scrape: Acme", "Search: SRE"} & names("?overrides=false")
