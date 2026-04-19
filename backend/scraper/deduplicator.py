"""Back-compat shim — moved to backend.scraper._shared.dedup in Task 4.

TODO: Delete this shim in Task 26 after all external callers have been migrated.
"""
from backend.scraper._shared.dedup import (  # noqa: F401
    make_external_id, make_content_hash,
    reload_tracking_params, _get_tracking_params, _normalize_url,
    _DEFAULT_TRACKING_PARAMS,
)
