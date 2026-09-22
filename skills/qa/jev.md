# Jev (TypeSafe System One) for QA: use vs skip

Source: all 111 pages of https://docs.typesafe.ai (read 2026-09-22). Model `jev-1.13.0` (= `jev-latest`);
most cookbooks ran `jev-1.12`, so their thresholds are starting points. Code computes, Jev screens, Claude proves.

## 1. Capabilities that matter for QA

**Speculative fan-out.** Put every check for a surface into one request, including checks that only
apply to some surfaces, and let code ignore the rest. Batching does not change answers: std was exactly 0
on 11 of 13 questions, whether sent in one call or 13. For a 54k-char document it was 12.2x cheaper and
10x faster. `/patterns/fan-out`, `/cookbooks/parallel_questions`.
QA: one request per surface, carrying all effect/query/mutation checks plus the invariant checks. Never
send one request per check.

**Structured criteria (`what` / `not_for` / `examples`).** Every `instructions`, Choice option, Score level
and Noul `true`/`false` can be a string, object or array. You pick the key names; the model sees them.
```python
Noul(instructions={"question": "Does `snippet` copy server data into local state?",
                   "focus": "Only useState/useReducer seeded from a query result",
                   "inspect": "`snippet`"},
     criteria={"true":  {"what": "...", "examples": ["useState(data.items)"]},
               "false": {"what": "...", "not_for": "form draft state initialised once",
                         "examples": ["useState(initialValues)"]}})
```
`/primitives/advanced`, `/primitives/choice#structured-instructions-and-criteria`.
QA: this is how you tune false positives. The one-line reason you would give for dismissing a lead goes
into `false.not_for` or `false.examples`. Examples help only when they look like real inputs: a matching
example moved a Score from conf 0.35 to 0.96, and an unrelated example changed nothing.

**Backticked paths plus code-built data in instructions.** Point a question at `state` fields
(`` `context.effects[2]` ``), and put records built by code in named instruction fields rather than
string templates. `/primitives#reference-specific-fields`, `/primitives/noul#structured-instructions`.
QA: state = `{file, snippet, context, facts}`. The instructions carry `{"rule": inv.rule,
"candidate": {...}, "question": ...}`. Facts computed by code (for example, "touches the query cache")
go in `state.facts`, never in a question.

**Uncertainty band instead of 0.5.** `no < 0.30 ≤ uncertain ≤ 0.70 < yes`. Across 15 identical runs one
Jev Noul wandered between 0.43 and 0.53 and so crossed 0.5. `/cookbooks/consistency_noul_cookbook`.
QA: three buckets. Above 0.70 is a lead, 0.30–0.70 goes to Claude's read queue, below 0.30 is dropped.
The band edges are illustrative until tuned on labelled verdicts.

**Self-consistency.** Re-ask the same request N times with a throwaway `"uid"` field in `state`. For
Choice, abstain when the top probability is below 0.60: repeat agreement rose from 90.8% to 99.2%, with
74% of answers still automatic. Mean probability std is about 0.01, so Jev is stable, but borderline
labels still flip (11/4 and 8/7 splits). `/cookbooks/consistency_choice_cookbook`.
QA: re-run only the leads inside the band, 3–5 times, and mark the ones that flip as `unstable`. Instability
on a lead means the question or criteria are ambiguous, and it does not tell you whether the code is buggy.
The docs cannot tell uid sensitivity apart from sampling noise.

**Verify-then-escalate cascade (SDE).** A cheap producer runs first. Jev then asks a per-field Noul battery
framed so that `true` means wrong, and code escalates to the expensive model if any Noul is above 0.7. The
holistic "is this record wrong?" head scored 0.56 while the per-field heads hit 0.95/0.85, so it is shown
but not gated on. Aggregate with `max`, never mean, so that one red flag is not averaged away.
`/cookbooks/sde_cascade`.
QA: lead triage. Run a narrow battery per lead (`hallucinated_api`, `already_handled_elsewhere`,
`guarded_by_caller`, `pattern_actually_present`) and send it to Opus/Claude deep-read only when a flag
fires. Every question gets explicit true/false criteria.

