"""LLM-based CV scorer — scores job vs all uploaded CV versions dynamically."""
import asyncio
import json
import logging
import time
from backend.analyzer.llm_client import call_llm
from backend.analyzer.llm_logger import log_llm_call
from backend.models.db import SessionLocal, Job, Setting

logger = logging.getLogger("jobnavigator.cv_scorer")

# ── Global scoring semaphore (limits concurrent LLM scoring jobs) ─────────
_scoring_semaphore: asyncio.Semaphore | None = None


def _get_scoring_semaphore() -> asyncio.Semaphore:
    """Lazy-init semaphore from DB setting. Created on first use (inside event loop)."""
    global _scoring_semaphore
    if _scoring_semaphore is None:
        db = SessionLocal()
        try:
            row = db.query(Setting).filter(Setting.key == "scoring_max_concurrent").first()
            try:
                limit = max(1, int(row.value)) if row and row.value else 5
            except (ValueError, TypeError):
                limit = 5
        finally:
            db.close()
        _scoring_semaphore = asyncio.Semaphore(limit)
        logger.info(f"Scoring semaphore initialized: max {limit} concurrent jobs")
    return _scoring_semaphore


def reset_scoring_semaphore():
    """Reset semaphore so next call re-reads the limit from DB. Called on settings change."""
    global _scoring_semaphore
    _scoring_semaphore = None


def _flatten_resume(json_data: dict) -> str:
    """Render a Resume.json_data dict (or Persona.resume_content — same shape) to plaintext
    for LLM scoring. Uses '## Section' headers so the LLM sees clear structure, and
    includes all six standard sections (header, summary, experience, skills, education,
    projects, publications) when present. Empty sections are omitted entirely.
    """
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
            # schema has location (no year); keep year as back-compat
            tail = edu.get("location") or edu.get("year") or ""
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
    """Return {'Persona': flattened_text} when the singleton persona has non-empty
    resume_content, else {}. Other persona nodes (contact, qa_bank, etc.) are
    NOT used for scoring — only resume_content."""
    from backend.models.db import Persona
    p = db.query(Persona).filter(Persona.id == 1).first()
    if not p:
        return {}
    text = _flatten_resume(p.resume_content or {})
    if not text:
        return {}
    return {_PERSONA_DISPLAY: text}


def _get_resume_texts(db) -> dict:
    """Return {Resume.name: flattened_text} for every base Resume + Persona (if populated).
    Persona always appears last. Replaces _get_cv_texts. Ordered by Resume.id for stable cache keys.
    """
    from backend.models.db import Resume
    out = {}
    for r in db.query(Resume).filter(Resume.is_base == True).order_by(Resume.id).all():
        text = _flatten_resume(r.json_data or {})
        if text:
            out[r.name] = text
    out.update(_get_persona_text(db))
    return out


def _get_default_resume(db) -> dict:
    """Return {Resume.name: flat_text} for the default Resume. Special id 'persona'
    returns persona text. Empty dict if not set or not found."""
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
    """Return resume texts for a company. Honors company.selected_resume_ids,
    which can mix Resume UUIDs with the special 'persona' key.
    Falls back to default; last resort all base resumes (+ persona if populated)."""
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


async def _get_job_text(job: Job, db=None) -> str | None:
    """Get job text from description, cached page, or live fetch (with caching).
    Returns text string or None if no text available.
    """
    # 1. Use description if available
    if job.description and len(job.description.strip()) > 50:
        return job.description.strip()

    # 2. Fall back to cached page text
    if job.cached_page_text and len(job.cached_page_text.strip()) > 50:
        logger.info(f"Job {job.id}: using cached_page_text (no description)")
        return job.cached_page_text.strip()

    # 3. Fetch live page, cache it, use text
    url = job.url
    if url and db:
        logger.info(f"Job {job.id}: no text available, fetching live page")
        try:
            from backend.api.routes_applications import _cache_job_page
            await _cache_job_page(str(job.id), url)
            # Re-read job to get cached text
            db.refresh(job)
            if job.cached_page_text and len(job.cached_page_text.strip()) > 50:
                return job.cached_page_text.strip()
        except Exception as e:
            logger.warning(f"Job {job.id}: live page fetch failed: {e}")

    return None


