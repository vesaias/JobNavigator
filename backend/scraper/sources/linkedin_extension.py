"""LinkedIn Extension source — Voyager enrichment for job IDs captured passively by the Chrome extension, received via POST /api/jobs/linkedin-import.
Runs Voyager from inside a logged-in Playwright browser (not linkedin-api) since password login now hits CHALLENGE and standalone HTTP clients get session-poisoned by LinkedIn's rotating cookies; the session is refreshed by backend/refresh_linkedin_session.py."""
import asyncio
import json
import logging
import os
from collections.abc import MutableMapping

from backend.models.db import (
    SessionLocal, Job,
    build_company_lookup, get_existing_external_ids,
)
from backend.scraper._shared.dedup import make_external_id, make_content_hash
from backend.scraper._shared.postings import is_short_link, resolve_short_link
from backend.analyzer.salary_extractor import apply_salary_to_job
from backend.analyzer.work_arrangement import apply_arrangement_to_job
from backend.analyzer.location import apply_location_to_job
from backend.analyzer.h1b_checker import check_job_h1b, determine_h1b_verdict
from backend.scraper._shared.filters import include_hit

logger = logging.getLogger("jobnavigator.jobs")

class _PerAccountProgress(MutableMapping):
    """In-memory LinkedIn import progress, one dict per account (QA F5, R5-02).

    Reads and writes go to the entry of the account in the current context (the import
    task runs under the account that started it), so two accounts' imports never wipe or
    mix each other's counters and each polls only its own."""

    def __init__(self):
        self._by_account: dict = {}

    @staticmethod
    def _key():
        from backend.accounts.context import current_account
        acc = current_account.get()
        return str(acc) if acc is not None else ""

    def _mine(self) -> dict:
        return self._by_account.setdefault(self._key(), {})

    def __getitem__(self, k):
        return self._mine()[k]

    def __setitem__(self, k, v):
        self._mine()[k] = v

    def __delitem__(self, k):
        del self._mine()[k]

    def __iter__(self):
        return iter(dict(self._by_account.get(self._key(), {})))

    def __len__(self):
        return len(self._by_account.get(self._key(), {}))

    def __repr__(self):
        return repr(self._by_account.get(self._key(), {}))

    def forget(self, account_id) -> None:
        """Drop a removed account's entry (QA F8 / R5-10)."""
        self._by_account.pop(str(account_id), None)

    def reset_all(self) -> None:
        """Tests: forget every account's progress."""
        self._by_account.clear()


# Shared with routes_jobs for the progress-polling endpoint.
_linkedin_import_progress = _PerAccountProgress()

# Persisted (mounted) Playwright session cookies — written by
# backend/refresh_linkedin_session.py. Survives container restarts.
def _session_path() -> str:
    """The jar the LinkedIn import reads: the mock account's session when a mock account is set
    (Settings › LinkedIn), else the main account's. MT-16: the current account's jars (the
    owner's mock jar is /root/.linkedin_api/li_cookies.json, a member's lives under accounts/<id>/)."""
    from backend.accounts.credentials import linkedin_extension_cookies, linkedin_personal_cookies
    from backend.accounts.settings import get_setting
    from backend.models.db import SessionLocal
    db = SessionLocal()
    try:
        mock = (get_setting(db, "linkedin_mock_email") or "").strip()
    finally:
        db.close()
    if mock:
        return linkedin_extension_cookies()
    main, old = linkedin_personal_cookies(), linkedin_extension_cookies()
    # Before the sessions split, an install without a mock account kept its personal session in
    # the extension jar: it carries over as the main session once.
    if not os.path.exists(main) and os.path.exists(old) and not os.path.exists(old + ".account"):
        try:
            import shutil
            os.makedirs(os.path.dirname(main) or ".", exist_ok=True)
            shutil.copyfile(old, main)
        except OSError:
            return old
    return main

