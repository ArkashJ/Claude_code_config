#!/usr/bin/env bash
# PreToolUse guard for the Bash tool (global). Exit 2 blocks the call and the
# stderr text is shown to the model. Documented in ~/.claude/CLAUDE.md; the
# self-test is guard-bash.test.sh — this guard is only trusted while it passes.
#
# Blocks:
#   1. `sleep <number>` anywhere in the command (compound, nohup, loops): use
#      Monitor / run_in_background instead of sleep-then-poll.
#   2. `cd <path> &&` at command start, or `; cd <path>` / `&& cd <path>` later:
#      cwd leaks into the next call; use absolute paths, `git -C`, `uv --directory`.
#   3. `git commit` while CHERRY_PICK_HEAD exists in the target repo. On
#      2026-09-21 a fixer agent cherry-picked another session's commit
#      (267da99e, deriq page-context) into the shared jev/fix-all worktree; it
#      conflicted and CHERRY_PICK_HEAD plus an unmerged test file sat there
#      until the orchestrator noticed at 05:32Z. A plain `git commit` in that
#      state folds the foreign diff AND its message into whatever is committed
#      next. REBASE_HEAD is deliberately not checked: git leaves it behind after
#      a finished rebase (the main worktree had one with no rebase in progress).
set -u
cmd=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("command",""))' 2>/dev/null || true)
[ -n "$cmd" ] || exit 0

if printf '%s' "$cmd" | grep -Eq '(^|[^[:alnum:]_./-])sleep[[:space:]]+[0-9]'; then
    echo "BLOCKED by ~/.claude/hooks/guard-bash.sh: 'sleep N' found. Do not sleep-then-poll; use the Monitor tool with an until-loop, or run_in_background and wait for the notification." >&2
    exit 2
fi
if printf '%s' "$cmd" | grep -Eq '(^[[:space:]]*cd[[:space:]]+[^;&|]+&&)|((;|&&)[[:space:]]*cd[[:space:]]+[^;&|]+(;|&&|$))'; then
    echo "BLOCKED by ~/.claude/hooks/guard-bash.sh: 'cd X &&' / '; cd X' chain found. The harness resets cwd between calls and the chain leaks it into the next command; use an absolute path, 'git -C <path>', or 'uv --directory <path>'." >&2
    exit 2
fi
if printf '%s' "$cmd" | grep -Eq '(^|[;&|][[:space:]]*)git([[:space:]]+-C[[:space:]]+[^[:space:]]+)?[[:space:]]+commit([[:space:]]|$)'; then
    dir=$(printf '%s' "$cmd" | sed -nE 's/.*git[[:space:]]+-C[[:space:]]+([^[:space:]]+)[[:space:]]+commit.*/\1/p' | head -1 | tr -d "\"'")
    dir=${dir:-$PWD}
    cp_head=$(git -C "$dir" rev-parse --git-path CHERRY_PICK_HEAD 2>/dev/null || true)
    # --git-path answers relative to the worktree for the main checkout and
    # absolute for linked worktrees; the first self-test run missed the file
    # because it tested the relative path from the hook's own cwd.
    case "$cp_head" in ""|/*) ;; *) cp_head="$dir/$cp_head" ;; esac
    if [ -n "$cp_head" ] && [ -f "$cp_head" ]; then
        what=$(git -C "$dir" log -1 --format='%h %s' CHERRY_PICK_HEAD 2>/dev/null || echo "unknown commit")
        echo "BLOCKED by ~/.claude/hooks/guard-bash.sh: a cherry-pick is in progress in $dir ($what). A plain 'git commit' would fold that foreign diff and its message into your commit. Run 'git cherry-pick --continue' if it is yours, or 'git cherry-pick --abort' if it is not, then commit." >&2
        exit 2
    fi
fi
exit 0
