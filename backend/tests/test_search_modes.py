"""The search-mode registry (R30 I-02): one backend table, one dashboard table, kept equal;
and the API bugs that came from the copies: any mode accepted (P0-02), JobSpy boards stored
on modes that take none (P0-03), Apify boards left on a search switched back to JobSpy (I-03)."""
import pathlib
import re

import pytest

from backend.models.db import Search, Setting
from backend.scraper import search_modes as M

FRONTEND = pathlib.Path(__file__).resolve().parents[2] / "frontend" / "src" / "searchModes.js"


def _frontend_modes():
    rows = []
    for line in FRONTEND.read_text(encoding="utf-8").splitlines():
        if not line.strip().startswith("{ key:"):
            continue
        get = lambda name: re.search(rf"{name}: ('[^']*'|true|false|\[[^\]]*\])", line).group(1)
        rows.append({
            "key": get("key").strip("'"),
            "label": get("label").strip("'"),
            "extension": get("extension") == "true",
            "needsQuery": get("needsQuery") == "true",
            "needsTerm": get("needsTerm") == "true",
            "sources": re.findall(r"'([^']*)'", get("sources")),
        })
    return rows


@pytest.mark.skipif(not FRONTEND.exists(), reason="the frontend is not in the backend image")
def test_dashboard_table_matches_the_backend_table():
    front = _frontend_modes()
    assert [m["key"] for m in front] == list(M.SEARCH_MODES)
    for f in front:
        b = M.SEARCH_MODES[f["key"]]
        assert f["label"] == b.label, f["key"]
        assert f["extension"] == b.extension, f["key"]
        assert f["needsQuery"] == b.needs_query, f["key"]
        assert f["needsTerm"] == b.needs_term, f["key"]
        assert f["sources"] == M.default_sources(f["key"]), f["key"]


def test_no_hand_written_mode_lists_are_left():
    """A tuple or array of two or more mode keys outside the two tables is a copy (I-02)."""
    root = pathlib.Path(__file__).resolve().parents[2]
    keys = "|".join(re.escape(k) for k in M.SEARCH_MODES)
    pattern = re.compile(rf"""[\(\[]\s*["']({keys})["']\s*,\s*["']({keys})["']""")
    files = [p for p in (root / "backend").rglob("*.py")
             if "tests" not in p.parts and p.name != "search_modes.py"]
    src = root / "frontend" / "src"
    if src.exists():
        files += [p for p in src.rglob("*.js*") if "__tests__" not in p.parts
                  and "node_modules" not in p.parts and p.name != "searchModes.js"]
    hits = [f"{p.relative_to(root)}:{m.group(0)}" for p in files
            for m in pattern.finditer(p.read_text(encoding="utf-8", errors="ignore"))]
    assert hits == []


def test_every_scraper_module_has_run_and_preview():
    import importlib
    for mode in M.SEARCH_MODES.values():
        if mode.runnable:
            module = importlib.import_module(f"backend.scraper.sources.{mode.module}")
            assert callable(module.run), mode.key
            # keyword's Test runs inline and levels.fyi's lives in routes_searches
            if mode.background_test and mode.key != "levels_fyi":
                assert callable(module.preview), mode.key


def test_config_error_names_what_is_missing():
    assert M.config_error(Search(search_mode="levels_fyi")) == "Levels.fyi needs a search URL before it can run"
    assert M.config_error(Search(search_mode="levels_fyi", direct_url="https://www.levels.fyi/jobs")) is None
    assert "search term or a URL" in M.config_error(Search(search_mode="freehire"))
    assert "no scraper" in M.config_error(Search(search_mode="extension"))
    assert "Unknown search mode" in M.config_error(Search(search_mode="nope"))
    assert M.config_error(Search(search_mode="keyword")) is None
    assert M.config_error(Search(search_mode=None)) is None          # the column default


