# Automatic subscription runner management

## Accepted behavior

- Manage Codex, Claude Code and Antigravity only. Ollama/LM Studio remain external HTTP servers.
- A runner is required while any account effectively selects it in Primary,
  Scoring, Scoring fallback, Tailoring, Cover letters, Autofill or Email.
  Resolve Own/Inherit with the existing account settings policy. Model catalog
  entries, credentials and disabled overrides do not create requirements.
- Download a missing image, create its container and wait for readiness in the
  background. Show progress/errors in Models. Never hold a browser request open
  for an image download or replay a completion whose outcome is unknown.
- Remove a runner container when no account selects it. Finish active calls
  first; keep images, auth volumes and tokens. No idle timeout.
- Reconcile after settings/policy/account changes and application/controller
  restarts. Serialize lifecycle operations per provider.

## Architecture

A small private `runner-manager` owns the Docker socket. Its API accepts only
three provider identifiers, never arbitrary images, commands, mounts or paths.
The backend sends the complete required-provider set and proxies subscription
completions through this controller. The controller holds request counts and
checks the runner's active-call endpoint before removing a container, including
after a controller restart. Existing Compose project names, network aliases and
auth volume paths are preserved. Manual Compose profiles remain a fallback when
automatic management is disabled.

Backend polling also captures account changes outside the Models screen; normal
settings/policy writes wake reconciliation immediately. Only the owner sees the
global state; members see their own selected providers, without other accounts'
configuration. Existing provider/model and credential resolution stays in the
backend. Preparing/unavailable services produce readable non-retryable errors so
scoring can use its fallback.

## Implementation steps

- [x] Required-provider resolver and account-policy tests.
- [x] Restricted Docker client, background lifecycle controller, progress,
      restart reconciliation, draining and unit/API tests.
- [x] Backend synchronization, completion forwarding and authorized status/retry endpoints.
- [x] Models UI status/progress/retry and component tests.
- [x] Controller image, Compose wiring, publishing/CI and migration documentation.
- [x] Real Docker smoke test with isolated project/volumes; regression tests,
      lint, frontend build and final verification.

## Validation

Test all slots, disabled overrides, inherited/own accounts and catalog-only
entries. Exercise single-flight startup, simultaneous calls, unselection during
pull/start/execution, restart while a call is active, foreign-container refusal,
failed pulls, stale configuration and recovery. Real Docker tests must use
unique project names and disposable volumes, never real subscription logins or
the user's running stack. Do not automatically delete images or auth volumes.

Completed locally:

- Full backend suite: 5,376 passed, 61 skipped, 11 expected failures.
- Latest lifecycle unit/API suite: 14 passed (including cases added after
  the full-suite snapshot: disabled management, outage grace, Docker pull progress,
  unselection during startup and the optional runner memory cap).
- Full frontend suite: 408 passed; status component rechecked after layout polish.
- Both real Docker smoke scripts passed without subscription credentials. The
  lifecycle test confirmed two active calls survived a forced controller restart,
  removal preserved auth/image data, cached recreation worked, and Compose
  exec/down recognized the managed container.
- Backend, frontend, manager and all three runner images built locally.
- Ruff, style lint, actionlint, Compose validation and git whitespace checks passed.

Deployment guidance: docs/CLI-RUNNERS.md. Release publication and changes to an
existing installation's running stack are separate from these isolated checks.
