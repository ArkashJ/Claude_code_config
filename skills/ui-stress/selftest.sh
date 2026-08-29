#!/usr/bin/env bash
# Regression test for probe.js. Serves a fixture with one planted instance of
# every rule, runs the probe, and fails if any rule stops firing.
#   bash ~/.claude/skills/ui-stress/selftest.sh
set -uo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${PORT:-8979}"
SESSION="uistress-selftest"

python3 -m http.server "$PORT" --directory "$DIR/references" >/dev/null 2>&1 &
SRV=$!
trap 'kill $SRV 2>/dev/null; playwright-cli -s=$SESSION close >/dev/null 2>&1' EXIT
curl -s --retry 30 --retry-connrefused --retry-delay 0 -o /dev/null "http://localhost:$PORT/fixture.html" || {
  echo "FAIL: fixture server never came up"; exit 1; }

playwright-cli -s="$SESSION" open "http://localhost:$PORT/fixture.html" >/dev/null 2>&1
playwright-cli -s="$SESSION" resize 390 800 >/dev/null 2>&1
OUT=$(playwright-cli -s="$SESSION" run-code "$(cat "$DIR/probe.js")" 2>&1 | sed -n '2p')

RESULT="$OUT" python3 - <<'PY'
import json, os, sys
raw = os.environ["RESULT"].strip()
try:
    d = json.loads(json.loads(raw))
except Exception:
    print("FAIL: probe returned no parsable JSON:\n" + raw[:400]); sys.exit(1)
# dead-end needs a blank page and is not exercised here.
expected = {"overflow-x","overflow-x-culprit","text-clipped","covered","touch-target",
            "zero-size-interactive","placeholder-only-label","broken-image",
            "empty-no-message","no-focus-indicator","missing-alt","off-token-color"}
got = {f["rule"] for f in d["findings"]}
missing = expected - got
if d["total"] and not d["findings"]:
    print("FAIL: %d violations detected but findings[] is empty (grouping bug)" % d["total"]); sys.exit(1)
if missing:
    print("FAIL: rules stopped firing: " + ", ".join(sorted(missing))); sys.exit(1)
print("PASS: %d/%d rules fire, %d violations, axe=%s" % (len(expected), len(expected), d["total"], d["axe"]))
PY
