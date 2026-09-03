"""D5 lint: fail on styling that bypasses the primitive layer.

Usage: py v2-testing/tools/stylelint.py [--strict]
Checks frontend/src/v2/*.jsx (except ui.jsx, UiGallery.jsx, ToastLab.jsx) and theme.css:
  1. raw colours (#hex, rgb(/rgba(/hsl() in JSX  → only theme.css may hold them
  2. fontFamily / fontSize literals in JSX style objects (numbers or px strings) outside ui.jsx
  3. borderRadius / boxShadow literals in JSX outside ui.jsx (var(--radius-*) / var(--*-shadow) are fine)
  4. hover classes (v2-bd, v2-bdc, v2-act, v2-row, v2-card, v2-menuitem, v2-hover-*, v2-dashadd, v2-navlink) on elements that are not ui.jsx primitives
  5. style objects matching a primitive role signature (radius 99 + border/background; 1px border + radius 6-12 + surface bg) outside ui.jsx
  6. theme.css: the semantic token block must be identical in the light and dark sections (same names)
Lines carrying `// ui: keep` or `// lint: allow` are exempt (reported separately as allowed).
Exit 1 on any finding unless every finding is allowed.
"""
import re, os, sys, io, collections

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "src", "v2")
SKIP = {"ui.jsx", "UiGallery.jsx", "ToastLab.jsx"}
HOVER = re.compile(r"\bv2-(bdc?|act|row|crow|arow|card|chip|menuitem|hover-[a-z-]+|dashadd|navlink|clhead)\b")
PRIMS = {"Button", "Pill", "IconButton", "Row", "Card", "Band", "DashedAdd", "Input", "Textarea", "SearchInput", "Select", "Menu", "MenuItem", "SectionHead", "Chip", "Tag", "Dot", "Link", "NavLink", "ModalPanel", "Drawer", "HeaderRow", "TableHead", "Label", "Helper", "Heading", "PageTitle", "Spinner", "ShowMore", "Rule", "Surface"}

def strip_block_comments(lines):
    """Blank out every `/* … */` span (the `{/* … */}` JSX form included) while
    keeping the line numbering. A block comment that runs over several lines used
    to leave its continuation lines looking like code — `(theme.css .v2-hover-accent)
    — the stage bands were the last` read as a hover class on a non-primitive —
    because each line was tested on its own. The open/closed state has to be
    carried across lines instead."""
    out, open_ = [], False
    for line in lines:
        buf, i = [], 0
        while i < len(line):
            if open_:
                j = line.find("*/", i)
                if j < 0: break
                open_ = False; i = j + 2
            else:
                j = line.find("/*", i)
                if j < 0: buf.append(line[i:]); break
                buf.append(line[i:j]); open_ = True; i = j + 2
        out.append("".join(buf))
    return out

