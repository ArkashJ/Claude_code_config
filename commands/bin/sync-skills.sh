#!/bin/sh
# Publish ~/.claude/commands/*.md to the /skills surface on arkashj.com.
# lib/skills.ts globs content/skills/*.md and needs `name:` in the frontmatter,
# which the command files don't carry — inject it after the opening `---`.
set -eu

SRC="${SRC:-$HOME/.claude/commands}"
SITE="${SITE:-$HOME/Developer/personal/Personal-Website}"
DEST="$SITE/content/skills"

[ -d "$DEST" ] || { echo "sync-skills: no $DEST — set SITE=<path to Personal-Website>" >&2; exit 1; }

n=0
written=""
for f in "$SRC"/*.md; do
  slug=$(basename "$f" .md)
  awk -v name="$slug" 'NR==1 && $0=="---" { print; print "name: " name; next } { print }' "$f" > "$DEST/$slug.md"
  written="$written $DEST/$slug.md"
  n=$((n + 1))
done

# CI runs `format:check` over content/, so normalize what we just wrote — and only that,
# so a sync never drags the other ~78 skill files into the diff.
if [ -x "$SITE/node_modules/.bin/prettier" ]; then
  # shellcheck disable=SC2086  # $written is a space-joined path list, intentionally split
  "$SITE/node_modules/.bin/prettier" --write --log-level warn $written
fi

echo "sync-skills: $n command(s) -> $DEST"
