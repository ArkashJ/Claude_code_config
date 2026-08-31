#!/bin/sh
# Prove the two new guards in block-wasteful-shell.sh bite, and stay quiet on
# correct commands. A guard that has never failed is indistinguishable from one
# that cannot fail — which is the exact defect class being guarded against.
H="$HOME/.claude/commands/hooks/block-wasteful-shell.sh"
cd /Users/arkashjain/Developer/todo/Profectus || exit 1

probe() {
  printf '{"tool_input":{"command":%s}}' \
    "$(python3 -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$1")" \
    | sh "$H" >/dev/null 2>&1
  echo $?
}

fail=0
must_block() {
  got=$(probe "$1")
  if [ "$got" = "2" ]; then echo "  ok    BLOCKED  $2"
  else echo "  MISS  guard did not fire (exit $got)  $2"; fail=1; fi
}
must_pass() {
  got=$(probe "$1")
  if [ "$got" = "0" ]; then echo "  ok    allowed  $2"
  else echo "  FALSE POSITIVE (exit $got)  $2"; fail=1; fi
}

echo "--- exit-code laundering (both shapes ran today over genuine failures)"
must_block 'go build ./... 2>&1 | head -5 && echo BUILD_OK'          'pipe-to-head then && echo OK'
must_block 'bash verify.sh /r | tail -40; echo "EXIT=$?"'            'pipe-to-tail then echo EXIT=$?'
must_block 'make test | grep -c PASS && echo GREEN'                  'pipe-to-grep then && echo'

echo "--- bun --filter, while worktrees exist"
must_block 'bun --filter web typecheck'                              'bun --filter web typecheck'
must_block 'bun --filter web test tests/unit'                        'bun --filter web test'

echo "--- must stay silent: these are the CORRECT forms"
must_pass  'OUT=$(go build ./... 2>&1); echo "$?"'                   'capture status, then inspect'
must_pass  'bun run --cwd apps/web typecheck'                        'bun run --cwd (the WORKING fix)'
# The form this hook used to recommend. It prints usage and exits 0 -- a false
# green -- so it must not be blocked (it is not a --filter fan-out) but it must
# not be advertised either. Kept here so the advice and the proof stay in step.
must_pass  'bun --cwd apps/web run typecheck'                        'the broken-but-harmless --cwd-before-run form'
must_pass  'node_modules/.bin/tsc --noEmit -p apps/web/tsconfig.json' 'the binary directly'
must_pass  'go test ./... 2>&1 | tail -20'                           'a bare pipe with no laundering'
must_pass  'grep -c PASS log.txt'                                    'a plain grep'
# Both of these were caught BY this proof while writing the guard. The first
# version matched the phrase anywhere in the command, so it blocked grepping the
# docs for it and blocked a heredoc that merely mentioned it.
must_pass  'grep -n "bun --filter web" CLAUDE.md'                    'grepping FOR the phrase, not running it'
must_pass  'echo "never use bun --filter here"'                      'the phrase inside an echo'
must_pass  'python3 - <<EOF
# bun --filter web typecheck is wrong here
print(1)
EOF'                                                                 'the phrase inside a heredoc body'
must_pass  'git -C /repo log --oneline | head -5'                    'pipe-to-head, nothing after it'
# Caught by this proof: a commit message that QUOTES the bad shape is not an
# instance of it. This blocked the very commit that documented the guard.
must_pass  'git commit -m "$(cat <<EOF
bad shape: make test | tail -3 && echo OK
also bad: verify.sh | tail; echo EXIT=$?
EOF
)"'                                                                  'the bad shape quoted in a commit message'

[ "$fail" = "0" ] && echo "HOOK GUARD PROOF: PASS" || echo "HOOK GUARD PROOF: FAIL"
exit "$fail"
