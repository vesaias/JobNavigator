"""Real Docker lifecycle checks in an isolated project; never use subscription credentials.

Requires jobnavigator-{runner-manager,codex-runner}:local. A fake Codex executable
is installed ONLY in the disposable container's writable layer, never the image.
Checks real execution draining after a controller restart and retains auth data.
"""
import json
import subprocess
import time
import uuid


def main():
    project = "jn-manager-test-" + uuid.uuid4().hex[:12]
    manager = project + "-manager"
    runner = project + "-codex-runner-1"
    network = project + "_llm"
    volumes = [project + "_" + name for name in ("runner_control", "codex_auth", "claude_accounts", "antigravity_auth")]
    pending = None

    def docker(*args):
        r = subprocess.run(["docker", *args], capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError(f"Docker {args[0]} failed: {r.stderr}\n{r.stdout}")
        return r.stdout.strip()

    def probe(code):
        return docker("exec", manager, "python", "-c", code)

    def desired(providers, expected):
        return json.loads(probe('''
import httpx, time, json
from backend.cli_runner.auth import read_token
with httpx.Client(trust_env=False, timeout=10, headers={"Authorization":"Bearer " + read_token()}) as c:
    for attempt in range(90):
        r = c.put("http://localhost:8000/v1/desired", json={"providers":''' + repr(providers) + '''})
        r.raise_for_status()
        row = next(x for x in r.json()["providers"] if x["provider"] == "codex_cli")
        if row["state"] == ''' + repr(expected) + ''':
            print(json.dumps(row)); break
        if row["state"] == "error": raise AssertionError(row)
        time.sleep(.5)
    else: raise AssertionError(row)
'''))

    try:
        docker("network", "create", network)
        for volume in volumes:
            docker("volume", "create", volume)
        docker("run", "--rm", "-v", f"{volumes[0]}:/run/jobnavigator-runner",
               "jobnavigator-runner-manager:local", "python", "-c",
               "from backend.cli_runner.auth import ensure_token; ensure_token()")
        docker("run", "--rm", "-v", f"{volumes[1]}:/auth", "jobnavigator-runner-manager:local", "python", "-c",
               "from pathlib import Path; Path('/auth/sentinel').write_text('keep-login')")
        docker("run", "-d", "--name", manager, "--network", network,
               "-e", f"JN_COMPOSE_PROJECT={project}", "-e", "JN_IMAGE_TAG=local",
               "-e", "JN_RUNNER_IMAGE_PREFIX=jobnavigator",
               "-v", "/var/run/docker.sock:/var/run/docker.sock",
               "-v", f"{volumes[0]}:/run/jobnavigator-runner:ro", "jobnavigator-runner-manager:local")
        for attempt in range(30):
            if docker("inspect", "--format", "{{.State.Health.Status}}", manager) == "healthy":
                break
            time.sleep(1)
        else:
            raise AssertionError("Controller did not become healthy")
        assert desired(["codex_cli"], "ready")["required"]
        listed = json.loads(docker("inspect", runner))[0]
        assert listed["Config"]["Image"] == "jobnavigator-codex-runner:local"
        assert listed["HostConfig"]["Init"] is True
        containers = docker("ps", "-a", "--filter", f"label=com.docker.compose.project={project}", "--format", "{{.Names}}")
        assert containers == runner, containers
        probe('''
import httpx
from backend.cli_runner.auth import read_token
url="http://localhost:8000"
assert httpx.put(url+"/v1/desired", json={"providers":[]}).status_code == 401
r=httpx.post(url+"/v1/complete", headers={"Authorization":"Bearer "+read_token()}, timeout=40,
             json={"protocol":1,"provider":"codex_cli","prompt":"test","system":"","model":"","max_tokens":10})
assert r.status_code == 422 and "not logged in" in r.text, r.text
''')
        fake = '''#!/usr/local/bin/python
import json, sys, time
from pathlib import Path
if sys.argv[1:3] == ['login', 'status']: sys.exit(0)
sys.stdin.read()
while not Path('/tmp/release-request').exists(): time.sleep(.1)
print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':'smoke-ok'}}))
'''
        docker("exec", runner, "python", "-c",
               "from pathlib import Path; p=Path('/usr/bin/codex'); p.unlink(); p.write_text(" + repr(fake) + "); p.chmod(0o755)")
        script = '''
import asyncio, httpx
from backend.cli_runner.auth import read_token
async def main():
    async with httpx.AsyncClient(trust_env=False, timeout=60) as c:
        async def call():
            try:
                await c.post('http://localhost:8000/v1/complete', headers={'Authorization':'Bearer '+read_token()},
                    json={'protocol':1,'provider':'codex_cli','prompt':'test','system':'','model':'','max_tokens':10})
            except httpx.HTTPError: pass  # controller restart: never replay
        await asyncio.gather(call(), call())
asyncio.run(main())
'''
        pending = subprocess.Popen(["docker", "exec", manager, "python", "-c", script],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        probe('''
import httpx,time
from backend.cli_runner.auth import read_token
with httpx.Client(trust_env=False, headers={'Authorization':'Bearer '+read_token()}) as c:
    for attempt in range(100):
        r=c.get('http://codex-runner:8000/v1/status'); r.raise_for_status()
        if r.json()['active_requests']==2: break
        time.sleep(.1)
    else: raise AssertionError(r.text)
''')
        docker("restart", "-t", "1", manager)
        # Wait for HTTP startup after forceful controller restart.
        for attempt in range(30):
            if docker("inspect", "--format", "{{.State.Health.Status}}", manager) == "healthy":
                break
            time.sleep(1)
        assert desired([], "draining")["required"] is False
        assert docker("inspect", "--format", "{{.State.Status}}", runner) == "running"
        docker("exec", runner, "python", "-c", "from pathlib import Path; Path('/tmp/release-request').touch()")
        desired([], "absent")
        absent = subprocess.run(["docker", "inspect", runner], capture_output=True)
        assert absent.returncode != 0
        docker("image", "inspect", "jobnavigator-codex-runner:local")
        for volume in volumes:
            docker("volume", "inspect", volume)
        assert docker("run", "--rm", "-v", f"{volumes[1]}:/auth:ro", "jobnavigator-runner-manager:local",
                      "python", "-c", "from pathlib import Path; print(Path('/auth/sentinel').read_text())") == "keep-login"
        desired(["codex_cli"], "ready")  # recreate from cached image, original login volume
        compose = "services:\n  codex-runner:\n    image: jobnavigator-codex-runner:local\n    profiles: [llm]\n"
        def compose_command(*args):
            r = subprocess.run(["docker", "compose", "-p", project, "--profile", "llm", "-f", "-", *args],
                               input=compose, capture_output=True, text=True)
            assert r.returncode == 0, r.stderr
            return r.stdout.strip()
        assert compose_command("exec", "-T", "codex-runner", "python", "-c", "print('reachable')") == "reachable"
        docker("stop", "-t", "1", manager)
        compose_command("down")  # Compose recognizes manager-created service labels
        assert subprocess.run(["docker", "inspect", runner], capture_output=True).returncode != 0
        print("Manager smoke passed: single selected runner, authenticated API, two active calls survive controller restart, container removed, image/auth retained, cached recreation, Compose exec/down")
    finally:
        if pending:
            try:
                pending.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                pending.kill()
                pending.communicate()
        # Fixed names derive solely from the random test project above.
        for name in (manager, runner):
            subprocess.run(["docker", "rm", "-f", name], capture_output=True)
        for volume in volumes:
            subprocess.run(["docker", "volume", "rm", volume], capture_output=True)
        subprocess.run(["docker", "network", "rm", network], capture_output=True)


if __name__ == "__main__":
    main()
