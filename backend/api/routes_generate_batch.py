"""Generate batch: a tailored résumé and a cover letter for each job of a list, with the
queue on the server.

    POST /api/generate-batches               start a batch, 202 + batch_id
    GET  /api/generate-batches/{batch_id}    its state: counts and the state of each job
    POST /api/generate-batches/{batch_id}/stop   cancel the queued jobs; the jobs in progress end

A batch is one background run (`generate_batch`), so it is in Run history and a backend
restart ends it as `failed` / `Process restarted`. Its state is the run's `meta`, written
at each step, so the state of each job is still readable after that.

Each job goes through three runs, one after the other: `tailor_resume`, the `analyze_job`
that the tailor chains (when Settings chains one), `generate_cover_letter`. They are the
same runs that the dashboard starts (same checks, same Run history, same in-flight state
on the job). The batch works on `tailoring_max_concurrent` jobs at a time, and a job is in
one run at a time, so the batch has at most that many LLM calls in progress. Runs started
outside the batch are not counted.
"""
import asyncio
import logging
import uuid as _uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

import backend.job_monitor as mon
from backend.accounts.owned import get_owned_or_404
from backend.models.db import CoverLetter, Job, JobRun, Resume, SessionLocal, get_db

logger = logging.getLogger("jobnavigator.generate_batch")
router = APIRouter(prefix="/generate-batches", tags=["resumes"])

JOB_TYPE = "generate_batch"
MAX_JOBS = 200
# One batch for each account at a time: two would double the load on the runner.
SCOPE = "batch"

# States of a job in a batch. The last four are final. `skipped`: `only_missing` found
# that the job has its resume and its letter, so the batch started no run for it.
QUEUED, TAILORING, SCORING, COVER_LETTER = "queued", "tailoring", "scoring", "cover_letter"
DONE, FAILED, CANCELLED, SKIPPED = "done", "failed", "cancelled", "skipped"
STATES = (QUEUED, TAILORING, SCORING, COVER_LETTER, DONE, FAILED, CANCELLED, SKIPPED)

# The meta of each batch that runs in this process, by batch id, from its start request
# to the end of its run. The stop request changes it, and the run sees the change (both
# are on the event loop).
_live: dict[str, dict] = {}


# ── Start ────────────────────────────────────────────────────────────────────

@router.post("", status_code=202)
async def start_batch(body: dict, db: Session = Depends(get_db)):
    """Start a batch: {"job_ids": [...], "base_resume_id": "...", "cover_letter": true,
    "only_missing": false}. `only_missing` keeps what a job has: a job with a tailored
    resume gets no tailor run, and a job that also has a cover letter is `skipped`."""
    base_resume_id = body.get("base_resume_id")
    cover_letter = body.get("cover_letter", True)
    only_missing = body.get("only_missing", False)
    job_ids = _job_ids(body.get("job_ids"))
    if not base_resume_id:
        raise HTTPException(400, "base_resume_id is required")
    for name, value in (("cover_letter", cover_letter), ("only_missing", only_missing)):
        if not isinstance(value, bool):
            raise HTTPException(400, f"{name} must be true or false")
    if base_resume_id != "persona":   # launch_tailor checks the Persona for each job
        get_owned_or_404(db, Resume, base_resume_id, "Base resume not found")
    known = {str(r[0]) for r in db.query(Job.id).filter(Job.id.in_([_uuid.UUID(j) for j in job_ids]))}
    unknown = [j for j in job_ids if j not in known]
    if unknown:
        raise HTTPException(422, f"job_ids: not found {unknown[:20]}")

    jobs = {j: {"state": QUEUED} for j in job_ids}
    if only_missing:
        for job_id, has in _existing(db, job_ids).items():
            if "cover_letter_id" in has or not cover_letter:
                jobs[job_id] = {"state": SKIPPED, **has, "finished_at": _now()}
            else:   # the letter is missing: write it from the resume that the job has
                jobs[job_id].update(resume_id=has["resume_id"], letter_only=True)
    meta = {"base_resume_id": str(base_resume_id), "cover_letter": cover_letter,
            "only_missing": only_missing, "jobs": jobs}
    try:
        batch_id = mon.launch_background(
            JOB_TYPE, _batch_impl, trigger="manual", scope_key=SCOPE, meta=meta,
            func_kwargs={"meta": meta})
    except mon.JobAlreadyRunningError:
        return JSONResponse(status_code=409, content={"detail": "A generate batch is already running"})
    _live[batch_id] = meta   # here, not in the run: a stop can come before the run's first step
    return {"batch_id": batch_id, "status": "running", "jobs": len(job_ids),
            "skipped": _counts(jobs)[SKIPPED]}


