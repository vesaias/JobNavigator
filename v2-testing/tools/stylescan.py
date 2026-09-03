"""D1 static scan: classify every inline style object in frontend/src/v2/*.jsx by role.

Usage: py v2-testing/tools/stylescan.py [--out v2-testing/round-design/scan.md] [--json path]

No LLM, no browser. Parses `style={{ ... }}` objects (one level, template-literal values
kept verbatim), pairs them with the element's className/tag, derives a signature from the
style keys that matter for design consistency, and groups sites by role and signature.
"""
import re, os, sys, json, collections, io

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "src", "v2")
KEEP = ["background", "backgroundColor", "color", "border", "borderColor", "borderBottom", "borderTop", "borderLeft",
        "borderRadius", "boxShadow", "fontFamily", "fontSize", "fontWeight", "lineHeight", "height", "padding",
        "letterSpacing", "textTransform", "opacity", "cursor"]
HOVER_CLASSES = ["v2-bdc", "v2-bd", "v2-act", "v2-row", "v2-crow", "v2-arow", "v2-card", "v2-chip", "v2-menuitem",
                 "v2-hover-accent", "v2-hover-accent-text", "v2-hover-bad", "v2-hover-bad-text", "v2-hover-bad-bdc",
                 "v2-navlink", "v2-navdark", "v2-anchor", "v2-dashadd", "v2-clhead", "v2-themebtn", "v2-rail", "v2-welcomestep"]

def norm(v):
    v = v.strip()
    v = re.sub(r"\s+", " ", v)
    return v

def parse_style(src):
    """Return dict of key -> raw value for a `{ ... }` style body (balanced, one object)."""
    out = {}
    depth = 0; key = None; buf = ""; i = 0; instr = None
    body = src
    tokens = []
    # split on top-level commas
    cur = ""; d = 0; q = None
    for ch in body:
        if q:
            cur += ch
            if ch == q: q = None
            continue
        if ch in "'\"`": q = ch; cur += ch; continue
        if ch in "([{": d += 1
        if ch in ")]}": d -= 1
        if ch == "," and d == 0:
            tokens.append(cur); cur = ""; continue
        cur += ch
    if cur.strip(): tokens.append(cur)
    for t in tokens:
        t = t.strip()
        if not t or t.startswith("..."):
            if t.startswith("..."): out.setdefault("__spread__", []).append(t[3:].strip())
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*|'[^']+'|\"[^\"]+\")\s*:\s*(.*)$", t, re.S)
        if not m: continue
        k = m.group(1).strip("'\""); out[k] = norm(m.group(2))
    return out

def find_styles(text):
    """Yield (line, tag, className, style_dict) for every JSX element carrying style={{...}}."""
    for m in re.finditer(r"<([A-Za-z][A-Za-z0-9.]*)\b", text):
        tag = m.group(1); start = m.end()
        # find the end of the opening tag (naive: first '>' not inside braces/strings)
        d = 0; q = None; j = start
        while j < len(text):
            ch = text[j]
            if q:
                if ch == q: q = None
            elif ch in "'\"`": q = ch
            elif ch == "{": d += 1
            elif ch == "}": d -= 1
            elif ch == ">" and d == 0: break
            j += 1
        attrs = text[start:j]
        sm = re.search(r"style=\{\{", attrs)
        if not sm: continue
        # balanced extraction of the style object
        k = sm.end(); d = 2; q = None; body_start = k
        while k < len(attrs) and d > 0:
            ch = attrs[k]
            if q:
                if ch == q: q = None
            elif ch in "'\"`": q = ch
            elif ch == "{": d += 1
            elif ch == "}": d -= 1
            k += 1
        body = attrs[body_start:k - 2]
        cm = re.search(r"className=(?:\"([^\"]*)\"|\{([^}]*)\})", attrs)
        cls = (cm.group(1) or cm.group(2) or "").strip() if cm else ""
        line = text.count("\n", 0, m.start()) + 1
        yield line, tag, cls, parse_style(body)

def _num(v):
    try: return float(str(v).strip("'\"px"))
    except Exception: return None

