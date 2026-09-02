#!/bin/sh
# Positive and negative cases for block-open-ended-stop.sh. Asserts exit code AND message.
set -eu
hook=${1:-$HOME/.claude/commands/hooks/block-open-ended-stop.sh}
tmp=$(mktemp -d)
git -C "$tmp" init -q
: > "$tmp/clean"
git -C "$tmp" add clean
git -C "$tmp" -c user.email=t@t -c user.name=t commit -qm init

check() { # expected-exit message-fragment last_assistant_message [stop_hook_active] [dirty]
  exp=$1; frag=$2; text=$3; active=${4:-false}; dirty=${5:-no}
  if [ "$dirty" = yes ]; then echo x >> "$tmp/clean"; else git -C "$tmp" checkout -q -- clean; fi
  set +e
  out=$(/usr/bin/jq -nc --arg m "$text" --argjson a "$active" '{last_assistant_message:$m, stop_hook_active:$a}' \
        | CLAUDE_PROJECT_DIR="$tmp" "$hook" 2>&1); got=$?
  set -e
  [ "$got" -eq "$exp" ] || { echo "FAIL exit $got != $exp: $text" >&2; exit 1; }
  [ -z "$frag" ] || printf '%s' "$out" | /usr/bin/grep -Fq "$frag" || { echo "FAIL missing '$frag': $text" >&2; exit 1; }
}
# blocks: deferral with no accepted reason
check 2 "defers work" "Landed the parser. Next steps: wire the CLI and add tests."
check 2 "defers work" "Done. Remaining work can go in a follow-up PR."
# allows: deferral carrying an accepted reason
check 0 "" "Next steps: merge PR 4 — human decision, one approved command away: gh pr merge 4 --squash. Recommend yes."
check 0 "" "Not done: deploy — blocked: benmore deploy exits 3, log attached. Not attempted: docs sync."
# allows: nothing deferred
check 0 "" "Fixed the null check in parse(); 28 tests pass."
# blocks: done-claim on a dirty tree
check 2 "uncommitted" "All done and shipped." false yes
# allows: dirty tree but no done-claim (mid-conversation answer)
check 0 "" "The bug is in parse(): it drops the last record." false yes
# never loops: second invocation always allows
check 0 "" "Next steps: everything, later." true
rm -rf "$tmp"
echo "OK: block-open-ended-stop 8/8"
