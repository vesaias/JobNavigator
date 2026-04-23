"""Gmail API OAuth2 client — polls for recruiter responses."""
import asyncio
import base64
import json
import logging
from datetime import datetime, timezone

import httpx

from backend.config import GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN
from backend.models.db import SessionLocal, Setting, Application
from backend.email_monitor.response_parser import classify_email

logger = logging.getLogger("jobnavigator.gmail")

GMAIL_API_BASE = "https://www.googleapis.com/gmail/v1"
TOKEN_URL = "https://oauth2.googleapis.com/token"


async def _get_access_token() -> str:
    """Exchange refresh token for access token."""
    if not GMAIL_REFRESH_TOKEN:
        logger.warning("GMAIL_REFRESH_TOKEN not set, skipping email check")
        return ""

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(TOKEN_URL, data={
            "client_id": GMAIL_CLIENT_ID,
            "client_secret": GMAIL_CLIENT_SECRET,
            "refresh_token": GMAIL_REFRESH_TOKEN,
            "grant_type": "refresh_token",
        })

        if resp.status_code != 200:
            logger.error(f"Gmail token refresh failed: {resp.text}")
            return ""

        return resp.json().get("access_token", "")



def _extract_email_domain(from_header: str) -> str:
    """Extract domain from email From header."""
    if "<" in from_header and ">" in from_header:
        email = from_header.split("<")[1].split(">")[0]
    else:
        email = from_header
    parts = email.split("@")
    return parts[1].lower() if len(parts) > 1 else ""


def _load_processed_ids(db) -> set:
    """Load previously processed Gmail message IDs from settings."""
    row = db.query(Setting).filter(Setting.key == "gmail_processed_ids").first()
    if row and row.value:
        try:
            return set(json.loads(row.value))
        except (json.JSONDecodeError, TypeError):
            pass
    return set()


def _save_processed_ids(db, processed_ids: set):
    """Save processed Gmail message IDs to settings (keep last 500)."""
    id_list = list(processed_ids)[-500:]  # Keep only the most recent 500
    row = db.query(Setting).filter(Setting.key == "gmail_processed_ids").first()
    if row:
        row.value = json.dumps(id_list)
    else:
        db.add(Setting(key="gmail_processed_ids", value=json.dumps(id_list),
                        description="Processed Gmail message IDs for dedup (auto-managed)"))
    db.commit()


def _build_gmail_query(db) -> str:
    """Build Gmail search query from settings — sender patterns + subject keywords + exclusions."""
    import json as _json

    # Sender patterns (domains, prefixes, specific addresses — all in one list)
    senders_row = db.query(Setting).filter(Setting.key == "email_gmail_query_senders").first()
    sender_patterns = []
    if senders_row and senders_row.value:
        try:
            sender_patterns = _json.loads(senders_row.value)
        except _json.JSONDecodeError:
            pass
    sender_parts = []
    for s in sender_patterns:
        if s.startswith('@') or '.' in s and '@' not in s:
            sender_parts.append(f'from:{s}' if s.startswith('@') else f'from:@{s}')
        else:
            sender_parts.append(f'from:"{s}"')

    # Subject keywords from settings
    subjects_row = db.query(Setting).filter(Setting.key == "email_gmail_query_subjects").first()
    subject_terms = []
    if subjects_row and subjects_row.value:
        try:
            subject_terms = _json.loads(subjects_row.value)
        except _json.JSONDecodeError:
            pass
    subject_parts = [f'subject:"{s}"' for s in subject_terms]

    # Exclusions from settings
    exclusions_row = db.query(Setting).filter(Setting.key == "email_gmail_query_exclusions").first()
    exclusion_terms = []
    if exclusions_row and exclusions_row.value:
        try:
            exclusion_terms = _json.loads(exclusions_row.value)
        except _json.JSONDecodeError:
            pass
    exclusion_parts = [f'-subject:"{e}"' for e in exclusion_terms]

    # Combine: newer_than:3d ((from:senders) OR (subject:keywords)) -exclusions
    from_block = " OR ".join(sender_parts)
    subject_block = " OR ".join(subject_parts)

    # `in:anywhere` forces Gmail to search all mail — including Trash and Spam.
    # The list endpoint's includeSpamTrash flag alone is not enough; Gmail still
    # filters some Trash hits out of the result set unless the query itself
    # opts into them. Paired with params.includeSpamTrash=True this guarantees
    # auto-archived rejection emails still get classified.
    parts = ["in:anywhere", "newer_than:3d"]
    if from_block and subject_block:
        parts.append(f"(({from_block}) OR ({subject_block}))")
    elif from_block:
        parts.append(f"({from_block})")
    elif subject_block:
        parts.append(f"({subject_block})")

    if exclusion_parts:
        parts.append(" ".join(exclusion_parts))

    return " ".join(parts)


