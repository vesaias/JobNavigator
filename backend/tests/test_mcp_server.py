"""MCP server at /api/mcp: the tool list, the read tools, and the auth of a tool call
(install password and account are the caller's, checked by the same middleware)."""
import json

from backend.tests.r4_support import ACT_AS, API_KEY, _no_outbound, client, make_job  # noqa: F401 — fixtures

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


WRITE_TOOLS = {"update_jobs", "mark_job_applied", "tailor_resume", "generate_cover_letter"}


def _tools(c):
    return _rpc(c, "tools/list").json()["result"]["tools"]


def test_tool_list_marks_the_write_tools(client):
    tools = _tools(client)
    names = {t["name"] for t in tools}
    assert {"get_stats", "list_jobs", "get_job", "list_searches", "list_companies",
            "list_applications", "list_scheduled_jobs", "list_active_runs",
            "list_run_history", "get_scrape_log", "list_failing_sources",
            "get_activity_log", "list_runners", "list_in_flight", "get_run",
            "list_resumes", "list_cover_letters"} | WRITE_TOOLS == names
    assert {t["name"] for t in tools if not t["annotations"]["readOnlyHint"]} == WRITE_TOOLS
    # The request context is not a tool argument.
    assert all("ctx" not in t["inputSchema"].get("properties", {}) for t in tools)


def test_every_read_tool_reaches_its_endpoint(client, test_db):
    from backend.models.db import JobRun
    job = make_job(test_db)
    run = JobRun(job_type="tailor_resume", trigger="manual", status="failed", error="runner lost")
    test_db.add(run)
    test_db.commit()
    args = {"get_job": {"job_id": str(job.id)}, "get_run": {"run_id": str(run.id)}}
    for tool in (t["name"] for t in _tools(client) if t["name"] not in WRITE_TOOLS):
        _data(_call(client, tool, args.get(tool)))
    assert _data(_call(client, "get_run", args["get_run"]))["error"] == "runner lost"


def test_update_jobs_returns_the_previous_values(client, test_db):
    from backend.models.db import Job
    a, b = make_job(test_db), make_job(test_db, status="saved")
    out = _data(_call(client, "update_jobs", {"job_ids": [str(a.id), str(b.id)], "status": "skip"}))
    assert out["updated"] == 2
    assert out["previous"] == {str(a.id): {"status": "new"}, str(b.id): {"status": "saved"}}
    test_db.expire_all()
    assert {test_db.get(Job, a.id).status, test_db.get(Job, b.id).status} == {"skip"}


def test_update_jobs_needs_a_field(client, test_db):
    job = make_job(test_db)
    assert _call(client, "update_jobs", {"job_ids": [str(job.id)]})["isError"]


def test_mark_job_applied_creates_the_application(client, test_db):
    from backend.models.db import Application
    job = make_job(test_db)
    out = _data(_call(client, "mark_job_applied", {"job_id": str(job.id)}))
    assert out["status"] == "applied" and out["created_application_id"]
    assert test_db.query(Application).filter(Application.job_id == job.id).count() == 1


def test_run_tools_post_to_their_endpoints(client, test_db):
    """No LLM here: an unknown resume proves that the POST reached the endpoint's checks."""
    job = make_job(test_db, description="text")
    missing = "00000000-0000-0000-0000-000000000000"
    for tool, key in (("tailor_resume", "base_resume_id"), ("generate_cover_letter", "resume_id")):
        result = _call(client, tool, {key: missing, "job_id": str(job.id)})
        assert result["isError"] and "404" in result["content"][0]["text"], result


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
