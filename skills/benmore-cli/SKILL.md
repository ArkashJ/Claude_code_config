---
name: benmore-cli
description: Build, edit, debug, verify, or deploy a hosted Benmore app with the benmore CLI. Use for app source, schema, access rules, flows, frontend work, and deployed-app troubleshooting. For changes to the Go framework itself, use the repository's AGENTS.md and benmore-dev skill.
---

# Build and deliver a Benmore app

Benmore turns Prisma + YAML + TSX into a hosted app: SQLite, auth, generated CRUD,
real-time APIs and an embedded TSX compiler, no Node, no `node_modules`, no
localhost dev server. The local folder is source; the hosted dev URL is where the
app runs. Existing frontends are built in their own project and deploy as browser
output (`api(at:"existing-frontends")`).

## Decision rules

1. **Name the target.** App = the `.benmore/app` marker or an explicit `--app`;
   never a folder-name guess. Environment = `--env dev|prod`, else the
   `benmore use` pin, else the app's default (dev when it has one, else prod).
   push, deploy, delete-file, `sql --write` and promote print a `target:` line
   on stderr (the save hook prints it only when its push lands in prod); read it.
   Pass `--env` explicitly to every other changing command.
2. **Look the contract up, never guess it.** YAML keys, columns, response
   envelopes and auth rules come from the reference (search, index, key:
   below) or a working file of the same kind. When an answer names a
   documentation address, fetch it before trying again. A loop over zero rows
   is not success: assert the count.
3. **Reconcile source first.** For an existing app run
   `benmore sync-status . --json`: exit 0 clean, 1 drift, 2 conflict, 3
   setup/auth/remote error. Resolve 1 and 2 deliberately; `--force` is an
   overwrite decision, never a way to get green.
4. **Deliver edits explicitly.** Installed Claude Code hooks fire on every Edit/Write
   matched by their configuration; shell or script edits are not covered, so
   check `benmore hooks status`. Codex, Cursor, and other agents run `benmore push <file>`
   explicitly; an installed skill is guidance, not an upload daemon, installs no
   Codex save hook and relaxes no tool permissions.
5. **Prove the effect.** A push exit code proves the upload, not a healthy app.
   Check the deployed route, logs and a real browser for UI. curl cannot show that
   JavaScript runs or a form saves.
6. **Model state explicitly.** A record that moves through stages (order, ticket,
   approval) gets a `workflows.yaml` entry with `initial`, named states and
   `transitions` (role/`when` guards), not a free `status` string or a pair of
   booleans. The framework then refuses any other move and audits each one
   (`api(at:"workflows")`).
7. **Release means production.** "Deploy", "ship" or "launch" means a URL other
   people use: verify on dev, then `benmore promote <app>` and hand back the
   production URL. If you stop at dev, say so and give the promote command.
   An app's first publish needs a paid plan with a free live-app slot on the
   app owner's account: without one, `promote` exits 1 and prints the reason
   and `→ Upgrade: <url>` (JSON: `upgrade_required: true`; `--dry-run` reports
   it too). Relay that message, and hand back the dev URL as a dev URL.

## Lifecycles you will meet

Each has named states, a command that moves it and a command that shows it.
The full table (jobs, approvals, imports, connector switches, idle sessions,
compliance) is in `benmore docs harness` → "Lifecycles".

| Lifecycle | States | Move with | Observe |
| --- | --- | --- | --- |
| Instance | dev only → dev + prod → dev only again (production removed, data kept); (prod only for old apps) | `benmore deploy` creates dev; `benmore promote <app>`; `benmore seed-dev <app>`; `benmore remove-production <app>` (owner) | `benmore apps --json`: `dev_url`, `url`; `benmore status <app>`: `production` |
| Source | clean / drift / conflict | `push`, `pull`, `delete-file` | `benmore sync-status . --json` exit 0/1/2 (3 = could not check) |
| Release | dev ahead → in sync; first publish refused for the plan (`upgrade_required`) | `benmore promote <app>` (`--dry-run` previews) | `benmore status <app>`: `in_sync`, `blocked_destructive`, `prod_last_promoted` |
| Record in a workflow | `initial` → declared states | `bm.workflow(t,id).transitionTo(s)` / `POST /api/<t>/<id>/transition` | `GET /api/<t>/<id>/transitions` → `current` |

## The loop

```bash
benmore version --json && benmore whoami && benmore use     # edition, account, pin
benmore sync-status . --json                                # exit 0 before editing
benmore api <app> '*'                                       # this app's routes, tables, flows
benmore api <app> --search "<words>"                        # which key answers the question
benmore api <app> <topic>.<key>                             # read that key
# edit the smallest coherent change, then (unless a hook already pushed it):
benmore push <file> [<file>...]                             # exit 0 = written + reloaded
benmore check <app>                                         # validators on the deployed source
benmore probe <app> GET /path; benmore errors <app>         # route answer, application errors
benmore verify .                                            # contract tests + journeys (exit 0 = pass)
benmore sync-status . && benmore sync-status --all          # both exit 0 to finish
```

