"""Application-question autofill: generate an answer from persona + qa_bank."""
import json as _json
import logging
import re as _re
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


def _trim_to_chars(text: str, max_chars: int):
    """Cut text to at most max_chars on a sentence or word boundary, enforced here since the model treats a character limit as a suggestion; returns (text, trimmed)."""
    if not text or max_chars <= 0 or len(text) <= max_chars:
        return text, False
    cut = text[:max_chars]
    # A sentence end is only a good cut if it isn't throwing most of the answer
    # away — otherwise a single early "e.g." would strand the reader mid-thought.
    end = max(cut.rfind("."), cut.rfind("!"), cut.rfind("?"))
    if end >= int(max_chars * 0.6):
        return cut[:end + 1].rstrip(), True
    space = cut.rfind(" ")
    if space > 0:
        cut = cut[:space]
    return cut.rstrip().rstrip(",;:-—–").rstrip(), True


_FENCE_OPEN = _re.compile(r"^```[A-Za-z0-9_+-]*[^\S\r\n]*\r?\n?")


def _strip_code_fences(text: str) -> str:
    """Drop a ```json … ``` wrapper the model put around its JSON."""
    t = (text or "").strip()
    if not t.startswith("```"):
        return t
    t = _FENCE_OPEN.sub("", t, count=1).strip()
    if t.endswith("```"):
        t = t[:-3].rstrip()
    return t


def _first_json_object(text: str):
    r"""Return the first balanced {...} in text (string/escape aware), or None; a naive brace regex would span to the last "}" in the reply and break on trailing prose."""
    depth = 0
    start = -1
    in_str = False
    esc = False
    for i, ch in enumerate(text or ""):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth:
                depth -= 1
                if depth == 0 and start >= 0:
                    return text[start:i + 1]
    return None


def _last_unescaped_quote(body: str) -> int:
    """Index of the last `"` that is not itself escaped, or -1; a plain rfind would land on an escaped quote and cut a truncated answer short."""
    i = len(body) - 1
    while i >= 0:
        if body[i] == '"':
            back = 0
            j = i - 1
            while j >= 0 and body[j] == "\\":
                back += 1
                j -= 1
            if back % 2 == 0:
                return i
        i -= 1
    return -1


def _unescape_json_fragment(body: str) -> str:
    """Decode a JSON string body that has lost its closing quote."""
    try:
        return _json.loads('"' + body + '"')
    except ValueError:
        pass
    # A truncated fragment can end mid-escape ("…\") — drop that and retry.
    trimmed = body[:-1] if body.endswith("\\") else body
    try:
        return _json.loads('"' + trimmed + '"')
    except ValueError:
        return (trimmed.replace("\n", "\n").replace("\t", "\t")
                       .replace('\\"', '"').replace("\\\\", "\\"))


def _extract_answer(raw: str) -> str:
    """Pull the answer text out of the model's reply, trying a fenced JSON envelope, the whole reply, the first balanced object, a hand-salvaged truncated envelope, then plain prose, so a malformed wrapper is never pasted into a real application form; returns "" when nothing usable is left."""
    text = _strip_code_fences(raw)
    if not text:
        return ""
    for candidate in (text, _first_json_object(text)):
        if not candidate:
            continue
        try:
            parsed = _json.loads(candidate)
        except ValueError:
            continue
        if isinstance(parsed, dict):
            value = parsed.get("answer")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                value = str(value)
            if isinstance(value, str) and value.strip():
                return value.strip()
        elif isinstance(parsed, str) and parsed.strip():
            return parsed.strip()
    # Truncated envelope: the opening `{"answer": "` is there, the closing quote
    # and brace are not (the model hit its token budget mid-sentence).
    m = _re.search(r'["\']answer["\']\s*:\s*"', text)
    if m:
        body = text[m.end():]
        end = _last_unescaped_quote(body)
        if end > 0:
            body = body[:end]
        body = _unescape_json_fragment(body.rstrip()).strip()
        if body and not body.startswith("{"):
            return body
    # Plain prose is fine; a leftover JSON envelope never is.
    text = text.strip().strip('"').strip()
    return "" if text.startswith("{") else text


def _qa_pair(entry) -> tuple:
    """Normalise one qa_bank entry to (question, answer); accepts both the canonical {"question","answer"} shape written by POST /persona/qa-bank and a legacy single-key {"<question>": "<answer>"} map."""
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
    """Serve everything the extension needs to fill structured fields: the projected fixed answers, matching dictionaries, and the schema."""
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
            # Mirrors the Persona's "prefer not to answer" checkbox so the extension
            # can decline questions the Persona has no field for at all.
            "decline_self_id": bool((persona.get("demographics") or {}).get("decline_demographics")),
        }
    finally:
        db.close()


