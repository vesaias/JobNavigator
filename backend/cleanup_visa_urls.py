"""One-shot: (1) merge the new search-filter-noise params into the
dedup_tracking_params DB setting; (2) re-normalize Job.url for all existing rows
where the URL has obvious search-filter noise (Visa, etc.).

Usage:
    docker compose exec backend python /app/backend/cleanup_visa_urls.py
"""
import json
from backend.models.db import SessionLocal, Job, Setting
from backend.scraper._shared.dedup import _normalize_url, reload_tracking_params

NEW_NOISE_PARAMS = [
    "categories", "cities", "locations", "departments",
    "teams", "regions", "country", "category",
]


def merge_setting(db):
    row = db.query(Setting).filter(Setting.key == "dedup_tracking_params").first()
    if not row:
        print("dedup_tracking_params setting missing — nothing to merge")
        return
    try:
        existing = json.loads(row.value or "[]")
    except Exception:
        existing = []
    added = [p for p in NEW_NOISE_PARAMS if p not in existing]
    if not added:
        print("dedup_tracking_params already has all new noise params")
        return
    row.value = json.dumps(existing + added)
    db.commit()
    print(f"Merged into dedup_tracking_params: {added}")


def main():
    db = SessionLocal()
    try:
        merge_setting(db)
        reload_tracking_params()  # pick up freshly-saved params
        suspicious = db.query(Job).filter(
            (Job.url.ilike('%categories=%')) | (Job.url.ilike('%cities=%'))
        ).all()
        print(f"Found {len(suspicious)} jobs with search-filter noise in url")
        cleaned = 0
        for job in suspicious:
            new_url = _normalize_url(job.url)
            if new_url and new_url != job.url:
                job.url = new_url
                cleaned += 1
        db.commit()
        print(f"Cleaned {cleaned} job URLs")
    finally:
        db.close()


if __name__ == "__main__":
    main()
