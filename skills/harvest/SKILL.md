---
name: harvest
description: Turn a session's mistakes into executable guards — scripts and build-failing tests, not another doc nobody reads. Use at the end of a session, after a review round, or whenever the same class of bug has bitten twice.
---

# Harvest

Convert this session's mistakes (or a named scope: `$ARGUMENTS` = PR range, date, issue) into
things that RUN. A lesson in a doc decays; a lesson in a test fails a build. The defect class to
hunt is **a check that reported success without having checked**: `MkdirAll` returning nil on an
existing dir, a `.catch(() => undefined)` that ate its own timeout, `toBeHidden()` passing on an
unmounted control, CI running 1 spec of 9, `| tail` laundering an exit code, an ANSI-prefixed
`31 failed` invisible to a grep.

**Don't create upkeep.** Most sessions need no new guard. Build one only for a mechanism that
recurs and costs real time; prefer fixing the existing verification path. Steps 0b/0c run only
for a requested audit or a demonstrated shared mechanism.

## 0. Read the transcript with a command, not memory

```bash
python3 ~/.claude/skills/harvest/signals.py        # this session (Claude or Codex); or pass a .jsonl
```

Jev judges every human turn (corrects / re-asks / doubts a claim / wants depth, plus failure area
and the ask) and prints SIGNALS, TOOL FAILURES and ASKS with turn numbers. Exit 1 = a Jev request
failed, 2 = unable to measure (0 turns). Neither means "nothing to harvest".

Open the deliverable with its counts: `N turns, S signals, R in the read band, F tool failures,
jev: Q requests / E errors / model`. Read every turn in the 0.30–0.70 band yourself.

Cross-session scope: `harness-extractor --repeats <files>` over fork-deduped transcripts; keep
only mechanisms that recur. Classify files first: subagent and guardian transcripts dominate raw
counts (1,526 of 1,603 Claude files were subagents). Count failures from output text too:
playwright-cli exits 0 on `### Error`.

## 0b. Carry a fix to its siblings: a calibrated sweep (`~/.claude/skills/qa/sweep.py`)

1. Add a family to `<repo>/.qa/families.json`: an extractor in code that finds every site, and ONE
   narrow Noul whose `true` means the bug is present.
2. Label the fix: `{"rev": "<fix-sha>^", "expect": true}`, `{"rev": "<fix-sha>", "expect": false}`,
   plus any known-fine site.
3. `sweep.py calibrate <family> --repo <repo>` must PASS (positives ≥ 0.70, negatives ≤ 0.30);
   read every MISS. On FAIL, reword: the deciding fact goes in the instructions, why a negative is
   fine goes in `criteria.false.not_for`, missing evidence becomes a code-computed `facts` entry.
   Never loosen the gate.
4. `sweep.py run <family> --all-repos`, then read every flagged site. Precision runs 3/26–14/57,
   so reading is not optional. Real sites go in the step 6 ledger; each false-positive class
   becomes a `not_for`, a label, or an extractor fix.

## 0c. Jev over the code this session touched

React/TanStack: `python3 ~/.claude/skills/qa/hunt.py <repo> --src <src> --since <session start>`
(start = the `start` field in the signals JSON). Backend: have Jev judge each changed endpoint
and write a failing test per real gap. Then every calibrated family on the same files:
`sweep.py run <family> --repo <repo> --since <session start>`. hunt.py judges hook call sites
only, and its surface count says so.

## 1. Gather all of it, untruncated

```bash
git log --oneline <range>
gh pr list --state merged --limit 30
gh api "repos/<owner>/<repo>/pulls/<n>/comments" --jq '.[] | "\(.path):\(.line) \(.body[0:300])"'
```

Inline review comments are a separate API that `gh pr view --json comments` does not return
(11 of 15 once went unread, two of them P1). State the total before reading. Also mine your own
retractions, every "actually, that's wrong", and every command you ran twice.

## 1b. Distrust the instrument first

When a measurement contradicts what the humans believe, suspect the instrument. Point it at a case
whose answer you know (a doc-edit metric that returns zero on a dir named `doc_recon` is broken).
Dedupe forked sessions before counting recurrence. State what the denominator excludes.

## 1c. Machine-readable findings

A findings corpus you intend to query must parse: validate it as part of writing it.

## 2. Classify by mechanism, not feature

For each item: what reported success? What did it not examine? What would have caught it? "Read
more carefully" means the mechanism is not found yet.

## 3. Rank by wasted time, not severity

A P3 that burned four hours outranks a P1 caught in a minute.

## 4. Build, in this order of preference

1. A script that makes the right thing easier than the wrong thing.
2. A test that fails the build (source scans are fine when the defect lives in how verification
   is written).
3. A comment at the call site stating the mechanism and why the obvious fix is wrong.
4. A doc, last.

Every artifact names its incident with real numbers; a bare "don't swallow timeouts" gets deleted.

## 5. Prove each guard bites

Break the guarded thing, watch the guard fail, restore, watch it pass; report both. Suspect a
guard that passes on first write. For an intermittent failure, reproduce the mechanism (shrink
the timeout, force the error branch) instead of trusting one green run.

## 6. Ledger: act on every signal, X of N

Each SIGNAL and non-trivial tool-failure shape gets one disposition: `guard` (committed, bite
proof) · `fix` (commit/PR) · `issue` (URL) · `memory` (behavioral, no code can check it) ·
`discard: <reason>`. Report `acted X of N`; a signal without a row is not acted on.

## Deliverable

1. The counts line from step 0.
2. Table: mechanism → instances (turn numbers) → artifact → bite proof.
3. The ledger, `acted X of N`, artifacts committed and pushed.
4. What you chose not to build, and why. Nine guards for nine incidents is noise: mechanisms
   should collapse into far fewer.

## With /wrap

Harvest first, then /wrap. Harvest commits guards but never merges, releases, deploys or cleans
up; /wrap owns those. Undispositioned signals go into /wrap's "Not done". Decisions for the human
are asked with the interactive question tool, all at once, inside /wrap's step 4 question.

## Rules

- Your own mistakes first and in detail; the harvester's errors are the most valuable entries.
- Check the invariant, not a proxy: "word count unchanged" passed twice while a YAML repair turned
  `recurring: true  # note` into a string; "`recurring` is a bool in all 532 records" fails.
- A guard's failure message says what to do next.
- A one-off that cost ten minutes gets a comment, not a framework.
- Never launder the harvest's own results: no pipe on exit codes, strip ANSI before grepping
  counts, untruncated totals before any conclusion.
