"""Effective selection and restricted runner lifecycle, without a Docker daemon."""
import asyncio
import copy
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi.testclient import TestClient

from backend import runner_management as M
from backend.accounts.context import use_account
from backend.accounts.settings import put_setting
from backend.models.db import Account, SectionPolicy
from backend.runner_manager.controller import Catalog, Controller
from backend.runner_manager.docker import DockerError
from backend.cli_runner.schemas import Completion


def test_runner_memory_cap_is_trusted_install_configuration(monkeypatch):
    monkeypatch.setenv("JN_COMPOSE_PROJECT", "isolated")
    monkeypatch.setenv("JN_RUNNER_MEMORY_MB", "768")
    spec = Catalog.environment().specification("codex_cli")
    assert spec["HostConfig"]["Memory"] == 768 * 1024 ** 2
    assert spec["HostConfig"]["MemorySwap"] == 768 * 1024 ** 2
    assert "Memory" not in Catalog("isolated").specification("codex_cli")["HostConfig"]
    monkeypatch.setenv("JN_RUNNER_MEMORY_MB", "-1")
    with pytest.raises(ValueError, match="JN_RUNNER_MEMORY_MB"):
        Catalog.environment()


def test_effective_union_respects_policies_and_all_slots(test_db):
    b = Account(name="Partner", role="member")
    test_db.add(b)
    test_db.flush()
    put_setting(test_db, "llm_provider", "openrouter")
    # Catalog-only entries, tokens and external servers must never launch containers.
    put_setting(test_db, "llm_models_list", '[{"provider":"antigravity_cli","model":"x"}]')
    put_setting(test_db, "claude_code_oauth_token", "secret")
    put_setting(test_db, "llm_provider", "antigravity_cli", account_id=b.id)
    test_db.commit()
    assert M.required_providers() == []  # member still inherits
    policy = SectionPolicy(account_id=b.id, section="models", mode="own")
    test_db.add(policy)
    test_db.commit()
    assert M.required_providers() == ["antigravity_cli"]
    for slot in M.PROVIDER_KEYS:
        put_setting(test_db, "llm_provider", "ollama", account_id=b.id)
        put_setting(test_db, slot, "codex_cli", account_id=b.id)
        test_db.commit()
        assert M.required_providers() == ["codex_cli"], slot
        put_setting(test_db, slot, "", account_id=b.id)
        test_db.commit()
    put_setting(test_db, "scoring_llm_provider", "claude_code")
    policy.mode = "inherit"
    test_db.commit()
    assert M.required_providers() == ["claude_code"]
    test_db.delete(b)
    test_db.commit()
    assert M.required_providers() == ["claude_code"]
    put_setting(test_db, "scoring_llm_provider", "")  # disabled override
    test_db.commit()
    assert M.required_providers() == []


@pytest.mark.asyncio
async def test_coordinator_sends_only_union_and_retains_retry_on_failure(monkeypatch):
    monkeypatch.setattr(M, "required_providers", lambda: ["codex_cli"])
    monkeypatch.setattr(M, "ensure_token", lambda: "test")
    calls = []
    fail = True

    def transport(request):
        calls.append((request.method, request.url.path, request.content))
        if request.url.path.endswith("retry") and fail:
            return httpx.Response(503)
        return httpx.Response(200, json={"management_version": 1, "providers": []})

    factory = httpx.AsyncClient
    monkeypatch.setattr(M.httpx, "AsyncClient", lambda **kw: factory(transport=httpx.MockTransport(transport), **kw))
    c = M.Coordinator()
    c.retry_requested = True
    with pytest.raises(httpx.HTTPStatusError):
        await c.sync()
    assert c.retry_requested
    fail = False
    await c.sync()
    assert not c.retry_requested
    assert all(body == b'{"providers":["codex_cli"]}' for _, _, body in calls)


