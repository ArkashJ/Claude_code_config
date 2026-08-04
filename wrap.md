---
description: Close a session — commit, derive all bookkeeping from git/gh, hand off into the PR
---

Close this session. The rule for every artifact below: **derive it from the authoritative
source (git log, diffs, PR state, the enumeration from /start) — never hand-write what can be
computed, and never write down state that a command can fetch fresh.** Do all applicable steps;
for any that don't apply, say so in one line. Use cheap-model subagents for the mechanical
derivations where it helps.

## 1. Land the work

`git status --porcelain` must end empty: commit remaining work (logical commits, not one blob),
push, and make sure the draft PR exists and is current. Remove scratch artifacts from the tree.

## 2. Handoff → PR, not loose files

Distill the rolling "Checkpoint log" comment first: every `SURPRISE:` / `FALSIFIED:` line gets
routed somewhere in the steps below (docs fix, issue, changelog note) or explicitly discarded
with a reason — freshness was captured in the log so nothing here relies on memory.

Then update the PR description (or add a final PR comment) with: what's done, what's not, what
was NOT read or covered (from the /start enumeration), surprises/falsifications hit, and exact
next steps.
This is the memory the next session's preflight picks up. No loose handoff markdown files.

## 3. Changelog

Derive the entry from commits/merged PRs since the last changelog entry — titles and diffs, not
memory. Conclusions only ("added X", "fixed Y because Z"), no state ("currently at version N").

## 4. Issues and board

For each issue touched: update or close via `gh issue`, with a link to the proving commit/PR —
never mark done without the rule-5 verification from /start. Create issues for anything
discovered-but-not-fixed (one per root cause, with evidence). Move board/kanban items
(`gh project item-edit`) to match reality.

## 5. % completion — only with a denominator

A percentage requires a countable ledger: X of N enumerated items, with the N named. No ledger →
report "done / in-progress / not-started" per item instead of a number. "Blocked" is only valid
with a recorded failing command/response attached; otherwise it is "not attempted".

## 6. API / docs sync

If code changed any surface that docs describe (API routes, schemas, CLI flags, env vars): diff
docs against the generated spec or the code itself, fix drift, and flag—don't silently fix—any
doc claim that was already wrong before this session. Never add mutable state to auto-loaded
files (CLAUDE.md and kin); those carry only invariants and pointers to commands.

## 7. Confidentiality gate

Before committing any derived artifact: no client names, addresses, credentials, or confidential
document content in anything committed or posted. Patterns, not payloads.

## 8. Final status line

End with: branch, HEAD, PR URL + state, CI state, issues updated/created, board moves, anything
left dirty or in flight — and the one thing most likely to bite the next session.
