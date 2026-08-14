#!/bin/sh
# Resolve every concrete token in a handed-in plan against THIS repo (CR-14, item 2 of
# 'if only three things get built'). A pasted plan can belong to another repository —
# 06f4a671's did (commit 602f40b: "Not a valid object name"; 1275 tests vs 120).
# Usage: resolve-plan.sh [planfile]   (or pipe the plan on stdin)
# Exit 1 if anything is STALE.
in=$(cat "${1:-/dev/stdin}")
fail=0
for sha in $(printf '%s' "$in" | grep -oE '\b[0-9a-f]{7,40}\b' | grep -E '[0-9]' | sort -u); do
  if git cat-file -e "$sha" 2>/dev/null; then echo "OK    commit $sha"
  else echo "STALE commit $sha — not in this repo"; fail=1; fi
done
for n in $(printf '%s' "$in" | grep -oE '#[0-9]+' | tr -d '#' | sort -un); do
  if gh issue view "$n" >/dev/null 2>&1 || gh pr view "$n" >/dev/null 2>&1; then echo "OK    #$n"
  else echo "STALE #$n — no such issue/PR here"; fail=1; fi
done
for p in $(printf '%s' "$in" | grep -oE '\b[A-Za-z0-9_][A-Za-z0-9_./-]+\.(ts|tsx|js|mjs|go|py|yaml|yml|md|json|sql|sh)\b' | sort -u); do
  if [ -e "$p" ]; then echo "OK    path $p"
  else echo "STALE path $p — does not exist here"; fail=1; fi
done
exit $fail
