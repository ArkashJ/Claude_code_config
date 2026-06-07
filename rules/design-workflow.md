# Design workflow (apply to every frontend repo)

The design skills (impeccable, design-taste-frontend, redesign-existing-projects,
high-end-visual-design, minimalist-ui) CONFLICT when more than one tries to own
"what good looks like." This rule removes the conflict and the guesswork about
ordering. Follow the four stages in order; do not skip ahead.

## Stage 1 — DIRECTION (exactly ONE owner per project)

- If the repo has a design contract (PRODUCT.md / DESIGN.md / brand-kit), that
  system owns direction. In Strata that means **impeccable** + the Sourced
  Ledger tokens. Other design skills become executors, never deciders.
- If greenfield with no system, **design-taste-frontend** proposes a direction
  ONCE (palette, type scale, spacing, motion). I lock it, then it's fixed.
- I am allowed to PROPOSE a direction when the user says they have none, AND to
  CRITIQUE/FIX what they built — but both happen under the single owner above.
- Never run two direction-owning skills against the same surface in one pass.

## Stage 2 — SUBSTRATE: shadcn/ui

- Components are **shadcn/ui** unless the repo already standardized elsewhere.
- Charts/graphs are **shadcn charts** (Recharts-based) — `ChartContainer`,
  `ChartConfig`, `ChartTooltip`. Do NOT hand-roll bespoke SVG charts when a
  shadcn chart covers it. Chart types: area, bar, line, pie, radar, radial.
- Theme charts through the design tokens / CSS variables, not hardcoded colors.

## Stage 3 — BUILD in Storybook (isolation first)

- Build each component (and every chart variant) in Storybook FIRST, with all
  states: empty, loading, error, populated, dense, dark/light.
- Storybook renders WITHOUT app auth — this is the fast visual loop. Screenshot
  the Storybook iframe, not the gated app, while iterating.

## Stage 4 — PROOF in the real app (Playwright)

- Only after the component looks right in isolation, wire it into the page and
  take ONE authed Playwright screenshot in the running app (see the screenshot
  honesty rule in workflow.md). That authed screenshot is the only "done" signal.

## Agnostic by default (reusable components must travel)

The whole point of building design assets is that they pay off in EVERY repo,
not one. So any component meant to be reusable (charts, primitives, layout
shells) must be portable:

- Data and colors come in as PROPS. Provide a default color palette as
  hardcoded hex so it renders with zero theming, and let the caller override.
- Depend ONLY on npm packages (react, recharts, …) and relative paths. No
  app-aliased imports (`@/lib/...`), no app domain types, no app CSS tokens
  (`var(--app-token)`), no app utility classes.
- Mark such a file with the word `AGNOSTIC` in its header comment. A PostToolUse
  hook (`~/.claude/hooks/enforce-agnostic.mjs`) then BLOCKS the edit if it finds
  app tokens or `@/` imports — so "agnostic" is enforced, not just promised.
- App-specific wiring (domain data → props, token → color mapping) lives in a
  thin SEPARATE wrapper in the app, never inside the reusable component.

## Speed contract (the user hates ceremony)

- Don't invoke all skills every time. Most tasks = Stage 2→3 only (the direction
  is already locked). Touch Stage 1 only when there's genuinely no system or the
  user asks to rethink the look. Touch Stage 4 only when wiring into the app.
