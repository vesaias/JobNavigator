#!/usr/bin/env python3
"""Audita currículos/cartas gerados contra o currículo-fonte.

O que ele faz:
  - extrai termos da taxonomia (tecnologias, práticas, domínios, soft skills);
  - canonicaliza aliases (k8s -> Kubernetes, postgres -> PostgreSQL);
  - compara o texto gerado com o currículo-fonte;
  - sinaliza tecnologias/empresas/datas/métricas que não existem na fonte;
  - agrupa categorias relacionadas por coocorrência;
  - permite consultar um termo ou listar uma categoria.

Uso:
  python3 profile/audit_generated.py --candidate /tmp/tailored.txt
  python3 profile/audit_generated.py --candidate /tmp/tailored.json --strict
  python3 profile/audit_generated.py --query kubernetes
  python3 profile/audit_generated.py --category "DevOps & SRE"
  python3 profile/audit_generated.py --list-categories

Formato do candidato:
  - texto livre (.txt/.md);
  - JSON/YAML com `json_data` (resume do JobNavigator);
  - JSON/YAML com `header/summary/experience/...`;
  - JSON de cover letter (`body_paragraphs`, `greeting`, ...).
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
DEFAULT_SOURCE = HERE / "examples" / "source_profile.yaml"
DEFAULT_TAXONOMY = HERE / "keyword_taxonomy.yaml"

METRIC_RE = re.compile(
    r"(?<![\w.-])("
    r"[$€£]\s?\d[\d.,]*"
    r"|\d[\d.,]*\s?\+?\s?(?:%|percent|per\s+cent|years?|yrs?|months?|weeks?|days?|"
    r"hours?|minutes?|million|billion|thousand|k|m|b|x|jobs?|clients?|customers?|"
    r"teams?|projects?|users?|people|employees?|roles?|applications?)"
    r")",
    re.I,
)
CAPITALIZED_RE = re.compile(r"\b[A-Z][A-Za-z0-9.+#/-]{2,}\b")

STOPWORDS = set("""
the and for with from that this these those into over under about across
using used use build built built lead led leading work worked working
experience experienced years year role roles company companies team teams
project projects customer customers client clients job jobs application applications
software developer development engineering engineer engineers product products
data systems system platform platforms service services solution solutions
business businesses technical technology technologies global national
january february march april may june july august september october november december
jan feb mar apr jun jul aug sep sept oct nov dec
de da do das dos e em no na nos nas para por com um uma uns umas o a os as
""".split())


def fold(value: str) -> str:
    """Lowercase, accents removed, whitespace collapsed; used for queries only."""
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text).strip().lower()


def clip(text: str, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def value_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return " ".join(value_text(v) for v in value)
    if isinstance(value, dict):
        return " ".join(value_text(v) for v in value.values())
    return str(value)


def flatten_resume(data: dict) -> str:
    """Flatten a JobNavigator resume json_data (or a profile-style dict) to text."""
    if not isinstance(data, dict):
        return value_text(data)
    if isinstance(data.get("resume"), dict):
        data = data["resume"]
    if isinstance(data.get("json_data"), dict):
        data = data["json_data"]
    parts = []
    header = data.get("header") or {}
    if isinstance(header, dict):
        parts.append(value_text(header.get("name")))
        parts.append(value_text(header.get("contact_items")))
    for key in ("summary", "skills", "education", "projects", "publications"):
        parts.append(value_text(data.get(key)))
    for exp in data.get("experience") or []:
        if isinstance(exp, dict):
            parts.append(value_text({k: exp.get(k) for k in
                                     ("title", "company", "date", "location", "description", "bullets")}))
        else:
            parts.append(value_text(exp))
    # cover letter / persona shapes
    for key in ("recipient", "date", "greeting", "body_paragraphs", "closing", "signature"):
        parts.append(value_text(data.get(key)))
    if not any(parts):
        parts.append(value_text(data))
    return "\n".join(p for p in parts if p)


def structured_experience(data: dict) -> list[dict]:
    if not isinstance(data, dict):
        return []
    if isinstance(data.get("resume"), dict):
        data = data["resume"]
    if isinstance(data.get("json_data"), dict):
        data = data["json_data"]
    rows = data.get("experience")
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def load_text(path: Path | None) -> str:
    if path is None:
        return ""
    raw = sys.stdin.read() if str(path) == "-" else path.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(raw)
    except Exception:
        return raw
    if isinstance(data, (dict, list)):
        return flatten_resume(data) if isinstance(data, dict) else value_text(data)
    return raw


def load_taxonomy(path: Path) -> tuple[dict, dict[str, set[str]], list[tuple[str, str]]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    categories: dict[str, list[str]] = data.get("categories") or {}
    aliases: dict[str, list[str]] = data.get("aliases") or {}
    term_categories: dict[str, set[str]] = defaultdict(set)
    alias_map: dict[str, str] = {}
    for category, terms in categories.items():
        for term in terms or []:
            term = str(term).strip()
            if not term:
                continue
            term_categories[term].add(category)
            alias_map.setdefault(term.casefold(), term)
    for canonical, values in aliases.items():
        term_categories[canonical]  # ensure key exists
        alias_map[canonical.casefold()] = canonical
        for alias in values or []:
            alias_map[str(alias).casefold()] = canonical
    pairs = sorted(alias_map.items(), key=lambda kv: len(kv[0]), reverse=True)
    return categories, term_categories, pairs


def extract_terms(text: str, alias_pairs: list[tuple[str, str]],
                  term_categories: dict[str, set[str]]) -> list[dict]:
    """Longest alias wins; spans prevent 'node' matching inside 'Node.js'."""
    matches = []
    occupied: list[tuple[int, int]] = []
    for alias, canonical in alias_pairs:
        if len(alias) < 2:
            continue
        pattern = re.compile(r"(?<![\w])" + re.escape(alias).replace(r"\ ", r"\s+") + r"(?![\w])", re.I)
        for m in pattern.finditer(text):
            start, end = m.span()
            if any(not (end <= a or start >= b) for a, b in occupied):
                continue
            occupied.append((start, end))
            matches.append({
                "canonical": canonical,
                "categories": sorted(term_categories.get(canonical, [])),
                "matched": m.group(0),
                "start": start,
                "end": end,
            })
    return sorted(matches, key=lambda m: m["start"])


def normalize_metric(metric: str) -> str:
    value = metric.casefold().replace("per cent", "percent")
    value = re.sub(r"\s+", "", value)
    value = value.replace("yrs", "years").replace("anos", "years").replace("meses", "months")
    value = value.replace("mil", "k").replace("milhão", "m").replace("milhões", "m")
    return value


def metrics_in(text: str) -> list[str]:
    return [m.group(0) for m in METRIC_RE.finditer(text or "")]


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text or "") if s.strip()]


def contexts_for(text: str, needles: list[str], limit: int = 3) -> list[str]:
    out = []
    for sentence in sentences(text):
        low = sentence.casefold()
        if any(n.casefold() in low for n in needles if n):
            out.append(clip(sentence))
            if len(out) >= limit:
                break
    return out


def query_term(query: str, alias_pairs: list[tuple[str, str]],
               term_categories: dict[str, set[str]]) -> list[tuple[str, str]]:
    q = query.casefold().strip()
    exact = [(alias, canonical) for alias, canonical in alias_pairs if alias == q]
    if exact:
        return exact[:1]
    contains = [(alias, canonical) for alias, canonical in alias_pairs if q in alias]
    if contains:
        return contains[:10]
    names = sorted({canonical for _, canonical in alias_pairs})
    close = difflib.get_close_matches(query, names, n=5, cutoff=0.6)
    return [(name.casefold(), name) for name in close]


def main() -> int:
    parser = argparse.ArgumentParser(description="Audita invenções em currículos/cartas gerados.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--taxonomy", type=Path, default=DEFAULT_TAXONOMY)
    parser.add_argument("--candidate", type=Path, help="texto, JSON ou YAML gerado")
    parser.add_argument("--job-description", type=Path, help="texto da vaga (termos permitidos)")
    parser.add_argument("--query", help="consulta um termo/alias e mostra categoria/contextos")
    parser.add_argument("--category", help="lista os termos de uma categoria")
    parser.add_argument("--list-categories", action="store_true")
    parser.add_argument("--json", action="store_true", help="saída JSON")
    parser.add_argument("--output", type=Path, help="grava o relatório JSON")
    parser.add_argument("--strict", action="store_true", help="exit 2 se houver métrica/empresa não comprovada")
    parser.add_argument("--scan-unknown", action="store_true", help="procura termos capitalizados fora da taxonomia")
    parser.add_argument("--max-items", type=int, default=40)
    args = parser.parse_args()

    categories, term_categories, alias_pairs = load_taxonomy(args.taxonomy)

    if args.list_categories:
        for name, terms in categories.items():
            print(f"{name} ({len(terms)}): {', '.join(terms)}")
        return 0

    if args.category:
        target = args.category.casefold()
        names = [n for n in categories if n.casefold() == target]
        if not names:
            print(f"categoria não encontrada: {args.category}", file=sys.stderr)
            print("categorias:", ", ".join(categories), file=sys.stderr)
            return 2
        name = names[0]
        source_text = load_text(args.source)
        source_terms = {m["canonical"] for m in extract_terms(source_text, alias_pairs, term_categories)}
        candidate_text = load_text(args.candidate) if args.candidate else ""
        candidate_terms = {m["canonical"] for m in extract_terms(candidate_text, alias_pairs, term_categories)}
        for term in categories[name]:
            print(f"- {term}: fonte={'sim' if term in source_terms else 'não'}"
                  f", candidato={'sim' if term in candidate_terms else 'não'}")
        return 0

    if args.query:
        matches = query_term(args.query, alias_pairs, term_categories)
        if not matches:
            print(f"nenhum termo encontrado para {args.query!r}", file=sys.stderr)
            return 1
        source_text = load_text(args.source)
        candidate_text = load_text(args.candidate) if args.candidate else ""
        for alias, canonical in matches:
            cats = sorted(term_categories.get(canonical, []))
            aliases = sorted(a for a, c in alias_pairs if c == canonical)
            print(f"{canonical}  [{', '.join(cats) or 'sem categoria'}]")
            print(f"  aliases: {', '.join(aliases)}")
            for label, text in (("fonte", source_text), ("candidato", candidate_text)):
                found = []
                for sentence in sentences(text):
                    low = sentence.casefold()
                    if any(a.casefold() in low for a in aliases):
                        found.append(clip(sentence))
                        if len(found) >= 3:
                            break
                print(f"  {label}: {len(found)} contexto(s)")
                for line in found:
                    print(f"    - {line}")
        return 0

    if not args.candidate:
        parser.error("--candidate é obrigatório (ou use --query/--category/--list-categories)")

    source_data = yaml.safe_load(args.source.read_text(encoding="utf-8")) or {}
    source_text = flatten_resume(source_data.get("resume", source_data))
    persona = source_data.get("persona") or {}
    if isinstance(persona.get("resume_content"), dict):
        source_text += "\n" + flatten_resume(persona["resume_content"])
    source_experience = structured_experience(source_data.get("resume", source_data))
    source_terms = {m["canonical"] for m in extract_terms(source_text, alias_pairs, term_categories)}
    source_metrics = {normalize_metric(m) for m in metrics_in(source_text)}
    source_companies = {str(e.get("company", "")).casefold().strip() for e in source_experience if e.get("company")}
    source_dates = {str(e.get("date", "")).casefold().strip() for e in source_experience if e.get("date")}

    raw_candidate = sys.stdin.read() if str(args.candidate) == "-" else args.candidate.read_text(encoding="utf-8")
    try:
        candidate_data = yaml.safe_load(raw_candidate)
    except Exception:
        candidate_data = None
    if isinstance(candidate_data, (dict, list)):
        candidate_text = flatten_resume(candidate_data) if isinstance(candidate_data, dict) else value_text(candidate_data)
    else:
        candidate_text = raw_candidate
    candidate_experience = structured_experience(candidate_data) if isinstance(candidate_data, dict) else []

    job_text = load_text(args.job_description) if args.job_description else ""
    job_terms = {m["canonical"] for m in extract_terms(job_text, alias_pairs, term_categories)}

    candidate_matches = extract_terms(candidate_text, alias_pairs, term_categories)
    candidate_terms = {m["canonical"] for m in candidate_matches}
    candidate_metrics = metrics_in(candidate_text)
    candidate_companies = {str(e.get("company", "")).casefold().strip() for e in candidate_experience if e.get("company")}
    candidate_dates = {str(e.get("date", "")).casefold().strip() for e in candidate_experience if e.get("date")}

    added = sorted(candidate_terms - source_terms)
    added_from_job = sorted(set(added) & job_terms) if job_text else []
    added_unverified = sorted(set(added) - set(added_from_job))
    unknown_metrics = sorted({m for m in candidate_metrics if normalize_metric(m) not in source_metrics})
    unknown_companies = sorted(candidate_companies - source_companies)
    unknown_dates = sorted(candidate_dates - source_dates)

    category_counter = Counter()
    for term in candidate_terms:
        for cat in term_categories.get(term, []):
            category_counter[cat] += 1

    added_by_category: dict[str, list[str]] = defaultdict(list)
    for term in added_unverified:
        for cat in term_categories.get(term, []):
            added_by_category[cat].append(term)

    related = Counter()
    for sentence in sentences(candidate_text):
        cats = set()
        for match in extract_terms(sentence, alias_pairs, term_categories):
            cats.update(match["categories"])
        if len(cats) >= 2:
            related[tuple(sorted(cats))] += 1

    unknown_caps = []
    if args.scan_unknown:
        known = {a.casefold() for a, _ in alias_pairs} | {a.casefold() for a in source_terms}
        for token in CAPITALIZED_RE.findall(candidate_text):
            low = token.casefold()
            if low in known or low in STOPWORDS or len(token) < 3:
                continue
            if token.isupper() or any(ch.isdigit() for ch in token):
                unknown_caps.append(token)
        unknown_caps = sorted(Counter(unknown_caps).items(), key=lambda kv: (-kv[1], kv[0]))[: args.max_items]

    report = {
        "source": str(args.source),
        "candidate": str(args.candidate),
        "job_description": str(args.job_description) if args.job_description else None,
        "counts": {
            "source_terms": len(source_terms),
            "candidate_terms": len(candidate_terms),
            "added_terms": len(added),
            "metrics": len(candidate_metrics),
            "unknown_metrics": len(unknown_metrics),
        },
        "categories": dict(category_counter.most_common()),
        "related_categories": [
            {"categories": list(pair), "count": count}
            for pair, count in related.most_common(10)
        ],
        "added_terms": added_unverified,
        "added_by_category": {cat: sorted(set(terms)) for cat, terms in sorted(added_by_category.items())},
        "added_terms_from_job_description": added_from_job,
        "unknown_metrics": unknown_metrics[: args.max_items],
        "unknown_companies": unknown_companies,
        "unknown_dates": unknown_dates,
        "unknown_capitalized": unknown_caps,
        "contexts": {term: contexts_for(candidate_text, [term]) for term in added_unverified[:15]},
    }

    if args.output:
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"fonte: {args.source}")
        print(f"candidato: {args.candidate}")
        print(f"termos: fonte={len(source_terms)} candidato={len(candidate_terms)}")
        print("\nCategorias no candidato:")
        for cat, count in category_counter.most_common():
            print(f"  {cat}: {count}")
        if related:
            print("\nCategorias relacionadas (coocorrência):")
            for pair, count in related.most_common(10):
                print(f"  {' + '.join(pair)}: {count}")
        if added_from_job:
            print("\nTermos que vêm da descrição da vaga (não da fonte):")
            for term in added_from_job:
                print(f"  - {term}")
        if added_unverified:
            print("\nATENÇÃO — termos no candidato que NÃO estão na fonte nem na vaga:")
            for term in added_unverified:
                print(f"  - {term}")
            if added_by_category:
                print("  agrupados por categoria:")
                for cat, terms in sorted(added_by_category.items()):
                    print(f"    {cat}: {', '.join(sorted(set(terms)))}")
        if unknown_metrics:
            print("\nATENÇÃO — métricas sem lastro na fonte:")
            for metric in unknown_metrics[: args.max_items]:
                print(f"  - {metric}")
        if unknown_companies:
            print("\nATENÇÃO — empresas não presentes na fonte:")
            for company in unknown_companies:
                print(f"  - {company}")
        if unknown_dates:
            print("\nATENÇÃO — datas não presentes na fonte:")
            for date in unknown_dates:
                print(f"  - {date}")
        if unknown_caps:
            print("\nPossíveis termos não catalogados (revisar):")
            for token, count in unknown_caps:
                print(f"  - {token} ({count}x)")
        if args.strict and (unknown_metrics or unknown_companies or unknown_dates or added_unverified):
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
