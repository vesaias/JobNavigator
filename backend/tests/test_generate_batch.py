"""Generate batch (/api/generate-batches): the queue is on the server, a job goes through
tailor -> chained score -> cover letter one run at a time, and the batch works on
`tailoring_max_concurrent` jobs at a time."""
import asyncio
import time
import uuid

import pytest
from fastapi import HTTPException

from backend.models.db import CoverLetter, Resume, Setting
from backend.tests.r4_support import ACT_AS, client, make_job  # noqa: F401 — client is a fixture

URL = "/api/generate-batches"


def _base(db):
    base = Resume(name="Base", is_base=True, template="inter",
                  json_data={"summary": "s", "experience": [], "skills": {}})
    db.add(base)
    db.commit()
    return base


def _until(condition, what, timeout=20):
    end = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < end, f"timeout: {what}"
        time.sleep(0.02)


def _wait(c, batch_id):
    """The state of the batch after its end. It waits on the in-memory run list, not on
    GET: the test database is one SQLite connection for every thread, so a read from the
    client thread during the run can roll back a write of the run (not so in Postgres)."""
    import backend.job_monitor as mon
    _until(lambda: not any(r.job_type == "generate_batch" for r in list(mon._running.values())),
           "the batch run ends")
    out = c.get(f"{URL}/{batch_id}").json()
    assert out["status"] != "running", out
    return out


class _Fakes:
    """`launch_tailor` and `launch_cover_letter` that start real tracked runs with fake
    workers (no LLM). They record how many workers run at the same time."""

    def __init__(self, monkeypatch, step_seconds=0.03, fail_tailor=(), refuse=(), hold=False):
        import backend.job_monitor as mon
        self.mon, self.step, self.fail_tailor, self.refuse = mon, step_seconds, set(fail_tailor), set(refuse)
        self.active = self.peak = 0
        self.hold = hold    # workers do not end while this is true
        self.letters = []   # the bodies that the batch gave to launch_cover_letter
        mon._running.clear()
        monkeypatch.setattr("backend.api.routes_resumes.launch_tailor", self.launch_tailor)
        monkeypatch.setattr("backend.api.routes_cover_letters.launch_cover_letter", self.launch_letter)

    async def _work(self):
        self.active += 1
        self.peak = max(self.peak, self.active)
        try:
            await asyncio.sleep(self.step)
            while self.hold:
                await asyncio.sleep(0.01)
        finally:
            self.active -= 1

    def launch_tailor(self, db, base_resume_id, job_id, job_description=None):
        mon = self.mon
        if job_id in self.refuse:
            raise HTTPException(400, "Job has no description, URL, or cached page to tailor from")

        async def score():
            await self._work()

        async def tailor():
            await self._work()
            if job_id in self.fail_tailor:
                raise RuntimeError("claude timed out after 300s")
            chained = mon.launch_background("analyze_job", score, scope_key=f"{job_id}:tailored")
            mon.note_run_created(resume_id=f"resume-of-{job_id}", chained_run_id=chained)

        return mon.launch_background("tailor_resume", tailor, scope_key=f"{base_resume_id}:{job_id}"), "light"

    def launch_letter(self, db, body):
        mon = self.mon
        self.letters.append(body)

        async def letter():
            await self._work()
            mon.note_run_created(cover_letter_id=body["cover_letter_id"] or f"letter-of-{body['job_id']}")

        return mon.launch_background("generate_cover_letter", letter, scope_key=f"cl:{body['job_id']}")


def _start(c, jobs, base, **extra):
    return c.post(URL, json={"job_ids": [str(j.id) for j in jobs], "base_resume_id": str(base.id), **extra})


# ── The queue ────────────────────────────────────────────────────────────────