**Citation check: verify Claude's own findings.** Step 1 is a string match in code: a quote that is
missing from the source is `fabricated`, and no model is called. Step 2 is a Choice
`supports / contradicts / says_nothing` on state `{claim, section}`. Confidence ≥ 0.8 is accepted
automatically; anything lower goes to a human. `/cookbooks/citation_check`.
QA: before reporting a finding, grep that its quoted `file:line` text exists. Then ask the Choice on
`{claim: finding, section: enclosing function}`. `contradicts` kills the finding; `says_nothing` means the
cited code does not show the bug.

**Guardrail policy (two thresholds, named policies).** One Noul per hazard plus a severity Score. A Noul
≥ review (0.35) sends the item to review; ≥ action (0.70 strict / 0.85 permissive) triggers that hazard's
action. Severity ≥ 2.0 upgrades review to block. A precedence list picks one outcome.
`/cookbooks/llm_guardrails`.
QA: give each check its own action (`lead`, `read`, `ignore`) and store the thresholds as named policies
(`strict` for pre-release, `permissive` for exploration). Screen subagent output too, for example
"does this patch do something the task said not to?"

**Ordered first-match routing (RAG gate).** Four Nouls per (query, passage) pair, with every threshold in
one dict. Security is tested first, then contradiction, then relevance, then evidence. Contradiction must
come before evidence, or a premise-refuting passage lands in the evidence block. `/cookbooks/classifying_rag_passages`.
QA: (a) choose which neighbour files or tests go into Claude's deep-read prompt; (b) a `contradicts_premise`
Noul catches leads whose premise the code refutes; (c) an `attempts_to_control_the_reader` Noul flags repo
text aimed at the agent. It is a filter, not a security boundary.

**Composite scoring.** Normalise each Score as `score / (len(levels) - 1)`, then take a weighted sum in
code. Weights are changed in code, not in prompts, and `1 - noul` is allowed for inverse signals.
`/patterns/composite-scoring`, `/primitives/score#splitting-a-complex-judgment-into-several-scores`.
QA: surface risk = `Σ w_check·noul + w_sev·severity_norm + w_blast·blast_norm`. Rank leads by this, not by
the single highest p. Keep the per-check values visible in the report.

**Severity as a Score with structured levels.** Levels describe situations, not degrees. Levels given
only as numbers failed (score 0.55, conf 0.33, versus 0.0 and 1.0 with descriptions). An extreme case gets
its own level. At most 10 levels. `/primitives/score`.
QA:
`["cosmetic, no behaviour change", "wrong in an edge case, workaround exists", "wrong data shown or saved on a common path", "data loss, security, or money path"]`.
Read `probabilities` as well as `score`: 1.0 can mean all mass on level 1 or a 50/50 split between 0 and 2.

**Three-outcome Score with no fitted threshold (entity alignment).** The levels are `different /
related-needs-a-curator / same`, routed by rounding to the nearest level. Companion Nouls (`same_name`,
`same_brewery`) tell the curator which field disagrees. `/cookbooks/entity_alignment`.
QA: deduplicate findings across runs or agents. On state `{finding_a, finding_b}` ask a Score with the
levels `different bug / same area, maybe same bug / same bug`, plus Nouls `same_file`, `same_root_cause`
and `same_fix`.

**Hierarchical classification with beam search.** One Choice per tree level; an option's value can be its
own subtree. Keep K=3 paths, scored by the geometric mean of their edge probabilities. Separation =
top/second path score, and a value near 1x means ambiguous. Beam matched 4/4 leaves where greedy matched
2/4, including a codebase file tree. `/cookbooks/hierarchical_classification`, `/primitives/advanced#walking-a-taxonomy`.
QA: bug taxonomy (area → pattern → specific) and "which file in `src/` does this bug report point to?"

