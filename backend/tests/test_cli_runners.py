"""The backend/runner wire boundary, authentication, isolation and lifecycle."""
import asyncio
import sys
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.analyzer import runner_client
from backend.cli_runner import runtime, paths
from backend.cli_runner.auth import ensure_token
from backend.cli_runner.protocol import CLITimeoutError, NonRetryableLLMError
from backend.cli_runner.server import create_app


@pytest.fixture
def token(monkeypatch, tmp_path):
    monkeypatch.setenv("JN_RUNNER_TOKEN_FILE", str(tmp_path / "control" / "token"))
    return ensure_token()


def body(**kw):
    return {"protocol": 1, "provider": "codex_cli", "prompt": "resume", "system": "score", "model": "test",
            "max_tokens": 100, **kw}


def test_runner_authenticates_before_execution_and_never_echoes_secrets(token, monkeypatch):
    async def forbidden(*a, **kw):
        pytest.fail("Unauthorized or invalid request executed a CLI")

    monkeypatch.setattr(runtime, "execute", forbidden)
    with TestClient(create_app("codex_cli")) as client:
        assert client.get("/health").json()["protocol"] == 1
        assert client.post("/v1/complete", json=body()).status_code == 401
        response = client.post("/v1/complete", json=body(account_id="../owner", claude_token="secret"),
                               headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 422
        assert "secret" not in response.text and "../owner" not in response.text
        assert client.post("/v1/complete", json=body(command="rm"),
                           headers={"Authorization": f"Bearer {token}"}).status_code == 422
        assert client.post("/v1/complete", json=body(provider="claude_code"),
                           headers={"Authorization": f"Bearer {token}"}).status_code == 409


@pytest.fixture
def wire(token, monkeypatch):
    """Use real HTTP serialization and ASGI endpoints, with a fake subprocess only."""
    original = httpx.AsyncClient
    app = create_app("codex_cli")

    def client(**kwargs):
        return original(transport=httpx.ASGITransport(app=app), **kwargs)

    monkeypatch.setattr(runner_client.httpx, "AsyncClient", client)
    return app


@pytest.mark.asyncio
async def test_backend_and_runner_roundtrip_preserves_login_scope(wire, monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "CODEX_ACCOUNTS_ROOT", str(tmp_path / "accounts"))
    account = uuid.uuid4()
    seen = []

    async def fake_cli(cmd, stdin, env=None, **kwargs):
        seen.append((cmd, stdin, env))
        if cmd[:3] == ["codex", "login", "status"]:
            return 0, b"", b""
        return 0, b'{"type":"item.completed","item":{"type":"agent_message","text":"ok"}}', b""

    monkeypatch.setenv("DATABASE_URL", "must-not-reach-cli")
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-reach-cli")
    monkeypatch.setattr(runtime, "_run_cli", fake_cli)
    result = await runner_client.complete("codex_cli", "resume", "score", "test", 100,
                                          account_id=account, effort="high")
    assert result["text"] == "ok"
    assert all(call[2]["CODEX_HOME"] == str(tmp_path / "accounts" / str(account)) for call in seen)
    assert all("DATABASE_URL" not in call[2] and "OPENAI_API_KEY" not in call[2] for call in seen)
    assert seen[-1][1] == b"score\n\nresume"


@pytest.mark.parametrize("error, expected", [
    (NonRetryableLLMError("quota exhausted"), NonRetryableLLMError),
    (CLITimeoutError("deadline", b"private partial output"), CLITimeoutError),
    (RuntimeError("transient"), RuntimeError),
])
@pytest.mark.asyncio
async def test_wire_preserves_error_class_without_leaking_partial_output(wire, monkeypatch, error, expected):
    async def fail(*a, **kw):
        raise error

    monkeypatch.setattr(runtime, "execute", fail)
    with pytest.raises(expected) as caught:
        await runner_client.complete("codex_cli", "resume", "score", "test", 100)
    assert type(caught.value) is expected
    assert "private partial output" not in str(caught.value)


@pytest.mark.asyncio
async def test_unavailable_runner_and_lost_response_are_not_replayed(token, monkeypatch):
    for error in (httpx.ConnectError("offline"), httpx.ReadTimeout("lost response")):
        count = []

        async def post(*a, **kw):
            count.append(1)
            raise error

        monkeypatch.setattr(httpx.AsyncClient, "post", post)
        with pytest.raises(NonRetryableLLMError):
            await runner_client.complete("codex_cli", "p", "s", "m", 10)
        assert count == [1]


@pytest.mark.asyncio
async def test_busy_runner_rejects_without_queueing_or_executing(token, monkeypatch):
    release = asyncio.Event()
    started = []

    async def run(*a, **kw):
        started.append(1)
        await release.wait()
        return {"text": "ok", "usage": {}}

    monkeypatch.setattr(runtime, "execute", run)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app("codex_cli")),
                                 base_url="http://runner", headers={"Authorization": f"Bearer {token}"}) as client:
        pending = [asyncio.create_task(client.post("/v1/complete", json=body())) for _ in range(2)]
        for _ in range(100):
            if len(started) == 2:
                break
            await asyncio.sleep(0.001)
        try:
            assert len(started) == 2
            busy = await client.post("/v1/complete", json=body())
            assert busy.status_code == 503
            assert len(started) == 2
        finally:
            release.set()
            await asyncio.gather(*pending)