def _build_autofill_prompt(body: dict, *, want_provider: bool = False) -> dict:
    """Shared prompt construction for both /answer and /answer/stream.

    Both variants must honour the editable `autofill_prompt` setting — the
    streaming path used to build its own hardcoded prefix, so editing the prompt
    in Settings had no effect on the answers the extension actually renders
    (R4-T1-22). Returns the cacheable prefix, the per-question suffix and the
    resolved character budget.
    """
    question = (body.get("question") or "").strip()
    if not question:
        raise HTTPException(400, "question is required")
    company = (body.get("company") or "").strip() or "(unknown company)"
    position = (body.get("position") or "").strip() or "(unknown role)"

    provider = model = None
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

        if want_provider:
            # Resolve provider/model for logging with the same resolver
            # call_autofill_llm dispatches through, so both stay in sync.
            from backend.analyzer.llm_client import resolve_llm_config
            _cfg = resolve_llm_config("autofill", db=db)
            provider, model = _cfg["provider"], _cfg["model"]
    finally:
        db.close()

    max_chars = body.get("max_chars")
    max_chars = int(max_chars) if isinstance(max_chars, (int, str)) and str(max_chars).isdigit() else default_len

    # Stable prefix (persona+bank+instructions) is cacheable; the per-question suffix
    # isn't. Split at the first {company} placeholder so the model sees each part once.
    if "{company}" in template:
        before, after = template.split("{company}", 1)
        suffix_template = "{company}" + after
    else:
        before, suffix_template = "", template

    # Every placeholder is substituted in BOTH halves, independently of where the
    # split fell. Filling only some of them per half meant a template written
    # without {company} put the whole thing in the suffix and never expanded
    # {persona} / {qa_bank} — the model was handed the literal braces and answered
    # with no profile at all (R4-E2E-04). Sequential .replace, not str.format_map:
    # the shipped template contains a literal JSON envelope ({"answer": …}) that
    # any format() call would choke on.
    values = {
        "{persona}": persona_txt,
        "{qa_bank}": qa_txt,
        "{max_chars}": str(max_chars),
        "{company}": company,
        "{position}": position,
        "{question}": question,
    }

    def _fill(chunk: str) -> str:
        for token, value in values.items():
            chunk = chunk.replace(token, value)
        return chunk

    cached_prefix = _fill(before) or None
    suffix = _fill(suffix_template)
    return {"cached_prefix": cached_prefix, "suffix": suffix,
            "max_chars": max_chars, "provider": provider, "model": model}


@router.post("/answer")
async def autofill_answer(body: dict):
    built = _build_autofill_prompt(body, want_provider=True)
    cached_prefix, suffix = built["cached_prefix"], built["suffix"]
    max_chars = built["max_chars"]
    provider, model = built["provider"], built["model"]
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
        # Extract the answer from the model's {"answer": ...} wrapper, discarding any
        # leaked preamble; an unsalvageable envelope is a failed generation (502)
        # rather than raw JSON pasted into the user's application form.
        answer = _extract_answer(raw)
        if not answer:
            raise ValueError(f"unusable model output: {raw[:160]!r}")
    except Exception as e:
        logger.error(f"autofill generation failed: {e}")
        raise HTTPException(502, "autofill generation failed") from e
    # The length the user picked is a contract, not a hint.
    answer, trimmed = _trim_to_chars(answer, max_chars)
    return {"answer": answer, "trimmed": trimmed, "max_chars": max_chars}


@router.post("/answer/stream")
async def autofill_answer_stream(body: dict):
    """SSE variant of /answer that streams the drafted answer as plain-text chunks (no JSON wrapper) so the extension can render it into the field live, sharing the persona/qa_bank cache prefix with /answer."""
    # Same editable `autofill_prompt` template as /answer, so what the user edits
    # in Settings governs the variant the extension actually streams (R4-T1-22).
    built = _build_autofill_prompt(body)
    cached_prefix = built["cached_prefix"]
    max_chars = built["max_chars"]

    # Refinements: ordered change requests already applied ("shorter", "mention
    # fintech work"), appended to the suffix so the cache prefix stays untouched.
    refinements = body.get("refinements") or []
    refine_block = ""
    if isinstance(refinements, list):
        lines = "\n".join(f"- {str(r).strip()}" for r in refinements if str(r).strip())
        if lines:
            refine_block = f"\n\nApply these changes the candidate requested, in order:\n{lines}"

    # The template steers toward the {"answer": …} envelope /answer parses; this
    # path renders straight into a form field, so the envelope is suppressed here
    # rather than by forking the whole prompt.
    suffix = (
        f"{built['suffix']}{refine_block}\n\n"
        f"Write a first-person answer in AT MOST {max_chars} characters — this is a "
        f"hard limit, not a target. Be concise and finish a sentence before reaching it. "
        f"Output only the answer text — no JSON, no quotes, no preamble, no labels."
    )
    system = ("You write concise, truthful first-person job-application answers grounded "
              "only in the provided profile. Respect the character limit strictly. "
              "Output only the answer as plain prose.")
    # ~4 chars/token, so cap tokens near the char budget plus a small buffer.
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
