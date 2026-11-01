"""himalayas.app source: remote jobs from every field, read from the documented public API.

Every job is remote, so a search has no Remote or Location: Country keeps the jobs open to that
country, worldwide ones included. The API terms ask to send applicants through `applicationLink`,
so that is the stored URL. It is a Himalayas page (136 of 136 sampled on 2026-10-31), so the job is
a Board link; a link that leaves Himalayas needs no `apply_url` to be Direct, as `url` holds it.
"""
import httpx

from backend.analyzer.work_arrangement import REMOTE
from backend.models.db import Search
from backend.scraper._shared import job_boards
from backend.scraper._shared.html_text import html_to_text
from backend.scraper._shared.job_boards import (Board, BoardError, annual_usd, country_name, iso_from_ts,
                                                make_row, term_of, too_old)

_SEARCH = "https://himalayas.app/jobs/api/search"
_PAGE = 20            # fixed by the API
_MAX_PAGES = 25


def _row(j: dict) -> dict:
    places = [p for p in j.get("locationRestrictions") or [] if p]
    period = "ANNUAL" if str(j.get("salaryPeriod") or "").lower() == "annual" else j.get("salaryPeriod")
    sal_min, sal_max = annual_usd(j.get("minSalary"), j.get("maxSalary"), period, j.get("currency"))
    return make_row(
        title=j.get("title"), company=j.get("companyName") or "",
        # The API terms ask to send applicants through applicationLink.
        url=j.get("applicationLink") or j.get("guid") or "",
        location="Remote: " + ", ".join(places) if places else "Remote (worldwide)",
        description=html_to_text(j.get("description") or ""),
        salary_min=sal_min, salary_max=sal_max, arrangement=REMOTE,
        posted=iso_from_ts(j.get("pubDate")))


async def _list(client: httpx.AsyncClient, search: Search, limit: int) -> list:
    """Country keeps the jobs open to that country (the API takes the English name). Results
    come newest first, so paging stops at the first job older than Hours old."""
    params = {"q": term_of(search), "sort": "recent"}
    country = country_name(search)
    if country:
        params["country"] = country
    rows = []
    for page in range(1, _MAX_PAGES + 1):
        resp = await client.get(_SEARCH, params=dict(params, page=page))
        if resp.status_code >= 400:
            raise BoardError(f"HTTP {resp.status_code} from the Himalayas API")
        jobs = resp.json().get("jobs") or []
        batch = [_row(j) for j in jobs]
        fresh = [r for r in batch if not too_old(r, search.hours_old)]
        rows += fresh
        if len(jobs) < _PAGE or len(fresh) < len(batch) or len(rows) >= limit:
            break
    return rows[:limit]


BOARDS = {"himalayas": Board("Himalayas", _list)}


async def run(search: Search) -> dict:
    return await job_boards.run(search, BOARDS)


async def preview(search: Search, db) -> dict:
    return await job_boards.preview(search, db, BOARDS)