# The exact Voyager endpoint + decoration the linkedin-api library used; returns plain JSON
# with top-level title/companyDetails/description/formattedLocation/applyMethod.
_VOYAGER_JOB_JS = """async (jid) => {
    const csrf = (document.cookie.match(/JSESSIONID="?([^;"]+)/) || [])[1] || '';
    const url = `https://www.linkedin.com/voyager/api/jobs/jobPostings/${jid}`
      + `?decorationId=com.linkedin.voyager.deco.jobs.web.shared.WebLightJobPosting-23`;
    const r = await fetch(url, {credentials: 'include', headers: {
        'csrf-token': csrf,
        'x-restli-protocol-version': '2.0.0',
        'accept': 'application/json'
    }});
    if (r.status !== 200) return {status: r.status};
    const d = await r.json();
    let company = '';
    for (const v of Object.values(d.companyDetails || {})) {
        if (v && v.companyResolutionResult) { company = v.companyResolutionResult.name; break; }
    }
    let apply = '';
    for (const v of Object.values(d.applyMethod || {})) {
        if (v && v.companyApplyUrl) { apply = v.companyApplyUrl; break; }
    }
    // "OffsiteApply" (the employer's site) or "...OnsiteApply" (Easy Apply), from the key's tail
    const applyKey = Object.keys(d.applyMethod || {})[0] || '';
    const applyType = applyKey.split('.').pop();
    // workplaceTypes is a URN list ("urn:li:fs_workplaceType:2"); workRemoteAllowed
    // is a plain bool. Both are read defensively: this decoration is not
    // documented, so a build that omits them just yields nulls.
    let wpt = '';
    if (Array.isArray(d.workplaceTypes) && d.workplaceTypes.length) {
        wpt = String(d.workplaceTypes[0]).split(':').pop();
    }
    return {status: 200, title: d.title || '', company: company || '',
            location: d.formattedLocation || '',
            description: (d.description && d.description.text) || '',
            apply_url: apply || '',
            apply_type: applyType,
            job_state: d.jobState || '',
            workplace_type: wpt,
            work_remote_allowed: (typeof d.workRemoteAllowed === 'boolean')
                ? d.workRemoteAllowed : null};
}"""


# LinkedIn's workplaceType URN tails. `workRemoteAllowed` is deliberately not
# mapped: like Ashby's `isRemote` it flags "a remote option exists", which a
# hybrid posting also sets.
_WORKPLACE_TYPES = {"1": "onsite", "2": "remote", "3": "hybrid"}


def _voyager_arrangement(job_data: dict) -> str | None:
    """Map the Voyager workplace type onto an arrangement the cascade accepts."""
    return _WORKPLACE_TYPES.get(str(job_data.get("workplace_type") or "").strip())


def _load_session_cookies():
    """Load persisted Playwright cookies, or None if the session file is absent."""
    try:
        with open(_session_path()) as f:
            cookies = json.load(f)
        return cookies or None
    except (OSError, ValueError):
        return None


async def _voyager_fetch(page, lid: str) -> dict | None:
    """Fetch one job's Voyager JSON from inside the logged-in browser page; returns None if the endpoint didn't return 200 (dead job / not logged in)."""
    try:
        d = await page.evaluate(_VOYAGER_JOB_JS, lid)
    except Exception:
        return None
    if not isinstance(d, dict) or d.get("status") != 200:
        return None
    return d


