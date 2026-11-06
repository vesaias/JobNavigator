"""One serialized lifecycle per allowed provider; never remove images or volumes."""
import asyncio
from dataclasses import dataclass, field
import hashlib
import json
import logging
import os
import re
import time

import httpx

from backend.cli_runner.auth import read_token
from backend.cli_runner.protocol import AGY_TIMEOUT, CLI_TIMEOUT, PROTOCOL_VERSION, SERVICES
from .docker import DockerError

logger = logging.getLogger("jobnavigator.runner_manager")


@dataclass(frozen=True)
class Catalog:
    project: str
    image_prefix: str = "ghcr.io/vesaias/jobnavigator"
    tag: str = "latest"
    memory_mb: int = 0
    # Minutes without a call before a ready runner is stopped (0 = keep it running).
    idle_minutes: int = 0

    def __post_init__(self):
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,62}", self.project):
            raise ValueError("Invalid Compose project name")
        if type(self.memory_mb) is not int or (self.memory_mb != 0 and not 64 <= self.memory_mb <= 65536):
            raise ValueError("JN_RUNNER_MEMORY_MB must be 0 (unlimited) or 64..65536")
        if type(self.idle_minutes) is not int or not 0 <= self.idle_minutes <= 1440:
            raise ValueError("JN_RUNNER_IDLE_MINUTES must be 0 (never) or 1..1440")

    @classmethod
    def environment(cls, project=None):
        """`JN_COMPOSE_PROJECT`, else `project` (the manager's own Compose project)."""
        project = os.getenv("JN_COMPOSE_PROJECT", "").strip() or project
        if not project:
            raise ValueError("Compose project unknown: set JN_COMPOSE_PROJECT")
        return cls(project,
                   os.getenv("JN_RUNNER_IMAGE_PREFIX", "ghcr.io/vesaias/jobnavigator"),
                   os.getenv("JN_IMAGE_TAG", "latest"), int(os.getenv("JN_RUNNER_MEMORY_MB", "0")),
                   int(os.getenv("JN_RUNNER_IDLE_MINUTES", "10")))

    @property
    def network(self):
        return f"{self.project}_llm"

    def name(self, provider):
        return f"{self.project}-{SERVICES[provider]}-1"

    def image(self, provider):
        return f"{self.image_prefix}-{SERVICES[provider]}:{self.tag}"

    def specification(self, provider):
        volume, path = {"codex_cli": ("codex_auth", "/root/.codex"),
                        "claude_code": ("claude_accounts", "/root/.claude-accounts"),
                        "antigravity_cli": ("antigravity_auth", "/root/.gemini")}[provider]
        spec = {
            "Image": self.image(provider),
            "Env": [f"JN_RUNNER_PROVIDER={provider}"],
            "Labels": {"com.docker.compose.project": self.project,
                       "com.docker.compose.service": SERVICES[provider],
                       "com.docker.compose.container-number": "1",
                       "com.docker.compose.oneoff": "False",
                       "io.jobnavigator.runner-manager": "1"},
            "HostConfig": {"Init": True, "NetworkMode": self.network,
                           "RestartPolicy": {"Name": "unless-stopped"},
                           "Binds": [f"{self.project}_{volume}:{path}",
                                     f"{self.project}_runner_control:/run/jobnavigator-runner:ro"],
                           "LogConfig": {"Type": "json-file", "Config": {"max-size": "20m", "max-file": "5"}}},
            "NetworkingConfig": {"EndpointsConfig": {self.network: {"Aliases": [SERVICES[provider]]}}},
        }
        if self.memory_mb:
            spec["HostConfig"].update(Memory=self.memory_mb * 1024 ** 2,
                                      MemorySwap=self.memory_mb * 1024 ** 2)
        # Compose's exec/logs/down discovery requires this label to exist:
        # https://github.com/docker/compose/blob/main/pkg/compose/containers.go
        # Hash our managed specification; explicit manual `compose up` may recreate it.
        spec["Labels"]["com.docker.compose.config-hash"] = hashlib.sha256(
            json.dumps(spec, sort_keys=True).encode()).hexdigest()
        return spec


@dataclass
class State:
    desired: bool = False
    phase: str = "unknown"
    message: str = "Waiting for account settings"
    downloaded: int = 0
    total: int = 0
    active: int = 0
    retry_after: float = 0
    failures: int = 0
    starting_since: float = 0
    unknown_since: float = 0
    last_used: float = 0       # monotonic time of the last call (or of becoming ready)
    sleeping: bool = False     # stopped for being idle; the next call starts it
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    task: object = None


