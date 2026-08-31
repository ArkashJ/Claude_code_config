#!/bin/sh

command=$(/usr/bin/jq -r '.tool_input.command // empty' 2>/dev/null) || exit 0

if /usr/bin/perl -e 'exit($ARGV[0] =~ /^\s*cd\s+\S+\s*&&|;\s*cd\s/ ? 0 : 1)' "$command"; then
  echo 'Blocked cd chain. Use git -C <path>, bun --cwd <path>, or an absolute path instead.' >&2
  exit 2
fi

if /usr/bin/perl -e 'exit($ARGV[0] =~ /\bsleep\s+\d/ ? 0 : 1)' "$command"; then
  echo 'Blocked sleep-based waiting. Use Monitor, run_in_background, or an event/state-based poll.' >&2
  exit 2
fi

# A pipeline reports the LAST command's status, so `cmd | head` and `cmd | tail`
# launder a failure into a success. Both of these ran today and both reported a
# pass over a genuine failure:
#   go build ./... 2>&1 | head -5 && echo BUILD_OK    -> printed BUILD_OK, build was RED
#   bash verify.sh ... | tail -40; echo "EXIT=$?"     -> printed EXIT=0, tool said FAIL
# CLAUDE.md documents this shape three separate times; it keeps recurring because
# the output looks exactly like the passing case.
# Matched PER LINE, and only on the first line, for the same reason the bun guard
# below is: the hook receives the whole command including any heredoc body, and a
# commit message that QUOTES this bad shape is not an instance of it. That false
# positive blocked the very commit documenting the guard.
if /usr/bin/perl -e 'my ($first) = split /\n/, $ARGV[0]; exit($first =~ /\|\s*(head|tail|grep)\b[^|;&]*(&&\s*echo|;\s*echo\s+[^|]*(EXIT|\$\?))/ ? 0 : 1)' "$command"; then
  echo 'Blocked exit-code laundering: `cmd | head/tail/grep` then `&& echo OK` or `echo EXIT=$?` reports the PIPE tail'"'"'s status, not the command'"'"'s. Capture first: OUT=$(cmd 2>&1); echo "$?"; then inspect "$OUT".' >&2
  exit 2
fi

# `bun --filter <name>` resolves packages by NAME. An agent worktree is a full
# checkout, so each contains its own apps/web/package.json named "web" -- with 8
# lanes running, 43 of them existed and `bun --filter web typecheck` reported
# 13,510 phantom errors including "Cannot find module 'react'" while direct tsc
# reported ZERO. A false RED that reads exactly like a wrecked node_modules.
# Only fires when the ambiguity actually exists.
#
# Anchored to the FIRST LINE and to command position. Two false positives caught
# while proving this guard: `grep -n "bun --filter" CLAUDE.md` (the phrase inside
# a search string is not an invocation) and a python heredoc whose BODY contained
# the phrase (the hook sees the whole command, heredoc included). Prefer a miss to
# a false positive -- a guard that cries wolf on a grep stops being read, which is
# the failure mode of every guard in this file.
if /usr/bin/perl -e 'my ($first) = split /\n/, $ARGV[0]; exit($first =~ /(?:^|[;&|]\s*)bun\s+--filter\b/ ? 0 : 1)' "$command"; then
  if ls .claude/worktrees/*/package.json >/dev/null 2>&1; then
    echo 'Blocked `bun --filter` while agent worktrees exist: --filter matches by package NAME and every worktree holds its own copy, so it fans out across all of them (measured: 43 packages named "web", 13510 phantom errors vs 0 from direct tsc). Use `bun run --cwd apps/web <script>` (the flag goes AFTER `run` -- `bun --cwd apps/web run x` prints usage and EXITS 0, a false green), or the binary directly: node_modules/.bin/tsc --noEmit -p apps/web/tsconfig.json' >&2
    exit 2
  fi
fi

exit 0