def role_of(tag, cls, st):
    bg = st.get("background", st.get("backgroundColor", "")); bd = st.get("border", ""); rad = st.get("borderRadius", "")
    h = st.get("height", ""); fs = st.get("fontSize", ""); cur = st.get("cursor", ""); pos = st.get("position", "")
    hover = next((c for c in HOVER_CLASSES if c in cls), "")
    if "inset: 0" in json.dumps(st) or (pos == "'fixed'" and st.get("inset")): return "scrim"
    if tag in ("input", "textarea", "select") or "cellInput" in json.dumps(st.get("__spread__", [])) or "BOX" in json.dumps(st.get("__spread__", [])): return "input"
    if rad == "99" and "--accent)" in bg and "--accent-ink" in st.get("color", ""): return "btn-primary"
    if rad == "99" and cur == "'pointer'" and bd: return "pill"
    if rad == "99" and ("--bad" in bg or "--warn" in bg): return "btn-danger"
    if rad == "99" and h in ("26", "28", "30", "31", "33", "36") and bd: return "pill"
    if rad == "99" and h in ("22", "24", "26", "28", "30", "36") and (st.get("width") == h): return "icon-btn"
    if hover in ("v2-row", "v2-crow", "v2-arow"): return "row"
    if hover == "v2-card" or (bd and rad in ("8", "9", "10", "12", "14") and "--surface" in bg and cur == "'pointer'"): return "card"
    if hover == "v2-act" and "dashed" in bd: return "band"
    if hover == "v2-dashadd" or "dashed" in bd: return "dashed-add"
    if hover == "v2-menuitem" or (rad in ("6", "7") and cur == "'pointer'" and h == "" and "7px 11px" in st.get("padding", "")): return "menu-item"
    if hover in ("v2-hover-accent", "v2-clhead") and cur == "'pointer'": return "section-head"
    if hover == "v2-chip": return "chip"
    if rad == "99" and fs in ("10", "10.5", "11") and not cur: return "tag"
    if hover in ("v2-navlink", "v2-anchor", "v2-hover-accent-text") or (cur == "'pointer'" and "--accent)" in st.get("color", "") and not bd): return "link"
    if pos == "'fixed'" or ("boxShadow" in st and "--shadow-modal" in st.get("boxShadow", "")): return "modal-panel"
    if "--shadow-menu" in st.get("boxShadow", ""): return "menu"
    if "--shadow-drawer" in st.get("boxShadow", ""): return "drawer"
    if "--shadow-toast" in st.get("boxShadow", ""): return "toast"
    if st.get("textTransform") == "'uppercase'" and st.get("letterSpacing"): return "label"
    if fs in ("10.5", "11", "11.5") and "--muted" in st.get("color", "") and not cur: return "helper-text"
    if bd and rad and "--surface" in bg: return "card-static"
    keys = set(st) - {"__spread__"}
    text_keys = {"color", "fontSize", "fontFamily", "fontWeight", "lineHeight", "letterSpacing", "textTransform", "fontStyle", "whiteSpace", "overflow", "textOverflow", "textAlign", "minWidth", "maxWidth", "flex", "marginLeft", "marginTop", "marginBottom", "marginRight", "display", "alignItems", "gap"}
    design_keys = {"background", "backgroundColor", "color", "border", "borderColor", "borderBottom", "borderTop", "borderLeft", "borderRadius", "boxShadow", "fontFamily", "fontSize", "fontWeight", "lineHeight", "letterSpacing", "textTransform", "opacity", "cursor", "height"}
    if not (keys & design_keys): return "layout"
    ff = st.get("fontFamily", "")
    if "--serif" in ff and (_num(fs) or 0) >= 24: return "page-title"
    if "--serif" in ff: return "heading"
    if "1.5px solid var(--accent)" in bd and rad == "99": return "spinner"
    if h == "1" and bg: return "rule"
    if st.get("borderBottom") and st.get("padding") and not cur and not bg: return "header-row"
    if keys <= text_keys:
        if st.get("textTransform") == "'uppercase'": return "label"
        if fs and (_num(fs) or 99) <= 11.5 and ("--muted" in st.get("color", "") or "--faint" in st.get("color", "")): return "helper-text"
        if "--mono" in ff: return "mono-text"
        return "text"
    if bg and not bd and not cur and rad in ("", "0"): return "surface-block"
    if rad == "99" and h and not cur and (bg or bd): return "dot-or-badge"
    return "unclassified"

def signature(st):
    return tuple((k, st[k]) for k in KEEP if k in st)

def main():
    out = "v2-testing/round-design/scan.md"; js = None
    a = sys.argv[1:]
    if "--out" in a: out = a[a.index("--out") + 1]
    if "--json" in a: js = a[a.index("--json") + 1]
    groups = collections.defaultdict(lambda: collections.defaultdict(list))
    total = 0
    for fn in sorted(os.listdir(ROOT)):
        if not fn.endswith(".jsx"): continue
        text = io.open(os.path.join(ROOT, fn), encoding="utf-8").read()
        for line, tag, cls, st in find_styles(text):
            total += 1
            r = role_of(tag, cls, st)
            groups[r][(signature(st), next((c for c in HOVER_CLASSES if c in cls), ""))].append(f"{fn}:{line}")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    o = io.StringIO(); w = o.write
    w("# D1 static scan — inline style objects by role\n\n")
    w(f"{total} `style={{{{…}}}}` objects across `frontend/src/v2/*.jsx`. Roles are heuristic; the `unclassified` list is for manual triage. Each row = one distinct signature (design-relevant keys only) + hover class; sites are `file:line`.\n\n")
    w("| role | signatures | sites |\n|---|---|---|\n")
    for r in sorted(groups, key=lambda r: -sum(len(v) for v in groups[r].values())):
        w(f"| {r} | {len(groups[r])} | {sum(len(v) for v in groups[r].values())} |\n")
    for r in sorted(groups, key=lambda r: -sum(len(v) for v in groups[r].values())):
        w(f"\n## {r} — {len(groups[r])} signatures\n\n")
        for (sig, hover), sites in sorted(groups[r].items(), key=lambda kv: -len(kv[1])):
            desc = "; ".join(f"{k}: {v}" for k, v in sig) or "(no design keys)"
            w(f"- **{len(sites)} sites** · hover `{hover or '—'}` · `{desc[:400]}`\n  - {', '.join(sites[:40])}{' …' if len(sites) > 40 else ''}\n")
    io.open(out, "w", encoding="utf-8", newline="\n").write(o.getvalue())
    if js:
        io.open(js, "w", encoding="utf-8").write(json.dumps({r: [{"sig": dict(s), "hover": h, "sites": v} for (s, h), v in g.items()] for r, g in groups.items()}, indent=1))
    print(f"{out}: {total} objects, {len(groups)} roles; " + ", ".join(f"{r} {len(g)}sig/{sum(len(v) for v in g.values())}" for r, g in sorted(groups.items(), key=lambda kv: -sum(len(v) for v in kv[1].values()))[:8]))

if __name__ == "__main__":
    main()
