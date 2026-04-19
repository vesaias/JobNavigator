"""Back-compat shim — moved to backend.scraper.sources.linkedin_personal in Task 19.

TODO: Delete this shim in Task 26 after all external callers have been migrated.
"""
from backend.scraper.sources.linkedin_personal import (  # noqa: F401
    run as scrape_linkedin_personal,
    preview as test_linkedin_personal,
    # Re-export module constants / helpers that external callers may import
    COOKIE_PATH,
    ALL_COLLECTIONS,
    LinkedInRateLimitError,
)
