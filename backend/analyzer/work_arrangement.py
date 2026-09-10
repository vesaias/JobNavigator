"""Work-arrangement extraction: remote / hybrid / onsite, or None when unknown.

The extractor is a cascade of decreasing confidence:

1. a structured field the source itself provides (jobright `workModel`,
   levels.fyi card token, Lever `workplaceType`, ...)
2. a standalone token in `location`  ("Remote", "Remote - US", "... | Hybrid")
3. a standalone token in `title`     ("Technical Leader (Remote)")
4. an explicit phrase in the job description

Tier 4 is the weakest and carries two guards. `_NOISE` drops "remote" used as a
technical term - in an infrastructure feed "remote state", "remote backends" and
"remote dev environments" outnumber the real matches. `_NEGATED` and
`_CONDITIONAL` drop "we do not offer remote" and "we may consider remote
candidates". A naive substring test (which is what JobSpy's LinkedIn scraper
does) marks about four jobs wrongly for each one it marks correctly.

The cascade never guesses. An unresolved job keeps `None`.
"""
import html as _html
import logging
import re

logger = logging.getLogger("jobnavigator.arrangement")

REMOTE = "remote"
HYBRID = "hybrid"
ONSITE = "onsite"

# Values seen in the structured fields of the sources we read.
_STRUCTURED = {
    "remote": REMOTE, "fully remote": REMOTE, "fullyremote": REMOTE,
    "remote_ok": REMOTE, "work from home": REMOTE, "wfh": REMOTE,
    "hybrid": HYBRID,
    "onsite": ONSITE, "on-site": ONSITE, "on site": ONSITE,
    "in office": ONSITE, "in-office": ONSITE, "office": ONSITE,
    "unspecified": None, "": None,
}

# A token on its own, not a word inside a sentence.
# Word forms scanned inside a string, for "Remote or Hybrid" where one regex
# pass over separators would report only the first.
ARRANGEMENT_WORDS = {
    "remote": REMOTE, "hybrid": HYBRID, "on-site": ONSITE, "onsite": ONSITE,
}

_TOKEN = re.compile(
    r"(?:^|[\s,;·|(\[\-–—])(remote|hybrid|on-?site|work from home|wfh)"
    r"(?:[\s,;·|)\]\-–—]|$)", re.I)

_JD_REMOTE = [
    r"100%\s+remote",
    r"fully[- ]remote",
    r"fully\s+distributed",
    r"this\s+(?:role|position|job)\s+is\s+(?:a\s+)?(?:100%\s+)?remote",
    r"(?:role|position)\s+is\s+available\s+(?:as\s+)?remote",
    r"remote\s+(?:role|position|job|opportunity|opening)",
    r"remote[- ]based",
    r"all\s+roles?\s+(?:\w+\s+){0,4}are\s+(?:global\s+and\s+)?remote",
    r"work\s+from\s+(?:home|anywhere)",
    r"work\s+(?:from\s+)?anywhere\s+in",
    r"located\s+anywhere\s+in",
    r"can\s+live\s+and\s+work\s+anywhere",
    r"home[- ]based\s+(?:role|position)",
    r"locations?\s*:\s*remote",
    r"this\s+is\s+a\s+remote",
]
_JD_HYBRID = [
    r"hybrid\s+(?:role|position|work\s+model|schedule|arrangement|capacity)",
    r"(?:this\s+)?role\s+operates\s+in\s+a\s+hybrid",
    r"is\s+a\s+hybrid\s+model",
    r"hybrid\s+(?:work\s+)?(?:setup|policy)",
    r"blend(?:ing)?\s+(?:of\s+)?in[- ](?:office|person)\s+(?:collaboration\s+)?and\s+remote",
    # "Work Arrangement Hybrid:" - the label form, with no noun after it. Only a
    # colon qualifies; a dash would match "hybrid-cloud".
    r"hybrid\s*:",
    r"(?:work\s+)?(?:arrangement|model|schedule)\s*:?\s*hybrid",
    # "designated days in the office per week" - a count that is not a digit.
    r"days?\s+in\s+(?:the\s+)?office",
    # "in the office per week, Monday, Wednesday and Thursday" - a weekday list.
    r"in\s+(?:the\s+)?office\s+(?:\w+\s+){0,3}(?:mon|tues|wednes|thurs|fri)day",
    r"\d\s*\+?\s*days?\s+(?:per\s+week\s+)?in\s+(?:the\s+)?office",
    r"\d\s*\+?\s*days?\s+(?:a\s+week\s+)?on[- ]site",
    r"(?:one|two|three|four)\s+days?\s+(?:per|a)\s+week\s+in\s+(?:the\s+)?office",
    r"in\s+(?:the\s+)?office\s+(?:for\s+)?(?:one|two|three|four|\d)\s*\+?\s*days?",
]
_JD_ONSITE = [
    r"(?:this\s+)?(?:role|position)\s+is\s+(?:fully\s+)?on[- ]?site",
    r"100%\s+on[- ]?site",
    r"fully\s+in[- ]office",
    r"must\s+be\s+(?:able\s+to\s+)?(?:work\s+)?on[- ]?site",
    r"(?:role|position)\s+is\s+based\s+in\s+(?:our|the)\s+\w+\s+office",
    r"required\s+to\s+work\s+(?:from|in)\s+(?:the\s+)?office",
]

