"""ATS-specific job description fetchers.

_fetch_description_ats is a dispatcher that tries each supported ATS's description
API (Oracle HCM ById, Workday JSON, Lever, Greenhouse, etc.) before falling back to
generic HTML extraction via _fetch_job_description.

During Phase 2 of the refactor this module still imports some helpers from
playwright_scraper (e.g. _oracle_hcm_host, _parse_workday_url, _LOCALE_PATH_RE).
These imports will be updated in Tasks 7-15 as each ATS module is created.
"""
import asyncio
import json
import logging
import re
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from backend.scraper._shared.browser import _USER_AGENT
from backend.scraper._shared.urls import host_matches as _host_matches

logger = logging.getLogger("jobnavigator.scraper.ats.descriptions")


async def _fetch_job_description(url: str) -> str | None:
    """Fetch a job page and extract plaintext description.
    Uses ATS-specific APIs for Oracle HCM, Workday, Lever, Greenhouse;
    falls back to generic HTML extraction for everything else.
    """
    # Try ATS-specific fetchers first (SPA pages won't work with plain HTTP)
    try:
        desc = await _fetch_description_ats(url)
        if desc:
            return desc
    except Exception as e:
        logger.debug(f"ATS description fetch failed for {url}: {e}")

    # Generic HTML fallback
    try:
        from bs4 import BeautifulSoup
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": _USER_AGENT})
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup.find_all(["script", "style", "nav", "footer", "header", "noscript", "svg", "img"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)[:30_000]
            if len(text) < 100:
                return None
            # Detect SPA garbage: JSON config blobs from JS-rendered pages
            import re
            # Check first 500 non-title chars for JSON object start
            body = text[text.index('\n'):] if '\n' in text[:200] else text
            body_start = body.lstrip()[:500]
            if body_start.startswith('{') or body_start.startswith('['):
                logger.debug(f"Rejected JSON blob description from {url}")
                return None
            # Also reject if text has too many JSON structural chars
            json_like = len(re.findall(r'[{}"\[\]]', text))
            if json_like > len(text) * 0.10:
                logger.debug(f"Rejected config-heavy description from {url} ({json_like}/{len(text)} JSON chars)")
                return None
            return text
    except Exception as e:
        logger.debug(f"Failed to fetch job description from {url}: {e}")
        return None


async def _fetch_description_ats(url: str) -> str | None:
    """Try ATS-specific APIs to get job description. Returns plaintext or None."""
    import json
    from bs4 import BeautifulSoup
    from urllib.parse import urlparse as _urlparse

    # Lazy imports for helpers still in playwright_scraper.py (avoid circular imports).
    # These will move into ats/ modules in Tasks 7-15.
    from backend.scraper.playwright_scraper import (
        _oracle_hcm_host, _parse_workday_url, _LOCALE_PATH_RE,
    )

    parsed = _urlparse(url)

    # ── Oracle HCM: /sites/{site}/job/{id} ──
    # Detail API: ById finder with quoted Id (%22 = ")
    if _oracle_hcm_host(url) and "/job/" in parsed.path:
        api_host = _oracle_hcm_host(url)
        api_origin = f"https://{api_host}"
        path_parts = parsed.path.split("/")
        site = job_id = ""
        for i, p in enumerate(path_parts):
            if p == "sites" and i + 1 < len(path_parts):
                site = path_parts[i + 1]
            if p == "job" and i + 1 < len(path_parts):
                job_id = path_parts[i + 1]
        if job_id:
            finder = f"ById;Id=%22{job_id}%22,siteNumber={site}" if site else f"ById;Id=%22{job_id}%22"
            api_url = (
                f"{api_origin}/hcmRestApi/resources/latest/recruitingCEJobRequisitionDetails"
                f"?expand=all&onlyData=true&finder={finder}"
            )
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(api_url)
                if resp.status_code == 200:
                    data = json.loads(resp.text)
                    items = data.get("items", [])
                    if items:
                        req = items[0]
                        parts = []
                        for field in ("ExternalDescriptionStr", "CorporateDescriptionStr",
                                      "ExternalResponsibilitiesStr", "ExternalQualificationsStr",
                                      "OrganizationDescriptionStr"):
                            val = req.get(field)
                            if val and val.strip():
                                soup = BeautifulSoup(val, "html.parser")
                                text = soup.get_text(separator="\n", strip=True)
                                if text:
                                    parts.append(text)
                        if parts:
                            return "\n\n".join(parts)[:30_000]
        return None

    # ── Workday: myworkdayjobs.com/{site}/job/{slug}/{id} ──
    if _host_matches(url, "myworkdayjobs.com"):
        origin, company_slug, site, _ = _parse_workday_url(url)
        # Extract externalPath from URL: everything after /{site}
        path_parts = [p for p in parsed.path.strip("/").split("/") if p]
        ext_path = ""
        found_site = False
        for part in path_parts:
            if _LOCALE_PATH_RE.match(part):
                continue
            if not found_site:
                found_site = True  # first non-locale part is the site
                continue
            ext_path += "/" + part
        if company_slug and site and ext_path:
            api_url = f"{origin}/wday/cxs/{company_slug}/{site}{ext_path}"
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(api_url, headers={"Accept": "application/json"})
                if resp.status_code == 200:
                    data = json.loads(resp.text)
                    info = data.get("jobPostingInfo", {})
                    desc_html = info.get("jobDescription", "")
                    if desc_html:
                        soup = BeautifulSoup(desc_html, "html.parser")
                        text = soup.get_text(separator="\n", strip=True)
                        if len(text) >= 50:
                            return text[:30_000]
        return None

    # ── Eightfold: {company}.eightfold.ai/careers/job/{id} or custom domains using Eightfold ──
    # Known custom domains: apply.careers.microsoft.com, paypal.eightfold.ai, etc.
    # API: GET https://{domain}/api/apply/v2/jobs/{id} → JSON with job_description (HTML)
    eightfold_job_id = None
    if _host_matches(url, "eightfold.ai") and "/job/" in parsed.path:
        eightfold_job_id = parsed.path.rstrip("/").split("/")[-1]
    elif _host_matches(url, "apply.careers.microsoft.com") and "/job/" in parsed.path:
        eightfold_job_id = parsed.path.rstrip("/").split("/")[-1]
    if eightfold_job_id:
        api_url = f"{parsed.scheme}://{parsed.hostname}/api/apply/v2/jobs/{eightfold_job_id}"
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(api_url, headers={"Accept": "application/json", "User-Agent": _USER_AGENT})
                if resp.status_code == 200:
                    data = json.loads(resp.text)
                    desc_html = data.get("job_description", "")
                    if desc_html:
                        soup = BeautifulSoup(desc_html, "html.parser")
                        text = soup.get_text(separator="\n", strip=True)
                        if len(text) >= 50:
                            logger.debug(f"Eightfold API description for {url}: {len(text)} chars")
                            return text[:30_000]
        except Exception as e:
            logger.debug(f"Eightfold API failed for {url}: {e}")

    # ── Apple: jobs.apple.com/en-us/details/{id}/... ──
    if _host_matches(url, "jobs.apple.com") and "/details/" in url:
        import re as _re
        m = _re.search(r'/details/(\d+)', url)
        if m:
            apple_job_id = m.group(1)
            api_url = f"https://jobs.apple.com/api/v1/jobDetails/{apple_job_id}"
            try:
                async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                    resp = await client.get(api_url, headers={"Accept": "application/json", "User-Agent": _USER_AGENT})
                    if resp.status_code == 200:
                        data = json.loads(resp.text).get("res", {})
                        parts = []
                        for field in ("jobSummary", "description", "responsibilities", "minimumQualifications", "preferredQualifications"):
                            val = data.get(field, "")
                            if val:
                                parts.append(val)
                        # Extract salary from postingPostLocationData compensation footer
                        ppld = data.get("postingPostLocationData", {})
                        for locale_data in ppld.values():
                            for loc_data in locale_data.values():
                                footer = (loc_data.get("postingSupplementFooter") or {}).get("content", "")
                                if footer and "$" in footer:
                                    clean = re.sub(r'<[^>]+>', ' ', footer).strip()
                                    parts.append(clean)
                                    break
                            else:
                                continue
                            break
                        text = "\n\n".join(parts)
                        if len(text) >= 50:
                            logger.debug(f"Apple API description for {url}: {len(text)} chars")
                            return text[:30_000]
            except Exception as e:
                logger.debug(f"Apple API failed for {url}: {e}")
        return None

    # ── Visa: corporate.visa.com/en/jobs/{refNumber} ──
    if _host_matches(url, "visa.com") and "/jobs/" in url:
        ref_match = re.search(r'/jobs/(REF\w+)', url)
        if ref_match:
            ref_number = ref_match.group(1)
            try:
                api_url = f"https://search.visa.com/CAREERS/careers/job?refNumber={ref_number}"
                async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                    resp = await client.get(api_url, headers={"User-Agent": "Mozilla/5.0"})
                    if resp.status_code == 200:
                        data = json.loads(resp.text)
                        items = data.get("jobDetails", [])
                        if items:
                            item = items[0]
                            parts = []
                            for field in ("jobDescription", "qualifications", "additionalInformation"):
                                val = item.get(field, "")
                                if val and len(val) > 20:
                                    soup = BeautifulSoup(val, "html.parser")
                                    parts.append(soup.get_text(separator="\n", strip=True))
                            desc = "\n\n".join(parts)
                            if len(desc) >= 50:
                                logger.debug(f"Visa API description for {url}: {len(desc)} chars")
                                return desc[:30_000]
            except Exception as e:
                logger.debug(f"Visa API failed for {url}: {e}")
            return None

    # ── Uber Careers: uber.com/careers/list/{id} ──
    if "uber.com/careers/" in url.lower():
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(url, headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                })
                if resp.status_code == 200:
                    import html as _html
                    ld_match = re.search(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', resp.text, re.DOTALL)
                    if ld_match:
                        ld_data = json.loads(ld_match.group(1))
                        if ld_data.get("description"):
                            desc_html = _html.unescape(ld_data["description"])
                            soup = BeautifulSoup(desc_html, "html.parser")
                            text = soup.get_text(separator="\n", strip=True)
                            if len(text) >= 50:
                                logger.debug(f"Uber JSON-LD description for {url}: {len(text)} chars")
                                return text[:30_000]
        except Exception as e:
            logger.debug(f"Uber description failed for {url}: {e}")
        return None

    # ── Meta Careers: metacareers.com/v2/jobs/{id} ──
    if _host_matches(url, "metacareers.com") and ("/jobs/" in url or "/job_details/" in url):
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
                if resp.status_code == 200:
                    parts = []
                    for field in ("description", "responsibilities", "qualifications"):
                        m = re.search(rf'"{field}":"(.*?)"', resp.text)
                        if m and len(m.group(1)) > 30:
                            text = m.group(1).encode().decode('unicode_escape')
                            text = re.sub(r'&nbsp;', ' ', text)
                            text = re.sub(r'<[^>]+>', '\n', text)
                            parts.append(text.strip())
                    desc = "\n\n".join(parts)
                    if len(desc) >= 50:
                        logger.debug(f"Meta Careers description for {url}: {len(desc)} chars")
                        return desc[:30_000]
        except Exception as e:
            logger.debug(f"Meta Careers description failed for {url}: {e}")
        return None

    # ── Ashby: jobs.ashbyhq.com/{company}/{id} ──
    if _host_matches(url, "jobs.ashbyhq.com"):
        def _ashby_append_comp(desc, posting_data):
            """Append Ashby compensation summary to description for salary extraction."""
            comp = posting_data.get("scrapeableCompensationSalarySummary") or posting_data.get("compensationTierSummary") or ""
            if comp and "$" in comp:
                desc = desc + "\n\nCompensation: " + comp
            return desc

        path_parts = [p for p in parsed.path.strip("/").split("/") if p]
        if len(path_parts) >= 2:
            company_slug = path_parts[0]
            job_id = path_parts[1]
            try:
                async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                    # Try 1: page HTML with __appData (works for companies with SSR)
                    resp = await client.get(url, headers={"Accept": "text/html", "User-Agent": _USER_AGENT})
                    if resp.status_code == 200:
                        m = re.search(r'window\.__appData\s*=\s*(\{.*?\});', resp.text, re.DOTALL)
                        if m:
                            data = json.loads(m.group(1))
                            posting = data.get("posting") or {}
                            desc = posting.get("descriptionPlainText") or ""
                            if not desc:
                                desc_html = posting.get("descriptionHtml", "")
                                if desc_html:
                                    soup = BeautifulSoup(desc_html, "html.parser")
                                    desc = soup.get_text(separator="\n", strip=True)
                            if len(desc) >= 50:
                                desc = _ashby_append_comp(desc, posting)
                                logger.debug(f"Ashby page description for {url}: {len(desc)} chars")
                                return desc[:30_000]

                    # Try 2: full board API (works when SSR returns null posting)
                    api_url = f"https://api.ashbyhq.com/posting-api/job-board/{company_slug}"
                    resp2 = await client.get(api_url)
                    if resp2.status_code == 200:
                        for posting in resp2.json().get("jobs", []):
                            if posting.get("id") == job_id:
                                desc = posting.get("descriptionPlain", "")
                                if not desc:
                                    desc_html = posting.get("descriptionHtml", "")
                                    if desc_html:
                                        soup = BeautifulSoup(desc_html, "html.parser")
                                        desc = soup.get_text(separator="\n", strip=True)
                                if len(desc) >= 50:
                                    desc = _ashby_append_comp(desc, posting)
                                    logger.debug(f"Ashby API description for {url}: {len(desc)} chars")
                                    return desc[:30_000]
                                break
            except Exception as e:
                logger.debug(f"Ashby description failed for {url}: {e}")
            return None

    # ── Lever: jobs.lever.co/{company}/{id} ──
    if "jobs.lever.co/" in url.lower():
        path_parts = [p for p in parsed.path.strip("/").split("/") if p]
        if len(path_parts) >= 2:
            company_slug, posting_id = path_parts[0], path_parts[1]
            api_url = f"https://api.lever.co/v0/postings/{company_slug}/{posting_id}"
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(api_url)
                if resp.status_code == 200:
                    data = json.loads(resp.text)
                    parts = []
                    desc_html = data.get("descriptionPlain") or ""
                    if desc_html:
                        parts.append(desc_html)
                    for lst in data.get("lists", []):
                        parts.append(lst.get("text", ""))
                        parts.append(lst.get("content", ""))
                    text = "\n\n".join(p for p in parts if p)
                    if len(text) >= 50:
                        return text[:30_000]
        return None

    # ── Greenhouse: boards.greenhouse.io/{company}/jobs/{id} ──
    if _host_matches(url, "greenhouse.io") and "/jobs/" in url:
        path_parts = [p for p in parsed.path.strip("/").split("/") if p]
        # Format: /{company}/jobs/{id}
        company_slug = job_id = ""
        for i, p in enumerate(path_parts):
            if p == "jobs" and i + 1 < len(path_parts):
                job_id = path_parts[i + 1]
                if i > 0:
                    company_slug = path_parts[i - 1]
        if company_slug and job_id:
            api_url = f"https://boards-api.greenhouse.io/v1/boards/{company_slug}/jobs/{job_id}"
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(api_url)
                if resp.status_code == 200:
                    data = json.loads(resp.text)
                    content_html = data.get("content", "")
                    if content_html:
                        import html as _html
                        content_html = _html.unescape(_html.unescape(content_html))
                        soup = BeautifulSoup(content_html, "html.parser")
                        text = soup.get_text(separator="\n", strip=True)
                        if len(text) >= 50:
                            return text[:30_000]
        return None

    return None


async def _fetch_descriptions_parallel(jobs_to_fetch, max_concurrent=5):
    """Fetch job descriptions in parallel with a concurrency semaphore."""
    sem = asyncio.Semaphore(max_concurrent)

    async def fetch_one(job_dict):
        async with sem:
            desc = await _fetch_job_description(job_dict["url"])
            return job_dict, desc

    results = await asyncio.gather(*[fetch_one(j) for j in jobs_to_fetch], return_exceptions=True)
    return results
