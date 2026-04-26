"""One-shot diagnostic: compare every persona experience bullet against bullets in
each base Resume (TPgM, PjM, PjM FinTech, PM) and report Jaccard similarities.

Helps pick a Jaccard threshold for the lexical dedupe approach.

Run inside the backend container:
    docker compose exec backend python /app/backend/analyze_bullet_dupes.py
"""
import re
from backend.models.db import SessionLocal, Resume, Persona


STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "at",
    "by", "for", "with", "from", "as", "is", "was", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did",
    "this", "that", "these", "those", "it", "its", "i", "we", "our",
    "you", "your", "into", "via", "across", "per",
}


def stem(w):
    for suf in ("ings", "ing", "edly", "ed", "ly", "es", "s"):
        if len(w) > len(suf) + 2 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def tokens(s):
    return {stem(w.lower()) for w in re.findall(r"[a-zA-Z]+", s or "") if w.lower() not in STOPWORDS}


def jaccard(a, b):
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def numbers(s):
    return set(re.findall(r"\$?\d+(?:[.,]\d+)?[KMB%+]?", s or ""))


def all_bullets(experience):
    """Yield (label, bullet_text) for every bullet across all experience entries."""
    for exp in experience or []:
        title = exp.get("title", "")
        company = exp.get("company", "")
        for b in exp.get("bullets", []) or []:
            yield f"{title}@{company}", b


def main():
    db = SessionLocal()
    try:
        persona = db.query(Persona).filter(Persona.id == 1).first()
        if not persona or not persona.resume_content:
            print("No persona resume_content — abort")
            return
        persona_bullets = list(all_bullets(persona.resume_content.get("experience", [])))
        print(f"Persona bullets: {len(persona_bullets)}")

        resumes = db.query(Resume).filter(Resume.is_base == True).order_by(Resume.name).all()

        # Threshold sweep: how many dup-pairs at each cutoff?
        thresholds = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
        sweep_counts = {t: {"with_number_match": 0, "without": 0} for t in thresholds}

        # Sample worst-offender pairs to print
        all_pairs = []  # (jaccard, has_num_match, resume_name, base_label, base, persona_label, persona_text)

        for r in resumes:
            if r.name == "PM":
                continue  # PM was the source for persona, expect very high overlap — show separately
            jd = r.json_data or {}
            base_bullets = list(all_bullets(jd.get("experience", [])))
            print(f"\n--- {r.name}: {len(base_bullets)} bullets ---")

            for base_label, base_b in base_bullets:
                for persona_label, persona_b in persona_bullets:
                    j = jaccard(base_b, persona_b)
                    has_num = bool(numbers(base_b) & numbers(persona_b))
                    all_pairs.append((j, has_num, r.name, base_label, base_b, persona_label, persona_b))
                    for t in thresholds:
                        if j >= t:
                            if has_num:
                                sweep_counts[t]["with_number_match"] += 1
                            else:
                                sweep_counts[t]["without"] += 1

        # Print threshold sweep
        print("\n=== Threshold sweep ===")
        print(f"{'Jaccard >=':<12} {'w/ num match':<15} {'no num match':<15}")
        for t in thresholds:
            sc = sweep_counts[t]
            print(f"{t:<12} {sc['with_number_match']:<15} {sc['without']:<15}")

        # Print top pairs by Jaccard, grouped by number-match status
        all_pairs.sort(key=lambda x: -x[0])

        print("\n=== Top 20 pairs WITH number match (likely true dups) ===")
        n = 0
        for j, has_num, rname, blab, b, plab, p in all_pairs:
            if not has_num:
                continue
            print(f"  J={j:.2f}  [{rname}] {blab}: {b[:90]}")
            print(f"            persona  {plab}: {p[:90]}")
            n += 1
            if n >= 20:
                break

        print("\n=== Top 20 pairs WITHOUT number match (lexical-only) ===")
        n = 0
        for j, has_num, rname, blab, b, plab, p in all_pairs:
            if has_num:
                continue
            print(f"  J={j:.2f}  [{rname}] {blab}: {b[:90]}")
            print(f"            persona  {plab}: {p[:90]}")
            n += 1
            if n >= 20:
                break

        # Borderline zone — pairs around suspected threshold
        print("\n=== Pairs in 0.4-0.6 zone (borderline) ===")
        n = 0
        for j, has_num, rname, blab, b, plab, p in all_pairs:
            if 0.4 <= j < 0.6:
                print(f"  J={j:.2f}  num={'Y' if has_num else 'N'}  [{rname}] {blab}: {b[:80]}")
                print(f"            persona  {plab}: {p[:80]}")
                n += 1
                if n >= 15:
                    break

    finally:
        db.close()


if __name__ == "__main__":
    main()
