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

## What this is, and is not

A **supplement** to typechecking, linting, application tests, app-owned
Playwright journeys and visual regression — not their replacement. It automates
the layer none of those cover (universal runtime invariants, cross-page cache
coherence, the defect classes decidable from source), and it hands business
intent back to you as one question per entity. It does not fix bugs: it emits
file/line findings and a non-zero exit code, and the agent driving it patches
the root cause and reruns the gate — detection and repair stay separate on
purpose, because a tool that grades its own fixes is a tool that learns to
grade generously. Static rules are heuristic (regex + import graph, not an AST
— see the header of `inventory.mjs` for the trade); the runtime invariants are
measured, not inferred.

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

# Everything, in order, cheapest first:
bash $S/verify.sh /abs/path/to/repo                                  # static only, seconds
bash $S/verify.sh /abs/path/to/repo --base http://localhost:3000     # + the runtime sweep
```

Exit: **0** clean · **1** P0/P1 findings · **2** could not run. That exit code is
the definition of done — it is what a Stop hook, a pre-commit hook, or CI reads.

`--auth state.json` for a gated app, `--width 390` for mobile, `--quiet` for
hooks, `--ratchet` inside a fix loop, and `--mutate` (**destructive**, dev DB
only) to prove sync risks at runtime by driving real forms.

Run a phase on its own when you want just that one:

```bash
node $S/bin/inventory.mjs "$R"                                   # routes, data deps, sync graph
node $S/bin/classify.mjs  "$R"                                   # source-decidable defects
node $S/bin/sweep.mjs --repo "$R" --base http://localhost:3000   # runtime invariants
```

**Exit 2 is not a pass.** Zero routes, zero swept pages, or a sweep that could not
start all exit 2 rather than 0 — a run that measured nothing must never read as
green, which is the failure this whole skill exists to prevent.

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
| `inventory.mjs` | routes, per-route data deps, mutations, entity→route matrix, sync risks (no invalidation AND wrong-key invalidation), duplicate cache keys | anything conditional at runtime |
| `classify.mjs` | missing empty/error/loading branches, server state in client stores, stale closures, unaborted effect fetches, build-time env read at runtime, index keys, unsanitized HTML, unguarded submits | whether the code actually runs |
| `sweep.mjs` + `probe.js` | console errors, failed requests, HTTP 4xx/5xx, hydration mismatch, chunk-load failure, CSP violations, DOM value leaks, stuck spinners, empty lists with no empty state, data fetched but zero rows rendered, horizontal scroll, tap targets, unlabeled controls and fields, long tasks, CLS, LCP, layout thrash, request waterfalls, heap retained across navigation | business intent |
| `--mutate` replay | whether a real write through a real form leaves a blast-radius route stale under client-side navigation | which payload a form considers valid |
| your journeys (`verify.journeys.mjs`) | create/update/delete flows, dynamic routes, role gates — scripted once, then swept under every invariant above | — |
| you | "this total must equal the sum of that column" | everything above, reliably |

Router recognition is Next (app + pages), react-router/route-config literals,
and `src/routes` file conventions. Anything else inventories **zero routes and
exits 2** — inconclusive, never a pass.

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
7. No API response whose records exist while every list renders zero rows
8. No `undefined` / `NaN` / `[object Object]` / `Invalid Date` / unresolved template var in the DOM
9. No horizontal scroll at the tested width
10. Interactive elements >= 24px (screen-reader-only elements excluded)
11. Every control has an accessible name (buttons, links, AND form fields)
12. Longest task < 200ms, CLS < 0.1, LCP < 2500ms — measured by observers
    installed **before navigation**; unmeasured is reported as unmeasured, never
    as clean
13. No interactive element whose center another element covers — clicks that
    land on an invisible overlay (open dialogs and `pointer-events:none`
    excluded)
14. No `SameSite=None` cookie without `Secure` — the browser rejects it, auth
    silently vanishes
15. No resource preloaded and never used (Chrome's own diagnostic, exact-matched)
16. No dependent request chain 3 deep
17. (opt-in `--leak-check`) heap returns after GC across repeated navigation
18. (opt-in `--mutate`) after a successful write, every blast-radius route either
    refetches or shows the new value under client-side navigation

The sweep is hardened for long runs: it liveness-checks the dev server before
every route (a dead server is one exit-2, not forty fake findings), retries a
dropped route once and marks a pass-on-retry `route.flaky` instead of clean, and
writes `sweep.json` incrementally so hour three cannot destroy hours one and two.

## Journeys: the app's flows, the skill's harness

A universal journey generator is brittle over-engineering — inventing what a
form "should" accept is guessing at intent. So the split is: **you script the
flow once, the harness supplies everything else.** Drop `verify.journeys.mjs`
at the repo root (committed, unlike `.verify/`):

```js
export default [
  { name: 'create-invoice', start: '/invoices', run: async (page, { base }) => {
      await page.fill('[name=amount]', '42');
      await page.click('button[type=submit]');
      await page.click('a[href="/invoices"]');
  }},
];
```

Each journey runs under the full console/network listeners, and wherever it
ends up gets the whole probe — so a journey is three lines of clicks, and the
fourteen invariants above are asserted for free at every step's destination.
This is how dynamic routes (`/invoices/:id`), role gates and CRUD flows get
covered: the journey knows a real id; the sweep never guesses one. A journey
that throws is a P0 (`journey.failed`), not a skipped test.

`--mutate` is the zero-authoring fallback for sync risks specifically: it fills
the mutation route's form with sentinel values, submits, client-side navigates
to each statically-computed stale route, and files `sync.stale-after-write` P0
only when the write succeeded AND no refetch happened AND the sentinel is
absent. A validation-rejected submit is reported as unverified, never as a
defect — the app's reaction to synthetic input is not a finding.

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
- Say how strong the claim is. "This write leaves route X stale" and "I could not
  determine what goes stale" are different assertions; filing both at one severity
  makes the strong one look as soft as the weak one. `unresolved: true` marks it.
- A finding repeated across N routes is usually one finding about the surface all
  N of them landed on. Check the denominator counts routes, not cells.

## Structural tells that a run is an artifact

The costliest failures are not wrong rows, they are confident numbers produced by
a harness that never measured the thing. Every one of these was caught by shape,
not by reading any individual finding:

| Tell | What it means |
|---|---|
| Identical output across deliberately different inputs | The experiment never ran. The differential check in `selftest.sh` exists for exactly this. |
| One selector or surface repeated across N routes | N routes landed on the same page — auth redirect, not-found shell — and got measured under their own names. |
| `modules: 1` on every route in the inventory | The import walk resolved nothing at hop 1. Aliases are wrong; the app is not "clean". |
| A count that is a multiple of the file count | Per-route sums counting shared modules once per route. |
| Zero of something a grep finds hundreds of | The matcher missed a wrapper, a generic, or a path alias. Grep before believing a zero. |

When a number looks decisive, check its denominator before publishing it.

## Prove the probes fire

```bash
bash ~/.claude/skills/frontend-verify/selftest-static.sh   # no browser needed
bash ~/.claude/skills/frontend-verify/selftest.sh          # needs Playwright in reach
```

The static selftest plants one instance of **all 16 classifier rules** (a meta
check fails the suite if a 17th rule is added without a plant), the wrong-key
and no-invalidation sync risks, the wrapper/monorepo/generics traversal shapes,
and the known false positives that must stay silent. The runtime selftest plants
20 finding kinds in the fixture, asserts the dedup invariants (one 404 = one
finding; classified console texts do not double as `console.error`), runs a
differential check (distinct inputs must yield distinct output), and drives the
journey and `--mutate` engines against a two-variant SPA — the stale variant
must be flagged, the fixed one must not. Not planted (still trust-but-unproven):
real hydration/chunk/CSP events (their console *classification* is tested via
planted text, not provoked browser events), LCP-over-threshold, redirects/auth,
and the leak check. **Run both after any edit to a rule.** A rule that silently
stops matching keeps reporting green.

## Wiring the gate

Done is an exit code, not a sentence — **and the exit code must survive the
wiring.** `verify.sh ... || echo BLOCKED` returns echo's 0 and waves every
failure through; that exact bug shipped in an earlier version of this section.
A Stop hook blocks on exit 2, so re-exit explicitly:

```json
{ "hooks": { "Stop": [{ "hooks": [{ "type": "command",
  "command": "bash ~/.claude/skills/frontend-verify/verify.sh \"$CLAUDE_PROJECT_DIR\" --quiet || { echo 'BLOCKED: frontend-verify found P0/P1 findings — run it without --quiet to see them' >&2; exit 2; }" }] }] } }
