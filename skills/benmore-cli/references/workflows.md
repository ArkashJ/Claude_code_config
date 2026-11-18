# Hosted app workflows

Each sequence lists the command, then what to check before the next step. The
operating contract is `benmore docs harness`; feature shapes come from the
deployed reference: search it, read the topic's index, fetch the key.

## New native app

```bash
benmore login                 # whoami exit 0 afterwards
cd ~/Benmore
benmore new crm               # creates ./crm, never another directory
cd crm
benmore deploy                # first run: creates the app (dev instance) and .benmore/app
benmore open .                # prints the dev URL
```

`deploy` exits 0 when every file was written and the app took the reload; when it
can resolve the app URL it also waits for `/health` and prints that URL. Replace the demo with the
requested product, reuse the shared UI primitives, and verify real journeys.

## Existing app

```bash
benmore apps --json           # find the app: subdomain, dev_url, url
benmore pull <app> <dir>      # writes .benmore/app and .benmore/remote.json
cd <dir>
benmore use                   # shows the pin; pass --env to be explicit
benmore sync-status . --json  # require exit 0 before editing
benmore api <app> '*'
```

A missing dev instance is a provisioning decision (`benmore seed-dev <app>`),
not permission to experiment on production.

## Small change

```bash
benmore api <app> --search "<words>"                          # which key answers the question
benmore api <app> <topic>.<key>                               # read it before writing
benmore push static/views/contacts.tsx static/styles.css --env dev
benmore probe <app> GET /contacts --env dev                   # route answer
benmore errors <app> --env dev                                # application errors (browser and server)
benmore sync-status . --env dev                               # exit 0
```

Skip the explicit push only for edits a verified Claude hook already pushed. For
UI work also use a real browser or `browser_check`: read its tool schema first
(`fill` needs `selector` + `text`; `select` needs `selector` + `value`; both can
change app data). Use an authorized test identity, and check console errors,
failed requests, responsive layout and the visible state after each action.

## Model a record's lifecycle

When a row moves through stages, declare them in `workflows.yaml` instead of
writing a `status` column freely:

```yaml
tickets:
  table: tickets
  field: status
  initial: open
  states: [open, in_progress, resolved, closed]
  transitions:
    open:        { in_progress: { role: agent } }
    in_progress: { resolved: { role: agent, when: "resolution IS NOT NULL" } }
    resolved:    { closed: { role: agent }, open: { role: agent } }
```

`agent` must be a role the app names somewhere else (app.yaml `roles:`, or an
`access:` mode such as `owner_or_role:agent`) and a user must hold it;
otherwise `benmore check` warns on every transition and only an admin can move a
ticket (`api(at:"workflows")` → `transition_roles`).

Creates always start in `initial`; PATCH cannot write `status`; only the listed
moves pass, each audited. Read the current state and allowed moves with
`GET /api/tickets/<id>/transitions` (`bm.workflow('tickets', id).available()`).
Full keys, timeouts and hooks: `api(at:"workflows")`.

## Declared flow permissions

`on.request.permissions: [projects:read, tasks:read]` requires authentication and
all listed scopes before any step runs, scoped administrators included;
discovery and scheduling honor the same gate. It does not replace tenant
predicates, roles or human approval (`api(at:"flows")`).

## Existing frontends

Build Vite, Next static export or another frontend in its own project and deploy
only the browser output under `static/`. Next server components, a Node backend
or a dev server do not become hosted runtimes by copying files. Read
`existing-frontends` and `sdk`.

## Production delivery

```bash
benmore verify . --release    # exit 0 = every check passed; evidence in .benmore/verify/<run>/
benmore status <app>          # in_sync, blocked_destructive (must be empty), prod_last_promoted
benmore doctor <app>          # PASS/WARN per check; resolve every WARN you cannot explain
benmore promote <app> --dry-run   # also reports upgrade_required: the owner's plan has no free live-app slot for a first publish
benmore promote <app>         # a terminal previews and asks y/N; --yes skips; scripts are not asked
benmore status <app>          # in_sync: true afterwards
```

`benmore ship . --promote` runs the same release verification and source check
in one guarded, interactive command; it refuses non-interactive stdin, so do not
fake a terminal. Promotion copies dev code to prod, never data; `publish`
changes testing posture only. If a check blocks, report it with its evidence;
never bypass it with an unrelated `--force`.

## Codex setup

```bash
benmore skill install --agent codex   # or --agent claude | --agent all
benmore skill path --agent codex
```

Installs the same bundle at `~/.agents/skills/benmore-cli`. Use `$benmore-cli`
or let Codex discover it; open Codex in the app directory so its `AGENTS.md`
applies; start a new session if discovery is stale. Without `--agent` the target
is Claude. Installation never changes Codex sandbox settings or grants tool
permissions; Codex pushes explicitly.
