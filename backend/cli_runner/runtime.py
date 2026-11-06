"""CLI adapters executed inside dedicated runners. No DB or application imports."""
import asyncio
import logging
import os
import re
import uuid
from contextvars import ContextVar
from typing import Optional
from .protocol import AGY_TIMEOUT, CLI_TIMEOUT, CLITimeoutError, NonRetryableLLMError

logger = logging.getLogger("jobnavigator.runner")
_execution_account = ContextVar("runner_account", default=None)
_execution_token = ContextVar("runner_claude_token", default="")


def _safe_env():
    allowed = {"PATH", "HOME", "LANG", "LC_ALL", "TZ", "TMPDIR", "SSL_CERT_FILE",
               "SSL_CERT_DIR", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY",
               "http_proxy", "https_proxy", "no_proxy", "AGY_CLI_DISABLE_AUTO_UPDATE"}
    return {key: value for key, value in os.environ.items() if key in allowed}


def _own_login_account():
    return _execution_account.get()


def _claude_code_token():
    return _execution_token.get()


async def _call_claude_code(prompt: str, system: str, model: str, max_tokens: int, effort: str = "") -> dict:
    """Call Claude via claude CLI subprocess. Returns {text, usage}. Caching not supported."""
    import os
    import json as _json
    full_prompt = f"{system}\n\n{prompt}"
    cmd = ["claude", "-p", "--output-format", "json", "--tools", ""]
    if model:
        cmd.extend(["--model", model])
    if effort:
        # A level the model lacks steps down to the highest one it has, so no error comes back.
        cmd.extend(["--effort", effort])

    # Build env: pass CLAUDE_CODE_OAUTH_TOKEN, explicitly EXCLUDE ANTHROPIC_API_KEY
    # so it uses subscription billing, not API credits
    env = _safe_env()
    # The backend resolves Own/Inherit and sends exactly this account's token.
    token = _claude_code_token()
    if token:
        env["CLAUDE_CODE_OAUTH_TOKEN"] = token
    # QA F8 / R5-08: a member on its own models section keeps its transcripts in a HOME and
    # config dir of its own (like CODEX_HOME / agy HOME); owner and 'inherit' unchanged.
    account = _own_login_account()
    if account is not None:
        from .paths import claude_config_dir, claude_home
        config_dir = claude_config_dir(account)
        os.makedirs(config_dir, exist_ok=True)
        env["HOME"] = claude_home(account)
        env["CLAUDE_CONFIG_DIR"] = config_dir

    rc, stdout, stderr = await _run_cli(cmd, full_prompt.encode(), env=env)

    if rc != 0:
        error = stderr.decode(errors="replace").strip()
        raise RuntimeError(f"claude-code subprocess failed (rc={rc}): {error}")

    raw = stdout.decode().strip()
    try:
        data = _json.loads(raw)
        text = data.get("result", raw)
    except _json.JSONDecodeError:
        data, text = None, raw

    # `claude -p --output-format json` reports a refusal, an overload or a hit
    # quota as a rc=0 envelope with is_error set. Returning its text as if it
    # were the answer buried the reason in whatever the caller did next.
    if isinstance(data, dict) and (data.get("is_error") or data.get("subtype") not in (None, "success")):
        reason = (str(text or "").strip() or str(data.get("error") or "").strip()
                  or str(data.get("subtype") or "").strip() or "no reason given")
        if _QUOTA_RE.search(reason):
            raise NonRetryableLLMError(f"Claude Code usage limit reached: {reason[:300]}")
        raise RuntimeError(f"Claude Code reported an error: {reason[:300]}")
    if not str(text or "").strip():
        # Retryable on purpose: an empty completion is a bad minute, not a bad setup.
        raise RuntimeError("Claude Code returned an empty reply")

    return {
        "text": text.strip(),
        "usage": {"input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0, "cache_write_tokens": 0},
    }


# codex exec processes share one auth.json and rewrite it on token refresh; OpenAI's docs say not
# to run many against the same file, so at most two at a time whatever the scoring limiter allows.
# QA F8 / R5-12 (decision, no change): the gates stay process-wide although members on own
# models have homes of their own. Within one account the login is shared, so the limit is
# still needed there, and across accounts it doubles as a CPU cap for the CLI processes; one
# account's backlog delaying another's CLI calls is accepted for a household install.
_codex_gate = asyncio.Semaphore(2)
_CODEX_LOGIN_HINT = "run `docker compose run --rm codex-runner codex login --device-auth`"
_QUOTA_RE = re.compile(r"usage limit|rate limit|quota|too many requests|\b429\b", re.I)
# agy refreshes one shared OAuth token file (per account home), so hold the same limit codex
# gets; process-wide on purpose, see R5-12 above.
_agy_gate = asyncio.Semaphore(2)
_AGY_LOGIN_HINT = "run `docker compose run --rm -it antigravity-runner agy` and sign in"
# 1.3.3+ reports an expired or revoked token as "Authentication expired. Please log back in."
_AGY_AUTH_RE = re.compile(r"authentication (required|failed|expired)|not logged in|sign in|log back in", re.I)
_AGY_STATE = "~/.gemini/antigravity-cli"
# agy is an agent and offers its ~60 tools whatever the deny list says; a -high model spent
# two turns (~45 s) on `ls` and read_file in the empty workdir before it answered. The deny
# list blocks those calls, this line stops the model from making them.
_AGY_NO_TOOLS = ("Answer in this one reply, from the text below only. Do not call any tool: "
                 "there are no files to read and no commands to run.")
# The deny list the image ships. It lives outside the state directory because agy rewrites
# settings.json on every start, and a read-only copy there only makes that write fail.
_AGY_SETTINGS_SOURCE = "/opt/antigravity-settings.json"
# MT-15: the state dir of the agy call in flight when it is not the default (a member with its
# own logins runs agy with HOME=~/.gemini/accounts/<id>). The helpers below read it, so the
# deny list goes into, and the transcript is cleared from, the directory that agy uses.
_agy_state_override: ContextVar[Optional[str]] = ContextVar("jn_agy_state", default=None)


def _agy_state() -> str:
    return _agy_state_override.get() or os.path.expanduser(_AGY_STATE)


async def _run_cli(cmd: list[str], stdin: bytes, env: dict | None = None, timeout: float = CLI_TIMEOUT,
                   cwd: str | None = None):
    """Run a CLI to completion with a hard timeout; returns (rc, stdout, stderr)."""
    process = await asyncio.create_subprocess_exec(
        *cmd, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE, env=env, cwd=cwd,
        start_new_session=(os.name == "posix"),
    )
    reader = asyncio.ensure_future(process.communicate(input=stdin))
    try:
        # shield, so a timeout does not cancel the read: after the kill the same task
        # hands back what the process managed to print, which is how a caller can still
        # clean up after a call that hung.
        stdout, stderr = await asyncio.wait_for(asyncio.shield(reader), timeout)
    except (asyncio.TimeoutError, asyncio.CancelledError) as interrupted:
        # Killing a CLI wrapper alone can leave its child holding stdout/auth files.
        import signal
        try:
            if os.name == "posix" and isinstance(getattr(process, "pid", None), int):
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
        except ProcessLookupError:
            pass
        await process.wait()
        partial = (b"", b"")
        try:
            partial = await asyncio.wait_for(reader, 5) or partial
        except (asyncio.TimeoutError, OSError, ValueError, TypeError):
            pass
        if isinstance(interrupted, asyncio.CancelledError):
            interrupted.stdout = partial[0]
            raise
        raise CLITimeoutError(f"{cmd[0]} timed out after {int(timeout)}s", *partial)
    return process.returncode, stdout, stderr


async def _call_codex_cli(prompt: str, system: str, model: str, max_tokens: int, effort: str = "") -> dict:
    """Call Codex CLI using its existing ChatGPT login; run in an empty read-only workspace."""
    import json as _json
    import os
    import tempfile

    # like ANTHROPIC_API_KEY for claude_code: the plan pays, never an API key that happens to be set
    env = _safe_env()
    login_hint = _CODEX_LOGIN_HINT
    # MT-15: a member with its own models section logs in under its own CODEX_HOME; owner and
    # 'inherit' keep the default home (~/.codex), exactly as before.
    account = _own_login_account()
    if account is not None:
        from .paths import codex_home
        home = codex_home(account)
        os.makedirs(home, exist_ok=True)
        env["CODEX_HOME"] = home
        login_hint = f"run `docker compose run --rm -it -e CODEX_HOME={home} codex-runner codex login --device-auth`"
    async with _codex_gate:
        # `codex exec` without a login retries for ~15 s and then prints a 401 storm; the status
        # check answers in milliseconds and names the fix
        rc, _, _ = await _run_cli(["codex", "login", "status"], b"", env=env, timeout=30)
        if rc != 0:
            raise NonRetryableLLMError(f"Codex CLI is not logged in — {login_hint}")

        full_prompt = f"{system}\n\n{prompt}"
        with tempfile.TemporaryDirectory(prefix="jobnavigator-codex-") as workdir:
            cmd = [
                "codex", "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules",
                "--skip-git-repo-check", "--sandbox", "read-only", "--color", "never",
                "-c", "web_search=disabled", "-c", "history.persistence=none",
                "-c", "check_for_update_on_startup=false",
                "--json", "-C", workdir,
            ]
            if model:
                cmd.extend(["--model", model])
            if effort:
                # -c parses its value as TOML, so the string is quoted.
                cmd.extend(["-c", f'model_reasoning_effort="{effort}"'])
            cmd.append("-")
            rc, stdout, stderr = await _run_cli(cmd, full_prompt.encode(), env=env)

    raw = stdout.decode(errors="replace").strip()
    text = ""
    failed = ""      # turn.failed carries the one readable reason (401, usage limit, model unknown)
    last_error = ""  # transport-level `error` events, the fallback reason when the turn never fails
    usage = {"input_tokens": 0, "output_tokens": 0,
             "cache_read_tokens": 0, "cache_write_tokens": 0}
    for line in raw.splitlines():
        try:
            event = _json.loads(line)
        except _json.JSONDecodeError:
            continue
        kind = event.get("type")
        if kind == "item.completed":
            item = event.get("item") or {}
            if item.get("type") == "agent_message" and item.get("text"):
                text = item["text"]
        elif kind == "turn.completed":
            token_usage = event.get("usage") or {}
            usage.update({
                "input_tokens": token_usage.get("input_tokens", 0) or 0,
                "output_tokens": token_usage.get("output_tokens", 0) or 0,
                "cache_read_tokens": token_usage.get("cached_input_tokens", 0) or 0,
            })
        elif kind == "turn.failed":
            failed = str((event.get("error") or {}).get("message") or "")
        elif kind == "error":
            last_error = str(event.get("message") or "")

    if failed or rc != 0:
        err_lines = stderr.decode(errors="replace").strip().splitlines()
        reason = failed or last_error or (err_lines[-1] if err_lines else "no output")
        if "401" in reason or "Unauthorized" in reason:
            raise NonRetryableLLMError(f"Codex CLI is not logged in — {login_hint} ({reason})")
        if _QUOTA_RE.search(reason):
            raise NonRetryableLLMError(f"Codex usage limit reached: {reason}")
        raise RuntimeError(f"codex exec failed (rc={rc}): {reason}")
    if not text:
        raise RuntimeError("codex exec completed without an agent response")
    return {"text": text.strip(), "usage": usage}


def _agy_events(stdout: bytes):
    """Every NDJSON event agy printed, skipping any line that is not one."""
    import json as _json
    for line in stdout.decode(errors="replace").splitlines():
        try:
            yield _json.loads(line)
        except _json.JSONDecodeError:
            continue


def _agy_conversation_id(stdout: bytes) -> str:
    """The id agy gave this call. The init event carries it before any answer, which is all
    a timed-out call leaves behind."""
    for event in _agy_events(stdout):
        cid = event.get("conversation_id") or (event.get("result") or {}).get("conversation_id")
        if cid:
            return str(cid)
    return ""


def _agy_install_settings() -> list[str]:
    """Put the shipped deny list where agy reads it, and answer with the rules it must honour.
    agy rewrites settings.json as it starts, so the file has to be writable: pinning a
    read-only copy there makes the write fail and drops the CLI onto its defaults."""
    import json as _json
    import os
    import tempfile
    target = os.path.join(_agy_state(), "settings.json")
    try:
        with open(_AGY_SETTINGS_SOURCE, encoding="utf-8") as fh:
            source = fh.read()
    except OSError as e:
        raise NonRetryableLLMError(
            f"Antigravity deny list is missing at {_AGY_SETTINGS_SOURCE} ({e}); "
            "the agent would run unconstrained, so the call is refused")
    os.makedirs(os.path.dirname(target), exist_ok=True)
    try:
        current = open(target, encoding="utf-8").read()
    except OSError:
        current = ""
    if current != source:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=os.path.dirname(target),
                                         prefix=".settings-", delete=False) as fh:
            tmp = fh.name
            fh.write(source)
        try:
            os.replace(tmp, target)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
    return list(_json.loads(source).get("permissions", {}).get("deny", []))