# "remote" as a technical term or part of a product name, not a work
# arrangement. The last group is what a job title does with the word: "Remote
# Site Services Data Center Manager" is an onsite job about remote sites.
_NOISE = re.compile(
    r"remote\s+(?:state|access|desktop|server|servers|host|hosts|machine|machines|"
    r"repositor(?:y|ies)|branch|branches|dev\s+environment|development\s+environment|"
    r"execution|procedure|call|calls|sensing|lifecycle|monitoring|management|"
    r"support|control|attacker|code\s+execution|backend|backends|endpoint|endpoints|"
    r"telemetry|device|devices|config|configuration|url|origin|"
    r"site|sites|assistance|build|builds|special\s+project|patient|patients)"
    r"|(?:git|ssh|rdp|vpn|tailscale|terraform|tofu)\s+remote"
    r"|remote[- ]first\s+(?:culture|team|teams|company)", re.I)

# "hybrid" as a technical term, not a work arrangement.
_HYBRID_NOISE = re.compile(
    r"hybrid[- ](?:cloud|deployment|deployments|infrastructure|architecture|"
    r"network|networks|storage|search|encryption|app|apps|application|"
    r"applications|mesh|environment|environments|setup\s+of\s+servers|"
    r"table|tables|index|indexes|query|queries|vector|vectors)"
    r"|(?:cloud|on[- ]?prem(?:ise)?s?|multi[- ]cloud)\s+(?:and\s+)?hybrid", re.I)

# "onsite" naming the work, not the workplace: "Onsite Construction Manager".
_ONSITE_NOISE = re.compile(
    r"on[- ]?site\s+(?:construction|installation|equipment|repair|repairs|"
    r"service\s+delivery|inspection|inspections|drilling)", re.I)

# The sentence says the job is not remote.
_NEGATED = re.compile(
    r"(?:not|no|isn't|is\s+not|does\s+not\s+(?:offer|support)|won't\s+be|"
    r"cannot\s+be|can't\s+be|nor)\s+(?:\w+\s+){0,3}remote"
    r"|remote\s+(?:work\s+)?is\s+not"
    r"|this\s+is\s+not\s+a\s+remote", re.I)

# "we may consider remote candidates" is not a remote posting.
_CONDITIONAL = re.compile(
    r"(?:may|might|could|open\s+to|willing\s+to|would)\s+"
    r"(?:be\s+)?(?:willing\s+to\s+)?(?:consider|entertain)\s+(?:\w+\s+){0,4}remote", re.I)

# Hybrid runs before remote: a hybrid posting almost always also praises "remote
# work flexibility", and the remote patterns would win on that sentence.
_JD_TIERS = [
    (HYBRID, [re.compile(p, re.I) for p in _JD_HYBRID]),
    (REMOTE, [re.compile(p, re.I) for p in _JD_REMOTE]),
    (ONSITE, [re.compile(p, re.I) for p in _JD_ONSITE]),
]

_CONTEXT = 120  # characters of context each guard inspects around a match


def _strip_html(text: str) -> str:
    if "<" in text and ">" in text:
        return _html.unescape(re.sub(r"<[^>]+>", " ", text))
    return text


def from_structured(value) -> str | None:
    """Read a field the source provides itself. `True`/`False` come from a
    boolean field such as Ashby's `isRemote`, where only `True` is informative -
    `False` means "not flagged remote", not "onsite"."""
    if value is None:
        return None
    if isinstance(value, bool):
        return REMOTE if value else None
    return _STRUCTURED.get(str(value).strip().lower())


def from_token(text: str) -> str | None:
    """Read a standalone token out of a `location` or `title` string."""
    if not text:
        return None
    match = _TOKEN.search(text)
    if not match:
        return None
    return _STRUCTURED.get(match.group(1).lower().replace("on site", "onsite"))