def test_batch_runs_each_job_through_tailor_score_and_letter(client, test_db, monkeypatch):
    fakes = _Fakes(monkeypatch)
    base, jobs = _base(test_db), [make_job(test_db) for _ in range(5)]
    resp = _start(client, jobs, base)
    assert resp.status_code == 202, resp.text
    assert resp.json()["jobs"] == 5

    out = _wait(client, resp.json()["batch_id"])
    assert out["status"] == "completed" and out["total"] == 5
    assert out["counts"]["done"] == 5 and sum(out["counts"].values()) == 5
    for job in jobs:
        assert out["jobs"][str(job.id)] == {"state": "done", "resume_id": f"resume-of-{job.id}",
                                            "cover_letter_id": f"letter-of-{job.id}"}
    # Two jobs at a time, and a job is in one run at a time: at most 2 fake LLM calls together.
    assert fakes.peak == 2
    # The letter is written from the copy that the tailor of the same job created.
    assert {b["resume_id"] for b in fakes.letters} == {f"resume-of-{j.id}" for j in jobs}


def test_batch_follows_the_tailoring_limit_setting(client, test_db, monkeypatch):
    import backend.job_monitor as mon
    test_db.add(Setting(key="tailoring_max_concurrent", value="1"))
    test_db.commit()
    mon.reset_limiter("tailoring")
    try:
        fakes = _Fakes(monkeypatch)
        base, jobs = _base(test_db), [make_job(test_db) for _ in range(3)]
        out = _wait(client, _start(client, jobs, base).json()["batch_id"])
        assert out["counts"]["done"] == 3 and fakes.peak == 1
    finally:
        mon.reset_limiter("tailoring")


def test_a_failed_job_does_not_stop_the_batch(client, test_db, monkeypatch):
    base, jobs = _base(test_db), [make_job(test_db) for _ in range(4)]
    _Fakes(monkeypatch, fail_tailor={str(jobs[0].id)}, refuse={str(jobs[1].id)})
    out = _wait(client, _start(client, jobs, base).json()["batch_id"])
    assert out["status"] == "completed"
    assert out["counts"]["done"] == 2 and out["counts"]["failed"] == 2
    assert out["jobs"][str(jobs[0].id)] == {"state": "failed", "step": "tailoring",
                                            "error": "claude timed out after 300s"}
    assert out["jobs"][str(jobs[1].id)]["error"].startswith("Job has no description")
    failed = client.get(f"{URL}/{out['batch_id']}?state=failed").json()["jobs"]
    assert set(failed) == {str(jobs[0].id), str(jobs[1].id)}
    assert client.get(f"{URL}/{out['batch_id']}?state=none").json()["jobs"] == {}


def test_batch_without_cover_letter_and_rewrite_of_an_existing_letter(client, test_db, monkeypatch):
    fakes = _Fakes(monkeypatch)
    base, job = _base(test_db), make_job(test_db)
    out = _wait(client, _start(client, [job], base, cover_letter=False).json()["batch_id"])
    assert out["jobs"][str(job.id)] == {"state": "done", "resume_id": f"resume-of-{job.id}"}
    assert fakes.letters == []

    old = CoverLetter(name="old", job_id=job.id, json_data={})
    test_db.add(old)
    test_db.commit()
    out = _wait(client, _start(client, [job], base).json()["batch_id"])
    assert fakes.letters[0]["cover_letter_id"] == str(old.id)        # rewritten, not a second letter
    assert out["jobs"][str(job.id)]["cover_letter_id"] == str(old.id)


def test_stop_cancels_the_queued_jobs(client, test_db, monkeypatch):
    fakes = _Fakes(monkeypatch, hold=True)
    base, jobs = _base(test_db), [make_job(test_db) for _ in range(6)]
    batch_id = _start(client, jobs, base).json()["batch_id"]
    _until(lambda: fakes.active == 2, "two jobs are in their tailor run")   # they hold; no writes now
    assert client.post(f"{URL}/{batch_id}/stop").json() == {"batch_id": batch_id, "stop_requested": True}
    fakes.hold = False
    out = _wait(client, batch_id)
    assert out["status"] == "completed" and out["stop_requested"] is False
    assert out["counts"]["done"] == 2 and out["counts"]["cancelled"] == 4, out["jobs"]
    assert client.post(f"{URL}/{batch_id}/stop").status_code == 409   # it is not running now


def test_one_batch_at_a_time(client, test_db, monkeypatch):
    _Fakes(monkeypatch, step_seconds=0.2)
    base, jobs = _base(test_db), [make_job(test_db) for _ in range(2)]
    first = _start(client, jobs, base).json()["batch_id"]
    assert _start(client, jobs, base).status_code == 409
    _wait(client, first)
    assert _start(client, jobs, base).status_code == 202