**Back off to the parent when unsure.** One Choice over 75 labels. If confidence ≥ 0.9, report the leaf;
otherwise report its parent. Confident answers were 27/30 right and unsure ones 12/30; reported at the
parent level, the unsure ones became about 70% right. Use `confidence`, not the top probability:
`/cookbooks/classification_using_confidence`.
QA: when the specific bug pattern is uncertain, report its family (for example "effect lifecycle")
instead of guessing.

**Rerank a shortlist with one Noul per pair.** Use grep or BM25 to build a shortlist, then one Noul per
(query, candidate) pair, and sort by `noul`. Top-1 went from 5% to 18% and top-10 from 38% to 62%;
1,200 calls cost $0.0645. Criteria: `true` = "states the specific rule…", `false` = "merely a
similar topic". `/cookbooks/rerank_typesafe`.
QA: pick the test file, handler or prior fix most relevant to a diff or bug report. The rerank cannot add
a candidate that the shortlist missed.

**Pick among regex-found candidates.** `Choice(criteria={span: None for span in spans} | {"none": "none fits"})`
returns a verbatim span, so it cannot be hallucinated. `/cookbooks/pre_parsed_value_extraction_cookbook`.
QA: "which of these AST- or grep-found queryKeys or handlers is the culprit?"

**Line-id search (confirmed).** `exists` Noul ≥ 0.7 means answered, < 0.35 absent; over 255 lines, pick
a window first. `/cookbooks/semantic_find`.

**Confidence-gated routing.** Choice intent plus a complexity Score. Confidence < 0.5 or 0.6 goes to a
human. Each action gets a threshold scaled to its stakes (0.6 for read-only, 0.85 for destructive).
`/patterns/intent-routing`, `/patterns/confidence-routing`, `/confidence`.
QA/routing: decide Haiku vs Sonnet vs Opus, or which skill, per lead or per task. A high complexity score
or low confidence escalates.

**Skill suggestion (confirmed).** The gate is the mean of 3 "is an action wanted?" Nouls (one worded the
other way round); below 0.30, suggest nothing. The rerank drops everything if the highest `fits::` Noul
is below 0.30. Word the suggestion as ignorable. `/cookbooks/skill_suggestion`.

**Min-confidence for multi-part answers.** Choice per closed-set argument, plus a `stated` Noul that
omits unmentioned arguments; call confidence = `min`, not the product. `/cookbooks/function_calling`.
QA: a verdict built from several answers is only as sure as its weakest part.

**Autoresearch: train a tiny classifier on labelled verdicts.** An LLM proposes questions, Jev answers
every row, and CatBoost trains on the answers. Each Score becomes 2 columns (expected level and its sd);
each Noul becomes 1. Flat columns (sd < 0.05) are dropped. A revision or drop is kept only if
cross-validated error improves, and refits are free. RMSE was 1.87 after one proposal call and 1.77 after
5 rounds; asking Jev for the score directly got 2.15. `/cookbooks/autoresearch_feature_discovery`.
QA: rows = judged surfaces, label = proved (1) or dismissed (0), features = all check probabilities
plus code facts. This learns the weights and thresholds that are hand-set today, and the worst misses feed
new check proposals. Hold out a test split; no labels means no loop.

**Narrowest-fact wording and code-conditioned thresholds (autoformat).** "Picks up mid-sentence" gave 17
correct blocks; "same paragraph" merged the lists into 12. The merge threshold depends on a fact code can
read: 0.2 after a dangling line, 0.5 after terminal punctuation. Use a second request only when its
questions depend on the first answers. `/cookbooks/autoformat`.
QA: set lower thresholds on surfaces with no test coverage and higher ones on generated code.

**SDK features worth using.** `AsyncTypeSafeClient` in place of urllib, `response.nouls/.choices/.scores`,
`response_model=`, `request_id`, per-call `retry=RetryPolicy(...)`, `TypeSafeRateLimitError.retry_after_ms`.
`/sdk/python/usage`.
## 2. Skip for QA

- Primer (RLCD theory), quickstart, coding-agents, agent-skill (install only; keeper: keep questions and
  thresholds in one file and hand-edit agent-written questions), demos (fan-out UI demo), legal, the
  models-list API, gateways, and the use-case map (only "semantic code linting in CI" is relevant).
