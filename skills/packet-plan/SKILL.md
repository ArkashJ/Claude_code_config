---
name: packet-plan
description: Plan a launch or hardening push as executable packets. Use when the user wants a deep plan for a codebase (frontend, backend, or both) that Sonnet agents will then code in parallel, or says "packet plan", "deep plan", "plan the push", "plan lanes", "coverage matrix". Forces lens enumeration from the CODE (hooks, stores, charts, primitives, routes, endpoints, PRs) before any plan text, requires a visual step per surface, caps lanes at three, and emits self-contained packets plus one register line. Not for single-feature design (use impeccable) or bug triage.
---

# packet-plan

You are planning on the strong model so Sonnet can code for a day without asking a question.
Tokens are constrained. Every sentence in the output is either a printed count, a command, or
a packet an agent will execute. No prose plans.

## Why this exists (2026-09-18, Profectus beta push)

The first plan enumerated FEATURES (from the repo guide) and missed the data layer, hooks,
charts, components, dashboards, PR review and every visual check until the user named them one
by one. It used six diagnostic lanes that shared setup six times. It had no visual step, so a
route that renders wrong with a green typecheck could never enter the matrix. Merging the
resulting PRs by hand took four hours before the procedure was scripted. Each of those is a
missing enumeration, not a missing idea. This command makes the enumeration mandatory.

## Step 0a — detect the stack, then derive the enumeration

Do not assume a layout. Detect, then derive the commands from what is present:

```
manifests:  ls package.json go.mod pyproject.toml Cargo.toml Gemfile pom.xml build.gradle \
               pubspec.yaml Package.swift *.csproj composer.json mix.exs 2>/dev/null
frameworks: grep -lE 'next|react|vue|svelte|angular|expo|react-native|django|fastapi|flask|\
               rails|spring|gin|chi|echo|actix|axum|phoenix' <manifests>
infra:      ls -d infra terraform pulumi k8s helm docker-compose* Dockerfile .github/workflows 2>/dev/null
data:       ls -d migrations db/migrate prisma alembic schema.sql 2>/dev/null
contracts:  ls openapi.* swagger.* schema.graphql *.proto 2>/dev/null
guide:      ls CLAUDE.md AGENTS.md CONTRIBUTING.md docs/README.md 2>/dev/null
```

For every framework and directory detected, derive the enumeration commands for that stack
(routes, state stores, server-state cache layer, components, charts, forms, jobs, migrations,
endpoints, connectors, feature flags, i18n catalogs, CLI entry points). Print each command AND
its count. **Every count must be nonzero or written as `n/a — <reason>`.** A bare zero is not
an enumeration; it is the lens you will forget.

## Step 0b — read the repo's own record of what bites

- The guide files above: extract every named trap, gate, and "do not" into a list; print N.
- `grep -rnE 'TODO|FIXME|HACK|ponytail:' --include=* . | wc -l` and the top 20 by file.
- Open issues and PRs: `gh issue list --state open --limit 500`, `gh pr list --state open`;
  for each open PR, `git diff --stat origin/main...<head>` — an empty diff is superseded, close
  it, never review it.
- Last 30 merged PRs' titles: the recent change surface is where regressions live.
- Hosted gates: `ls .github/workflows` and `gh run list --limit 10`. If no workflow runs the
  repo's own verify target, that is packet number one.

## Step 0c — read, not grep

Then read the code the counts pointed at: every server-state hook or query layer (what does
each mutation invalidate, what is optimistic, what replays offline), every client store (what
persists, is it cleared on logout, is it scoped by principal), every chart's data source and
empty state, every auth boundary and middleware allowlist, every background job's retry policy,
every connector's live-versus-fixture switch. Write one line per file read. A plan written
before this step is a plan written from the guide, and the guide indexes only what someone
already knew to write down.

## Step 1 — coverage matrix, no empty cells

Rows: domain clusters with disjoint file ownership, plus every cross-cutting surface the
stack has (shell, auth, admin, public, CLI, jobs, infra).

Columns come in two sets. The universal set is always present:

live parity against the real backend · end-to-end journeys · authorization and in-page
controls · data layer (cache invalidation, optimistic writes, offline replay, logout and
principal scoping) · data model and migrations · background jobs and retry policy ·
contract tests against the API schema · states and honesty (empty, zero, loading, error,
denied, stale, approximate) · components and shared primitives · charts and data display ·
forms and validation · error handling and logging · a11y · responsive at the smallest
supported width · theming · i18n if any catalog exists · security (IDOR, audit, secrets,
dependency audit) · performance and bundle · observability (error reporting, telemetry,
alarms that page a human) · infra and deploy readiness · docs drift against code ·
**visual** · polish

The stack-derived set is whatever step 0a surfaced that is not above (native platform
permissions, push notifications, offline sync engine, payment webhooks, CLI ergonomics,
plugin API). Add a column per item; never fold one into "other".

Each cell is one of: `lane`, `gate:<existing check that proves it>`, or `CUT:<reason>`.
Print the three counts and `empty=0`. An empty cell fails the plan. A column with every cell
`CUT` must say why the lens does not apply to this repo.

