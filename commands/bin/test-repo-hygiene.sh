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

# 5. A worktree with a live process still using it as cwd must be flagged, even
# with no PR/branch signal at all (this is a pure lsof/filesystem check). Added
# 2026-09-09: `git worktree remove --force` deleted a directory a running
# `next dev` still had as its cwd; the dev server kept answering 200 on / while
# every route started 500ing, undetected for ~20 minutes.
mkdir -p "$D/live-wt"
git -C "$D/repo" worktree add -q "$D/live-wt" -b live-wt-branch >/dev/null 2>&1
( cd "$D/live-wt" && exec tail -f /dev/null ) &
live_pid=$!
# lsof needs the child's own cwd, not the backgrounding shell's -- give it a beat
# to actually chdir and open cwd, bounded so this test can't hang.
deadline=$((SECONDS + 5))
while [ "$SECONDS" -lt "$deadline" ]; do
  lsof -d cwd -Fpn -p "$live_pid" 2>/dev/null | grep -q "n$D/live-wt" && break
done
stub_gh "" ""
check "a worktree with a live process as cwd is flagged, not silently removable" "live-wt.*live process" present
kill "$live_pid" 2>/dev/null
wait "$live_pid" 2>/dev/null
git -C "$D/repo" worktree remove --force "$D/live-wt" >/dev/null 2>&1

# 6-8. --landed: /wrap's SAFE TO END line must be computed from the tree, and must say "no"
# for each way work can exist only on this machine (sessions 19df0d01, a3ec5016: "do i end
# session" / "are the files on main or no??" asked after a wrap had already reported done).
runl() { (cd "$D/repo" && PATH="$D/stub:$PATH" bash "$SCRIPT" --landed 2>&1); }
checkl() {  # $1 = label, $2 = pattern
  local out; out=$(runl)   # capture first: under pipefail `runl | grep -q` fails on runl's exit 1
  if printf '%s' "$out" | grep -qE "$2"; then echo "ok   — $1"; else echo "FAIL — $1"; printf '%s\n' "$out" | sed 's/^/       /'; fails=$((fails + 1)); fi
}
stub_gh "" ""
git -C "$D/repo" update-ref refs/remotes/origin/master HEAD   # everything so far is "pushed"
checkl "a clean, pushed repo is safe to end" "^SAFE TO END: yes"
echo x > "$D/repo/scratch.txt"
checkl "an uncommitted file blocks ending" "^SAFE TO END: no — 1 uncommitted"
rm "$D/repo/scratch.txt"
git -C "$D/repo" checkout -q -b local-only
git -C "$D/repo" commit -q --allow-empty -m "never pushed"
checkl "a branch with no upstream and an unpushed commit blocks ending" "branch 'local-only' has 1 commit"
checkl "…and the verdict says no" "^SAFE TO END: no"
git -C "$D/repo" checkout -q master
stub_gh "local-only" ""   # its PR was squash-merged and GitHub deleted the remote head
checkl "a squash-merged branch gets delete advice, not push advice" "^SAFE TO END: yes"

if [ "$fails" -gt 0 ]; then
  echo "$fails check(s) failed — repo-hygiene.sh can recommend destroying live work"
  exit 1
fi
echo "all checks passed"
