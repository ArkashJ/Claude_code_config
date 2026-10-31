---
description: Long-running autonomous run — phases with per-phase wraps, batched blockers, self-preservation before limits, adversarial review, then /wrap
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

## Wrap — a short one every phase, the full /wrap at the end

Each phase boundary:
- `git status --porcelain` empty: logical commits, pushed, PR current, scratch removed.
- Checkpoint-log line with a `verify:` certificate; route every `SURPRISE:`/`FALSIFIED:` line to a
  fix, an issue or an explicit discard.
- The step 2 dynamic QA lines of /wrap for what this phase changed (`--since <phase start>`).
- Master issue / PR comment: done, not done (`blocked: <cmd>` or `not attempted`), not read.

After the adversarial pass, run /wrap in full: it owns the release (one batched go), the
changelog, issues, hygiene, asks proven X of N, the continuation prompt and `SAFE TO END:`.

## Status format — banned: completion percentages

Never emit a percentage no command produces. Status is the pasted output of the done-criteria
checks (tests, lint, build, PR state, dirty files) plus what's next. With a real denominator, say
X of N.
