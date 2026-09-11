"""Generic CSS-selector fallback for career pages with no ATS match: launches a headless browser,
extracts job-card links, paginates, and returns {title, url} dicts filtered through _validate_job."""
import asyncio
import logging
import re
from urllib.parse import urlparse

from backend.scraper._shared.browser import _get_browser, _new_page, _close_page
from backend.scraper._shared.filters import _validate_job
from backend.analyzer.location import CA_REGIONS, COUNTRY_NAMES, US_REGIONS, fold

logger = logging.getLogger("jobnavigator.scraper.ats.generic")


# ── Reading a place off a job card ───────────────────────────────────────────
#
# These boards have no API, so the place is only ever printed on the card beside
# the title: "Sales · Full-time · Singapore", "title | Save | Addison",
# "title | Mountain View, California; San Francisco, California". The card text
# minus the title is therefore a handful of short segments, of which at most one
# or two name a place. Everything here is deliberately conservative: a segment
# that cannot be recognised as a place is dropped, and a card that yields none
# reports no location rather than a guess.

# Every place name the location gazetteer knows, plus the phrases a board prints
# when a posting spans more sites than the card has room for. "Multiple Cities"
# is deliberately absent: the parser reads it as a city, and a city called
# "Multiple Cities" is worse than no place at all.
_PLACE_WORDS = (set(COUNTRY_NAMES) | set(CA_REGIONS) | set(US_REGIONS)
                | {"multiple locations", "various locations"})

# The label a card prints before the place ("… | Location | Sunnyvale").
_PLACE_LABELS = {"location", "locations", "office", "offices", "job location"}
_HINT_LABEL = re.compile(r"^(job\s+)?locations?\s*[:\-]?\s+", re.I)

# Card furniture: a button, a badge, an employment type. None of it is a place.
_NOISE_SEGMENTS = {
    "save", "saved", "save job", "unsave", "apply", "apply now", "easy apply",
    "new", "featured", "hot", "urgent", "view job", "view details", "details",
    "learn more", "read more", "share", "posted", "date posted", "job type",
    "category", "department", "team", "function", "req id", "requisition id",
    "full-time", "full time", "part-time", "part time", "fulltime", "parttime",
    "intern", "internship", "contract", "contractor", "temporary", "permanent",
    "regular", "employee", "student", "graduate", "entry level", "experienced",
}

_MONTHS = "jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec"
_DATE_SEGMENT = re.compile(
    r"^(posted\s+)?("
    rf"(\d{{1,2}}\s+)?({_MONTHS})[a-z]*\.?\s+\d{{1,2}}(,?\s*\d{{4}})?"
    rf"|\d{{1,2}}\s+({_MONTHS})[a-z]*\.?,?\s*\d{{4}}?"
    r"|\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}"
    r"|\d{4}-\d{2}-\d{2}"
    r"|\d+\+?\s+(minute|minutes|hour|hours|day|days|week|weeks|month|months)\s+ago"
    r"|today|yesterday)$", re.I)

_ARRANGEMENT_WORD = re.compile(r"\b(remote|hybrid|on-?site|work from home)\b", re.I)
# A card with no separator at all runs the place straight onto the previous
# word: Coinbase prints "…Business DevelopmentRemote - USA".
_RUN_ON = re.compile(r"(?<=[a-z])(?=(?:Remote|Hybrid|On-?site|Onsite)\b)")
_SEGMENT_SPLIT = re.compile(r"[\n|·•\t]+")
# A place on a card is short; anything longer is prose that happened to have a
# comma in it.
_MAX_SEGMENT = 80
_MAX_PLACES = 3


def _is_date(segment: str) -> bool:
    return bool(_DATE_SEGMENT.match(segment.strip()))


def _looks_like_place(segment: str) -> bool:
    """True when this segment names a place or an arrangement.

    A comma is the strongest signal ("Dallas, US", "Austin, Texas, United States
    of America"); failing that the segment has to be a name the gazetteer knows
    or end in a region code.
    """
    text = segment.strip()
    if not text or len(text) > _MAX_SEGMENT:
        return False
    if any(ch in text for ch in "$©@") or text.lower().startswith("http"):
        return False
    if _is_date(text):
        return False
    folded = fold(text)
    if folded in _NOISE_SEGMENTS:
        return False
    if _ARRANGEMENT_WORD.search(text):
        return True
    if folded in _PLACE_WORDS:
        return True
    # A comma is what separates a place from its region ("Dallas, US", "Austin,
    # Texas, United States of America"). Without one, a trailing two-letter token
    # proves nothing: "Sign In" would read as Indiana.
    if len(re.split(r"\s+", text)) > 12:
        return False
    return "," in text and not text.endswith(".")


