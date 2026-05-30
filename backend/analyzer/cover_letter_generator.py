"""Cover-letter generation — builds the prompt and calls the LLM.

Voice comes from the paired resume (already in the candidate's voice) plus a
selectable voice preset; the persona `preferences` node supplies the "why this
role/company" beat. writing_samples are intentionally NOT used (retired).

Prompt-caching split (Anthropic): the cacheable PREFIX = flattened resume +
persona preferences + output schema (stable per resume), the per-job SUFFIX =
JD + voice + length. So switching voice/length and regenerating reuses the
cached prefix.
"""
import json
import logging
import re

from backend.analyzer.cv_scorer import _flatten_resume
from backend.analyzer.llm_client import call_cover_letter_llm
from backend.models.db import Setting

logger = logging.getLogger("jobnavigator.cover_letter")

_LENGTH_INSTRUCTIONS = {
    "concise": "Keep it tight — 3 short paragraphs, ~200 words total.",
    "standard": "Standard length — 3 paragraphs, ~300 words total.",
    "detailed": "Fuller — 3-4 paragraphs, ~400 words, more proof points.",
}


def resolve_voice_instruction(db, voice_id: str | None) -> tuple[str, str]:
    """Return (voice_id, instruction) for the given preset id.

    Falls back to cover_letter_default_voice, then to the first preset, then to a
    neutral instruction. Returns the resolved id so callers can persist it.
    """
    presets = []
    row = db.query(Setting).filter(Setting.key == "cover_letter_voice_presets").first()
    if row and row.value:
        try:
            presets = json.loads(row.value)
        except (ValueError, TypeError):
            presets = []

    if not voice_id:
        d = db.query(Setting).filter(Setting.key == "cover_letter_default_voice").first()
        voice_id = (d.value if d and d.value else "") or None

    by_id = {p.get("id"): p for p in presets if isinstance(p, dict)}
    if voice_id and voice_id in by_id:
        return voice_id, by_id[voice_id].get("instruction", "")
    if presets:
        first = presets[0]
        return first.get("id", ""), first.get("instruction", "")
    return "", "Professional, concise, concrete. No corporate filler."


def build_cover_letter_prompt(resume_data: dict, preferences: dict, jd_text: str,
                              voice_instruction: str, length: str,
                              prompt_template: str) -> tuple[str, str]:
    """Return (cached_prefix, suffix_prompt).

    cached_prefix = resume + preferences + schema (stable per resume).
    suffix        = the editable prompt with JD/voice/length filled in.
    """
    resume_text = _flatten_resume(resume_data or {})
    pref_text = ""
    if preferences:
        try:
            pref_text = json.dumps(preferences, indent=2)
        except (TypeError, ValueError):
            pref_text = str(preferences)

    cached_prefix = (
        "You will write a cover letter. Use ONLY the facts in this candidate "
        "resume and persona preferences — never invent employers, titles, "
        "metrics, or skills.\n\n"
        "=== CANDIDATE RESUME ===\n" + resume_text + "\n\n"
        "=== PERSONA PREFERENCES (what the candidate values) ===\n" + (pref_text or "(none)")
    )

    length_instruction = _LENGTH_INSTRUCTIONS.get(length, _LENGTH_INSTRUCTIONS["standard"])
    suffix = (
        prompt_template
        .replace("{voice_instruction}", voice_instruction or "Professional and concise.")
        .replace("{length_instruction}", length_instruction)
        .replace("{job_description}", (jd_text or "")[:6000])
    )
    return cached_prefix, suffix


def parse_cover_letter_response(raw: str) -> dict:
    """Extract the {greeting, body_paragraphs[], closing, signature} JSON."""
    text = (raw or "").strip()
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        text = match.group(0)
    data = json.loads(text)
    # Normalize shape
    return {
        "greeting": (data.get("greeting") or "Dear Hiring Team,").strip(),
        "body_paragraphs": [str(p).strip() for p in (data.get("body_paragraphs") or []) if str(p).strip()],
        "closing": (data.get("closing") or "Sincerely,").strip(),
        "signature": (data.get("signature") or "").strip(),
    }


async def generate_cover_letter_body(resume_data: dict, preferences: dict, jd_text: str,
                                     voice_instruction: str, length: str,
                                     prompt_template: str) -> dict:
    """Call the LLM and return the parsed body dict. Caching enabled via prefix."""
    cached_prefix, suffix = build_cover_letter_prompt(
        resume_data, preferences, jd_text, voice_instruction, length, prompt_template
    )
    system = (
        "You are an expert cover-letter writer. Write a genuine, specific letter "
        "grounded strictly in the candidate's resume and the job description. "
        "Never fabricate facts. Output only the requested JSON."
    )
    resp = await call_cover_letter_llm(suffix, system, max_tokens=1500, cached_prefix=cached_prefix)
    parsed = parse_cover_letter_response(resp["text"])
    parsed["_usage"] = resp.get("usage", {})
    return parsed
