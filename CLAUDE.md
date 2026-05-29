# Claude Code Config Repo

This repo versions `~/.claude` — Claude Code's global config directory.
When Claude Code is run from inside `~/.claude`, these instructions apply.

## What this repo is

Hand-authored config only. Everything generated (transcripts, caches, history,
credentials, downloaded plugin code) is git-ignored. See `.gitignore` and
`README.md` for the full breakdown.

## Tracked files and their roles

| File / Dir | Role |
|---|---|
| `CLAUDE.md` | Global instructions for all projects (this file's parent) |
| `RTK.md` | RTK proxy reference, @-included by the parent CLAUDE.md |
| `settings.json` | Permissions, hooks, env vars, MCP server config |
| `statusline.sh` | Status line script |
| `sync.sh` | push / pull / setup helper |
| `commands/` | Custom slash commands (.md files) |
| `hooks/` | PreToolUse / PostToolUse / Stop event scripts |
| `rules/` | Auto-loaded rule files (@-included by CLAUDE.md) |
| `skills/` | Installed agent skills |
| `plugins/installed_plugins.json` | Plugin manifest — list of what's installed |
| `plugins/known_marketplaces.json` | Marketplace registry |

## Rules for maintaining this repo

- Never commit secrets. `settings.local.json` and `.credentials.json` are
  gitignored. Machine-specific MCP credentials go there, not in `settings.json`.
- Whitelist gitignore: `/*` ignores everything; `!path` re-includes. A new
  top-level file is ignored until explicitly added to `.gitignore`.
- Plugin code is not committed. Only the JSON manifests are versioned.
- `history.jsonl` is never committed — it can contain CLI secrets.
- No force-push. Multiple machines share this remote.

## Sync workflow

```bash
./sync.sh status              # what's pending
./sync.sh push "message"      # commit + push (message optional)
./sync.sh pull                # rebase on remote
./sync.sh setup <git-url>     # first-time setup on a new machine
```

## Adding a new skill or command

Skills and commands are auto-tracked (`!/skills/` and `!/commands/` are in
`.gitignore`). Just `./sync.sh push` after installing.

## Adding any other new file

Add a `!/filename` (or `!/dirname/`) re-include line to `.gitignore` first,
then commit both the new file and the updated `.gitignore` together.
