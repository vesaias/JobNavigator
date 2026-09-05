#!/bin/bash
# Run the v2 frontend unit tests (Vitest). Node is not installed on the host, and
# the `frontend` compose service builds to an NGINX image with no /app and no
# node_modules — `docker compose run frontend` lands in that image, so this uses a
# one-off node:20-alpine container with the frontend directory bind-mounted instead.
#
#   bash v2-testing/tools/fe-test.sh              # whole suite
#   bash v2-testing/tools/fe-test.sh time         # only files matching "time"
#   bash v2-testing/tools/fe-test.sh --reporter=verbose
#
# Every argument is passed straight through to `vitest run`.
#
# node_modules lives in the named volume $VOLUME, NOT in the working tree: the
# host frontend/ is bind-mounted at /app and the volume is mounted over
# /app/node_modules, so a cold start installs into the volume and every rerun is
# instant. Docker still creates an EMPTY frontend/node_modules mount point on the
# host; it is git-ignored (.gitignore: frontend/node_modules/). `--no-package-lock`
# keeps npm from writing a package-lock.json the app build would then start
# honouring — this script must not change what `docker compose build frontend`
# produces.
#
# Exits non-zero when a test fails.
#
# Flags: --fresh   wipe the node_modules volume and reinstall from scratch.
set -e

DOCKER="/c/Program Files/Docker/Docker/resources/bin/docker.exe"
export MSYS_NO_PATHCONV=1                       # keep /app from being mangled into a Windows path

VOLUME=jn_fe_node_modules
IMAGE=node:20-alpine

# Repo root from this script's own location, as a path the Docker daemon accepts
# (V:/JTrakProject, not the MSYS /v/JTrakProject).
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd "$HERE/../.." && { pwd -W 2>/dev/null || pwd; })
FRONTEND="$ROOT/frontend"

ARGS=()
for a in "$@"; do
  if [ "$a" = "--fresh" ]; then
    echo "removing volume $VOLUME"
    "$DOCKER" volume rm -f "$VOLUME" >/dev/null || true
  else
    ARGS+=("$a")
  fi
done

echo "frontend: $FRONTEND"
"$DOCKER" run --rm \
  -e TZ=UTC \
  -e CI=1 \
  -v "$FRONTEND:/app" \
  -v "$VOLUME:/app/node_modules" \
  -w /app \
  "$IMAGE" \
  sh -c 'npm install --no-audit --no-fund --no-package-lock --loglevel=error >/dev/null && exec npx vitest run "$@"' _ "${ARGS[@]}"