def _place_segments(segments: list) -> list:
    """The segments of one card that name a place, in the order printed."""
    kept: list = []
    labelled = False
    for segment in segments:
        text = segment.strip(" -–—,·•")
        if not text:
            continue
        folded = fold(text)
        if folded in _PLACE_LABELS:
            labelled = True
            continue
        if folded in _NOISE_SEGMENTS or _is_date(text) or len(text) > _MAX_SEGMENT:
            labelled = False
            continue
        take = labelled or _looks_like_place(text)
        labelled = False
        if take and text not in kept:
            kept.append(text)
            if len(kept) >= _MAX_PLACES:
                break
    return kept


# What a card prints beside a place: the discipline, the team, the job family.
# The fallback below only fires when one segment is left after these go, so this
# list is what keeps "Sales · Full-time · London" from answering "Sales".
_NON_PLACE_WORDS = {
    "sales", "marketing", "engineering", "design", "product", "product management",
    "program management", "project management", "operations", "business operations",
    "finance", "accounting", "legal", "compliance", "recruiting", "people",
    "human resources", "talent", "support", "customer support", "customer success",
    "research", "data", "data science", "security", "it", "information technology",
    "business development", "corporate functions", "software engineering",
    "machine learning", "consulting", "hardware", "software", "services",
    "software and services", "communications", "growth", "strategy", "partnerships",
    "community", "content", "analytics", "infrastructure", "platform", "solutions",
    "technology", "administration", "facilities", "quality", "manufacturing",
    "supply chain", "health", "education", "public policy", "trust and safety",
    "corporate", "general", "other", "various", "all", "apply now", "apply",
}
# A place written as a proper noun: "London", "NEW YORK", "Sunnyvale".
_PROPER_NOUN = re.compile(r"^[A-Z][A-Za-z.'’-]*(?:\s+[A-Z][A-Za-z.'’-]*){0,3}$")


def _fallback_place(segments: list, title: str = "") -> str | None:
    """The one segment left when a card names its place without punctuating it.

    "Account Executive · Sales · Full-time · London" has no comma, no country and
    no arrangement word, so nothing above recognises London. What it does have is
    exactly one segment left once the buttons, the dates, the employment types
    and the disciplines are gone. One survivor is the whole condition: two would
    mean guessing which of them is the place, and this returns nothing instead.
    """
    candidates = []
    for segment in segments:
        text = segment.strip(" -–—,·•→")
        folded = fold(text)
        if (not text or len(text) > 40 or folded in _NOISE_SEGMENTS
                or folded in _NON_PLACE_WORDS or folded == fold(title)
                or _is_date(text) or any(ch.isdigit() for ch in text)):
            continue
        if not _PROPER_NOUN.match(text) and text != text.upper():
            continue
        if text not in candidates:
            candidates.append(text)
    return candidates[0] if len(candidates) == 1 else None


def _hint_place(hint: str) -> str | None:
    """A card element the board itself classes as the location.

    That class is evidence the card text cannot give, so a bare city name is
    taken from it ("Toronto") where the same word in the card text would be
    ambiguous. The label itself ("Location") and the furniture are still refused.
    """
    # Apple's cell prints its own label above the place: "Location\nSunnyvale".
    text = _HINT_LABEL.sub("", re.sub(r"\s+", " ", hint or "").strip())
    folded = fold(text)
    if (not text or len(text) > _MAX_SEGMENT or _is_date(text)
            or folded in _PLACE_LABELS or folded in _NOISE_SEGMENTS
            or folded in _NON_PLACE_WORDS):
        return None
    if _looks_like_place(text):
        return text
    if len(text) <= 40 and (_PROPER_NOUN.match(text) or text == text.upper()):
        return text
    return None


