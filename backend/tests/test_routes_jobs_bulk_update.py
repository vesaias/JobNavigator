"""Tests for POST /api/jobs/bulk-update — returns not_found for unresolved IDs."""
import pytest
import uuid


def _seed_first_run(db):
    from backend.models.db import Setting
    db.add(Setting(key="dashboard_api_key", value=""))
    db.commit()


def test_bulk_update_all_valid_ids(api_client, test_db):
    _seed_first_run(test_db)
    from backend.models.db import Job
    job = Job(external_id="x1", content_hash="c1",
              company="Acme", title="Senior Product Manager",
              url="https://x.com/1", status="new")
    test_db.add(job)
    test_db.commit()

    resp = api_client.post("/api/jobs/bulk-update", json={
        "job_ids": [str(job.id)],
        "updates": {"status": "saved"},
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("updated") == 1
    assert data.get("not_found") == [] or data.get("not_found") is None


def test_bulk_update_returns_not_found_ids(api_client, test_db):
    """Invalid IDs are reported in the response, not silently dropped."""
    _seed_first_run(test_db)
    from backend.models.db import Job
    job = Job(external_id="x2", content_hash="c2",
              company="Acme", title="Senior PM",
              url="https://x.com/2", status="new")
    test_db.add(job)
    test_db.commit()

    bogus_id = str(uuid.uuid4())
    resp = api_client.post("/api/jobs/bulk-update", json={
        "job_ids": [str(job.id), bogus_id],
        "updates": {"status": "saved"},
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("updated") == 1
    not_found = data.get("not_found") or []
    assert len(not_found) == 1
    assert bogus_id in not_found


def test_bulk_update_all_bogus_ids(api_client, test_db):
    _seed_first_run(test_db)
    bogus1 = str(uuid.uuid4())
    bogus2 = str(uuid.uuid4())
    resp = api_client.post("/api/jobs/bulk-update", json={
        "job_ids": [bogus1, bogus2],
        "updates": {"status": "saved"},
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("updated") == 0
    not_found = data.get("not_found") or []
    assert set(not_found) == {bogus1, bogus2}
