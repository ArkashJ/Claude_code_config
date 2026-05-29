@RTK.md

# Working with me
- Multiple client repos (TypeScript + Python).
- Auto-mode trusted; don't ask before reading/grepping.
- Use context-mode for any tool output over ~20 lines.
- Comments: only WHY, never WHAT.
- ASCII flow diagrams when explaining a process or system; otherwise plain prose.
- Brainstorm before non-trivial changes; don't impose blanket rules.

---

# This config repo (`~/.claude`)

This repo versions `~/.claude`. When Claude Code is run from inside this
directory, the rules below apply in addition to the global instructions above.

## Tracked files and their roles

| File / Dir | Role |
|---|---|
| `CLAUDE.md` | This file — global + repo-level instructions |
| `RTK.md` | RTK proxy reference (@-included above) |
| `settings.json` | Permissions, hooks, env vars, MCP server config |
| `statusline.sh` | Custom Claude Code status line |
| `sync.sh` | push / pull / status / setup helper |
| `commands/` | Custom slash commands (.md files) |
| `hooks/` | PreToolUse / PostToolUse / Stop event scripts |
| `rules/` | Auto-loaded rule files |
| `skills/` | Installed agent skills |
| `plugins/installed_plugins.json` | Plugin manifest |
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
then commit the new file and the updated `.gitignore` together.
