Codex-adapted variants of the session commands. Hand-adapted from ../start.md etc.
(Claude-specific mechanics removed: Skill invocations, subagent model tiering).
Dot-dir so Claude Code's command scanner ignores it. sync.sh copies these to
~/.codex/prompts/ where Codex exposes them as /start, /wrap, /checkpoint, /mission.
DRIFT: sync.sh regenerates wrap.prompt from ../wrap.md, and exits 1 when any other variant
lacks a "## " section of its source that is not listed in OMIT.