def from_description(description: str) -> tuple[str | None, str | None]:
    """Read an explicit phrase out of the job description.

    Returns (arrangement, snippet). The snippet is ~240 characters of context
    for a UI tooltip. Never write it to a log line: it can carry
    recruiter-confidential text, the same rule `scan_jd_for_h1b_flags` follows.
    """
    if not description:
        return None, None
    text = _strip_html(description)[:30_000]

    for value, patterns in _JD_TIERS:
        for pattern in patterns:
            match = pattern.search(text)
            if not match:
                continue
            start = max(0, match.start() - _CONTEXT)
            end = min(len(text), match.end() + _CONTEXT)
            context = text[start:end]
            if value == REMOTE and (_NOISE.search(context)
                                    or _NEGATED.search(context)
                                    or _CONDITIONAL.search(context)):
                continue
            if value == HYBRID and _HYBRID_NOISE.search(context):
                continue
            return value, " ".join(context.split())
    return None, None


def _tokens_in(text: str) -> set:
    """Every arrangement named in one string: "Remote or Hybrid" gives both."""
    if not text:
        return set()
    found = set()
    for match in _TOKEN.finditer(text):
        value = _STRUCTURED.get(match.group(1).lower().replace("on site", "onsite"))
        if value:
            found.add(value)
    # finditer skips an overlapping second match ("Remote / Hybrid" shares the
    # separator), so a plain word scan catches what it misses.
    for word, value in ARRANGEMENT_WORDS.items():
        if re.search(r"(?<![\w-])%s(?![\w-])" % re.escape(word), text, re.I):
            found.add(value)
    return found


def _denoise(values: set, text: str) -> set:
    """Drop a token the surrounding words disown.

    The description tier has always run these guards; a title needs them just as
    much. "AI Platforms and Hybrid Cloud - REMOTE" is a remote job about hybrid
    cloud, and "Remote Site Services Manager" is not a remote job at all. A
    token dropped here falls through to the next tier, which is the right
    outcome: the cascade never guesses.
    """
    if not values or not text:
        return values
    out = set(values)
    if REMOTE in out and _NOISE.search(text):
        out.discard(REMOTE)
    if HYBRID in out and _HYBRID_NOISE.search(text):
        out.discard(HYBRID)
    if ONSITE in out and _ONSITE_NOISE.search(text):
        out.discard(ONSITE)
    return out


def extract_arrangement(location: str = None, title: str = None,
                        description: str = None, structured=None) -> dict:
    """Run the cascade. The first tier that resolves wins.

    `arrangements` is a set: one posting may be offered several ways, and it has
    to answer each of those filters. `arrangement` names the primary one for a
    caller that wants a single label.
    """
    def _result(values, source, snippet):
        ordered = [v for v in (REMOTE, HYBRID, ONSITE) if v in values]
        return {"arrangements": set(values),
                "arrangement": ordered[0] if ordered else None,
                "arrangement_source": source, "snippet": snippet}

    values = from_structured_set(structured)
    if values:
        return _result(values, "structured", None)

    values = _denoise(_tokens_in(location), location)
    if values:
        return _result(values, "location", location)

    values = _denoise(_tokens_in(title), title)
    if values:
        return _result(values, "title", title)

    value, snippet = from_description(description)
    if value:
        return _result({value}, "description", snippet)

    return {"arrangements": set(), "arrangement": None,
            "arrangement_source": None, "snippet": None}


def from_structured_set(value) -> set:
    """Read a source field that may name more than one arrangement.

    A handler passes either one value ("Hybrid"), or a collection when its board
    exposes independent flags.
    """
    if value is None:
        return set()
    if isinstance(value, (set, list, tuple)):
        return {v for v in (from_structured(item) for item in value) if v}
    single = from_structured(value)
    return {single} if single else set()


def apply_arrangement_to_job(job, structured=None) -> None:
    """Set the arrangement flags from the cascade; leave them alone when set.

    The flags are a set, so a posting offered both ways answers both filters.
    All three NULL is the fourth state, "unknown" - it is not the same as
    "known, and not remote", and no filter may quietly mix the two.

    `job.remote` is written from `arr_remote` for the API's existing parameter.
    """
    if job.arr_remote is not None or job.arr_hybrid is not None             or job.arr_onsite is not None:
        return

    result = extract_arrangement(
        location=job.location,
        title=job.title,
        description=job.description,
        structured=structured,
    )
    found = result["arrangements"]
    if not found:
        return
    job.arr_remote = REMOTE in found
    job.arr_hybrid = HYBRID in found
    job.arr_onsite = ONSITE in found
    job.remote = job.arr_remote
