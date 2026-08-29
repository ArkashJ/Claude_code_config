---
name: frontend-verify
description: Use when a frontend is "done" but not trusted - when a feature was built and claimed working but data does not load, one page shows stale values after another page saved, or the last 20% before launch is being burned clicking through screens by hand. Inventories every route and its data dependencies, finds the defect classes that are decidable without a browser, then drives the real app against universal runtime invariants and exits non-zero. Triggers on "verify the frontend", "why does page B still show the old value", "half the data does not load", "QA before launch", "prove this works", "find what is broken before I click through it". Not for visual taste (design-director), not for building UI (impeccable), not for one screen's states (ui-stress).
---

# frontend-verify

## The problem this exists for

Every other frontend tool produces an **observation**: a screenshot, a snapshot,
a console log, a probe result. None produces an **expectation**. An observation
cannot fail, so a loop built from observations terminates on "it looked right",
and the two defect classes that dominate the last 20% before launch survive it
untouched:

- **Cardinality defects** — 14 rows rendered where 17 belong. Pixel-perfect.
- **Identity defects** — page B holds a copy of what page A just changed.

Both render as beautiful pages with wrong contents. No design pass, no visual
diff, and no amount of clicking finds them reliably.

**The fix is not more test cases.** Cases are authored per feature, so coverage
grows only as fast as you write it, and the next thing you prompt into existence
is uncovered. This skill enumerates **invariants** instead: properties that hold
on every route forever, written once, applying to code that does not exist yet.

## Assert at the boundary that does not change

Types, store patterns and framework idioms are per-stack; everything asserted
above the browser gets rebuilt every time you switch. A console error, a failed
request, an `undefined` in the DOM and a stale cache entry are identical in
Next, Vite, Remix, TSX-on-a-CDN and whatever is next. Anchor there and the work
transfers at zero cost.

## Run order

Cheapest and most exhaustive first. Do not open a browser to learn something a
file read can tell you.

**Pass the repo as an absolute path.** The skill lives in `~/.claude/skills/` and
is run against many repos; nothing resolves against the current working
directory, so it cannot matter where your shell happens to be.

```bash
S=~/.claude/skills/frontend-verify
R=/abs/path/to/the/repo        # the repo under test

# 1. INVENTORY — what exists, what reads what, what goes stale when.  (seconds, no browser)
node $S/bin/inventory.mjs "$R"

# 2. CLASSIFY — the defect classes decidable from source alone.        (seconds, no browser)
node $S/bin/classify.mjs "$R"

# 3. SWEEP — drive every route against the universal invariants.       (minutes, app must be running)
node $S/bin/sweep.mjs --repo "$R" --base http://localhost:3000

# 4. GATE — the exit code IS the definition of done.
```

### Where everything lives

| | Path | Scope |
|---|---|---|
| The tools, `SKILL.md`, `references/atlas.md` | `~/.claude/skills/frontend-verify/` | **global** — installed once, identical for every repo |
| `inventory.json`, `classify.json`, `sweep.json` | `<repo>/.verify/` | **per-repo** — written beside the repo analysed, never into your cwd |

The atlas is reference material for the tool, so it stays global; findings are
facts about one codebase, so they stay with it. Add `.verify/` to the repo's
`.gitignore` unless you want the reports reviewed in PRs — committing them turns
each run into a diff, which is a reasonable choice for a repo heading to launch.

Add `--stdout` (inventory) or `--json` (classify) to pipe instead of writing.

Read `.verify/inventory.json` before writing any test. `syncRisks` is the
cross-page staleness bug located statically, with its blast radius; a P1 there
names the hook, the endpoint, and every route that goes stale when it runs.

## What each phase can and cannot see

