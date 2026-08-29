#!/usr/bin/env bash
# Proves the probes actually fire. Serves references/fixture.html, which carries
# one planted instance of each detectable class, and asserts every one is found.
#
#   bash ~/.claude/skills/frontend-verify/selftest.sh
#
# A probe nobody has watched fail is not a gate. Run this after any edit to
# probe.js -- a rule that silently stops matching is worse than no rule, because
# it keeps occupying the verification slot while measuring nothing.
set -uo pipefail

SKILL="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${PORT:-8749}"
TMP="$(mktemp -d)"
trap 'kill "${SRV:-0}" 2>/dev/null; rm -rf "$TMP"' EXIT

cp "$SKILL/references/fixture.html" "$TMP/index.html"
python3 -m http.server "$PORT" --directory "$TMP" >/dev/null 2>&1 &
SRV=$!

# Wait for the port instead of sleeping blind.
for _ in $(seq 1 40); do
  curl -fsS "http://127.0.0.1:$PORT/" >/dev/null 2>&1 && break
  perl -e 'select undef,undef,undef,0.25'
done

# PLAYWRIGHT_HOME lets the selftest borrow an install from any repo, since the
# skill itself carries no node_modules by design.
node "$SKILL/bin/sweep.mjs" --repo "${PLAYWRIGHT_HOME:-$PWD}" --base "http://127.0.0.1:$PORT" \
  --routes / --json "$TMP/report.json" >"$TMP/out.txt" 2>&1
echo "--- sweep output"; cat "$TMP/out.txt"

if grep -q "Playwright not found" "$TMP/out.txt"; then
  echo
  echo "SELFTEST SKIPPED -- Playwright is not installed anywhere this script can reach."
  echo "The static half (inventory.mjs, classify.mjs) needs nothing and is covered by"
  echo "selftest-static.sh. To cover the runtime half, install it in any repo and rerun"
  echo "from there:"
  echo "    npm i -D @playwright/test && npx playwright install chromium"
  exit 2
fi
if [ ! -s "$TMP/report.json" ]; then
  echo "FAIL: sweep produced no report -- see the output above"; exit 1
fi

fail=0
have() {
  if grep -q "\"kind\": \"$1\"" "$TMP/report.json"; then
    echo "  ok    $1"
  else
    echo "  MISS  $1  <- planted in the fixture, probe did not fire"; fail=1
  fi
}
have_exact() {
  if grep -q "$1" "$TMP/report.json"; then echo "  ok    exact: $1"
  else echo "  MISS  expected exactly: $1"; fail=1; fi
}
absent() {
  if grep -q "$1" "$TMP/report.json"; then
    echo "  FALSE-POSITIVE  $1"; fail=1
  else
    echo "  ok    no false positive: $1"
  fi
}

echo "--- planted defects"
have value.leak
have render.stuck-loading
have render.empty-list-no-state
have layout.h-scroll
have a11y.tap-target
have a11y.unlabeled-control

echo "--- must NOT fire"
# The sr-only skip link is 1x1 BY DESIGN. Counting it is how an accessibility
# ticket claims 103 failures and a browser finds one.
# Exactly ONE small target (.tiny). If the sr-only skip link were counted it
# would be 2 -- which is how an accessibility ticket claims 103 failures.
have_exact '1 interactive element(s) under 24px'
absent '2 interactive element(s) under 24px'

# value.leak must report all four leaked shapes, not just the first.
for s in NaN undefined "object Object" "Invalid Date"; do
  grep -q "$s" "$TMP/report.json" && echo "  ok    leak reported: $s" || { echo "  MISS  leak not reported: $s"; fail=1; }
done

echo
if [ "$fail" -eq 0 ]; then echo "SELFTEST PASS"; else echo "SELFTEST FAIL"; fi
exit "$fail"