def _get_active_apps_for_llm(db) -> list:
    """Build numbered list of active applications for LLM prompt."""
    active_statuses = ["applied", "screening", "phone_screen", "interview", "final_round"]
    apps = db.query(Application).filter(Application.status.in_(active_statuses)).all()
    result = []
    for i, app in enumerate(apps, 1):
        job = app.job
        if not job:
            continue
        applied_at = app.applied_at.strftime("%Y-%m-%d") if app.applied_at else "unknown"
        result.append({
            "index": i,
            "id": app.id,
            "company": job.company or "Unknown",
            "title": job.title or "Unknown",
            "status": app.status,
            "applied_at": applied_at,
        })
    return result


def _apply_email_to_app(db, matched_app, class_type: str, body: str, subject: str):
    """Apply phrase-classified email result to an application (existing logic extracted)."""
    snippet = body[:200] if body else subject[:200]
    matched_app.last_email_received = datetime.now(timezone.utc)
    matched_app.last_email_snippet = snippet

    from backend.models.db import record_transition, utcnow
    if class_type == "positive":
        if matched_app.status == "applied":
            record_transition(matched_app, "screening", "email")
    elif class_type == "rejection":
        record_transition(matched_app, "rejected", "email")

    matched_app.updated_at = utcnow()
    db.commit()

    logger.info(f"Email classified as '{class_type}' for application {matched_app.id}")


def _apply_llm_result_to_app(db, matched_app, llm_result: dict, body: str, subject: str):
    """Apply LLM classification result to an application."""
    snippet = body[:200] if body else subject[:200]
    matched_app.last_email_received = datetime.now(timezone.utc)
    matched_app.last_email_snippet = snippet

    from backend.models.db import record_transition, utcnow
    new_status = llm_result["status"]

    # Only transition forward, never backward
    status_order = {"applied": 0, "screening": 1, "phone_screen": 2, "interview": 3, "final_round": 4, "offer": 5, "rejected": 99}
    current_rank = status_order.get(matched_app.status, -1)
    new_rank = status_order.get(new_status, -1)

    if new_rank > current_rank:
        record_transition(matched_app, new_status, "email")

    matched_app.updated_at = utcnow()
    db.commit()

    logger.info(
        f"Email LLM: '{new_status}' (confidence {llm_result['confidence']}) "
        f"for application {matched_app.id} — {llm_result.get('summary', '')}"
    )


