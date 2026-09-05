#!/usr/bin/env bash
# One command for the v2 e2e suite.
#
#   bash v2-testing/e2e/run.sh            # every case
#   bash v2-testing/e2e/run.sh modals     # only cases whose name contains "modals"
#   JN_E2E_LIVE=1 bash v2-testing/e2e/run.sh flows
#
# Copies v2-testing/tools/h.py plus every .py in this folder into /tmp/v2e inside
# the backend container (which already has Playwright + a browser) and runs them
# there against http://caddy. Exits non-zero if any case fails.
#
# Env: JN_KEY (default pick-a-password) · JN_BASE (default http://caddy)
#      JN_E2E_LIVE=1 unlocks the cases that scrape / spend / call out
#      JN_BACKEND overrides the container name · DOCKER overrides the docker path
set -uo pipefail

DOCKER="${DOCKER:-/c/Program Files/Docker/Docker/resources/bin/docker.exe}"
[ -x "$DOCKER" ] || DOCKER="$(command -v docker || true)"
if [ -z "${DOCKER:-}" ]; then echo "run.sh: no docker binary found (set \$DOCKER)" >&2; exit 2; fi
export MSYS_NO_PATHCONV=1

SVC="${JN_BACKEND:-jtrakproject-backend-1}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HARNESS="$HERE/../tools/h.py"
DEST=/tmp/v2e

if ! "$DOCKER" ps --format '{{.Names}}' | grep -qx "$SVC"; then
  echo "run.sh: backend container '$SVC' is not running (set \$JN_BACKEND)" >&2; exit 2
fi
[ -f "$HARNESS" ] || { echo "run.sh: missing harness at $HARNESS" >&2; exit 2; }

"$DOCKER" exec "$SVC" sh -c "rm -rf $DEST && mkdir -p $DEST" || exit 2
# piped through `cat` rather than `docker cp`: no host path ever reaches the
# docker CLI, so Git Bash's MSYS path rewriting cannot mangle it
for f in "$HERE"/*.py "$HARNESS"; do
  "$DOCKER" exec -i "$SVC" sh -c "cat > $DEST/$(basename "$f")" < "$f" || exit 2
done

exec "$DOCKER" exec \
  -e JN_KEY="${JN_KEY:-pick-a-password}" \
  -e JN_BASE="${JN_BASE:-http://caddy}" \
  -e JN_E2E_LIVE="${JN_E2E_LIVE:-0}" \
  -e PYTHONUNBUFFERED=1 \
  "$SVC" python "$DEST/main.py" ${1:+"$1"}
