#!/usr/bin/env bash
# One command. Inventory -> classify -> sweep, in that order, cheapest first.
#
#   verify.sh <repoRoot> [--base URL] [--auth state.json] [--width N] [--quiet]
#
#   verify.sh /path/to/repo                          static only, seconds, no install
#   verify.sh /path/to/repo --base http://localhost:3000   + the runtime sweep
#
# Exit: 0 clean · 1 P0/P1 findings · 2 could not run.
# That exit code is the definition of done -- it is what a Stop hook, a
# pre-commit hook or CI reads. Everything else here is reporting.
set -uo pipefail

SKILL="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO=""; BASE=""; AUTH=""; WIDTH=""; QUIET=0
while [ $# -gt 0 ]; do
  case "$1" in
    --base)  BASE="${2:-}"; shift 2 ;;
    --auth)  AUTH="${2:-}"; shift 2 ;;
    --width) WIDTH="${2:-}"; shift 2 ;;
    --quiet) QUIET=1; shift ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) [ -z "$REPO" ] && REPO="$1" || true; shift ;;
  esac
done

[ -z "$REPO" ] && REPO="$PWD"
REPO="$(cd "$REPO" 2>/dev/null && pwd)" || { echo "verify: no such directory" >&2; exit 2; }
command -v node >/dev/null || { echo "verify: node not found" >&2; exit 2; }

OUT="$REPO/.verify"
mkdir -p "$OUT"
say() { [ "$QUIET" -eq 1 ] || printf '%s\n' "$*"; }
rc=0

say ""
say "  frontend-verify  $REPO"

# --- 1. inventory (always; also the route list the sweep uses) --------------
if ! node "$SKILL/bin/inventory.mjs" "$REPO" >"$OUT/inventory.log" 2>&1; then
  cat "$OUT/inventory.log" >&2; echo "verify: inventory failed" >&2; exit 2
fi
[ "$QUIET" -eq 1 ] || sed -n '2,5p' "$OUT/inventory.log"

# A sync risk that names the routes it breaks is a real defect, and the only one
# of the three phases that does not already exit non-zero on its own.
if [ "$QUIET" -eq 1 ]; then
  node -e 'try { process.exit(require(process.argv[1]).syncRisks.some((r) => r.severity === "P1") ? 1 : 0) } catch { process.exit(0) }' "$OUT/inventory.json" || rc=1
else
  node -e '
    let p1 = [];
    try { p1 = require(process.argv[1]).syncRisks.filter((r) => r.severity === "P1") } catch { process.exit(0) }
    if (!p1.length) process.exit(0);
    console.log("");
    console.log("  " + p1.length + " P1 sync risk(s) -- a write with no invalidation, on routes that render it:");
    for (const r of p1.slice(0, 12)) console.log("    " + r.detail);
    if (p1.length > 12) console.log("    ... and " + (p1.length - 12) + " more in .verify/inventory.json");
    process.exit(1);
  ' "$OUT/inventory.json" || rc=1
fi

# --- 2. classify (always) ---------------------------------------------------
node "$SKILL/bin/classify.mjs" "$REPO" >"$OUT/classify.log" 2>&1
cls=$?
[ "$QUIET" -eq 1 ] || sed -n '2,40p' "$OUT/classify.log"
[ "$cls" -ne 0 ] && rc=1

# --- 3. sweep (only with --base; needs the app running) ---------------------
if [ -n "$BASE" ]; then
  args=( --repo "$REPO" --base "$BASE" )
  [ -n "$AUTH" ]  && args+=( --auth "$AUTH" )
  [ -n "$WIDTH" ] && args+=( --width "$WIDTH" )
  node "$SKILL/bin/sweep.mjs" "${args[@]}" >"$OUT/sweep.log" 2>&1
  sw=$?
  [ "$QUIET" -eq 1 ] || sed -n '2,40p' "$OUT/sweep.log"
  # 2 means the sweep could not run at all. Never let that read as clean.
  [ "$sw" -eq 2 ] && { echo "verify: sweep could not run -- see $OUT/sweep.log" >&2; exit 2; }
  [ "$sw" -ne 0 ] && rc=1
else
  say ""
  say "  runtime sweep skipped (no --base). Static analysis cannot see whether the"
  say "  code runs -- pass --base http://localhost:3000 with the app up to cover that."
fi

# PASS must mean "measured, and clean" -- never "measured nothing". A repo with no
# routes is one the tool did not understand, and reporting it green is the exact
# failure this whole skill exists to prevent.
ROUTES=$(node -e 'try { console.log(require(process.argv[1]).counts.routes) } catch { console.log(0) }' "$OUT/inventory.json")
if [ "${ROUTES:-0}" -eq 0 ]; then
  echo "" >&2
  echo "  INCONCLUSIVE  0 routes found in $REPO" >&2
  echo "  Nothing was measured, so this is not a pass. Either this is not a frontend" >&2
  echo "  repo, or its router is not one inventory.mjs recognises (Next app/pages," >&2
  echo "  react-router config, or a src/routes file convention)." >&2
  exit 2
fi

say ""
if [ "$rc" -eq 0 ]; then say "  PASS  $ROUTES routes analysed, no P0/P1 findings"
else say "  FAIL  P0/P1 findings above  ·  reports in $OUT/"; fi
exit "$rc"
