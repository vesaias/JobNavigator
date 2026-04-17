"""SHA256 deduplication logic with URL normalization."""
import hashlib
import json
import logging
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

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
    "jk",
}

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
    """Strip tracking/referral query params from a URL for dedup purposes."""
    if not url:
        return ""
    try:
        params = _get_tracking_params()
        parsed = urlparse(url)
        path = parsed.path
        # Strip ATS application/apply suffixes (Ashby, Lever, etc.)
        for suffix in ("/application", "/apply", "/thanks"):
            if path.endswith(suffix):
                path = path[:-len(suffix)]
        qs = parse_qs(parsed.query, keep_blank_values=False)
        # Remove tracking params (case-insensitive key match) + all utm_* params
        cleaned = {k: v for k, v in qs.items()
                   if k.lower() not in params and not k.lower().startswith("utm_")}
        # Sort params for stable hashing
        new_query = urlencode(cleaned, doseq=True)
        # Remove fragment (anchors are display-only)
        return urlunparse(parsed._replace(path=path, query=new_query, fragment=""))
    except Exception:
        return url


def make_external_id(company: str, title: str, url: str) -> str:
    """Generate SHA256 hash for deduplication. Uses normalized URL only — title/company
    changes on the same posting (e.g. 'PM - X' vs 'PM, X') won't bypass dedup.
    Falls back to company+title if URL is empty."""
    clean_url = _normalize_url(url)
    if clean_url:
        return hashlib.sha256(clean_url.encode()).hexdigest()
    # Fallback for jobs without URLs
    raw = f"{company or ''}{title or ''}"
    return hashlib.sha256(raw.encode()).hexdigest()


def make_content_hash(company: str, title: str) -> str:
    """Hash of company+title only (no URL) for cross-source dedup."""
    raw = f"{(company or '').lower().strip()}{(title or '').lower().strip()}"
    return hashlib.sha256(raw.encode()).hexdigest()