```

In CI and pre-commit hooks, run `verify.sh` bare — its own exit status is the
gate; anything appended after `||` must end in `exit 1` or the pipeline reads
green. Pass `--base` against the preview deployment in CI so the runtime half
runs too.

The agent cannot end a turn claiming done while that exits non-zero.

## The fix loop, and its ratchet

Hours-long autonomous runs are an agent driving this tool, not a feature of it:

```
run verify.sh --ratchet →  exit 0? done.
  → pick the top finding → fix the ROOT CAUSE (grep every caller first)
  → selftests still pass → rerun verify.sh --ratchet → repeat
```

Two rules keep the loop honest, and both are enforced, not aspirational:

- **The detectors are not the patient.** After any edit to `classify.mjs`,
  `probe.js` or `sweep.mjs`, both selftests must pass — a "fix" that blinds a
  rule is caught by its planted instance.
- **`--ratchet`: total findings never increase.** A fix that trades one finding
  for two exits 1 with `RATCHET`, and the right response is revert-and-retry,
  not argue. The baseline (`.verify/ratchet.json`) tightens itself on every
  improvement; delete it only to knowingly accept a regression.

## The loop that ends the clicking

Every bug you still find by hand becomes a rule **once**:

1. Reproduce it.
2. Add the rule to `classify.mjs` (static) or `probe.js` (runtime) — or, if it
   is a flow bug, three lines in `verify.journeys.mjs`.
3. Plant an instance in the matching fixture and confirm the selftest catches it.
4. Fix the bug.

Clicking hours currently produce nothing durable, which is why they recur on
every project. Under this rule each one permanently retires a defect class
across every repo you own, and the manual pass asymptotes toward zero.

## References

- `references/atlas.md` — the full failure taxonomy, 11 layers, each class keyed
  to its detection method. Rule IDs in tool output (`L4.36`) index into it.