def lint_jsx(fn, text):
    out = []
    lines = text.splitlines()
    nocomment = strip_block_comments(lines)
    def is_allowed(i):
        # The keep note is written *above* the element it annotates, so the walk
        # back may cross that element's own opening tag — but only that one: a
        # second `^<Tag` means we have stepped into the previous sibling and the
        # note is not ours. When the flagged line carries its own `<Tag`, the
        # element starts on this line and no crossing is allowed at all.
        crossed = bool(re.search(r"<[A-Za-z]", lines[i - 1]))
        for j in range(i - 1, max(-1, i - 8), -1):
            if "ui: keep" in lines[j] or "lint: allow" in lines[j]: return True
            if j < i - 1 and re.search(r"^\s*<[A-Za-z]", lines[j]):
                if crossed: break
                crossed = True
        return False
    for i, line in enumerate(lines, 1):
        allowed = is_allowed(i)
        if re.match(r"^\s*(//|/\*|\*|\{/\*)", line): continue  # comment lines
        line = nocomment[i - 1]
        code = re.sub(r"//.*$", "", line) if "//" in line and "http" not in line else line
        if re.search(r"(?<![\w-])#[0-9a-fA-F]{3,8}\b", code) and "var(--" not in code and "href" not in code:
            out.append((i, "raw-colour", allowed, line.strip()[:120]))
        if re.search(r"\brgba?\(|\bhsla?\(", code):
            out.append((i, "raw-colour", allowed, line.strip()[:120]))
        m = re.search(r"fontSize:\s*(?:'?\d[\d.]*(?:px)?'?)", code)
        if m and "var(--t-" not in code and re.search(r"(background|border|borderRadius|boxShadow):", code):
            out.append((i, "font-size-with-design-keys", allowed, line.strip()[:120]))
        if re.search(r"fontFamily:\s*'(?!var\()", code):
            out.append((i, "font-family-literal", allowed, line.strip()[:120]))
        if re.search(r"borderRadius:\s*\d", code) and "var(--radius" not in code:
            out.append((i, "radius-literal", allowed, line.strip()[:120]))
        if re.search(r"boxShadow:\s*'(?!var\()", code):
            out.append((i, "shadow-literal", allowed, line.strip()[:120]))
        if HOVER.search(code):
            tag = re.search(r"<([A-Z][A-Za-z]*)\b", code)
            if not (tag and tag.group(1) in PRIMS):
                out.append((i, "hover-class-on-non-primitive", allowed, line.strip()[:120]))
        # matches the token form too: tokenising `99` must not be a way to make a
        # hand-rolled pill invisible to the rule.
        if re.search(r"borderRadius:\s*(99\b|'var\(--radius-control\)')", code) and re.search(r"\b(background|border):", code):
            out.append((i, "pill-shaped-inline", allowed, line.strip()[:120]))
    return out

def lint_css(text):
    out = []
    blocks = re.findall(r"\.jn-v2(\[data-theme=\"dark\"\])?\s*\{([^}]*)\}", text, re.S)
    names = []
    for dark, body in blocks:
        names.append((bool(dark), set(re.findall(r"(--[a-z0-9-]+)\s*:", body))))
    light = set().union(*[n for d, n in names if not d]) if any(not d for d, _ in names) else set()
    dark = set().union(*[n for d, n in names if d]) if any(d for d, _ in names) else set()
    INVARIANT = {"--sans", "--serif", "--mono", "--knob", "--faint", "--iframe-bg", "--rail-active", "--rail-hover", "--rail-ink", "--rail-line", "--on-rail-dim", "--on-rail-line", "--on-rail-sep"}  # same in both themes by design
    sem = {n for n in light | dark if not re.match(r"--(t-|radius-)", n) and n not in INVARIANT}
    only_light = sorted(n for n in sem if n in light and n not in dark and not n.startswith("--t-"))
    only_dark = sorted(n for n in sem if n in dark and n not in light)
    if only_light: out.append(("theme.css", "token-missing-in-dark", ", ".join(only_light[:30])))
    if only_dark: out.append(("theme.css", "token-missing-in-light", ", ".join(only_dark[:30])))
    return out

def main():
    findings = []; allowed = []
    for fn in sorted(os.listdir(ROOT)):
        if not fn.endswith(".jsx") or fn in SKIP: continue
        for i, kind, ok, snippet in lint_jsx(fn, io.open(os.path.join(ROOT, fn), encoding="utf-8").read()):
            (allowed if ok else findings).append((fn, i, kind, snippet))
    css = lint_css(io.open(os.path.join(ROOT, "theme.css"), encoding="utf-8").read())
    by = collections.Counter(k for _, _, k, _ in findings)
    print(f"stylelint: {len(findings)} findings ({dict(by)}), {len(allowed)} allowed, {len(css)} css")
    for fn, i, kind, snippet in findings[:400]: print(f"  {fn}:{i} {kind}: {snippet}")
    for f, kind, detail in css: print(f"  {f} {kind}: {detail}")
    sys.exit(1 if findings or css else 0)

if __name__ == "__main__":
    main()
