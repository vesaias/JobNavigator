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


# ── DS-A-02: the test preview must apply title_exclude_global ────────────────
# The run merges the global list into the per-search excludes before it stores
# anything (scraper/sources/jobspy.py:285). The preview used to skip that layer
# entirely, so it reported "5 kept · 0 title-filtered" for a run that then filed
# two of those rows as `ignored`. The Companies preview already surfaces the
# layer (routes_companies.py:603); these tests pin the Searches one to it.

def _seed_global_exclude(db, keywords):
    import json
    from backend.models.db import Setting
    db.add(Setting(key="title_exclude_global", value=json.dumps(keywords)))
    db.commit()


def _mk_keyword_search(db, **kw):
    from backend.models.db import Search
    # Search.title_exclude_keywords defaults to ["intern", "junior", "associate"];
    # blank it unless a test is deliberately exercising the per-search layer, so
    # what these tests measure is the *global* list and nothing else.
    kw.setdefault("title_exclude_keywords", [])
    s = Search(name="Global exclude probe", search_mode="keyword", active=True,
               sources=["indeed"], search_term="program manager", **kw)
    db.add(s)
    db.commit()
    return str(s.id)


def _stub_jobspy(monkeypatch, titles):
    """Make jobspy.scrape_jobs return one row per title.

    `test_search` does `from jobspy import scrape_jobs` *inside* the handler, so
    patching the module attribute is enough.
    """
    import jobspy
    import pandas as pd
    df = pd.DataFrame([{
        "title": t, "company": f"Co {i}", "job_url": f"https://example.com/{i}",
        "site": "indeed", "location": "United States", "description": "",
        "min_amount": None, "max_amount": None,
    } for i, t in enumerate(titles)])
    monkeypatch.setattr(jobspy, "scrape_jobs", lambda **kwargs: df)


def test_preview_applies_global_title_exclude(api_client, test_db, monkeypatch):
    _seed_first_run(test_db)
    _seed_global_exclude(test_db, ["intern", "marketing"])
    sid = _mk_keyword_search(test_db)
    _stub_jobspy(monkeypatch, [
        "Technical Program Manager",
        "Intern, Design Engineering",
        "Staff Technical Product Marketing Manager",
    ])

    resp = api_client.post(f"/api/searches/{sid}/test")
    assert resp.status_code == 200, f"Unexpected {resp.status_code}: {resp.text}"
    d = resp.json()

    assert d["raw_count"] == 3
    # only the row that no list touches survives
    assert d["after_filter"] == 1
    # all three pass the search's own (empty) filters — the global list is what drops two
    assert d["after_search_filter"] == 3
    assert d["global_excluded_count"] == 2
    assert d["global_exclude_keyword_count"] == 2

    by_title = {j["title"]: j for j in d["jobs"]}
    assert by_title["Technical Program Manager"]["kept"] is True
    assert by_title["Technical Program Manager"]["global_excluded_by"] == []

    dropped = by_title["Intern, Design Engineering"]
    assert dropped["kept"] is False
    assert dropped["global_excluded_by"] == ["intern"]
    assert dropped["reason"] == "[Global] Excluded by: intern"

    dropped2 = by_title["Staff Technical Product Marketing Manager"]
    assert dropped2["kept"] is False
    assert dropped2["global_excluded_by"] == ["marketing"]


def test_preview_global_exclude_is_word_bounded_and_optional(api_client, test_db, monkeypatch):
    """No global list configured -> no drops; and the match is word-bounded."""
    _seed_first_run(test_db)
    _seed_global_exclude(test_db, ["intern"])
    sid = _mk_keyword_search(test_db)
    # "Internal Communications Manager" contains "intern" as a substring only —
    # the run's filter is word-bounded, so the preview's must be too.
    _stub_jobspy(monkeypatch, ["Internal Communications Manager"])

    d = api_client.post(f"/api/searches/{sid}/test").json()
    assert d["global_excluded_count"] == 0
    assert d["jobs"][0]["kept"] is True


def test_preview_per_search_exclude_still_wins_its_own_label(api_client, test_db, monkeypatch):
    """A per-search exclude keeps its own reason — it is not relabelled [Global]."""
    _seed_first_run(test_db)
    _seed_global_exclude(test_db, ["marketing"])
    sid = _mk_keyword_search(test_db, title_exclude_keywords=["senior"])
    _stub_jobspy(monkeypatch, ["Senior Program Manager"])

    d = api_client.post(f"/api/searches/{sid}/test").json()
    j = d["jobs"][0]
    assert j["kept"] is False
    assert j["reason"] == "Excluded by: senior"
    assert j["global_excluded_by"] == []
    # it never reached the global layer, so it counts as a per-search drop
    assert d["after_search_filter"] == 0
    assert d["global_excluded_count"] == 0
