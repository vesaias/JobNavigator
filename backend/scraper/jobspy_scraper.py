"""Back-compat shim — moved to backend.scraper.sources.jobspy + orchestrator in Tasks 18/23.

TODO: Delete this shim in Task 26 after all external callers have been migrated.
"""
# Helpers that used to live here — now in sources/jobspy.py
from backend.scraper.sources.jobspy import (  # noqa: F401
    get_setting_value, apply_title_filters, apply_company_filter,
    _run_sync as run_jobspy_search,
)

# Orchestrator entrypoints (Task 23)
from backend.scraper.orchestrator import (  # noqa: F401
    run_all as run_all_searches,
    _run_search_by_id as run_single_search,
)
