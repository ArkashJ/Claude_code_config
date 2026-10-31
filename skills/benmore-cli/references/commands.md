# Find the supported command or recipe

Run `benmore help` for the installed edition. `benmore api --help` is local and
shows selector/call syntax. The current server's `api` recipes and MCP tool schemas
are authoritative for remote capabilities; the installed binary's help is
authoritative for local CLI syntax.

| Concern | Entry points |
| --- | --- |
| Identity and workspace | `login`, `signup`, `whoami`, `bootstrap`, `sync`, `pull`, `use` |
| Agent support | `skill install --agent codex`, `skill install --agent claude`, `hooks status`, `docs harness` |
| Discover app contracts | `api <app> '*'`, `api <app> <topic>`, `describe <app> <kind>`, `tool` |
| Source iteration | `push`, `delete-file`, `sync-status`, `types` |
| App lifecycle | `new`, `deploy`, `apps`, `open`, `disable`, `enable` |
| Verify and release | `check`, `verify`, `ship`, `status`, `diff`, `doctor`, `promote`, `publish` |
| Runtime diagnosis | `probe`, `errors`, `logs`, `tail`, `requests`, `audit`, `health` |
| Source history | `git log`, `git show`, `git revert`, `github` |
| Data and recovery | `sql`, `import`, `integrity-check`, `restore` |
| Reuse and integration | `feature`, `clone`, `env`, `upload`, `media`, `domain` |
| Hosted services | `email`, `email-domain`, `sms`, `payments`, `dns` |
| Usage and privacy | `usage --local`, `usage sync`, `telemetry` |

This map is a starting point, not an assertion that every command is read-only or
available in every edition. `tool` passes arguments to an MCP tool; it does not
bypass its access checks. Prefer its `--args-json` form for nested data instead of
inventing shell quoting for structured values.

There is no `init-workspace` command. Use `bootstrap`, `skill`, and the generated
per-app `AGENTS.md`. Do not use old manuals advertising local `context`, `add`, or
`screenshot` workflows. For hosted UI checks, discover `browser_check`; for source
and contract checks, use `api`, `check`, and `verify`.
