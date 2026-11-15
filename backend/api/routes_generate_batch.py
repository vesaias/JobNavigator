"""Generate batch: a tailored résumé and a cover letter for each job of a list, with the
queue on the server.

    POST /api/generate-batches               start a batch, 202 + batch_id
    GET  /api/generate-batches/{batch_id}    its state: counts and the state of each job
    POST /api/generate-batches/{batch_id}/stop   start no more jobs; the jobs in progress end

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

# States of a job in a batch. The last three are final.
QUEUED, TAILORING, SCORING, COVER_LETTER = "queued", "tailoring", "scoring", "cover_letter"
DONE, FAILED, CANCELLED = "done", "failed", "cancelled"
STATES = (QUEUED, TAILORING, SCORING, COVER_LETTER, DONE, FAILED, CANCELLED)

_stop_requested: set[str] = set()   # batch run ids; in memory, as the runs themselves are


# ── Start ────────────────────────────────────────────────────────────────────

@router.post("", status_code=202)
async def start_batch(body: dict, db: Session = Depends(get_db)):
    """Start a batch: {"job_ids": [...], "base_resume_id": "...", "cover_letter": true}."""
    base_resume_id = body.get("base_resume_id")
    cover_letter = body.get("cover_letter", True)
    job_ids = _job_ids(body.get("job_ids"))
    if not base_resume_id:
        raise HTTPException(400, "base_resume_id is required")
    if not isinstance(cover_letter, bool):
        raise HTTPException(400, "cover_letter must be true or false")
    if base_resume_id != "persona":   # launch_tailor checks the Persona for each job
        get_owned_or_404(db, Resume, base_resume_id, "Base resume not found")
    known = {str(r[0]) for r in db.query(Job.id).filter(Job.id.in_([_uuid.UUID(j) for j in job_ids]))}
    unknown = [j for j in job_ids if j not in known]
    if unknown:
        raise HTTPException(422, f"job_ids: not found {unknown[:20]}")

    meta = {"base_resume_id": str(base_resume_id), "cover_letter": cover_letter,
            "jobs": {j: {"state": QUEUED} for j in job_ids}}
    try:
        batch_id = mon.launch_background(
            JOB_TYPE, _batch_impl, trigger="manual", scope_key=SCOPE, meta=meta,
            func_kwargs={"meta": meta})
    except mon.JobAlreadyRunningError:
        return JSONResponse(status_code=409, content={"detail": "A generate batch is already running"})
    return {"batch_id": batch_id, "status": "running", "jobs": len(job_ids)}


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
        jobs[job_id] = {**jobs[job_id], "state": state, **fields}
        mon.save_run_meta(meta)

    async def one(job_id: str) -> None:
        async with slots:
            if batch_id in _stop_requested:
                set_state(job_id, CANCELLED)
                return
            try:
                await _generate_for_job(job_id, meta, set_state)
            except Exception as e:   # a defect in one job must not end the batch
                logger.exception("generate batch: job %s failed", job_id)
                set_state(job_id, FAILED, error=str(e)[:300])

    try:
        await asyncio.gather(*(one(j) for j in jobs))
    finally:
        _stop_requested.discard(batch_id)
    # The run itself is `completed` even when jobs failed: `failed` means that the batch
    # did not get to its end (a backend restart). The counts carry the failed jobs.
    counts = _counts(jobs)
    return ", ".join(f"{n} {state}" for state, n in counts.items() if n) + f" of {len(jobs)}"


async def _generate_for_job(job_id: str, meta: dict, set_state) -> None:
    """One job: tailor, the chained score, the cover letter. Each `_step` is one tracked run."""
    from backend.api.routes_cover_letters import launch_cover_letter
    from backend.api.routes_resumes import launch_tailor

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
    in that state; `state=none` leaves the jobs out). When the batch is not `running`, a job
    that is not `done` got no result from it."""
    if state is not None and state != "none" and state not in STATES:
        raise HTTPException(422, f"state must be none or one of {list(STATES)}")
    run = _batch_run(db, batch_id)
    meta = run.meta or {}
    jobs = meta.get("jobs") or {}
    shown = {} if state == "none" else {j: row for j, row in jobs.items() if state in (None, row["state"])}
    return {
        "batch_id": str(run.id),
        "status": run.status,
        "stop_requested": str(run.id) in _stop_requested,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "error": mon.sanitize_run_error(run.error),
        "base_resume_id": meta.get("base_resume_id"),
        "cover_letter": meta.get("cover_letter"),
        "total": len(jobs),
        "counts": _counts(jobs),
        "jobs": shown,
    }


@router.post("/{batch_id}/stop")
def stop_batch(batch_id: str, db: Session = Depends(get_db)):
    """Start no more jobs of the batch. The jobs in progress run to their end; the queued ones become `cancelled`."""
    run = _batch_run(db, batch_id)
    if run.status != "running":
        raise HTTPException(409, f"The batch is not running (status: {run.status})")
    _stop_requested.add(str(run.id))
    return {"batch_id": str(run.id), "stop_requested": True}
