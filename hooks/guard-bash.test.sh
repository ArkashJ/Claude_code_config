#!/usr/bin/env bash
# Self-test for guard-bash.sh: every case asserts exit code AND message. Run
# after any edit; ~/.claude/CLAUDE.md trusts the guard only while this is green.
set -u
G="$(dirname "$0")/guard-bash.sh"; fail=0
check() {  # expected_exit  expected_msg_substring  command
    out=$(printf '%s' "$3" | python3 -c 'import json,sys; print(json.dumps({"tool_input":{"command":sys.stdin.read()}}))' | bash "$G" 2>&1 >/dev/null); rc=$?
    if [ "$rc" != "$1" ] || { [ -n "$2" ] && [[ "$out" != *"$2"* ]]; }; then
        echo "FAIL exit=$rc want=$1 msg='$out' cmd: $3"; fail=1
    else
        echo "ok   exit=$rc cmd: $3"
    fi
}
# must block
check 2 "sleep N" 'sleep 5 && curl localhost'
check 2 "sleep N" 'nohup bash -c "sleep 30; ./run" &'
check 2 "sleep N" 'for i in 1 2 3; do sleep 2; done'
check 2 "sleep N" 'while true; do sleep 1; check; done'
check 2 "disguised sleep" "perl -e 'select(undef,undef,undef,5)'; curl localhost"
check 2 "disguised sleep" 'read -t 30 < /dev/null; ./check'
check 2 "disguised sleep" 'while ! curl -s x; do read -r -t 2 _ <> <(:); done'
check 0 "" 'while read -r line; do echo "$line"; done < f'
check 0 "" 'grep -n "read -t" docs/notes.md'
# empty-body busy-wait: 2026-10-24, 11 spinning `until grep ...; do :; done` loops, load 105 on 8 CPUs
check 2 "busy-wait" 'until grep -qE "passed|failed" /tmp/l1.log; do :; done; tail -25 /tmp/l1.log'
check 2 "busy-wait" 'while ! test -f /tmp/done; do true; done'
check 2 "busy-wait" 'until [ -s /tmp/x ]; do : ; done'
check 0 "" 'until grep -q ok /tmp/x; do timeout 15 tail -f /dev/null; done'
check 0 "" 'for f in a b; do echo "$f"; done'
check 0 "" 'grep -n "do :; done" notes.txt'
check 2 "cd X" 'cd /tmp/x && make'
check 2 "cd X" 'ls; cd /tmp/x; make'
check 2 "cd X" 'true && cd /tmp/x && make'
# playwright-cli close-all/kill-all: session afac82d1, a sub-agent closed EVERY browser session on the machine
check 2 "close-all" 'playwright-cli close-all'
check 2 "close-all" 'npx playwright-cli kill-all'
check 2 "close-all" 'playwright-cli -s=a snapshot; playwright-cli close-all'
# relative ./scripts/ next to a worktree path: 2026-10-02 ran from the harness cwd, exit 127
check 2 "relative './scripts/" 'I=/x/.claude/worktrees/lane; make -C $I verify.sg; ./scripts/check-tracked-artifacts.sh'
check 2 "relative './scripts/" '( make -C /x/.claude/worktrees/lane verify.sg; echo A; ./scripts/check-evidence-policy.sh ) > /tmp/log 2>&1'
# name-matched kills: 2026-10-17, two lanes killed another session's next-server / bun test
check 2 "pkill/killall" 'pkill -f next-server'
check 2 "pkill/killall" 'pkill -f "bun test --isolate"'
check 2 "pkill/killall" 'echo done; killall node'
check 2 "pkill/killall" 'sudo pkill -9 go'
check 2 "pkill/killall" 'kill $(pgrep -f playwright)'
check 2 "pkill/killall" 'kill -9 `pidof next-server`'
check 2 "pkill/killall" 'pgrep -f storybook | xargs kill'
check 2 "pkill/killall" 'pgrep -f storybook | xargs -r kill -9'
# must allow
check 0 "" 'kill 12345'
check 0 "" 'kill "$(cat /tmp/lane.pid)"'
check 0 "" 'grep -rn pkill scripts/'
check 0 "" 'echo "never use pkill"'
check 0 "" 'pgrep -fl next-server'
check 0 "" 'playwright-cli -s=cg-trial-sc-owner close'
check 0 "" 'playwright-cli list'
check 0 "" 'git -C /tmp/x status'
check 0 "" 'uv --directory /tmp/x run pytest'
check 0 "" 'python3 -c "import time; time.sleep(1)"'
check 0 "" 'grep -rn "asleep" src/'
check 0 "" 'echo cd /tmp/x'
check 0 "" 'env -C /x/.claude/worktrees/lane ./scripts/check-tracked-artifacts.sh'
check 0 "" '/x/.claude/worktrees/lane/scripts/check-tracked-artifacts.sh; git -C /x/.claude/worktrees/lane status'
check 0 "" './scripts/check-tracked-artifacts.sh'
check 0 "" 'ssh host "cd /srv && ls"'
check 0 "" 'cat file | sed s/sleepy/awake/'
# cherry-pick guard: a scratch repo with, then without, a stalled CHERRY_PICK_HEAD
T=$(mktemp -d)
git -C "$T" init -q
git -C "$T" -c user.email=t@t -c user.name=t commit -q --allow-empty -m base
check 0 "" "git -C $T commit -q --allow-empty -m clean"
git -C "$T" rev-parse HEAD > "$T/.git/CHERRY_PICK_HEAD"
check 2 "cherry-pick is in progress" "git -C $T commit -m folded"
check 2 "cherry-pick is in progress" "git -C '$T' add -A; git -C $T commit -m folded"
check 0 "" "git -C $T cherry-pick --abort"
check 0 "" "git -C $T status"
rm -rf "$T"
# merge --delete-branch with stacked children: 2026-10-24, deleting #1931's branch CLOSED child #1936.
# A stub gh answers: PR 10's head is "base-br"; "base-br" has open child 11, any other base has none.
S=$(mktemp -d); cat > "$S/gh" <<'STUB'
#!/usr/bin/env bash
case "$*" in
  *"pr view 10"*) echo base-br ;; *"pr view 20"*) echo lonely-br ;;
  *"--base base-br"*) echo 11 ;; *) echo "" ;;
esac
STUB
chmod +x "$S/gh"; export GUARD_GH="$S/gh"
check 2 "Retarget first" 'gh pr merge 10 -R o/r --squash --delete-branch --admin'
check 0 "" 'gh pr merge 20 -R o/r --squash --delete-branch --admin'
check 0 "" 'gh pr merge 10 -R o/r --squash --admin'
unset GUARD_GH; rm -rf "$S"
[ $fail = 0 ] && echo "guard-bash self-test: PASS" || { echo "guard-bash self-test: FAIL"; exit 1; }