def _agy_assert_denied(log_path: str, rules: list[str]) -> None:
    """Fail the call unless agy's own log says it loaded every deny rule.
    Without this the CLI can silently fall back to defaults and hand the agent
    `run_command` and `write_file` back, and nothing in the answer would show it."""
    try:
        with open(log_path, encoding="utf-8", errors="replace") as fh:
            loaded = [ln for ln in fh if "CLI settings initialized" in ln]
    except OSError:
        loaded = []
    if not loaded:
        raise NonRetryableLLMError(
            "Antigravity CLI never reported its permissions, so the deny list cannot be "
            "confirmed; the call is refused rather than run unconstrained")
    line = loaded[-1]
    missing = [r for r in rules if r not in line]
    if missing:
        raise NonRetryableLLMError(
            f"Antigravity CLI started without the deny rules {missing}; "
            "it would be free to read files and run commands, so the call is refused")


def _agy_discard(conversation_id: str) -> None:
    """Delete the per-call transcript agy writes. It holds the whole prompt — the resume text —
    and nothing reads it back, so it is disk growth and a copy of user data we do not want."""
    import glob
    import os
    import shutil
    if not re.fullmatch(r"[A-Za-z0-9_-]+", conversation_id):
        return
    home = _agy_state()
    for path in (*glob.glob(f"{home}/conversations/{conversation_id}.db*"),
                 f"{home}/presence/{conversation_id}.lock",
                 f"{home}/annotations/{conversation_id}.pbtxt",
                 f"{home}/brain/{conversation_id}"):
        try:
            shutil.rmtree(path) if os.path.isdir(path) else os.remove(path)
        except OSError:
            pass   # a leftover file is untidy, never a reason to fail a scored job


