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

exit 0
