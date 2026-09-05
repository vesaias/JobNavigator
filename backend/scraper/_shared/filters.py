"""Title/URL filtering helpers + title expression parser: the central "is this a
valid job posting?" gate all scrapers run jobs through before DB insert."""
import json
import re
from urllib.parse import urlparse


def build_search_exclude_sets(db, search) -> tuple[set, set]:
    """Return (global_exclude_set, search_exclude_set) of lowercased company names; the search set adds every active Company's name+aliases when exclude_active_companies is true."""
    from backend.models.db import Setting, Company

    global_row = db.query(Setting).filter(Setting.key == "company_exclude_global").first()
    global_list = []
    if global_row:
        try:
            global_list = json.loads(global_row.value or "[]")
        except (ValueError, TypeError):
            global_list = []
    global_set = {e.lower() for e in global_list if e}

    search_set = {(e or "").lower() for e in (search.company_exclude or []) if e}
    if getattr(search, "exclude_active_companies", False):
        # Only exclude companies with at least one scrape_url — one with no URLs
        # never duplicates this search's results, so excluding it would hide real hits.
        for c in db.query(Company).filter(Company.active == True).all():  # noqa: E712
            if not c.scrape_urls:
                continue
            if c.name:
                search_set.add(c.name.lower())
            for alias in (c.aliases or []):
                if alias:
                    search_set.add(alias.lower())

    return global_set, search_set


# ── Garbage-title filtering ─────────────────────────────────────────────────
# Known garbage strings to discard (case-insensitive exact match)
GARBAGE_TITLES = {
    "apply", "apply now", "contact", "contact us", "search", "search jobs",
    "back", "next", "previous", "filter", "filters", "reset", "clear",
    "sign in", "sign up", "login", "log in", "register", "submit",
    "load more", "show more", "view all", "see all", "close", "menu",
    "home", "about", "about us", "privacy", "terms", "cookie", "cookies",
    "accept", "decline", "subscribe", "follow", "share", "save",
    "join talent network", "join our talent network", "talent network",
    "sign up for alerts", "sign up for job alerts", "job alerts",
    "create job alert", "set up job alert", "email me jobs",
    "explore careers", "explore opportunities", "why work here",
    "our culture", "our values", "benefits", "open roles",
    "university", "universities", "internships", "intern program",
    "early careers", "students", "student programs", "students + early careers",
    "early careers / internships", "application and interview tips",
    "job search",
    "blog", "events", "news", "newsroom", "podcast",
    "learn more", "read more", "find out more", "get started",
    "all locations", "all departments", "all categories",
    "accessibility", "equal opportunity", "eeo", "privacy policy",
    "terms of use", "terms and conditions", "sitemap",
    "careers blog", "my profile", "my account", "my applications",
    "locations", "teams", "departments", "categories",
}

# Substrings that indicate garbage even in longer text
GARBAGE_SUBSTRINGS = [
    "join talent network", "join our talent", "talent community",
    "sign up for job alert", "create job alert", "email me jobs",
    "cookie settings", "cookie preferences", "privacy policy",
    "equal opportunity employer", "© 20", "open roles",
    "life at ",  # "Life at Stripe", "Life at Google", etc.
]

# Language names used in locale switchers — these are navigation, not job titles
_LOCALE_NAMES = {
    "nederlands", "deutsch", "français", "español", "português", "italiano",
    "polski", "svenska", "norsk", "dansk", "suomi", "čeština", "română",
    "magyar", "türkçe", "bahasa indonesia", "bahasa melayu", "tiếng việt",
    "english", "english (us)", "english (uk)",
    "日本語", "한국어", "中文", "简体中文", "繁體中文", "ภาษาไทย", "العربية", "עברית",
}


# ── Boolean expression parser for title_include_expr ──────────────────────────

