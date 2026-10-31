Codex mirror of the session commands, /start, /wrap and /mission.
sync.sh generates <name>.prompt from ../<name>.md (plus <name>.codex-extra for Codex-only rules)
and copies it to ~/.codex/prompts/<name>.md and ~/.agents/skills/<name>/SKILL.md.
Edit ../start.md, ../wrap.md or ../mission.md, never the generated files. Dot-dir so Claude's command scanner ignores it.