## Step 2 — three lanes, never more

1. **diagnose** — one agent per cluster walks EVERY column for that cluster and files
   tickets. Shared setup once. Output: tickets with `class | enumeration command | sibling
   count | file:line | repro | expected tally`, plus a PNG with landed URL for every visual
   cell.
2. **build** — one packet per ticket group, one worktree per packet, Sonnet.
3. **verify and land** — Haiku reads tallies only; integrator runs the merge-train script
   once on the integrated tree; the strong model does one refutation pass on the merged head.

If you find yourself writing a fourth lane, fold it into diagnose.

## Step 3 — packets

A packet is a file of 3,000 to 5,000 words that a Sonnet agent executes with no questions.
Fixed sections, in order:

```
Owns            exact files and dirs; everything else read-only
Shared files    append-only list (mocks, generated schema, nav, route matrix, changelog)
Spec            verbatim from the plan, never paraphrased
Invariants      each with the test file that proves it; write the test RED first
Acceptance      the command and the exact tally it must print
Visual          URL, viewport, persona; PNG path + landed URL required; login page = FAIL
Hand-off        artifact path and who consumes it
Refute          one subagent told to refute the top three claims before "done"
Environment     cloud-viable yes/no; what needs local creds; MOCK vs live labelled
```

Print packet count and total word count.

## Step 4 — token economy, enforced

- Strong model: this plan, one refutation pass, polish. Nothing else.
- Sonnet: every packet. Haiku: every tally read and cleanup inventory.
- One gate run per integration point. Read the log's own exit line, never the wrapper's.
- Hosted CI must run the static gate on every PR; if it does not, that is packet number one.
- Cloud lanes for anything MOCK-only; local only for live stack, creds, AWS.
- Merge with the merge-train script, never PR by PR through the UI.
- Never rerun a gate that already produced a verdict; fix the named failure and move on.

## Step 5 — visual is not optional

Every surface in the matrix gets a baseline capture before work and a current capture after,
same URL, same viewport, same persona, desktop and 390px. A claim about a rendered surface
without a PNG path and the landed URL is not a claim. A login or denied card is a failure.
Use the project's visual diff tool if one exists; otherwise Playwright screenshots into an
evidence directory named by date.

## Step 6 — where the advantage compounds

Everything above prevents omissions. These five make each run cheaper and sharper than the
last. Skip none.

1. **Rank cells by yield before spending tokens.** For every matrix cell compute
   `reach × mutation × reports`: reach from telemetry if the repo has any (page views per
   route, else persona count that can reach it), mutation = 1 if the cell writes data or
   money else 0.3, reports = 1 + count of client or issue reports naming that surface.
   Packets are cut in descending yield; the cut list is the tail, never a guess.
2. **Ingest reports and expand each into a class.** Read client messages, transcripts,
   issues, and support notes. Every reported bug becomes: class name, one enumeration
   command listing every sibling site, sibling count, and one failing test written at the
   class level. Five reported bugs with siblings is thirty fixes for the price of five reads.
3. **Dry-run every packet on Haiku before Sonnet touches it.** A Haiku agent, given ONLY the
   packet text and no repo access, must restate the acceptance command, the tally it expects,
   and the files it may edit. If it cannot, the packet is ambiguous; fix the packet, not the
   agent. This costs cents and saves a full coding run per ambiguous packet.
4. **Emit the launch artifacts, not a description of them.** Alongside the packets write:
   the Workflow script that fans them out (coding agent per packet, Haiku verify per result,
   one integrator running the merge-train script), and a baseline capture pack (visual
   screenshots and gate tallies at the starting head) so every after has a before.
5. **Keep a ledger and read it first.** `packet-ledger.tsv` in the evidence directory: one
   row per packet with words, lines changed, tallies, questions asked, gate result, wall
   time. Step 0 of the next run reads it: packets that asked questions were too vague,
   packets that went red at the gate were missing an invariant, lenses that were cut and
   later bit are never cut again. The plan learns from its own execution instead of from
   the planner's memory.

Two mandatory rules that ride on these:

- **Every packet adds at least one build-failing guard** for the class it touches, proven
  red then green in its commit message. A packet that only ships code leaves the next
  regression unguarded.
- **Every lane's top claim gets its falsification command written before the work starts.**
  "Verified" means that command was run and its output is in the PR. Refute first, then
  build, then confirm.

## Plan mode

Steps 0 through 2 are read-only and run unchanged in plan mode. Plan mode blocks writing
files, so the packets (step 3) go INTO the plan document verbatim, each under its own heading
with its target path. The first action after approval is writing those files to disk and
printing the count; a plan whose packets never reach disk produced nothing an agent can run.

## Deliver

1. The printed counts from step 0.
2. The matrix with disposition counts and `empty=0`.
3. The three lanes with owners and cloud/local split.
4. The packet directory and its counts.
5. One register line for the project's war-room or changelog, nothing more.
Then stop and ask which packets to launch, and whether to launch them as a workflow.
