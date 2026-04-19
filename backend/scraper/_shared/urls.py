"""URL helpers shared across scrapers: host matching, path matching, tracking-param cleaning.

host_matches uses strict hostname parsing (not substring) to resist attacker-controlled
URLs with lookalike domains or path injection (CodeQL incomplete-url-substring-sanitization).
"""
import logging
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

logger = logging.getLogger("jobnavigator.scraper.urls")


def _get_url_tracking_params():
    """Lazy import to avoid circular dependency; tracking params live in dedup module."""
    from backend.scraper.deduplicator import _get_tracking_params
    return _get_tracking_params()


def _clean_application_url(url: str) -> str:
    """Strip referral/tracking params from application URLs, preserving functional params like gh_jid."""
    if not url:
        return url
    parsed = urlparse(url)
    qs = parse_qs(parsed.query, keep_blank_values=True)
    cleaned = {k: v for k, v in qs.items() if k.lower() not in _get_url_tracking_params()}
    new_query = urlencode(cleaned, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def host_matches(url: str, *domains: str) -> bool:
    """True if URL's hostname equals or is a subdomain of any given domain.

    Uses strict hostname comparison (not substring) to avoid attacker-controlled
    lookalike domains matching (e.g. "evil-metacareers.com").
    """
    if not url:
        return False
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return False
    if not host:
        return False
    for raw in domains:
        d = (raw or "").lower().strip().rstrip("/")
        if not d:
            continue
        if host == d or host.endswith("." + d):
            return True
    return False


def path_contains(url: str, *needles: str) -> bool:
    """True if URL's path contains any of the given needles (case-insensitive)."""
    if not url:
        return False
    try:
        path = (urlparse(url).path or "").lower()
    except Exception:
        return False
    return any(n.lower() in path for n in needles if n)
