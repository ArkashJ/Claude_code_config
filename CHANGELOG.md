# Changelog

All notable changes to this config repo are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] — 2026-05-29

### Added

**Config infrastructure**
- `.gitignore` — whitelist-style ignore rules; tracks config, never transcripts/caches/secrets
- `sync.sh` — `push` / `pull` / `status` / `setup` subcommands for cross-machine sync
- `CLAUDE.md` — repo-level instructions for working within this config directory
- `README.md` — full setup guide, repo layout, skills table, sync flow diagram

**Global instructions**
- `CLAUDE.md` (global) — instructions applied across all projects
- `RTK.md` — RTK (Rust Token Killer) usage reference, @-included by global CLAUDE.md

**Harness config**
- `settings.json` — permissions, hooks, environment variables, MCP server config
- `statusline.sh` — custom Claude Code status line

**Custom commands** (`commands/`)
- `full-app-test.md` — end-to-end app test slash command

**Hooks** (`hooks/`)
- `context-mode-cache-heal.mjs` — PreToolUse hook; keeps context-mode cache healthy

**Rules** (`rules/`)
- `context7.md` — ctx7 docs-fetching rule; fetches current library docs before answering

**Skills** (`skills/`) — 41 agent skills installed
- `ast-grep` — structural code search via AST patterns
- `build-a-chatbot` — chatbot / AI assistant wiring guide
- `client-value-maximizer` — high-impact codebase improvement audit
- `docx` / `pdf` / `xlsx` — document creation and manipulation
- `find-skills` — skill discovery from skills.sh ecosystem
- `frontend-design` — production-grade UI component generation
- `network-graph-modal` — force-directed relationship graph modal
- `playwright-cli` — browser automation and E2E testing
- `playwright-doc-generator` — screenshot-driven client-facing documentation
- `presentation_maker` — formatted presentation generation
- `remotion-best-practices` — video creation in React with Remotion
- `vercel-composition-patterns` — React composition and component API design
- `vercel-react-best-practices` — React / Next.js performance patterns

**Plugin manifests** (`plugins/`)
- `installed_plugins.json` — reproducible list of installed plugins
- `known_marketplaces.json` — marketplace registry for reinstall on new machines

---

[1.0.0]: https://github.com/ArkashJ/Claude_code_config/releases/tag/v1.0.0
