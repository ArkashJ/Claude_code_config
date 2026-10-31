# Hosted app workflows

Use `benmore docs harness` for the full operating contract and the deployed
`benmore api <app> <topic>` response for feature shapes.

## New native app

```bash
benmore login
cd ~/Benmore
benmore new crm
cd crm
benmore deploy
benmore open .
```

`new` creates the directory under the current directory. `deploy` creates a hosted
app on the first run, records `.benmore/app`, and pushes source through validators.
Read the printed app identifier and dev URL. Replace the demo's content with the
requested product, reuse the shared UI primitives, and verify real user journeys.

## Existing app

```bash
benmore apps
benmore pull <app> <directory>
cd <directory>
benmore use
benmore sync-status . --json
benmore api <app> '*'
```

`pull` is guarded against conflicting edits. Read its result before changing files.
Use an explicit `--env dev` on environment-aware commands when development is the
target; a saved `prod` pin otherwise affects subsequent commands. A missing dev
instance is a provisioning decision, not permission to experiment on production.

## Declared flow permissions (unreleased B1)

Use `api(at:"flows")` / `benmore api <app> flows` for `on.request.permissions`.
A declaration such as `[projects:read, tasks:read]` requires authentication and all
scopes before any step runs, including for scoped administrators. Discovery and
scheduling honor the same gate. This is a scope constraint, not a replacement for
tenant predicates, roles, or human approval; it does not enable application MCP.

## Small change

Inspect the relevant `api` topic and existing source. Edit, then explicitly push
changed files unless verified Claude hooks already did it:

```bash
benmore push static/views/contacts.tsx static/styles.css --app <app> --env dev
benmore probe <app> GET /contacts --env dev
benmore errors <app> --env dev
benmore sync-status . --env dev
```

For UI work, also use a real browser or `browser_check`. Inspect its current tool
schema first. `fill` needs `selector` + `text`; `select` needs `selector` + `value`.
Both may change app data. Test authenticated paths only with an authorized test
identity. Check console errors, failed requests, responsive layout, and visible
state after an action; preserve meaningful screenshots/evidence where useful.

## Existing frontends

Build Vite, Next static export, or another frontend in its own project. Deploy only
browser output under the Benmore app's `static/`. Next server components, a Node
backend, or a development server do not become hosted runtimes by copying files.
Read `existing-frontends` and `sdk` for import maps, `@benmore/bm`, clean navigation,
asset paths, and generated declarations.

## Production delivery

Read `verification` and `environments`. `benmore verify . --release` runs the
configured release checks. `benmore ship . --promote` is the guarded promotion
workflow: it requires an interactive terminal, runs fresh release verification,
and checks source identity again before promotion. Inspect `status`/`diff`
and `doctor` findings before promotion. Promotion concerns dev-to-prod source;
`publish` changes testing posture. Neither means arbitrary dev data is copied.

Inspect production routes and the changed user journey after a release. If blocked,
report the failing check and retained evidence; do not bypass it with an unrelated
force flag. Keep source and database recovery decisions separate.

## Codex setup

```bash
benmore skill install --agent codex
benmore skill path --agent codex
```

This installs the same app-building bundle used by Claude at
`~/.agents/skills/benmore-cli`, including its referenced files and Codex UI metadata.
Use `$benmore-cli` in Codex or allow discovery by its description. Open Codex in the
app directory so its `AGENTS.md` applies. If discovery is stale, start a new session.
`CODEX_HOME` identifies a Codex configuration home; user skill discovery remains
under `~/.agents/skills`. Use `--agent all` to install for both supported harnesses.

The legacy default without `--agent` remains Claude. Installation never changes
Codex sandbox settings or grants permission to run tools. Codex pushes explicitly.
