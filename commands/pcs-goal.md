---
description: Upgrade ONE PCS frontend page per run (UI + data layer) via the impeccable pipeline, behavior-preserving, resumable. Run with /loop to sweep every page.
argument-hint: "[optional page path or module code, e.g. app/(app)/compliance/drug-testing/page.tsx or DRG]"
---

# /pcs-goal — behavior-preserving per-page UI + data upgrade

You upgrade **exactly one page per run** of the PCS_prod Next.js app, then stop.
This is designed to be driven by `/loop /pcs-goal` (self-paced): each run advances
one page and records progress so the next run resumes. Quality over speed —
a single well-verified page beats five half-done ones.

`$ARGUMENTS` — if a page path or module code is given, target that page.
Otherwise pick the next `todo` page from the ledger (below).

## North star

The **RTM corpus** (`../pcs_backend/docs/rtm-diagrams/`) is the spec for what each
module's page should do. The **impeccable** skill + `components/impeccable` kit +
shadcn `components/ui` are how it should look. `PRODUCT.md` / `DESIGN.md` own the
visual direction — do not invent a new one.

## The ledger (resumable state) — do this first

1. Read `docs/ui-upgrade-ledger.md`. **If it does not exist, create it**:
   - Enumerate every page: `git ls-files 'app/**/page.tsx'` (skip `app/api/**`).
   - Map each to its RTM module code (EXE, COMP, ONB, AAP, BSCP, BSCD, CCD, ROS,
     POL, DRG, BGS, OH, CRT, DOTDQ, DER, GEO, BIL, INT) by route/topic.
   - Write a table: `| status | route | file | module | notes |`, all `todo`,
     ordered weakest-first using the RTM coverage + the frontend module-status
     in `CLAUDE.md` (e.g. GEO/BG/Drug/DOT/OH lead).
2. Pick the target: `$ARGUMENTS` if given, else the first `todo` row.
3. Mark it `in-progress` in the ledger before you start.

## Per-page pipeline (one page, then STOP)

### 1. Understand (read before you touch)
- The page + its colocated `_components/` and `_lib/`.
- The RTM module doc `../pcs_backend/docs/rtm-diagrams/modules/<CODE>.md`
  (feature flow, gap map, persona journey, as-built endpoints).
- The data it shows and where it comes from (existing fetch, hooks, mock).
- **Inventory the logic you must preserve**: RBAC guards (`ProtectedRoute` /
  `<Can>` / `<Gated>` / `allowedRoles` / `permissions`), routes + params, form
  submission, mutations, event handlers, query keys, feature flags, demo-mode
  fallback. Write this list in the ledger `notes`. These behaviors MUST be
  identical after your change.

### 2. UI upgrade (impeccable, behavior-preserving)
- **Reuse, don't hand-roll.** Compose from `@/components/impeccable`
  (`KpiTile`, `MetricCardGrid`, `DataGrid`, `CommandMenu`, `Stepper`,
  `SegmentedControl`, `ProgressBar`, `InlineBanner`, `Toolbar`, `StatusPill`,
  `RadialGauge`, `TrendSparkline`, `EmptyState`, `Skeleton*`) and shadcn
  `@/components/ui/*`. Charts = shadcn charts (Recharts).
- **Every state**: default, loading (Skeleton — never a centered spinner),
  empty (`EmptyState` that teaches), error (`InlineBanner`/`EmptyState`),
  populated, dense, long/short text.
- **Status vocabulary**: `@/lib/ui/status.ts` + `<StatusBadge>` — full border +
  bg tint + icon + label, never color alone. Replace inline `green-*/amber-*/
  red-*` bundles.
- **a11y (Section 508 / WCAG 2.1 AA)**: keyboard paths, ARIA on icon-only
  controls, focus-visible rings, `tabular-nums` on metrics, contrast ≥ 4.5:1,
  honor `prefers-reduced-motion`. Sensitive PII columns stay gated on
  `employee:sensitive`.
- **Do not** add slop (gradient text, glassmorphism, side-stripe borders,
  per-section uppercase eyebrows) — see DESIGN.md bans.

### 3. Data layer (TanStack Query + Zod + Orval) — only where it doesn't change behavior
- Server state goes through **TanStack Query** hooks (`@tanstack/react-query`),
  not ad-hoc `useEffect` + `fetch`. Reuse existing `lib/dashboard/*`,
  `lib/<domain>/api.ts`, or generated hooks.
- **Orval**: if the page calls an endpoint that the BFF OpenAPI exposes, prefer
  the generated TanStack hooks (`bun run codegen:gateway`) through
  `lib/api/custom-fetch.ts`. Never mix generated `customFetch` calls with
  hand-written `apiGet` in the same module.
- **Zod**: validate every form / inbound payload with a Zod schema
  (`react-hook-form` + `zodResolver`). Colocate schemas in `_lib/`.
- **HTTP rules (ast-grep enforced, will fail CI)**: never `fetch()` directly —
  use `apiGet/apiPost/apiPatch/apiDelete` from `@/lib/auth/api-fetch`. Never
  touch `pcs_access_token`/`pcs_refresh_token` outside `lib/auth/token-store.ts`.
  Audit reads set `X-Access-Reason-Code`.
- **Keep the demo-mode fallback** so the page still renders without a backend.
- **No PII in logs/Sentry** — use `lib/observability/log.ts`.

### 4. HARD GUARDRAILS — stop and flag instead of breaking
- **Behavior is frozen.** No change to RBAC semantics, routes, query keys that
  other code depends on, mutation side-effects, or API request/response shapes.
  If an improvement requires changing behavior, STOP, write the proposal in the
  ledger `notes`, leave the page `in-progress`, and end the run.
- **Don't invent endpoints.** If the RTM/UI needs data the backend doesn't
  expose yet (check the module's as-built diagram + `lib/codegen/*.d.ts`), keep
  the mock, mark the gap in `notes`, and ship the UI-only improvement.
- **Don't edit `components/impeccable/`** (AGNOSTIC kit) to wire app data — build
  a thin wrapper in the app. The enforce-agnostic hook will reject violations.
- **One page per run.** Do not start a second page.

### 5. Verify (a claim is not a result)
- `bun run type-check` on the changed surface — 0 new errors.
- **Real authed screenshot**: drive the running dev server, log in (demo mode is
  fine), navigate to the page, screenshot. Print the **absolute PNG path + the
  URL the browser landed on**. A login/403 bounce is a FAILURE — say so, don't
  present it as success. Reuse `tests/` Playwright auth setup / `scripts/` shot
  helpers; capture mobile + desktop for responsive pages.
- **axe** scan (`@axe-core/playwright`, wcag2a+wcag2aa) — 0 new serious/critical
  violations introduced by your change.
- Re-confirm the preserved-behavior list from step 1 still holds (guards, forms,
  mutations).

### 6. Record + commit
- Update the ledger row to `done` with: the screenshot path, a one-line summary
  of what changed, and any gap noted. Keep the table sorted.
- Commit just this page's files + the ledger:
  `feat(<module>): impeccable UI pass on <route> (behavior-preserving)`
  with the trailer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
  **Do not push** unless the user asked.
- Briefly report: page, before→after summary, screenshot path + landed URL,
  verification results, any gap. Then STOP (the loop will re-invoke for the next).

## Running the sweep

- One page: `/pcs-goal` (or `/pcs-goal DRG` / `/pcs-goal app/(app)/.../page.tsx`).
- Every page: `/loop /pcs-goal` — self-paced; each iteration upgrades the next
  `todo` page and the ledger makes it resumable. Stop the loop any time; rerun
  to continue where it left off.