async def check_emails():
    """Poll Gmail for recruiter responses and update application statuses."""
    access_token = await _get_access_token()
    if not access_token:
        return

    db = SessionLocal()
    try:
        # Load previously processed message IDs
        processed_ids = _load_processed_ids(db)

        # Build improved Gmail search query from settings
        query = _build_gmail_query(db)

        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient(timeout=30) as client:
            # List messages matching query
            resp = await client.get(
                f"{GMAIL_API_BASE}/users/me/messages",
                params={"q": query, "maxResults": 20, "includeSpamTrash": True},
                headers=headers,
            )

            if resp.status_code != 200:
                logger.error(f"Gmail list messages failed: {resp.text}")
                return

            messages = resp.json().get("messages", [])
            logger.info(f"Gmail: found {len(messages)} messages from known domains")

            llm_calls_this_run = 0
            for msg_ref in messages:
                msg_id = msg_ref["id"]

                # Skip already-processed messages
                if msg_id in processed_ids:
                    continue

                # Get full message
                msg_resp = await client.get(
                    f"{GMAIL_API_BASE}/users/me/messages/{msg_id}",
                    params={"format": "full"},
                    headers=headers,
                )

                if msg_resp.status_code != 200:
                    continue

                msg_data = msg_resp.json()
                headers_list = msg_data.get("payload", {}).get("headers", [])

                # Extract headers
                from_header = ""
                subject = ""
                for h in headers_list:
                    if h["name"].lower() == "from":
                        from_header = h["value"]
                    elif h["name"].lower() == "subject":
                        subject = h["value"]

                # Extract body text
                body = _extract_body(msg_data.get("payload", {}))

                sender_domain = _extract_email_domain(from_header)

                # Classify the email
                classification = classify_email(subject, body)
                class_type = classification["classification"]

                if class_type == "auto_reply":
                    processed_ids.add(msg_id)
                    continue

                # High-confidence phrase match — use existing matching logic
                if classification["confidence"] >= 0.8 and class_type in ("positive", "rejection"):
                    matched_app = _match_email_to_application(db, from_header, subject, body, sender_domain)
                    if matched_app:
                        _apply_email_to_app(db, matched_app, class_type, body, subject)
                    processed_ids.add(msg_id)
                    continue

                # Low confidence or ambiguous — try LLM pass 2 (max 5 per run)
                from backend.email_monitor.response_parser import classify_email_llm
                if llm_calls_this_run >= 5:
                    logger.info("LLM call limit reached (5), deferring remaining ambiguous emails to next run")
                    continue
                active_apps = _get_active_apps_for_llm(db)
                llm_result = await classify_email_llm(from_header, subject, body, active_apps)
                llm_calls_this_run += 1
                await asyncio.sleep(2)  # Rate limit between LLM calls

                if llm_result:
                    # Check confidence threshold
                    threshold_row = db.query(Setting).filter(Setting.key == "email_llm_confidence_threshold").first()
                    threshold = int(threshold_row.value) if threshold_row and threshold_row.value else 70

                    if llm_result["confidence"] >= threshold and llm_result["status"] != "no_change":
                        # Find matched application
                        match_idx = llm_result.get("match_index")
                        matched_app = None
                        if match_idx and 1 <= match_idx <= len(active_apps):
                            app_info = active_apps[match_idx - 1]
                            matched_app = db.query(Application).get(app_info["id"])

                        if matched_app:
                            _apply_llm_result_to_app(db, matched_app, llm_result, body, subject)

                        from backend.activity import log_activity
                        log_activity("email", f"LLM classified email: {llm_result['summary']} (confidence: {llm_result['confidence']})", db=db)
                    else:
                        from backend.activity import log_activity
                        log_activity("email", f"LLM low confidence ({llm_result['confidence']}): {llm_result.get('summary', 'no summary')}", db=db)

                processed_ids.add(msg_id)

        # Save updated processed IDs
        _save_processed_ids(db, processed_ids)

        from backend.activity import log_activity
        log_activity("email", f"Email check: {len(messages)} messages found from known domains", db=db)
        db.commit()

    except Exception as e:
        logger.error(f"Email check failed: {e}")
        from backend.activity import log_activity
        log_activity("email", f"Email check failed: {e}")
        raise  # Let tracked_run / caller mark the JobRun as failed
    finally:
        db.close()


def _extract_body(payload: dict) -> str:
    """Extract body from Gmail message payload. Prefers text/plain, falls back to text/html → stripped text."""
    plain = _extract_mime(payload, "text/plain")
    if plain:
        return plain
    html = _extract_mime(payload, "text/html")
    if html:
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            for tag in soup(["script", "style", "head"]):
                tag.decompose()
            return soup.get_text(separator="\n", strip=True)
        except Exception:
            import re
            return re.sub(r'<[^>]+>', '', html).strip()
    return ""


def _extract_mime(payload: dict, mime_type: str) -> str:
    """Recursively extract content of a specific MIME type from Gmail payload."""
    if payload.get("mimeType") == mime_type:
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

    for part in payload.get("parts", []):
        if part.get("mimeType") == mime_type:
            data = part.get("body", {}).get("data", "")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        result = _extract_mime(part, mime_type)
        if result:
            return result

    return ""


def _match_email_to_application(db, from_header: str, subject: str, body: str, sender_domain: str):
    """Try to match an email to an existing application."""
    # Get active applications
    active_statuses = ["applied", "screening", "phone_screen", "interview", "final_round"]
    apps = db.query(Application).filter(Application.status.in_(active_statuses)).all()

    subject_lower = subject.lower()
    from_lower = from_header.lower()
    body_lower = body.lower()
    sender_slug = sender_domain.replace(".com", "").replace(".", "")

    for app in apps:
        job = app.job
        if not job:
            continue

        # Match by company name in subject, from header, or body
        company_lower = (job.company or "").lower()
        if company_lower and (
            company_lower in subject_lower or
            company_lower in from_lower or
            company_lower in body_lower or
            sender_slug in company_lower.replace(" ", "").lower()
        ):
            return app

        # Match by job title in subject or body
        title_lower = (job.title or "").lower()
        if title_lower and (
            title_lower in subject_lower or
            title_lower in body_lower
        ):
            return app

    return None
