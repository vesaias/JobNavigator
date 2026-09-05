"""SHA256 deduplication logic with URL normalization."""
import hashlib
import json
import logging
import re
from urllib.parse import urlparse, parse_qs, parse_qsl, urlencode, urlunparse

logger = logging.getLogger("jobnavigator.dedup")

# Hardcoded fallback — used until DB setting is loaded
_DEFAULT_TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term", "mode",
    "src", "source", "ref", "refid", "refsrc", "refsource",
    "origin", "from", "channel", "medium",
    "gns", "gnk", "gni",
    "trk", "trackingid", "tracking_id", "currentjobid",
    "ebp", "recommendedflavor",
    "gh_src", "lever_source", "lever_origin",
    "lever-source", "lever-origin", "lever-source[]", "lever-source%5b%5d",
    "visitid", "impid",
    "jz",
    "iis", "iisn",
    "fbclid", "gclid", "msclkid", "mc_cid", "mc_eid",
    "_ga", "_gl", "dclid", "zanpid",
    "igshid", "yclid", "twclid",
    "_hsenc", "_hsmi", "mkt_tok",
    "jclickid", "publisher",
    "p_sid", "p_uid", "ss",
    "__jvsd", "__jvst", "jobpipeline", "cmpid", "codes", "feedid",
    "partnerid", "siteid", "bid", "customredirect",
    "chnlid", "v", "ccd", "frd", "r", "a",
    # "jk" is gone from this list — it is Indeed's entire job identity, not
    # tracking. _IDENTITY_PARAMS below is the real guard, protecting it even if
    # an operator's editable `dedup_tracking_params` setting still contains it.
    # Search-context noise (career page filters that leak into job hrefs):
    "categories", "cities", "locations", "departments", "teams", "regions", "country", "category",
}

# A query param can be pure tracking on one board and the posting's whole identity
# on another (Indeed's `/viewjob?jk=<key>` carries nothing in the path) — these
# params are kept for their host regardless of the user-editable tracking list.
# Keys match the host and any subdomain of it, lowercased.
_IDENTITY_PARAMS = {
    "indeed.com": {"jk", "vjk"},
    "glassdoor.com": {"jl", "joblistingid"},
    "linkedin.com": {"currentjobid"},
    "dice.com": {"jobid"},
    "monster.com": {"jobid"},
}
# LinkedIn is the exception: on /jobs/view/<id> the identity is already in the
# path, so `currentJobId` is noise there — it's an identity only on search shapes.
_LINKEDIN_ID_IN_PATH = re.compile(r"/jobs/view/\d+")


def _identity_params_for(parsed) -> set:
    """Query params that must survive normalization for this host."""
    host = (parsed.netloc or "").lower().split(":")[0]
    for domain, keys in _IDENTITY_PARAMS.items():
        if host == domain or host.endswith("." + domain):
            if domain == "linkedin.com" and _LINKEDIN_ID_IN_PATH.search(parsed.path or ""):
                return set()
            return keys
    return set()


# Module-level cache — loaded from DB on first use or reload
_tracking_params_cache: set | None = None


def _get_tracking_params() -> set:
    """Return the tracking params set, loading from DB on first call."""
    global _tracking_params_cache
    if _tracking_params_cache is not None:
        return _tracking_params_cache
    try:
        from backend.models.db import SessionLocal, Setting
        db = SessionLocal()
        try:
            row = db.query(Setting).filter(Setting.key == "dedup_tracking_params").first()
            if row and row.value:
                params = json.loads(row.value)
                _tracking_params_cache = {p.lower() for p in params}
                logger.info(f"Loaded {len(_tracking_params_cache)} dedup tracking params from DB")
                return _tracking_params_cache
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Failed to load dedup params from DB, using defaults: {e}")
    _tracking_params_cache = _DEFAULT_TRACKING_PARAMS
    return _tracking_params_cache


def reload_tracking_params():
    """Force reload tracking params from DB. Called after settings update."""
    global _tracking_params_cache
    _tracking_params_cache = None
    _get_tracking_params()