async def score_job_sync(job: Job, cv_texts: dict, db=None, depth="light", preloaded_text: str = None) -> dict:
    """Score a single job against all provided CV versions using LLM.
    Acquires the global scoring semaphore to limit concurrent LLM calls.
    Returns dict with scores and best_cv. depth='full' includes detailed report.
    """
    sem = _get_scoring_semaphore()
    async with sem:
        return await _score_job_inner(job, cv_texts, db, depth, preloaded_text)


async def _score_job_inner(job: Job, cv_texts: dict, db=None, depth="light", preloaded_text: str = None) -> dict:
    """Inner scoring logic (called under semaphore).

    Prompt is split into a cacheable prefix (rubric + CVs + schema) and a per-job suffix
    (just the JD). On Claude API this uses Anthropic prompt caching — subsequent calls
    with the same CV set hit the cache for ~10x cheaper input tokens.

    Return contract (important for rescoring):
    - dict with scores → success
    - ``None`` → no text / no CVs (intentional skip, caller may pre-check via
      ``_get_job_text`` / ``cv_texts`` before calling to distinguish) OR transient
      LLM failure (exception in ``call_llm``, JSON parse error).

    Callers that persist a ``_skipped`` sentinel so the job won't be retried MUST
    pre-check for empty ``cv_texts`` and missing job text *before* calling this
    function. A ``None`` return from inside ``call_llm`` MUST be treated as a
    transient failure so the scheduler can rescore on the next pass.
    """
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
        def _sv(k, d=""):
            r = settings_db.query(Setting).filter(Setting.key == k).first()
            return (r.value if r and r.value else d)
        # Scoring can override the Primary model (empty = use Primary). The Fallback
        # (llm_fallback_*) is applied inside call_llm regardless.
        provider_for_log = _sv("scoring_llm_provider") or _sv("llm_provider", "claude_api")
        model_for_log = _sv("scoring_llm_model") or _sv("llm_model", "claude-sonnet-5")
        scoring_api_key = _sv("scoring_llm_api_key") or _sv("llm_api_key")
        cache_row = settings_db.query(Setting).filter(Setting.key == "prompt_caching_enabled").first()
        caching_enabled = (cache_row.value if cache_row else "true").strip().lower() == "true"
    finally:
        if not db:
            settings_db.close()

    # Build CV sections dynamically
    cv_sections = []
    cv_names = list(cv_texts.keys())
    for i, (name, text) in enumerate(cv_texts.items(), 1):
        cv_sections.append(f"Resume Version {i} — {name}:\n{text}")

    # Replace CV_NAMES_HERE placeholder in output schema
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

        # Parse JSON — handle markdown wrapping and trailing commentary
        import re
        cleaned = text.strip()
        match = re.search(r'\{[\s\S]*\}', cleaned)
        if match:
            cleaned = match.group(0)
        result = json.loads(cleaned)

        # Validate the shape before returning success. A confused model can emit
        # {"scores": null} or a non-dict — .get("scores", {}) does NOT catch an
        # explicit null (the default only applies when the key is absent), and
        # callers do scores.values(). Treat malformed output as a transient
        # failure (return None) so the job is retried next pass instead of
        # crashing the whole analyze/scrape run.
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


def _find_company_for_job(db, job: Job):
    """Find the Company record matching a job's company name or alias (case-insensitive)."""
    from backend.models.db import find_company_by_name
    return find_company_by_name(db, job.company)


