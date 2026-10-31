---
name: benmore-cli
description: Build, edit, debug, verify, or deploy a hosted Benmore app with the benmore CLI. Use for app source, schema, access rules, flows, frontend work, and deployed-app troubleshooting. For changes to the Go framework itself, use the repository's AGENTS.md and benmore-dev skill.
---

# Build and deliver a Benmore app

Benmore supplies the app runtime, SQLite database, authentication, generated CRUD,
real-time APIs, and embedded TSX compiler. The local project is a source workspace;
the hosted dev URL is where you run and verify it. Native Benmore apps need no
Node server, node_modules, or separate frontend build step. Existing frontends may
be built in their original project and deployed as browser output.

## Orient before changing anything

1. Read the project's `AGENTS.md` and existing app conventions. Respect the user's
   requested scope and visual direction; preserve working functionality.
2. Run `benmore version --json`, `benmore whoami`, and `benmore use` to establish
   edition, identity, and environment. Use the app's `.benmore/app` marker or an
   explicit deployed app name. Never infer the production target from a folder name.
3. Read `benmore docs harness` for the operating workflow and `benmore docs build`
   for the app model. These are bundled, offline documentation. For a deployed app,
   use `benmore api <app> '<topic>'` for the current server contract.
4. For existing source, run `benmore sync-status . --json`. Reconcile differences
   deliberately before writing; do not force a push or overwrite newer remote work.

Cloud/platform editions have hosted commands; framework edition is self-hosted.
The CLI and server use separate version numbers. If a documented command is absent,
inspect `benmore help` and the installed version before substituting another command.

## Discover the contract

`api(at:"<topic>")` is the canonical reference. With CLI access:

```bash
benmore api <app> '*'
benmore api <app> 'table:contacts'
benmore api <app> 'POST /api/contacts'
benmore api <app> flows
```

With MCP, use `help(topic:"harness")`, `help(topic:"build")`, and `api` with the
same `at` selectors. Inspect the selected tool's actual input schema before calling
it. Descriptions are reads; `api --call`, probes, browser actions, and flows can
execute real operations. Follow the user's authorization for those operations.

Do not guess YAML keys, database columns, response envelopes, or authentication
behavior. Read the app's live API shape and a working definition. An empty loop or
zero-row write is not evidence of success: assert expected rows and inspect effects.

