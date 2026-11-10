## Enumeration discipline — count before you truncate

Never draw a conclusion from a truncated list. `| head`, `--limit`, `[:N]` output is a SAMPLE:
print the untruncated count first (`wc -l`, `--json | jq length`) and state "N total, showing M"
before reasoning about the set. Any completeness claim ("all PRs reviewed") cites the full count.
A `WHERE outcome = X` drops the complement as silently as `| head`: count both sides.

## Depth before plan — read the whole corpus first

- Before any plan or checklist built from a corpus (client docs, CSVs, specs, issues): enumerate it
  as files × lines/bytes, then read EVERY decision-relevant file in full. Fan out parallel readers
  by folder (routing below). Never sample a rules CSV or an answer key.
- Every plan states coverage: "read N of N files". Below 100%, say so first and finish reading
  before writing. A plan written from a sample gets rewritten after the user demands depth.
- **Depth gates the plan, not the fixes.** A defect confirmed with file:line or a failing spec goes
  to a fixer lane that hour; a validation lane fixes in-lane when the fix is local to its files.
  Never hold confirmed defects until every lane reports (Measured 11-08: defects confirmed 03:50,
  first fixer 05:42, user: "WHAT WERE YOU DOING FOR ALL THESE HOURS"). Ask for the merge grant
  with the plan, not after the PRs pile up.
- **Find the oracle.** Ask what already exists upstream (the client's own engine, ledger, report,
  answer key) and make it the acceptance test. Port it; don't reinvent it.

## Verify before you relay

- **Agent output is a claim, not a fact.** Spot-check every load-bearing claim at source before
  relaying it: recompute the arithmetic, grep the symbol, open the row. A lane's work exists only
  when its commits are reachable from the branch and its worktree is clean.
- **Adversarial review on every artifact before shipping:** a cold reviewer (opus) that never sees
  the author's reasoning, prompted to refute. Expect 20–30 findings on a big rewrite.
- **Prod evidence over code reading.** Measure behavior from logs, CI or build history (counts per
  day, p50/p95, pass rates) before claiming it. Remote/deployed/DB state needs output from that
  source; after any write, read it back.

## Model routing — one table, used everywhere

- **haiku**: enumeration, counts, file moves, ticking checklists, status collection.
- **sonnet**: builders, verifiers, parsers, well-specified implementation lanes.
- **opus**: money, locks, migrations, legal/finance reading, architecture, the adversary.

Subagents run in the foreground. Each brief carries the shell rules below, ONE output path, and the
exact proof command. One worktree per writing agent; no file-set overlap between lanes.
Briefs say: "never end your turn while your own background job runs; write your output doc as you
go" (Measured 11-08: a reviewer parked on its own job, reported 66 min late, doc half-written).
Remove a lane's worktree the moment its PR merges: a leftover checkout locks the branch for the
next lane. Prod reads a subagent needs go through the integrator, whose grant covers them.

## Never `sleep` to wait

`sleep N`, sleep-then-poll and `sleep` inside compound commands are blocked by
`~/.claude/hooks/guard-bash.sh` (self-test `guard-bash.test.sh`; enforced only while it passes). Use `Monitor` with an until-loop or
`run_in_background` on the FIRST attempt. An inner `timeout 900` longer than the Bash tool's cap is
decorative: pass `timeout:` on the call itself, or background it.

## One command, one absolute path — never `cd &&` chains

The harness resets cwd between calls and the guard rejects `cd X && cmd` and `; cd X`. Use absolute
paths, `git -C`, `bun --cwd`. `rm` targets are literal paths or `"${VAR:?}"`. **A loop that reports
success without a count is not verified:** print the count and sanity-check it (`2>/dev/null` has
hidden 121 empty files in a 122-file batch).
**Scripted text replaces anchor on the target's own unique name** (e.g. `_tool("name",`, never a shared marker
like `description=`) and assert the match count before writing (`assert s.count(old) == 1`). Quote heredoc
delimiters (`<<'EOF'`; guard-bash blocks an unquoted one whose body holds a backtick).

## Session and delivery

- **Hazard check before any push:** `git log origin/<trunk>..HEAD --stat`; list what unpushed commits
  ADD (client data, exports, secrets, binaries, `*.jsonl`, scratch md) and untrack them first.
- **Deliverables live in GitHub, not local files.** One master issue (checklist body + log section;
  prompts and context as comments); close superseded issues with a pointer; open PRs. When the
  user says post, merge or close, do it; don't stop at a plan.
