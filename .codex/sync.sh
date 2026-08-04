#!/bin/sh
# Sync Codex-adapted command variants to BOTH Codex surfaces:
#  1. ~/.codex/prompts/<name>.md      — custom prompts (/name)
#  2. ~/.agents/skills/<name>/SKILL.md — agent skills ($name), symlinked into ~/.codex/skills
# Sources are *.prompt so Claude Code's command scanner never registers them.
cd "$(dirname "$0")"
for f in *.prompt; do
  n="${f%.prompt}"
  cp "$f" ~/.codex/prompts/"$n.md"
  mkdir -p ~/.agents/skills/"$n"
  { echo "---";
    echo "name: $n";
    case "$n" in
      start)      echo "description: Open a session properly — preflight (git/gh/PATH), enumerate sources with counts, working rules (commit/push/checkpoint continuously, verify at source, volunteered status). Use at the start of any coding session." ;;
      wrap)       echo "description: Close a session — land all work, derive changelog/issues/board from git and gh, hand off into the PR, final gate-output status (no percentages)." ;;
      checkpoint) echo "description: Force a save-point now — commit, push, checkpoint log with verify certificates, status. Use before stepping away or when a session feels risky." ;;
      mission)    echo "description: Long-running autonomous run — phases with per-phase wraps, batched blockers, self-preservation before limits, skeptical review before final wrap." ;;
    esac;
    echo "---"; echo; cat "$f"; } > ~/.agents/skills/"$n"/SKILL.md
  [ -e ~/.codex/skills/"$n" ] || ln -s ~/.agents/skills/"$n" ~/.codex/skills/"$n"
done
echo "prompts: $(ls ~/.codex/prompts/ | tr '\n' ' ')"
echo "skills:  $(ls ~/.codex/skills/ | grep -E 'start|wrap|checkpoint|mission' | tr '\n' ' ')"