class FakeDocker:
    def __init__(self):
        self.containers = {}
        self.images = set()
        self.calls = []
        self.pull_gate = None
        self.pull_entered = asyncio.Event()
        self.fail_pull = False

    async def container(self, name):
        return copy.deepcopy(self.containers.get(name))

    async def image(self, name):
        return {"Id": name} if name in self.images else None

    async def pull(self, image, progress):
        self.calls.append(("pull", image))
        self.pull_entered.set()
        progress(10, 100)
        if self.pull_gate:
            await self.pull_gate.wait()
        if self.fail_pull:
            raise DockerError("Download failed")
        self.images.add(image)
        progress(100, 100)

    async def request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        if path == "/containers/create":
            name = kwargs["params"]["name"]
            assert name not in self.containers
            spec = kwargs["json"]
            self.containers[name] = {"Id": name, "Config": spec, "State": {"Status": "created"}}
            return {"Id": name}
        name = path.split("/")[2]
        if method == "DELETE":
            del self.containers[name]
        elif path.endswith("/start"):
            self.containers[name]["State"]["Status"] = "running"
        elif path.endswith("/stop"):
            self.containers[name]["State"]["Status"] = "exited"
        else:
            raise AssertionError((method, path))
        return {}

    async def close(self):
        pass


@pytest.fixture
def control(monkeypatch):
    monkeypatch.setattr("backend.runner_manager.controller.read_token", lambda: "test")
    docker = FakeDocker()
    client = AsyncMock()
    c = Controller(docker, Catalog("isolated", "local", "test"), client)
    client.get.return_value = httpx.Response(200, json={"management_version": 1, "protocol": 1,
                                                         "provider": "codex_cli", "active_requests": 0})
    return c


async def settled(c):
    await asyncio.gather(*(s.task for s in c.states.values() if s.task))


@pytest.mark.asyncio
async def test_single_flight_start_stop_preserves_images_and_volumes(control):
    c = control
    c.schedule()
    assert c.docker.calls == []  # never remove runners before first settings snapshot
    c.desired(["codex_cli"])
    c.desired(["codex_cli"])
    await settled(c)
    assert c.states["codex_cli"].phase == "ready"
    creates = [x for x in c.docker.calls if x[:2] == ("POST", "/containers/create")]
    assert len(creates) == 1
    spec = creates[0][2]["json"]
    assert spec["HostConfig"]["Binds"] == ["isolated_codex_auth:/root/.codex",
                                                     "isolated_runner_control:/run/jobnavigator-runner:ro"]
    assert "docker.sock" not in str(spec)
    assert len(c.docker.containers) == 1
    c.desired([])
    await settled(c)
    assert not c.docker.containers
    assert c.docker.images == {"local-codex-runner:test"}
    deletes = [x for x in c.docker.calls if x[0] == "DELETE"]
    assert deletes[0][2]["params"] == {"v": "false"}
    assert c.states["codex_cli"].phase == "absent"
    await c.close()


@pytest.mark.asyncio
async def test_unselect_during_download_never_creates_container(control):
    c = control
    c.docker.pull_gate = asyncio.Event()
    c.desired(["codex_cli"])
    await c.docker.pull_entered.wait()
    assert c.snapshot()["providers"][0]["downloaded_bytes"] == 10
    c.desired([])
    c.docker.pull_gate.set()
    await settled(c)
    assert not c.docker.containers
    assert not any(x[:2] == ("POST", "/containers/create") for x in c.docker.calls)
    await c.close()


@pytest.mark.asyncio
async def test_unselect_during_start_removes_container_and_refuses_new_calls(control):
    c = control
    entered, release = asyncio.Event(), asyncio.Event()
    request = c.docker.request
    async def blocked_start(method, path, **kw):
        if path.endswith("/start"):
            entered.set()
            await release.wait()
        return await request(method, path, **kw)
    c.docker.request = blocked_start
    c.desired(["codex_cli"])
    await entered.wait()
    c.desired([])
    release.set()
    await settled(c)
    body = Completion(protocol=1, provider="codex_cli", prompt="test", system="", model="", max_tokens=10)
    with pytest.raises(DockerError, match="not ready"):
        await c.complete(body)
    c.schedule()
    await settled(c)
    assert not c.docker.containers
    assert c.states["codex_cli"].phase == "absent"
    await c.close()