async def _call_antigravity_cli(prompt: str, system: str, model: str, max_tokens: int) -> dict:
    """Call Antigravity CLI on its Google subscription. The prompt rides on stdin as one NDJSON
    line because `-p` reads argv and argv caps near 128 KB. `max_tokens` is ignored: the CLI
    exposes no output cap. Tool use is blocked by a deny list installed before each call and
    confirmed from agy's own log afterwards — `--sandbox` restricts the terminal only, never
    the file tools."""
    # like ANTHROPIC_API_KEY for claude_code: the plan pays, never a key that happens to be set
    env = _safe_env()
    login_hint = _AGY_LOGIN_HINT
    # MT-15: a member with its own models section runs agy with its own HOME, so the login and
    # the state dir (deny list, transcripts) are its own; owner and 'inherit' keep HOME.
    account = _own_login_account()
    state_token = None
    if account is not None:
        from .paths import agy_home, agy_state_dir
        home = agy_home(account)
        os.makedirs(home, exist_ok=True)
        env["HOME"] = home
        state_token = _agy_state_override.set(agy_state_dir(account))
        login_hint = f"run `docker compose run --rm -it -e HOME={home} antigravity-runner agy` and sign in"
    try:
        return await _agy_run(prompt, system, model, env, login_hint)
    finally:
        if state_token is not None:
            _agy_state_override.reset(state_token)


