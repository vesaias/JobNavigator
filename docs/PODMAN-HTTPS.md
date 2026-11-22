# Secure deployment: Podman rootless + HTTPS-first

## Summary

JobNavigator ships as a Docker Compose stack that publishes Caddy on HTTP (:80/:443)
and stores the dashboard API key in a cookie with `Secure=False`. The default works
for a local Docker install, but it does not cover two common self-hosted setups:

1. **Podman rootless**, where the Docker socket is unavailable/undesirable and the
   runner manager's privileged socket is a blocker.
2. **HTTPS-first operation**, so a deployment can be tested and used over TLS by
   default, avoiding mixed `http://` / `https://` origins, CORS, extension and
   cookie surprises between development and production.

This issue proposes first-class support for both, without breaking the existing
Docker/HTTP workflow.

## Motivation

- The Docker socket is effectively root on the host. Rootless Podman removes that
  privilege from the core app; the runner manager should be optional.
- Running HTTP in development and HTTPS in production changes the browser origin,
  CORS allow-list, extension server URL and cookie `Secure` flag. Those differences
  should be explicit, configurable and tested, not discovered in production.
- Users copy `http://localhost` from the docs into the extension and OAuth callback
  settings; after enabling HTTPS those values silently break.
- A local CA (`tls internal` / Caddy) gives HTTPS parity without a public domain.

## Scope

### A. Podman rootless

- Add a supported Podman path: documentation + reference Compose file/override.
- Do not require `/var/run/docker.sock` for the core stack (dashboard, DB,
  scrapers). Subscription CLI runners may remain Docker-only or get a documented
  socketless/opt-in mode.
- Account for Podman/Compose differences:
  - `podman-compose` version vs `network: alias=` syntax;
  - healthcheck/`depends_on: condition: service_healthy` support;
  - `logging: json-file` (Docker-specific) vs Podman's default;
  - rootless CNI/network configuration and published ports on `127.0.0.1`;
  - no privileged/host-network/socket mounts.
- Add a CI smoke job (or documented manual test) for `podman-compose config` and a
  minimal `up`/`down` cycle.

### B. HTTPS-first

- Make the public site address configurable, e.g. `JN_SITE_ADDRESS`:
  - default local: `https://localhost:8443` (Caddy `tls internal`);
  - production: a real hostname with automatic ACME or a mounted certificate;
  - explicit opt-out for `http://localhost:8080` during development.
- Redirect HTTP to HTTPS when TLS is enabled; never serve the dashboard on both
  schemes by accident.
- Make origins derive from the configured address:
  - `ALLOWED_ORIGINS` includes the selected scheme/host/port;
  - extension docs/examples use the same base URL;
  - OAuth redirect examples use `<dashboard>/api/gmail/callback`;
  - health checks accept a CA file for local TLS.
- Session cookie: set `Secure=True` when the request is HTTPS (or when a
  `JN_COOKIE_SECURE=1` / `X-Forwarded-Proto=https` is trusted from Caddy).
- Document how to trust the local CA (Caddy root) or use a real certificate.
- Avoid HSTS by default for local/self-signed setups; make it opt-in for real
  domains.

## Non-goals

- Do not change the default for existing Docker users without an explicit opt-in.
- Do not expose the dashboard to the internet by default.
- Do not make the runner manager rootless in this issue; that is a separate design
  (the runner manager needs a container engine socket to start CLI containers).
- Do not add a hosted service or a public CA dependency.

## Proposed design

### Compose / Caddy

- Keep `docker-compose.yml` for Docker + HTTP development.
- Add `compose.podman.yaml` (or a documented override) for rootless Podman.
- Add a Caddy site block driven by `JN_SITE_ADDRESS`; `tls internal` for localhost,
  ACME for a real domain, or a mounted cert.
- Publish only loopback ports (`127.0.0.1:8443:8443`) by default; production users
  put a reverse proxy/VPN in front.
