#!/usr/bin/env bash
# Periodic housekeeping for ~/.claude — keeps the directory from ballooning
# over weeks of use without ever touching versioned config.
#
#   - cache / scratch files older than 14 days are removed
#   - plan files older than 36 hours are removed
#
# NEVER touched: plugins/, skills/, settings.json, hooks/, commands/, rules/,
# agents/, statusline.sh, sync.sh, CLAUDE.md, RTK.md. Only the disposable
# directories listed below are swept.
#
# Wired to SessionStart. The cache sweep self-throttles to once / 6h via a
# marker file so it stays cheap; the plans sweep runs every session (36h
# granularity, negligible cost).
set -uo pipefail
ROOT="$HOME/.claude"
[ -d "$ROOT" ] || exit 0

# -- plans: drop anything older than 36h (2160 minutes) ----------------------
if [ -d "$ROOT/plans" ]; then
  find "$ROOT/plans" -mindepth 1 -mmin +2160 -delete 2>/dev/null || true
fi

# -- caches: heavier sweep, throttled to once / 6h ---------------------------
MARK="$ROOT/.last-cache-sweep"
now=$(date +%s)
last=0
[ -f "$MARK" ] && last=$(date -r "$MARK" +%s 2>/dev/null || echo 0)
if [ $(( now - last )) -ge 21600 ]; then
  for d in cache paste-cache image-cache shell-snapshots file-history backups; do
    dir="$ROOT/$d"
    [ -d "$dir" ] || continue
    find "$dir" -mindepth 1 -type f -mtime +14 -delete 2>/dev/null || true
    find "$dir" -mindepth 1 -type d -empty -delete 2>/dev/null || true
  done
  # stray top-level *-cache.json files (gh-pr-status-cache.json, etc.)
  find "$ROOT" -maxdepth 1 -type f -name '*-cache.json' -mtime +14 -delete 2>/dev/null || true
  touch "$MARK"
fi
exit 0