async def analyze_unscored_jobs(status: str = "saved"):
    """Score all unscored jobs against uploaded CVs. Processes in batches of 20 until done.
    status='saved' scores saved jobs; status='new' scores new jobs (only from auto_scoring_depth != 'off' entities).
    """
    db = SessionLocal()
    try:
        default_cv_texts = _get_default_resume(db) or _get_resume_texts(db)
        if not default_cv_texts:
            logger.warning("No CVs uploaded yet, skipping analysis pipeline")
            return

        from sqlalchemy import or_, text, func
        from backend.models.db import Search, Company as CompanyModel
        total_scored = 0
        batch_size = 20

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

        # Per-run constants — hoisted out of the per-job loop (were re-queried per job)
        default_depth_row = db.query(Setting).filter(Setting.key == "scoring_default_depth").first()
        default_depth = default_depth_row.value if default_depth_row and default_depth_row.value else "light"
        threshold_row = db.query(Setting).filter(Setting.key == "fit_score_threshold").first()
        alert_threshold = int(threshold_row.value) if threshold_row else 60

        while True:
            q = db.query(Job).filter(
                (Job.cv_scores == None) | (Job.cv_scores == text("'{}'::jsonb")),
            )
            if status == "saved":
                q = q.filter(Job.saved == True)
            else:
                q = q.filter(Job.status == status)
                if auto_score_filter is not None:
                    q = q.filter(auto_score_filter)

            unscored = q.limit(batch_size).all()

            if not unscored:
                break

            logger.info(f"Analyzing batch of {len(unscored)} unscored jobs (total so far: {total_scored})")

            # ── Phase 1 (sequential, shared session): resolve CV set, depth, and job
            # text per job; persist _skipped sentinels for jobs with no text.
            to_score = []  # (job, cv_texts, depth, preloaded_text)
            for job in unscored:
                # Look up company to get per-company CV selection
                company = _find_company_for_job(db, job)
                cv_texts = _get_resume_texts_for_company(db, company) if company else default_cv_texts

                # Determine depth based on auto_scoring_depth
                if status == "saved":
                    depth = "full"  # Saved jobs always get full report
                elif company and company.auto_scoring_depth in ("light", "full"):
                    depth = company.auto_scoring_depth
                elif job.search_id:
                    from backend.models.db import Search
                    search = db.query(Search).filter(Search.id == job.search_id).first()
                    if search and search.auto_scoring_depth in ("light", "full"):
                        depth = search.auto_scoring_depth
                    else:
                        depth = default_depth
                else:
                    depth = default_depth

                # Pre-check: does the job have any text available (description,
                # cached page, or live fetch)? If not, mark _skipped now — this is
                # a permanent condition (no JD to score against) so we persist a
                # sentinel to avoid re-processing on every pass.
                #
                # This pre-check is what distinguishes "intentional skip" from
                # "transient LLM failure" at the caller. If we skipped this check
                # and relied only on score_job_sync returning None, we'd also mark
                # LLM outages as _skipped, permanently preventing rescoring.
                preloaded_text = await _get_job_text(job, db)
                if not preloaded_text:
                    # Mark with sentinel so it won't match the unscored filter again.
                    # (LLM was not called — this is a true skip, not a transient failure.)
                    job.cv_scores = {"_skipped": "no_text_available"}
                    job.best_cv_score = None
                    total_scored += 1
                    continue
                to_score.append((job, cv_texts, depth, preloaded_text))
            db.commit()  # persist sentinels

            # ── Phase 2 (parallel): LLM calls. db=None — with preloaded_text the
            # inner scorer never touches the shared session (it opens its own
            # short-lived one for settings), so gather is session-safe. Actual
            # concurrency is capped by the scoring semaphore inside score_job_sync
            # (scoring_max_concurrent, default 5); previously this loop awaited
            # jobs one at a time, so the semaphore never saw >1.
            results = await asyncio.gather(
                *[score_job_sync(j, c, db=None, depth=d, preloaded_text=t)
                  for (j, c, d, t) in to_score],
                return_exceptions=True,
            )

            # ── Phase 3 (sequential, shared session): apply results + alerts.
            for (job, cv_texts, depth, _t), result in zip(to_score, results):
                if isinstance(result, BaseException):
                    logger.warning(
                        f"Job {job.id} ({job.company} - {job.title}): scoring raised "
                        f"{type(result).__name__}: {result} — transient, will retry next pass"
                    )
                    total_scored += 1
                    continue
                if result:
                    # Belt-and-braces: _score_job_inner validates this, but a
                    # null/non-dict scores here must degrade to a per-job retry,
                    # never crash the batch (and with it the whole scrape run).
                    scores = result.get("scores")
                    if not isinstance(scores, dict):
                        logger.warning(
                            f"Job {job.id} ({job.company} - {job.title}): result has "
                            f"invalid scores ({type(scores).__name__}) — skipping, will retry"
                        )
                        total_scored += 1
                        continue
                    job.cv_scores = scores
                    # Precompute max score for fast DB filtering (Task 2)
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
                        try:
                            from backend.notifier.telegram import send_job_alert
                            await send_job_alert({
                                "job": job,
                                "best_score": best_score,
                            })
                        except Exception as e:
                            logger.error(f"Failed to send Telegram alert: {e}")
                else:
                    # Transient LLM failure (exception or JSON parse error).
                    # Do NOT persist a _skipped sentinel — that would permanently
                    # mark the job as un-rescoreable. Leave cv_scores as-is so the
                    # next scheduler pass retries this job.
                    logger.warning(
                        f"Job {job.id} ({job.company} - {job.title}): score_job_sync "
                        "returned None after pre-check passed — transient failure, "
                        "will retry next pass"
                    )

                total_scored += 1
            db.commit()  # one commit per batch (was per job)

        logger.info(f"Analysis pipeline complete: {total_scored} jobs processed")

        from backend.activity import log_activity
        log_activity("cv_score", f"Resume scoring complete: {total_scored} jobs processed", db=db)
        db.commit()

    finally:
        db.close()


