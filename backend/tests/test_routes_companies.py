"""Tests for /api/companies CRUD + detect_scrape_type ATS dispatch.

Note: routes_companies.py exposes no DELETE endpoint and no HTTP detect-scrape-type
endpoint (the latter is a module-level helper consumed internally). We cover:
  - POST /api/companies            (create)
  - GET  /api/companies            (list)
  - PATCH /api/companies/{id}      (update)
  - detect_scrape_type(url)        (unit test of the URL classifier)
"""
import pytest


def _seed_first_run(db):
    from backend.models.db import Setting
    db.add(Setting(key="dashboard_api_key", value=""))
    db.commit()


@pytest.fixture(autouse=True)
def _stub_h1b_background(monkeypatch):
    """Prevent real H-1B network fetches from any create/patch flow."""
    async def _noop(*a, **kw):
        return None

    # Stub both the private BackgroundTasks target and the underlying fetcher.
    import backend.api.routes_companies as rc
    monkeypatch.setattr(rc, "_fire_h1b_async", _noop, raising=False)
    try:
        import backend.analyzer.h1b_checker as h1b
        if hasattr(h1b, "fetch_h1b_for_company_id"):
            monkeypatch.setattr(h1b, "fetch_h1b_for_company_id", _noop, raising=False)
        if hasattr(h1b, "fetch_h1b_for_company"):
            monkeypatch.setattr(h1b, "fetch_h1b_for_company", _noop, raising=False)
    except Exception:
        pass


# ── CRUD endpoints ───────────────────────────────────────────────────────────


def test_create_company(api_client, test_db):
    _seed_first_run(test_db)
    resp = api_client.post("/api/companies", json={
        "name": "TestCoAlpha",
        "scrape_urls": ["https://nvidia.wd5.myworkdayjobs.com/CareerSite"],
        "tier": 1,
    })
    assert resp.status_code in (200, 201), f"Unexpected {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data.get("name") == "TestCoAlpha"
    assert data.get("tier") == 1


def test_create_company_rejects_duplicate(api_client, test_db):
    """POST with an existing name should return 409."""
    _seed_first_run(test_db)
    from backend.models.db import Company
    test_db.add(Company(name="DupCo", scrape_urls=[]))
    test_db.commit()

    resp = api_client.post("/api/companies", json={
        "name": "DupCo",
        "scrape_urls": [],
    })
    assert resp.status_code == 409


def test_list_companies(api_client, test_db):
    _seed_first_run(test_db)
    from backend.models.db import Company
    test_db.add(Company(name="ListedCo", scrape_urls=[]))
    test_db.commit()

    resp = api_client.get("/api/companies")
    assert resp.status_code == 200
    data = resp.json()
    # Response is a list per route implementation
    companies = data if isinstance(data, list) else data.get("companies") or []
    names = [c.get("name") for c in companies]
    assert "ListedCo" in names


def test_update_company(api_client, test_db):
    _seed_first_run(test_db)
    from backend.models.db import Company
    co = Company(name="BeforeName", scrape_urls=[], tier=1)
    test_db.add(co)
    test_db.commit()
    cid = str(co.id)

    resp = api_client.patch(f"/api/companies/{cid}", json={"tier": 2})
    assert resp.status_code == 200, f"Unexpected {resp.status_code}: {resp.text}"

    test_db.expire_all()
    co_refreshed = test_db.query(Company).filter(Company.id == co.id).first()
    assert co_refreshed.tier == 2


def test_update_company_not_found(api_client, test_db):
    """PATCH on unknown ID returns 404."""
    _seed_first_run(test_db)
    import uuid
    resp = api_client.patch(f"/api/companies/{uuid.uuid4()}", json={"tier": 2})
    assert resp.status_code == 404


# ── detect_scrape_type unit tests ────────────────────────────────────────────


def test_detect_scrape_type_workday():
    from backend.api.routes_companies import detect_scrape_type
    assert detect_scrape_type(
        "https://nvidia.wd5.myworkdayjobs.com/CareerSite"
    ) == "Workday API"


def test_detect_scrape_type_greenhouse():
    from backend.api.routes_companies import detect_scrape_type
    result = detect_scrape_type("https://boards.greenhouse.io/acme")
    assert "Greenhouse" in result


def test_detect_scrape_type_generic_fallback():
    from backend.api.routes_companies import detect_scrape_type
    # An unknown career page should fall through to the Playwright generic path.
    result = detect_scrape_type("https://example.com/careers")
    assert "Playwright" in result or "Generic" in result
