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
check 2 "cd X" 'cd /tmp/x && make'
check 2 "cd X" 'ls; cd /tmp/x; make'
check 2 "cd X" 'true && cd /tmp/x && make'
# must allow
check 0 "" 'git -C /tmp/x status'
check 0 "" 'uv --directory /tmp/x run pytest'
check 0 "" 'python3 -c "import time; time.sleep(1)"'
check 0 "" 'grep -rn "asleep" src/'
check 0 "" 'echo cd /tmp/x'
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
[ $fail = 0 ] && echo "guard-bash self-test: PASS" || { echo "guard-bash self-test: FAIL"; exit 1; }
