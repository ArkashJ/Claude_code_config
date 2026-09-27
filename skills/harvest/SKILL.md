---
name: harvest
description: Turn a session's mistakes into executable guards — scripts and build-failing tests, not another doc nobody reads. Use at the end of a session, after a review round, or whenever the same class of bug has bitten twice.
---

# Harvest

Harvest the learnings from this session (or a named scope) and convert them into things that
RUN. A lesson written into a document decays; a lesson written into a test fails a build.

`$ARGUMENTS` may name a scope (a PR range, a date, an issue, "this session"). Default: this session.

## Why this exists

The harvest that produced this command found **nine** defects in one session that shared a single
shape: **a check that reported success without having checked.**

- `os.MkdirAll` returns nil on a directory that already exists, whatever its ownership — so a
  retention feature "worked" for two days while not one file was ever stored.
- `waitForLoadState(...).catch(() => undefined)` discarded its own timeout, so a navigation helper
  returned onto a still-compiling page and reported success.
- `toBeHidden()` passed on content that is unmounted until opened — it passed on a page where the
  entire control did not exist.
- CI ran 1 test spec of 9 and called the suite green while it was 31 tests red.
- `| tail` and a trailing `echo` laundered exit codes, twice, in front of two different people.
- An ANSI-prefixed `31 failed` was invisible to a grep that matched `124 passed` — a clean,
  plausible, **half** answer.
- A content guard's *scope* excluded the one document that was wrong.
- A runbook comment claimed a gitignored file would protect you.

Three were written by the person harvesting them. Two were inside documents whose entire purpose
was preventing the thing they got wrong. **Documentation stopped none of them.**

That is the yield you are looking for. Not "we should be careful" — a command that cannot lie.

## Method

### 0. Read the transcript with a command, not with memory

```
python3 ~/.claude/skills/harvest/signals.py        # this session (Claude or Codex); or pass a .jsonl
```

It reduces the transcript with harness-extractor, has Jev judge every human turn in one fanned-out
request each (corrects / re-asks / doubts a claim / wants depth + failure area + what was asked),
and prints SIGNALS, TOOL FAILURES and ASKS with turn numbers. Exit 1 = a Jev request failed,
2 = unable to measure (0 turns read). Neither is "nothing to harvest".

Why it exists: a 2026-09-27 study of 187 deduped Claude+Codex sessions found every /harvest ran
from memory, and the next human turn was the correction: "are you sure thats ALL YOU LEARNT???"
(9fc47df2), "there were tons of mistakes no??" (b10f8486), "so you acted on those signals??"
(a Codex session). The transcript already held those mistakes.

