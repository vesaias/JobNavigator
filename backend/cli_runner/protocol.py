"""Shared wire contract. Keep this module free of application dependencies."""

PROTOCOL_VERSION = 1
CLI_TIMEOUT = 300
AGY_TIMEOUT = 450
SERVICES = {
    "codex_cli": "codex-runner",
    "claude_code": "claude-runner",
    "antigravity_cli": "antigravity-runner",
}


class NonRetryableLLMError(RuntimeError):
    """A failure a retry cannot fix; the backend can use its fallback."""


class CLITimeoutError(NonRetryableLLMError):
    """A CLI exceeded its deadline; partial output is used for local cleanup only."""

    def __init__(self, message: str, stdout: bytes = b"", stderr: bytes = b""):
        super().__init__(message)
        self.stdout = stdout
        self.stderr = stderr
