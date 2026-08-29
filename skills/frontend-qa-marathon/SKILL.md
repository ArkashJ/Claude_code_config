---
name: frontend-qa-marathon
description: Hours-long autonomous frontend QA - study every feature in the repo, author journeys for each, then loop test-fix-retest until the gate is green and the feature ledger is fully checked. Use when the user wants "automated testing for hours", "test the whole app", "find and fix every frontend bug", "QA marathon", or continuous testing with Playwright and agents. Orchestrates frontend-verify (the gate), playwright-cli (ad-hoc browser work), and ui-stress (per-screen states); not for a single quick check (run frontend-verify's verify.sh directly).
---

# frontend-qa-marathon

The tools already exist; this skill is the discipline for driving them for
hours without drifting, lying, or looping. The definition of done is **two
artifacts, not a feeling**: `verify.sh` exits 0, and every row of the feature
ledger is checked off.

## Phase 0 — preconditions (5 minutes, refuse to skip)

1. App running (`--base` reachable), **dev database** confirmed — the marathon
   submits real forms. Never run `--mutate` against anything shared.
2. Clean git branch. Every fix lands as its own commit; a wrecked run must be
   revertible per-fix.
3. Auth: if any route redirects to login, capture storage state FIRST
   (`npx playwright codegen --save-storage=.verify/auth.json <base>` or ask the
   user for credentials once). A sweep that reaches 6/49 routes is not a
   marathon, it is a lap of the parking lot — the Profectus run proved exactly
   this shape.
4. `bash ~/.claude/skills/frontend-verify/selftest-static.sh` and
   `selftest.sh` pass — the instruments are calibrated before the flight.

## Phase 1 — study the features (read, don't browse)

Run `node ~/.claude/skills/frontend-verify/bin/inventory.mjs <repo>` and read
`.verify/inventory.json`. Then write `.verify/ledger.md` — the contract for the
whole run — one row per route:

```
| route | entities | mutations | forms | journey | swept | stressed | status |
```

- `status` starts `untested` for every row. Legal values:
  `untested → journeyed → swept → stressed → clean | bug:<finding-id> → fixed`
- Dynamic routes (`/:id`) get a **seed note**: which record the journey will
  create or look up. The sweep skips them by design; the ledger must not.
- Read the page source of every route with mutations. You are studying what
  each feature *claims* to do; the marathon tests those claims, not vibes.

**Enumeration discipline**: the ledger row count must equal
`inventory.counts.routes`. State both numbers. A ledger built from a truncated
list tests a sample and reports a total.

## Phase 2 — author journeys (one per feature, three lines each)

For every ledger row with a form or mutation, add a journey to
`<repo>/verify.journeys.mjs` (format in frontend-verify's SKILL.md). Rules:

- The journey performs the feature's ONE core flow: create/edit/delete, then
  client-side-navigate to wherever the result should appear. The harness
  asserts the 18 invariants automatically; the journey only supplies intent.
- Seed data the journey needs, create inside the journey — never depend on
  yesterday's database.
- Add the one business assertion per entity ("total equals sum of rows") as an
  explicit `expect` inside the journey. This is the irreducible human part;
  the study in Phase 1 is where you learned what it should be.
- Use `playwright-cli` interactively to discover selectors; the *durable*
  output is the journey file, not the session. Browsing that leaves no journey
  behind is the clicking this system exists to end.

## Phase 3 — the loop (this is the "hours" part)

```
while true:
  bash ~/.claude/skills/frontend-verify/verify.sh <repo> \
       --base <url> --auth .verify/auth.json --mutate --ratchet --quiet
  exit 0 → break
  read the reports, pick the TOP finding (P0 first, then P1, then count)
  fix the ROOT CAUSE: grep every caller before editing; one guard in the
    shared function beats N guards at N call sites
  commit that one fix; update the ledger row (bug:<id> → fixed)
  if you touched classify.mjs/probe.js/sweep.mjs: both selftests must pass
  rerun. RATCHET failure → revert the last commit, try the next finding.
```

- **Pace with ScheduleWakeup/`/loop`, never sleep-poll.** Long sweeps run in
  the background; a 20-route sweep deserves one check when it finishes, not
  sixty while it runs.
- Checkpoint every ~45 minutes: commit, one-line ledger summary
  ("31/49 clean, 3 bugs fixed, 2 open"). Numbers, not adjectives.
- A finding you decide is a false positive is not ignored — it goes through
  frontend-verify's rule loop (fix the rule, plant the counter-example, run
  the selftest) or it stays on the ledger as open. No third bucket.

## Phase 4 — state stress (after the gate is green, not before)

For the ledger's top ~10 routes by mutation count, run `ui-stress` (empty /
one / many / error / slow / 320px / dark). Bugs found here re-enter Phase 3's
loop. Skipping this on green is acceptable for a short run; mark the ledger
column `-` rather than falsely `stressed`.

## Fan-out (optional)

Independent bugs on disjoint routes can go to parallel agents — each gets one
ledger row, must run the full gate before reporting, and reports a commit hash
or "blocked", nothing else. Never parallelize edits to the same store/hook:
two agents fixing one cache produce a third bug. The lead re-runs the gate
after merging; agents' green claims are inputs, not results.

## Exit report

The final message states: routes total / clean / fixed (with commit hashes) /
still open (with finding ids), the ratchet's best-count trajectory, and which
ledger columns were skipped. `verify.sh` exit code quoted verbatim. If the
gate is red at hand-off, the first word of the report is FAIL.