async def enrich(linkedin_ids: list[str], db=None):
    """Background: fetch LinkedIn job data via in-browser Voyager, create jobs."""
    import re
    from backend.models.db import Search

    logger.info(f"LinkedIn import: fetching {len(linkedin_ids)} jobs via Voyager (browser session)")

    db = SessionLocal()
    try:
        # Pre-check: skip LinkedIn IDs already in the DB (avoid unnecessary fetches)
        existing_li_ids = {
            r[0] for r in db.query(Job.linkedin_job_id).filter(Job.linkedin_job_id != None).all()
        }
        pre_dedup = [lid for lid in linkedin_ids if lid not in existing_li_ids]
        pre_skipped = len(linkedin_ids) - len(pre_dedup)
        if pre_skipped:
            logger.info(f"LinkedIn import: {pre_skipped}/{len(linkedin_ids)} already in DB, skipping fetch")

        _linkedin_import_progress.update({
            "total": len(linkedin_ids),
            "pre_skipped": pre_skipped,
            "processed": 0,
            "imported": 0,
            "skipped": pre_skipped,
            "status": "running",
        })

        if not pre_dedup:
            _linkedin_import_progress["status"] = "done"
            logger.info("LinkedIn import: all IDs already exist, nothing to fetch")
            return

        # Load the LinkedIn Extension search for filters + linking
        ext_search = db.query(Search).filter(Search.search_mode == "linkedin_extension").first()

        # Require a persisted logged-in session (established out-of-band via
        # backend/refresh_linkedin_session.py). Without it we can't reach Voyager.
        session_cookies = _load_session_cookies()
        if not session_cookies:
            logger.error("LinkedIn import: no session cookies at %s — run "
                         "Settings › LinkedIn › Sign in (or `python -m backend.refresh_linkedin_session --session main|mock`) first", _session_path())
            _linkedin_import_progress["status"] = "error"
            _linkedin_import_progress["error_details"] = [{"stage": "session",
                "error": "no LinkedIn session — refresh it in Settings › LinkedIn"}]
            return

        existing_ext_ids = get_existing_external_ids(db)
        company_lookup = build_company_lookup(db)
        # Hoisted per import so these aren't re-read per job in the loop
        from backend.models.db import get_global_title_exclude
        from backend.analyzer.h1b_checker import load_exclusion_phrases
        _global_te = get_global_title_exclude(db)
        _phrases = load_exclusion_phrases(db)
        imported = 0
        skipped = pre_skipped

        # One logged-in browser for the whole batch (reuses linkedin_personal's stealth browser);
        # navigate to a LinkedIn origin first so in-page fetch() carries the session + fresh cookies.
        from backend.scraper.sources.linkedin_personal import _get_linkedin_browser
        pw = browser = None
        try:
            pw, browser, context, page = await _get_linkedin_browser()
            await context.add_cookies(session_cookies)
            await page.goto("https://www.linkedin.com/jobs/",
                            wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)
            # Verify the session is live before burning through the batch.
            probe = await _voyager_fetch(page, pre_dedup[0])
            if probe is None:
                # Re-check with a /me call to distinguish dead-session from dead-job
                # (csrf-token header is required or Voyager returns 403).
                me_status = await page.evaluate(
                    "async () => {"
                    "  const csrf=(document.cookie.match(/JSESSIONID=\"?([^;\"]+)/)||[])[1]||'';"
                    "  return (await fetch('https://www.linkedin.com/voyager/api/me',"
                    "    {credentials:'include', headers:{'csrf-token':csrf}})).status;"
                    "}")
                if me_status != 200:
                    logger.error("LinkedIn import: session invalid (me=%s) — run "
                                 "Settings › LinkedIn › Sign in (or `python -m backend.refresh_linkedin_session --session main|mock`)", me_status)
                    _linkedin_import_progress["status"] = "error"
                    _linkedin_import_progress["error_details"] = [{"stage": "session",
                        "error": f"session invalid (me={me_status}) — refresh it in Settings › LinkedIn"}]
                    return

            for lid in pre_dedup:
                linkedin_url = f"https://www.linkedin.com/jobs/view/{lid}"
                try:
                    job_data = await _voyager_fetch(page, lid)
                    if not job_data or not job_data.get("title"):
                        logger.warning(f"LinkedIn {lid}: no data returned, skipping")
                        skipped += 1
                        continue

                    title = (job_data.get("title") or "").strip()
                    company = (job_data.get("company") or "").strip()

                    if not title or not company:
                        logger.warning(f"LinkedIn {lid}: missing title/company, skipping")
                        skipped += 1
                        continue

                    # Apply search filters (title include/exclude, company exclude)
                    if ext_search:
                        title_lower = title.lower()
                        include_kw = ext_search.title_include_keywords or []
                        if include_kw and not any(include_hit(kw, title_lower) for kw in include_kw):
                            logger.info(f"LinkedIn {lid}: title '{title}' doesn't match include filter, skipping")
                            skipped += 1
                            continue
                        # Title exclude filter (merge global — hoisted above loop)
                        exclude_kw = list(set((ext_search.title_exclude_keywords or []) + _global_te))
                        if exclude_kw:
                            pattern = "|".join(r'\b' + re.escape(kw) + r'\b' for kw in exclude_kw)
                            if re.search(pattern, title, re.IGNORECASE):
                                logger.info(f"LinkedIn {lid}: title '{title}' matches exclude filter, skipping")
                                skipped += 1
                                continue
                        company_excl = ext_search.company_exclude or []
                        if company_excl and company.lower().strip() in {c.lower().strip() for c in company_excl}:
                            logger.info(f"LinkedIn {lid}: company '{company}' excluded, skipping")
                            skipped += 1
                            continue

                    location = (job_data.get("location") or "").strip()
                    description = (job_data.get("description") or "").strip()

                    # Real external apply URL from Voyager (companyApplyUrl); use it
                    # for dedup + display, fall back to the LinkedIn URL (Easy-Apply).
                    apply_url = (job_data.get("apply_url") or "").strip()
                    job_url = apply_url if apply_url else linkedin_url

                    ext_id = make_external_id(company, title, job_url)
                    c_hash = make_content_hash(company, title)
                    alt_ext_id = make_external_id(company, title, linkedin_url) if apply_url else None

                    if ext_id in existing_ext_ids:
                        skipped += 1
                        continue
                    if alt_ext_id and alt_ext_id in existing_ext_ids:
                        skipped += 1
                        continue

                    landed = await resolve_short_link(job_url) if is_short_link(job_url) else job_url
                    job = Job(
                        external_id=ext_id,
                        content_hash=c_hash,
                        company=company,
                        title=title,
                        url=job_url,
                        apply_url=landed if landed != job_url else None,
                        source="linkedin_extension",
                        linkedin_job_id=lid,
                        search_id=ext_search.id if ext_search else None,
                        location=location,
                        description=description,
                        status="new",
                    )

                    # H-1B + language check first, then salary (reuses the cache
                    # median that check_job_h1b stashes on the job).
                    try:
                        await check_job_h1b(job, db, company_lookup=company_lookup, phrases=_phrases)
                        job.h1b_verdict = determine_h1b_verdict(
                            job.h1b_company_lca_count, job.h1b_jd_flag
                        )
                        apply_salary_to_job(job, getattr(job, "_h1b_median", None))
                        apply_arrangement_to_job(
                            job, structured=_voyager_arrangement(job_data))
                        apply_location_to_job(job)
                    except Exception as e:
                        logger.warning(f"LinkedIn {lid}: analysis error: {e}")
                        _linkedin_import_progress["errors"] = (
                            _linkedin_import_progress.get("errors", 0) + 1
                        )
                        _linkedin_import_progress.setdefault("error_details", []).append({
                            "lid": lid,
                            "stage": "analysis",
                            "error": str(e)[:200],
                        })

                    # Skip flagged jobs (same as other scrapers)
                    if job.h1b_jd_flag:
                        _phrase = getattr(job, "_h1b_matched_phrase", None) or "?"
                        logger.info(f"LinkedIn {lid} ({job.title!r}): skipping (body exclusion) — matched phrase: {_phrase!r}")
                        skipped += 1
                        continue

                    db.add(job)
                    db.commit()
                    imported += 1
                    existing_ext_ids.add(ext_id)
                    logger.info(f"LinkedIn {lid}: imported '{title}' at '{company}' -> {job_url[:80]}")

                except Exception as e:
                    logger.warning(f"LinkedIn {lid}: failed: {e}")
                    db.rollback()
                    skipped += 1
                    _linkedin_import_progress["errors"] = (
                        _linkedin_import_progress.get("errors", 0) + 1
                    )
                    _linkedin_import_progress.setdefault("error_details", []).append({
                        "lid": lid,
                        "stage": "fetch",
                        "error": str(e)[:200],
                    })

                _linkedin_import_progress.update({
                    "processed": _linkedin_import_progress["processed"] + 1,
                    "imported": imported,
                    "skipped": skipped,
                })

                await asyncio.sleep(1)  # Rate limit

            _linkedin_import_progress["status"] = "done"
            logger.info(f"LinkedIn import: done — imported {imported}, skipped {skipped}/{len(linkedin_ids)}")

            if imported > 0 and ext_search and ext_search.auto_scoring_depth in ("light", "full"):
                try:
                    from backend.analyzer.cv_scorer import analyze_unscored_jobs
                    await analyze_unscored_jobs(status="new")
                    logger.info("LinkedIn import: auto-scoring triggered")
                except Exception as e:
                    logger.warning(f"LinkedIn import: auto-scoring failed: {e}")
                    _linkedin_import_progress["errors"] = (
                        _linkedin_import_progress.get("errors", 0) + 1
                    )
                    _linkedin_import_progress.setdefault("error_details", []).append({
                        "lid": None,
                        "stage": "auto_scoring",
                        "error": str(e)[:200],
                    })
        finally:
            try:
                if browser:
                    await browser.close()
                if pw:
                    await pw.stop()
            except Exception:
                pass
    finally:
        db.close()
