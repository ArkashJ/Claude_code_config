#!/usr/bin/env bash
# Proof that repo-hygiene.sh cannot recommend destroying load-bearing work.
#
# Exists because on 2026-08-18 the script recommended `git branch -D` on
# feat/pcs-admin-organization-operations while PR #999 was OPEN and CI-green —
# and printed "keeping 1 branch(es) owned by open PRs" in the SAME output. The
# protective claim was decorative: the branch loop consulted the merged list and
# never the open one, and the summary printed a global open-PR count rather than
# an exclusion it had performed.
#
# Fixing that surfaced a second, worse instance: `dev` is itself a merged
# headRefName (a dev->staging PR), so the script recommended deleting the default
# branch from any feature branch. It had been masked only by the "current branch"
# skip, i.e. it never fired while you happened to be standing on dev.
#
# Both are the same shape and it is the shape this harness guards: a
# recommendation to destroy something, produced by a check that never looked at
# the thing that made it unsafe.
#
# Run: ~/.claude/commands/bin/test-repo-hygiene.sh   (exit 0 = all three hold)

set -uo pipefail

SCRIPT="${1:-$HOME/.claude/commands/bin/repo-hygiene.sh}"
D=$(mktemp -d)
trap 'rm -rf "$D"' EXIT
mkdir -p "$D/stub" "$D/repo"

git -C "$D/repo" init -q
git -C "$D/repo" commit -q --allow-empty -m init
git -C "$D/repo" remote add origin https://example.invalid/x/y.git

# gh is stubbed so the cases are deterministic; the real script must not care.
stub_gh() {  # $1 = merged heads (newline-sep), $2 = open heads
  cat > "$D/stub/gh" <<EOF
#!/usr/bin/env bash
if [[ "\$*" == *"--state merged"* ]]; then printf '%s\n' $(printf '%q' "$1"); exit 0; fi
if [[ "\$*" == *"--state open"*   ]]; then printf '%s\n' $(printf '%q' "$2"); exit 0; fi
exit 0
EOF
  chmod +x "$D/stub/gh"
}

run() { (cd "$D/repo" && PATH="$D/stub:$PATH" bash "$SCRIPT" 2>&1); }

fails=0
check() {  # $1 = label, $2 = pattern, $3 = want present|absent
  local out; out=$(run)
  if printf '%s' "$out" | grep -qE "$2"; then found=present; else found=absent; fi
  if [ "$found" = "$3" ]; then
    echo "ok   — $1"
  else
    echo "FAIL — $1 (wanted $3, got $found)"
    printf '%s\n' "$out" | sed 's/^/       /'
    fails=$((fails + 1))
  fi
}

# 1. A head reused across PRs: merged once, open now. Deleting it destroys the
#    open PR's branch, so an OPEN PR must outrank a merged one on the same head.
git -C "$D/repo" branch reused-head
stub_gh "reused-head" "reused-head"
check "open PR outranks a merged PR on the same head" "branch 'reused-head'" absent

# 2. The actual job still has to work — no false negative from fix 1.
git -C "$D/repo" branch truly-merged
stub_gh "truly-merged" ""
check "a genuinely merged feature branch is still reported" "branch 'truly-merged'" present

# 3. Long-lived branches appear as merged HEADS (dev->staging PRs). Never
#    recommend deleting one, whichever branch you are standing on.
git -C "$D/repo" branch dev
stub_gh "dev" ""
check "the default/long-lived branch is never reported" "branch 'dev'" absent

# 4. The main checkout is the one you are standing in; "safe to remove" is always
#    wrong for it, and it was being printed on every run.
stub_gh "master
main" ""
check "the main worktree is never called safe to remove" "worktree .* safe to remove" absent

if [ "$fails" -gt 0 ]; then
  echo "$fails check(s) failed — repo-hygiene.sh can recommend destroying live work"
  exit 1
fi
echo "all checks passed"
