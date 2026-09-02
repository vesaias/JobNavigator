import re, glob, collections, io, os
os.chdir(r"V:\JTrakProject")
ups = {"v2-testing/stage3/companies.md": ("COMP-01", "fixed + verified after rebuild (drawer stays open on PATCH 500, inline \"Save failed — nothing was changed\", error toast; Drawer `save` awaits `patchCompany`, which now returns true/false)"),
       "v2-testing/stage3/persona-stats.md": ("PERS-01", "fixed + verified after rebuild (`Persona.jsx` qa memo accepts list, legacy dict → pairs, anything else → []; dict qa_bank rendered with 0 page errors)"),
       "v2-testing/stage3/resumes.md": ("RES-01", "fixed + verified after rebuild (`ResumeEditor.jsx:250` autosave catch → error toast \"Save failed — your last edit is not stored\", `savedAt` cleared; measured on PATCH 500)")}
for f, (fid, new) in ups.items():
    s = open(f, encoding="utf-8").read()
    m = re.search(r"(^### " + fid + r" ·.*?\*\*Status\*\*\s*)([^\n]*)", s, re.S | re.M)
    assert m, fid
    s = s[:m.start(2)] + new + s[m.end(2):]
    open(f, "w", encoding="utf-8").write(s); print("updated", fid)

sev = collections.Counter(); status = collections.Counter(); rows = []; per = collections.OrderedDict()
files = sorted(glob.glob("v2-testing/stage3/*.md")) + ["v2-testing/FINDINGS.md", "v2-testing/stage5/cross-cutting.md"]
for f in files:
    if f.endswith("BRIEF.md") or f.endswith("REVERIFY.md"): continue
    s = open(f, encoding="utf-8").read(); name = f.replace("\\", "/").split("/")[-1]
    c = collections.Counter()
    for m in re.finditer(r"^### ([A-Z]+-\d+) · (P[1-4]) · ([^\n]*)\n((?:(?!^### ).*\n?)*)", s, re.M):
        fid, p, title, body = m.groups(); st = re.search(r"\*\*Status\*\*\s*([^\n]*)", body); st = (st.group(1) if st else "").lower()
        kind = "fixed" if st.startswith("fixed") else ("decision" if "needs decision" in st or "needs your" in st else "logged")
        sev[p] += 1; status[kind] += 1; c[p] += 1; c[kind] += 1; rows.append((fid, p, kind, title.strip()))
    per[name] = c
fixed_ids = [r for r in rows if r[2] == "fixed"]
p1 = [r for r in rows if r[1] == "P1"]; p2open = [r for r in rows if r[1] == "P2" and r[2] != "fixed"]
cant = []
for f in sorted(glob.glob("v2-testing/stage3/*.md")):
    s = open(f, encoding="utf-8").read(); m = re.search(r"## Couldn.t test\s*\n((?:- .*\n?)+)", s)
    if m: cant += [os.path.basename(f).replace(".md", "") + ": " + l[2:].strip() for l in m.group(1).splitlines() if l.startswith("- ")]

o = io.StringIO(); w = o.write
w("# v2 verification pass — REPORT\n\nBranch `v2-redesign`, 2026-09-01 → 2026-09-02. State files: `PLAN.md` (stages), `FINDINGS.md` (cross-cutting F-nnn), `stage3/<screen>.md` (per-screen findings), `stage4/settings-roundtrip.md`, `stage5/cross-cutting.md`, `stage3/REVERIFY.md` (post-rebuild confirmation), `inventory/` (every route, control, endpoint and settings key), `artifacts/` (gitignored raw JSON + screenshots).\n\n")
w("## Totals\n\n| Severity | Total | Fixed | Needs your decision | Logged only |\n|---|---|---|---|---|\n")
for p in ("P1", "P2", "P3", "P4"):
    rs = [r for r in rows if r[1] == p]
    w(f"| {p} | {len(rs)} | {sum(1 for r in rs if r[2]=='fixed')} | {sum(1 for r in rs if r[2]=='decision')} | {sum(1 for r in rs if r[2]=='logged')} |\n")