def _card_place(card_text: str, title: str = "", hint: str = None) -> str | None:
    """The place printed on one job card, as the board printed it, or None.

    `hint` is the text of an element the card itself marks as the location; it
    wins when it reads as a place. Otherwise the card's text minus the title is
    split into segments and the ones that name a place are joined back with the
    separator boards use for a list of them.
    """
    hinted = _hint_place(hint)
    if hinted:
        return hinted

    text = card_text or ""
    if title and title in text:
        text = text.replace(title, "\n", 1)
    text = _RUN_ON.sub("\n", text)
    segments = [re.sub(r"\s+", " ", s).strip() for s in _SEGMENT_SPLIT.split(text)]
    places = _place_segments(segments)
    if not places:
        return _fallback_place(segments, title)
    return "; ".join(places)


def _split_places(location: str) -> list:
    """A card's place text into the several places it lists (Databricks prints
    "Mountain View, California; San Francisco, California")."""
    return [p.strip() for p in (location or "").split(";") if p.strip()]


# Runs in the page: the box around the title link that holds this posting and no
# other, plus the text of whatever element that box marks as the location.
#
# The climb stops at the first ancestor that contains another job's link, which
# is what keeps a list container (eightfold renders one for the whole page) from
# handing every posting its neighbours' places. A second cap on the text length
# stops it walking into the page chrome.
_CARD_JS = """
(el) => {
  const LIMIT = 600;
  const own = el.getAttribute('href');
  const isolated = (node) => {
    for (const a of node.querySelectorAll('a[href]')) {
      if (a === el || el.contains(a) || a.contains(el)) continue;
      if (a.getAttribute('href') === own) continue;
      if ((a.innerText || '').trim().length >= 15) return false;
    }
    return true;
  };
  let card = el;
  let node = el.parentElement;
  for (let hop = 0; hop < 6 && node; hop++) {
    const text = (node.innerText || '').trim();
    if (text.length > LIMIT || !isolated(node)) break;
    card = node;
    node = node.parentElement;
  }
  let hint = null;
  try {
    const locEl = card.querySelector('[class*="location" i], [data-automation-id*="location" i], [itemprop="jobLocation"], [class*="Location"]');
    if (locEl) hint = (locEl.innerText || '').trim().slice(0, 120);
  } catch (e) { hint = null; }
  return {text: (card.innerText || '').slice(0, LIMIT), hint: hint};
}
"""


async def _card_location(el, title: str):
    """Read the place off the card around this title link; never raises."""
    try:
        data = await el.evaluate(_CARD_JS)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    return _card_place(data.get("text") or "", title, data.get("hint"))


# ── Route blocking ───────────────────────────────────────────────────────────

async def _setup_route_blocks(page):
    """Block unwanted endpoints such as the Eightfold similar-positions widget.

    The global SSRF route guard is already installed by ``_new_page``.
    """
    async def _block_handler(route):
        logger.info(f"Blocked request: {route.request.url}")
        await route.abort()
    await page.route(re.compile(r"similar_positions"), _block_handler)


# ── Wait for content ──────────────────────────────────────────────────────────

async def _wait_for_content(page, wait_for_selector: str = None):
    """Wait for page content to render. Uses custom selector if provided, else 3s delay."""
    if wait_for_selector and wait_for_selector.strip():
        try:
            await page.wait_for_selector(wait_for_selector.strip(), timeout=15000)
            await asyncio.sleep(1)  # Extra moment for JS to finish
        except Exception as e:
            logger.warning(f"wait_for_selector '{wait_for_selector}' timed out: {e}")
            await asyncio.sleep(3)  # Fallback
    else:
        await asyncio.sleep(3)


# ── Extract job links from current page ───────────────────────────────────────

