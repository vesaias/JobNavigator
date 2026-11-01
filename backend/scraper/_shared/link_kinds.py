"""Whether a job's link reaches the employer's own site.

Every job gets a `link_kind`:

- `direct`: its link (or the employer link beside it, `apply_url`) names an employer posting, is a
  company's own site, or is a short link that lands on one (grnh.se, prng.co, appcast).
- `board`: only a job board or aggregator listing is known (LinkedIn, Indeed, Glassdoor,
  ZipRecruiter, WhatJobs, Telegram, ...). Dedup can't safely tell two board listings of one job apart,
  and you apply through the board.
- `easy_apply`: a board listing known to have no employer link at all, applied to on the board itself:
  LinkedIn Easy Apply (found by the LinkedIn lookup), a levels.fyi job whose page data names no
  apply link (levels_jobs.py), and Behance, Hollylist and Wana Create postings with no employer link
  (job_boards.py). Kept when the links alone would say `board`. The dashboard shows it as Direct.

A host not in `BOARD_HOSTS` counts as the company's own site: a board found in the data that is
missing from the list is added to it.
"""
from urllib.parse import urlparse

from backend.scraper._shared.postings import _host, _is, is_employer_key, is_short_link, posting_key, unwrap

DIRECT = "direct"
BOARD = "board"
EASY_APPLY = "easy_apply"

BOARD_HOSTS = (
    "linkedin.com", "indeed.com", "glassdoor.com", "ziprecruiter.com", "levels.fyi", "jobright.ai",
    "caribbeanjobs.com", "trulyremotework.com", "whatjobs.com", "t.me", "hackajob.com", "haystack.cv",
    "swooped.co", "jobsyn.org", "dice.com", "monster.com", "simplyhired.com", "builtin.com",
    "wellfound.com", "remocate.app", "teletype.in", "behance.net", "hollylist.com", "wanacreate.art",
    "dribbble.com", "artstation.com", "workwithindies.com", "himalayas.app", "eluta.ca",
    "welcometothejungle.com",
    "lnkd.in",   # LinkedIn's short link lands on LinkedIn
)


def _on_board(url: str) -> bool:
    try:
        host = _host(urlparse(unwrap(url)))
    except Exception:
        return True
    return not host or any(_is(host, b) for b in BOARD_HOSTS)


def link_kind(url, apply_url) -> str:
    """`direct` or `board` for a job's links (see the module docstring)."""
    for link in (apply_url, url):
        if link and is_employer_key(posting_key(link)):
            return DIRECT
    # `apply_url` only ever holds the employer's link: a company site without a known system counts
    if apply_url and not _on_board(apply_url):
        return DIRECT
    if not url or _on_board(url):
        return BOARD
    return DIRECT   # a company's own site, or a short link (grnh.se, prng.co, appcast) that lands on one


def classify(job) -> None:
    """Set `job.link_kind` from its links; an Easy Apply row stays Easy Apply while its links say board."""
    kind = link_kind(job.url, job.apply_url)
    if kind == BOARD and job.link_kind == EASY_APPLY:
        return
    job.link_kind = kind


def job_link(job):
    """The link to open, fetch or cache for a job: the employer's (`apply_url`, which only ever
    holds an employer link: posting_links.employer_link and the LinkedIn lookup) when there is
    one, else the job's own. `url` itself is never rewritten; it stays the import and dedup identity."""
    if job is None:
        return None
    # a description fetch passes a stand-in (SimpleNamespace) that carries only `url`
    return getattr(job, "apply_url", None) or getattr(job, "url", None)
