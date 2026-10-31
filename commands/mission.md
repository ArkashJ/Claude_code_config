---
description: Long-running autonomous run — phases with per-phase wraps, batched blockers, self-preservation before limits, adversarial review before the final wrap
---

This is an autonomous multi-hour run. Mission: $ARGUMENTS

Run /start first (preflight, hazard check, enumeration with counts, working rules).

Then, BEFORE executing: resolve every concrete token in the mission text against this repo —
commits (`git cat-file -e <sha>`), branches (`git ls-remote --heads origin <name>`), issues/PRs
(`gh issue view <n>`), test counts, file paths. A handed-in plan goes stale and can even belong to
another repo. Report what failed to resolve and adapt before phase 1. If the mission rests on a
corpus (client docs, CSVs, specs), the /start depth rule applies: "read N of N files" before the
phase plan is written.

## Autonomy rules — these are what make hours-long unattended work safe

1. **Phase boundaries are wrap points.** Post the phase plan to the master issue or draft PR up
   front. At the end of each phase run the phase wrap below. A run that dies mid-phase loses at most
   one phase.
2. **Never stop to ask mid-run, never run silent.** Record blockers and decisions-that-are-mine
   (issue or checkpoint log) with a recommendation, and continue with everything not blocked. Stop
   only when nothing actionable remains, then ask all batched questions at once with the
   interactive question tool. Post a one-line status with counts at every phase boundary and at
   least every ~15 minutes; never claim done while any lane is unfinished.
3. **Self-preserve before limits kill you.** Behave as if the run can be killed at any moment. On
   context pressure: checkpoint, write a continuation prompt into the PR, then delegate the remaining
   phases or wrap. Never start an irreversible operation you might not finish.
4. **Every subagent prompt carries the shell rules** (no `cd X &&`, no `sleep`, `pw`, `once`), one
   output path, and the exact proof command. Foreground subagents only.
5. **Delegate hard, tiered** (routing per CLAUDE.md). A lane's work exists only once VERIFIED
   LANDED: when it returns or dies, check its worktree is clean and its commits are reachable from
   the branch, and spot-check its load-bearing claims at source before relaying them.
6. **Blast radius still holds.** Merges, deploys, bulk deletes and prod data mutations are never
   autonomous: stage each one approved command away and ask at the end. Hosted CI is never a gate:
   local gates are the evidence, and a merge blocked only on hosted CI goes through `--admin` once
   the human approves it.
7. **Adversarial pass before the final wrap.** Run a cold adversarial reviewer (opus, never shown the
   author's reasoning, prompted to refute) over the run's output. Fix what it finds, then do the
   final wrap.

## Wrap — every phase, and once more at the end

Derive every artifact from git/gh/the enumeration; never hand-write what a command can compute.
Each phase:
- `git status --porcelain` empty: logical commits, pushed, PR current, scratch removed.
- Checkpoint-log line with a `verify:` certificate; route every `SURPRISE:`/`FALSIFIED:` line to a
  fix, an issue or an explicit discard.
- `python3 ~/.claude/skills/harvest/signals.py` and report `asks proven X of N`; if the phase changed
  React/TanStack code, `python3 ~/.claude/skills/qa/hunt.py <repo> --since <phase start>`.
- Master issue / PR comment: done, not done (`blocked: <cmd>` or `not attempted`), not read.

Final wrap adds:
- Run the repo's local gates once (`once <cmd>`) and paste the output into the PR.
- If the repo keeps a `CHANGELOG.md`, add the entry derived from commits/merged PRs since the last
  one: conclusions only, no state.
- Issues updated or closed with a link to the proving commit; one new issue per discovered root
  cause; superseded issues closed with a pointer; board items moved.
- Docs the change touched: fix drift against code; regenerate any doc that carries values (counts,
  hosts, DNS, issue numbers) from a readback. Nothing mutable in CLAUDE.md/AGENTS.md.
- No client names, credentials or confidential content in anything committed or posted.
- `~/.claude/commands/bin/repo-hygiene.sh --landed`, then `wt-clean`. Deleting a remote branch or a
  worktree wt-clean kept still needs confirmation.
- Ask every pending decision in one interactive question call, each with a recommendation.
- Print the continuation prompt in a fenced block:

```
/start then: <one-sentence mission>.
Re-derive before acting: `git -C <repo> fetch --prune && git status --porcelain && gh pr view <n> --json state,mergeable`.
Done: <3 lines max, each with its verify command>.
Not done: <each "blocked: <failing command>" or "not attempted">.
Decisions waiting: <each one approved command away, with a recommendation>.
Read first: master issue #<n>; PR #<n> checkpoint log.
```

- Prove each ask with a command: merge `gh pr view <n> --json state,mergedAt`; code `git branch -r
  --contains <sha>`; issue `gh issue view <n> --json state`; deploy a readback of the NEW behavior
  (absence of the old string passes on any error page). An unproven ask goes in "Not done".
- Last lines: branch, HEAD, PR URL + state, issues touched; any "deployed/live" claim needs a fresh
  readback of the NEW behavior from the serving system in this turn; then the `SAFE TO END:` line
  copied verbatim from the `--landed` run.

## Status format — banned: completion percentages

Never emit a percentage no command produces. Status is the pasted output of the done-criteria
checks (tests, lint, build, PR state, dirty files) plus what's next. With a real denominator, say
X of N.
