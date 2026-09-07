"""LLM-based CV scorer — scores job vs all uploaded CV versions dynamically."""
import asyncio
import json
import logging
import time
from backend.analyzer.llm_client import call_llm
from backend.analyzer.llm_logger import log_llm_call
from backend.models.db import SessionLocal, Job, Setting

logger = logging.getLogger("jobnavigator.cv_scorer")

# ── Global scoring gate (limits concurrent LLM scoring jobs) ──────────────
# The gate itself lives in job_monitor so launch_background can take it before
# the worker opens its first DB session; this is the same object, re-entrant
# per task, so a worker already inside the gate is not blocked by its own
# score_job_sync call.


def _get_scoring_semaphore():
    """The process-wide scoring gate (`scoring_max_concurrent`)."""
    from backend.job_monitor import get_limiter
    return get_limiter("scoring")


def reset_scoring_semaphore():
    """Drop the gate so the next call re-reads the limit. Called on settings change."""
    from backend.job_monitor import reset_limiter
    reset_limiter("scoring")


def _flatten_resume(json_data: dict) -> str:
    """Render a Resume.json_data dict (or Persona.resume_content) to plaintext with '## Section' headers for LLM scoring; empty sections are omitted."""
    if not json_data:
        return ""
    parts = []

    header = json_data.get("header") or {}
    if isinstance(header, dict):
        if header.get("name"):
            parts.append(str(header["name"]))
        contact_bits = []
        for key in ("email", "phone", "linkedin", "github", "website", "location"):
            if header.get(key):
                contact_bits.append(str(header[key]))
        if contact_bits:
            parts.append(" | ".join(contact_bits))

    summary = json_data.get("summary")
    if summary:
        parts.append("## Summary")
        parts.append(str(summary))

    experience = json_data.get("experience") or []
    if experience:
        parts.append("## Experience")
        for exp in experience:
            title = exp.get("title", "")
            company = exp.get("company", "")
            # schema field is "date"; keep "dates" as back-compat
            dates = exp.get("date") or exp.get("dates") or ""
            location = exp.get("location", "")
            line = f"{title} at {company} ({dates})".strip(" ()")
            if line:
                parts.append(f"{line} — {location}".strip(" —") if location else line)
            desc = exp.get("description", "")
            if desc:
                parts.append(desc)
            for b in exp.get("bullets", []) or []:
                parts.append(f"- {b}")

    skills = json_data.get("skills") or {}
    if skills:
        parts.append("## Skills")
        if isinstance(skills, dict):
            for category, items in skills.items():
                if isinstance(items, list):
                    parts.append(f"{category}: {', '.join(str(i) for i in items)}")
                else:
                    parts.append(f"{category}: {items}")
        elif isinstance(skills, list):
            parts.append(", ".join(str(s) for s in skills))

    education = json_data.get("education") or []
    if education:
        parts.append("## Education")
        for edu in education:
            degree = edu.get("degree", "")
            school = edu.get("school", "")
            loc = edu.get("location", "")
            years = edu.get("years") or edu.get("year") or ""
            tail = " ".join(x for x in (loc, years) if x)
            parts.append(f"{degree} — {school}, {tail}".strip(" —,"))

    projects = json_data.get("projects") or []
    if projects:
        parts.append("## Projects")
        for proj in projects:
            name = proj.get("name", "")
            desc = proj.get("description", "")
            line = f"{name}: {desc}".strip(": ")
            if line:
                parts.append(line)
            for b in proj.get("bullets", []) or []:
                parts.append(f"- {b}")

    publications = json_data.get("publications") or []
    if publications:
        parts.append("## Publications")
        for pub in publications:
            title = pub.get("title", "")
            # schema is {title, description}; keep venue/year as back-compat
            detail = pub.get("description") or " ".join(x for x in (pub.get("venue"), pub.get("year")) if x)
            line = f"{title} — {detail}".strip(" —,")
            if line:
                parts.append(line)

    return "\n".join(p for p in parts if p)


