#!/usr/bin/env bash
# Sync ~/.claude config with its git remote.
#
#   ./sync.sh push ["message"]   commit all tracked changes and push
#   ./sync.sh pull               rebase local config on top of the remote
#   ./sync.sh status             show pending tracked changes
#   ./sync.sh setup <git-url>    first-time setup on a NEW machine
#
# Only tracked config moves; gitignored transcripts/caches/credentials
# never leave (or arrive on) the machine.
set -euo pipefail
cd "$HOME/.claude"

case "${1:-}" in
  push)
    git add -A
    if git diff --cached --quiet; then
      echo "nothing to commit — already in sync"
      exit 0
    fi
    git commit -m "${2:-config sync $(date +%Y-%m-%d)}"
    git push
    ;;
  pull)
    git pull --rebase --autostash
    ;;
  status)
    git status -s
    ;;
  setup)
    url="${2:?usage: ./sync.sh setup <git-url>}"
    git init
    git remote add origin "$url" 2>/dev/null || git remote set-url origin "$url"
    git fetch origin
    git reset --hard origin/main   # overwrites tracked config only
    git branch -M main
    git branch --set-upstream-to=origin/main main
    echo "synced. review with: git log --oneline -5"
    ;;
  *)
    sed -n '2,9p' "$0"   # print the usage header above
    exit 1
    ;;
esac
