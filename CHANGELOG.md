# Changelog

All notable changes to this config repo are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.1.0] — 2026-06-22

### Added
- `hooks/cleanup.sh` (new) + a `SessionStart` hook — periodic housekeeping that
  keeps `~/.claude` from ballooning over weeks of use. Cache and scratch files
  older than 14 days are removed; plan files older than 36 hours are removed.
  Versioned config is never touched. The cache sweep self-throttles to once
  every 6 hours; the plans sweep runs each session.

  ```
  swept (disposable)                     never touched (versioned)
  -----------------------------------    -------------------------------
  cache/ paste-cache/ image-cache/   ->  plugins/   skills/
  shell-snapshots/ file-history/         settings.json   hooks/
  backups/   *-cache.json   (>14 days)   commands/  rules/  agents/
  plans/                    (>36 hours)  statusline.sh   sync.sh
  ```

### Changed
- `settings.json` — added `aws-core@claude-plugins-official` to `enabledPlugins`
  so the AWS plugin survives a clean reinstall restore (keep-all union; no
  plugin is ever dropped on restore).
- `skills/` — materialized 11 skills that were committed as symlinks into
  `~/.agents/skills/` (docx, xlsx, vocabulary, find-skills, playwright-cli,
  brandkit, mcp-builder, high-end-visual-design, design-taste-frontend,
  redesign-existing-projects, full-output-enforcement) so they restore on any
  machine, and added `grill-me`. Eight skills whose source is absent on this
  machine remain symlinks and must be re-materialized from the machine that has
  them.

## [1.0.2] — 2026-05-30

### Fixed
- `hooks/format-on-edit.sh` (new) replaces the inline Biome formatter in the
  `PostToolUse` hook. It is now repo-aware: Prettier when the repo configures it
  (`.prettierrc*` / `prettier.config.*` / a `"prettier"` key or dependency in
  `package.json`), Biome only when `biome.json` is present and Prettier is not,
  and nothing for repos that configure no JS/TS formatter. Formatters run from
  the repo root so they respect the repo's own config. Fixes the previous hook
  reformatting Prettier repos with Biome defaults (tabs/semicolons/double-quotes).

## [1.0.1] — 2026-05-30

### Added
- `settings.json` — allowlisted the context-mode MCP tools (`ctx_execute`,
  `ctx_execute_file`, `ctx_batch_execute`, `ctx_search`) to cut permission
  prompts on the most-used tools (~90 calls/session). These run in a sandboxed
  subprocess that cannot mutate the host filesystem.

### Changed
- `settings.json` — find-skills `UserPromptSubmit` hook now prunes stale
  `state/turn-counter-*` files (older than 1 day) on each run, so per-session
  counters no longer accumulate. Firing is unchanged — exactly once at the 3rd
  turn, keyed per session.
- `CLAUDE.md` (global) — added a tool-preferences line: prefer the LSP tool for
  symbol navigation and ast-grep for structural search/edits over plain grep.
- `plugins/installed_plugins.json`, `plugins/known_marketplaces.json` — routine
  plugin auto-update manifest sync.

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

[1.1.0]: https://github.com/ArkashJ/Claude_code_config/releases/tag/v1.1.0
[1.0.2]: https://github.com/ArkashJ/Claude_code_config/releases/tag/v1.0.2
[1.0.1]: https://github.com/ArkashJ/Claude_code_config/releases/tag/v1.0.1
[1.0.0]: https://github.com/ArkashJ/Claude_code_config/releases/tag/v1.0.0