def _existing(db: Session, job_ids: list[str]) -> dict[str, dict]:
    """What each job has already: {job_id: {"resume_id", "cover_letter_id"}}, the newest of
    each. Only the jobs with a tailored resume are in the reply. A copy of another base
    resume counts too: a job has one tailored copy, as on the dashboard."""
    ids = [_uuid.UUID(j) for j in job_ids]
    out: dict[str, dict] = {}
    for job_id, resume_id in (db.query(Resume.job_id, Resume.id)
                              .filter(Resume.job_id.in_(ids), Resume.is_base == False)  # noqa: E712
                              .order_by(Resume.updated_at)):
        out[str(job_id)] = {"resume_id": str(resume_id)}
    for job_id, letter_id in (db.query(CoverLetter.job_id, CoverLetter.id)
                              .filter(CoverLetter.job_id.in_(ids)).order_by(CoverLetter.updated_at)):
        if str(job_id) in out:
            out[str(job_id)]["cover_letter_id"] = str(letter_id)
    return out


def _job_ids(value) -> list[str]:
    """The job ids of a request: canonical uuid strings, in order, without repeats."""
    if not isinstance(value, list) or not value:
        raise HTTPException(400, "job_ids must be a list with at least one job id")
    out: list[str] = []
    for raw in value:
        try:
            jid = str(_uuid.UUID(str(raw)))
        except (ValueError, AttributeError, TypeError):
            raise HTTPException(422, f"job_ids: {raw!r} is not a job id")
        if jid not in out:
            out.append(jid)
    if len(out) > MAX_JOBS:
        raise HTTPException(422, f"job_ids: {MAX_JOBS} jobs at most in one batch")
    return out


# ── The run ──────────────────────────────────────────────────────────────────

async def _batch_impl(meta: dict) -> str:
    batch_id = mon.current_run_id()
    jobs: dict = meta["jobs"]
    slots = asyncio.Semaphore(mon.get_limiter("tailoring").value)

    def set_state(job_id: str, state: str, **fields) -> None:
        row = {**jobs[job_id], "state": state, **fields}
        row.setdefault("started_at", _now())
        if state in (DONE, FAILED):
            row["finished_at"] = _now()
        jobs[job_id] = row
        mon.save_run_meta(meta)

    async def one(job_id: str) -> None:
        async with slots:
            if jobs[job_id]["state"] != QUEUED:   # skipped at the start, or cancelled by a stop
                return
            try:
                await _generate_for_job(job_id, meta, set_state)
            except Exception as e:   # a defect in one job must not end the batch
                logger.exception("generate batch: job %s failed", job_id)
                set_state(job_id, FAILED, error=str(e)[:300])

    try:
        await asyncio.gather(*(one(j) for j in jobs))
    finally:
        _live.pop(batch_id, None)
    # The run itself is `completed` even when jobs failed: `failed` means that the batch
    # did not get to its end (a backend restart). The counts carry the failed jobs.
    counts = _counts(jobs)
    return ", ".join(f"{n} {state}" for state, n in counts.items() if n) + f" of {len(jobs)}"


async def _generate_for_job(job_id: str, meta: dict, set_state) -> None:
    """One job: tailor, the chained score, the cover letter. Each `_step` is one tracked run."""
    from backend.api.routes_cover_letters import launch_cover_letter
    from backend.api.routes_resumes import launch_tailor

    resume_id = meta["jobs"][job_id].get("resume_id")   # `only_missing`: the job has its resume
    if not resume_id:
        set_state(job_id, TAILORING)
        tailor = await _step(lambda db: launch_tailor(db, meta["base_resume_id"], job_id)[0])
        resume_id = tailor["created"].get("resume_id")
        if tailor["error"] or not resume_id:
            set_state(job_id, FAILED, step=TAILORING, error=tailor["error"] or "The run created no resume")
            return

        chained = tailor["created"].get("chained_run_id")
        if chained:
            set_state(job_id, SCORING, resume_id=resume_id)
            await mon.wait_for_run(chained)   # its result is on the job; a failed score keeps the copy

    if not meta["cover_letter"]:
        set_state(job_id, DONE, resume_id=resume_id)
        return

    set_state(job_id, COVER_LETTER, resume_id=resume_id)

    def launch(db):
        # Rewrite the newest letter of the job, as Regenerate does; a job gets one letter.
        newest = (db.query(CoverLetter.id).filter(CoverLetter.job_id == _uuid.UUID(job_id))
                  .order_by(CoverLetter.updated_at.desc()).first())
        return launch_cover_letter(db, {"resume_id": resume_id, "job_id": job_id,
                                        "cover_letter_id": str(newest[0]) if newest else None})
    letter = await _step(launch)
    letter_id = letter["created"].get("cover_letter_id")
    if letter["error"] or not letter_id:
        set_state(job_id, FAILED, step=COVER_LETTER, resume_id=resume_id,
                  error=letter["error"] or "The run created no cover letter")
        return
    set_state(job_id, DONE, resume_id=resume_id, cover_letter_id=letter_id)


