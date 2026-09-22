# Changelog

## v1.1.1 — 2026-09-22
- Track `CHANGELOG.md` (the root `/*` ignore rule hid it from v1.1.0).

## v1.1.0 — 2026-09-22

Sync of the rebuilt `~/.claude` after the 2026-09-16 wipe.

### Added
- `hooks/guard-bash.sh` (+ `guard-bash.test.sh`): PreToolUse Bash guard — blocks `sleep N`
  anywhere in a command and `cd X && cmd` chains. Wired in `settings.example.json`.
- Commands: `/backend-edges`, `/review-queue`, `/ui-hunt`.
- Skills: `qa` (merges `qa_skill` + `frontend-verify`), `packet-plan`, `find-skills`,
  `typesafe-ai`, `featuredev`, `map`.
- `CLAUDE.md`: enumeration discipline, no-`sleep` rule, no `cd &&` chains, LSP-first navigation.

- `claude-sync adopt` works on any machine in one command: falls back to HTTPS when no
  SSH key is loaded, always links `~/.local/bin/claude-sync`, and reinstalls every plugin
  and marketplace from `plugins/*.json`.

### Changed
- `claude-sync` (push) pulls with `--rebase --autostash` first, so pushes from several
  machines never get rejected; `claude-sync pull` autostashes local edits.
- `settings.example.json` writes `$HOME` as `~`, so hook paths work for any user, adds a
  SessionStart hook that runs `claude-sync pull` in the background, and no longer carries
  `autoMode` (it held client-specific policy; this repo is public).
- `settings.example.json` regenerated from the live settings: `opus[1m]`, auto permission
  mode, per-model effort, ponytail / typesafe marketplaces.
- Plugin manifests, `agents-skill-lock.json`, `/start`, `/wrap`, `/mission`, `/map`,
  `/checkpoint` refreshed.

### Removed
- `qa_skill`, `frontend-verify` (folded into `qa`).
- `source-command-{checkpoint,start,wrap}` skills, `/harvest` and `/investigate` commands
  (`harvest` lives on as a skill).

## v1.0.2 — 2026-05-30
- hooks: make format-on-edit repo-aware (Prettier vs Biome).

## v1.0.1 — 2026-05-30
- config: prune stale turn-counters, allowlist context-mode MCP, tool prefs.

## v1.0.0 — 2026-05-29
- Initial production release.
