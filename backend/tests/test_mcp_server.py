"""MCP server at /api/mcp: the tool list, the read tools, and the auth of a tool call
(install password and account are the caller's, checked by the same middleware)."""
import json

from backend.tests.r4_support import ACT_AS, API_KEY, client, make_job  # noqa: F401 — client is a fixture

MCP = "/api/mcp"
_ACCEPT = {"Accept": "application/json, text/event-stream"}


def _rpc(c, method, params=None, **headers):
    return c.post(MCP, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
                  headers={**_ACCEPT, **headers})


def _call(c, tool, args=None, **headers):
    resp = _rpc(c, "tools/call", {"name": tool, "arguments": args or {}}, **headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["result"]


def _data(result):
    assert not result.get("isError"), result
    return json.loads(result["content"][0]["text"])


def _member(db):
    import backend.models.db as db_mod
    member = db_mod.Account(name="Member", role="member", color=db_mod.ACCOUNT_COLORS[1])
    db.add(member)
    db.commit()
    return member


def test_initialize_handshake(client):
    resp = _rpc(client, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                       "clientInfo": {"name": "test", "version": "0"}})
    assert resp.status_code == 200, resp.text
    result = resp.json()["result"]
    assert result["serverInfo"]["name"] == "JobNavigator"
    assert "tools" in result["capabilities"]


def test_tool_list_is_read_only(client):
    tools = _rpc(client, "tools/list").json()["result"]["tools"]
    names = {t["name"] for t in tools}
    assert {"get_stats", "list_jobs", "get_job", "list_searches", "list_companies",
            "list_applications", "list_scheduled_jobs", "list_active_runs",
            "list_run_history", "get_scrape_log", "list_failing_sources",
            "get_activity_log", "list_runners"} == names
    assert all(t["annotations"]["readOnlyHint"] for t in tools)
    # The request context is not a tool argument.
    assert all("ctx" not in t["inputSchema"].get("properties", {}) for t in tools)


def test_every_tool_reaches_its_endpoint(client, test_db):
    job = make_job(test_db)
    args = {"get_job": {"job_id": str(job.id)}}
    for tool in (t["name"] for t in _rpc(client, "tools/list").json()["result"]["tools"]):
        _data(_call(client, tool, args.get(tool)))


def test_list_jobs_filters_and_is_brief(client, test_db):
    make_job(test_db, title="Art Director", company="Acme", description="x" * 5000)
    make_job(test_db, title="Illustrator", company="Globex")
    out = _data(_call(client, "list_jobs", {"title_search": "art dir"}))
    assert out["total"] == 1
    assert out["jobs"][0]["title"] == "Art Director"
    assert "description" not in out["jobs"][0]


def test_get_job_has_description(client, test_db):
    job = make_job(test_db, description="full text")
    assert _data(_call(client, "get_job", {"job_id": str(job.id)}))["description"] == "full text"


def test_api_error_is_a_tool_error(client):
    result = _call(client, "get_job", {"job_id": "00000000-0000-0000-0000-000000000000"})
    assert result["isError"]
    assert "404" in result["content"][0]["text"]


def test_wrong_install_password_is_refused(client):
    assert _rpc(client, "tools/list", **{"X-API-Key": "wrong"}).status_code == 401


def test_tool_call_is_scoped_to_the_token_account(client, test_db):
    from backend.accounts.context import use_account
    make_job(test_db, title="Owner job")
    member = _member(test_db)
    with use_account(member.id):
        make_job(test_db, title="Member job")

    as_member = _data(_call(client, "list_jobs", **{ACT_AS: str(member.id)}))
    assert [j["title"] for j in as_member["jobs"]] == ["Member job"]
    as_owner = _data(_call(client, "list_jobs"))
    assert [j["title"] for j in as_owner["jobs"]] == ["Owner job"]


def test_two_accounts_need_a_token(client, test_db):
    _member(test_db)
    resp = _rpc(client, "tools/list", **{ACT_AS: ""})
    assert resp.status_code == 401
    assert resp.json() == {"detail": "account_required"}


def test_not_started_without_lifespan(test_db):
    from fastapi.testclient import TestClient
    from backend.main import app
    resp = TestClient(app).post(MCP, json={}, headers=_ACCEPT)  # no `with`: no lifespan
    assert resp.status_code == 503
