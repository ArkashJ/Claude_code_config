---
name: qa
description: One QA entry point, built on Jev (TypeSafe). DOCS consolidates docs with zero lost knowledge (claims checked against code, lost-claim review). HISTORY classifies a repo's past fix commits to show where bugs escape. HUNT screens every React/TanStack surface against generic checks and the repo's own invariants. REVIEW triages the open PR queue (stacks, PRs already contained in others, CI, risk) and assigns each PR a review depth and model (haiku/sonnet/opus) plus a merge order. PLAN writes an evidence-first QA plan from a diff. MEASURE runs the `qa` browser/static CLI. Use for "audit this repo", "bugs we keep missing", invariants, hooks/TanStack, edge cases, "review these PRs", "which model should do this", QA plans, pre-release QA.
---

# QA

## Core principles: every mode, non-negotiable

These are carried over from qa_skill and frontend-verify. A report that breaks one of them is not done.

1. **Evidence first.** Every risk, test, lead verdict, graph edge and fix cites a verified
   `path:line`, command output, or run id. Never invent a reference; an unverifiable claim
   is marked `Confidence = low` / inference, never presented as fact.
2. **Unmeasured is not clean.** Missing evidence, unreached routes, zero denominators,
   unjudged surfaces and failed requests are reported as *unmeasured* with a count. Every
   completeness claim cites the full count, not a sample.
3. **Fixed means measured again and gone.** Re-run the same measurement after a fix. A
   finding the later run never visited is unmeasured, not fixed. A prior artifact is
   historical once any input changed.
4. **The instrument's output is the authority.** Read exit code, run id, findings and gaps
   (`qa` exits 0 clean · 1 gating findings · 2 invalid/unable to measure; fix a 2 before reading
   any finding). Never infer success from files an earlier run left behind.
5. **Group symptoms into causes.** N findings across routes are usually one shared cause:
   fix it once, where all callers route through.
6. **Adjudicate, never delete.** A false positive gets a scoped, expiring waiver with a note
   and evidence (`qa fix fp add …`), or a tuned question in HUNT, never silent removal.
7. **No silent mutation.** QA produces a Fix Queue; code changes only with explicit user
   authorization. Never mutate production; writes need the declared non-production policy.
   Credentials stay out of argv, reports and model context; screenshots of authenticated
   apps are user data.
8. **Size depth to risk, not to time available.** Use the smallest run that settles the
   question; sustained QA only when the user asks for it and gives a budget. A budget grants no extra permissions.
9. **Adversarial pass before finalizing.** Challenge missing consumers, unsupported edges,
   generic tests, stale evidence, denominator mistakes. Unresolved items stay visible.
10. **Done is an exit code that survives wiring.** Gates re-exit explicitly (`|| { …; exit 2; }`);
    `cmd || echo BLOCKED` exits 0 and passes every failure through.

Pick the smallest mode that answers the question. For a whole-repo audit run them in
order: the repo's own gates → HUNT → prove leads → PLAN the fixes → MEASURE at runtime.

| Mode | Input | Output | Manual |
| --- | --- | --- | --- |
| HISTORY | repo | fix commits by surface × mechanism: where bugs escape | `history.py` |
| HUNT | repo | ranked leads, `file:line`, per-check probability | `hunt.py` |
| REVIEW | OWNER/REPO | PR queue: tier, model, merge order, PRs contained in others | `review.py` |
| DOCS | repo + `.qa/docs.json` | per-doc disposition, model-routed task plan, dropped-claim queue | `docs.py` |
| PLAN | diff / PR / branch / module | `docs/QA-PLAN-*.md` with evidence ledger | [plan.md](plan.md) |
| MEASURE | repo + optional `--base URL` | `qa` findings, coverage, gaps, exit code | `~/Developer/todo/Automated_QA/SKILL.md` (`qa help`) |

## HUNT: Jev over every surface

Jev is TypeSafe's System One model: state + yes/no questions in, calibrated probabilities
out, ~100 ms, $0.042 per million input tokens. It judges; it does not reason in chains,
write code, or count. So code enumerates, Jev screens, Claude proves.