async def score_single_job(job_id: str, cv_ids: list = None, depth: str = "full"):
    """Re-run CV analysis for a specific job. Optionally score only against specific CV IDs.
    DB sessions are opened and closed around each phase to avoid holding connections during LLM calls.
    """
    # ── Phase 1: Read job + CVs from DB, then release connection ──
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            logger.error(f"Job {job_id} not found")
            return

        job_title = job.title
        job_company = job.company

        if cv_ids:
            # cv_ids may reference base Resumes, tailored Resumes (is_base=False), or
            # the reserved 'persona' magic id (a virtual Resume backed by Persona.resume_content).
            # No is_base filter — explicit IDs are the caller's responsibility.
            from backend.models.db import Resume
            cv_texts = {}
            resume_ids = [c for c in cv_ids if c != _PERSONA_KEY]
            if resume_ids:
                resumes = db.query(Resume).filter(Resume.id.in_(resume_ids)).order_by(Resume.id).all()
                # Single tailored (is_base=False) → label "Tailored" so the frontend's
                # tailored-link handler picks it up and the chip stays short. Multiple
                # tailored in one batch (rare) → fall back to Resume.name to avoid
                # silent dict-key collision dropping all but one. Same convention as
                # POST /resumes/{id}/score-check.
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
            return

        # Pre-fetch job text (may do live page fetch + cache, needs DB)
        job_text = await _get_job_text(job, db)
        if not job_text:
            logger.warning(f"Job {job_id} has no text, skipping scoring")
            return
    finally:
        db.close()

    # ── Phase 2: LLM scoring (no DB connection held) ──
    result = await score_job_sync(job, cv_texts, db=None, depth=depth, preloaded_text=job_text)
    if not result:
        return

    # ── Phase 3: Save results back to DB ──
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return

        # Defensive: .get's default doesn't catch an explicit "scores": null.
        new_scores = result.get("scores")
        if not isinstance(new_scores, dict):
            logger.warning(f"Job {job_id}: rescore result has invalid scores — not persisting")
            return
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

    finally:
        db.close()