- **Status:** while the user waits on agents, one line with counts ("3 of 5 lanes
  landed, 1 running, 1 blocked: <cmd>"), not prose. Never say "done" while any lane is unfinished.
  No completion percentages without a real denominator.
- Merges, deploys, bulk deletes, force pushes and prod data mutations need fresh confirmation that
  names the action. Cheap reversible work inside a grant gets done, not deferred.

## Model state mathematically — invalid states unrepresentable

- **Triggers** (otherwise skip; a two-state toggle needs no table): adding or changing a status,
  phase, flag or nullable field; a retry, timeout, webhook, queue or job handler; a permission,
  role, plan or feature-flag check; money, auth or a multi-step workflow.
- On a trigger, name the state machine first: states, invariants, transition table (`from → to`,
  every writer), and what retries, duplicate or late events and concurrency can reach (two tabs,
  webhook before redirect, crash between writes).
- Make the bad state unrepresentable, in this order: a sum type / discriminated union in place of
  flag + nullable combinations; a smart constructor or branded id for an invariant; one guarded
  transition function every writer goes through; a runtime check only at the trust boundary.
- Every branch over a union is exhaustive and machine-checked: TS `switch` with an `assertNever`
  default (lint: `@typescript-eslint/switch-exhaustiveness-check`), Go the `exhaustive` linter,
  Python `match` + `typing.assert_never` under mypy/pyright. Adding a state must break every
  branch that forgot it.
- Payments, auth, workflows: state the safety property ("never X after Y") and the liveness
  property ("every pending reaches a terminal state"); the E2E test replays the interleaving that
  would break it.
- Permissions, flags, plans with 3+ levels: one partial order (lattice) with one comparison
  function, never ad-hoc lists or string compares scattered across callers.
- No new implicit state machines: no status booleans beside a status field, no second
  representation beside the old one. Migrate the writers and delete the old fields in the same
  change. A deliberate recovery state (pending row, tombstone, lease) names its exit, and the exit
  must be reachable.
- Whole-repo audit: `qa STRUCTURE` (inventory ranked by impact; fix only high-impact rows).

## Repo hygiene, docs and testing — house rules

- **Worktrees are disposable.** Remove yours as soon as its work is merged or abandoned
  (`git worktree remove`, then delete the branch). `wt-clean` runs at session start.
- **Few markdown files.** No new plans, handoffs, reports or summaries in repos: use the PR, the
  commit, the master issue or an existing doc. One owner doc per domain; README + a handful of
  owner docs is the target. Delete or merge stale, duplicated or dated docs.
- **Consolidating docs** needs a preservation ledger (every doc read and dispositioned) and an
  adversarial review (`document-consolidation`, `qa DOCS`).
- **Agent manuals (CLAUDE.md, AGENTS.md) hold rules only:** no dated narrative, no file:line cites,
  no counts a test already pins, no links to deleted docs, no mutable state.
- **Enforce hygiene mechanically:** a make target that fails on forbidden tracked files (`*.jsonl`,
  client exports, scratch HANDOFF/SESSION/PLAN md, tool caches), run as a step of the existing pipeline (not a new job), plus a pre-commit hook.
- **Tests: end-to-end and smoke only.** No new unit or integration tests. Prove behavior with E2E
  tests that drive the real app (`qa STORIES`, Playwright via `pw`) and smoke checks (it boots,
  the key route answers, the CLI runs). A standalone script's smoke test is its E2E.
- **Minimal CI/CD.** One pipeline: build, smoke, E2E, deploy. No new jobs, matrices or workflows
  unless the user asks. GitHub-hosted CI is not a gate (a repo whose own deploy pipeline gates releases follows its manual): local gates (`once <cmd>`) are the evidence.
- **Better code over more code.** Reuse an existing helper before writing one; extract a shared one
  when the second copy appears; delete dead code you touch.

## Code intelligence (LSP)

For TypeScript/JavaScript, Go and Python, prefer the `LSP` tool over grep for definitions,
references, renames, diagnostics and hover types (load it via `ToolSearch("select:LSP")`). Fall back
to grep only when LSP returns nothing useful.

- Before changing a shared symbol run `findReferences`; after, `hover` to confirm types. Treat pushed
  `<new-diagnostics>` as a correctness gate. Tell spawned agents to do the same.
- LSP works only after indexing (Go: `go.mod` + deps; TS: `tsconfig.json` + `node_modules`). On "still
  indexing", warm it with `documentSymbol`, then retry `workspaceSymbol`.
- gopls may warn about worktree modules or cache deleted worktree roots: harmless; restart gopls.

## Tools

- **graphify** — any input to knowledge graph. Trigger `/graphify`; CLI `~/.local/bin/graphify`
  (`graphify query|explain|path`); no SKILL.md.
- Session commands: `/start` (open a session), `/wrap` (close a session; pair with `harvest`) and
  `/mission` (long autonomous runs, with its own per-phase wrap). Codex mirrors all three via `~/.claude/commands/.codex/sync.sh`.
