"""Back-compat shim — moved to backend.scraper.sources.jobright in Task 20.

TODO: Delete this shim in Task 26 after all external callers have been migrated.
"""
from backend.scraper.sources.jobright import (  # noqa: F401
    run as scrape_jobright,
    preview as test_jobright,
    # Re-export module constants / helpers that external callers may import
    SessionExpiredError,
    API_BASE,
    SITE_BASE,
    DELAY_BETWEEN_PAGES,
    MAX_RETRIES,
    RETRY_BACKOFF,
)