| Phase | Sees | Blind to |
|---|---|---|
| `inventory.mjs` | routes, per-route data deps, mutations, entity→route matrix, sync risks, duplicate cache keys | anything conditional at runtime |
| `classify.mjs` | missing empty/error/loading branches, server state in client stores, stale closures, unaborted effect fetches, build-time env read at runtime, index keys, unsanitized HTML, unguarded submits | whether the code actually runs |
| `sweep.mjs` + `probe.js` | console errors, failed requests, HTTP 4xx/5xx, hydration mismatch, chunk-load failure, CSP violations, DOM value leaks, stuck spinners, empty lists with no empty state, horizontal scroll, tap targets, long tasks, CLS, LCP, layout thrash, request waterfalls, heap retained across navigation | business intent |
| you | "this total must equal the sum of that column" | everything above, reliably |

That last row is the only part a human must supply, and it is **one question per
entity**, not per feature.

## The invariants the sweep enforces

Every route, every run, no authoring:

1. Zero console errors, page errors, unhandled rejections
2. Zero failed same-origin requests; zero unexpected 4xx/5xx
3. No hydration mismatch, no chunk-load failure, no CSP violation
4. Root renders non-empty text
5. No loading indicator still mounted after settle
6. No list with zero rows and no empty state
7. No `undefined` / `NaN` / `[object Object]` / `Invalid Date` / unresolved template var in the DOM
8. No horizontal scroll at the tested width
9. Interactive elements >= 24px (screen-reader-only elements excluded)
10. Every control has an accessible name
11. Longest task < 200ms, CLS < 0.1, LCP < 2500ms
12. No dependent request chain 3 deep
13. (opt-in `--leak-check`) heap returns after GC across repeated navigation

## Readiness, not networkidle

`domcontentloaded` fires before client-rendered content exists, and a gate that
captures there measures nothing while still occupying the verification slot —
worse than no gate, because it reports green. `networkidle` never arrives under
long polling, websockets or background refetch. The sweep waits for the root to
have text, then settles. Keep it that way.

## Precision is the product

Every rule here was tuned against real repos until its false-positive rate hit
roughly zero, because a report with noise in it stops being read, and a tool
that is not read is worse than no tool. When adding a rule:

- Run it on a real repo before committing it. Open the top three hits and
  confirm each is genuinely a defect.
- A wrapper hook that returns its query is not ignoring the error — its caller
  reads it. Follow one level of indirection before flagging.
- Screen-reader-only elements are 1x1 by design. Measuring them as tap targets
  is how a ticket claims 103 failures and a browser finds one.
- JSON-LD blocks are serialized data, not markup.
- Prefer a miss to a false positive. A miss surfaces later; a false alarm costs
  the reader's trust the first time they open the file and find nothing wrong.

## Prove the probes fire

```bash
bash ~/.claude/skills/frontend-verify/selftest-static.sh   # no browser needed
bash ~/.claude/skills/frontend-verify/selftest.sh          # needs Playwright in reach
```

Both serve a fixture carrying one planted instance of each class and assert every
one is found, plus that the known false positives stay silent. **Run these after
any edit to a rule.** A rule that silently stops matching keeps reporting green.

## Wiring the gate

Done is an exit code, not a sentence. Add to `.claude/settings.json`:

```json
{ "hooks": { "Stop": [{ "hooks": [{ "type": "command",
  "command": "node ~/.claude/skills/frontend-verify/bin/classify.mjs . || echo 'BLOCKED: P0/P1 findings — see above' >&2" }] }] } }
```

The agent cannot end a turn claiming done while that exits non-zero.

## The loop that ends the clicking

Every bug you still find by hand becomes a rule **once**:

1. Reproduce it.
2. Add the rule to `classify.mjs` (static) or `probe.js` (runtime).
3. Plant an instance in the matching fixture and confirm the selftest catches it.
4. Fix the bug.

Clicking hours currently produce nothing durable, which is why they recur on
every project. Under this rule each one permanently retires a defect class
across every repo you own, and the manual pass asymptotes toward zero.

## References

- `references/atlas.md` — the full failure taxonomy, 11 layers, each class keyed
  to its detection method. Rule IDs in tool output (`L4.36`) index into it.
