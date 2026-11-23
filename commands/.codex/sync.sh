#!/bin/sh
# Mirror the Claude-local commands (start, wrap, mission, refute-pr) to BOTH Codex surfaces:
#  1. ~/.codex/prompts/<name>.md      — custom prompts (/name)
#  2. ~/.agents/skills/<name>/SKILL.md — agent skills ($name), ~/.codex/skills is a symlink to ~/.agents/skills
# Each <name>.prompt is GENERATED from ../<name>.md (frontmatter stripped) plus an optional
# <name>.codex-extra, so the Codex copy can never drift from the Claude one. link-skills.sh reads the
# *.prompt names as the codex-only list. POSIX sh only: claude-sync runs this with `sh`.
set -eu
cd "$(dirname "$0")"
NAMES="start wrap mission refute-pr"
for n in $NAMES; do
  [ -f "../$n.md" ] || { echo "sync: missing ../$n.md" >&2; exit 1; }
  { awk 'NR==1&&/^---$/{f=1;next} f&&/^---$/{f=0;next} !f' "../$n.md"
    if [ -f "$n.codex-extra" ]; then echo; cat "$n.codex-extra"; fi; } > "$n.prompt"
  # Never write through a symlink (an old link points into another repo).
  if [ -L ~/.codex/prompts/"$n.md" ]; then rm ~/.codex/prompts/"$n.md"; fi
  cp "$n.prompt" ~/.codex/prompts/"$n.md"
  # A symlink here would make the write below land in another copy; replace it with a real dir.
  if [ -L ~/.agents/skills/"$n" ]; then rm ~/.agents/skills/"$n"; fi
  mkdir -p ~/.agents/skills/"$n"
  d=$(sed -n 's/^description: *//p' "../$n.md" | head -1)
  printf -- '---\nname: %s\ndescription: %s\n---\n\n' "$n" "$d" > ~/.agents/skills/"$n"/SKILL.md
  cat "$n.prompt" >> ~/.agents/skills/"$n"/SKILL.md
done
echo "prompts: $(ls ~/.codex/prompts/ | tr '\n' ' ')"
echo "skills:  $NAMES"
# ~/.codex/AGENTS.md = Codex header + CLAUDE.md without its claude-only blocks, so the two never drift.
if [ -L ~/.codex/AGENTS.md ]; then rm ~/.codex/AGENTS.md; fi
{ cat AGENTS.codex-extra
  awk '/<!-- claude-only:begin/{s=1;next} /<!-- claude-only:end/{s=0;next} !s' ../../CLAUDE.md; } > ~/.codex/AGENTS.md.tmp
grep -q 'state-rules:begin' ~/.codex/AGENTS.md.tmp || { echo "sync: generated AGENTS.md lost the state-rules block" >&2; exit 1; }
mv ~/.codex/AGENTS.md.tmp ~/.codex/AGENTS.md
echo "agents:  ~/.codex/AGENTS.md ($(wc -l < ~/.codex/AGENTS.md | tr -d ' ') lines)"