class Controller:
    def __init__(self, docker, catalog, client=None):
        self.docker = docker
        self.catalog = catalog
        self.client = client or httpx.AsyncClient(trust_env=False, timeout=5)
        self.states = {provider: State() for provider in SERVICES}
        self.initialized = False

    def snapshot(self):
        return {"management_version": 1, "providers": [
            {"provider": provider, "required": state.desired, "state": state.phase,
             "message": state.message, "downloaded_bytes": state.downloaded,
             "total_bytes": state.total, "active_requests": state.active}
            for provider, state in self.states.items()]}

    def desired(self, providers):
        if not set(providers) <= SERVICES.keys():
            raise ValueError("Unknown provider")
        self.initialized = True
        for provider, state in self.states.items():
            selected = provider in providers
            if selected != state.desired:
                state.failures = 0
                state.retry_after = 0
                state.sleeping = False
                state.last_used = 0
            state.desired = selected
        self.schedule()

    def retry(self, providers):
        for provider in providers:
            state = self.states[provider]
            if state.desired:
                state.retry_after = 0
        self.schedule()

    def schedule(self):
        if not self.initialized:
            return
        for provider, state in self.states.items():
            if (state.task is None or state.task.done()) and time.monotonic() >= state.retry_after:
                state.task = asyncio.create_task(self.step(provider))

    async def loop(self):
        while True:
            self.schedule()
            await asyncio.sleep(2)

    async def close(self):
        tasks = [state.task for state in self.states.values() if state.task is not None]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await self.client.aclose()
        await self.docker.close()

    def _owned(self, provider, container):
        labels = container.get("Config", {}).get("Labels") or {}
        if (labels.get("com.docker.compose.project") != self.catalog.project or
                labels.get("com.docker.compose.service") != SERVICES[provider] or
                labels.get("com.docker.compose.oneoff", "False").lower() == "true"):
            raise DockerError("A foreign container uses this runner name; no changes were made to it")

    async def status(self, provider):
        try:
            response = await self.client.get(f"http://{SERVICES[provider]}:8000/v1/status",
                                             headers={"Authorization": f"Bearer {read_token()}"})
        except httpx.HTTPError:
            return None
        if response.status_code == 404:
            raise DockerError("Runner image is out of date; pull or rebuild the current runner images")
        if not response.is_success:
            return None
        data = response.json()
        if (data.get("management_version") != 1 or data.get("provider") != provider or
                data.get("protocol") != PROTOCOL_VERSION or
                type(data.get("active_requests")) is not int or data["active_requests"] < 0):
            raise DockerError("Runner returned an incompatible status; pull or rebuild it")
        return data

    async def _remove(self, provider, state, container):
        if state.active:
            state.phase, state.message = "draining", "Finishing active requests before removing the container"
            return False
        if container["State"]["Status"] == "running":
            remote = await self.status(provider)
            if remote is not None:
                state.unknown_since = 0
            if remote is not None and remote["active_requests"]:
                state.phase, state.message = "draining", "Runner is finishing active requests"
                return False
            if remote is None:
                state.unknown_since = state.unknown_since or time.monotonic()
                if time.monotonic() - state.unknown_since < AGY_TIMEOUT + 40:
                    state.phase, state.message = "draining", "Waiting to confirm the runner has finished"
                    return False
            state.phase, state.message = "removing", "Stopping unused container"
            if state.desired:
                return False
            await self.docker.request("POST", f"/containers/{container['Id']}/stop", params={"t": 10})
        if state.desired:
            # Desired configuration may have changed during the stop operation.
            return False
        await self.docker.request("DELETE", f"/containers/{container['Id']}", params={"v": "false"})
        state.phase, state.message = "absent", "Not selected in any account"
        state.unknown_since = 0
        return True

    async def step(self, provider):
        state = self.states[provider]
        async with state.lock:
            try:
                container = await self.docker.container(self.catalog.name(provider))
                if container is not None:
                    self._owned(provider, container)
                if not state.desired:
                    if container is None:
                        state.phase, state.message = "absent", "Not selected in any account"
                    else:
                        await self._remove(provider, state, container)
                    return
                if container is None:
                    image = await self.docker.image(self.catalog.image(provider))
                    if image is None:
                        state.phase, state.message = "pulling", "Downloading runner image"
                        state.downloaded = state.total = 0

                        def progress(current, total):
                            state.downloaded, state.total = current, total

                        await self.docker.pull(self.catalog.image(provider), progress)
                    if not state.desired:
                        state.phase, state.message = "absent", "Not selected in any account"
                        return
                    state.phase, state.message = "creating", "Creating runner container"
                    await self.docker.request("POST", "/containers/create",
                                              params={"name": self.catalog.name(provider)},
                                              json=self.catalog.specification(provider))
                    container = await self.docker.container(self.catalog.name(provider))
                if not state.desired:
                    await self._remove(provider, state, container)
                    return
                if state.sleeping:
                    if container["State"]["Status"] != "running":
                        state.phase, state.message = "sleeping", self._sleep_message()
                        return
                    state.sleeping = False   # started by hand (`docker compose up`)
                if container["State"]["Status"] != "running":
                    state.phase, state.message = "starting", "Starting runner container"
                    await self.docker.request("POST", f"/containers/{container['Id']}/start")
                    state.starting_since = time.monotonic()
                remote = await self.status(provider)
                if remote is None:
                    state.starting_since = state.starting_since or time.monotonic()
                    if time.monotonic() - state.starting_since > 90:
                        raise DockerError("Runner did not become ready; check its installation and logs")
                    state.phase, state.message = "starting", "Waiting for runner readiness"
                else:
                    state.phase, state.message = "ready", "Container ready; subscription login is checked on use"
                    state.starting_since = state.unknown_since = 0
                    state.failures = 0
                    await self._sleep_if_idle(provider, state, container, remote)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                state.phase = "error"
                state.message = str(exc) if isinstance(exc, DockerError) else "Runner management failed; check Docker and the controller logs"
                logger.warning("Runner %s management failed (%s): %s", provider, type(exc).__name__, state.message)
                state.failures += 1
                state.retry_after = time.monotonic() + min(30 * 2 ** min(state.failures - 1, 3), 240)

    async def complete(self, body):
        provider = body.provider
        state = self.states[provider]
        if state.desired and state.sleeping:
            await self.wake(provider)
        if not state.desired or state.phase != "ready":
            self.schedule()
            raise DockerError("Runner is not ready. Check provider status in Settings > Models and try again")
        async with state.lock:
            if not state.desired or state.phase != "ready":
                raise DockerError("Runner selection changed; try again with the current settings")
            state.active += 1
            state.last_used = time.monotonic()
        payload = body.model_dump(mode="json")
        payload["claude_token"] = body.claude_token.get_secret_value()
        limit = AGY_TIMEOUT if provider == "antigravity_cli" else CLI_TIMEOUT + 30
        try:
            return await self.client.post(f"http://{SERVICES[provider]}:8000/v1/complete", json=payload,
                                          headers={"Authorization": f"Bearer {read_token()}"},
                                          timeout=httpx.Timeout(limit + 10, connect=5))
        except httpx.HTTPError:
            raise DockerError("Connection to runner lost; execution outcome is unknown and was not replayed") from None
        finally:
            state.active -= 1
            state.last_used = time.monotonic()

    def _sleep_message(self):
        return (f"Stopped after {self.catalog.idle_minutes} idle minutes to free memory; "
                "the next call starts it")

    async def _sleep_if_idle(self, provider, state, container, remote):
        """Stop a ready runner that has had no call for `idle_minutes` (kept, not removed)."""
        if not self.catalog.idle_minutes or state.active or remote["active_requests"]:
            return
        now = time.monotonic()
        state.last_used = state.last_used or now
        if now - state.last_used < self.catalog.idle_minutes * 60:
            return
        await self.docker.request("POST", f"/containers/{container['Id']}/stop", params={"t": 10})
        state.sleeping = True
        state.phase, state.message = "sleeping", self._sleep_message()
        logger.info("Runner %s stopped after %s idle minutes", provider, self.catalog.idle_minutes)

    async def wake(self, provider, timeout=90):
        """Start a sleeping runner and wait until it answers (a call waits here)."""
        state = self.states[provider]
        state.sleeping = False
        state.last_used = time.monotonic()
        deadline = time.monotonic() + timeout
        while state.desired and time.monotonic() < deadline:
            await self.step(provider)
            if state.phase in ("ready", "error"):
                return
            await asyncio.sleep(0.5)
