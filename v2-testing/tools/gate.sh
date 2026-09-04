#!/bin/bash
# Pixel + style gate with the scheduler paused, so a diff is a code diff.
# Usage: bash v2-testing/tools/gate.sh <stage> [<base-stage>] [--theme X]
# Pauses scrape/email intervals, waits for active runs, builds nothing (build first),
# captures shots + crawl, diffs against <base-stage> when given, restores the intervals.
set -e
DOCKER="/c/Program Files/Docker/Docker/resources/bin/docker.exe"; export MSYS_NO_PATHCONV=1
KEY=pick-a-password; API=http://localhost/api
STAGE=$1; BASE=$2; THEME=""
[ "$BASE" = "--theme" ] && { THEME="--theme $3"; BASE=""; }
[ "$3" = "--theme" ] && THEME="--theme $4"
for f in h.py shots.py stylecrawl.py shotdiff.py stylediff.py; do "$DOCKER" compose cp v2-testing/tools/$f backend:/tmp/v2t/$f >/dev/null; done
SAVED=$(curl -s -H "X-API-Key: $KEY" $API/settings | py -c "import json,sys; d=json.load(sys.stdin); d=d.get('settings',d); print(json.dumps({k:d[k] for k in ('scrape_interval_minutes','email_check_interval_minutes') if k in d}))")
echo "saved intervals: $SAVED"
curl -s -X PATCH -H "X-API-Key: $KEY" -H "Content-Type: application/json" $API/settings -d '{"scrape_interval_minutes":0,"email_check_interval_minutes":0}' >/dev/null
for i in $(seq 1 60); do
  n=$(curl -s -H "X-API-Key: $KEY" $API/monitor/active | py -c "import json,sys; d=json.load(sys.stdin); print(len(d if isinstance(d,list) else d.get('active',d.get('items',[]))))")
  [ "$n" = "0" ] && break; sleep 5
done
echo "active runs: $n"
"$DOCKER" compose exec -T backend python /tmp/v2t/shots.py $STAGE $THEME 2>&1 | tail -1
"$DOCKER" compose exec -T backend python /tmp/v2t/stylecrawl.py $STAGE $THEME 2>&1 | tail -1
curl -s -X PATCH -H "X-API-Key: $KEY" -H "Content-Type: application/json" $API/settings -d "$SAVED" >/dev/null
echo "intervals restored"
mkdir -p v2-testing/artifacts/design
"$DOCKER" compose cp backend:/tmp/v2t/shots/$STAGE v2-testing/artifacts/design/$STAGE >/dev/null 2>&1 || true
if [ -n "$BASE" ]; then
  "$DOCKER" compose exec -T backend python /tmp/v2t/shotdiff.py $BASE $STAGE 2>&1 | grep -v Deprecation | grep -v getdata | sort -rn | head -40
  "$DOCKER" compose exec -T backend python /tmp/v2t/stylediff.py $BASE $STAGE 2>&1 | tail -1
  "$DOCKER" compose cp backend:/tmp/v2t/shots/diff_${BASE}_${STAGE} v2-testing/artifacts/design/diff_${BASE}_${STAGE} >/dev/null 2>&1 || true
  "$DOCKER" compose cp backend:/tmp/v2t/shots/stylediff_${BASE}_${STAGE}.md v2-testing/artifacts/design/stylediff_${BASE}_${STAGE}.md >/dev/null 2>&1 || true
fi