Start the deliverable with the script's own counts: `N turns, S signals, R in the read band,
F tool failures, jev: Q requests / E errors / model`. That line answers "did you use jev?".
Read every turn in the 0.30–0.70 band yourself. Jev screens; you decide.
Across sessions (a repo's recent history, or "everything"): run `harness-extractor --repeats <files>`
over fork-deduped transcripts, and include only the mechanisms that recur.

### 0b. Carry each fix to its siblings, across repos: a calibrated Jev sweep

Every bug fixed this session is a pattern, and its siblings are in this repo and in other repos.
A notifications fix becomes "is the recipient list filtered by role?", asked at every notify call
everywhere. The machinery is `~/.claude/skills/qa/sweep.py` (see qa SWEEP). Per mechanism:

1. Add a family to `<repo>/.qa/families.json`. The extractor is code that finds every site (`grep` to
   the enclosing function, `py_except`, or `file`). The question is ONE narrow Noul whose `true`
   means the bug is present, and whose `score` is high for a finding.
2. Label the fix itself: `{"rev": "<fix-sha>^", "expect": true}` (the bug) and
   `{"rev": "<fix-sha>", "expect": false}` (the fix), plus any known-fine site.
3. `sweep.py calibrate <family> --repo <repo>` must PASS (positives >= 0.70, negatives <= 0.30),
   and every MISS line gets read. On FAIL, reword it: the narrowest deciding fact goes in the
   instructions, the reason a negative is fine goes in `criteria.false.not_for`. Missing evidence
   becomes a code-computed `facts` entry, not wording. Never loosen the gate.
4. `sweep.py run <family> --all-repos` sweeps every repo under `$HARVEST_REPO_ROOTS`.
5. Verify each flagged site by reading it. Real sites go into the step 6 ledger as fix or issue.
   Each false-positive class becomes a `not_for`, a new label, or a new question for next time.

Measured on repo A (2026-09-27), the port behaved like the original: 654 sites against 652,
0 errors, 26 s. Calibration caught a first wording at 0.69. A readiness-flag false-positive class
went from 0.81 to 0.60 once code supplied the cross-file fact. Flags fell from 35 to 13, and every
held-out bug scored >= 0.76. Precision is still low (3/26 and 14/57 in the original run), which is
why step 5 is not optional.

### 0c. Jev over the code this session touched, in this repo

Every session is fresh, so the end of each one is the only time its own changes get a deep look.
For React/TanStack code: `python3 ~/.claude/skills/qa/hunt.py <repo> --src <src> --since <session start>`
judges every hook surface in the files this session changed or left uncommitted, against the
generic checks and the repo's `.qa/invariants.json`. The session start is the `start` field in
the signals JSON. For backend code, run the /backend-edges Nouls on the endpoints whose files changed.
LEADs go into the step 6 ledger like any other signal. Known ceiling: hunt.py judges hook call
sites only, and says so by its surface count.

### 1. Gather the raw material — all of it, untruncated

Do not work from memory; memory keeps the story and drops the mechanism.

```
git log --oneline <range>                      # what actually landed
gh pr list --state merged --limit 30           # and what was reviewed
```

**Read every INLINE review comment, not just the top-level reviews.** They are a different API
and they are where the specific findings live:

```
gh api "repos/<owner>/<repo>/pulls/<n>/comments" --jq '.[] | "\(.path):\(.line) \(.body[0:300])"'
```

Count them first and state the total. In the session that produced this command, 15 inline
comments existed and 11 had never been read — including two P1s — because `gh pr view --json
comments` does not return them.

Also mine: your own corrections mid-session, anything you said and then retracted, every "actually,
that's wrong", and every command you had to run twice.

### 1b. Distrust the instrument before you distrust the corpus

When you measure a codebase or a corpus and the answer contradicts what the humans involved
believe, **the instrument is the first suspect, not the belief.** A measuring tool's blind spot
is indistinguishable from absence of the thing you are measuring.

Three ways this went wrong in one harvest (2026-08-10), all found only by cross-checking a number
against something already known:

- **The reduction logged tool NAMES without file paths.** Four sessions living in a directory
  literally called `doc_recon` — one running `Edit×11` against `docs/` — measured as **zero doc
  edits**. Two successive percentages (33%, then 55%) were computed and reported before anyone
  noticed the instrument could not see the phenomenon at all.
- **Forked sessions were counted twice.** Same run, two uuids, byte-identical to the millisecond.
  The metric was *cross-session recurrence*, so a fork manufactures exactly the signal being
  hunted. **Dedupe before counting recurrence**, always.
- **The denominator was contaminated.** "Command X ran in 6 of 109 sessions" became "25 of 51"
  once transcripts that *cannot* invoke a command were removed from the denominator. State what
  the denominator excludes, or the rate is fiction.

Cheapest catch, and it is nearly free: **point the instrument at a case whose answer you already
know.** A doc-audit metric that returns zero on the directory named after doc audits is broken —
that check costs one command and invalidates a whole synthesis.

### 1c. Make the findings machine-readable, or they are not findings

35 of 84 findings files in one corpus failed `yaml.safe_load` because a header packed
`repo: X    branch: Y` onto one line. Everything downstream had to `grep` instead of parse, so
every aggregate silently dropped whatever failed to load. If the deliverable is a corpus you
intend to query, **validating that it parses is part of writing it.**

### 2. Classify by mechanism, not by feature

Group by **how the failure hid**, not what it touched. Features are unique; mechanisms repeat.
"Three bugs in the export panel" teaches nothing. "Three checks that passed on absent input"
generates a guard that catches the fourth.

For each item, answer:
- **What reported success?** The specific call, flag, or line.
- **What did it not examine?**
- **What would have caught it?** If the answer is "reading more carefully", you have not found
  the mechanism yet. Keep going.

### 3. Rank by wasted time, not by severity

The goal is preventing recurrence, so rank by what the mistake **cost** — hours burned, wrong
conclusions published, work redone. A P3 that wasted four hours outranks a P1 caught in a minute.

### 4. Build. Prefer, in order:

1. **A script that makes the right thing easier than the wrong thing.** People do not adopt
   discipline; they adopt convenience. If the safe command is longer than the unsafe one, the
   unsafe one wins forever.
2. **A test that fails the build.** Source scans are legitimate — some defects live in how
   verification is *written*, where no runtime assertion can see them.
3. **A comment at the exact call site**, stating the mechanism and *why the obvious fix is wrong*.
4. **A doc.** Last resort. Nothing above was prevented by a doc.

Every artifact must carry **the incident that produced it**, concretely, with the real numbers.
`// don't swallow timeouts` gets deleted by the next person. `// this discarded its own timeout
and a retention feature silently did nothing for two days` does not.

### 5. Prove each guard bites

**A guard that has never failed is indistinguishable from one that cannot fail** — which is the
very defect class you are harvesting. For each one: break the thing it guards, watch it fail,
restore, watch it pass. Report both observations. If a guard passes on first write, be suspicious
of it rather than pleased.

Against an *intermittent* failure a single green run proves nothing — reproduce the **mechanism**
instead (shrink a timeout, force the error branch, point it at a surface where the thing genuinely
does not exist).

### 6. Act on every signal: a ledger, X of N

Every SIGNAL and every non-trivial tool-failure shape gets exactly one disposition:
`guard` (committed, with bite proof) · `fix` (commit/PR link) · `issue` (URL) · `memory`
(behavioural only, no code can check it) · `discard: <reason>`. Report `acted X of N`. A signal
without a row counts as not acted on. "So you acted on those signals??" was asked
after a harvest whose findings were only a report.

## Deliverable

1. The counts line from step 0.
2. A short table: mechanism → instances (turn numbers) → artifact built → proof it bites.
3. The disposition ledger, `acted X of N`, plus the artifacts, committed and pushed.
4. **What you chose not to build and why.** A harvest that produces nine guards for nine incidents
   has probably built noise; the mechanisms should collapse into far fewer.

## With /wrap (the usual case)

Harvest is almost always invoked together with wrap ("do a /harvest and /wrap"). The order is
harvest first, then wrap. Harvest builds and commits its guards but never merges, deploys or
cleans up; those belong to wrap. Any signal left undispositioned goes into wrap's "Not done"
list in the handoff prompt, never silently dropped. Decisions that need the human (merge
bypasses, deletions, product choices) are asked with the interactive question tool, all at
once, not as a prose list. "ask all interactively!!" was a correction in 3 sessions.

## Rules

- Include your OWN mistakes, first and in detail. A harvest that only indicts other people's code
  is a performance. The most valuable entries are the ones where the harvester was wrong.
- Never claim a guard works because you wrote it carefully. Show it failing.
- **Check the invariant you care about, not a proxy for it.** A bulk repair of 86 YAML files was
  guarded by "the word count must not change". It passed — twice — while the transform treated
  the word `stale:` inside prose as a new key and rewrote `recurring: true  # note` into the
  *string* `"true # note"`. Every word survived; the meaning did not. The right guard was
  "`recurring` must still be a bool in all 532 records", which takes the same one line and
  actually fails. A proxy guard is the defect class in this skill's own title: a check that
  reported success without having checked.
- Do not write a guard whose failure message does not say what to do next.
- Do not turn a one-off into a framework. If a mechanism occurred once and cost ten minutes,
  a comment is the correct artifact.
- Never let the harvest itself launder a result: read exit codes without a pipe, strip ANSI before
  grepping any pass/fail count, and state untruncated totals before any conclusion.
