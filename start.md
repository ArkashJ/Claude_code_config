---
description: Open a session — preflight, enumerate sources, set the working rules
---

Start this session properly. These rules encode corrections that recurred across 21 harvested
sessions — they are structural, not suggestions. If a step is impossible here (no git repo, no
`gh`, no remote), say so explicitly in one line and move on; never silently skip.

## 1. Preflight — do this NOW, before anything else

Run and show: `git status --porcelain`, `git log --oneline -5`, `gh pr list --state open`,
`gh issue list --limit 20`, `gh auth status`. Also check the project board if one exists
(`gh project list`). Never infer remote/branch/PR state from local git — query it. Never fork
from a branch without checking whether an open PR already owns it.

Check for a dead predecessor: any open draft PR with a "Checkpoint log" comment but no final
handoff means a session died before /wrap. Read its checkpoint log, report what it was doing and
where it stopped, and ask whether to resume it or start fresh.

## 2. Enumerate, then DIVE on the intersection

When I give you the task, first list every source you will draw from WITH COUNTS (N open PRs and
their review comments, N issues, N docs files, changelog entries since last touchpoint,
deployed/runtime state if relevant). This list is the completeness contract: any "done /
verified / covered everything" claim must cite it and NAME what was not read. "Thorough" means
the enumeration is exhausted, not an effort level.

Then go DEEP on everything that intersects the task — and only that. Dispatch cheap-model
subagents (so the reading costs their context, not yours) to fetch and distill:
- PRs (open AND recently merged) touching the same files/feature: full bodies, review threads,
  inline comments — `gh pr list --json number,files`, `gh pr view <n> --comments`. Review
  threads carry the "why" that prevents re-litigating settled decisions.
- Issues whose bodies mention the task's feature/files: `gh issue view <n> --comments`.
- The predecessor session's Checkpoint log and handoff comments on any related PR.
- Changelog/commits touching the same paths: `git log --oneline -20 -- <paths>`.
Each subagent returns a distilled brief (decisions made, open questions, gotchas — with PR/issue
numbers), not raw dumps. Depth is proportional to intersection with the task; the rest of the
repo's history stays at count-level. If the ground is genuinely unfamiliar, run /map instead of
crawling inline.

## 3. Isolate, commit, push, checkpoint — continuously, without being asked

Work in a worktree. Commit after every green verify; push every commit; open a draft PR at the
first commit. Non-empty `git status` at a stopping point is a defect. Scratch artifacts go to a
temp dir, never the repo tree.

After each completed unit of work (green verify, finished sub-task, before any large fan-out),
CHECKPOINT unprompted: commit + push, then append one line to a single rolling "Checkpoint log"
comment on the draft PR: `<time> — <what landed> — <verify: one command/URL that proves it in
under 2 min> — <what's next>`. The verify field is mandatory: work whose correctness can only be
checked by re-doing it is not done — attach the cheap certificate (test that flips, screenshot,
command output) or say explicitly that this delta is judgment-only and needs human review. Capture surprises the moment
they happen, in the same comment: `SURPRISE: <doc/plan said X, reality is Y>` or
`FALSIFIED: <what I asserted vs what the test showed>`. Raw one-liners only — routing them into
changelog/issues/docs happens at /wrap, not now. This log is the recovery record: if this
session dies, the next session reconstructs from it.

## 4. Delegate — agents and workflows, tiered by cost

Fan out subagents/workflows for parallelizable work: **haiku** for mechanical sweeps
(enumeration, file-read summaries, discovery, status collection); **sonnet** for well-specified
implementation lanes with a verify step; **strongest model** only for architecture, judgment,
synthesis, and adversarial verification (verifiers try to REFUTE, not confirm). Isolation is
allocated at dispatch: one worktree per writing agent; declared file sets rejected on overlap
with sibling lanes AND with any open PR's files; per-lane DB/fixture names for concurrent tests.
Every dispatch prompt includes the commit/push cadence from rule 3.

## 5. Verify at the authoritative source

Assertions about remote, deployed, DB, or runtime state must show proving command output from
the source itself — not the repo, not a green pipeline, not an HTTP 200, not an exit status.
After any write, read it back. A report on a runnable app states whether the app was run.

## 6. Status — volunteered, never polled

At every stopping point print one unprompted line: branch, HEAD, PR state, agents in flight,
dirty files, what's blocking. Background work reports progress unasked. If I have to ask
"status?", this rule was violated.

## 7. Blast radius

Merges, deploys, bulk deletes, force pushes, and production data mutations each need a fresh
per-action confirmation naming the action — no prior broad grant covers them. Conversely, cheap
reversible work inside an explicit grant gets done, not deferred. Rank by blast radius, not
effort.

Now show me the preflight output, then ask for the task if I haven't given one.
