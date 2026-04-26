"""Diagnostic: Jaccard similarity between Persona bullets and each of the 4 base
Resumes (PM, PjM, PjM FinTech, TPgM). Writes a markdown report to
docs/persona_vs_resumes_jaccard.md.

Run inside the backend container:
    docker compose exec backend python /app/backend/analyze_persona_vs_resumes.py
"""
import re
from pathlib import Path
from backend.models.db import SessionLocal, Resume, Persona
from backend.api.routes_resumes import (
    _bullet_jaccard, _numeric_anchors, _is_duplicate_bullet,
    _normalize_company, _normalize_title_root,
)


OUTPUT_PATH = Path("/app/docs/persona_vs_resumes_jaccard.md")


def all_bullets_by_role(experience):
    """Group bullets by (normalized_company, title_root). Returns dict of
    (company_norm, title_root) -> [(orig_title, orig_company, bullet_text)]."""
    groups = {}
    for exp in experience or []:
        title = exp.get("title", "")
        company = exp.get("company", "")
        key = (_normalize_company(company), _normalize_title_root(title))
        for b in exp.get("bullets", []) or []:
            groups.setdefault(key, []).append((title, company, b))
    return groups


def render_pair(j_score, has_num, persona_b, resume_b):
    flag = "🔴 DUP" if _is_duplicate_bullet(persona_b, resume_b) else ("🟡 borderline" if j_score >= 0.30 else "🟢 unique")
    num_marker = " (num)" if has_num else ""
    return (f"  - **J={j_score:.2f}{num_marker}** {flag}\n"
            f"    - persona: `{persona_b[:140]}`\n"
            f"    - resume:  `{resume_b[:140]}`\n")


def main():
    db = SessionLocal()
    try:
        persona = db.query(Persona).filter(Persona.id == 1).first()
        if not persona or not persona.resume_content:
            print("No persona resume_content")
            return
        persona_groups = all_bullets_by_role(persona.resume_content.get("experience", []))
        persona_total = sum(len(v) for v in persona_groups.values())

        resumes = db.query(Resume).filter(Resume.is_base == True).order_by(Resume.name).all()
        if not resumes:
            print("No base resumes")
            return

        out = ["# Persona ↔ Base Resumes — Jaccard Bullet Similarity\n"]
        out.append(f"Persona has **{persona_total} bullets** across {len(persona_groups)} roles "
                   f"(grouped by normalized company + title-root).\n")
        out.append("Thresholds used by `_is_duplicate_bullet`:\n")
        out.append("- `J ≥ 0.40` when both bullets share a numeric anchor (e.g. `$350M`, `40%`)\n")
        out.append("- `J ≥ 0.50` lexical only (no shared number)\n\n")

        # Per-resume summary table
        summary_rows = []

        for r in resumes:
            jd = r.json_data or {}
            resume_groups = all_bullets_by_role(jd.get("experience", []))
            resume_total = sum(len(v) for v in resume_groups.values())

            out.append(f"\n---\n\n## Resume: **{r.name}** ({resume_total} bullets across {len(resume_groups)} roles)\n")

            dup_count = 0
            borderline_count = 0
            unique_count = 0

            # For each role group that BOTH persona and resume have, compare bullets
            shared_keys = set(persona_groups.keys()) & set(resume_groups.keys())
            for key in sorted(shared_keys):
                cn, tr = key
                pb = persona_groups[key]
                rb = resume_groups[key]
                # use the original company/title from first entry for display
                orig_company = pb[0][1] or rb[0][1]
                orig_title_p = pb[0][0]
                orig_title_r = rb[0][0]
                title_disp = (f"{orig_title_p} (persona) / {orig_title_r} (resume)"
                              if orig_title_p != orig_title_r else orig_title_p)
                out.append(f"\n### {title_disp} @ {orig_company}\n")
                out.append(f"persona: {len(pb)} bullets · resume: {len(rb)} bullets · "
                           f"comparing all {len(pb) * len(rb)} pairs\n\n")

                pair_lines = []
                for (_, _, p_text) in pb:
                    # Find best-match resume bullet for THIS persona bullet
                    best_j = 0.0
                    best_rb = None
                    best_has_num = False
                    for (_, _, r_text) in rb:
                        j = _bullet_jaccard(p_text, r_text)
                        has_num = bool(_numeric_anchors(p_text) & _numeric_anchors(r_text))
                        # Prefer dup-matched pair, else highest Jaccard
                        is_dup = _is_duplicate_bullet(p_text, r_text)
                        if is_dup and not (best_rb and _is_duplicate_bullet(p_text, best_rb)):
                            best_j, best_rb, best_has_num = j, r_text, has_num
                        elif j > best_j and not (best_rb and _is_duplicate_bullet(p_text, best_rb)):
                            best_j, best_rb, best_has_num = j, r_text, has_num

                    if best_rb is None:
                        continue
                    is_dup = _is_duplicate_bullet(p_text, best_rb)
                    if is_dup:
                        dup_count += 1
                    elif best_j >= 0.30:
                        borderline_count += 1
                    else:
                        unique_count += 1
                    pair_lines.append(render_pair(best_j, best_has_num, p_text, best_rb))

                # Persona bullets not in any matched group → also count as unique
                # (already counted via shared_keys filter)
                out.extend(pair_lines)

            # Persona roles NOT in this resume — all bullets are unique by definition
            persona_only_keys = set(persona_groups.keys()) - shared_keys
            for key in sorted(persona_only_keys):
                pb = persona_groups[key]
                unique_count += len(pb)
                if pb:
                    cn, tr = key
                    out.append(f"\n### Persona-only role: {pb[0][0]} @ {pb[0][1]}\n")
                    out.append(f"{len(pb)} bullets — no matching role in {r.name} (counted as unique).\n")

            summary_rows.append((r.name, persona_total, dup_count, borderline_count, unique_count))

        # Top-of-file summary
        summary = ["\n---\n\n## Summary\n",
                   "| Resume | Persona bullets | 🔴 Dup vs resume | 🟡 Borderline (J ≥ 0.30) | 🟢 Unique |\n",
                   "|---|---:|---:|---:|---:|\n"]
        for name, ptot, d, b, u in summary_rows:
            summary.append(f"| {name} | {ptot} | {d} | {b} | {u} |\n")

        # Insert summary right after the top intro
        final = out[:5] + summary + out[5:]

        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text("".join(final), encoding="utf-8")
        print(f"Wrote {OUTPUT_PATH}")
        print(f"Total persona bullets: {persona_total}")
        for name, ptot, d, b, u in summary_rows:
            print(f"  {name:<14} dup={d}  borderline={b}  unique={u}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