0. **Find where this repo's bugs escape before choosing what to hunt.**
   `python3 ~/.claude/skills/qa/history.py <repo>` sorts every `fix` commit into a surface ×
   mechanism pair with Jev (386 commits ≈ 1 minute, a few cents). Aim at the top rows, not at the
   surfaces you assume. On repo A, hooks/TanStack were only ~25 of 301 user-facing
   fixes. Permissions (38), API contract (39), auth/session (29) and loading/empty/error
   states (29) were the real escapes. Exact cross-checks (frontend gate vs backend requirement,
   wire enum vs UI mapping) belong in code; Jev handles the judgments that code can't make.
1. **Run the repo's own gates first** (`verify`/`lint`/`tsc`/custom `check:*`). Jev never
   re-asks what a linter or script already enforces.
2. **Write or refresh `<repo>/.qa/invariants.json`** from the repo's rules (CLAUDE.md hard
   rules, `docs/specs/`, ADRs). Keep only rules that need judgment; mechanical rules belong
   in a grep or script. Shape (see `a repo's .qa/invariants.json`):
   `{id, rule, kinds:[effect|query|mutation], hooks?, files?, when?, when_scope?, question, true?, false?}`.
   `when` is a regex prefilter: cheaper and fewer false positives.
3. **Run** `python3 ~/.claude/skills/qa/hunt.py <repo> [--src src] [--limit 20]`.
   Needs `TYPESAFE_API_KEY` or `TYPESAFE_JEV_KEY`. Writes `~/.claude/qa-runs/<repo>/hunt.{md,json}`.
   It exits 1 if any request failed. Report the surface count, the judged count and the lead count, never a sample.
4. **Prove or dismiss the top leads** by reading the code: a failing test, a repro, or a
   one-line reason it is fine. A lead is a place to look, not a finding.
5. **Judge a rule where it lives.** HUNT judges hook call sites. Rules about what a *component renders*
   (a control shown without its permission, a failed read shown as empty, money shown without a gate)
   can't be decided from hook files: repo B asked one 184 times with 0 leads, and the verifier said
   "not determinable". Leave those to PARITY/STATES, or judge them at the component that consumes the hook.
6. **An agent verdict isn't ground truth.** Verifiers make confident wrong claims (one said `usePushSegment`
   wasn't queued; it was). P1s, and cases where two agents contradict each other, get an independent read before reporting.
7. **Tune when dismissals cluster on one check.** Jev reads literally: the explanation you
   would give for "why this isn't a bug" is the missing `false` criterion. Add it, re-run.

Built-in checks. Code computes facts (for example, whether a mutation touches the query
cache) and Jev only judges meaning:

| kind | checks |
| --- | --- |
| effect | draft_clobber (overwrites user draft × reruns on refetch), url_sync_one_way (writes input to URL × no read-back), missing_cleanup, async_race |
| query | key_missing_input, runs_without_param |
| mutation | mutation_no_cache_update (Jev: writes shown data × code: no cache update), optimistic_no_rollback |

**Non-React stacks** (Benmore/DOM-string apps; repo C 2026-09-22): hunt.py's extractors don't
apply. At 40k-char module chunks, 3 of 4 Jev checks returned ≈0 leads while 59–71 chunks sat
in the review band. Treat "no lead" at that chunk size as *unmeasured*, and chunk per
function with its owning component. Code facts carried more signal there: `Promise.all([...])`
with no `.catch` found 20 boot hangs across 15 modules. **Strip comments before any trap regex**: every one of 30+
flow-trap hits was a comment documenting the trap (hunt.py does this; test_hunt.py proves it).

Extending HUNT, with patterns from the TypeSafe cookbooks. Add them when a repo needs them:
- **Pin the line:** tag file lines `L001|…`, ask a Choice "which line …" plus a Noul "does any
  line …" (Choice always picks something; the Noul says whether anything matches). ≤255 lines per Choice.
- **Reuse / duplicates:** candidate components found by code → Choice "which existing
  component does this duplicate, or none", then one Noul per top-3 candidate.
- **Model / skill routing:** rank all options with one Choice, then re-check the top 3 with
  a Noul each. Either step may return nothing. (TypeSafe measured this: wrong skill loads fell from 16.8% to 7.3%.)

## Two exact audits (agent recipes: code, not Jev; history ranks them first on most repos)

**PARITY: frontend gate vs backend permission.** repo A 2026-09-22: 9 verified, 1 P1. This is the #1 escaped class there.
1. Backend: import each service's real app (FastAPI: `app.main`) and walk `app.routes`. For each route,
   resolve the permission from the dependency and body AST, including constants and closures. Count gated / ungated / unresolved.
