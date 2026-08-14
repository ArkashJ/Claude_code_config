## Enumeration discipline — count before you truncate

Never draw a conclusion from a truncated list. `| head`, `--limit`, `[:N]` output is a
SAMPLE: print the untruncated count first (`wc -l`, `--json | jq length`) and state
"N total, showing M" before reasoning about the set. Any completeness claim ("3 new
sessions", "all PRs reviewed") must cite the full count, not the sample.
(Origin: extractor 2026-08-06 — "3 new sessions" concluded from `find | head -12`; there were 19.)

## Never `sleep` to wait — the single most repeated waste in the corpus

`sleep N && check`, `sleep`-then-poll, and `sleep` inside a compound command are blocked by the
harness. **Reach for `Monitor` with an until-loop, or `run_in_background`, on the FIRST attempt.**

This is the most frequently repeated correction across every session ever harvested: **21 of 86
sessions**, extracted independently under five different names. The former prefix-only block did
not always fire: 151 sleep-bearing commands produced only 15 blocks. The current PreToolUse hook
blocks any `sleep\s+\d` token anywhere in the command, including compound, `nohup`, and loop forms.
Treat that as enforced only while the hook's adjacent self-test remains green.

Related, same family: an inner `timeout 900` is decorative when it exceeds the Bash tool's own
cap — the call dies at the tool's limit, not yours (592c8a27: two dead 2-minute waits and a
re-run of the full suite). Pass `timeout:` on the Bash call itself, or background it.

## One command, one absolute path — never `cd &&` chains

A compound `cd X && cmd` leaks the wrong cwd into the next command, and the harness resets cwd
between calls. Use absolute paths, or `git -C <path>`, per command.

The global PreToolUse hook rejects `cd X && cmd` at command start and `; cd X` later in a command;
use `git -C`, `bun --cwd`, or an absolute path instead.

Recurring in 81175d0e (exit 128 ×3, "not a git repository"), e17314ef (cwd leaked into
`git add`), and 0ad310c2 (model noted the recurrence itself). It is still recurring: on
2026-08-10 it silently produced 121 empty files in a 122-file batch — `2>/dev/null` hid the
error — and then made a corpus-wide grep return 0 hits from the wrong directory. Both were
caught only by sanity-checking the count, which is the real lesson: **a loop that reports
success without a count is not verified.**

## Code intelligence (LSP)

For TypeScript/JavaScript (`typescript-lsp` → `typescript-language-server`), Go
(`gopls-lsp` → `gopls`), and Python (`pyright-lsp` → `pyright-langserver`),
prefer the `LSP` tool over grep/text search whenever the task involves:

- finding a symbol's definition or all of its references
- renaming a symbol across the codebase
- checking diagnostics / type errors before declaring a change done
- getting hover / type information for a function, variable, or import

If the `LSP` tool's schema isn't loaded yet, load it first via
ToolSearch (`select:LSP`), then call it. Fall back to grep only when LSP
returns nothing useful (e.g. the language server isn't running for that repo).

### Use it in fixes and in workflows
- **When fixing/refactoring** (TS/JS via typescript-lsp, Go via gopls-lsp): run
  `findReferences` on a shared symbol before changing it, and `hover` to confirm types
  after. Treat the `<new-diagnostics>` pushed after edits as a real correctness gate —
  resolve them before calling a change done.
- **In `Workflow` runs:** instruct spawned agents to use the same `LSP` tool (load via
  `ToolSearch("select:LSP")`) for navigation + to honor diagnostics. Agents inherit the
  session's running language servers.

### Caveats
- LSP resolves only after the server has **indexed** the repo: Go needs `go.mod` + deps;
  TS/JS needs `tsconfig.json`/`package.json` + installed `node_modules`. First call on a
  big repo may say "still indexing" — warm it with a `documentSymbol` call, then retry
  `workspaceSymbol`.
- **git worktrees:** gopls treats each worktree module as separate and may warn "file is
  within module … not included in your workspace", and can cache roots for *deleted*
  worktrees. Harmless noise; restart gopls (or the session) to clear it.
- Speed: one LSP call is marginally slower than a single grep on a cold index, but for
  symbol work it's more accurate and usually faster overall than grep + reading files, and
  it won't false-match comments/strings. Prefer it.
# graphify
- **graphify** — any input to knowledge graph. Trigger: `/graphify`. The CLI lives at
  `~/.local/bin/graphify` (`graphify query|explain|path`); there is no SKILL.md for it.
