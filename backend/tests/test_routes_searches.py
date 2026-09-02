"""Tests for /api/searches guards on the built-in extension searches.

The two seeded searches ("Extension" / "Extension LI") have no scraper: jobs are
pushed in by the Chrome extension. The v2 UI hides Run/Test/Delete for them; these
tests cover the server-side half of that gating (SRCH-26). PATCH stays allowed —
the editor saves their title/company filters through it.
"""
import pytest


def _seed_first_run(db):
    from backend.models.db import Setting
    db.add(Setting(key="dashboard_api_key", value=""))
    db.commit()


def _mk_search(db, mode):
    from backend.models.db import Search
    s = Search(name=f"Extension {mode}", search_mode=mode, active=True)
    db.add(s)
    db.commit()
    return str(s.id)


@pytest.mark.parametrize("mode", ["extension", "linkedin_extension"])
def test_run_rejects_extension_search(api_client, test_db, mode):
    _seed_first_run(test_db)
    sid = _mk_search(test_db, mode)
    resp = api_client.post(f"/api/searches/{sid}/run")
    assert resp.status_code == 409, f"Unexpected {resp.status_code}: {resp.text}"
    assert "extension" in resp.json()["detail"].lower()


@pytest.mark.parametrize("mode", ["extension", "linkedin_extension"])
def test_delete_rejects_extension_search(api_client, test_db, mode):
    _seed_first_run(test_db)
    sid = _mk_search(test_db, mode)
    resp = api_client.delete(f"/api/searches/{sid}")
    assert resp.status_code == 409, f"Unexpected {resp.status_code}: {resp.text}"

    from backend.models.db import Search
    assert test_db.query(Search).filter(Search.id == sid).first() is not None


@pytest.mark.parametrize("mode", ["extension", "linkedin_extension"])
def test_patch_still_allowed_on_extension_search(api_client, test_db, mode):
    """The editor saves filters via PATCH — it must stay open."""
    _seed_first_run(test_db)
    sid = _mk_search(test_db, mode)
    resp = api_client.patch(f"/api/searches/{sid}", json={"title_exclude_keywords": ["intern"]})
    assert resp.status_code == 200, f"Unexpected {resp.status_code}: {resp.text}"
    assert resp.json()["title_exclude_keywords"] == ["intern"]


def test_run_still_allowed_on_keyword_search(api_client, test_db, monkeypatch):
    """A normal search still launches (202) — the guard is mode-scoped."""
    _seed_first_run(test_db)
    sid = _mk_search(test_db, "keyword")

    import backend.job_monitor as mon
    monkeypatch.setattr(mon, "launch_background", lambda *a, **kw: "run-1")

    resp = api_client.post(f"/api/searches/{sid}/run")
    assert resp.status_code == 202, f"Unexpected {resp.status_code}: {resp.text}"