async def _agy_run(prompt: str, system: str, model: str, env: dict, login_hint: str) -> dict:
    """One agy call with `env` (see _call_antigravity_cli); the state dir is `_agy_state()`."""
    import json as _json
    import tempfile

    message = _json.dumps({"event": "user",
                           "message": {"role": "user",
                                       "content": f"{_AGY_NO_TOOLS}\n\n{system}\n\n{prompt}"}})

    denied = _agy_install_settings()
    stdout = b""
    try:
        async with _agy_gate:
            with tempfile.TemporaryDirectory(prefix="jobnavigator-agy-") as workdir:
                # The log goes in the temp directory: it holds the permissions line this
                # call is checked against, and ~16 KB per call has no business surviving.
                log_path = os.path.join(workdir, "cli.log")
                # `-p` always swallows the next token, so it goes last with an attached empty value.
                cmd = ["agy", "--input-format", "stream-json", "--output-format", "stream-json",
                       "--print-timeout", f"{int(AGY_TIMEOUT)}s", "--log-file", log_path]
                if model:
                    cmd.extend(["--model", model])
                cmd.append("-p=")
                rc, stdout, stderr = await _run_cli(cmd, (message + "\n").encode(),
                                                    env=env, timeout=AGY_TIMEOUT, cwd=workdir)
                _agy_assert_denied(log_path, denied)
    except (CLITimeoutError, asyncio.CancelledError) as e:
        stdout = getattr(e, "stdout", b"")
        raise
    finally:
        # A timeout kills agy before the result event, so the id comes from the init event.
        # The transcript has to go exactly in that case too — it holds the whole prompt.
        conversation_id = _agy_conversation_id(stdout)
        if conversation_id:
            _agy_discard(conversation_id)

    result = {}
    for event in _agy_events(stdout):
        if event.get("event") == "result":
            result = event.get("result") or {}

    if result.get("status") != "SUCCESS" or rc != 0:
        err_lines = stderr.decode(errors="replace").strip().splitlines()
        reason = str(result.get("error") or "") or (err_lines[-1] if err_lines else "no output")
        if _AGY_AUTH_RE.search(reason):
            raise NonRetryableLLMError(f"Antigravity CLI is not logged in — {login_hint} ({reason})")
        if _QUOTA_RE.search(reason):
            raise NonRetryableLLMError(f"Antigravity usage limit reached: {reason}")
        raise RuntimeError(f"agy failed (rc={rc}): {reason}")

    text = str(result.get("response") or "").strip()
    if not text:
        raise RuntimeError("agy completed without a response")
    usage = result.get("usage") or {}
    return {
        "text": text,
        "usage": {
            "input_tokens": usage.get("input_tokens", 0) or 0,
            "output_tokens": usage.get("output_tokens", 0) or 0,
            "cache_read_tokens": usage.get("cache_read_tokens", 0) or 0,
            "cache_write_tokens": 0,
        },
    }


