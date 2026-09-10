"""Regenerate `location_golden.csv` from `location_corpus.csv`.

The corpus is every distinct `jobs.location` string in the live database with
how often it occurs and one example source. The golden file is what the parser
makes of each of them, so a change to `analyzer/location.py` shows up as a diff
over real board strings instead of over invented ones.

Run it from the backend container after an intended parser change:

    python -m backend.tests.fixtures.generate_location_golden
"""
import csv
import pathlib

from backend.analyzer.location import parse

HERE = pathlib.Path(__file__).parent
CORPUS = HERE / "location_corpus.csv"
GOLDEN = HERE / "location_golden.csv"
FIELDS = ["raw", "country", "region", "city", "arrangement", "ambiguous"]


def golden_row(raw: str) -> dict:
    result = parse(raw)
    return {
        "raw": raw,
        "country": result["country"] or "",
        "region": result["region"] or "",
        "city": result["city"] or "",
        "arrangement": result["arrangement"] or "",
        "ambiguous": "1" if result["ambiguous"] else "",
    }


def rows() -> list:
    with CORPUS.open(encoding="utf-8", newline="") as handle:
        return [golden_row(row["raw"]) for row in csv.DictReader(handle)]


def main() -> None:
    with GOLDEN.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows())
    print("wrote %s" % GOLDEN)


if __name__ == "__main__":
    main()
