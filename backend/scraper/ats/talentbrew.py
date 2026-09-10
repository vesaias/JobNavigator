"""TalentBrew ATS handler — AJAX endpoint for legacy TalentBrew-hosted career pages."""
import html as _html
import logging
import re
from urllib.parse import urlparse

import httpx

from backend.scraper._shared.filters import _validate_job

logger = logging.getLogger("jobnavigator.scraper.ats.talentbrew")

# The place sits inside the same anchor as the title:
# <a href="/job/..."><h2>Title</h2><span class="job-location">Mountain View, California</span></a>
_LOCATION_SPAN = re.compile(
    r'<span[^>]*class="[^"]*job-location[^"]*"[^>]*>(.*?)</span>',
    re.DOTALL | re.I)


def _locations_in(block: str) -> list[str]:
    """Every `job-location` span inside one job's markup, in board order."""
    out: list[str] = []
    for match in _LOCATION_SPAN.finditer(block):
        text = _html.unescape(re.sub(r"<[^>]+>", " ", match.group(1)))
        text = re.sub(r"\s+", " ", text).strip()
        if text and text not in out:
            out.append(text)
    return out


def is_talentbrew(url: str) -> bool:
    """Check if URL is a TalentBrew AJAX search-results endpoint (BlackRock, Intuit, etc.)."""
    return "/search-jobs/results?" in url.lower()


async def scrape(url: str, debug: bool = False) -> list[dict] | tuple:
    """Fetch TalentBrew AJAX search-results URL via HTTP and parse job links from JSON."""
    import json
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    jobs = []
    rejected = []
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(url, headers={"X-Requested-With": "XMLHttpRequest"})

    data = json.loads(resp.text)
    results_html = data.get("results", "")

    for m in re.finditer(r'<a\s[^>]*href="(/job/[^"]+)"[^>]*>(.*?)</a>', results_html, re.DOTALL):
        href, raw_title = m.group(1), m.group(2)
        title = re.sub(r'<[^>]+>', '', raw_title).strip()
        if '\n' in title:
            title = title.split('\n')[0].strip()
        full_url = f"{origin}{href}"
        reason = _validate_job(title, full_url)
        if reason is None:
            places = _locations_in(raw_title)
            jobs.append({"title": title, "url": full_url,
                         "location": places[0] if places else None,
                         "locations": places})
        elif debug:
            rejected.append({"title": title, "url": full_url, "selector": "talentbrew_ajax", "reason": reason})

    logger.info(f"TalentBrew AJAX: parsed {len(jobs)} valid jobs from {url[:80]}...")
    if debug:
        return jobs, rejected
    return jobs
