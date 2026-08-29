---
name: ui-stress
description: Use when a UI must be tested against the states and content it will actually meet in production - empty, one, many, loading, error, permission-denied, slow, long text, broken image, 320px, dark mode - rather than the happy path it was built against. Triggers on "find the UI bugs", "test every state", "QA this screen", "why does it break with real data", "the empty state is broken", "it overflows on mobile", and on any codebase that has accumulated many UI defects and needs a systematic sweep instead of one-off fixes. Not for visual taste or design identity (use design-director), and not for building or redesigning UI (use impeccable).
---

# UI Stress

## The rule that makes this cheap

**Probe before you look.**

A script can tell you a button is 18px tall, that the page scrolls sideways at
390px, that a modal covers the submit button, that a list renders empty with no
message. That costs no tokens. Vision is for the residual — is this readable,
does the user have a next step, does the hierarchy hold.

Most UI-testing attempts invert this: build a harness page, screenshot
everything, eyeball it. That burns the entire budget on cells a script would
have cleared in milliseconds, so the sweep stays small and most states never get
rendered at all.

Probes are free. **Ration screenshots, never probes.** A sweep of 6 routes × 6
states × 2 widths is 72 probe runs, seconds of wall time, and it is the right
size for a first pass.

## Where this sits

| Skill | Its job |
|---|---|
| `design-director` | Which surfaces exist, and what good looks like (`DESIGN.md`, the survey) |
| `impeccable` | Building and redesigning the UI |
| `playwright-cli` | The browser transport — sessions, `route`, `run-code`, `vcheck` |
| **`ui-stress`** | **What happens to those surfaces under content and states nobody built for** |

Every other tool walks the app logged-in, data-present, network-fine, desktop.
The bugs live in the states none of them render. That is this skill's territory.
Severities are `P0`–`P3` matching design-director, so findings append cleanly to
a `DESIGN-AUDIT.md`.

## Phase 0 — Reuse before you build

Do not construct fixtures that already exist.

- `*.stories.*`, Storybook, Ladle, Histoire → **that is the state catalog.** Sweep
  its iframe URLs. Never rebuild it.
- MSW handlers, fixtures, seed scripts, `__mocks__` → the state data already exists.
- `.vcheck/` baselines → the regression lock already exists; extend it.
- `DESIGN.md` or CSS custom properties → the token palette, which turns
  `off-token-color` from noise into a contract violation.

Build a harness page **only** for a design-system package with no stories, or
when the user names one component. For an app, the real routes are strictly
better evidence: they exercise real composition, routing, and data flow.

## Phase 1 — Enumerate the matrix

Pick surfaces by blast radius, not by what is convenient: routes on a money,
auth, or write path; components imported in the most places (count the imports);
whatever git touched most recently.

Then read `references/state-matrix.md` and derive states from what each surface
**actually accepts** — its props, its API calls, its query params. Skip cases a
surface cannot receive. Do not pad the matrix to look thorough.

Cap the cross product. Default sweep: every state at **390px**, then re-run only
the passing cells at **1440px**, and add dark mode only where the project
supports it. A full states × widths × themes cross product is waste.

## Phase 2 — Force and probe

Three engines, in yield order. Exact commands are in `references/state-matrix.md`.

1. **Network forcing** — `playwright-cli route` returns empty / one / many / 500 /
   403 / slow / malformed to the real screen. Highest yield: this is where the
   missing empty states and unhandled errors are.
2. **Content stress** — mutate the live DOM: multiply text ×5, inject an
   unbreakable 60-character string, break every image `src`, inflate numbers. No
   fixtures required, and it stresses the real layout.
3. **Viewport and theme** — resize, toggle `prefers-color-scheme`.

Probe every cell:

```bash
playwright-cli -s=stress run-code "$(cat ~/.claude/skills/ui-stress/probe.js)"
```

Returns JSON: findings grouped by rule, severity-sorted, three examples each.
It detects horizontal overflow (and names the culprit element), clipped text,
interactive elements covered by overlays, sub-24px targets, zero-size focusables,
placeholder-only labels, broken images, containers that render empty with no
message, dead-end screens with no text and no action, missing focus indicators,
off-token colours, plus the full axe-core ruleset when the CDN is reachable.

Record `route · state · viewport · theme` with every result, or the findings are
not reproducible and therefore not actionable.

## Phase 3 — Triage before reporting

- **Deduplicate.** The same rule at the same selector across 40 cells is **one**
  systemic finding with a count — never 40 rows. One fix closes all of them.
- **Rank** by severity, then instance count.
- **Now** screenshot — only the cells with P0/P1 findings, plus a sample of clean
  cells as evidence. Read them as one contact sheet, not one image per state.
- **Vision answers only what the probe cannot:** is this readable, is there a next
  action, does this look like a mistake. Do not re-litigate what the probe measured.

`off-token-color` is advisory: its top rows are often UA defaults on unstyled
elements. That is still worth knowing — it means no token reached that element.

## Phase 4 — Fix at the shared node

- **Reproduce or drop it.** A failure predicted from reading source is a
  hypothesis. Get it on screen or delete the finding.
- **Fix once, where all callers route through.** The same wrong gray on 12 screens
  is one token fix, not twelve patches. Grep every caller before editing.
- **Re-probe the exact cell** — same route, state, viewport, theme — plus the
  cells that already passed. A fix that breaks a neighbour is not a fix.
- **Route design failures to the narrowest `impeccable` command:** overflow and
  rhythm → `layout`, missing empty states → `onboard`, error wording → `clarify`,
  edge cases → `harden`, dead or unreadable states → `colorize`. Running every
  command on one surface averages into generic output.
- **Never change the public API to make a state pass.** If a fix requires one,
  stop and report it as a decision.

## Phase 5 — Lock it, or you will be back here

A one-shot audit regenerates the same backlog next quarter. Before finishing:

1. Write `ui-stress.md` at the repo root: the matrix that was swept, findings
   with status, and **accepted exceptions with reasons** — so the next run is a
   diff, not a re-audit.
2. Refresh `vcheck` baselines for states that now pass (`vcheck base urls.txt`).
3. Leave the one-line re-run command in that file.
4. Delete any harness route you created, or gate it behind the project's existing
   dev-only flag. Never leave a test page reachable in production.

## Report

State matrix with pass/fail per cell · deduplicated findings by severity with
instance counts · before/after screenshots for confirmed failures only · what was
fixed and where · what was deliberately left, with reasons · test and build
output pasted, not summarised.

**Done when** every applicable state has been probed, every reproduced failure is
fixed and re-probed in its original cell, the lock file is written, tests pass,
and the build succeeds.

## Maintaining the probe

`bash ~/.claude/skills/ui-stress/selftest.sh` serves a fixture with one planted
instance of every rule and fails if any rule stops firing. Run it after editing
`probe.js`. The probe must contain no backticks and no `$` — it is passed as a
double-quoted shell argument.
