# App MCP authoring

Run `benmore docs connector` for the embedded, offline guide with a complete
native mcp.yaml example, digest placement, source review and deployment order.
No Benmore framework source checkout or Go toolchain is required. The hosted
canonical reference is `benmore api <app> connector` (`api(at:"connector")`
through platform MCP).

`mcp review --reviewed` keeps mcp.yaml as written (integers, comments,
indentation) and edits only its digest keys; see `review_serialization` in that
reference. Omitted optional arrays stay omitted.

`mcp check <appdir>` and `mcp review <appdir> --reviewed` print the whole
inspection document as JSON (over 100 KB; scripts read it). Add `--summary` for
a few lines of text: verdict, digests, reviewed tools, warnings.

To exercise a hosted connector from a script (client registration with a loopback
redirect, consent form fields, PKCE token exchange, approving `review_url` with a
cookie session), follow `hosted_test_recipe` in that reference or the offline
guide's "Test a hosted connector from a script".

Exact private-file binding: declare `handler.file_column` on both `ingest` and
`verify`; omission preserves legacy any-string-column matching. Read the offline
guide for current-column authorization and its limits.

File-tool membership and status: optional
`handler.membership_constraints: {kind: human, status: active}` requires every
equality on the actor's one live canonical group-membership row, in addition
to existing grant, table/row, exact file-column and ownership checks. A
`kind: file` `status` operation requires `processing_id`, `record_id` and
`file_ref`, and returns bounded metadata only for a known successful
snapshot-backed result; it exposes no parsed blocks or snapshot payload.
`complete` is historical parser completion, not proof of current file bytes.
Failure-only and legacy unbound records are not eligible. Omission of membership
constraints preserves existing behavior.

Tenant-bound uploads: a file handler may declare
`handler.upload_tenant: current` only with `handler.file_column` and configured
groups table/key/user field plus the same key on the source row. The recorded
private-upload group must be nonempty and match both the grant's selected
workspace and that source row. This is checked for ingest, cache reuse, verify,
status and publication; strict tools cannot consume legacy-policy snapshots.
Omission preserves the established admin/uploader/row-owner vouch policy.
The setting changes the reviewed contract digest; source inspection reports
`upload_tenant: current`.

Command SQL may call only allowlisted functions, `json_array_length` and
`json_group_array` among them (the offline guide lists them all under app
triggers). Table enrollment, caller scope and rollback stay in force.

An approved command whose valid `expect_rows` assertion fails returns `conflict`
and records a retryable conflict attempt after rollback. Invalid assertions, SQL
failures and unavailable row counts remain `unavailable_provider` failures.
A FOREIGN KEY, UNIQUE, NOT NULL or CHECK failure of the apply SQL returns
`constraint_failed`; a dependency query that does not return one `id` column,
command SQL that calls a function outside the allowlist, or command SQL that
names a column the database does not have, returns
`invalid_declaration`. Both are final (`retryable: false`), and review,
`mcp check`, the write gate and `benmore check` refuse the dependency shape and
the function whenever the schema files can prepare the statement
(`dependency_shape`, `connector_command_sql`).
