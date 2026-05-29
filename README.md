# Claude Code config

Version-controlled `~/.claude` configuration: global instructions, custom
commands, hooks, rules, skills, and the plugin manifest. Everything generated
or machine-specific (transcripts, caches, history, credentials, downloaded
plugin code) is git-ignored — see `.gitignore`.

## What's tracked

```
CLAUDE.md  RTK.md                  global instructions
settings.json  statusline.sh       harness config + statusline
commands/  hooks/  rules/  skills/  customizations
plugins/installed_plugins.json     reproducible plugin list
plugins/known_marketplaces.json    marketplaces to re-add
```

> `settings.local.json` and `.credentials.json` are intentionally ignored —
> keep machine-specific overrides and secrets local, never commit them.

## Sync to a new machine

`~/.claude` already exists after installing Claude Code, so init-in-place and
hard-reset to the repo (this only overwrites *tracked* files — your local
transcripts/caches are left untouched):

```bash
# 1. install Claude Code first (creates ~/.claude), then:
cd ~/.claude
git init
git remote add origin https://github.com/ArkashJ/Claude_code_config.git
git fetch origin
git reset --hard origin/main      # overwrites tracked config only
git branch -M main
git branch --set-upstream-to=origin/main main
```

Then restore plugins (the JSON manifests list what to reinstall):

```bash
cat ~/.claude/plugins/known_marketplaces.json   # marketplaces to add
cat ~/.claude/plugins/installed_plugins.json     # plugins to install
# re-add via the /plugin marketplace commands inside Claude Code
```

## Day-to-day sync

Use the bundled `sync.sh` (or the raw git commands underneath):

```bash
cd ~/.claude
./sync.sh status            # what's pending
./sync.sh push "message"    # commit tracked changes + push  (msg optional)
./sync.sh pull              # rebase local config on top of remote
./sync.sh setup <git-url>   # first-time setup on a new machine
```

## Adding a new file to version control

The repo uses a **whitelist** `.gitignore` (ignore `*`, then re-include).
A new top-level file or dir is ignored by default — add a `!path` line to
`.gitignore` to start tracking it.
