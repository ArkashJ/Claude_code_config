#!/bin/sh
# SessionStart gate (synthesis 2026-08-06 §0 + CR-2, item 3 of 'if only three things
# get built'): fetch BEFORE any state is read, and put fresh git state into context
# unprompted — /start's two field failures were "not invoked" and "read git log
# before fetching" (81175d0e, cbfc486c).
cd "$CLAUDE_PROJECT_DIR" 2>/dev/null || exit 0
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0
timeout 8 git fetch --all --prune --quiet 2>/dev/null
branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
dirty=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
ab=$(git rev-list --left-right --count '@{upstream}...HEAD' 2>/dev/null | awk '{print "behind="$1" ahead="$2}')
[ -n "$ab" ] || ab="no-upstream"
echo "[preflight] repo=$(basename "$PWD") branch=$branch dirty-files=$dirty $ab (origin freshly fetched)."
echo "If this is a WORK session: run /start before acting — enumerate sources with UNTRUNCATED counts first."
# Repo hygiene at OPEN, not just at close. Inherited mess is what the corpus documents
# (39771011 CLAUDE.md files inherited uncommitted; ca8cacbc a forgotten worktree owning
# main and blocking a checkout; e7665ec7 a polluted main checkout costing a whole
# worktree/branch/PR cycle for a one-file fix) — cleanup at close only tidies.
# Measured 2026-08-10: /wrap was invoked in 4 of 109 sessions, /start in 7. This hook
# fires in all of them. --brief prints one line and is silent when clean.
timeout 25 "$HOME/.claude/commands/bin/repo-hygiene.sh" --brief 2>/dev/null
exit 0