@pytest.mark.asyncio
async def test_foreign_container_and_pull_backoff(control):
    c = control
    name = c.catalog.name("codex_cli")
    c.docker.containers[name] = {"Config": {"Labels": {}}, "Id": name, "State": {"Status": "running"}}
    c.desired([])
    await settled(c)
    assert "foreign" in c.states["codex_cli"].message
    assert c.docker.calls == []
    del c.docker.containers[name]
    c.docker.fail_pull = True
    c.desired(["codex_cli"])
    await settled(c)
    assert c.states["codex_cli"].phase == "error"
    assert c.states["codex_cli"].retry_after > 0
    c.schedule()
    await settled(c)
    assert len([x for x in c.docker.calls if x[0] == "pull"]) == 1
    c.docker.fail_pull = False
    c.retry(["codex_cli"])
    await settled(c)
    assert c.states["codex_cli"].phase == "ready"
    await c.close()


@pytest.mark.asyncio
async def test_restart_checks_runner_active_requests_before_removal(control):
    c = control
    c.desired(["codex_cli"])
    await settled(c)
    restarted = Controller(c.docker, c.catalog, c.client)
    c.client.get.return_value = httpx.Response(200, json={"management_version": 1, "protocol": 1,
                                                         "provider": "codex_cli", "active_requests": 1})
    restarted.desired([])
    await settled(restarted)
    assert restarted.states["codex_cli"].phase == "draining"
    assert c.docker.containers
    c.client.get.return_value = httpx.Response(200, json={"management_version": 1, "protocol": 1,
                                                         "provider": "codex_cli", "active_requests": 0})
    restarted.schedule()
    await settled(restarted)
    assert not c.docker.containers
    await restarted.close()


@pytest.mark.asyncio
async def test_execution_holds_container_and_forwards_token_without_replay(control):
    c = control
    body = Completion(protocol=1, provider="codex_cli", prompt="hello", system="", model="", max_tokens=10,
                      claude_token="actual-token")
    with pytest.raises(DockerError, match="not ready"):
        await c.complete(body)
    c.desired(["codex_cli"])
    await settled(c)
    gate = asyncio.Event()
    entered = asyncio.Event()

    async def post(*args, **kw):
        assert kw["json"]["claude_token"] == "actual-token"
        entered.set()
        await gate.wait()
        raise httpx.ReadError("secret")

    c.client.post.side_effect = post
    task = asyncio.create_task(c.complete(body))
    await entered.wait()
    c.desired([])
    await settled(c)
    assert c.states["codex_cli"].phase == "draining"
    assert c.docker.containers
    gate.set()
    with pytest.raises(DockerError, match="not replayed"):
        await task
    c.schedule()
    await settled(c)
    assert not c.docker.containers
    assert c.client.post.call_count == 1
    await c.close()


def test_private_manager_schema_and_authentication(monkeypatch):
    from backend.runner_manager.server import create_app
    monkeypatch.setattr("backend.runner_manager.server.read_token", lambda: "test")
    c = Controller(FakeDocker(), Catalog("isolated"), AsyncMock())
    with TestClient(create_app(c)) as client:
        assert client.put("/v1/desired", json={"providers": []}).status_code == 401
        for invalid in ({"providers": ["ollama"]}, {"providers": [], "image": "evil", "token": "secret"}):
            r = client.put("/v1/desired", json=invalid, headers={"Authorization": "Bearer test"})
            assert r.status_code == 422
            assert "secret" not in r.text and "evil" not in r.text
        r = client.put("/v1/desired", json={"providers": []}, headers={"Authorization": "Bearer test"})
        assert r.status_code == 200
        assert r.json()["management_version"] == 1


def test_manual_mode_cannot_mutate_runners(monkeypatch):
    from backend.runner_manager.server import create_app
    monkeypatch.setenv("JN_RUNNER_MANAGEMENT", "0")
    monkeypatch.setattr("backend.runner_manager.server.read_token", lambda: "test")
    c = Controller(FakeDocker(), Catalog("isolated"), AsyncMock())
    with TestClient(create_app(c)) as client:
        assert client.get("/health").status_code == 200
        r = client.put("/v1/desired", json={"providers": ["codex_cli"]},
                       headers={"Authorization": "Bearer test"})
        assert r.status_code == 409
        assert not c.initialized and not c.docker.calls