async def _extract_job_links_from_page(page, base_url: str, debug: bool = False) -> list[dict]:
    """Extract and validate job links from the currently loaded page; if debug=True, returns
    all found links with their validation status/reason."""
    jobs_by_url = {}      # URL -> job dict (valid jobs)
    rejected = []         # debug: rejected entries

    # Specific selectors first — if these find results, skip the broad ones
    specific_selectors = [
        '[class*="position-card"] a', '[class*="position-title"] a',
        '[data-automation-id="jobTitle"]',
        '.job-listing a', '.job-card a', '.opening a',
        '[data-job] a', '.career-listing a', '[role="listitem"] a',
        'a.js-view-job',
    ]
    # Broad URL-pattern selectors — only used as fallback
    broad_selectors = [
        'a[href*="/jobs/"]', 'a[href*="/job/"]',
        'a[href*="/position"]', 'a[href*="/opening"]', 'a[href*="/role"]',
        'a[href*="/viewjob"]', 'a[href*="/requisition"]',
        'a[href*="eightfold.ai/careers"]',
        'a[href*="/careers/"]',
    ]

    base_parsed = urlparse(base_url)
    seen_hrefs = set()  # track all hrefs we've checked (valid or not)

    # Remove footer/header from DOM to avoid extracting garbage links
    # (keep <nav> — pagination buttons may live inside it)
    await page.evaluate("""
        for (const tag of ['footer', 'header']) {
            document.querySelectorAll(tag).forEach(el => el.remove());
        }
    """)

    async def _run_selectors(selectors):
        for selector in selectors:
            try:
                elements = await page.query_selector_all(selector)
                for el in elements:
                    href = await el.get_attribute("href")
                    if not href:
                        continue

                    if href.startswith("/"):
                        href = f"{base_parsed.scheme}://{base_parsed.netloc}{href}"
                    elif not href.startswith("http"):
                        continue

                    if href in seen_hrefs:
                        continue
                    seen_hrefs.add(href)

                    # Try to get title from a heading element inside the <a>
                    text = None
                    for heading_sel in ('[class*="heading"]', '[class*="title"]', 'h2', 'h3', 'h4'):
                        heading_el = await el.query_selector(heading_sel)
                        if heading_el:
                            text = (await heading_el.inner_text() or "").strip()
                            if text:
                                break
                    if not text:
                        text = (await el.inner_text() or "").strip()
                    if '\n' in text:
                        lines = [l.strip() for l in text.split('\n') if l.strip()]
                        text = lines[0] if lines else ""

                    if not text:
                        if debug:
                            rejected.append({"title": "(empty)", "url": href, "selector": selector, "reason": "No text"})
                        continue

                    reason = _validate_job(text, href)
                    if reason is None:
                        job = {"title": text, "url": href}
                        place = await _card_location(el, text)
                        if place:
                            job["location"] = place
                            job["locations"] = _split_places(place)
                        jobs_by_url[href] = job
                    elif debug:
                        rejected.append({"title": text, "url": href, "selector": selector, "reason": reason})
            except Exception:
                continue

    await _run_selectors(specific_selectors)

    if not jobs_by_url:
        await _run_selectors(broad_selectors)

    if debug:
        return list(jobs_by_url.values()), rejected
    return list(jobs_by_url.values())


# ── Pagination ────────────────────────────────────────────────────────────────

async def _extract_all_pages(page, base_url: str, max_pages: int = 5, debug: bool = False, wait_for_selector: str = None) -> list[dict] | tuple:
    """Extract jobs from current page, then paginate through next pages."""
    all_jobs = []
    all_rejected = []
    pagination_debug = []
    seen_urls = set()

    for page_num in range(max_pages):
        if debug:
            page_jobs, page_rejected = await _extract_job_links_from_page(page, base_url, debug=True)
            all_rejected.extend(page_rejected)
        else:
            page_jobs = await _extract_job_links_from_page(page, base_url)

        # Add only new jobs (not seen on previous pages)
        new_on_page = 0
        for j in page_jobs:
            if j["url"] not in seen_urls:
                seen_urls.add(j["url"])
                all_jobs.append(j)
                new_on_page += 1

        logger.info(f"Page {page_num + 1}: found {len(page_jobs)} links, {new_on_page} new")

        if page_num >= max_pages - 1:
            break

        # Stop if this page found no new jobs (we've exhausted results)
        if new_on_page == 0:
            break

        result = await _click_next_page(page, debug=debug)
        if debug:
            pagination_debug.append({"page": page_num + 1, **result})
            if not result["clicked"]:
                break
        else:
            if not result:
                break

        await asyncio.sleep(2)

    if debug:
        return all_jobs, all_rejected, pagination_debug
    return all_jobs