w(f"| **All** | **{len(rows)}** | **{status['fixed']}** | **{status['decision']}** | **{status['logged']}** |\n\n")
w("| Area | Findings | P1 | P2 | P3 | P4 | fixed |\n|---|---|---|---|---|---|---|\n")
for n, c in per.items(): w(f"| {n} | {c['P1']+c['P2']+c['P3']+c['P4']} | {c['P1']} | {c['P2']} | {c['P3']} | {c['P4']} | {c['fixed']} |\n")
w("\n## The five P1s — all fixed and re-verified on the rebuilt bundle\n")
for r in p1: w(f"- **{r[0]}** — {r[3]}\n")
w("\n## Fixed in this pass (source, then verified live or on the rebuilt bundle)\n")
for r in fixed_ids: w(f"- {r[0]} ({r[1]}) — {r[3]}\n")
w("\n### Cross-cutting fixes not tied to one finding id\n- Toast system mounted on Searches, Companies, Applications, Persona and Stats (every failure there was console-only); Searches' helper used `text:` instead of `msg:` (blank toasts) — fixed.\n- Six dead hover rules in `theme.css` hardened with `!important` (rail, menu items, anchors, navlinks, `.v2-hover-accent`), plus a `--rail-hover` token for the footer ◐.\n- Backend: `DataError` → 404 handler for malformed ids on every route; `flag_modified` on Résumé and Persona JSON PATCHes; `create_company` persists `aliases` + `auto_scoring_depth`; per-search `trigger_url` pointed at a real endpoint.\n- Docs: HANDOVER and CLAUDE.md said the backend hot-reloads — it does not (no `--reload`); corrected.\n\n")
w("## Open P2s that need you (%d)\n" % len(p2open))
for r in p2open: w(f"- {r[0]} — {r[3]}\n")
w("\n## Decisions that close many findings at once\n1. **Half-pixel rows (F-009)** — a systematic line-height pass (~40–60 one-line edits) or accept as backlog. Closes the FEED-02 residue, SRCH-07, APPS-08, CL-09/10, PERS-11.\n2. **Design-vs-code deviations (~110 P3/P4)** — most look like your deliberate consistency choices (unified accent hovers, lifted rail dim, widened Settings rows, 980 vs 880 px modals). A yes/no per screen report closes them.\n3. **`--reload` in the backend Dockerfile (F-006)** — dev convenience vs prod behaviour.\n4. **Feed first-run copy (F-010)** and the `open roles` label over an unfiltered list (FEED-01).\n5. **Interview time stored as UTC (APPS-03)** — one-line client fix that changes the wire format.\n6. **`POST /applications` upsert-by-job (APPS-04)** silently overwrites notes/stage on re-log.\n\n")
w("## Verified clean (no finding)\n- 587 backend tests green before and after all backend edits.\n- Console clean on 23 routes × 2 themes on the real DB and again on an empty DB (46 + 46 loads).\n- All 74 mutable settings keys round-trip and bind; 7 timing keys reach the scheduler.\n- Every rail/header/Stats count agrees; background jobs return 409 on duplicate, survive navigation, and are marked failed on restart.\n- v1 routes load without errors on the shared backend after every backend change (Stage 6).\n\n")
w("## Couldn't test (%d items, from the screen reports)\n" % len(cant))
for c in cant: w(f"- {c}\n")
w("\n## Data\nReal DB used throughout; every agent's scratch rows deleted (0 `ZZTEST` rows at each wave end). The overnight scheduled cleanup deleted 69 stale skipped jobs (normal). **Final step: restored from `backups/v2testing_baseline_20260901_2345.dump`** — see PLAN Stage 7.\n\n## Not done / deferred\n- Résumés design fidelity was measured against `Resumes Home D`; you named `Resumes Shelf` canonical afterwards — the RES P3 geometry items need a re-check against Shelf (decoded to `design/Resumes Shelf.dc.html`).\n- The `/v2/toasts` lab page and route are still present (your call to delete).\n- Real LLM runs: 2 accidental scores (Feed) + 1 generation + 1 regenerate (Cover Letters); no tailor run — the tailor pending→review flow was verified with interception only.\n")
open("v2-testing/REPORT.md", "w", encoding="utf-8").write(o.getvalue())
print("REPORT.md written:", len(rows), "findings;", dict(status), dict(sev))

p = "frontend/src/v2/HANDOVER.md"; s = open(p, encoding="utf-8").read()
if "v2-testing/REPORT.md" not in s:
    s = s.replace("## The job now: a deep testing pass", "## The testing pass (2026-09-02) — done\n\nResults live in `v2-testing/REPORT.md` (totals, P1s, open decisions), `v2-testing/FINDINGS.md` + `v2-testing/stage3/*.md` (every finding with repro + measurement), `v2-testing/PLAN.md` (what was and wasn't covered). Read those before touching a screen.\n\n## The job then: a deep testing pass", 1)
    open(p, "w", encoding="utf-8").write(s); print("handover pointer added")