@pytest.mark.asyncio
async def test_unreachable_runner_waits_full_grace_and_resets_after_activity(control):
    from backend.cli_runner.protocol import AGY_TIMEOUT
    import time
    c = control
    c.desired(["codex_cli"])
    await settled(c)
    c.client.get.side_effect = httpx.ConnectError("temporary outage")
    c.desired([])
    await settled(c)
    s = c.states["codex_cli"]
    assert s.phase == "draining" and s.unknown_since
    s.unknown_since = time.monotonic() - AGY_TIMEOUT - 41
    c.client.get.side_effect = None
    c.client.get.return_value = httpx.Response(200, json={"management_version": 1, "protocol": 1,
                                                         "provider": "codex_cli", "active_requests": 1})
    c.schedule()
    await settled(c)
    assert s.unknown_since == 0 and c.docker.containers
    c.client.get.side_effect = httpx.ConnectError("outage again")
    c.schedule()
    await settled(c)
    assert c.docker.containers and s.unknown_since
    s.unknown_since = time.monotonic() - AGY_TIMEOUT - 41
    c.schedule()
    await settled(c)
    assert not c.docker.containers
    await c.close()


@pytest.mark.asyncio
async def test_docker_pull_progress_missing_image_and_safe_errors():
    from backend.runner_manager.docker import Docker
    observed = []
    def handle(request):
        observed.append(request)
        if request.method == "GET":
            return httpx.Response(404)
        return httpx.Response(200, content=(
            b'{"id":"layer","status":"Downloading","progressDetail":{"current":10,"total":20}}\n'
            b'{"id":"layer","status":"Download complete"}\n'
            b'{"error":"registry-secret-error"}\n'))
    d = Docker()
    await d.client.aclose()
    d.client = httpx.AsyncClient(base_url="http://docker", transport=httpx.MockTransport(handle))
    try:
        assert await d.image("registry.example/org/runner:tag") is None
        progress = []
        with pytest.raises(DockerError) as exc:
            await d.pull("registry.example/org/runner:tag", lambda a, b: progress.append((a, b)))
        assert progress == [(10, 20), (20, 20)]
        assert "secret" not in str(exc.value)
        assert observed[-1].url.params["fromImage"] == "registry.example/org/runner:tag"
    finally:
        await d.close()


def test_status_filters_other_accounts_and_restricts_retry(test_db, monkeypatch):
    from backend.api.routes_llm import runner_status, retry_runners
    from fastapi import HTTPException
    monkeypatch.setenv("JN_RUNNER_MANAGEMENT", "1")
    monkeypatch.setattr(M.coordinator, "snapshot", {"providers": [
        {"provider": "codex_cli", "state": "ready"}, {"provider": "claude_code", "state": "ready"}]})
    monkeypatch.setattr(M.coordinator, "error", False)
    b = Account(name="Other", role="member")
    test_db.add(b)
    test_db.flush()
    test_db.add(SectionPolicy(account_id=b.id, section="models", mode="own"))
    put_setting(test_db, "llm_provider", "codex_cli", account_id=b.id)
    test_db.commit()
    with use_account(b.id):
        assert [x["provider"] for x in runner_status()["providers"]] == ["codex_cli"]
        with pytest.raises(HTTPException) as error:
            retry_runners()
        assert error.value.status_code == 403
    assert len(runner_status()["providers"]) == 2


def _idle_control(monkeypatch, minutes=1):
    monkeypatch.setattr("backend.runner_manager.controller.read_token", lambda: "test")
    client = AsyncMock()
    client.get.return_value = httpx.Response(200, json={"management_version": 1, "protocol": 1,
                                                         "provider": "codex_cli", "active_requests": 0})
    client.post.return_value = httpx.Response(200, json={"protocol": 1, "result": {"text": "ok", "usage": {}}})
    return Controller(FakeDocker(), Catalog("isolated", "local", "test", idle_minutes=minutes), client)


def _status(c, name):
    return c.docker.containers[name]["State"]["Status"]