async def _click_next_page(page, debug: bool = False) -> bool | dict:
    """Try to click a next page or load more button; returns True/False normally,
    or a details dict when debug=True."""
    debug_info = {"clicked": False, "candidates": []}

    # Detect eightfold pages by checking for their CSS module classes in the DOM
    is_eightfold = await page.query_selector('[class*="pagination-module_pagination"]') is not None
    if is_eightfold:
        next_selectors = [
            'button[class*="pagination-module_pagination-next"]',
            'button[aria-label="Next jobs"]',
        ]
    else:
        next_selectors = [
            'button[aria-label*="next" i]',
            'a[aria-label*="next" i]',
            'button[aria-label*="Next" i]',
            'a[aria-label*="Next" i]',
            '[data-automation-id="lnkNextPage"]',
            '.pagination-next a',
            '.pagination a.next',
            'a.next-page',
            'button.next-page',
            'li.next a',
            'button[aria-label*="load more" i]',
            'button[aria-label*="Load more" i]',
            'button[aria-label*="Show more" i]',
        ]

    if debug:
        debug_info["is_eightfold"] = is_eightfold

    # Scroll to bottom to trigger lazy-loaded pagination
    try:
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(1)
    except Exception:
        pass

    for selector in next_selectors:
        try:
            btn = await page.query_selector(selector)
            if btn:
                is_visible = await btn.is_visible()
                is_disabled = await btn.get_attribute("disabled")
                aria_disabled = await btn.get_attribute("aria-disabled")
                tag = await btn.evaluate("el => el.tagName")
                text = await btn.evaluate("el => el.innerText.trim().substring(0, 80)")
                candidate = {
                    "selector": selector, "tag": tag, "text": text,
                    "visible": is_visible, "disabled": bool(is_disabled),
                    "aria_disabled": aria_disabled,
                }
                if debug:
                    debug_info["candidates"].append(candidate)
                if is_visible and not is_disabled and aria_disabled != "true":
                    logger.info(f"Pagination: clicking [{selector}] tag={tag} text='{text}'")
                    try:
                        await btn.click(timeout=5000)
                    except Exception as click_err:
                        logger.warning(f"Pagination: click failed ({click_err}), trying dispatch_event")
                        if debug:
                            candidate["click_error"] = str(click_err)
                        try:
                            await btn.dispatch_event("click")
                        except Exception as de_err:
                            logger.warning(f"Pagination: dispatch_event also failed ({de_err})")
                            if debug:
                                candidate["dispatch_error"] = str(de_err)
                            continue
                    if debug:
                        debug_info["clicked"] = True
                        debug_info["clicked_via"] = candidate
                        return debug_info
                    return True
        except Exception as e:
            logger.warning(f"Pagination: selector {selector} error: {e}")
            continue

    # Text-based fallback — skip for eightfold (avoids false positives)
    text_patterns = ["Next", "Load more", "Show more", "Load More", "Show More"] if not is_eightfold else []
    for text_pat in text_patterns:
        try:
            btn = await page.query_selector(f'button:has-text("{text_pat}")')
            if not btn:
                btn = await page.query_selector(f'a:has-text("{text_pat}")')
            if btn:
                is_visible = await btn.is_visible()
                is_disabled = await btn.get_attribute("disabled")
                tag = await btn.evaluate("el => el.tagName")
                btn_text = await btn.evaluate("el => el.innerText.trim().substring(0, 80)")
                candidate = {
                    "selector": f':has-text("{text_pat}")', "tag": tag, "text": btn_text,
                    "visible": is_visible, "disabled": bool(is_disabled),
                }
                if debug:
                    debug_info["candidates"].append(candidate)
                if is_visible and not is_disabled:
                    box = await btn.bounding_box()
                    if box and box["width"] > 20 and box["height"] > 10:
                        logger.info(f"Pagination: clicking text='{text_pat}' tag={tag}")
                        await btn.click()
                        if debug:
                            debug_info["clicked"] = True
                            debug_info["clicked_via"] = candidate
                            return debug_info
                        return True
        except Exception:
            continue

    logger.info("Pagination: no next button found")
    if debug:
        return debug_info
    return False


# ── Public entry point ───────────────────────────────────────────────────────

async def scrape(url: str, browser=None, max_pages: int = 5, debug: bool = False) -> list[dict] | tuple:
    """Fallback scraper for career pages with no ATS match; launches its own browser if one isn't
    passed, then navigates, waits, extracts links, and paginates."""
    own_browser = browser is None
    pw = None
    if own_browser:
        pw, browser = await _get_browser()
    try:
        page = await _new_page(browser)
        try:
            await _setup_route_blocks(page)
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await _wait_for_content(page)
            result = await _extract_all_pages(page, url, max_pages=max_pages, debug=debug)
            return result
        finally:
            await _close_page(page)
    finally:
        if own_browser and pw is not None:
            await pw.stop()
