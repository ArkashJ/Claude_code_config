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
#   4. pkill / killall / kill $(pgrep …): name-matched kills hit other sessions.
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
# Same wait, renamed to dodge the rule above. 2026-10-23 harvest of 14 days of Claude transcripts:
# `perl -e 'select(undef,undef,undef,N)'` 540x and `read -t N` 145x, versus 111 blocked `sleep N`.
if printf '%s' "$cmd" | grep -Eq 'select\(undef|(^|[;&|[:space:]])read[[:space:]]+(-[a-zA-Z]+[[:space:]]+)*-t[[:space:]]*[0-9]'; then
    echo "BLOCKED by ~/.claude/hooks/guard-bash.sh: a disguised sleep (perl select / read -t). Same rule as 'sleep N': use the Monitor tool with an until-loop, or run_in_background." >&2
    exit 2
fi
# Empty-body wait loop, the inverse dodge: `until grep -q X log; do :; done` spins a CPU and forks grep
# thousands of times a second. 2026-10-24: 11 of them in one session plus a helper's took load to 105 on 8 CPUs.
if printf '%s' "$cmd" | grep -Eq '(^|[;&|[:space:]])do[[:space:]]+(:|true)?[[:space:]]*;?[[:space:]]*done([;&|[:space:]]|$)'; then
    echo "BLOCKED by ~/.claude/hooks/guard-bash.sh: empty-body busy-wait loop ('do :; done'). It spins a CPU forever; use run_in_background and wait for its notification, or a Monitor until-loop with 'timeout 15 tail -f /dev/null' as the pause." >&2
    exit 2
fi
if printf '%s' "$cmd" | grep -Eq '(^[[:space:]]*cd[[:space:]]+[^;&|]+&&)|((;|&&)[[:space:]]*cd[[:space:]]+[^;&|]+(;|&&|$))'; then
    echo "BLOCKED by ~/.claude/hooks/guard-bash.sh: 'cd X &&' / '; cd X' chain found. The harness resets cwd between calls and the chain leaks it into the next command; use an absolute path, 'git -C <path>', or 'uv --directory <path>'." >&2
    exit 2
fi
# 2026-10-17 (Spot missions #821/#823 running side by side): two lanes ran
# `pkill -f "bun test --isolate"` and `pkill -f next-server`, which can kill the OTHER
# session's web gate and dev server and make its run report a false red. Kill only a PID
# you recorded at launch (`echo $! > /tmp/<lane>.pid`; `kill "$(cat /tmp/<lane>.pid)"`).
if printf '%s' "$cmd" | grep -Eq '(^|[;&|(`][[:space:]]*|sudo[[:space:]]+)(pkill|killall)([[:space:]]|$)' \
   || printf '%s' "$cmd" | grep -Eq 'kill[^;&|]*(\$\(|`)[[:space:]]*(pgrep|pidof)' \
   || printf '%s' "$cmd" | grep -Eq '(pgrep|pidof)[^;&]*\|[[:space:]]*xargs([[:space:]]+-[^[:space:]]+)*[[:space:]]+kill'; then
    echo "BLOCKED by ~/.claude/hooks/guard-bash.sh: pkill/killall (or kill via pgrep/pidof) matches processes by name and can kill OTHER sessions' dev servers and test runs (2026-10-17). Record your own PID at launch and use 'kill <pid>'." >&2
    exit 2
fi
# Session afac82d1 (2026-09-27): a sub-agent meant to close its own sessions ran
# `playwright-cli close-all`, which closes EVERY playwright-cli session on the machine,
# including other lanes' logged-in browsers. Name the session instead.
# 2026-10-02 (Profectus launch train): a backgrounded compound command ran
# `make -C $I verify.sg; ...; ./scripts/check-tracked-artifacts.sh; ./scripts/check-evidence-policy.sh`
# — every other step named the worktree, the two relative ones ran from the
# harness cwd (apps/api) and exited 127 "No such file", which the log then
# carried as ART_EXIT=127 next to green steps. A relative ./scripts/ path in a
# command that names a worktree is always the wrong tree: use `env -C <wt>
# ./scripts/x.sh` or the absolute path.
if printf '%s' "$cmd" | grep -q '/\.claude/worktrees/' && printf '%s' "$cmd" | grep -Eq '(^|[;&|(][[:space:]]*)\./scripts/'; then
    echo "BLOCKED by ~/.claude/hooks/guard-bash.sh: relative './scripts/...' in a command that names a .claude/worktrees/ path. The harness cwd is not that worktree (2026-10-02: exit 127 next to green steps). Use 'env -C <worktree> ./scripts/x.sh' or the absolute path." >&2
    exit 2
fi
if printf '%s' "$cmd" | grep -Eq 'playwright-cli[^;&|]*[[:space:]](close-all|kill-all)([[:space:]]|$)'; then
    echo "BLOCKED by ~/.claude/hooks/guard-bash.sh: 'playwright-cli close-all/kill-all' closes every browser session on this machine, including other lanes'. Close only your own: 'playwright-cli -s=<name> close' (see 'playwright-cli list')." >&2
    exit 2
fi
# 2026-10-24 (lane-1 session c569eb61): `gh pr merge 1931 --squash --delete-branch` deleted the
# branch another lane's open #1936 was stacked on; GitHub auto-CLOSED #1936 (not retargeted), and
# it had to be restored by recreating the ref, reopening and retargeting. Retarget children first.
if printf '%s' "$cmd" | grep -Eq 'gh[[:space:]]+pr[[:space:]]+merge[[:space:]]' && printf '%s' "$cmd" | grep -q -- '--delete-branch'; then
    gh_bin=${GUARD_GH:-gh}
    pr=$(printf '%s' "$cmd" | sed -nE 's/.*gh[[:space:]]+pr[[:space:]]+merge[[:space:]]+([0-9]+).*/\1/p' | head -1)
    repo=$(printf '%s' "$cmd" | sed -nE 's/.*gh[[:space:]]+pr[[:space:]]+merge[[:space:]].*(-R|--repo)[[:space:]]+([^[:space:]]+).*/\2/p' | head -1)
    if [ -n "$pr" ]; then
        rflag=(); [ -n "$repo" ] && rflag=(-R "$repo")
        head=$("$gh_bin" pr view "$pr" "${rflag[@]}" --json headRefName -q .headRefName 2>/dev/null || true)
        if [ -n "$head" ]; then
            kids=$("$gh_bin" pr list "${rflag[@]}" --base "$head" --state open --json number -q '[.[].number]|join(" ")' 2>/dev/null || true)
            if [ -n "$kids" ]; then
                echo "BLOCKED by ~/.claude/hooks/guard-bash.sh: open PR(s) $kids are based on '$head'; --delete-branch would make GitHub CLOSE them (2026-10-24: #1936 closed this way). Retarget first: 'gh pr edit <child> --base <new-base>', or merge without --delete-branch." >&2
                exit 2
            fi
        fi
    fi
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
