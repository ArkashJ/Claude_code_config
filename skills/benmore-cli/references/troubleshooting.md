# Diagnose the failing layer

Start with the selected app, environment, CLI version, exact command, exit status,
and the smallest useful error. Inspect `benmore api <app> recovery` for current
recovery behavior. Avoid copying credentials or unrelated application records.

| Symptom | Next observation |
| --- | --- |
| Missing command | `benmore version --json`, `benmore help`; framework and cloud editions differ |
| Wrong app or URL | `.benmore/app`, `benmore whoami`, `benmore use`, explicit `--env` |
| Sync rejection | `benmore sync-status . --json`; compare local, remote, and saved base |
| Validation rejection | Read the complete filename/key error and relevant `api` topic |
| Upload succeeded, behavior unchanged | Server logs/reload error, deployed manifest, route response |
| HTML loads but UI fails | Real browser console/network and `benmore errors <app>` |
| Flow appears successful but did nothing | Actual response shape, loop input, rows affected, asserted expected count |
| 401/403 or missing rows | Session, token scope, temporary-password state, tenant membership and table access |
| No email/SMS | Provider/host capability, quota or suppression, recipient and guarded flow result |
| Missing assets or routes | `static/` path, compiled TSX import graph, URL and returned content type |

## Malformed configuration and failed reloads

Since framework/platform 2.7.224, malformed core application, backup, hook, flow,
cron, workflow, and encryption settings reject startup or reload instead of being
silently ignored. Read `recovery.configuration_loading` and the relevant topic.
Missing optional files and invalid existing files are distinct cases.

A rejected reload retains the previous handler/configuration/workers. It does not
promise rollback of already committed database migrations or external effects.
Not every auxiliary feature loader has the same checked-loading contract. Do not
"repair" an old inactive job or webhook by activating it without understanding its
schema, side effects, and authorization.

## Slow startup

Inspect process state, logs, health, and ongoing work before restarting. Large DB
checks/backups can outlast an operator's wait deadline. Repeated restarts can reset
progress. Existing extra-column warnings are not authorization to drop columns.

## Database reads and mutations

`benmore sql` / MCP `query_db` are inspection surfaces, with SQLite read-only
enforcement, bounded output, and cancellation. Ordinary app mutations go through
CRUD or authorized flows. SQL restore is a separate owner operation; review its
current restrictions and backup/recovery plan. Do not disable a guard to fit a query.

## Exit codes

General hosted command failures use 1 for transport/server failures, 2 for usage,
4 for authentication/authorization, and 5 for missing/inaccessible apps where that
command implements the shared contract. `sync-status` deliberately differs:
0 clean, 1 drift, 2 conflict, 3 setup/auth/remote error. Read structured command output
and `api(at:"cli-contracts")`; never treat every nonzero result as permission to retry.

## Agent usage

`benmore usage --local --json` is offline. `benmore usage sync` uploads attributed
numeric usage counters; telemetry is enabled by default with disclosure. Use
`benmore telemetry off` or `BENMORE_TELEMETRY=0` according to the user's preference.
Prompts, transcripts, code, tool payloads, provider session IDs, and local paths are
not uploaded. Cache counters are measured provider values, not a cost estimate.
See `api(at:"agent-usage")` for attribution, retention, and account isolation.