async def _step(launch) -> dict:
    """Start one run with `launch(db) -> run_id`, wait for it: {"error": text or None, "created": {...}}."""
    db = SessionLocal()
    try:
        run_id = launch(db)
    except HTTPException as e:
        return {"error": str(e.detail), "created": {}}
    except mon.JobAlreadyRunningError as e:
        return {"error": f"{e.job_type} is already running for this job", "created": {}}
    finally:
        db.close()
    # No await between the launch and this call, so the run is still registered.
    run = await mon.wait_for_run(run_id)
    if run is None:
        return {"error": "The run is not known to this process", "created": {}}
    return {"error": run.error, "created": run.created or {}}


def _counts(jobs: dict) -> dict:
    counts = {state: 0 for state in STATES}
    for row in jobs.values():
        counts[row["state"]] += 1
    return counts


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _average_job_seconds(jobs: dict) -> Optional[float]:
    """The mean time of a `done` job that went through the tailor, from its first run to
    its last. A `letter_only` job is not counted: it takes about a third of that time.
    For an estimate of the rest: jobs not final x this / jobs in progress at a time."""
    times = [(datetime.fromisoformat(row["finished_at"]) - datetime.fromisoformat(row["started_at"])).total_seconds()
             for row in jobs.values()
             if row["state"] == DONE and not row.get("letter_only")
             and row.get("started_at") and row.get("finished_at")]
    return round(sum(times) / len(times), 1) if times else None


# ── State and stop ───────────────────────────────────────────────────────────

def _batch_run(db: Session, batch_id: str) -> JobRun:
    try:
        run_id = _uuid.UUID(str(batch_id))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(404, "Batch not found")
    run = db.query(JobRun).filter(JobRun.id == run_id, JobRun.job_type == JOB_TYPE).first()
    if run is None:
        raise HTTPException(404, "Batch not found")
    return run


@router.get("/{batch_id}")
def get_batch(batch_id: str, state: Optional[str] = None, db: Session = Depends(get_db)):
    """The batch: status, counts for each state, and the jobs (`state=failed` keeps the jobs
    in that state; `state=none` leaves the jobs out). `stopped` tells that a stop request
    cancelled its queue. When the batch is not `running`, a job that is not `done` or
    `skipped` got no result from it."""
    if state is not None and state != "none" and state not in STATES:
        raise HTTPException(422, f"state must be none or one of {list(STATES)}")
    run = _batch_run(db, batch_id)
    meta = run.meta or {}
    jobs = meta.get("jobs") or {}
    shown = {} if state == "none" else {j: row for j, row in jobs.items() if state in (None, row["state"])}
    return {
        "batch_id": str(run.id),
        "status": run.status,
        "stopped": bool(meta.get("stopped")),
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "error": mon.sanitize_run_error(run.error),
        "base_resume_id": meta.get("base_resume_id"),
        "cover_letter": meta.get("cover_letter"),
        "only_missing": bool(meta.get("only_missing")),
        "total": len(jobs),
        "counts": _counts(jobs),
        "average_job_seconds": _average_job_seconds(jobs),
        "jobs": shown,
    }


@router.post("/{batch_id}/stop")
async def stop_batch(batch_id: str, db: Session = Depends(get_db)):
    """Stop the batch: the queued jobs become `cancelled` now. A job in progress is not
    interrupted: it goes through all its steps (tailor, score, cover letter), and then
    the batch ends as `completed` with `stopped` true.

    `async`, so that it runs on the event loop, between two steps of the batch run."""
    run = _batch_run(db, batch_id)
    meta = _live.get(str(run.id))
    if run.status != "running" or meta is None:
        raise HTTPException(409, f"The batch is not running (status: {run.status})")
    jobs = meta["jobs"]
    cancelled = [j for j, row in jobs.items() if row["state"] == QUEUED]
    for job_id in cancelled:
        jobs[job_id] = {**jobs[job_id], "state": CANCELLED, "finished_at": _now()}
    meta["stopped"] = True
    run.meta = dict(meta)   # a new object, so that the session sees the change
    db.commit()
    counts = _counts(jobs)
    return {"batch_id": str(run.id), "stopped": True, "cancelled_now": len(cancelled),
            "in_progress": counts[TAILORING] + counts[SCORING] + counts[COVER_LETTER], "counts": counts}