async def execute(provider, prompt, system, model, max_tokens, *, account_id=None,
                  claude_token="", effort=""):
    """Execute a resolved login context; inputs can never choose commands or paths."""
    import shutil
    from .paths import account_home, deletion_marker

    account = uuid.UUID(str(account_id)) if account_id is not None else None
    home = account_home(provider, account) if account is not None else None
    if home is not None and deletion_marker(home).exists():
        raise NonRetryableLLMError("This account has been removed")
    account_token = _execution_account.set(account)
    secret_token = _execution_token.set(claude_token)
    try:
        if provider == "claude_code":
            if not claude_token.strip():
                raise NonRetryableLLMError("Claude Code is not logged in: set its token in Settings > Models")
            return await _call_claude_code(prompt, system, model, max_tokens, effort)
        if provider == "codex_cli":
            return await _call_codex_cli(prompt, system, model, max_tokens, effort)
        if provider == "antigravity_cli":
            return await _call_antigravity_cli(prompt, system, model, max_tokens)
        raise NonRetryableLLMError("Unknown runner provider")
    finally:
        _execution_account.reset(account_token)
        _execution_token.reset(secret_token)
        # Deletion may occur while the CLI is completing. Never leave recreated state.
        if home is not None and deletion_marker(home).exists():
            shutil.rmtree(home, ignore_errors=True)