- Make the backend health check independent of the database (already true) and
  provide an HTTPS-aware compose healthcheck.

### Configuration

```ini
# Local HTTPS (default for the new profile)
JN_SITE_ADDRESS=https://localhost:8443
JN_COOKIE_SECURE=1
ALLOWED_ORIGINS=https://localhost:8443
```

```ini
# Legacy/development HTTP
JN_SITE_ADDRESS=http://localhost:8080
JN_COOKIE_SECURE=0
ALLOWED_ORIGINS=http://localhost:8080
```

- The backend reads `JN_COOKIE_SECURE` (or derives it from a trusted
  `X-Forwarded-Proto`) for `set_session`.
- Caddy sets `X-Forwarded-Proto` and only accepts it from its own network.
- Frontend uses relative API URLs, so the origin follows the page scheme.

### Podman specifics

- Document `podman-compose` version requirements and known incompatibilities
  (e.g. network alias syntax, CNI version, pod mode).
- Do not mount the Docker/Podman socket in the core services.
- Explicitly document that `JN_RUNNER_MANAGEMENT=1` requires an engine socket and
  is therefore not available in the rootless profile.
- Provide a `podman unshare`/volume ownership note if bind mounts are used.

## Acceptance criteria

- [ ] A user can run the stack rootless with Podman without a Docker socket,
      without `privileged`, `network_mode: host` or home mounts.
- [ ] `podman-compose -f compose.podman.yaml config` passes in CI.
- [ ] A smoke test starts the stack, checks `/health`, and stops it without
      deleting volumes.
- [ ] HTTPS profile serves the dashboard on `https://localhost:8443`, redirects
      HTTP (if enabled) and sets a `Secure` session cookie.
- [ ] `ALLOWED_ORIGINS`, extension docs and Gmail callback examples use the
      configured scheme/host.
- [ ] Existing Docker + HTTP workflow still works unchanged.
- [ ] Documentation covers CA trust, certificate rotation, and the HTTP/HTTPS
      origin switch.
- [ ] Tests cover both schemes: CORS, cookie flags, redirect, and `/health` over
      TLS.

## Test plan

- Matrix: Docker/HTTP (legacy), Docker/HTTPS, Podman/HTTP, Podman/HTTPS.
- Automated: `podman-compose config`, `docker compose config`, backend tests for
  cookie/origin derivation, a smoke script that boots the stack and calls
  `https://localhost:8443/health` with the local CA.
- Manual: extension configured with the HTTPS URL; Gmail OAuth redirect; browser
  mixed-content check; HTTP→HTTPS redirect.
- Negative: access via LAN IP must fail; DB must have no host port; no socket mount.

## Security considerations

- Rootless Podman reduces host impact but does not make the app untrusted-safe.
- The runner manager's socket remains the highest-risk component; keep it optional
  and clearly documented.
- A local CA private key lives in the Caddy data volume; protect it and document
  rotation.
- `Secure` cookies plus HTTPS-only origins prevent accidental credential leakage
  over plaintext HTTP.
- Do not enable HSTS on localhost/self-signed setups; make it opt-in for real
  domains.

## Related code

- `Caddyfile` (`:80`), `docker-compose.yml` (`ports: 80:80`, `443:443`)
- `backend/main.py` (`set_session`, `secure=False`)
- `docs/GETTING-STARTED.md`, `README.md`, extension docs (`http://localhost`)
- `runner-manager` service (Docker socket) and `JN_RUNNER_MANAGEMENT`

## Open questions

1. Should the Podman profile be a separate Compose file, or a set of overrides?
2. Is `JN_SITE_ADDRESS` enough, or do we need separate `JN_PUBLIC_URL` and
   `JN_LISTEN_ADDRESS`?
3. Should HTTPS become the default for new installs, or remain opt-in with a
   prominent “secure setup” path?
4. Do we want Caddy ACME in the default file, or only `tls internal` + an external
   reverse proxy for production?
