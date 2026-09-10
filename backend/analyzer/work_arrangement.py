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

# "remote" as a technical term, not a work arrangement.
_NOISE = re.compile(
    r"remote\s+(?:state|access|desktop|server|servers|host|hosts|machine|machines|"
    r"repositor(?:y|ies)|branch|branches|dev\s+environment|development\s+environment|"
    r"execution|procedure|call|calls|sensing|lifecycle|monitoring|management|"
    r"support|control|attacker|code\s+execution|backend|backends|endpoint|endpoints|"
    r"telemetry|device|devices|config|configuration|url|origin)"
    r"|(?:git|ssh|rdp|vpn|tailscale|terraform|tofu)\s+remote"
    r"|remote[- ]first\s+(?:culture|team|teams|company)", re.I)

# "hybrid" as a technical term, not a work arrangement.
_HYBRID_NOISE = re.compile(
    r"hybrid[- ](?:cloud|deployment|deployments|infrastructure|architecture|"
    r"network|networks|storage|search|encryption|app|apps|application|"
    r"applications|mesh|environment|environments|setup\s+of\s+servers)"
    r"|(?:cloud|on[- ]?prem(?:ise)?s?|multi[- ]cloud)\s+(?:and\s+)?hybrid", re.I)

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


def extract_arrangement(location: str = None, title: str = None,
                        description: str = None, structured=None) -> dict:
    """Run the cascade. The first tier that resolves wins."""
    value = from_structured(structured)
    if value:
        return {"arrangement": value, "arrangement_source": "structured", "snippet": None}

    value = from_token(location)
    if value:
        return {"arrangement": value, "arrangement_source": "location", "snippet": location}

    value = from_token(title)
    if value:
        return {"arrangement": value, "arrangement_source": "title", "snippet": title}

    value, snippet = from_description(description)
    if value:
        return {"arrangement": value, "arrangement_source": "description", "snippet": snippet}

    return {"arrangement": None, "arrangement_source": None, "snippet": None}


def apply_arrangement_to_job(job, structured=None) -> None:
    """Set `job.remote` from the cascade; leave it alone when already set.

    `Job.remote` is a three-state boolean. `True` means the posting is remote,
    `False` means it is hybrid or onsite, and `None` means no source resolved it.
    A filter for remote work therefore reads `remote IS TRUE`, and a filter for
    on-location work reads `remote IS FALSE` - neither one sweeps in the
    unresolved jobs.
    """
    if job.remote is not None:
        return

    result = extract_arrangement(
        location=job.location,
        title=job.title,
        description=job.description,
        structured=structured,
    )
    arrangement = result["arrangement"]
    if arrangement is None:
        return
    job.remote = arrangement == REMOTE