def test_idle_minutes_is_trusted_install_configuration(monkeypatch):
    monkeypatch.setenv("JN_COMPOSE_PROJECT", "isolated")
    assert Catalog.environment().idle_minutes == 10
    monkeypatch.setenv("JN_RUNNER_IDLE_MINUTES", "0")
    assert Catalog.environment().idle_minutes == 0
    monkeypatch.setenv("JN_RUNNER_IDLE_MINUTES", "2000")
    with pytest.raises(ValueError, match="JN_RUNNER_IDLE_MINUTES"):
        Catalog.environment()


@pytest.mark.asyncio
async def test_an_idle_runner_is_stopped_and_the_next_call_starts_it(monkeypatch):
    c = _idle_control(monkeypatch)
    clock = [1000.0]
    monkeypatch.setattr("backend.runner_manager.controller.time.monotonic", lambda: clock[0])
    name = c.catalog.name("codex_cli")
    c.desired(["codex_cli"])
    await settled(c)
    assert c.states["codex_cli"].phase == "ready" and _status(c, name) == "running"
    clock[0] += 59
    c.schedule()
    await settled(c)
    assert _status(c, name) == "running"            # not idle long enough
    clock[0] += 2
    c.schedule()
    await settled(c)
    assert c.states["codex_cli"].phase == "sleeping" and _status(c, name) == "exited"
    assert name in c.docker.containers               # stopped, not removed: logins and image stay
    c.schedule()
    await settled(c)
    assert _status(c, name) == "exited"              # the loop does not start it again
    body = Completion(protocol=1, provider="codex_cli", prompt="test", system="", model="", max_tokens=10)
    response = await c.complete(body)
    assert response.status_code == 200
    assert c.states["codex_cli"].phase == "ready" and _status(c, name) == "running"
    await c.close()


@pytest.mark.asyncio
async def test_a_runner_with_a_call_in_flight_is_not_stopped(monkeypatch):
    c = _idle_control(monkeypatch)
    clock = [1000.0]
    monkeypatch.setattr("backend.runner_manager.controller.time.monotonic", lambda: clock[0])
    c.desired(["codex_cli"])
    await settled(c)
    c.client.get.return_value = httpx.Response(200, json={"management_version": 1, "protocol": 1,
                                                           "provider": "codex_cli", "active_requests": 1})
    clock[0] += 3600
    c.schedule()
    await settled(c)
    assert c.states["codex_cli"].phase == "ready"
    assert _status(c, c.catalog.name("codex_cli")) == "running"
    await c.close()


@pytest.mark.asyncio
async def test_idle_zero_keeps_runners_running(monkeypatch):
    c = _idle_control(monkeypatch, minutes=0)
    clock = [1000.0]
    monkeypatch.setattr("backend.runner_manager.controller.time.monotonic", lambda: clock[0])
    c.desired(["codex_cli"])
    await settled(c)
    clock[0] += 86400
    c.schedule()
    await settled(c)
    assert _status(c, c.catalog.name("codex_cli")) == "running"
    await c.close()


def test_the_project_comes_from_the_managers_own_container_when_not_set(monkeypatch):
    """An install cloned into another folder has another Compose project (jtrakproject_llm,
    jtrakproject_claude_accounts); assuming `jobnavigator` would miss its network and logins."""
    monkeypatch.setenv("JN_COMPOSE_PROJECT", "")
    assert Catalog.environment("jtrakproject").network == "jtrakproject_llm"
    with pytest.raises(ValueError, match="JN_COMPOSE_PROJECT"):
        Catalog.environment(None)
    monkeypatch.setenv("JN_COMPOSE_PROJECT", "explicit")
    assert Catalog.environment("jtrakproject").project == "explicit"


@pytest.mark.asyncio
async def test_own_project_reads_the_compose_label(monkeypatch):
    from backend.runner_manager.docker import Docker
    d = Docker.__new__(Docker)
    monkeypatch.setattr("socket.gethostname", lambda: "abc123")

    async def container(name):
        assert name == "abc123"
        return {"Config": {"Labels": {"com.docker.compose.project": "jtrakproject"}}}
    d.container = container
    assert await d.own_project() == "jtrakproject"

    async def missing(name):
        raise DockerError("Docker operation failed (HTTP 500)")
    d.container = missing
    assert await d.own_project() is None
