#!/bin/sh
# Sync Codex-adapted command variants to BOTH Codex surfaces:
#  1. ~/.codex/prompts/<name>.md      — custom prompts (/name)
#  2. ~/.agents/skills/<name>/SKILL.md — agent skills ($name), symlinked into ~/.codex/skills
# Sources are *.prompt so Claude Code's command scanner never registers them.
cd "$(dirname "$0")"
# wrap is harness-neutral, so its Codex variant is GENERATED from ../wrap.md. The hand-copied
# variant silently lacked the hygiene, continuation-prompt and final-status steps, and "give me
# a handoff prompt" was the most repeated Codex re-ask after $wrap (2026-09-27 study).
for n in wrap; do awk 'NR==1&&/^---$/{f=1;next} f&&/^---$/{f=0;next} !f' "../$n.md" > "$n.prompt"; done
# POSIX sh only: claude-sync runs this with `sh` (a bash `< <(...)` here broke every sync).
# Drift gate for the hand-adapted rest: every "## " section of ../<n>.md must appear in
# <n>.prompt or be listed in OMIT as deliberately Claude-only ("<n>: <heading>").
drift=0
for f in *.prompt; do
  n="${f%.prompt}"; [ -f "../$n.md" ] || continue
  while IFS= read -r h; do
    grep -qxF -- "$h" "$f" || grep -qxF -- "$n: $h" OMIT 2>/dev/null ||
      { echo "DRIFT: $f lacks '$h' (port it, or add '$n: $h' to .codex/OMIT)" >&2; drift=1; }
  done <<EOF
$(grep -E '^##+ ' "../$n.md")
EOF
done
[ "$drift" -eq 0 ] || exit 1
for f in *.prompt; do
  n="${f%.prompt}"
  cp "$f" ~/.codex/prompts/"$n.md"
  # A symlink here (e.g. link-skills pointing it at ~/.claude/skills) would make the write below land in
  # the repo copy, which link-skills then removes, leaving Codex a dangling link (2026-09-22, featuredev/map).
  [ -L ~/.agents/skills/"$n" ] && rm ~/.agents/skills/"$n"
  mkdir -p ~/.agents/skills/"$n"
  { echo "---";
    echo "name: $n";
    case "$n" in
      start)      echo "description: Open a session properly — preflight (git/gh/PATH), enumerate sources with counts, working rules (commit/push/checkpoint continuously, verify at source, volunteered status). Use at the start of any coding session." ;;
      wrap)       echo "description: Close a session — land all work, derive changelog/issues/board from git and gh, hand off into the PR, final gate-output status (no percentages)." ;;
      checkpoint) echo "description: Force a save-point now — commit, push, checkpoint log with verify certificates, status. Use before stepping away or when a session feels risky." ;;
      mission)    echo "description: Long-running autonomous run — phases with per-phase wraps, batched blockers, self-preservation before limits, skeptical review before final wrap." ;;
      *) d=$(sed -n 's/^description: *//p' "../$n.md" 2>/dev/null | head -1); echo "description: ${d:-Codex variant of /$n}" ;;
    esac;
    echo "---"; echo; cat "$f"; } > ~/.agents/skills/"$n"/SKILL.md
  [ -e ~/.codex/skills/"$n" ] || ln -s ~/.agents/skills/"$n" ~/.codex/skills/"$n"
done
echo "prompts: $(ls ~/.codex/prompts/ | tr '\n' ' ')"
echo "skills:  $(ls ~/.codex/skills/ | grep -E "$(ls *.prompt | sed 's/.prompt$//' | paste -sd'|' -)" | tr '\n' ' ')"
