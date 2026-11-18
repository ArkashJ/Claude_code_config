# Find the supported command

`benmore help` lists the common workflows; `benmore help all` lists every command
with its effect; `benmore help <command>` prints one command's syntax. The
installed binary's help is authoritative for local CLI syntax; the deployed app's
`benmore api <app> <topic>` and MCP tool schemas are authoritative for server
behavior.

Effect labels: **inspect** reads only; **change** writes source, data or settings
of one instance (`--env`, else the `benmore use` pin, else dev when the app has
one, else prod);
**promote** writes production; **account** changes the app or account itself.
push, deploy, delete-file, `sql --write` and promote print a `target:` line on
stderr first (the save hook only when its push lands in prod); other changing
commands do not, so pass `--env` explicitly. `--env` takes `dev` or `prod`
(`benmore env` also `shared`); any other value stops the command (exit 2)
before anything is sent.

| Concern | Commands | Effect |
| --- | --- | --- |
| Identity and workspace | `login`, `whoami`, `use`, `apps`, `bootstrap`, `sync`, `pull` | account / local (`login` signs in; `whoami`, `apps` inspect; `use`, `sync`, `pull` write local files only; `bootstrap` signs in and writes local files) |
| Agent support | `skill install --agent codex\|claude\|all`, `hooks status`, `docs <topic>` | local |
| Discover contracts | `api <app> '*'`, `api <app> <topic>`, `describe <app> <kind>`, `tool <name>` | inspect (`api --call` and `tool` can change) |
| Source iteration | `push`, `delete-file`, `deploy`, `types`, `sync-status` | change (dev if the app has one, else prod) / inspect |
| Verify | `check`, `verify`, `qa draft`, `probe`, `status`, `diff`, `doctor` | inspect (`probe` runs the route) |
| Release | `promote`, `ship --promote`, `publish`, `unpublish`, `seed-dev`, `refresh-dev` | promote / change |
| Runtime diagnosis | `logs`, `tail`, `errors`, `decode`, `requests`, `audit`, `health` (row counts, sessions, database size against its storage limit), `integrity-check` | inspect |
| Data and recovery | `sql` (`--write --confirm` changes), `import`, `restore`, `reset-seed`, `users` (`list`, `create`, `set-password`, `deactivate`, `reactivate`, `delete`) | change |
| Source history | `git log\|show\|revert`, `github` | inspect / change |
| Settings and services | `env`, `domain`, `email`, `email-domain`, `sms`, `payments`, `dns`, `mcp status\|enable\|disable` | change |
| App and account | `create-app`, `delete`, `disable`, `enable`, `remove-production`, `restart`, `collaborators`, `transfer-ownership` | account |
| Reuse | `feature`, `clone`, `upload`, `media` | change |
| Plan, usage and privacy | `billing`, `usage --local`, `usage sync`, `telemetry` | inspect (`billing`: the account's plan, published apps and seats used / allowed, storage limits) / local / account |

`tool` passes arguments to an MCP tool and keeps its access checks; prefer its
`--args-json` form for nested data. Exit codes: 0 ok, 1 failure, 2 usage, 3
domain failure, 4 authentication, 5 not found; `sync-status` uses 0 clean, 1
drift, 2 conflict, 3 setup/auth/remote error (`api(at:"cli-contracts")`).

There is no `init-workspace`, local `context`, `add` or `screenshot` command. For
hosted UI checks use `browser_check`; for source and contract checks use `api`,
`check` and `verify`.
