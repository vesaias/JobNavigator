"""Classify emails as positive/rejection/auto-reply/ambiguous."""
import logging

logger = logging.getLogger("jobnavigator.email_parser")

POSITIVE_PHRASES = [
    "would like to schedule",
    "next steps",
    "move forward",
    "like to invite",
    "schedule a call",
    "schedule an interview",
    "pleased to inform",
    "we'd like to",
    "we would like to",
    "preliminary phone screen",
    "set up a time",
    "availability for",
    "connect with you",
    "meet with",
    "excited to",
]

REJECTION_PHRASES = [
    "unfortunately",
    "not moving forward",
    "other candidates",
    "position has been filled",
    "decided not to",
    "not a match",
    "pursuing other",
    "regret to inform",
    "will not be moving",
    "after careful consideration",
    "competitive pool",
    "decided to go with",
    "not proceed",
    "no longer being considered",
]

AUTO_REPLY_PHRASES = [
    "thank you for applying",
    "we received your application",
    "application has been received",
    "thank you for your interest",
    "confirming receipt",
    "application received",
    "auto-reply",
    "do not reply",
    "noreply",
    "no-reply",
]


def classify_email(subject: str, body: str) -> dict:
    """Classify an email response.
    Returns dict with classification and confidence.
    """
    combined = f"{subject} {body}".lower()

    # Count all signals first
    positive_count = sum(1 for p in POSITIVE_PHRASES if p in combined)
    rejection_count = sum(1 for p in REJECTION_PHRASES if p in combined)
    auto_reply_count = sum(1 for p in AUTO_REPLY_PHRASES if p in combined)

    # Rejection/positive take priority over auto-reply (rejections often contain "thank you for your interest")
    if rejection_count > 0 and positive_count == 0:
        confidence = min(0.5 + rejection_count * 0.15, 0.95)
        return {"classification": "rejection", "confidence": confidence}

    if positive_count > 0 and rejection_count == 0:
        confidence = min(0.5 + positive_count * 0.15, 0.95)
        return {"classification": "positive", "confidence": confidence}

    if positive_count > 0 and rejection_count > 0:
        return {"classification": "ambiguous", "confidence": 0.4}

    # Auto-reply only if no rejection/positive signals
    if auto_reply_count > 0:
        return {"classification": "auto_reply", "confidence": 0.9}

    return {"classification": "ambiguous", "confidence": 0.2}


async def classify_email_llm(from_header: str, subject: str, body: str, active_apps: list) -> dict | None:
    """Classify an ambiguous email using LLM. Returns dict with match_index, status, confidence, summary or None on failure.

    active_apps: list of dicts with keys: index (1-based), id, company, title, status, applied_at
    """
    from backend.models.db import SessionLocal, Setting

    db = SessionLocal()
    try:
        # Check if LLM email classification is enabled
        enabled_row = db.query(Setting).filter(Setting.key == "email_llm_enabled").first()
        if not enabled_row or enabled_row.value != "true":
            return None

        # Load prompt template
        prompt_row = db.query(Setting).filter(Setting.key == "email_llm_prompt").first()
        if not prompt_row or not prompt_row.value:
            logger.warning("email_llm_prompt setting is empty, skipping LLM classification")
            return None
        prompt_template = prompt_row.value
    finally:
        db.close()

    # Build numbered applications list
    app_lines = []
    for app in active_apps:
        app_lines.append(f"{app['index']}. {app['company']} — {app['title']} ({app['status']} since {app['applied_at']})")
    applications_text = "\n".join(app_lines) if app_lines else "(no active applications)"

    # Build prompt from template
    truncated_body = body[:1500] if body else ""
    prompt = prompt_template.replace("{applications}", applications_text)
    prompt = prompt.replace("{from}", from_header)
    prompt = prompt.replace("{subject}", subject)
    prompt = prompt.replace("{body}", truncated_body)

    system = "You classify recruiter emails and match them to job applications. Return only valid JSON."

    try:
        from backend.analyzer.llm_client import call_email_llm
        import json
        raw = await call_email_llm(prompt, system, max_tokens=150)

        # Extract JSON from response — handles markdown fences and trailing commentary
        import re
        text = raw.strip()
        # Try to extract JSON object between { and }
        match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if match:
            text = match.group(0)
        else:
            # Fallback: strip markdown fences
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if "```" in text:
                text = text[:text.index("```")]
            text = text.strip()

        result = json.loads(text)

        # Validate required fields
        if not isinstance(result.get("confidence"), (int, float)):
            logger.warning(f"Email LLM: missing/invalid confidence in response: {raw[:200]}")
            return None
        if result.get("status") not in ("interview", "offer", "rejected", "no_change"):
            logger.warning(f"Email LLM: invalid status '{result.get('status')}' in response")
            result["status"] = "no_change"

        # Validate match_index
        match_idx = result.get("match_index")
        if match_idx is not None:
            if not isinstance(match_idx, int) or match_idx < 1 or match_idx > len(active_apps):
                logger.warning(f"Email LLM: invalid match_index {match_idx}, setting to null")
                result["match_index"] = None

        return result

    except json.JSONDecodeError as e:
        logger.warning(f"Email LLM: failed to parse JSON: {e}. Raw: {raw[:300]}")
        return None
    except Exception as e:
        logger.warning(f"Email LLM classification failed: {e}")
        return None
