"""Gmail API OAuth2 client — polls for recruiter responses."""
import asyncio
import base64
import json
import logging
import re
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
    id_list = list(processed_ids)[-500:]
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

    subjects_row = db.query(Setting).filter(Setting.key == "email_gmail_query_subjects").first()
    subject_terms = []
    if subjects_row and subjects_row.value:
        try:
            subject_terms = _json.loads(subjects_row.value)
        except _json.JSONDecodeError:
            pass
    subject_parts = [f'subject:"{s}"' for s in subject_terms]

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

    # `in:anywhere` forces Gmail to search all mail incl. Trash/Spam — the list endpoint's
    # includeSpamTrash flag alone isn't enough to surface auto-archived rejection emails.
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
    active_statuses = ["applied", "interview"]
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
        # Positive recruiter response on an applied row -> interview.
        if matched_app.status == "applied":
            record_transition(matched_app, "interview", "email")
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
    status_order = {"applied": 0, "interview": 1, "offer": 2, "rejected": 99}
    current_rank = status_order.get(matched_app.status, -1)
    new_rank = status_order.get(new_status, -1)

    if new_rank > current_rank:
        record_transition(matched_app, new_status, "email")

    matched_app.updated_at = utcnow()
    db.commit()

    logger.info(
        f"Email LLM: '{new_status}' (confidence {llm_result['confidence']}) "
        f"for application {matched_app.id}"
    )


async def check_emails():
    """Poll Gmail for recruiter responses and update application statuses."""
    access_token = await _get_access_token()
    if not access_token:
        return

    db = SessionLocal()
    try:
        processed_ids = _load_processed_ids(db)
        query = _build_gmail_query(db)

        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient(timeout=30) as client:
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

                if msg_id in processed_ids:
                    continue

                msg_resp = await client.get(
                    f"{GMAIL_API_BASE}/users/me/messages/{msg_id}",
                    params={"format": "full"},
                    headers=headers,
                )

                if msg_resp.status_code != 200:
                    continue

                msg_data = msg_resp.json()
                headers_list = msg_data.get("payload", {}).get("headers", [])

                from_header = ""
                subject = ""
                for h in headers_list:
                    if h["name"].lower() == "from":
                        from_header = h["value"]
                    elif h["name"].lower() == "subject":
                        subject = h["value"]

                body = _extract_body(msg_data.get("payload", {}))

                sender_domain = _extract_email_domain(from_header)

                classification = classify_email(subject, body)
                class_type = classification["classification"]

                if class_type == "auto_reply":
                    processed_ids.add(msg_id)
                    continue

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
                    threshold_row = db.query(Setting).filter(Setting.key == "email_llm_confidence_threshold").first()
                    threshold = int(threshold_row.value) if threshold_row and threshold_row.value else 70

                    if llm_result["confidence"] >= threshold and llm_result["status"] != "no_change":
                        match_idx = llm_result.get("match_index")
                        matched_app = None
                        matched_company = ""
                        if match_idx and 1 <= match_idx <= len(active_apps):
                            app_info = active_apps[match_idx - 1]
                            matched_company = app_info.get("company", "")
                            matched_app = db.query(Application).get(app_info["id"])

                        # Guards against the LLM force-matching an email onto the wrong company's
                        # application (e.g. an Amazon email onto a Kpler application).
                        if matched_app and not _email_matches_company(
                            matched_company, from_header, subject, body, sender_domain
                        ):
                            logger.warning(
                                f"Email LLM matched app {matched_app.id} ({matched_company!r}) but "
                                f"sender {sender_domain!r} doesn't correspond — skipping status change"
                            )
                            matched_app = None

                        if matched_app:
                            _apply_llm_result_to_app(db, matched_app, llm_result, body, subject)

                        # Status + confidence only — a summary paraphrasing the recruiter's email
                        # body is not something we want persisted in activity_log.
                        from backend.activity import log_activity
                        log_activity(
                            "email",
                            f"LLM classified email → {llm_result.get('status', '?')} "
                            f"(confidence: {llm_result['confidence']})",
                            db=db,
                        )
                    else:
                        from backend.activity import log_activity
                        log_activity(
                            "email",
                            f"LLM low confidence ({llm_result['confidence']}): status={llm_result.get('status', '?')}",
                            db=db,
                        )

                processed_ids.add(msg_id)

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


# Common legal/entity suffixes and filler words dropped when deriving a company's
# identifying tokens, so "Kpler Technologies Inc." matches on "kpler".
_COMPANY_SUFFIXES = {
    "inc", "llc", "ltd", "limited", "gmbh", "ag", "sa", "plc", "co", "corp",
    "corporation", "company", "technologies", "technology", "labs", "group",
    "holdings", "international", "the",
}


def _company_tokens(company: str) -> list:
    """Identifying tokens for a company name (drop entity suffixes + very short tokens)."""
    toks = [
        t for t in re.findall(r"[a-z0-9]+", (company or "").lower())
        if t not in _COMPANY_SUFFIXES and len(t) >= 3
    ]
    if not toks:  # name was all suffixes / short tokens — fall back to whatever we have
        toks = [t for t in re.findall(r"[a-z0-9]+", (company or "").lower()) if t]
    return toks


def _email_matches_company(company: str, from_header: str, subject: str,
                           body: str, sender_domain: str) -> bool:
    """True iff an email plausibly belongs to `company`, matching on From/domain/subject (authoritative)
    or the full company name in the body (weak fallback); job title is deliberately never used."""
    if not company or not company.strip():
        return False
    sender_text = f"{from_header or ''} {subject or ''}".lower()
    domain_slug = re.sub(r"[^a-z0-9]", "", (sender_domain or "").lower())
    for t in _company_tokens(company):
        # Word-boundary match in the human-readable sender/subject (so "Box" does not
        # match inside "inbox"), or a substring match in the collapsed sender domain.
        if re.search(rf"\b{re.escape(t)}\b", sender_text):
            return True
        if len(t) >= 4 and t in domain_slug:
            return True
    full = company.lower().strip()
    return full in (body or "").lower()


def _match_email_to_application(db, from_header: str, subject: str, body: str, sender_domain: str):
    """Match an email to an active application anchored on the sender; a body-only company
    match is used only as a fallback after every app is checked for a stronger sender match."""
    active_statuses = ["applied", "interview"]
    apps = db.query(Application).filter(Application.status.in_(active_statuses)).all()

    body_lower = (body or "").lower()
    body_fallback = None
    for app in apps:
        job = app.job
        if not job:
            continue
        company = job.company or ""
        # Strong: the company is named in the sender / subject.
        if _email_matches_company(company, from_header, subject, "", sender_domain):
            return app
        # Weak: the full company name appears only in the body — remember it, but keep
        # scanning in case a later app is a stronger (sender-based) match.
        if body_fallback is None and company.strip() and company.lower().strip() in body_lower:
            body_fallback = app
    return body_fallback