2. Mapping: run the real gateway app with auth overridden and the outbound HTTP client stubbed, and send every
   frontend endpoint through it. Record the upstream URL and forwarded permissions. Report the mapped % (it was 76%) and
   list the unmapped endpoints as unmeasured.
3. Frontend: for each route file and write call site, find the gate (route guard plus ancestors, `<Can>`/`<Protected>`)
   using the TS checker, following hooks → api → path.
4. Replay with real personas (role → permission sets from the backend's own tables, never guessed).
   Candidate = the frontend lets it through, the backend denies it, or the backend doesn't check a write at all.
   Verify each candidate with file:line on both sides.
Hidden classes seen: writes gated only on the frontend; the gateway needs *both* of two scopes; a gateway
`safe_get` swallows a 403 into an empty list; the gateway turns an upstream 403 into a 502.
Delete the per-service virtualenvs afterwards (14 of them = 1.7 GB).

**STATES: loading/empty/error/partial.** 16 verified, 2 P1. Enumerate, count, then verify each:
(1) suspense with no pending/error boundary · (2) `useQuery` whose error is never read, or `isError`
without a `!data` check (a failed refetch wipes loaded data) · (3) polls that keep running on error or after a terminal state ·
(4) an empty array that renders nothing · (5) **fail-open**: a default/`??`/ternary/`z.default(0)` that shows a
positive badge for unknown or degraded data. Pattern 5 held the P1s. **Reconcile the counts:**
candidates == verified + dismissed + unmeasured for each pattern, or the report is invalid. A repo B
agent silently adjudicated 27 of 81 and its grep missed generics (`useQueuedWrite<T>(`); only
reconciling the counts caught it. Compare against sibling pages:
the CCD page had the guard (`coverageKnown`) that the SC page lacked.

## REVIEW: the PR queue, and which model reviews what

`python3 ~/.claude/skills/qa/review.py OWNER/REPO` (read-only). Code works out the stacks
(base = another PR's head), **containment** (head of A is an ancestor of head of B via the GitHub
compare API, meaning A is already inside B), file overlap, CI and size. Jev judges each PR in
≤60k-char file chunks: auth, shared surface, data writes, behavior change, tests cover it, and
a risk Score. The PR takes its worst chunk, and the files behind that chunk are listed as "hot". Code then assigns:

| tier | model | when |
| --- | --- | --- |
| covered | — | contained in another open PR: review that one, then close this |
| blocked | — | CI failing or conflicting. The table still shows the tier it gets once green |
| skim | haiku | <150 lines, risk <1.2, tests cover it, Jev confident |
| review | sonnet | everything else |
| deep | opus | >2000 lines, risk ≥2, auth, data writes, or shared surface without tests. Also run PLAN on the blast radius |

Run the reviews in parallel, one agent per PR, with `model` set from the table, in merge order
(stack parents first, then low risk, few overlaps). The deep reviewer starts from the hot files.
First run, repo B (2026-09-22): 16 open PRs → 12 already contained in #1525, 4 need action,
and #1525 (70k lines) goes deep once CI is green.

**Model routing for any workflow** (same principle: code decides from facts, Jev from judgment):
fan-out search / enumeration → haiku · lead verification, normal review, test writing → sonnet ·
cross-file bugs, auth/data changes, fixes to shared code, final adversarial pass → opus.
When Jev's confidence is below 0.5, go one tier up; never down.

## DOCS: consolidate docs with Jev (pairs with the `document-consolidation` skill)

The `document-consolidation` skill owns the method and the `preserve.py` guard. `docs.py` adds
the Jev layer. Write `<repo>/.qa/docs.json` (`goal`, `owners` {path: scope}, `risk`
{path: note}, `code_dirs`, `exclude`), then run `python3 ~/.claude/skills/qa/docs.py <repo>`
with each of these in turn: `docs` → `claims` → `decide` → `plan`. After the writers finish, run `dropped`.
repo C (2026-09-22): 184 → 53 docs, 4,707 claims checked, PR #677. What that run taught, now built into the tool:
- **"Contradicts" from Jev is triage, not a deletion signal.** It was right only 4 of 33 times
  (external APIs, framework behaviour, and symbols outside the grep scope all looked "missing").
  Every deletion rests on an agent reading the code.
- **Hard keeps are code, not Jev:** client transcripts, agent prompts, generated files and third-party
  docs are always kept. (Jev once tried to delete transcripts.)
- **The first writing pass loses content.** Of 1,110 dropped claims, 105 were real rules or open items (~10%).
  `dropped` queues claims whose tokens are missing from their owner; agents classify each as
  LOST / FIXED / NOT_DURABLE and restore the LOST ones. Not optional.
- **One output path per agent.** Two lanes that wrote the same file silently dropped 19 items, and forks
  inherit file-write instructions from their parent prompt. Also mind the 20-concurrent-subagent cap.
- **Never use Haiku for edits touching citations, links inside source text, or tests.** A Haiku link pass rewrote
  citations to point at themselves and undid two test fixes. Haiku is only for deletes and checker runs.
- **Deleting non-Markdown files needs a reference scan that includes `docs/` itself.** Transcripts
  embed images from their own folder, and scanning references only outside `docs/` marked 23 needed files deletable.
  Keep test-harness output directories.
- **Route models per module batch, not per item:** use the highest tier any item in the batch needs. A 0.5 floor per item sent
  122 of 256 open items to Opus.
- Every deleted original stays recoverable: `git show <base-sha>:<path>`. Cite that base in the PR.

## PLAN: evidence-first QA plan from a change

Follow [plan.md](plan.md): change inventory → evidence ledger → global context map →
two-hop blast radius with Mermaid + ASCII graphs (every edge cites evidence) → risk rows
(scored below) → P0–P3 test tables → adversarial review → Fix Queue → self-review →
summary. Compact mode for small low-risk diffs; full audit for high-risk, release, security, or cross-module changes.
Proven HUNT leads go in as evidence rows.

## MEASURE: the `qa` instrument (frontend-verify)

`qa` (→ `~/Developer/todo/Automated_QA/bin/qa.mjs`) measures, archives, ranks and reports.
It never fixes. Deep manual: `~/Developer/todo/Automated_QA/SKILL.md`, `README.md`,
`references/{operating-manual,auth-lanes,coherence-math}.md`; `qa help COMMAND` owns flags.

```bash
qa verify APP                          # static, seconds
qa verify APP --base http://localhost:3000   # + browser (reuse the user's server)
qa verify APP --preflight --base URL   # when readiness is uncertain
qa show APP | qa show next APP         # ranked findings + coverage | next finding + brief
qa show diff APP                       # after a fix: fixed / new / unmeasured
qa measure coherence APP --views       # stale values across routes
qa verify APP --runs N --base URL      # intermittent findings
qa init APP --analysis && qa show analysis APP   # traceable analysis with Mermaid/ASCII
qa run APP --base URL --once | --hours N         # sustained QA, only with an explicit budget
```

- Review each feature on six axes: surfaces, producers, consumers, consistency rules
  (what must refresh after each mutation), RBAC at every appearance, coverage.
- Unreached routes are gaps, not app defects. Check the served app, revision, persona and
  lane before trusting a green summary. `landedOn: "/"` everywhere usually means the router mode was detected wrong (hash vs path).
- `unauthenticated-api-fetch` is a candidate that needs a real-persona run to confirm;
  `unchecked-fetch-response` needs no confirmation.
- Declarations (`verify.roles.json`, `verify.crud.json`, `verify.read-only.json`,
  `verify.auth-launcher.mjs`) only when a named gap asks for one. Never fabricate selectors,
  identities or fixtures. Writing the launcher once is the highest-value declaration.
- **Next.js app + separate API origin (repo B 2026-09-22 hit these in order; check them all before the first run):**
  (a) the identity oracle is off unless the web server runs with `QA_IDENTITY_ORACLE=true`; (b) dev-server compiles over 40 s
  read as "server unreachable", so use a prod build; (c) a prod PWA service worker invalidates protected journeys and
  leaves route cells with "no interceptable data request", so build with the app's service-worker-disable flag;
  (d) writes fail "must stay on the declared base origin" when the API is on another port, so put a same-origin proxy in front.
- **A `qa` crash must never read as findings.** Before Automated_QA#333, a large run crashed Node
  (`RangeError: Invalid string length` capturing agent stdout) and exited 1, the FINDINGS code. If `--json` is
  empty or `.verify/runs/.pending-*` is left behind, the run is invalid whatever the exit code says.
- `--capture` screenshots are off by default and are user data; keep `.verify/` out of git.
- Close with: verdict, exact commands + exits, source/run ids, scope and personas, cleanup, remaining gaps, artifact paths.

MEASURE and HUNT cover each other's blind spots. HUNT reads every hook statically but
can't see runtime behavior. MEASURE sees runtime but only on routes and personas it reaches.
A HUNT lead like `mutation_no_cache_update` becomes a MEASURE coherence check on the
surfaces that should refresh.

**Bands, not 0.5:** ≥0.7 is a lead; 0.3–0.7 is a review queue (one question drifted
0.43–0.53 over 15 identical runs); below 0.3 is dropped. `.qa/known-bugs.json` holds confirmed bugs, and every
run reports recall against it, so tuning never silently loses a real catch.

**Pilot result, repo A (2026-09-22):** first pass 592 leads at 0.5. Four agents
checked 76 sampled leads: 6 real bugs (1 P1, 2 P2, 3 P3); `runs_without_param` 0/9 and
`derived_state` 0/9 were noise. The broad checks were replaced with composed pairs
(`draft_clobber`, `url_sync_one_way`) and code facts (helper-aware cache detection).

**Not built yet, ranked by value** (details and sources in [jev.md](jev.md)):
1. Stability re-runs: ask review-band leads 3–5× with a throwaway `uid` in state; a lead that flips means an ambiguous question.
2. A verify-then-escalate second pass: narrow "this lead is wrong because…" Nouls; escalate to Claude only if none fire.
3. Check Claude's own findings: grep that the quoted `file:line` text exists, then a Choice of
   supports / contradicts / says_nothing against the enclosing function.
4. A composite surface risk score (weighted Nouls + a severity Score); weights live in code.
5. Autoresearch: turn proved/dismissed verdicts into labels and fit thresholds per check.
6. Context rerank: pick the neighbouring files and tests for each lead before the deep read.

## Jev rules (from docs.typesafe.ai; jev-1.13 jaggedness page). Full reference: [jev.md](jev.md)

- One atomic, literal question per check; put boundary cases in `true`/`false` criteria.
  Instructions and criteria must agree (never map "yes" to the bad case in one and good in the other).
- Keep state small and relevant: the snippet plus its owning component. Irrelevant context
  lowers accuracy. Limit: 32k tokens for state plus the longest question.
- Math, counting, dates and multi-hop reasoning go to code or Claude, not Jev.
- A Noul near 0.5 means an even split between yes and no, not a medium-strength signal. Noul answers carry no confidence field;
  Choice/Score do. Noul and Choice scores aren't comparable; don't reuse a threshold across them.
- Pin `jev-1.13.0` (default in hunt.py) so thresholds don't shift when `jev-latest` moves.
- All questions in one request run in parallel, so fan out speculative questions and let code pick.
- Typed output guarantees the format, not the truth. Thresholds are tuned on your own data.

## Risk scoring (shared by PLAN and MEASURE)

Score likelihood and impact 1–5 each; take the highest `likelihood × impact` in scope.

| Likelihood factor | 1 | 3 | 5 |
| --- | --- | --- | --- |
| Change size | tiny rename or copy change | localized logic change | broad or new flow |
| Complexity | mechanical | conditional logic | new algorithm, async path, migration, state machine |
| Coupling | one file | 2–3 modules | 4+ modules or an external integration |
| Historical risk | no signal | known fragile area | repeated bugs, incidents, or TODO warnings |
| Evidence confidence | high | medium | low or partly inferred |

| Impact factor | 1 | 3 | 5 |
| --- | --- | --- | --- |
| User effect | cosmetic or internal-only | degraded workflow | broken core workflow or data loss |
| Data integrity | read-only | validated write | destructive or irreversible write |
| Security/privacy | no sensitive data | scoped sensitive data | auth, tenant, permission, secrets, PII |
| Financial/compliance | no regulated output | reporting or export | billing, audit record, legal/compliance |
| Recovery | easy rollback | manual cleanup | hard correction or customer-visible fallout |

| Score | Level | Coverage |
| --- | --- | --- |
| 20–25 | CRITICAL | exhaustive: happy path, main error paths, boundaries, permissions, data integrity, regression |
| 12–19 | HIGH | heavy: happy path, error path, a representative edge case, a direct integration check |
| 6–11 | MEDIUM | standard: happy path and one negative or regression check |
| 1–5 | LOW | smoke only, unless evidence shows a known hotspot |

A HUNT lead that is proven real enters PLAN as evidence with `Historical risk` ≥ 3.
