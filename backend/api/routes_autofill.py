"""Application-question autofill: generate an answer from persona + qa_bank."""
import json as _json
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from backend.models.db import SessionLocal, Setting, Persona
from backend.analyzer.llm_client import call_autofill_llm, call_autofill_llm_stream
from backend.analyzer.llm_logger import track_llm_call
from backend.autofill_schema import ANSWER_SCHEMA, project_answers

logger = logging.getLogger("jobnavigator.autofill")
router = APIRouter(prefix="/autofill", tags=["autofill"])


def _flatten_persona(p: Persona) -> str:
    parts = []
    for label, node in (("Contact", p.contact), ("Work authorization", p.work_auth),
                        ("Preferences", p.preferences), ("Resume content", p.resume_content)):
        if node:
            parts.append(f"{label}:\n{_json.dumps(node, indent=2)}")
    return "\n\n".join(parts) if parts else "(empty)"


def _qa_pair(entry) -> tuple:
    """Normalise one qa_bank entry to (question, answer).

    Canonical shape is {"question": ..., "answer": ...} — what POST /persona/qa-bank
    writes and what the Persona editor saves. Hand-written banks also used a
    single-key map {"<question>": "<answer>"}; those silently flattened to blank
    Q/A pairs, so the whole bank vanished from the prompt. Accept both.
    """
    if not isinstance(entry, dict):
        return "", ""
    if "question" in entry or "answer" in entry:
        return str(entry.get("question") or ""), str(entry.get("answer") or "")
    for k, v in entry.items():
        return str(k or ""), str(v or "")
    return "", ""


def _flatten_qa_bank(bank) -> str:
    if not bank:
        return "(empty)"
    pairs = [_qa_pair(e) for e in bank]
    pairs = [(q, a) for q, a in pairs if q or a]
    if not pairs:
        return "(empty)"
    return "\n\n".join(f"Q: {q}\nA: {a}" for q, a in pairs)


def _setting(db, key, default=""):
    row = db.query(Setting).filter(Setting.key == key).first()
    return row.value if row and row.value is not None else default


def _json_setting(db, key, default):
    try:
        return _json.loads(_setting(db, key, "") or "")
    except ValueError:
        return default


@router.get("/config")
def autofill_config():
    """Serve everything the extension needs to fill structured fields:
    the projected fixed answers, the matching dictionaries, and the schema."""
    db = SessionLocal()
    try:
        p = db.query(Persona).filter(Persona.id == 1).first()
        persona = {
            "contact": (p.contact if p else None) or {},
            "work_auth": (p.work_auth if p else None) or {},
            "demographics": (p.demographics if p else None) or {},
            "compensation": (p.compensation if p else None) or {},
            "preferences": (p.preferences if p else None) or {},
        }
        return {
            "answers": project_answers(persona),
            "field_patterns": _json_setting(db, "autofill_field_patterns", {}),
            "option_synonyms": _json_setting(db, "autofill_option_synonyms", {}),
            "schema": ANSWER_SCHEMA,
            # One source of truth: the Persona's own "prefer not to answer"
            # checkbox. autofill_schema already fills unset demographics with
            # "decline" from the same flag; this carries it to the extension so
            # it can pick a decline option on questions the Persona has no field
            # for at all.
            "decline_self_id": bool((persona.get("demographics") or {}).get("decline_demographics")),
        }
    finally:
        db.close()


