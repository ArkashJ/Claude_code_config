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
exit 0