def _normalize_url(url: str) -> str:
    """Strip tracking/referral query params, apply/thanks suffixes, and fragment; case is PRESERVED since some ATS WAFs (Oracle HCM, Workday) 403 on lowercased paths."""
    if not url:
        return ""
    try:
        params = _get_tracking_params()
        parsed = urlparse(url)
        path = parsed.path
        # Strip ATS application/apply suffixes (Ashby, Lever, etc.) — case-insensitive
        # match so we don't miss /Apply or /APPLY variants, but preserve the rest.
        for suffix in ("/application", "/apply", "/thanks"):
            if path.lower().endswith(suffix):
                path = path[:-len(suffix)]
        qs = parse_qs(parsed.query, keep_blank_values=False)
        # Remove tracking params + utm_* except the ones that ARE the posting's
        # identity on this host — stripping those merges unrelated jobs onto one id.
        keep = _identity_params_for(parsed)
        cleaned = {k: v for k, v in qs.items()
                   if k.lower() in keep
                   or (k.lower() not in params and not k.lower().startswith("utm_"))}
        # Param ORDER is deliberately preserved here: this value is stored as
        # Job.url by the company-page scraper, and a board can be picky about the
        # URL it handed out. Order-independence belongs to the hash, and is done
        # in _canonical_for_hash() below.
        new_query = urlencode(cleaned, doseq=True)
        # Remove fragment (anchors are display-only)
        return urlunparse(parsed._replace(path=path, query=new_query, fragment=""))
    except Exception:
        return url


_ATS_SUFFIXES = ("/application", "/apply", "/thanks")


def _fold_path(path: str) -> str:
    """Drop a trailing slash and any ATS apply/thanks suffix it was hiding.

    `_normalize_url` only strips a suffix that ends the path, so
    `…/4012345/apply/` keeps its `/apply`. Folding the slash first, then the
    suffix, then the slash the suffix exposed, collapses both spellings.
    """
    for _ in range(2):
        before = path
        if len(path) > 1 and path.endswith("/"):
            path = path[:-1]
        for suffix in _ATS_SUFFIXES:
            if path.endswith(suffix):
                path = path[:-len(suffix)]
                break
        if path == before:
            break
    return path


def _canonical_for_hash(url: str) -> str:
    """Hash-only canonical form.

    Folds everything that spells the same posting two ways — scheme (http vs
    https), a leading `www.`, host/path case, a trailing slash, and query-param
    order — so twenty spellings of one job collapse onto one `external_id`. The
    stored `Job.url` is untouched by this: it keeps the bytes the board handed us
    (some ATS WAFs 403 without the exact path they linked).
    """
    if not url:
        return ""
    stripped = _normalize_url(url)
    try:
        parsed = urlparse(stripped)
        # http and https serve the same posting; a board upgrading its scheme
        # must not re-import its whole catalogue.
        scheme = (parsed.scheme or "").lower()
        if scheme in ("http", "https"):
            scheme = "https"
        netloc = (parsed.netloc or "").lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        path = _fold_path((parsed.path or "").lower())
        # Sorted so ?a=1&b=2 and ?b=2&a=1 hash alike.
        query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=False)))
        return urlunparse((scheme, netloc, path, parsed.params, query, ""))
    except Exception:
        return stripped


def make_external_id(company: str, title: str, url: str) -> str:
    """Generate a SHA256 dedup hash from the canonical (lowercased) URL, falling back to company+title if URL is empty."""
    canonical = _canonical_for_hash(url)
    if canonical:
        return hashlib.sha256(canonical.encode()).hexdigest()
    # Fallback for jobs without URLs
    raw = f"{company or ''}{title or ''}"
    return hashlib.sha256(raw.encode()).hexdigest()


def make_content_hash(company: str, title: str) -> str:
    """Hash of company+title only (no URL) for cross-source dedup."""
    raw = f"{(company or '').lower().strip()}{(title or '').lower().strip()}"
    return hashlib.sha256(raw.encode()).hexdigest()
