"""Exercise built runner images over a real Docker network without user logins.

Run: python tests/tools/runner_smoke.py
Uses jobnavigator-{backend,codex-runner,claude-runner,antigravity-runner}:local.
All containers, networks and volumes have a random name and are removed on exit.
No project .env, host directories, database or existing auth volume is mounted.
"""
import argparse
import subprocess
import time
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", default="jobnavigator")
    parser.add_argument("--tag", default="local")
    args = parser.parse_args()
    scope = "jn-runner-test-" + uuid.uuid4().hex[:12]
    names = []
    volumes = []

    def docker(*command):
        result = subprocess.run(["docker", *command], capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(f"Docker command failed: {command[0]}\n{result.stderr}\n{result.stdout}")
        return result.stdout.strip()

    def image(name):
        return f"{args.prefix}-{name}:{args.tag}"

    try:
        docker("network", "create", scope)
        for suffix in ("control", "codex", "agy", "claude"):
            volume = f"{scope}-{suffix}"
            docker("volume", "create", volume)
            volumes.append(volume)
        docker("run", "--rm", "--volume", f"{scope}-control:/run/jobnavigator-runner",
               image("backend"), "python", "-c",
               "from backend.cli_runner.auth import ensure_token; ensure_token()")
        for service, volume, target in (
            ("codex-runner", "codex", "/root/.codex"),
            ("claude-runner", "claude", "/root/.claude-accounts"),
            ("antigravity-runner", "agy", "/root/.gemini"),
        ):
            name = f"{scope}-{service}"
            docker("run", "-d", "--name", name, "--network", scope, "--network-alias", service,
                   "--volume", f"{scope}-control:/run/jobnavigator-runner:ro",
                   "--volume", f"{scope}-{volume}:{target}", image(service))
            names.append(name)
        for name in names:
            for attempt in range(30):
                health = docker("inspect", "--format", "{{.State.Health.Status}}", name)
                if health == "healthy":
                    break
                time.sleep(1)
            else:
                raise RuntimeError(f"Runner did not become healthy: {name}")
        script = '''
import asyncio, httpx, importlib.util
from backend.analyzer.runner_client import complete
from backend.cli_runner.protocol import NonRetryableLLMError

async def main():
    for provider, service in [('codex_cli', 'codex-runner'), ('claude_code', 'claude-runner'),
                              ('antigravity_cli', 'antigravity-runner')]:
        async with httpx.AsyncClient(trust_env=False) as client:
            health = await client.get(f'http://{service}:8000/health')
            assert health.json()['provider'] == provider, health.text
            denied = await client.post(f'http://{service}:8000/v1/complete', json={})
            assert denied.status_code == 401, denied.text
        try:
            await complete(provider, 'test', 'test', '', 10)
        except NonRetryableLLMError as error:
            assert 'not logged in' in str(error), str(error)
        else:
            raise AssertionError('Fresh runner unexpectedly has a subscription login')
        print(service + ': healthy, authenticated, missing login handled correctly')

asyncio.run(main())
'''
        print(docker("run", "--rm", "--network", scope, "--volume",
                     f"{scope}-control:/run/jobnavigator-runner", image("backend"), "python", "-c", script))
        print("Runner container smoke checks passed")
    finally:
        for name in names:
            subprocess.run(["docker", "rm", "-f", name], capture_output=True)
        for volume in volumes:
            subprocess.run(["docker", "volume", "rm", volume], capture_output=True)
        subprocess.run(["docker", "network", "rm", scope], capture_output=True)


if __name__ == "__main__":
    main()