# ── Request checks and scope ─────────────────────────────────────────────────

def test_start_rejects_a_bad_request(client, test_db):
    base, job = _base(test_db), make_job(test_db)
    post = lambda body: client.post(URL, json=body)  # noqa: E731
    assert post({"job_ids": [str(job.id)]}).status_code == 400                       # no base
    assert post({"job_ids": [], "base_resume_id": str(base.id)}).status_code == 400
    assert post({"job_ids": ["x"], "base_resume_id": str(base.id)}).status_code == 422
    missing = post({"job_ids": [str(job.id), str(uuid.uuid4())], "base_resume_id": str(base.id)})
    assert missing.status_code == 422 and "not found" in missing.json()["detail"]
    assert post({"job_ids": [str(job.id)], "base_resume_id": str(uuid.uuid4())}).status_code == 404
    many = [str(uuid.uuid4()) for _ in range(201)]
    assert post({"job_ids": many, "base_resume_id": str(base.id)}).status_code == 422
    assert post({"job_ids": [str(job.id)], "base_resume_id": str(base.id), "cover_letter": "yes"}).status_code == 400


def test_batch_state_is_readable_by_its_account_only(client, test_db, monkeypatch):
    import backend.models.db as db_mod
    _Fakes(monkeypatch)
    base, job = _base(test_db), make_job(test_db)
    batch_id = _start(client, [job], base).json()["batch_id"]
    _wait(client, batch_id)
    member = db_mod.Account(name="Member", role="member", color=db_mod.ACCOUNT_COLORS[1])
    test_db.add(member)
    test_db.commit()
    as_member = {ACT_AS: str(member.id)}
    assert client.get(f"{URL}/{batch_id}", headers=as_member).status_code == 404
    assert client.post(f"{URL}/{batch_id}/stop", headers=as_member).status_code == 404
    assert client.get(f"{URL}/{uuid.uuid4()}").status_code == 404
    assert client.get(f"{URL}/not-an-id").status_code == 404
    assert client.get(f"{URL}/{batch_id}?state=nope").status_code == 422


# ── With the real launch functions (fake LLM only) ───────────────────────────

def test_batch_end_to_end_with_the_real_runs(client, test_db, monkeypatch):
    import backend.api.routes_resumes as rr
    import backend.job_monitor as mon
    from backend.analyzer import cover_letter_generator as gen
    mon._running.clear()
    test_db.add_all([
        Setting(key="cv_tailor_prompt", value="p {resume_json} {job_description}"),
        Setting(key="cover_letter_prompt", value="p {resume_json} {job_description}"),
        Setting(key="tailor_auto_quick_score", value="off"),
    ])
    base, job = _base(test_db), make_job(test_db, description="We need an SRE.")

    async def fake_tailor(prompt, system, max_tokens):
        return {"text": '{"summary":"tailored"}', "usage": {}}

    async def fake_letter(prompt, system, max_tokens=1500, cached_prefix=None):
        return {"text": '{"greeting":"Dear Team,","body_paragraphs":["P1","P2","P3"],'
                        '"closing":"Sincerely,","signature":"Jordan"}', "usage": {}}

    monkeypatch.setattr("backend.analyzer.llm_client.call_cv_tailor_llm", fake_tailor)
    monkeypatch.setattr(gen, "call_cover_letter_llm", fake_letter)
    monkeypatch.setattr(rr, "_tailoring_semaphore", None, raising=False)

    out = _wait(client, _start(client, [job], base).json()["batch_id"])
    row = out["jobs"][str(job.id)]
    assert row["state"] == "done", out
    test_db.expire_all()
    copy = test_db.query(Resume).filter(Resume.job_id == job.id, Resume.is_base == False).one()  # noqa: E712
    letter = test_db.query(CoverLetter).filter(CoverLetter.job_id == job.id).one()
    assert row == {"state": "done", "resume_id": str(copy.id), "cover_letter_id": str(letter.id)}
    assert str(letter.resume_id) == str(copy.id)
    history = client.get("/api/monitor/history?limit=10").json()
    rows = history if isinstance(history, list) else history["runs"]
    assert {"generate_batch", "tailor_resume", "generate_cover_letter"} <= {r["job_type"] for r in rows}