def _tokenize(expr: str) -> list[str]:
    tokens = []
    i = 0
    while i < len(expr):
        if expr[i].isspace():
            i += 1
        elif expr[i] == '(':
            tokens.append('(')
            i += 1
        elif expr[i] == ')':
            tokens.append(')')
            i += 1
        elif expr[i] == '"':
            j = expr.index('"', i + 1) if '"' in expr[i + 1:] else len(expr)
            tokens.append(expr[i + 1:j])
            i = j + 1
        else:
            j = i
            while j < len(expr) and expr[j] not in '() \t' and expr[j] != '"':
                j += 1
            word = expr[i:j]
            if word.upper() in ('AND', 'OR'):
                tokens.append(word.upper())
            else:
                tokens.append(word)
            i = j
    return tokens


def _parse_expr(tokens, pos):
    left, pos = _parse_and(tokens, pos)
    while pos < len(tokens) and tokens[pos] == 'OR':
        pos += 1
        right, pos = _parse_and(tokens, pos)
        left = ('OR', left, right)
    return left, pos


def _parse_and(tokens, pos):
    left, pos = _parse_atom(tokens, pos)
    while pos < len(tokens) and tokens[pos] == 'AND':
        pos += 1
        right, pos = _parse_atom(tokens, pos)
        left = ('AND', left, right)
    return left, pos


def _parse_atom(tokens, pos):
    if pos >= len(tokens):
        return ('WORD', ''), pos
    if tokens[pos] == '(':
        pos += 1
        node, pos = _parse_expr(tokens, pos)
        if pos < len(tokens) and tokens[pos] == ')':
            pos += 1
        return node, pos
    return ('WORD', tokens[pos]), pos + 1


def _eval_expr(node, title_lower):
    if node[0] == 'WORD':
        return node[1].lower() in title_lower
    elif node[0] == 'AND':
        return _eval_expr(node[1], title_lower) and _eval_expr(node[2], title_lower)
    elif node[0] == 'OR':
        return _eval_expr(node[1], title_lower) or _eval_expr(node[2], title_lower)
    return True


def match_title_expr(expr: str, title: str) -> bool:
    tokens = _tokenize(expr)
    if not tokens:
        return True
    tree, _ = _parse_expr(tokens, 0)
    return _eval_expr(tree, title.lower())


# ── Job validation ────────────────────────────────────────────────────────────

def _validate_job(title: str, url: str) -> str | None:
    """Validate a scraped job entry. Returns None if valid, or rejection reason."""
    if not title or len(title.strip()) < 10:
        return f"Title too short ({len((title or '').strip())} chars)"
    title_clean = title.strip()
    title_lower = title_clean.lower()
    if title_lower in GARBAGE_TITLES:
        return "Garbage title (exact match)"
    for sub in GARBAGE_SUBSTRINGS:
        if sub in title_lower:
            return f"Garbage substring: '{sub}'"
    if title_lower in _LOCALE_NAMES:
        return "Locale/language name"
    if re.match(r'^[\d\s\-\.]+$', title_clean):
        return "Title is just numbers/symbols"

    if not url:
        return "No URL"
    url_lower = url.lower()
    if not (url_lower.startswith('http://') or url_lower.startswith('https://')):
        # Covers mailto:, javascript:, relative paths — anything non-http(s)
        return "Bad URL scheme"
    parsed = urlparse(url)
    if not parsed.netloc:
        return "No host in URL"
    if parsed.path in ('/', '') and not parsed.query:
        return "Root URL (not a job link)"

    return None


# ── Per-company keyword filters ───────────────────────────────────────────────

def _apply_company_filters(jobs: list[dict], company, global_title_exclude: list = None) -> tuple[list[dict], list[dict]]:
    """Filter jobs using per-company title_include_expr and title_exclude_keywords; returns (kept, rejected)."""
    include_expr = company.title_include_expr
    merged = list(set((company.title_exclude_keywords or []) + (global_title_exclude or [])))
    exclude_kws = [kw.lower() for kw in merged]

    kept = []
    rejected = []
    for j in jobs:
        title_lower = j["title"].lower()
        if any(re.search(r'\b' + re.escape(kw) + r'\b', title_lower) for kw in exclude_kws):
            rejected.append(j)
            continue
        if include_expr and include_expr.strip():
            if not match_title_expr(include_expr, j["title"]):
                rejected.append(j)
                continue
        kept.append(j)
    return kept, rejected