Keep `static/app.tsx` a thin entry; features in `static/views/`, shared UI in
`static/components/`, logic in `static/lib/`. Use the generated `src/bm.d.ts`
and the `bm` SDK; never hand-edit generated files. Hidden UI is not
authorization: the server's `access:` rules are. Change schema/config and the
frontend together; CRUD writes keep the framework's access, CSRF, validation,
hook, audit and event gates. If a documented command is missing, check
`benmore help` and `benmore version --json` before substituting another. Report the tested URL and environment, what you observed, and
any limitation left. Exact sequences: [workflows](references/workflows.md);
failures: [troubleshooting](references/troubleshooting.md); command map:
[commands](references/commands.md); connectors: [connector](references/connector.md).
With MCP instead of the CLI, use `help(topic:"harness")` and the `api` tool with
the same `at` selectors, and read each tool's input schema before calling it; `api --call`, probes, browser actions and flows run real
operations, so stay inside the user's authorization.

## Look it up: search, index, key

Read the reference one piece at a time (MCP form in brackets):

1. **Search.** `benmore api <app> --search "<words>"` [`api(search:"<words>")`]:
   up to ten addresses, each with a one-line description and a size.
2. **Index.** `benmore api <app> <topic>` [`api(at:"<topic>")`]: a small topic
   whole, a large one as an index of its keys; `benmore api <app> index`
   lists every topic.
3. **Key.** `benmore api <app> <topic>.<key>` [`api(at:"<topic>.<key>")`].
   `--full` [`full:true`] returns a whole large topic (some exceed 100 KB).

Offline, without an app: `benmore docs --search "<words>"`, `benmore docs
<topic>`, `benmore docs <topic>.<key>`, `benmore docs index`.

| Area | Topics |
| --- | --- |
| Task recipes: complete working files | `tasks` (multi-tenant app, owner-only records, public form, inbound webhook, scheduled sync, status workflow) |
| Agent setup and CLI | `harness`, `cli-install`, `cli-auth`, `cli-contracts`, `agent-usage`, `api-reference-cache`, `machine-discovery` |
| Source, environments, recovery | `sync-status`, `environments`, `recovery`, `feature-packs`, `github`, `collaborators`, `compliance` |
| Verification | `verification`, `qa`, `browser_check` |
| Data model and reads | `schema`, `computed`, `aggregates`, `query`, `search`, `count`, `pagination`, `errors` |
| Writes and history | `batch`, `ingest`, `import`, `idempotency`, `concurrency`, `locks`, `versioning`, `audit`, `retention`, `analytics` |
| Identity and access (row access: start at `access.which_topic`) | `auth`, `csrf`, `mfa`, `oauth`, `access`, `scoping`, `rbac`, `permissions`, `act-as`, `auto_memberships`, `encryption`, `csp` |
| Server logic | `flows`, `async-flows`, `hooks`, `workflows`, `cron`, `scheduling`, `compute`, `sql-dynamic`, `parse`, `success_when`, `sign`, `verify`, `webhooks`, `transcribe` |
| Messages and services | `email`, `sms`, `notifications`, `payments`, `dns` |
| Frontend and SDK | `frontend`, `sdk`, `components`, `ssr`, `existing-frontends`, `mobile`, `i18n`, `markdown`, `cache`, `optimistic`, `live-scoped` |
| Real-time and files | `realtime`, `sse`, `websocket`, `webrtc`, `presence`, `uploads`, `signed-urls`, `pdf` |
| App MCP connector | `connector` (offline guide: `benmore docs connector`) |

`benmore api <app> '*'`, `'table:<name>'` and `'POST /api/<table>'` describe
the deployed app itself. `benmore docs changes` lists behavior changes by
release, each with its topic.

## Scope and sensitive operations

- Use the authorization you have; ask only for a missing decision or authority the
  next action needs. A request to inspect an app does not authorize sending
  messages, charging customers, changing collaborators, exposing private data or
  erasing data. Read the exact operation before executing it.
- Never put credentials, raw database exports or private customer records in a
  handoff, log or commit.
- Ask before promoting only when production already has users or data at stake.
  Never present a `-dev` URL as the release.
- These are different actions with different effects: `benmore promote` (dev code
  to prod, never data), `benmore publish` (turns off testing mode: the feedback
  flag and demo gate; there is no banner), `benmore push` (source to one
  instance), `benmore git revert` (source only) and `benmore restore` (database
  only). Read `environments`, `verification` and `recovery` before each, keep the
  selected environment, and verify the effect afterwards.
