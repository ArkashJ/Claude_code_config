#!/bin/sh
# Push Codex-adapted command variants into Codex's custom-prompts dir.
# Sources are *.prompt so Claude Code's command scanner never registers them.
cd "$(dirname "$0")"
for f in *.prompt; do cp "$f" ~/.codex/prompts/"${f%.prompt}.md"; done
echo "synced: $(ls ~/.codex/prompts/)"
