"""Phenom People ATS handler — POST to a custom API endpoint with a JSON payload.
Company URLs are stored as 'POST|{api_url}|{json_payload}' since Phenom has no public API; each company has its own endpoint and filter schema."""
import json
import logging
import re
from urllib.parse import urlparse

import httpx

from backend.scraper._shared.filters import _validate_job

logger = logging.getLogger("jobnavigator.scraper.ats.phenom")


def is_phenom(url: str) -> bool:
    return url.strip().upper().startswith("POST|")


def _parse_phenom_url(raw: str) -> tuple[str, dict]:
    """Parse 'POST|https://host/widgets|{json payload}' format."""
    parts = raw.strip().split("|", 2)
    endpoint = parts[1].strip()
    if len(parts) > 2:
        # Collapse runs of whitespace (from textarea line-wrapping) before parsing
        cleaned = re.sub(r'\s+', ' ', parts[2].strip())
        payload = json.loads(cleaned)
    else:
        payload = {}
    return endpoint, payload


# Phenom boards vary in which of these keys they populate, and the widget API
# needs a per-board URL, so this was not confirmed against a live board. Reading
# several keys keeps the handler at today's behaviour (no location) when a board
# carries none of them.
# "city" is absent on purpose: the composite branch below joins it with state
# and country, which reads better than the bare city name.
_LOCATION_KEYS = ("cityState", "cityStateCountry", "location")


def _location_of(job: dict) -> str | None:
    for key in _LOCATION_KEYS:
        value = job.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    city = job.get("city")
    state = job.get("state")
    country = job.get("country")
    parts = [p for p in (city, state, country) if isinstance(p, str) and p.strip()]
    return ", ".join(parts) or None


async def scrape(raw_url: str, debug: bool = False) -> list[dict] | tuple:
    """Fetch jobs from a Phenom People /widgets POST API."""
    endpoint, base_payload = _parse_phenom_url(raw_url)
    parsed = urlparse(endpoint)
    origin = f"{parsed.scheme}://{parsed.netloc}"

    base_payload["from"] = 0
    base_payload["size"] = 200
    base_payload.setdefault("jobs", True)
    ddo_key = base_payload.get("ddoKey", "refineSearch")
    base_payload.setdefault("ddoKey", ddo_key)

    logger.info(f"Phenom API: endpoint={endpoint} ddoKey={ddo_key}")
    logger.info(f"Phenom API: selected_fields={base_payload.get('selected_fields', 'NONE')}")

    jobs = []
    rejected = []
    offset = 0

    headers = {
        "Content-Type": "application/json",
        "Referer": f"{origin}/",
    }

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        while True:
            base_payload["from"] = offset
            resp = await client.post(endpoint, json=base_payload, headers=headers)
            data = json.loads(resp.text)

            rs = data.get(ddo_key, {})
            total = rs.get("totalHits", 0)
            job_list = rs.get("data", {}).get("jobs", [])

            if offset == 0:
                logger.info(f"Phenom API: totalHits={total}")

            if not job_list:
                break

            for j in job_list:
                title = j.get("title", "").strip()
                job_id = j.get("jobId", "")
                job_url = j.get("applyUrl") or f"{origin}/global/en/job/{job_id}"
                # Strip trailing /apply to get the job detail page
                if job_url.endswith("/apply"):
                    job_url = job_url[:-6]
                reason = _validate_job(title, job_url)
                if reason is None:
                    jobs.append({"title": title, "url": job_url,
                                 "location": _location_of(j)})
                elif debug:
                    rejected.append({"title": title, "url": job_url, "selector": "phenom_api", "reason": reason})

            offset += len(job_list)
            if offset >= total:
                break

    logger.info(f"Phenom API: fetched {len(jobs)} jobs from {endpoint}")
    if debug:
        return jobs, rejected
    return jobs
