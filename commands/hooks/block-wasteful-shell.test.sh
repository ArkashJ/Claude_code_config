#!/bin/sh
set -eu

hook=${1:-/Users/arkashjain/.claude/commands/hooks/block-wasteful-shell.sh}

check() {
  expected=$1
  message=$2
  command=$3

  set +e
  output=$(/usr/bin/jq -nc --arg command "$command" '{tool_input:{command:$command}}' | "$hook" 2>&1)
  actual=$?
  set -e

  if [ "$actual" -ne "$expected" ]; then
    echo "FAIL: expected exit $expected, got $actual: $command" >&2
    exit 1
  fi
  if [ -n "$message" ] && ! printf '%s' "$output" | /usr/bin/grep -Fq "$message"; then
    echo "FAIL: missing '$message': $command" >&2
    exit 1
  fi
}

check 2 'git -C' 'cd /tmp && git status'
check 2 'bun --cwd' '  cd repo && bun test'
check 2 'absolute path' 'echo ready; cd repo'
check 2 'sleep-based waiting' 'sleep 1 && echo ready'
check 2 'sleep-based waiting' 'nohup server & sleep 45; tail server.log'
check 2 'sleep-based waiting' 'until test -f ready; do sleep 30; done'

check 0 '' 'git -C /tmp status'
check 0 '' 'bun --cwd /tmp test'
check 0 '' 'cd /tmp'
check 0 '' 'printf ready'
check 0 '' 'printf nosleep 1'

echo '11 cases passed'
