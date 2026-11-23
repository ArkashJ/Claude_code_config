Codex mirror of the Claude-local commands /start, /wrap, /mission and /refute-pr, plus ~/.codex/AGENTS.md.
sync.sh generates <name>.prompt from ../<name>.md (plus <name>.codex-extra for Codex-only rules) and copies it to
~/.codex/prompts/<name>.md and ~/.agents/skills/<name>/SKILL.md. It also writes ~/.codex/AGENTS.md from
AGENTS.codex-extra + ../../CLAUDE.md minus <!-- claude-only --> blocks. Edit the sources, never the generated files.
Dot-dir so Claude's command scanner ignores it.