# Reserved id used in selected_resume_ids / default_resume_id to mean
# "score against Persona.resume_content as a virtual Resume named 'Persona'".
_PERSONA_KEY = "persona"
_PERSONA_DISPLAY = "Persona"


def _get_persona_text(db) -> dict:
    """Return {'Persona': flattened_text} when the singleton persona has non-empty resume_content, else {} — only resume_content is used for scoring."""
    from backend.models.db import Persona
    p = db.query(Persona).filter(Persona.id == 1).first()
    if not p:
        return {}
    text = _flatten_resume(p.resume_content or {})
    if not text:
        return {}
    return {_PERSONA_DISPLAY: text}


def _get_resume_texts(db) -> dict:
    """Return {Resume.name: flattened_text} for every base Resume + Persona (if populated, always last), ordered by Resume.id for stable cache keys."""
    from backend.models.db import Resume
    out = {}
    for r in db.query(Resume).filter(Resume.is_base == True).order_by(Resume.id).all():
        text = _flatten_resume(r.json_data or {})
        if text:
            out[r.name] = text
    out.update(_get_persona_text(db))
    return out


def _get_default_resume(db) -> dict:
    """Return {Resume.name: flat_text} for the default Resume (special id 'persona' returns persona text); empty dict if not set or not found."""
    from backend.models.db import Resume
    row = db.query(Setting).filter(Setting.key == "default_resume_id").first()
    if not row or not row.value:
        return {}
    if row.value == _PERSONA_KEY:
        return _get_persona_text(db)
    r = db.query(Resume).filter(Resume.id == row.value, Resume.is_base == True).first()
    if not r:
        return {}
    text = _flatten_resume(r.json_data or {})
    if not text:
        return {}
    return {r.name: text}


def _get_resume_texts_for_company(db, company) -> dict:
    """Return resume texts for a company from company.selected_resume_ids (which can mix Resume UUIDs with 'persona'), falling back to the default, then all base resumes."""
    from backend.models.db import Resume
    selected = getattr(company, "selected_resume_ids", None) or []
    if selected:
        out = {}
        resume_ids = [s for s in selected if s != _PERSONA_KEY]
        if resume_ids:
            for r in db.query(Resume).filter(Resume.is_base == True, Resume.id.in_(resume_ids)).order_by(Resume.id).all():
                text = _flatten_resume(r.json_data or {})
                if text:
                    out[r.name] = text
        if _PERSONA_KEY in selected:
            out.update(_get_persona_text(db))
        if out:
            return out
    default = _get_default_resume(db)
    if default:
        return default
    return _get_resume_texts(db)


def _job_text_from_row(job) -> str | None:
    """Job text already on the row (description, then cached page). No I/O, so
    the caller's session is never held across a network call."""
    description = getattr(job, "description", None)
    if description and len(description.strip()) > 50:
        return description.strip()

    cached = getattr(job, "cached_page_text", None)
    if cached and len(cached.strip()) > 50:
        logger.info(f"Job {job.id}: using cached_page_text (no description)")
        return cached.strip()

    return None


async def _fetch_job_text(job_id, url: str) -> str | None:
    """Cache the live page for a job that has no text, then read the result back.

    Deliberately takes ids, not an ORM instance: it must be callable with no
    session open, since `_cache_job_page` does an HTTP fetch and possibly a
    Playwright render. Opens one short session at the end to read the result.
    """
    if not url:
        return None
    logger.info(f"Job {job_id}: no text available, fetching live page")
    try:
        from backend.api.routes_applications import _cache_job_page
        await _cache_job_page(str(job_id), url)
    except Exception as e:
        logger.warning(f"Job {job_id}: live page fetch failed: {e}")
        return None

    db = SessionLocal()
    try:
        text = db.query(Job.cached_page_text).filter(Job.id == job_id).scalar()
    except Exception as e:
        logger.warning(f"Job {job_id}: could not read back cached page: {e}")
        return None
    finally:
        db.close()
    if text and len(text.strip()) > 50:
        return text.strip()
    return None


