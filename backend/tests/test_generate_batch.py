"""Generate batch (/api/generate-batches): the queue is on the server, a job goes through
tailor -> chained score -> cover letter one run at a time, and the batch works on
`tailoring_max_concurrent` jobs at a time."""
import asyncio
import time
import uuid
from datetime import datetime

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


def _row(out, job):
    """The row of a job without its times; a started job has `started_at`, and a job in
    a final state has `finished_at`."""
    row = dict(out["jobs"][str(job.id)])
    assert ("started_at" in row) == (row["state"] not in ("queued", "cancelled", "skipped")), row
    assert ("finished_at" in row) == (row["state"] in ("done", "failed", "cancelled", "skipped")), row
    row.pop("started_at", None), row.pop("finished_at", None)
    return row


class _Fakes:
    """`launch_tailor` and `launch_cover_letter` that start real tracked runs with fake
    workers (no LLM). They record how many workers run at the same time."""

    def __init__(self, monkeypatch, step_seconds=0.03, fail_tailor=(), refuse=(), hold=False):
        import backend.job_monitor as mon
        self.mon, self.step, self.fail_tailor, self.refuse = mon, step_seconds, set(fail_tailor), set(refuse)
        self.active = self.peak = 0
        self.hold = hold    # workers do not end while this is true
        self.letters = []   # the bodies that the batch gave to launch_cover_letter
        self.tailored = []  # the job ids that the batch gave to launch_tailor
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
        self.tailored.append(job_id)
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
        assert _row(out, job) == {"state": "done", "resume_id": f"resume-of-{job.id}",
                                  "cover_letter_id": f"letter-of-{job.id}"}
    assert out["stopped"] is False and out["average_job_seconds"] is not None
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
    assert _row(out, jobs[0]) == {"state": "failed", "step": "tailoring",
                                  "error": "claude timed out after 300s"}
    assert out["jobs"][str(jobs[1].id)]["error"].startswith("Job has no description")
    failed = client.get(f"{URL}/{out['batch_id']}?state=failed").json()["jobs"]
    assert set(failed) == {str(jobs[0].id), str(jobs[1].id)}
    assert client.get(f"{URL}/{out['batch_id']}?state=none").json()["jobs"] == {}


def test_batch_without_cover_letter_and_rewrite_of_an_existing_letter(client, test_db, monkeypatch):
    fakes = _Fakes(monkeypatch)
    base, job = _base(test_db), make_job(test_db)
    out = _wait(client, _start(client, [job], base, cover_letter=False).json()["batch_id"])
    assert _row(out, job) == {"state": "done", "resume_id": f"resume-of-{job.id}"}
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
    stop = client.post(f"{URL}/{batch_id}/stop").json()
    assert (stop["stopped"], stop["cancelled_now"], stop["in_progress"]) == (True, 4, 2), stop
    assert stop["counts"]["cancelled"] == 4 and stop["counts"]["queued"] == 0
    # The queue is cancelled at the stop request, not when a worker gets free.
    now = client.get(f"{URL}/{batch_id}").json()
    assert now["status"] == "running" and now["stopped"] is True
    assert now["counts"]["cancelled"] == 4 and now["counts"]["tailoring"] == 2
    assert all("finished_at" in r for r in now["jobs"].values() if r["state"] == "cancelled")
    assert client.post(f"{URL}/{batch_id}/stop").json()["cancelled_now"] == 0   # a second stop does no harm
    fakes.hold = False
    out = _wait(client, batch_id)
    # The jobs in progress went through all their steps.
    assert out["status"] == "completed" and out["stopped"] is True
    assert out["counts"]["done"] == 2 and out["counts"]["cancelled"] == 4, out["jobs"]
    assert len(fakes.tailored) == 2 and len(fakes.letters) == 2
    assert client.post(f"{URL}/{batch_id}/stop").status_code == 409   # it is not running now


def test_only_missing_keeps_what_a_job_has(client, test_db, monkeypatch):
    fakes = _Fakes(monkeypatch)
    base = _base(test_db)
    ready, no_letter, new = (make_job(test_db) for _ in range(3))
    copies = {}
    for job in (ready, no_letter):
        copies[job.id] = Resume(name="copy", is_base=False, parent_id=base.id, job_id=job.id, json_data={})
        test_db.add(copies[job.id])
    test_db.commit()
    letter = CoverLetter(name="letter", job_id=ready.id, resume_id=copies[ready.id].id, json_data={})
    test_db.add(letter)
    test_db.commit()

    start = _start(client, [ready, no_letter, new], base, only_missing=True)
    assert start.status_code == 202 and start.json()["skipped"] == 1, start.text
    out = _wait(client, start.json()["batch_id"])
    assert out["only_missing"] is True
    assert out["counts"]["skipped"] == 1 and out["counts"]["done"] == 2, out["jobs"]
    assert _row(out, ready) == {"state": "skipped", "resume_id": str(copies[ready.id].id),
                                "cover_letter_id": str(letter.id)}
    # The job with a resume and no letter: no tailor run, the letter from the resume it has.
    assert _row(out, no_letter) == {"state": "done", "resume_id": str(copies[no_letter.id].id),
                                    "cover_letter_id": f"letter-of-{no_letter.id}", "letter_only": True}
    # The mean time counts the job that went through the tailor only.
    full = out["jobs"][str(new.id)]
    assert out["average_job_seconds"] == round(
        (datetime.fromisoformat(full["finished_at"]) - datetime.fromisoformat(full["started_at"])).total_seconds(), 1)
    assert _row(out, new)["resume_id"] == f"resume-of-{new.id}"
    assert fakes.tailored == [str(new.id)]
    assert {b["job_id"] for b in fakes.letters} == {str(no_letter.id), str(new.id)}

    # Without a cover letter, a job that has its resume needs nothing.
    start = _start(client, [ready, no_letter], base, only_missing=True, cover_letter=False)
    assert start.json()["skipped"] == 2
    out = _wait(client, start.json()["batch_id"])
    assert out["status"] == "completed" and out["counts"]["skipped"] == 2
    assert fakes.tailored == [str(new.id)]

    # Without `only_missing` the batch makes each job again.
    out = _wait(client, _start(client, [ready], base).json()["batch_id"])
    assert _row(out, ready)["state"] == "done" and fakes.tailored[-1] == str(ready.id)


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
    assert post({"job_ids": [str(job.id)], "base_resume_id": str(base.id), "only_missing": 1}).status_code == 400


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
    assert _row(out, job) == {"state": "done", "resume_id": str(copy.id), "cover_letter_id": str(letter.id)}
    assert str(letter.resume_id) == str(copy.id)
    history = client.get("/api/monitor/history?limit=10").json()
    rows = history if isinstance(history, list) else history["runs"]
    assert {"generate_batch", "tailor_resume", "generate_cover_letter"} <= {r["job_type"] for r in rows}