- Generating text or code with chained Choices: slow and poor (jaggedness #9). Claude writes; Jev picks.
- Asking Jev to count, do arithmetic, compare dates or versions, or interpolate a magnitude from a Score.
  Instead extract the parts as `none`-able Choices (or ask one Noul per item) and compute in code
  (`/cookbooks/date_extraction_cookbook`).
- Hex, RGB or low-level encodings: convert to a named bucket first.
- Non-English content and non-text input: English is best; images and audio are unsupported.
- JS SDK (skip unless a TS tool needs it) and the consistency cookbooks' LLM-vs-Jev tables (context, not method).
- `extra_body={"beam_width": 4}` and question `"weight": 2`: the docs label both **illustrative**
  forward-compat examples. They are not documented API fields, so don't send them (unverified whether the API ignores or rejects them).

## 3. Rules that move accuracy

1. One atomic, literal judgment per question, the kind an expert makes in a second. Split "A and B" into
   two Nouls. Decompose broad checks: "is this spam?" became 6 Nouls; "is this tool call correct?" became 9.
2. When an answer is wrong, the explanation of what you meant is the missing criterion. Add it to
   `criteria`, and try each question with and without criteria.
3. Name the narrowest fact that decides the answer (mid-sentence, not same paragraph). Write about the
   idea, not a parameter name ("Which resolution?" gives the model nothing to match).
4. A high value must mean the thing you act on. For verifier batteries, `true` = wrong. Never write
   "free of X". Instructions and criteria must agree; a Noul whose `true` means "no" performs worse.
5. Question ids are never sent to the model, so write the full question in `instructions`. Choice option
   names and descriptions are sent, so make descriptions contrastive.
6. A Choice always picks something. Add a `none`/`other` option, or pair it with an `exists` Noul.
7. Score levels describe situations. The model never sees level numbers or neighbouring levels, so "worse
   than above" means nothing to it. Keep one dimension per Score and at most 10 levels.
8. A Noul value of 0.5 is an even split, not a medium; ask degree with a Score. Noul values, Choice
   probabilities and confidence are not interchangeable, so never carry a threshold across types.
   P(q) + P(not q) need not equal 1 (0.72 + 0.47).
9. Aggregation: `max` for "any flag fires"; `min` confidence across the parts of one verdict; geometric
   mean along a path; weighted sum for ranking. To pick the best option, take the argmax; don't threshold
   confidence everywhere.
10. Thresholds scale with the cost of error. Use three bands (act / review / drop), start conservative,
    and tune on labelled verdicts, plotting confidence against accuracy. Thresholds may also depend on
    facts code can read.
11. State: a named-field object with only the relevant context, because irrelevant detail costs accuracy
    (context rot). Filter in code first. Limit: 32k tokens for state plus the longest question.
12. State is untrusted. Repo comments and strings can steer answers, so test adversarial snippets.
13. Route in a fixed order, first match wins: security first, then contradiction, before relevance or evidence.
14. Use a second request only when it truly needs the first answers (new state, new candidate texts).
15. Pin `jev-1.13.0` and log `response.model`, because aliases move. Key any cache on
    `hash(state, questions, model)` so an edited question never serves a stale answer.
16. Screen a proposed check before running it on the repo. Ask Nouls about the question itself: can it be
    answered from the snippet, does it have one meaning under its criteria, does it apply to most surfaces,
    will it vary. After a run, drop checks whose values barely vary (sd < 0.05 across surfaces).
17. Suggestions handed to Claude must be framed as ignorable: a confident wrong hint does more harm than none.
18. Rate-limit discipline: keep 6–8 requests in flight on a shared key; the cookbooks hit 429s above
    about 8. hunt.py's `--workers 12` default is too high.

## 4. Numbers

| Item | Value | Source |
| --- | --- | --- |
| Price | $0.042 per Mtok input ($42/Btok); output free | `/models` |
| Rate limits | 1,200 rpm **and** 250,000 tokens/s; "adjusting dynamically", can change without notice | `/models` |
| Context | 64k tokens per request; 32k for state plus the single longest question | `/models` |
| Choice options | max 255; "works reliably up to roughly 240" | `/api`, `/cookbooks/classification_using_confidence` |
| Score levels | min 2, max 10; 11 returns a server error | `/api`, `/cookbooks/autoresearch_feature_discovery` |
| Latency | ~100 ms typical; 111 ms for 14 Nouls; 114 ms for 8 Choices; 0.27 s for 13 questions on a 54k-char doc; 0.51 s for 62 questions | `/concepts/how-to-build-with-system-one`, consistency cookbooks, `/cookbooks/parallel_questions`, `/cookbooks/autoformat` |
| Cost examples | $0.000043 per 14-Noul rubric call; rerank ≈1,280 input tok/call | consistency_noul, rerank_typesafe |
| Stability | mean per-question std: Noul 0.0102, Choice 0.0098 (max 0.0515) | consistency cookbooks |
| Safe concurrency | "rate-limits above roughly eight"; cookbooks use 4–12 workers | `/cookbooks/entity_alignment`, autoresearch |
| Models | `jev-latest` and `jev-preview` → `jev-1.13.0`; cookbooks used `jev-1.12`; `"jev"`, `"jev-1.13"` appear in examples (unverified as accepted ids) | `/models`, `/sdk/python/usage`, jaggedness |
| Endpoints | `POST /v1/systemone`; `GET /v1/models`; header `x-typesafe-request-id` | `/api`, `/models` |
| Batch API | none: one state per request; parallelism is client-side only | `/api`, SDK refs |
| HTTP errors | 401 bad key, 422 validation, 429 rate limit, 529 overloaded | `/api` |
| Python SDK | `typesafe-sdk` v0.7.1 (2026-09-21), Python ≥ 3.10, pydantic; per-HTTP-op timeout 10.0 s | `/sdk/python/changelog`, `/sdk/python/api/constants` |
| Python RetryPolicy | max_retries 2, backoff 0.5 s doubling to 5.0 s, jitter 0.25, retries 408/429/5xx plus connection and timeout errors, honors Retry-After, total retry budget `timeout=30.0` s | `/sdk/python/api/retries` |
| JS SDK | `@typesafe-ai/sdk` v0.6.0, Node ≥ 20; timeout 10,000 ms per attempt (no total budget); retries as Python, `maxRetryAfterMs` 60,000; `dangerouslyAllowBrowser` false | `/sdk/javascript/api/*` |
| Env vars | `TYPESAFE_API_KEY`, `TYPESAFE_BASE_URL` (https://api.typesafe.ai), `TYPESAFE_DEFAULT_MODEL` (jev-latest), `TYPESAFE_LOG_LEVEL`; debug logs bodies unredacted | `/sdk/python/usage` |

Cookbook thresholds (all "starting points; tune on your data"):

| Use | Threshold | Source |
| --- | --- | --- |
| Noul act / review / drop | >0.70 / 0.30–0.70 / <0.30 | consistency_noul |
| Choice auto-act | top probability ≥ 0.60 | consistency_choice |
| Escalate verifier | any field > 0.7 (max) | sde_cascade |
| Guardrail | review ≥ 0.35; action ≥ 0.70 strict / 0.85 permissive; severity ≥ 2.0 blocks | llm_guardrails |
| Citation auto-accept | Choice confidence ≥ 0.8 | citation_check |
| Leaf vs parent label | confidence ≥ 0.9 | classification_using_confidence |
| RAG gate | injection > 0.70, contradicts > 0.70, relevant < 0.45 drop, evidence > 0.55 | classifying_rag_passages |
| Exists (semantic find) | ≥ 0.7 answered, < 0.35 absent | semantic_find |
| Skill gate / rerank | mean gate < 0.30 or max fits < 0.30 → none | skill_suggestion |
| Routing floor | confidence < 0.5–0.6 → human; destructive action > 0.85 | patterns, confidence |
