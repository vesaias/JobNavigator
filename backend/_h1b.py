import asyncio
from backend.models.db import SessionLocal, Company
from backend.analyzer.h1b_checker import fetch_company_h1b_data
from datetime import datetime, timezone

async def main():
    db = SessionLocal()
    try:
        companies = db.query(Company).order_by(Company.tier, Company.name).all()
        print(f"Refreshing H-1B data for {len(companies)} companies...")
        for c in companies:
            data = await fetch_company_h1b_data(c.name)
            c.h1b_lca_count = data["lca_count"]
            c.h1b_approval_rate = data["approval_rate"]
            c.h1b_median_salary = data["median_salary"]
            c.h1b_last_checked = datetime.now(timezone.utc)
            print(f"  {c.name:20s}  LCA={data['lca_count']:>5}, rate={data['approval_rate']:>5.1f}%, salary=${data['median_salary']:>7}")
        db.commit()
        print("Done.")
    finally:
        db.close()

asyncio.run(main())