@pytest.mark.asyncio
async def test_run_search_dispatches_through_the_table(monkeypatch):
    from backend.scraper import orchestrator
    import backend.scraper.sources.freehire as freehire
    import backend.scraper.sources.jobspy as jobspy
    seen = {}

    async def fake_run(search, **kw):
        seen[search.search_mode] = kw
        return {"jobs_found": 0}
    monkeypatch.setattr(freehire, "run", fake_run)
    monkeypatch.setattr(jobspy, "run", fake_run)
    await orchestrator.run_search(Search(search_mode="freehire"), proxy_url="http://p", shared="S")
    await orchestrator.run_search(Search(search_mode="keyword"), proxy_url="http://p")
    assert seen == {"freehire": {"shared": "S"}, "keyword": {"proxy_url": "http://p"}}
    with pytest.raises(ValueError):
        await orchestrator.run_search(Search(search_mode="nope"))
    out = await orchestrator.run_search(Search(search_mode="extension"))
    assert out["jobs_found"] == 0 and "no scraper" in out["error"]


# ── the API ─────────────────────────────────────────────────────────────────

@pytest.fixture
def api_client(api_client, test_db):
    """Open access: an empty dashboard_api_key row (see test_apify_source.py)."""
    test_db.add(Setting(key="dashboard_api_key", value=""))
    test_db.commit()
    return api_client


def test_unknown_or_built_in_modes_are_refused_on_create(api_client):
    r = api_client.post("/api/searches", json={"name": "x", "search_mode": "made_up"})
    assert r.status_code == 400 and "Unknown search mode" in r.json()["detail"]
    r = api_client.post("/api/searches", json={"name": "x", "search_mode": "linkedin_extension"})
    assert r.status_code == 400 and "built in" in r.json()["detail"]


def test_unknown_mode_is_refused_on_patch_and_the_row_is_untouched(api_client):
    sid = api_client.post("/api/searches", json={"name": "kw", "search_term": "pm"}).json()["id"]
    assert api_client.patch(f"/api/searches/{sid}", json={"search_mode": "made_up"}).status_code == 400
    assert api_client.patch(f"/api/searches/{sid}", json={"search_mode": "extension"}).status_code == 400
    row = next(s for s in api_client.get("/api/searches").json() if s["id"] == sid)
    assert row["search_mode"] == "keyword"


def test_a_built_in_extension_search_keeps_its_mode(api_client, test_db):
    ext = Search(name="Extension", search_mode="extension", active=True)
    test_db.add(ext)
    test_db.commit()
    r = api_client.patch(f"/api/searches/{ext.id}", json={"search_mode": "keyword"})
    assert r.status_code == 400
    # its filters stay editable
    r = api_client.patch(f"/api/searches/{ext.id}", json={"title_include_keywords": ["pm"]})
    assert r.status_code == 200


def test_modes_without_boards_store_no_sources(api_client):
    r = api_client.post("/api/searches", json={
        "name": "lv", "search_mode": "levels_fyi", "direct_url": "https://www.levels.fyi/jobs",
        "sources": ["linkedin", "indeed"]})
    assert r.status_code == 200 and r.json()["sources"] == []
    r = api_client.post("/api/searches", json={"name": "kw", "search_term": "pm"})
    assert r.json()["sources"] == M.JOBSPY_DEFAULT_BOARDS
    r = api_client.post("/api/searches", json={"name": "li", "search_mode": "linkedin_personal"})
    assert r.json()["sources"] == ["recommended", "top-applicant"]


def test_boards_are_checked_against_the_mode(api_client):
    r = api_client.post("/api/searches", json={"name": "kw", "search_term": "pm", "sources": ["apify_linkedin"]})
    assert r.status_code == 400 and "JobSpy boards" in r.json()["detail"]
    r = api_client.post("/api/searches", json={"name": "li", "search_mode": "linkedin_personal",
                                               "sources": ["indeed"]})
    assert r.status_code == 400 and "LinkedIn collections" in r.json()["detail"]


def test_switching_apify_back_to_jobspy_resets_the_boards(api_client):
    sid = api_client.post("/api/searches", json={
        "name": "ap", "search_mode": "apify", "search_term": "pm", "sources": ["apify_linkedin"]}).json()["id"]
    r = api_client.patch(f"/api/searches/{sid}", json={"search_mode": "keyword"})
    assert r.status_code == 200 and r.json()["sources"] == M.JOBSPY_DEFAULT_BOARDS
    r = api_client.patch(f"/api/searches/{sid}", json={"search_mode": "trulyremote"})
    assert r.json()["sources"] == []
