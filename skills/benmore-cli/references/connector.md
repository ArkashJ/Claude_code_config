# App MCP authoring

Run `benmore docs connector` for the embedded, offline guide with a complete
native mcp.yaml example, digest placement, source review and deployment order.
No Benmore framework source checkout or Go toolchain is required. The unreleased
source change targets CLI 0.1.37 / runtime 2.7.259; confirm those versions are
installed before using this workflow. The hosted canonical reference is
`benmore api <app> connector` (`api(at:"connector")` through platform MCP).

For omitted optional arrays, see `review_serialization` in that reference and
the offline guide's review section; older CLIs require explicit unused `[]` arrays.

Unreleased exact private-file binding: declare `handler.file_column` on both
`ingest` and `verify`; omission preserves legacy any-string-column matching.
Read the offline guide for current-column authorization and release limits.

Unreleased file-tool membership and status: optional
`handler.membership_constraints: {kind: human, status: active}` requires every
equality on the actor's one live canonical group-membership row, in addition
to existing grant, table/row, exact file-column and ownership checks. A native
`status` operation requires `processing_id`, `record_id` and `file_ref`, and
returns bounded metadata only for a known successful snapshot-backed result;
it exposes no parsed blocks or snapshot payload. `complete` is historical
parser completion, not proof of current file bytes. Failure-only and legacy
unbound records are not eligible. Omission of membership constraints preserves
existing behavior.

Unreleased tenant-bound uploads: a file handler may declare
`handler.upload_tenant: current` only with `handler.file_column` and configured
groups table/key/user field plus the same key on the source row. The recorded
private-upload group must be nonempty and match both the grant's selected
workspace and that source row. This is checked for ingest, cache reuse, verify,
status and publication; strict tools cannot consume legacy-policy snapshots.
Omission preserves the established admin/uploader/row-owner vouch policy.
The setting changes the reviewed contract digest; source inspection reports
`upload_tenant: current`.

Unreleased command SQL adds only `json_array_length` and `json_group_array` to
the function allowlist. Table enrollment, caller scope and rollback stay in force.

An approved command whose valid `expect_rows` assertion fails returns `conflict`
and records a retryable conflict attempt after rollback. Invalid assertions, SQL
failures and unavailable row counts remain `unavailable_provider` failures.
