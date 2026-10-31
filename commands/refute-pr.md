---
description: Cold adversarial review of a PR - a fresh opus reviewer that never sees the author's reasoning is prompted to REFUTE the diff across fixed lenses; findings come back ranked with file:line and a failure scenario
argument-hint: <pr-number> [owner/repo]
---

Refute PR `$ARGUMENTS`. The reviewer is cold on purpose: it gets the diff and repo access, never the PR
description, commit messages, review thread, or your own opinion of the change. An author's explanation
anchors a reviewer toward "it works".

## 1. Gather (you, not the reviewer)

1. Parse `$ARGUMENTS`: first token is the PR number, optional second is `owner/repo` (default: the cwd repo).
   Pass `-R <repo>` to every `gh` call if one was given.
2. `gh pr view <N> --json state,baseRefName,headRefName,headRefOid,additions,deletions,changedFiles`.
   Stop and say so if the PR is not OPEN or MERGED. Print the counts ("N files, +A -D").
3. `git fetch -q origin <baseRefName> pull/<N>/head` so both ends are local.
4. Write the three-dot diff to a file the reviewer can read in full:
   `git diff origin/<base>...<headRefOid> > /tmp/refute-pr-<N>.diff` and compare against `gh pr diff <N>`
   (line counts must match; if they differ, the base moved - use the gh diff and say so).
   Also write `git diff --stat origin/<base>...<headRefOid>` next to it.
5. In a Profectus checkout, also run `scripts/check-pr-regen-drift.sh <N>` and keep its one-line verdict
   for step 3 (do not pass your reading of it to the reviewer).
6. State the untruncated size: "diff is N lines across M files". If it is over ~3000 lines, split the
   file list into groups of related files and launch one reviewer per group in parallel.

## 2. Launch the reviewer

`Agent` with `subagent_type: general-purpose`, `model: opus`, foreground. The prompt is exactly the
block below with `<N>`, `<headRefOid>` and `<base>` filled in, plus the diff path and repo path. Nothing else:
no PR title or body, no "the author says", no hints about what you think is wrong.

> You are a hostile reviewer. Your job is to REFUTE this change, not to approve it. Assume it is wrong
> and find the input, state or ordering that proves it. The diff is at /tmp/refute-pr-<N>.diff
> (stat beside it). The checkout is at <repo path>; read the files at head `<headRefOid>`
> (`git show <headRefOid>:<path>`), their callers, and the code they replace. Read whole functions, not
> just hunks. Run read-only commands to prove claims (grep, `git grep`, `git show`, go vet, tests you can
> run locally without writing to shared state). Do not edit files, push, comment on the PR, or call
> external services.
>
> Attack through each lens. For every lens, either produce a finding or write one line saying what you
> checked and why it holds.
> 1. Authz / tenant scope: every new or changed read/write checked against the caller's role AND the
>    customer/tenant (404 vs 403, list endpoints, exports, MCP tools, background jobs acting without an actor).
> 2. Data loss and silent success: nil slice or map written as NULL, zero value overwriting real data,
>    `Done` with zero rows processed, retry-on-permanent-error, swallowed errors, partial writes outside a
>    transaction, "unknown" rendered as 0 or empty.
> 3. Money: integer cents end to end, rounding, currency, sums that skip rows, null amounts shown as a zero dollar amount.
> 4. Outbound sends and consent: any email/SMS/webhook/NetSuite write; consent ledger, STOP handling,
>    archived or test records, idempotency keys, double-send on retry, recipient scoping.
> 5. Migrations, locks and races: lock level and duration on big tables, backfills in the same transaction,
>    down migrations, number collisions, check-then-act without a unique index, concurrent double-submit.
> 6. Mock-layer drift: a changed or new endpoint/field must change BOTH mock layers (the payload module and
>    the service-worker file) and the fixtures; stale mocks make MOCK-mode QA pass for the wrong reason.
> 7. Generated-file drift: sqlc output, openapi.json, the generated TS schema, API reference docs and the
>    MCP tool catalog must match their sources; hand-edited generated files.
> 8. UX dirty-dialog state: dialogs/sheets/forms that lose input on dismiss, skip the unsaved guard, keep
>    stale state after success or error, double-submit, or leave focus/scroll wrong.
> 9. Anything else that breaks a caller you can find by grep.
>
> Report format, nothing else: a ranked list, most severe first. Each finding has: severity
> (blocker / major / minor), `path:line` at head, one sentence of what is wrong, a concrete failure
> scenario (who does what, what they see or what is lost), and the command or lines that prove it.
> Then a "lenses with no finding" section, one line each. No praise, no summary of the change, no
> reasoning transcript. If you cannot find a real defect in a lens, say so; never pad with style nits.

## 3. Triage (you)

The reviewer's output is a claim, not a fact. For every blocker and major finding, open the cited
`path:line` at head and confirm it (grep the symbol, run the command it names). Mark each CONFIRMED,
REFUTED (say why) or UNVERIFIED. Do not relay an unconfirmed finding as real.

Report to the user: the PR, diff size, the drift-script verdict, and the ranked CONFIRMED findings with
file:line and failure scenario, then the refuted/unverified ones in one line each, then the lenses with
no finding. Do not paste the reviewer's reasoning. Do not edit the PR, post comments or push fixes
unless the user then asks; a fix lane is a separate step.