@pytest.mark.asyncio
async def test_deleted_account_is_refused_and_inflight_state_is_removed(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "CODEX_ACCOUNTS_ROOT", str(tmp_path / "accounts"))
    account = uuid.uuid4()
    home = paths.account_home("codex_cli", account)
    marker = paths.deletion_marker(home)

    async def removed_while_running(*a, **kw):
        marker.parent.mkdir(parents=True)
        marker.touch()
        home.mkdir(parents=True)
        (home / "auth.json").write_text("private")
        return {"text": "ok", "usage": {}}

    monkeypatch.setattr(runtime, "_call_codex_cli", removed_while_running)
    await runtime.execute("codex_cli", "p", "s", "m", 10, account_id=account)
    assert not home.exists()
    with pytest.raises(NonRetryableLLMError, match="removed"):
        await runtime.execute("codex_cli", "p", "s", "m", 10, account_id=account)


def test_shared_service_credential_is_stable_and_never_overwrites_an_existing_login(token):
    assert ensure_token() == token


@pytest.mark.asyncio
async def test_concurrent_requests_never_share_account_or_claude_token(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "CLAUDE_ACCOUNTS_ROOT", str(tmp_path))
    observed = []

    async def run(*a, **kw):
        before = (runtime._own_login_account(), runtime._claude_code_token())
        await asyncio.sleep(0)
        observed.append((before, (runtime._own_login_account(), runtime._claude_code_token())))
        return {"text": "ok", "usage": {}}

    monkeypatch.setattr(runtime, "_call_claude_code", run)
    accounts = [uuid.uuid4(), uuid.uuid4()]
    await asyncio.gather(*(runtime.execute("claude_code", "p", "s", "m", 10,
                                          account_id=account, claude_token=str(account)) for account in accounts))
    assert {before for before, after in observed} == {(account, str(account)) for account in accounts}
    assert all(before == after for before, after in observed)
    assert runtime._own_login_account() is None and runtime._claude_code_token() == ""


@pytest.mark.asyncio
async def test_real_subprocess_cancellation_reaps_process_and_preserves_partial_output(tmp_path):
    pidfile = tmp_path / "pid"
    task = asyncio.create_task(runtime._run_cli(
        [sys.executable, "-u", "-c",
         "import os, pathlib, sys, time; pathlib.Path(sys.argv[1]).write_text(str(os.getpid())); "
         "print('partial', flush=True); time.sleep(60)", str(pidfile)], b""))
    try:
        for _ in range(500):
            if pidfile.exists():
                break
            await asyncio.sleep(0.01)
        assert pidfile.exists()
        await asyncio.sleep(0.02)
        task.cancel()
        with pytest.raises(asyncio.CancelledError) as cancelled:
            await task
        assert b"partial" in cancelled.value.stdout
        if sys.platform != "win32":
            import os
            with pytest.raises(ProcessLookupError):
                os.kill(int(pidfile.read_text()), 0)
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
