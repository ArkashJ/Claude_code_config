Codex-adapted variants of the session commands. Hand-adapted from ../start.md etc.
(Claude-specific mechanics removed: Skill invocations, subagent model tiering).
Dot-dir so Claude Code's command scanner ignores it. sync.sh copies these to
~/.codex/prompts/ where Codex exposes them as /start, /wrap, /checkpoint, /mission.
DRIFT RISK: when patching ../start.md and kin, patch these too — check with:
  diff <(ls ~/.claude/commands/*.md) — no automation yet; revisit if drift bites.