| Task | Canonical topics |
| --- | --- |
| Unreleased: a /static/ file is immutable only at the exact `?v=` served HTML writes for its current bytes; any other request revalidates against a content ETag; poster/srcset/og:image and manifest icons get the version too | `api(at:"frontend")` |
| Unreleased: serve_file signs private audio/video for 4h (2m otherwise), `with.expires_in` up to 6h; bm.signedUrl media default 4h | `api(at:"uploads")` (`signed_link_lifetime`) |
| Unreleased: promote/doctor env warnings read only runtime config, skip `if:`/defaulted reads and name the files | `api(at:"environments")` (`env_parity`) |
| Unreleased: browser_check click/dblclick wait (max 8s) for a visible, enabled, unobscured, still target and fail with the reason (hidden, covered by X, disabled) instead of hanging until `deadline_exceeded` or clicking an overlay | `api(at:"browser_check")` |
| Runtime 2.7.300: feature-pack exact custom routes compose with model renames; arbitrary dynamic URLs require explicit review | `api(at:"feature-packs")` (`route_composition`) |
| Runtime 2.7.299: feature-pack checksums are verified before route/model prefixes or exact maps | `api(at:"feature-packs")` (`payload_integrity`) |
| Runtime 2.7.299: schema checks and drift cleanup preserve generated and retained history tables | `api(at:"versioning")` (`drift_protection`) |
| Runtime 2.7.298: inline GHA signing preserves source order for dependent compute bindings, including anchors and nested steps | `api(at:"sign")` (`compute_order`) |
| Runtime 2.7.296: Prisma uuid() generates v4 values; native creates/imports repair known legacy defaults without rewriting stored IDs; existing raw SQL defaults require explicit migration | `api(at:"scoping")` (`primary_keys.uuid_upgrade`) |
| Bulk-write hook contracts: /batch runs per-row effects, streaming ingest runs before-hooks only, atomic import skips per-row hooks | `api(at:"batch")`, `api(at:"ingest")` (`hooks`), `api(at:"import")` (`hooks`) |
| CLI 0.1.50: deploy and multi-file push send schema/config before command flows, with the reviewed manifest last | `api(at:"connector")` (`manifest_authoring`) |
| Runtime 2.7.291: a compute argument that reads an output of a step the flow reached (no row, skipped by `if:`, key not returned) is null again instead of stopping the flow | `api(at:"compute")` (`missing_arguments`) |
| Runtime 2.7.292: `benmore check` refuses missing durable field-encryption keys before database changes; initialize through app startup/environment first | `api(at:"encryption")` (`validation`) |
| Runtime 2.7.292: encrypted fields and non-sensitive full-text columns coexist across checks and restarts; old FTS update triggers upgrade automatically | `api(at:"search")` (`index_lifecycle`) |
| Runtime 2.7.289: connector registration and authorization drop client-defined scopes (Claude's `claudeai`) instead of refusing the client | `api(at:"connector")` (`connector_grants`) |
| Runtime 2.7.288: a reviewed MCP read tool declares `artifact:` and `artifact.create` exports it as XLSX, a branded HTML report or PDF | `api(at:"connector")` (`connector_grants`) |
| v2.7.290 SDK: cache invalidation and optimistic edits prevent older in-flight reads from replacing newer state | `api(at:"sdk")` (`query_cache`) |
| CLI 0.1.49: automatic types refresh once after the push/deploy batch reload; unverified refresh preserves the file and warns | `api(at:"sdk")` (`types`) |
| v2.7.290: filtered INSERT/SELECT upserts keep their existing outer predicate; WHERE true is a separator fallback | `api(at:"flows")` (`upsert_select`) |
| Runtime 2.7.287 / CLI 0.1.48: guarded soft-delete restore, SDK pagination and accurate mutation/history result types | `api(at:"scoping")`, `api(at:"pagination")`, `api(at:"sdk")` |
| Runtime 2.7.287 / CLI 0.1.48: Prisma scalar validation, typed/null updates and precise optimistic edit timestamps | `api(at:"schema")`, `api(at:"batch")`, `api(at:"concurrency")` |
| Runtime 2.7.281 / CLI 0.1.46: approved MCP writes resume after a hosted restart or release (the boot check no longer forgets the approval) | `api(at:"connector")` (`connector_grants`) |
| Runtime 2.7.280 / CLI 0.1.45: MCP commands draw server-generated tokens (`generated:`, invitation links), sign a removed member out (`run: revoke_user_sessions`), and declare their own reviewed-migration triggers for approved-write enrollment (`app_triggers:`) | `api(at:"connector")` (`connector_grants`), `benmore docs connector` |
| Unreleased: `benmore_today('America/New_York')` in SQL steps returns the server's current calendar date for an explicit IANA zone and refuses blank, `Local`, or invalid zones | `api(at:"flows")` (`timezone_dates`) |
| Runtime 2.7.279 / CLI 0.1.44: approved MCP commands no longer re-scan every enrolled table per step (prepare/commit stay well inside the 30s deadline on large apps); `benmore login --device` works without a terminal | `api(at:"connector")` |
| Runtime 2.7.278 / CLI 0.1.43: pinned file reads, atomic grant cleanup, exact tenant event IDs, singleton detection, WebSocket cleanup, compute arguments, isolated parallel branches, HTTP error responses, response reachability and saved-environment notices | `api(at:"uploads")`, `api(at:"permissions")`, `api(at:"sse")`, `api(at:"scoping")`, `api(at:"websocket")`, `api(at:"compute")`, `api(at:"flows")`, `api(at:"environments")` |
| Unreleased: disable framework HTTP PDF and user-data exports with `features.exports: false` | `api(at:"pdf")` (`availability`) |
| Runtime 2.7.277 / CLI 0.1.42: MCP writes without per-write approval (`approval: grant` + `--auto-approve` + consent), batch approval, writes survive restarts, capability-scope commands, grants API, nullable/optional args, prepare refusals, runtime-only execution digest | `api(at:"connector")` (`connector_grants`) |
| Runtime 2.7.276 / CLI 0.1.41: MCP connectors end to end (write-tool consent, hosted origin without seo.url, `table_scopes: access`, `serve --mcp-local`) | `api(at:"connector")` (`connector_grants`), `api(at:"rbac")` |
| Unreleased `table_scopes: access`: declaring capability roles: (e.g. for MCP tool permissions) no longer 403s every auto-CRUD call; access: decides table access | `api(at:"rbac")` |
| Unreleased local connector test: `benmore serve <app> --mcp-local [--mcp-writes]` exposes /api/_mcp with OAuth on localhost before deploy | `api(at:"connector")` (`connector_grants`) |
| Unreleased immutable file originals/blocks: ingest returns a processing ID; verify rechecks current access against retained snapshots; every restore revokes delegated credentials | `api(at:"connector")` (`connector_grants`) |
| Unreleased per-app router request budgets: one app's traffic no longer spends another's or the CLI's; every 429 carries Retry-After and the CLI retries it | `environments` |
| MCP HTTP-flow prerequisite: opt in to selected integer 4xx responses with `with.handled_statuses: [400]`; 5xx, transport/read and over-1-MiB responses remain errors | `flows` |
| MCP source CLI: inspect, generate disabled OpenAPI candidates, check and explicit review from app files without a framework checkout; hosted authority and real-client acceptance remain separate gates | `benmore docs connector`, `api(at:"connector")` (`connector_grants`) |
| Unreleased private MCP file tools bind private upload references to a readable table row; bounded CSV/XLSX/XLSM results keep cell coordinates, `verify` checks `VerifySpan`, and PDF uses bounded Poppler layout plus Tesseract OCR when fixed binaries and English data exist | `api(at:"connector")` (`connector_grants`) |
| Unreleased native MCP document parsing adds bounded DOCX paragraphs/tables and PPTX slides in presentation order; it extracts text only and refuses unsupported tracked or alternate content | `api(at:"connector")` (`connector_grants`) |
| Unreleased MCP PDF extraction caps documents at 200 pages, 40 MP/page, 60s/512 MiB per child page, 512 MiB temp and 10 minutes total; encrypted PDFs fail closed; child processes require a proven seccomp socket-deny probe and fail closed if host policy blocks it | `api(at:"connector")` (`connector_grants`) |
| MCP SQL metadata/identifier matching and captured schema and user migration inputs preserve tenant guards and migration semantics; validate against the host's actual schema and migration state | `api(at:"schema")` (`sql_metadata`) |
| Legacy archive deployment validates uploads, preserves failed reservations and verifies activation (v2.7.226) | `api(at:"recovery")` (`archive_deploy`) |
| Schema, CRUD, query, imports | `schema`, `query`, `import`, `search` |
| Login, temporary passwords, tenancy, permissions | `auth`, `access`, `scoping`, `rbac` |
| Backend logic and external services | `flows`, `hooks`, `cron`, `compute`, `sign`, `verify` |
| Frontend, SDK, components, uploads | `frontend`, `sdk`, `components`, `uploads` |
| Source/environment safety and recovery | `sync-status`, `environments`, `recovery` |
| Browser checks and delivery evidence | `browser_check`, `verification` |
| Agent setup, authentication, usage | `harness`, `cli-auth`, `agent-usage` |

## Edit, ship, verify

Keep `static/app.tsx` as the entry point. Put feature code in `static/views/`, shared
UI in `static/components/`, and reusable logic in `static/lib/`. Preserve an existing
app's organization when it already serves that purpose. Use generated `src/bm.d.ts`
and the `bm` SDK; never edit generated declarations or treat hidden UI as authorization.

- Change the authoritative schema/config and the frontend together. CRUD mutations
  must retain the framework's access, CSRF, validation, hooks, audit, and event gates.
- Installed Claude Code hooks fire on every Edit/Write matched by their configuration.
  Shell/script edits are not covered by that matcher. Check `benmore hooks status`
  when relying on hooks and inspect their reported errors.
- Codex, Cursor, and other agents run `benmore push <file>` explicitly. Benmore does
  not install a Codex edit hook. An installed skill is guidance, not an upload daemon.
- Push all changed dependencies, check command exit status, and verify the actual
  deployed route. A successful file upload alone does not prove a healthy reload.
- Use `benmore verify .` when the app has a verification contract. Inspect logs,
  API results, and real browser behavior for the changed path. A curl response cannot
  establish that JavaScript executes, a form saves, or the layout works.
- Finish with a clean `benmore sync-status .` and `benmore sync-status --all`.
  Report unrelated workspace drift without changing unrelated apps to clear it.
  Report the tested URL/environment, observed outcome, and any unresolved limitation.

For exact commands and task-specific sequences, read [workflows](references/workflows.md).
For failure diagnosis and safe recovery, read [troubleshooting](references/troubleshooting.md).
For discovery and command families, read [command map](references/commands.md).

## Recent

- Unreleased: a restart that changes nothing no longer copies the database or runs integrity/quick checks (snapshots come from schema changes, new releases and storage-config changes; 3 are kept), and auto-recovery restores only snapshots under 24h old, otherwise the start fails. See `api(at:"recovery")` (`startup_checks`, `auto_recovery`).
- Unreleased: a benmore.ai account can be deleted from the account page once it owns no app and has no subscription that can still charge; deletion ends its CLI token and MCP connections. See `api(at:"cli-auth")` (`account_deletion`).
- Unreleased: CLI fixes: `benmore pull <app>` inside that app's workspace refreshes it instead of nesting a copy; `benmore restart` exits 1 when the app never answers healthy; `benmore status` `prod_last_promoted` is the latest promote; a 401 for an expired or revoked token no longer suggests `read: anon`. See `api(at:"sync-status")` (`pull_default_dir`), `api(at:"recovery")` (`restart_and_reload`), `api(at:"environments")` (`status_promoted`).
- Unreleased: frontend SDK matches the runtime: `bm.flows.saveQuote` reaches flows/save-quote.yaml (kebab spelling still typed), `bm.table().list()` sends `orderBy`/`include`/`fields`/`page`/`per_page` and warns on other keys, `bm.workflow()` types match the wire shapes, the `Role` type lists tenant roles, and `bm.auth.me().group_id` is the current tenant. On the media CDN a `serve_file` download streams with its filename and pages may `fetch()` the CDN. See `api(at:"frontend")` (`sdk_surface`), `api(at:"flows")` (`serving_private_files`), `api(at:"csp")` (`media_cdn`).
- Unreleased: SQL binds of `${{ params.n > 3 }}` or `${{ x | default:'0' }}` booleans are 1/0; omitted flow inputs take their `default:`; cron writes that `RETURNING <tenant column>` refresh that tenant's live views; cron `sql:` works in the jobs list and an unknown `flow:` is refused; on_transition `{{user_id}}` is the caller, the owner is `{{old_user_id}}`. See `api(at:"flows")` (`sql_boolean_params`, `inputs_block`, `realtime_events`), `api(at:"cron")`, `api(at:"workflows")` (`hook_context`).
- Unreleased: generated framework tests (`benmore test --framework`, `benmore verify`) assert the refusal an access rule or role scope declares instead of expecting success, create required parent rows first, use unique values per test, and report a journey they cannot build as SKIP with the reason. See `api(at:"verification")` (`generated_tests`).
- Unreleased: `benmore import <app> <table> <file> --owner EMAIL` assigns every imported row of a `user_id` table to that user of the app; without it, a table whose `user_id` is required is refused before upload instead of failing row 1. See `api(at:"import")` (`owner`).
- Unreleased: `benmore restore` keeps a database and its ENCRYPTION_KEY together: a backup the current key cannot decrypt is refused before anything stops, and on dev a backup from before a `refresh-dev --data-only` is installed with its preserved key. See `api(at:"recovery")` (`restore_encryption_key`).
- Unreleased: PATCH names the columns it never writes (a workflow state column, user_id, the tenant key, timestamps) in X-Stripped-Fields and `stripped_fields`, with a `hint` pointing state changes at `/transition`; it answered 200 with the state silently unchanged. See `api(at:"workflows")`.
- Unreleased: /api error bodies are JSON (auto-CRUD refusals and server errors, flow input/gate refusals, and a failed flow, whose text line moved into `message`); a create, update or delete refused on a table you may read answers 403 instead of the no-route 404. See `api(at:"errors")` and `api(at:"access")` (`behavior_notes`).
- Unreleased: the scaffold links `static/favicon.svg` (a missing /favicon.ico failed every journey) and `benmore verify` names why a journey failed; `benmore doctor` says when prod was never promoted. See `api(at:"verification")` (`failure_contract`).
- Unreleased: `api(at:"access")` points tiered owner-or-manager reads at `owner_or_role:` (it said they needed a secure-read flow), and `api(at:"environments")` no longer says push cannot reach prod (`push --env prod` is the hotfix path).
- Unreleased: the page CSP allows unpkg, jsDelivr, esm.sh or Skypack only when the app's own files name that host; an app importing sdui gets just the Leaflet files its Map loads (now SRI-pinned). A CDN URL built from data or env needs `csp: script_src`. Embedded Mermaid is 11.17.2. See `api(at:"csp")` (`script_cdns`).
- CLI: hosted commands refuse unknown flags with a did-you-mean hint (`probe --data` was ignored) and treat `--help` anywhere as help; promoted migrations are reused instead of renumbered on prod, and sync-status lists leftover instance-generated ones as `instance_migration`. See `api(at:"cli-contracts")`, `api(at:"environments")` (`promoted_migrations`).
- Unreleased: `benmore restore` refuses a snapshot the app's current code would drop again at start (a removed model, or a drop in an unapplied migration file) and names it; `--force` overrides. See `api(at:"recovery")` (`restore_code_mismatch`).
- Unreleased: promote refuses, without force, a copied migration file that would drop a prod table or column holding data, and answers ok:false (CLI exit 1) when prod does not come back healthy. See `api(at:"environments")` (`promote_safety`).
- Unreleased: a schema.prisma push that removes a model whose table holds rows is refused unless `--allow-table-drop` / `allow_table_drop`. See `api(at:"schema")` (`removed_models`).
- Unreleased: schema.prisma changes the live database will not make (a type, nullability or default change, a removed field) are named in the push answer (`schema_not_applied`), `benmore check` and promote's preview; promote no longer demands force for them, a file-less change no longer double-numbers prod's migrations, and failed generated migrations are not sync drift. See `api(at:"schema")` (`unapplied_changes`), `api(at:"environments")` (`promote_force`, `fileless_changes`), `api(at:"sync-status")` (`failed_migrations`).
- Unreleased: adding `@default(now())`, `@updatedAt` or a required `DateTime` to a table with rows no longer fails the migration (it took dev down and crash-looped prod on promote). See `api(at:"schema")` (`time_defaults`).
- Unreleased: `/static` refuses every file a `run: compute` module imports, not just the module itself. See `api(at:"compute")` (`server_only_sources`).
- Unreleased: a flow on a framework-registered route (per-table `/share`, `/permissions`, `/versions`, `/transition`, `/health`, ...) is refused at push with a free path, and a deployed one is skipped instead of crashing the app. See `api(at:"flows")` (`route_collisions`).
- Unreleased: `api(at:"*")` lists auto-CRUD routes whose access op is `off` under `crud_access_off`, not as callable; OpenAPI and docs drop them. See `api(at:"access")` (`route_discovery`).
- Unreleased: a flow or auto-CRUD request body over its limit (a flow's JSON body or `parse: body`: 1 MiB; otherwise the app's MAX_REQUEST_BODY_BYTES, default 10 MiB) answers 413 with the limit; it used to run with every field empty. See `api(at:"flows")` (`request_body`).
- Unreleased: a failed flow step's 500 carries a fixed `reason`; the step's own error is in the answer only for a signed-in app admin, and always on the `FLOW ERROR` journal line with the request id. See `api(at:"flows")` (`step_failures`).
- Unreleased: `${{ }}` values take the `if:` expression grammar (`${{ params.id && 'yes' || 'no' }}` was always 'no'); an expression that doesn't parse is refused at push. See `api(at:"flows")` (`value_expressions`).
- Unreleased: `benmore tail` / `tail_logs` say when the answer is truncated, and `--grep` searches the last 1000 journal lines instead of the last `--lines`. See `api(at:"errors")` (`journal_tail`).
- Unreleased: in `run: compute` a backtracking regex that hits its 5-second match limit throws a RangeError instead of reporting no match; uncaught, the step error omits the matched text. See `api(at:"compute")`.

- Runtime 2.7.305: GHA `on.schedule.transaction: true` applies the flow transaction to scheduled cron runs. See `api(at:"flows")` (`scheduled_transaction`).

- Runtime 2.7.305: MCP command SQL after-hooks may use the captured tool name as `{{_mcp_command_name}}`; it stays out of before-hooks, conditions, jobs and row output. See `api(at:"connector")` (`command_hook_context`).

- Runtime 2.7.304: list filters/sorts an encrypted column cannot answer (no blind index, range/LIKE, sort) answer 400 instead of empty or unfiltered rows. See `api(at:"encryption")` (`blind_index`).
- Runtime 2.7.304: an `if:` reading a `steps.<id>.outputs.<name>` column the SQL step does not return is refused at push (it compared as empty, so the guard never fired). See `api(at:"flows")` (`step_output_refs`).
- Runtime 2.7.304 / CLI 0.1.55: pushing encrypted fields restarts the app with a pinned key (the hot reload refused them, so the config never went live); a hosted app whose process wrote an owner-only `env.yaml` key can be restarted again; `versioned:`/`encrypted.yaml` tables the app does not have are refused at push (the next restart failed); `benmore deploy` fails when the app does not come back healthy. See `api(at:"encryption")` (`hosted_restart`).
- Runtime 2.7.304: `/static` no longer serves TS/JSX source or `run: compute` modules; flow SQL never returns `_benmore_users` credential columns; `sql_dynamic` with `params.X` is refused at push; denied tables 404 like unknown paths. See `api(at:"flows")` (`user_credential_columns`).

- Runtime 2.7.304: data-event flows bind row columns as `:name` (they bound NULL); `${{ }}` inside a quoted SQL string is refused at push. See `api(at:"flows")` (`event_row_params`).

- Runtime 2.7.304: numbers of a million or more reach flow SQL and templates in full (`1234567`, not `1.234567e+06`, which `CAST(... AS INTEGER)` read as 1). See `api(at:"flows")` (`number_text`).
- Runtime 2.7.304: `run: api` `json: ${{ steps.x.outputs }}` sends the referenced object instead of an empty body; other `json:` text is refused at push. See `api(at:"flows")` (`api_json_reference`).
- Runtime 2.7.304: pushes and `benmore check` refuse a static/ or src/ script that does not parse (file:line:column). See `api(at:"compute")` (`write_time_parse`).
- Runtime 2.7.304: `benmore env set` returns after the app restarted with the new value; unchanged instances (prod for a dev-only key) are not restarted. See `api(at:"recovery")` (`environment_materialization`).
- Runtime 2.7.304: Cloudflare hides 502/504 bodies; checks warn on flow 502/504 responses, framework upstream errors answer 503, and router restarts hold requests. See `api(at:"flows")` (`edge_error_status`).
- Runtime 2.7.304: unversioned static/ URLs (images in TSX, CSS url(), icons) revalidate instead of caching for a year; replaced logos show without `?v=2`. See `api(at:"frontend")`.
- Runtime 2.7.304: `for_each` iterates lists of strings/numbers (they were skipped: zero iterations, 200). See `api(at:"flows")` (`loop_sources`).
- Runtime 2.7.304: flows accept `auth: optional` (signed-in callers get `${{ user.* }}`, anonymous callers null) - one route for both. See `api(at:"flows")` (`auth_optional`).
- Runtime 2.7.304: checks warn on hooks.yaml `{{name}}`/`:name` references that are not columns of the hooked table.
- Runtime 2.7.304: `<meta name="bm-cookie-banner" content="off">` drops the consent banner on one page (embeds). See `api(at:"analytics")` (`banner_opt_out`).
- Runtime 2.7.304: auto-CRUD names unknown body fields in `X-Ignored-Fields` and unapplied list filters in `X-Ignored-Params`.
- CLI 0.1.55: `benmore help <cmd>` shows that command; `benmore logs -n N` prints recent lines, `-f` streams; pushes stop repeating app-wide warnings (see `benmore check`).
- CLI 0.1.55: a schema push copies the server-generated `migrations/*.sql` back into the workspace (new files only, hash-checked).

- Runtime 2.7.303: constrained native file bindings validate without optional encryption configuration; encrypted membership columns remain refused. See `api(at:"connector")` (`connector_grants`).

- Runtime 2.7.303: data-event transaction panics release their database connection after rollback. See `api(at:"flows")` (`event_transaction_cleanup`).
- Runtime 2.7.303: platform upload-retention sweeps keep selection and deletion on their captured database. See `api(at:"recovery")` (`worker_generations`).

- Runtime 2.7.303: PDF jobs isolate Chrome HOME/XDG caches, select disposable credential stores and report cleanup failures; host startup and old residue remain separate. See `api(at:"pdf")` (`runtime_cleanup`).

- CLI 0.1.54: confirmed user deletion accepts an explicit environment; invalid or duplicate flags refuse before dispatch. See `api(at:"auth")` (`cli_user_provisioning`).

- Runtime 2.7.303: source history separates successful Git warnings from parsed paths; unreadable-directory cleanup remains separate. See `api(at:"github")` (`git_diagnostics`).

- Runtime 2.7.303: test diagnostics retain published root pages and partials until validated reload. See `api(at:"frontend")` (`root_page_reload`).
- Runtime 2.7.303: route registration and graph extraction preserve published page definitions and use matching effective gates. See `api(at:"frontend")` (`root_page_reload`).

- Runtime 2.7.303: reviewed command SQL admits `json_array_length` and `json_group_array`; existing authorization and rollback apply. See `api(at:"connector")` (`connector_grants`).

- Runtime 2.7.303: use `handler.file_column` for exact native MCP document-version reads; confirm the runtime release first. See `api(at:"connector")` (`connector_grants`).

- Runtime 2.7.303: file handlers may constrain one live canonical membership row and expose bounded metadata through `status` for known successful snapshot-backed processing results; no parsed content is returned. See `api(at:"connector")` (`connector_grants`).

- Runtime 2.7.303: opt into `handler.upload_tenant: current` to bind private-upload provenance to the selected workspace and source-row tenant. See `api(at:"connector")` (`connector_grants`).

- Runtime 2.7.300: import launch synchronizes its cancellation generation with reload; cancellation still rolls back pending rows. See `api(at:"import")` (`reload_generation`).

- Runtime 2.7.300: YAML writes and checks reject over-budget content before repeated validation. See `api(at:"verification")` (`yaml_resource_limits`).

- Runtime 2.7.300: maintenance workers and lazy connector operation limiters keep their original stop generation across reloads. See `api(at:"recovery")` (`worker_generations`).

- Runtime 2.7.300: backup file uploads hash and stream without an object-sized buffer. See `api(at:"recovery")` (`backup_upload_memory`) for capacity limits.

- Runtime 2.7.300: scheduled snapshots include WAL-only writes and refresh idle production apps. See `api(at:"recovery")` (`scheduled_snapshots`).

- Runtime 2.7.300: platform PITR captures committed WAL boundaries with SQLite coordination. See `api(at:"recovery")` (`wal_committed_capture`) for outage and rollout limits.

- Runtime 2.7.300: durable jobs preserve project ordering across overlapping reload workers while unrelated jobs remain eligible. See `api(at:"async-flows")` (`ordering`).
- Runtime 2.7.300: backup listings require complete S3 inventories; the dashboard lists bounded ordinary snapshots. See `api(at:"recovery")` (`backup_inventory`).
- Runtime 2.7.300: active production apps retain their newest ordinary backup candidate; removed-app expiry requires a fresh route inventory. See `api(at:"recovery")` (`retention_safety`).
- Runtime 2.7.300: PITR base upload readiness gates WAL publication and retries while idle. See `api(at:"recovery")` (`wal_base_readiness`).

- Runtime 2.7.300: full inbox retention uses newest IDs to resolve same-second timestamps. See `api(at:"notifications")` (`retention`).

- Runtime 2.7.300: feature-pack model/table maps apply once per original identifier and update references in unchanged models. See `api(at:"feature-packs")` (`model_maps`).

- Runtime 2.7.300 sharing dialog load errors: failed permission listing shows an error and Retry, clears stale controls, and never claims the row is unshared. See `api(at:"permissions")` (`share_dialog_errors`).

- Runtime 2.7.300: personal inbox badges and live hints honor delegated credential scopes. See `api(at:"notifications")` (`credentials`).
- Runtime 2.7.300: ordinary-app hot reloads refresh root page routes, access gates, partials and auth paths; rejected candidates retain the active page set. See `api(at:"frontend")` (`root_page_reload`) and `api(at:"recovery")` (`page_reload`).
- Runtime 2.7.300: frontmatter rendering preserves shared page metadata during concurrent requests and context-graph reads. See `api(at:"frontend")` (`ssr_page_gates`).
- Runtime 2.7.300: the standard sharing dialog displays and revokes the recipient from the native permission list. See `api(at:"permissions")` (`share_dialog`).

- Sharing grants keep edit and delete separate; permission lists also require current sharing authority. See `api(at:"permissions")` (`grant_actions`, `sharing_authority`).

- Runtime 2.7.300: local MCP review accepts omitted optional arrays and seals the YAML it writes; explicit null remains invalid. See `api(at:"connector")` (`review_serialization`).

- Runtime 2.7.300: new record shares resolve one existing account's stored email spelling and refuse legacy case ambiguity; future recipients and historical grants keep their exact-spelling limits. See `api(at:"permissions")` (`recipient_resolution`).
- Runtime 2.7.300: record-share expiry validation rejects malformed dates before changing grants or audit; existing SQLite/RFC3339 formats, valid past dates and no-expiry behavior remain supported. See `api(at:"permissions")` (`share_expiry`).
- Runtime 2.7.300: `bm.live.scoped` serializes callback promises and queues one trailing refresh; see `api(at:"live-scoped")` for ordering and teardown limits.

- Runtime 2.7.300: schema write/check refuses ignored `@relation` onDelete/onUpdate arguments, including reverse lists; existing foreign keys keep their behavior. See `api(at:"schema")` (`referential_actions`).
- Runtime 2.7.300: locale requests and HTML/raw-page dictionaries use the published app generation; `bm.t` treats variable names and values literally. See `api(at:"i18n")`.
- Runtime 2.7.300: stored SQL hooks recognize commented and quoted write targets so automatic enrollment refreshes live views after the job runs. Existing reader gates remain. See `api(at:"hooks")` (`sql_refresh`) and `api(at:"auto_memberships")` (`verifying`).
- Runtime 2.7.300: generated types and per-caller flow metadata share private origin cache headers; CDN bypass and removal of previously cached objects remain deployment requirements. See `api(at:"frontend")` (`private_metadata_cache`).

- Runtime 2.7.300: framework admin rows, command hook snapshots and transfer digests use trusted source columns; workspace identities stay literal. Older affected transfer previews require reprepare. See `api(at:"encryption")` (`framework_read_source`).

- Runtime 2.7.299: account/system metadata remains literal even with encrypted-envelope prefixes; webhook secret hints decode once. See `api(at:"encryption")` (`metadata_literals`) for the bounded coverage and remaining SQL limits.

- Runtime 2.7.299: canonical table reads preserve ordinary ciphertext-looking text and decrypt only configured source columns; generic SQL and other metadata paths retain their separate contract. See `api(at:"encryption")` (`native_read_source`).

- Runtime 2.7.299: configured encrypted fields seal native ciphertext-looking inputs as literal text, preserving blind indexes and mutation gates. See `api(at:"encryption")` (`ciphertext_input`).

- Runtime 2.7.300: read-audit history validates `limit` (1–1000, default 100) before flushing or querying audit history. See `api(at:"audit")` (`read_history`).

- Unreleased: flow email supports CC/BCC with shared recipient limits and envelope-only BCC; native one-click unsubscribe is explicit opt-in with exactly one recipient and a valid HTTPS POST target. See `api(at:"email")` and `api(at:"flows")`.

- Runtime 2.7.298: existing-table Prisma relations install physical constraints; see `api(at:"schema")` (`relation_migrations`) for preserving migrations and read-only legacy-drift upgrade checks.


- Runtime 2.7.298: query aggregate aliases remain derived values; source authorization and ordinary projection masks remain. See `api(at:"query")` (`aggregate_outputs`).

- Runtime 2.7.298: declarative queries refuse unsupported operations on encrypted ciphertext instead of returning misleading totals or matches. See `api(at:"query")` (`encrypted_operations`).

- Runtime 2.7.297: full-text search supports UUID/text record ids and repairs earlier indexes atomically. See `api(at:"search")` (`record_ids`).
- Runtime 2.7.297: native query lists and summaries refresh on tableless private/member-of live hints. See `api(at:"sdk")` (`query_live`).
- Runtime 2.7.297: native create responses preserve encrypted numeric types immediately, matching canonical reads. See `api(at:"encryption")` (`create_readback`).
- Runtime 2.7.297: MFA enrollment/removal share sign-in's one-use TOTP boundary, with atomic proof consumption and rollback. See `api(at:"mfa")` (`code_replay`).

- Runtime 2.7.296: notification subscriptions discard old-session pending responses and restart their live cursor after native auth/scope changes. See `api(at:"notifications")` (`session_boundary`).
- Runtime 2.7.296: whole boolean references in SQL `with.params` use SQLite 1/0; literal strings and explicit JSON text stay text. See `api(at:"flows")` (`sql_boolean_params`).
- Runtime 2.7.296: schema writes and checks refuse unsupported/undefined field types and scalar lists instead of silently omitting columns. See `api(at:"schema")` (`field_types`).
- Runtime 2.7.296: workflow transitions and timeouts advance precise monotonic edit versions; see `api(at:"workflows")` (`transition_writes`).

- Runtime 2.7.295: native SDK session and tenant changes clear private query state and rebind live subscriptions; custom auth flows finish with `bm.auth.refreshMe()`. See `api(at:"sdk")` (`session_cache`).

- Runtime 2.7.295: optimistic query rollback preserves newer cache publications and pending reads, including overlapping failed edits. See `api(at:"sdk")` (`query_cache`).
- Runtime 2.7.295: create-time cross-field validators see omitted schema defaults, evaluated once for validation and persistence across single/bulk/transaction/ingest/bootstrap writes; explicit null and submitted-field tracking stay distinct. See `api(at:"schema")` (`cross_field_validators`).
- Runtime 2.7.295: generated record-sharing list types use the actual `grantee_id` and grant metadata, with nullable expiry. See `api(at:"permissions")` (`list_shape`).
- Runtime 2.7.295: strict JSON numeric inputs remain native JavaScript numbers in compute, including nested arrays/objects. See `api(at:"compute")` (`json_numbers`).
- Runtime 2.7.295: `for_each` reads arrays nested in compute results and request objects. See `api(at:"flows")` (`loop_sources`).
- Runtime 2.7.295: transactional HTTP and worker flows roll back before independent `on_error` writes, avoiding lost failure journals. See `api(at:"flows")` (`error_handler_response`).

- Runtime 2.7.294: SQLite update constraint refusals return 400 across PATCH, batch and transactions while preserving rollback and production redaction. See `api(at:"errors")` (`update_constraints`).
- Runtime 2.7.294: workflows, approved commands and SSR membership roles honor `groups.role_field`; stale legacy roles cannot override it. See `api(at:"workflows")` (`transition_roles`).

- CLI 0.1.51 / runtime 2.7.293: generated workflow tests choose deterministic unconditional transitions and separate role identities; conditional and tenant-specific fixtures need authored tests. See `api(at:"workflows")` (`generated_tests`).

- Runtime 2.7.293: hosted restart prepares durable field-encryption keys before boot; restore/refresh keep their prepared environment. See `api(at:"encryption")` (`hosted_restart`).

- Runtime 2.7.293: generated history keeps precise boundaries and Prisma maintenance preserves canonical update tokens; retained historical gaps are not invented. See `api(at:"versioning")` (`precise_intervals`).

- CLI 0.1.48 / runtime 2.7.287: hosted CLI `new` supports its first deploy without a premature connector review; live notification callbacks drain every page of a burst. See `api(at:"connector")` and `api(at:"notifications")`.

- GHA `run: enqueue` and legacy active-job `unique_key` use the native durable queue. See `api(at:"flows")` → `enqueue`.

- App-private PDF inspection and signature rendering have fixed 90-second and 120-second end-to-end deadlines; a started artifact save can take up to 30 seconds. The source context remains untouched. See `api(at:"flows")`.
- Account self-service can be closed with `features.account_settings: false` while identity, password/passkey login, logout, login MFA and required password replacement remain; email changes recheck `auth.domain` / `auth.allow_emails` at request and confirmation. See `api(at:"auth")` (`account_settings`).

Read the named topic when the change matters to the task; this is an index, not a
second copy of the runtime recipes.

| Change | Reference |
| --- | --- |
| Runtime 2.7.292: pending MFA/OTP sign-ins are one-use, credential-bound and commit factor/session changes together | `api(at:"auth")` (`signin_steps`), `api(at:"mfa")` |
| Runtime 2.7.292: tenant-root role/permission policies use the effective tenant despite founder user_id; old ownership cannot cross tenants, and admin act-as stays bounded | `api(at:"access")` (`tenant_root_role_scope`) |
| Runtime 2.7.284: hosted API discovery advertises installed full-text search in CLI and MCP router contexts | `api(at:"search")` |
| Runtime 2.7.283 / CLI 0.1.47: deployed relationships and encrypted-field storage refresh correctly; SDK sharing revoke, row status responses, versioning YAML and mapped full-text search are repaired | `api(at:"permissions")`, `api(at:"encryption")`, `api(at:"versioning")`, `api(at:"search")`, `api(at:"sdk")` |
| Unreleased CLI user creation: `--password-stdin` reads a bounded password outside argv; the distinct create-only platform tool refuses existing accounts and is unknown-tool safe on older servers; `users list --all --env dev` includes deactivated accounts | `api(at:"auth")` (`cli_user_provisioning`) |
| Unreleased: journeys can declare exact same-origin 4xx denials by method, path, and status; every expected denial must occur, and unrelated failures still fail | `api(at:"verification")` |
| Unreleased: journeys default to preflighting every action target; use `sequential_actions: true` only when a prior action renders or replaces a later control | `api(at:"verification")` |
| Unreleased: `csp.frame_ancestors: "'none'"` denies all framing and mixed `'none'` lists are rejected; `features.analytics: false` prevents intermediary script injection while keeping HTML no-store | `api(at:"csp")`, `api(at:"analytics")` |
| Unreleased MCP connector pages: one branded layout (app name, favicon, `theme:`/`brand:`), `groups.label` workspace names + single-workspace auto-skip, styled identical "can't be shown" errors, review/batch approve fixed in browsers (`Origin: null`) | `api(at:"connector")` (`connector_grants`) |
| Unreleased MCP auto-approval: a command declared `approval: grant` applies in one call (no browser trip) when the owner ran `benmore mcp enable <app> --writes --auto-approve` and the user ticked it at consent; other writes get `batch_review_url` to approve a connection's pending changes together | `api(at:"connector")` |
| Unreleased generic upload opt-out: `features.uploads: false` closes both HTTP upload endpoints before parsing | `api(at:"uploads")` (`feature_gate`) |
| Unreleased MCP review text: command tools declare `title`, `review_summary`, `labels`, `review_changes` in mcp.yaml; review pages show labelled before to after rows; prepared calls return `approval_reason` | `api(at:"connector")` → `connector_grants` |
| Unreleased: apps list and revoke the signed-in user's connected AI clients with `GET /api/_mcp/grants` and `DELETE /api/_mcp/grants/{id}` | `api(at:"connector")` → `connector_grants` |
| Runtime 2.7.275 / CLI 0.1.40: private upload ownership, feature export path checks, SSE reconnect/refresh, NULL and aggregate queries, and per-row loop values | `api(at:"uploads")`, `api(at:"feature-packs")`, `api(at:"sse")`, `api(at:"query")`, `api(at:"flows")` |
| Runtime 2.7.274 / CLI 0.1.39: encrypted history and schema repair, atomic password/workflow writes, safe migrations/backups/retention, related-row access, async tenant broadcasts, accurate pagination and source synchronization | `api(at:"encryption")`, `api(at:"versioning")`, `api(at:"auth")`, `api(at:"workflows")`, `api(at:"recovery")`, `api(at:"scoping")`, `api(at:"async-flows")`, `api(at:"flows")`, `api(at:"environments")` |
| Unreleased encrypted writes: `benmore_encrypt_plaintext(value, table, column)` seals prefix-looking plaintext; trigger replacement is transactional and a failed install refuses app load while preserving prior triggers | `api(at:"encryption")` |
| Unreleased: password recovery invalidates prior MFA enrollment grants; encrypted-field unmasking and filters honor the row's tenant | `api(at:"mfa")`, `api(at:"encryption")` |
| Unreleased: historical reads normalize timestamp offsets, interrupted ingestion reports committed counts, bulk booleans use 1/0, and malformed queued input fails before execution | `api(at:"versioning")`, `api(at:"ingest")`, `api(at:"batch")`, `api(at:"async-flows")` |
| Unreleased: signed-in flow responses use private/no-store caching; api/webhook missing inputs stop before delivery, webhooks require 2xx, and respond arrays resolve nested values | `api(at:"flows")` (`respond_headers`) |
| Unreleased: `run: parse` with `source: headers` exposes canonical inbound header names and all values as arrays, separate from the body and marked as request input | `api(at:"flows")` (`parse`) |
| Unreleased: `bm.api` accepts custom headers and AbortSignal options while retaining automatic CSRF and same-origin credentials | `api(at:"sdk")` (`request_options`) |
| Unreleased: opt-in `on.request.strict_json: true` caps requests at 32 KiB and rejects duplicate JSON keys, malformed/trailing JSON, non-object bodies, and non-JSON media types before flow steps | `api(at:"flows")` (`strict_json`) |
| Unreleased: flow step values that were dropped are sent - `run: webhook` `payload:` (or a map/list `body:`) is the JSON body (no longer the whole context); a `${{ }}` or quoted respond `status:` is rendered (an integer 200-599, else the step fails with a 500 - no silent 200); `run: api` `body:` as a map/list and `json:` as a list are sent as JSON; respond `headers:` / `content_type:` are sent through an allowlist (a declared type sends a text body as written); email `unsubscribe_url` becomes `List-Unsubscribe` (https only; one-click POST is opt-in) | `api(at:"flows")` (`respond_headers`), `api(at:"email")` |
| Unreleased: a server error from a built-in route or a flow keeps its status and shape, but the answer is the route's generic text plus a request id (`list failed (request id: ...)`, JSON `{"error": ..., "request_id": ...}`, `X-Request-Id` header), never SQLite's text; the detail is in `_benmore_request_log.error` / `request_id`, `get_request_logs` (`request_id` filter) and a `SERVER ERROR` journal line | `api(at:"errors")` (`server_errors`) |
| Unreleased: the database engine is SQLite 3.53 - a number computed in SQL and written as text or JSON there (`json_object('total', price * qty)`, `CAST(.. AS TEXT)`, `||`, a `SUM()` of REAL prices) keeps up to 17 digits (`434.99999999999994`, was `435.0`): round it in the statement (`round(.., 2)`); a top-level `EXISTS (...)` with `LIMIT .. OFFSET` returns the right page and `EXISTS` over an `OR` of indexed columns finds its row (both were wrong before); the query deadline now stops a statement at any step | `api(at:"flows")`, `api(at:"query")` (`query_deadline`) |
| Unreleased: a flow step key its step type does not read is refused at write time and logged at load (`retry`/`on_error`/`if`/`id` under `with:`, `timeout` off api/compute/transcribe, `params` on `sql_dynamic`, `with.sql`, any `with:` key not listed for the type); `else:` on a gated `if:` + `run:` step, `with.timeout` on transcribe and step-root `timeout` on compute are read now; a SQL step with no statement fails with `no SQL statement` | `api(at:"flows")` (`step_keys`) |
| Unreleased: a table/column name in config must be a plain identifier (letters, digits, `_`, not starting with a digit): `groups.table`/`key`/`user_field`/`role_field`/`bootstrap.org_table`, encrypted.yaml and inline `encrypted:` tables/columns, retention.yaml `table`/`column`, a workflow's `table`/`field` - a non-identifier is refused at push / `benmore check` (plain names unchanged) | `api(at:"scoping")` (`tenant_bootstrap`) |
| Unreleased: `expect_rows` is checked on every `run: sql` / `sql_dynamic` step - rows returned for a SELECT or a `RETURNING` write (it was ignored there), rows affected otherwise - and under `with:` (was ignored; the step root is canonical); `WITH ... <write>` without RETURNING stores `rows_affected`; an assertion that cannot be checked is refused at write time and stops the step. A valid mismatch in an approved command records a retryable `conflict`; SQL/assertion/count errors remain operational | `api(at:"flows")`, `api(at:"connector")` |
| Unreleased: `${{ steps.<id>.outputs.rows_affected }}` resolves (it never did: `!=` on it was always true, `==` always false; same for any output column named `rows…`) | `api(at:"flows")` |
| Unreleased: a hard-bounce email pause ends by itself (24h, then 72h, then manual; complaints stay manual) and a resume restarts the measurement; accepting an ownership transfer is refused while the app carries paid features the recipient's plan lacks (`plan_gaps`); `GET /platform/ops/over-plan` for operators | `api(at:"email")`, `api(at:"collaborators")` |
| Unreleased security round seventeen: `before_update` hook SQL placeholders are the request's fields again (2.7.251 regression); the groups membership table needs a tenant admin unless it declares its own rule; `member-of:` parents can be explicit (`<join>=id`); encrypted secret-named columns stay hidden without unmask roles; email `to:` values are one recipient (`| recipients` for a list) and HTML email bodies escape values (`| raw` keeps markup); sign-up limits (`auth.signup_rate_limit`); support sessions can't manage credentials | `api(at:"hooks")`, `api(at:"scoping")`, `api(at:"access")`, `api(at:"encryption")`, `api(at:"email")`, `api(at:"auth")` |
| Unreleased security round sixteen: `self`/`group` access returns 404 on tables with no owner/tenant column (declare `everyone` if intended); membership identity and reactivation guarded; per-app Stripe events applied once and in order; presence honors `ws_rooms`; IPv6 /64 sign-in and flow rate limits | `api(at:"access")`, `api(at:"auth")`, `api(at:"payments")`, `api(at:"realtime")` |
| Unreleased: `/sitemap.xml` and `/robots.txt` serve your own `static/sitemap.xml` / `static/robots.txt` when present; generated links no longer point at localhost on hosted apps | `api(at:"frontend")` |
| Unreleased security round fifteen: JSON bodies/room payloads keep values whole; payload-less `ws:` sends only `{}`/`{"table":…}` (declare payloads); `validators.yaml` compares whole operands; tenant roles no longer pass `perm:` on un-grouped tables; hosted writes refuse editor auto-run config | `api(at:"hooks")`, `api(at:"flows")`, `api(at:"access")`, `api(at:"realtime")` |
| Unreleased security round fourteen: `benmore sync`/`pull` stay inside the workspace and skip hidden/auto-run files; an email change revokes tokens and grants and applies on a confirm button; `run: compute` gets copies of its args; `/api/_schema` follows RBAC scopes; session recordings mask secrets | `api(at:"auth")`, `api(at:"flows")`, `api(at:"components")`, `api(at:"frontend")` |
| Unreleased: a stale `mcp.yaml` review no longer freezes the app; it reloads from disk with only the connector off, writes warn `mcp_connector_withheld`; review again and push `mcp.yaml`, or delete it if the app serves no connector | `api(at:"connector")` (`manifest_authoring`) |
| Unreleased `pwa.service_worker: /static/sw.js` serves the app's own service worker at the reserved `/sw.js` (offline cold start); opt-in, other apps unchanged | `api(at:"mobile")` (`pwa_service_worker`) |
| Unreleased security round thirteen: tenant roles no longer pass `role:` gates on un-grouped tables (list shared catalogs under `groups.shared`); env-derived values make outbound calls credentialed; a recent sign-in can add a passkey; `GOMEMLIMIT`/`GOGC` reserved | `api(at:"access")`, `api(at:"flows")`, `api(at:"auth")` |
| Unreleased security & performance round twelve: adding a passkey needs `{ password }` or `{ mfa_code }`; don't name tenant roles `admin` (only global admins bypass) and declare `roles:` for `perm:`; a foreign key must name a parent the caller can read (422); has-many includes stop at 100 per parent; in `run: api` URLs split `owner/repo` into two refs and pass query strings via `with.query`; `sql write:true` runs one DML per call; accept collaborator invites with `collaborator_invites`; page past 100k rows with `?cursor=`, queries stop at 10s | `api(at:"auth")`, `api(at:"rbac")`, `api(at:"access")`, `api(at:"scoping")` (`automatic_indexes`, `deep_pagination`), `api(at:"flows")`, `api(at:"query")` (`query_deadline`), `api(at:"recovery")` (`db_pool_sizing`, `audit_retention`), `api(at:"collaborators")` |
| Unreleased security round eleven (MCP connector): a password change revokes connector grants; command event flows keep row taint; command SQL with an unclosed `/*` is refused; commands, file ingest and artifacts work on apps without groups; `GODEBUG`/`MCPGODEBUG` are reserved env keys | `api(at:"connector")` (`connector_grants`) |
| Unreleased passkeys: `bm.auth.passkey.register()` / `.signIn()` add Face ID / Touch ID / phone sign-in to any app (on by default, `auth.passkeys: false` turns it off); a passkey works only on the host it was created on | `api(at:"auth")` (`passkeys`) |
| Unreleased auth controls: `auth.signup: false`, `auth.password_reset: false`, and `auth.api_tokens: false` close public account creation, end-user password recovery, and user token issuance; defaults stay on | `api(at:"auth")` (`self_service_controls`) |
| Unreleased fixed-tool PDF/OCR qualification: native, raster-only, rotated, encrypted and missing-provider paths run in Linux amd64 CI; Ubuntu 22 English data is installed at the frozen path | `api(at:"connector")` (`connector_grants`) |
| Unreleased artifact manifest schema version and private telemetry format/source-schema revisions; confirmed workflow terminal transitions are counted after commit without payloads | `api(at:"connector")` (`connector_grants`) |
| Unreleased hook/webhook delivery: only 2xx is delivered; ordinary subscription retries, permanent failures and unknown transport outcomes stay distinct; approved effects never blindly replay | `api(at:"connector")` (`connector_grants`) |
| Unreleased read-only MCP starter and explicit `benmore mcp review <appdir> --reviewed`; owner exposure and approved writes stay opt-in | `api(at:"connector")` (`connector_grants`) |
| Unreleased app MCP authoring from app files: unsealed review, native example, top-level digests and manifest-last deployment (target CLI 0.1.37 / runtime 2.7.259) | `benmore docs connector`, [connector reference](references/connector.md) |
| MCP connector contract: manifest, tools, commands and human approval; execution states/recovery; files, artifacts, resources, external connections, owner switches and security limits | `api(at:"connector")` (`connector_grants`) |
| Unreleased Notify Hub portability fixture: native and pinned remote status reads expose only id/status/timestamps through a shared StatusCard; recipient/subject remain outside tool output and observability, foreign reads are denied, and no send tool exists | `api(at:"connector")` (`connector_grants`) |
| Unreleased immutable MCP artifacts: `artifact.export` formats the caller's committed reviewed-command receipt as XLSX, escaped HTML or sandboxed PDF; private manifests bind owner, account incarnation, tenant and original scopes; byte retrieval is owner-only, cookie-session-only, rechecks current role/scopes, and verifies size/hash | `api(at:"connector")` (`connector_grants`) |
| Unreleased read-tool artifacts: a native read tool declares `artifact: {title, formats, sheets: [{name, source, columns}]}` in `mcp.yaml` (contract-digest content, omitted when absent) and the built-in `artifact.create` re-runs it with the caller's grant to store an XLSX (typed cells, frozen header), printable branded HTML or sandboxed PDF through the same immutable store, with per-user rate, size and 25-artifact/128 MiB ring budgets | `api(at:"connector")` (`connector_grants`) |
| Unreleased security round ten: write flow `auth: required` (true/yes/typos now require sign-in); a namespaced ref on the right of `==` is compared by value; the write gate refuses keys the parser drops (flows, workflows, access ops, app.yaml auth/features, cron.yaml); don't name a step after a request field (read it as `${{ params.x }}`); `set_env` refuses `PATH`/`LD_*`/`GIT_*`/transcribe binary paths | `api(at:"flows")`, `api(at:"workflows")`, `api(at:"access")`, `api(at:"transcribe")` |
| Unreleased command-owned fields: `command.owns: [table.column]` makes generic CRUD (create, update, batch, ingest, transaction, group bootstrap, admin panel, import Mode A, connector update; admins included) refuse the column with 403 `field_owned_by_command` (an unchanged echo on update is allowed for callers who can read the column; `deleted_at`/`updated_at` cannot be owned); ownership is CRUD-only, so flows, hooks, other commands and Mode B restore can still write it | `api(at:"scoping")` → `command_owned_fields`, `api(at:"connector")` (`connector_grants`) |
| MCP owner switches: `benmore mcp status\|enable\|disable <app> [--writes] [--export] [--publication] [--revoke] [--env dev\|prod]` control owner-only exposure; host authority, live app-user grants and real-client acceptance remain required. Disable is protective; revoke requires every client to reconnect | `benmore docs connector`, `api(at:"connector")` (`connector_grants`) |
| Unreleased hosted push fix: `write_file`/`edit_file` run only source validators after a write, scoped to the written file unless it is schema/app/flows config (app-load and drift moved to `check`); `write_file` takes `reload:false` and `benmore deploy` reloads once per batch; restart surfaces return 202 `verified:false` instead of 503 when the restart was issued but not verified in time | `api(at:"environments")` (`restart_and_reload`) |
| MCP approved writes: with owner write exposure on and host authority provisioned, command tools only prepare (operation id, exact preview, 15-minute expiry, review link); a person approves in the browser, then `_commit` applies once and `_status` reads back; writes off hides and refuses every surface | `benmore docs connector`, `api(at:"connector")` (`connector_grants`) |
| Unreleased approved-command CRUD parity: validators, computed/encrypted fields, workflow role guards and outboxed event flows follow the command transaction; unsupported kinds remain refused | `api(at:"connector")` (`connector_grants`) |
| MCP synchronous command-flow prerequisite: `transaction: true` responses wait for commit, buffer up to 1 MiB, and reject nested `serve_file`; a missing `respond` still commits prior SQL and returns the existing diagnostic 500 | `api(at:"flows")` (`transactional_responses`) |
| MCP native update prerequisite: PATCH and atomic transaction updates share the canonical transaction-owned pipeline; SQL after-hooks, authoritative readback, audit and durable hook/webhook intents commit together, while hosted retry/recovery acceptance remains open | `api(at:"PATCH /api/<table>/{id}")`, `api(at:"batch")` (`cross_table_transaction`) |
| MCP revision prerequisite: explicit opt-in bootstrap installs incarnation-bound row revisions and retained tombstones; read-only verification refuses schema/trigger drift, unsupported tables and alternate UNIQUE indexes. Hosted enrollment and restore-epoch acceptance remain separate gates | `api(at:"batch")` (`cross_table_transaction`) |
| Join flow `if:` comparisons with `&&`/`||`/`!`/parentheses; write hook and workflow `when:` as SQL over the row (`status IN (...)`, `x IS NOT NULL`), never `{{templates}}` (v2.7.247) | `api(at:"flows")`, `api(at:"hooks")` |
| Flow `if:` with `>=`/`<=` now fires and `>`/`<` compare numbers; values you substitute are never expanded as templates; read request fields that share a step id as `${{ params.<id> }}`; new workflow rows start in `initial`; frontmatter `require:`/`role:` gate pages (v2.7.246) | `api(at:"flows")`, `api(at:"workflows")`, `api(at:"frontend")` |
| Security round nine: a list filter or sort on a hidden column (`share_token`, `*_api_key`) answers 400, so read those through a flow; `sql_dynamic` text can't use a step output built from request input (bind it with `:name` in `run: sql`); `enqueue` needs a literal `flow:`; a before-update hook row holds only the written columns; sending-domain claims need DKIM or a TXT proof; v2.7.248 | `api(at:"scoping")`, `api(at:"flows")`, `api(at:"sql-dynamic")`, `api(at:"email")` |
| Need a secret inside a `run: compute` module? Pass it as an arg, `key: "${{ env.NAME }}"`; before v2.7.245 it arrived empty (v2.7.245) | `api(at:"compute")` |
| Adding Google Analytics or another tracker? Name it in `seo.cookie_notice` and load it only after `bm:cookie-consent` / `window.bmCookieConsent() === "accepted"` (v2.7.244) | `api(at:"analytics")` |
| Webhook `secret: "${{ env.NAME }}"` works with `verify: stripe`/header verifiers; `idempotent: true` (top level) makes an async flow replay after a crash; `bm.notifications.list/onNew` return real data (v2.7.243) | `api(at:"webhooks")`, `api(at:"async-flows")`, `api(at:"notifications")` |
| `benmore restore` keeps current sign-in state (passwords, MFA, revoked sessions and tokens) while rolling data back; users signed in after the backup sign in again (v2.7.242) | `api(at:"recovery")` (`database_restore`) |
| Hosted databases: creates answer 507 `storage cap reached` at the plan storage limit and every write stops a quarter past it; delete data, or upgrade and restart. A password you set on an existing account with `users set-password` is temporary unless you pass `--no-change-required` (v2.7.242) | `api(at:"recovery")` (`storage_limit`) |
| Flow SQL writes notify `bm.live()` views like auto-CRUD writes (after commit), so drop polling fallbacks; `run: broadcast` messages a WebSocket room from a flow (`from: 'server'`) (v2.7.240) | `api(at:"flows")`, `api(at:"websocket")` |
| HTTPS session cookie is `__Host-benmore_session`; grandfathered unverified accounts must verify email at next sign-in when the app keys grants by email; edges may live on a separate domain (v2.7.239) | `api(at:"auth")`, `api(at:"edges")` |
| Security round six: TSX and compute imports must stay inside `static/`; compute returns JSON and bounds regex backtracking; admin-only management rejects scoped admin tokens; tenant roles, workflow transitions and hook `{{user_group_id}}`/`{{_submitted}}` follow the current tenant and written columns (v2.7.238) | `api(at:"frontend")`, `api(at:"compute")`, `api(at:"auth")`, `api(at:"workflows")`, `api(at:"hooks")` |
| Security round five: docs, types and flows.json are per caller; secret-named text columns never appear in reads; `{{var}}` escapes by HTML context; templated redirects stay same-origin (`allow_hosts`); before-hooks get `{{_submitted}}`; profile PATCH needs `auth.profile_fields`; email-keyed grants wait for verification (v2.7.237) | `api(at:"scoping")`, `api(at:"auth")`, `api(at:"frontend")` |
| QA inventory + batched browser journeys: `qa_inventory` drafts `tests/journeys/*.yaml` from the rendered app and declared rules; `browser_batch`/`benmore verify` run them all on one headless browser; use `data-testid` selectors (v2.7.229, CLI 0.1.32) | `api(at:"qa")` |
| Checked app history and explicit saved-source/failed-commit receipts (v2.7.226) | `api(at:"github")`, `api(at:"environments")` |
| Checked dev refresh, recoverable database/key transfer and explicit failure state (v2.7.226) | `api(at:"environments")` (`refresh_dev`) |
| Checked environment snapshots and explicit saved-but-unapplied errors (v2.7.226) | `api(at:"recovery")` (`environment_materialization`) |
| Checked database restore, preserved originals and explicit failure/activation state (v2.7.226) | `api(at:"recovery")` (`database_restore`) |
| Per-app lifecycle coordination, cancellable reloads and busy-operation retry | `api(at:"recovery")` (`lifecycle_coordination`) |
| Publishing uses the previewed source and reports migration preflight/verification failures (v2.7.226) | `api(at:"environments")` |
| Atomic analytics pageviews, session reuse and explicit storage failures (v2.7.226) | `api(at:"analytics")` |
| Pending-only migration backups and startup failure/phase reporting (v2.7.226) | `api(at:"recovery")` |
| OAuth connection availability, visible errors, and app-scoped custom providers (v2.7.226) | `api(at:"oauth")` |
| App-specific audit/usage buffers and graceful worker shutdown (v2.7.226) | `api(at:"audit")` |
| Atomic reset-and-seed with transaction and framework-table protection (v2.7.226) | `api(at:"recovery")` (`reset_and_seed`) |
| Checked app teardown and retained reservations after deletion failure | `api(at:"recovery")` (`delete_app`) |
| Verified restart results and runtime reload receipts | `api(at:"recovery")` (`restart_and_reload`) |
| Codex/Claude skill bundle, edition-aware agent guides, harness workflow | `api(at:"harness")` |
| Malformed core configuration fails before startup/reload mutation | `api(at:"recovery")` |
| Rejected reloads retain the running handler and workers; committed DB changes are not automatically undone | `api(at:"workflows")`, `recovery` |
| Unchanged FTS indexes reused; changed definitions rebuilt transactionally | `api(at:"search")` |
| Read-only MCP query enforcement, bounded rows, execution deadline | `api(at:"query")` |
| Temporary credentials must be replaced before protected access | `api(at:"auth")` |
| Source conflict guards and feature packs | `api(at:"sync-status")`, `feature-packs` |
| Headless auth, agent usage privacy, stable reference caching | `cli-auth`, `agent-usage`, `api-reference-cache` |
| Deploy existing frontends with their generated browser output | `existing-frontends`, `sdk` |

## Scope and sensitive operations

Use existing authorization; ask only for a missing decision or authority needed for
the next action. Do not infer authorization to send messages, charge customers,
change collaborators, expose private data, or erase data from a request to inspect
an app. Read the exact operation before executing it. Never include credentials,
raw database exports, or private customer records in a handoff.

When the user asks to deploy, ship or launch the app, they mean a URL other
people can use, not the dev instance. Verify on dev, then promote
(`benmore promote <app>`) and hand back the production URL. Ask first only when
the app already has production users or data at stake. If you stop at dev, say
so and give the exact promote command; never present a `-dev` URL as the release.

Production promotion, `benmore publish` (turns off testing mode: the feedback flag and demo gate; there is no banner), and source push are different actions.
A database restore is not a source revert. See `environments`, `verification`, and
`recovery` before the corresponding operation. Preserve the selected environment
and verify effects after every consequential action.
