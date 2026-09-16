#!/bin/sh
# Catch "closed by #N" / "fixes #N" / "#N ... are now closed" claims that were never
# checked against live GitHub state (CR-2026-09-10, portal mission run). A session
# claimed "Issues #147 and #148 are now closed by #154" in three posted comments and a
# doc, based on believing an unmerged draft PR fixed them -- #154 was still a draft,
# closes nothing, and #147/#148 were still open. An independent audit caught it after
# the fact; this script catches it before you post.
#
# First version of this script only matched GitHub's own auto-close direction
# ("fixes #N", verb-before-number) and missed the actual incident text, where the
# numbers come BEFORE the verb ("#147 and #148 ... are now closed by #154") -- caught
# by testing the script against the real sentence that caused the incident, not a
# synthetic one. Both directions are matched below. Second pass over its own control
# case ("Issue #108 was closed") found the number-first pattern only recognized
# is/are/has been/have been and missed "was"/"were" -- fixed after that test failed,
# not assumed correct because the first two tests passed.
#
# Usage: verify-github-claims.sh [textfile]   (or pipe text on stdin)
# Run from inside the target repo (gh resolves the repo from cwd, same as resolve-plan.sh).
# Exit 1 if any "closed/fixed/resolved" claim names a #N that is actually still open.
in=$(cat "${1:-/dev/stdin}")
fail=0

# Direction 1 (GitHub auto-close syntax): "fixes #123", "closed #123", "resolves #123"
verb_first=$(printf '%s' "$in" | grep -oiE '(closed?|clos(e|ing)|fix(e[sd])?|resolv(e[sd]|ing))[^.]{0,40}#[0-9]+' \
  | grep -oE '#[0-9]+' | tr -d '#')

# Direction 2 (natural language): "#123 ... is/are/was/were/has been ... closed/fixed/resolved"
num_first=$(printf '%s' "$in" | grep -oiE '#[0-9]+([^.]{0,80})?(is|are|was|were|has been|have been)[^.]{0,30}(closed|fixed|resolved)' \
  | grep -oE '#[0-9]+' | tr -d '#')

nums=$(printf '%s\n%s\n' "$verb_first" "$num_first" | grep -E '^[0-9]+$' | sort -un)

if [ -z "$nums" ]; then
  echo "No closed/fixed/resolved #N claims found."
  exit 0
fi
for n in $nums; do
  state=$(gh issue view "$n" --json state -q '.state' 2>/dev/null) \
    || state=$(gh pr view "$n" --json state -q '.state' 2>/dev/null)
  if [ -z "$state" ]; then
    echo "UNKNOWN #$n — could not resolve as issue or PR in this repo"
    fail=1
  elif [ "$state" = "OPEN" ]; then
    echo "STALE  #$n — claimed closed/fixed/resolved but is still OPEN"
    fail=1
  else
    echo "OK     #$n — $state, consistent with a closed/fixed/resolved claim"
  fi
done
exit $fail
