"""Every search mode in one table (R30 I-02).

A search's `search_mode` picks the source that fetches it. What each mode is (its label, the
module that runs it, whether its fetch is shared between accounts, whether its Test runs in
the background, which `sources` values it takes, what it needs before it can run) used to be
copied by hand into about 25 places; they now read it from here. The dashboard keeps the same
facts in `frontend/src/searchModes.js`, and `test_search_modes.py` fails when the two differ.

Adding a source: one entry here, one in searchModes.js, and its module under
`backend/scraper/sources/` with `run(search, ...)` and `preview(search, db)`. What is
per-mode code rather than a fact (the target key in `targets.search_key`, the editor fields)
stays where it is.
"""
from dataclasses import dataclass
from typing import Optional

# `sources` per kind of board list.
JOBSPY_BOARDS = ("linkedin", "indeed", "zip_recruiter", "google", "glassdoor", "bayt", "naukri", "bdjobs", "direct")
JOBSPY_DEFAULT_BOARDS = ["linkedin", "indeed", "zip_recruiter", "google"]
LINKEDIN_COLLECTIONS = ("recommended", "top-applicant")
CREATIVE_BOARDS = ("behance", "hollylist", "wanacreate", "himalayas", "eluta")    # sources/creative.py BOARDS
# `sources` kind -> (allowed values, what they are called in an error)
_BOARD_LISTS = {
    "jobspy": (JOBSPY_BOARDS, "JobSpy boards"),
    "collections": (LINKEDIN_COLLECTIONS, "LinkedIn collections"),
    "creative": (CREATIVE_BOARDS, "creative boards"),
}


@dataclass(frozen=True)
class SearchMode:
    key: str
    label: str
    module: Optional[str] = None      # backend.scraper.sources.<module>; None = no scraper
    log_source: Optional[str] = None  # ScrapeLog.source, when it is not the key
    extension: bool = False           # a seeded browser-extension search: jobs arrive by push
    shareable: bool = False           # one fetch may feed several accounts (targets.py)
    takes_proxy: bool = False         # run(search, proxy_url=...)
    background_test: bool = False     # Test runs as a task and returns a run_id to poll
    uses_country: bool = False        # location + country go to the board and must agree
    boards: Optional[str] = None      # what `sources` holds: "jobspy" | "apify" | "collections" | "creative" | None
    needs_url: bool = False           # cannot run without direct_url
    needs_query: bool = False         # cannot run without a search term or direct_url
    paid: bool = False                # bills per run: new, switched and copied searches start paused
    # Shared fetch (targets.search_fetch_params): the fields a shared fetch takes at the largest
    # value among its subscribers, each account trimming its own copy; (field, default) pairs.
    fetch_params: tuple = ()

    @property
    def runnable(self) -> bool:
        return self.module is not None

    @property
    def source(self) -> str:
        return self.log_source or self.key


SEARCH_MODES: dict[str, SearchMode] = {m.key: m for m in (
    SearchMode("keyword", "Keyword (JobSpy)", "jobspy", log_source="jobspy", shareable=True,
               takes_proxy=True, uses_country=True, boards="jobspy",
               fetch_params=(("results_wanted", 50), ("hours_old", 24))),
    SearchMode("levels_fyi", "Levels.fyi", "levelsfyi", shareable=True, background_test=True,
               needs_url=True),
    # The account's own LinkedIn session: never shared.
    SearchMode("linkedin_personal", "LinkedIn Personal", "linkedin_personal", background_test=True,
               boards="collections"),
    # The account's own Jobright session: never shared.
    SearchMode("jobright", "Jobright.ai", "jobright", background_test=True),
    SearchMode("freehire", "freehire.me", "freehire", shareable=True, background_test=True,
               needs_query=True, fetch_params=(("results_wanted", 100),)),
    # Never shared: each account's run is billed to its own Apify token.
    SearchMode("apify", "Apify", "apify", background_test=True, uses_country=True, boards="apify",
               paid=True),
    SearchMode("caribbeanjobs", "CaribbeanJobs.com", "caribbeanjobs", shareable=True,
               background_test=True, needs_query=True, fetch_params=(("results_wanted", 100),)),
    # The roster is fetched whole; results_wanted applies per subscriber after dedup.
    SearchMode("trulyremote", "TrulyRemoteWork.com", "trulyremote", shareable=True,
               background_test=True),
    # Not shared yet: a proof of concept; its key would be boards + term + location + remote.
    SearchMode("creative", "Creative boards", "creative", background_test=True, boards="creative"),
    SearchMode("linkedin_extension", "LinkedIn Extension", extension=True),
    SearchMode("extension", "Extension", extension=True),
)}

EXTENSION_MODES = tuple(k for k, m in SEARCH_MODES.items() if m.extension)
SHAREABLE_MODES = tuple(k for k, m in SEARCH_MODES.items() if m.shareable)


def get_mode(key) -> Optional[SearchMode]:
    """The mode called `key` ("" or None means keyword, the column default), or None."""
    return SEARCH_MODES.get(key or "keyword")


def is_extension(key) -> bool:
    mode = get_mode(key)
    return bool(mode and mode.extension)


def default_sources(key) -> list:
    """What `sources` holds for a new search of this mode when the client sent none."""
    mode = get_mode(key)
    if mode is None:
        return []
    if mode.boards == "jobspy":
        return list(JOBSPY_DEFAULT_BOARDS)
    if mode.boards in ("collections", "creative"):
        return list(_BOARD_LISTS[mode.boards][0])
    return []   # apify has no default board here: the client picks one (GET /searches/apify-boards)


def bad_sources(key, sources) -> Optional[str]:
    """Why `sources` does not fit this mode, or None. Apify boards are checked by the route
    (`_apify_sources`), which knows the presets; modes without a board list take none."""
    mode = get_mode(key)
    if mode is None or mode.boards in (None, "apify"):
        return None
    if not isinstance(sources, list):
        return "sources must be a list"
    allowed, what = _BOARD_LISTS[mode.boards]
    unknown = [s for s in sources if s not in allowed]
    if unknown:
        return (f"{mode.label} takes {what} ({', '.join(allowed)}); "
                f"not one: {', '.join(map(str, unknown))}")
    return None


def config_error(search) -> Optional[str]:
    """A human reason this search cannot run as configured, or None."""
    mode = get_mode(getattr(search, "search_mode", None))
    if mode is None:
        return f"Unknown search mode {getattr(search, 'search_mode', None)!r}"
    if mode.extension:
        return f"{mode.label} searches have no scraper: jobs arrive from the browser extension"
    if mode.needs_url and not (search.direct_url or "").strip():
        return f"{mode.label} needs a search URL before it can run"
    if mode.needs_query and not (search.direct_url or search.search_term):
        return f"{mode.label} needs a search term or a URL before it can run"
    if mode.boards == "apify":
        from backend.scraper.sources.apify import configured_presets
        if not (search.search_term or "").strip():
            return "Apify needs a search term before it can run"
        if not configured_presets(search):
            return "Apify needs at least one board before it can run"
    if mode.boards == "creative":
        if not (search.search_term or "").strip():
            return f"{mode.label} needs a search term before it can run"
        if not any(s in CREATIVE_BOARDS for s in (search.sources or [])):
            return f"{mode.label} needs at least one board before it can run"
    return None