@router.post("/answer")
async def autofill_answer(body: dict):
    question = (body.get("question") or "").strip()
    if not question:
        raise HTTPException(400, "question is required")
    company = (body.get("company") or "").strip() or "(unknown company)"
    position = (body.get("position") or "").strip() or "(unknown role)"

    db = SessionLocal()
    try:
        persona = db.query(Persona).filter(Persona.id == 1).first()
        len_row = db.query(Setting).filter(Setting.key == "autofill_default_length").first()
        default_len = int(len_row.value) if len_row and (len_row.value or "").isdigit() else 120
        tmpl_row = db.query(Setting).filter(Setting.key == "autofill_prompt").first()
        if not tmpl_row or not (tmpl_row.value or "").strip():
            raise HTTPException(500, "autofill_prompt setting is empty")
        template = tmpl_row.value
        persona_txt = _flatten_persona(persona) if persona else "(no persona)"
        qa_txt = _flatten_qa_bank(persona.qa_bank if persona else [])

        # Resolve provider/model for logging with the very resolver
        # call_autofill_llm dispatches through — one source of truth (R2-H-15).
        from backend.analyzer.llm_client import resolve_llm_config
        _cfg = resolve_llm_config("autofill", db=db)
        provider, model = _cfg["provider"], _cfg["model"]
    finally:
        db.close()

    max_chars = body.get("max_chars")
    max_chars = int(max_chars) if isinstance(max_chars, (int, str)) and str(max_chars).isdigit() else default_len

    # Stable prefix (persona + bank + instructions) is cacheable; the per-question
    # suffix (company/position/question) is not. Split at the first {company}
    # placeholder so the model sees each part exactly once: [cached_prefix, suffix].
    if "{company}" in template:
        before, after = template.split("{company}", 1)
        suffix_template = "{company}" + after
    else:
        before, suffix_template = "", template

    cached_prefix = (before
                     .replace("{persona}", persona_txt)
                     .replace("{qa_bank}", qa_txt)
                     .replace("{max_chars}", str(max_chars))) or None

    suffix = (suffix_template
              .replace("{company}", company)
              .replace("{position}", position)
              .replace("{question}", question)
              .replace("{max_chars}", str(max_chars)))
    system = "You write concise, truthful first-person job-application answers grounded only in the provided profile."

    # token budget: char budget (~4 chars/token) + headroom for the JSON wrapper
    # and any discarded preamble. Kept tight so the answer respects max_chars.
    max_tokens = max(96, min(900, max_chars // 4 + 96))
    try:
        async with track_llm_call("autofill", provider, model) as tracker:
            resp = await call_autofill_llm(suffix, system, max_tokens=max_tokens,
                                           cached_prefix=cached_prefix)
            tracker.record(resp)
        raw = (resp.get("text") or "").strip()
        # The model returns {"answer": "..."}; extract it so any leaked reasoning /
        # preamble outside the JSON is discarded. Fall back to the raw text.
        answer = raw
        try:
            import json as _json
            import re as _re
            m = _re.search(r'\{[\s\S]*\}', raw)
            if m:
                parsed = _json.loads(m.group(0))
                if isinstance(parsed, dict) and parsed.get("answer"):
                    answer = str(parsed["answer"])
        except Exception:
            pass
        answer = answer.strip().strip('"')
    except Exception as e:
        logger.error(f"autofill generation failed: {e}")
        raise HTTPException(502, "autofill generation failed") from e
    return {"answer": answer}


@router.post("/answer/stream")
async def autofill_answer_stream(body: dict):
    """Server-Sent Events variant of /answer: streams the drafted answer as
    plain-text chunks so the extension can render it into the field live.
    Unlike /answer this asks for prose (no JSON wrapper) so tokens render
    directly. Shares the persona/qa_bank prompt-cache prefix with /answer."""
    question = (body.get("question") or "").strip()
    if not question:
        raise HTTPException(400, "question is required")
    company = (body.get("company") or "").strip() or "(unknown company)"
    position = (body.get("position") or "").strip() or "(unknown role)"

    db = SessionLocal()
    try:
        persona = db.query(Persona).filter(Persona.id == 1).first()
        len_row = db.query(Setting).filter(Setting.key == "autofill_default_length").first()
        default_len = int(len_row.value) if len_row and (len_row.value or "").isdigit() else 120
        persona_txt = _flatten_persona(persona) if persona else "(no persona)"
        qa_txt = _flatten_qa_bank(persona.qa_bank if persona else [])
    finally:
        db.close()

    max_chars = body.get("max_chars")
    max_chars = int(max_chars) if isinstance(max_chars, (int, str)) and str(max_chars).isdigit() else default_len

    # Build a dedicated PLAIN-PROSE prefix rather than reusing the /answer template
    # (which steers the model to a JSON {"answer": ...} wrapper — that leaked into
    # the streamed field). Persona + qa_bank is stable per user, so it still caches
    # across refinements/length changes.
    cached_prefix = (
        "You are the candidate, writing concise first-person answers to job-application "
        "questions. Use ONLY facts from the profile and reusable Q&A bank below — never "
        "invent employers, titles, metrics, or skills.\n\n"
        f"CANDIDATE PROFILE:\n{persona_txt}\n\n"
        f"REUSABLE Q&A BANK:\n{qa_txt}\n"
    )

    # Refinements: the ordered list of change requests the candidate has applied to
    # this answer ("shorter", "mention my fintech work"). Sent in full so they
    # compound; appended to the per-question suffix so the persona/qa_bank cache
    # prefix is untouched.
    refinements = body.get("refinements") or []
    refine_block = ""
    if isinstance(refinements, list):
        lines = "\n".join(f"- {str(r).strip()}" for r in refinements if str(r).strip())
        if lines:
            refine_block = f"Apply these changes the candidate requested, in order:\n{lines}\n\n"

    suffix = (
        f"Company: {company}\nRole: {position}\n"
        f"Question: {question}\n\n"
        f"{refine_block}"
        f"Write a first-person answer in AT MOST {max_chars} characters — this is a "
        f"hard limit, not a target. Be concise and finish a sentence before reaching it. "
        f"Output only the answer text — no JSON, no quotes, no preamble, no labels."
    )
    system = ("You write concise, truthful first-person job-application answers grounded "
              "only in the provided profile. Respect the character limit strictly. "
              "Output only the answer as plain prose.")
    # ~4 chars/token, so cap tokens near the char budget (+ small buffer) instead of
    # the old 256-token floor that let a 250-char ask balloon past 500 chars.
    max_tokens = max(48, min(800, max_chars // 4 + 24))

    async def _events():
        try:
            async for chunk in call_autofill_llm_stream(suffix, system, max_tokens=max_tokens,
                                                        cached_prefix=cached_prefix):
                if chunk:
                    yield f"data: {_json.dumps({'delta': chunk})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"autofill stream failed: {e}")
            yield f"data: {_json.dumps({'error': 'autofill generation failed'})}\n\n"

    return StreamingResponse(_events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