async def _get_job_text(job: Job, db=None) -> str | None:
    """Job text from description, cached page, or a live fetch; None if nothing is available.

    Passing `db` still means "a live fetch is welcome" (unchanged), but the
    session is NOT held across it: the live path goes through `_fetch_job_text`,
    which owns its own short sessions.
    """
    text = _job_text_from_row(job)
    if text:
        return text
    if db is None:
        return None
    text = await _fetch_job_text(job.id, getattr(job, "url", None))
    if text and db is not None:
        try:
            db.refresh(job)
        except Exception:
            pass
    return text


async def score_job_sync(job: Job, cv_texts: dict, db=None, depth="light", preloaded_text: str = None) -> dict:
    """Score a job against all provided CV versions under the global scoring semaphore; depth='full' includes a detailed report."""
    sem = _get_scoring_semaphore()
    async with sem:
        return await _score_job_inner(job, cv_texts, db, depth, preloaded_text)


async def _score_job_inner(job: Job, cv_texts: dict, db=None, depth="light", preloaded_text: str = None) -> dict:
    """Inner scoring logic (called under the semaphore); returns a dict on success, or None for either an intentional skip (no text/CVs — callers must pre-check before calling) or a transient LLM failure that should be retried next pass."""
    job_text = preloaded_text or await _get_job_text(job, db)
    if not job_text:
        logger.warning(f"Job {job.id} has no text (description, cache, or live), skipping scoring")
        return None

    if len(cv_texts) < 1:
        logger.warning("No CVs uploaded, skipping scoring")
        return None

    # Read prompts + model from settings (quick DB read, released immediately)
    settings_db = db or SessionLocal()
    try:
        rubric_row = settings_db.query(Setting).filter(Setting.key == "scoring_rubric").first()
        rubric = rubric_row.value if rubric_row and rubric_row.value else ""
        schema_key = "scoring_output_full" if depth == "full" else "scoring_output_light"
        schema_row = settings_db.query(Setting).filter(Setting.key == schema_key).first()
        output_schema = schema_row.value if schema_row and schema_row.value else ""
        # Scoring can override the Primary model (empty = use Primary); the Fallback
        # is applied inside call_llm regardless, which reports the pair that answered.
        from backend.analyzer.llm_client import resolve_llm_config
        _cfg = resolve_llm_config("scoring", db=settings_db)
        provider_for_log = _cfg["provider"]
        model_for_log = _cfg["model"]
        scoring_api_key = _cfg["api_key"]
        cache_row = settings_db.query(Setting).filter(Setting.key == "prompt_caching_enabled").first()
        caching_enabled = (cache_row.value if cache_row else "true").strip().lower() == "true"
    finally:
        if not db:
            settings_db.close()

    cv_sections = []
    cv_names = list(cv_texts.keys())
    for i, (name, text) in enumerate(cv_texts.items(), 1):
        cv_sections.append(f"Resume Version {i} — {name}:\n{text}")

    score_fields = ", ".join(f'"{name}": 0-100' for name in cv_names)
    if output_schema:
        output_schema = output_schema.replace("CV_NAMES_HERE", score_fields)
        best_cv_options = " | ".join(f'"{name}"' for name in cv_names)
        output_schema = output_schema.replace('"CV_NAME"', best_cv_options)

    # CACHEABLE PREFIX: rubric + CV sections + schema. Invariant across jobs scored
    # against the same CV set. Anthropic ephemeral cache TTL = 5 min.
    cached_prefix = f"""{rubric}

{chr(10).join(cv_sections)}

{output_schema}"""

    # PER-JOB SUFFIX: just the JD. Changes every call.
    user_prompt = f"JOB DESCRIPTION:\n{job_text[:8000]}"

    max_tokens = 2000 if depth == "full" else 600
    system_msg = "You are a senior tech recruiter evaluating candidate-job fit. Score precisely using the rubric provided. Return ONLY valid JSON, no markdown."

    purpose = "score_full" if depth == "full" else "score_light"
    started = time.monotonic()
    call_success = True
    call_error = None
    usage = {"input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0, "cache_write_tokens": 0}
    return_value = None

    try:
        # Honor the prompt_caching_enabled setting — setting cached_prefix=None disables
        # the cache_control block on the Anthropic request, so caching is fully off.
        effective_prefix = cached_prefix if caching_enabled else None
        resp = await call_llm(user_prompt, system_msg, max_tokens, cached_prefix=effective_prefix,
                              provider=provider_for_log, model=model_for_log, api_key=scoring_api_key)
        text = resp["text"]
        usage = resp.get("usage", usage)
        # If call_llm fell back to the secondary pair, log what actually ran.
        provider_for_log = resp.get("provider") or provider_for_log
        model_for_log = resp.get("model") or model_for_log

        # Parse JSON — handle markdown wrapping and trailing commentary
        import re
        cleaned = text.strip()
        match = re.search(r'\{[\s\S]*\}', cleaned)
        if match:
            cleaned = match.group(0)
        result = json.loads(cleaned)

        # A confused model can emit {"scores": null}; .get's default doesn't catch
        # an explicit null, so validate the shape and treat malformed output as a transient failure.
        if not isinstance(result.get("scores"), dict) or not result["scores"]:
            call_success = False
            call_error = "malformed LLM response: 'scores' missing, null, or not a dict"
            logger.warning(
                f"Job {job.id}: {call_error} — raw head: {text[:200]!r}"
            )
            result = None

        # For full depth, extract scoring_report fields
        if result is None:
            pass  # fall through with return_value = None (transient failure)
        elif depth == "full":
            report = {}
            for key in ["summary", "breakdown", "requirement_mapping", "keyword_coverage_pct",
                         "matched_keywords", "missing_keywords", "hard_blockers", "ats_tip"]:
                if key in result:
                    report[key] = result[key]
            if report:
                return_value = {**result, "_scoring_report": report}
            else:
                return_value = result
        else:
            return_value = result

    except json.JSONDecodeError as e:
        call_success = False
        call_error = f"JSON decode: {e}"
        logger.error(f"Failed to parse LLM response as JSON: {e}")
    except Exception as e:
        call_success = False
        call_error = str(e)
        logger.error(f"LLM call failed: {e}")
    finally:
        duration_ms = int((time.monotonic() - started) * 1000)
        if not call_success:
            # The caller turns this into the string "Scoring failed", which
            # launch_background would otherwise record as a successful run — a
            # provider outage then shows green in Stats (R4-T1-28).
            try:
                from backend.job_monitor import mark_run_failed
                mark_run_failed(f"Scoring failed: {call_error or 'unknown LLM error'}")
            except Exception:
                pass
        try:
            log_llm_call(
                purpose=purpose,
                provider=provider_for_log,
                model=model_for_log,
                usage=usage,
                duration_ms=duration_ms,
                job_id=getattr(job, "id", None),
                success=call_success,
                error=call_error,
            )
        except Exception as e:
            logger.warning(f"log_llm_call failed in scorer (non-fatal): {e}")

    return return_value


def _alert_snapshot(job: Job):
    """Detached copy of the fields `telegram.send_job_alert` reads.

    The alert is an HTTP round trip, so it is sent after the session closes; a
    committed ORM instance would have its attributes expired by then.
    """
    from types import SimpleNamespace
    return SimpleNamespace(
        id=job.id, company=job.company, title=job.title, url=job.url,
        location=job.location, remote=job.remote,
        salary_min=job.salary_min, salary_max=job.salary_max,
        h1b_verdict=job.h1b_verdict,
        h1b_company_lca_count=job.h1b_company_lca_count,
        h1b_company_approval_rate=job.h1b_company_approval_rate,
        h1b_jd_flag=job.h1b_jd_flag, h1b_jd_snippet=job.h1b_jd_snippet,
        cv_scores=dict(job.cv_scores or {}),
    )


def _find_company_for_job(db, job: Job):
    """Find the Company record matching a job's company name or alias (case-insensitive)."""
    from backend.models.db import find_company_by_name
    return find_company_by_name(db, job.company)


async def analyze_unscored_jobs(status: str = "saved"):
    """Score all unscored jobs against uploaded CVs in batches of 20; status='saved' scores saved jobs, status='new' scores new jobs from auto_scoring_depth != 'off' entities only.

    Every phase owns a short session and closes it before anything is awaited
    over the network: read the batch -> (fetch missing pages) -> LLM -> write.
    A batch used to hold one connection from the first query to the last commit,
    LLM calls included, so a slow provider pinned a pooled connection for the
    whole run.
    """
    from types import SimpleNamespace
    from sqlalchemy import or_, text, func
    from backend.models.db import Search, Company as CompanyModel

    batch_size = 20
    total_scored = 0
    # Jobs this pass has already handled. A transient LLM failure leaves
    # cv_scores NULL on purpose (so the next pass retries), which without this
    # would make the `while True` loop re-select the same batch forever.
    attempted: set = set()

    # -- Phase 0: per-run constants (short session, no network) --------------
    db = SessionLocal()
    try:
        default_cv_texts = _get_default_resume(db) or _get_resume_texts(db)
        if not default_cv_texts:
            logger.warning("No CVs uploaded yet, skipping analysis pipeline")
            return

        # For "new" jobs, only score those from entities with auto_scoring_depth != 'off'
        auto_score_filter = None
        if status != "saved":
            auto_companies = db.query(CompanyModel).filter(CompanyModel.auto_scoring_depth.in_(["light", "full"])).all()
            auto_company_names = set()
            for c in auto_companies:
                auto_company_names.add(c.name.lower())
                if c.aliases:
                    for alias in c.aliases:
                        auto_company_names.add(alias.lower())
            auto_search_ids = [s.id for s in db.query(Search).filter(Search.auto_scoring_depth.in_(["light", "full"])).all()]

            conditions = []
            if auto_company_names:
                conditions.append(func.lower(Job.company).in_(list(auto_company_names)))
            if auto_search_ids:
                conditions.append(Job.search_id.in_(auto_search_ids))

            if not conditions:
                logger.info("No entities with auto_scoring_depth enabled, skipping new job analysis")
                return

            auto_score_filter = or_(*conditions)

        # Per-run constants -- hoisted out of the per-job loop (were re-queried per job)
        default_depth_row = db.query(Setting).filter(Setting.key == "scoring_default_depth").first()
        default_depth = default_depth_row.value if default_depth_row and default_depth_row.value else "light"
        threshold_row = db.query(Setting).filter(Setting.key == "fit_score_threshold").first()
        alert_threshold = int(threshold_row.value) if threshold_row else 60
    finally:
        db.close()

    while True:
        # -- Phase 1 (short session, no network): pick a batch, resolve the CV
        # set, the depth and whatever text is already on the row. Jobs with no
        # text and no URL get their _skipped sentinel here. ------------------
        to_score = []     # (job_ref, cv_texts, depth, preloaded_text)
        needs_fetch = []  # (job_ref, cv_texts, depth, url)
        db = SessionLocal()
        try:
            q = db.query(Job).filter(
                (Job.cv_scores == None) | (Job.cv_scores == text("'{}'::jsonb")),
            )
            if status == "saved":
                q = q.filter(Job.saved == True)
            else:
                q = q.filter(Job.status == status)
                if auto_score_filter is not None:
                    q = q.filter(auto_score_filter)
            if attempted:
                q = q.filter(Job.id.notin_(list(attempted)))

            unscored = q.limit(batch_size).all()
            if not unscored:
                break

            logger.info(f"Analyzing batch of {len(unscored)} unscored jobs (total so far: {total_scored})")

            for job in unscored:
                attempted.add(job.id)
                company = _find_company_for_job(db, job)
                cv_texts = _get_resume_texts_for_company(db, company) if company else default_cv_texts

                if status == "saved":
                    depth = "full"  # Saved jobs always get full report
                elif company and company.auto_scoring_depth in ("light", "full"):
                    depth = company.auto_scoring_depth
                elif job.search_id:
                    search = db.query(Search).filter(Search.id == job.search_id).first()
                    if search and search.auto_scoring_depth in ("light", "full"):
                        depth = search.auto_scoring_depth
                    else:
                        depth = default_depth
                else:
                    depth = default_depth

                # Detached snapshot: the scorer only needs the id (LLM cost rows)
                # plus company/title for its log lines, and phases 2-3 run with
                # this session closed.
                job_ref = SimpleNamespace(id=job.id, company=job.company, title=job.title)

                # Pre-check for job text so a permanent "no JD" condition gets a
                # sentinel here, distinct from a transient LLM failure inside score_job_sync.
                preloaded_text = _job_text_from_row(job)
                if preloaded_text:
                    to_score.append((job_ref, cv_texts, depth, preloaded_text))
                elif job.url:
                    needs_fetch.append((job_ref, cv_texts, depth, job.url))
                else:
                    job.cv_scores = {"_skipped": "no_text_available"}
                    job.best_cv_score = None
                    total_scored += 1
            db.commit()  # persist sentinels
        finally:
            db.close()

        # -- Phase 1b: live page fetches, with no connection held -------------
        if needs_fetch:
            no_text_ids = []
            for (job_ref, cv_texts, depth, url) in needs_fetch:
                fetched = await _fetch_job_text(job_ref.id, url)
                if fetched:
                    to_score.append((job_ref, cv_texts, depth, fetched))
                else:
                    no_text_ids.append(job_ref.id)
                    total_scored += 1
            if no_text_ids:
                db = SessionLocal()
                try:
                    for j in db.query(Job).filter(Job.id.in_(no_text_ids)).all():
                        j.cv_scores = {"_skipped": "no_text_available"}
                        j.best_cv_score = None
                    db.commit()
                finally:
                    db.close()

        # -- Phase 2 (parallel): LLM calls, no session anywhere. Concurrency is
        # capped by the scoring gate. ----------------------------------------
        results = await asyncio.gather(
            *[score_job_sync(j, c, db=None, depth=d, preloaded_text=t)
              for (j, c, d, t) in to_score],
            return_exceptions=True,
        )

        # -- Phase 3 (short session): apply results. Alerts are collected here
        # and sent after the session closes -- Telegram is an HTTP round trip.
        alerts = []
        db = SessionLocal()
        try:
            ids = [jr.id for (jr, _c, _d, _t) in to_score]
            job_map = {}
            if ids:
                job_map = {j.id: j for j in db.query(Job).filter(Job.id.in_(ids)).all()}

            for (job_ref, cv_texts, depth, _t), result in zip(to_score, results):
                if isinstance(result, BaseException):
                    logger.warning(
                        f"Job {job_ref.id} ({job_ref.company} - {job_ref.title}): scoring raised "
                        f"{type(result).__name__}: {result} - transient, will retry next pass"
                    )
                    total_scored += 1
                    continue
                job = job_map.get(job_ref.id)
                if job is None:
                    logger.warning(f"Job {job_ref.id} disappeared mid-run - result dropped")
                    total_scored += 1
                    continue
                if result:
                    # Belt-and-braces: a null/non-dict scores here must degrade to a
                    # per-job retry, never crash the batch (and the whole scrape run).
                    scores = result.get("scores")
                    if not isinstance(scores, dict):
                        logger.warning(
                            f"Job {job.id} ({job.company} - {job.title}): result has "
                            f"invalid scores ({type(scores).__name__}) - skipping, will retry"
                        )
                        total_scored += 1
                        continue
                    job.cv_scores = scores
                    # Precompute max score for fast DB filtering
                    try:
                        _scores = job.cv_scores or {}
                        _numeric = [float(v) for v in _scores.values() if isinstance(v, (int, float))]
                        job.best_cv_score = max(_numeric) if _numeric else None
                    except (ValueError, TypeError):
                        job.best_cv_score = None
                    job.best_cv = result.get("best_cv", "")

                    # Store scoring report per CV (nested dict keyed by CV name)
                    if result.get("_scoring_report"):
                        report = result["_scoring_report"]
                        existing = dict(job.scoring_report or {})
                        # Migrate flat format to nested if needed
                        if existing and "summary" in existing:
                            old_cv = existing.pop("scored_with", job.best_cv or "Unknown")
                            existing = {old_cv: existing}
                        scored_cv_names = list(scores.keys())
                        cv_name = scored_cv_names[0] if len(scored_cv_names) == 1 else job.best_cv or scored_cv_names[0]
                        existing[cv_name] = report
                        job.scoring_report = existing

                    numeric_scores = [v for v in scores.values() if isinstance(v, (int, float))]
                    best_score = max(numeric_scores) if numeric_scores else 0
                    score_summary = ", ".join(f"{k}={v}" for k, v in scores.items())
                    logger.info(
                        f"Scored {job.company} - {job.title}: "
                        f"{score_summary}, Best={job.best_cv}"
                    )

                    # Check if should trigger Telegram alert (threshold hoisted above loop)
                    if best_score >= alert_threshold:
                        alerts.append((_alert_snapshot(job), best_score))
                else:
                    # Transient LLM failure: do NOT persist a _skipped sentinel, so
                    # the next scheduler pass retries this job.
                    logger.warning(
                        f"Job {job.id} ({job.company} - {job.title}): score_job_sync "
                        "returned None after pre-check passed - transient failure, "
                        "will retry next pass"
                    )

                total_scored += 1
            db.commit()  # one commit per batch
        finally:
            db.close()

        for snapshot, best_score in alerts:
            try:
                from backend.notifier.telegram import send_job_alert
                await send_job_alert({"job": snapshot, "best_score": best_score})
            except Exception as e:
                logger.error(f"Failed to send Telegram alert: {e}")

    logger.info(f"Analysis pipeline complete: {total_scored} jobs processed")

    db = SessionLocal()
    try:
        from backend.activity import log_activity
        log_activity("cv_score", f"Resume scoring complete: {total_scored} jobs processed", db=db)
        db.commit()
    finally:
        db.close()


async def score_single_job(job_id: str, cv_ids: list = None, depth: str = "full"):
    """Re-run CV analysis for a job, optionally against specific CV IDs.

    Sessions are opened and closed per phase: read → (live fetch) → LLM → write.
    No connection is held while the page fetch or the LLM call is awaited, so N
    queued scoring tasks cost N coroutines rather than N pooled connections.
    Returns a one-line summary stored as JobRun.result_summary.
    """
    from types import SimpleNamespace

    # ── Phase 1: Read job + CVs from DB, then release connection ──
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            logger.error(f"Job {job_id} not found")
            return "Job not found"

        job_title = job.title
        job_company = job.company
        job_url = job.url

        if cv_ids:
            # cv_ids may reference base Resumes, tailored Resumes, or the reserved
            # 'persona' id; no is_base filter — explicit IDs are the caller's responsibility.
            from backend.models.db import Resume
            cv_texts = {}
            resume_ids = [c for c in cv_ids if c != _PERSONA_KEY]
            if resume_ids:
                resumes = db.query(Resume).filter(Resume.id.in_(resume_ids)).order_by(Resume.id).all()
                # A single tailored resume is labeled "Tailored" so the frontend's tailored-link
                # handler picks it up; multiple in one batch fall back to Resume.name to avoid a dict-key collision.
                tailored_count = sum(1 for r in resumes if not r.is_base)
                for r in resumes:
                    text = _flatten_resume(r.json_data or {})
                    if not text:
                        continue
                    if r.is_base:
                        label = r.name
                    elif tailored_count == 1:
                        label = "Tailored"
                    else:
                        label = r.name  # disambiguate; loses the short-chip nicety, but no data loss
                    cv_texts[label] = text
            if _PERSONA_KEY in cv_ids:
                cv_texts.update(_get_persona_text(db))
        else:
            company = _find_company_for_job(db, job)
            cv_texts = _get_resume_texts_for_company(db, company) if company else (_get_default_resume(db) or _get_resume_texts(db))
        if not cv_texts:
            logger.warning(
                "score_single_job: empty cv_texts (job=%s, cv_ids=%r) — nothing to score against",
                job_id, cv_ids,
            )
            return "No resumes to score against"

        # Text already on the row; the live fetch (below) happens with no session.
        job_text = _job_text_from_row(job)
        job_ref = SimpleNamespace(id=job.id, company=job_company, title=job_title)
    finally:
        db.close()

    # ── Phase 1b: live page fetch, with the connection already released ──
    if not job_text:
        job_text = await _fetch_job_text(job_id, job_url)
    if not job_text:
        logger.warning(f"Job {job_id} has no text, skipping scoring")
        return "No job text to score"

    # ── Phase 2: LLM scoring (no DB connection held) ──
    result = await score_job_sync(job_ref, cv_texts, db=None, depth=depth, preloaded_text=job_text)
    if not result:
        return "Scoring failed"

    # ── Phase 3: Save results back to DB ──
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return "Job disappeared mid-run"

        # Defensive: .get's default doesn't catch an explicit "scores": null.
        new_scores = result.get("scores")
        if not isinstance(new_scores, dict):
            logger.warning(f"Job {job_id}: rescore result has invalid scores — not persisting")
            return "Malformed LLM response - not persisted"
        merged = dict(job.cv_scores or {})
        merged.update(new_scores)
        job.cv_scores = merged
        # Precompute max score for fast DB filtering (Task 2)
        try:
            _scores = job.cv_scores or {}
            _numeric = [float(v) for v in _scores.values() if isinstance(v, (int, float))]
            job.best_cv_score = max(_numeric) if _numeric else None
        except (ValueError, TypeError):
            job.best_cv_score = None

        numeric_merged = {k: v for k, v in merged.items() if isinstance(v, (int, float))}
        if numeric_merged:
            job.best_cv = max(numeric_merged, key=numeric_merged.get)
        else:
            job.best_cv = result.get("best_cv", "")

        if result.get("_scoring_report"):
            report = result["_scoring_report"]
            existing = dict(job.scoring_report or {})
            if existing and "summary" in existing:
                old_cv = existing.pop("scored_with", job.best_cv or "Unknown")
                existing = {old_cv: existing}
            scored_cv_names = list(new_scores.keys())
            cv_name = scored_cv_names[0] if len(scored_cv_names) == 1 else job.best_cv or scored_cv_names[0]
            existing[cv_name] = report
            job.scoring_report = existing

        db.commit()

        from backend.activity import log_activity
        numeric_new = [v for v in new_scores.values() if isinstance(v, (int, float))]
        best = max(numeric_new) if numeric_new else 0
        log_activity("cv_score", f"Scored job '{job_title}' at {job_company}: best={best}", company=job_company)

        # Returned string becomes JobRun.result_summary (Stats -> Run history).
        return (f"{job_title} - best {best}"
                + (f" ({job.best_cv})" if job.best_cv else "")
                + f", {depth}")
    finally:
        db.close()
