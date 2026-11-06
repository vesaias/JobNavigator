"""Minimal Docker Engine client. Callers supply only trusted catalog specifications."""
import json
from urllib.parse import quote

import httpx


class DockerError(RuntimeError):
    pass


class Docker:
    def __init__(self, socket="/var/run/docker.sock"):
        self.client = httpx.AsyncClient(base_url="http://docker", trust_env=False,
                                       transport=httpx.AsyncHTTPTransport(uds=socket), timeout=30)

    async def close(self):
        await self.client.aclose()

    async def request(self, method, path, *, missing=False, **kwargs):
        response = await self.client.request(method, path, **kwargs)
        if missing and response.status_code == 404:
            return None
        if response.status_code == 304 and method == "POST" and path.endswith(("/start", "/stop")):
            return {}
        if not response.is_success:
            # Engine errors can contain host paths/registry details; keep UI messages fixed.
            raise DockerError(f"Docker operation failed (HTTP {response.status_code})")
        return response.json() if response.content else {}

    async def image(self, name):
        return await self.request("GET", f"/images/{quote(name, safe='')}/json", missing=True)

    async def own_project(self):
        """The Compose project of the container this code runs in (its hostname is the
        container id), or None outside Compose."""
        import socket
        try:
            me = await self.container(socket.gethostname())
        except (DockerError, OSError):
            return None
        labels = ((me or {}).get("Config") or {}).get("Labels") or {}
        return labels.get("com.docker.compose.project")

    async def container(self, name):
        return await self.request("GET", f"/containers/{quote(name, safe='')}/json", missing=True)

    async def pull(self, image, progress):
        layers = {}
        async with self.client.stream("POST", "/images/create", params={"fromImage": image},
                                      timeout=httpx.Timeout(1800, connect=10)) as response:
            if not response.is_success:
                raise DockerError(f"Image download failed (HTTP {response.status_code}); publish or build this runner image")
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                event = json.loads(line)
                if event.get("error") or event.get("errorDetail"):
                    raise DockerError("Image download failed; check registry access, available disk space and image tag")
                detail = event.get("progressDetail") or {}
                if event.get("id") and event.get("status") == "Downloading":
                    layers[event["id"]] = (detail.get("current", 0), detail.get("total", 0))
                if event.get("id") in layers and event.get("status") in ("Download complete", "Pull complete"):
                    _, total = layers[event["id"]]
                    layers[event["id"]] = (total, total)
                progress(sum(row[0] for row in layers.values()), sum(row[1] for row in layers.values()))
