#!/bin/sh
# Stop gate. Harvest 2026-09-02 over 236 sessions: the human said "keep going" (40
# sessions), "do all next steps" (39), "no deferrals / fix everything" (38) and
# "do a /wrap" (42) — four hats on one behaviour: the turn ended with work still
# available. The rule already lived in /mission and did not land; prose never does
# (cd-chain: 186 blocks in 110 sessions with the rule in CLAUDE.md the whole time).
# So this is a gate. Exit 2 = do not stop; stderr goes back to the model.
#
# Blocks when the final reply DEFERS work with no accepted reason, or claims done
# on a dirty tree. Accepted reasons: `blocked: <failing cmd>`, `not attempted`,
# `human decision` (blast radius, /start rule 7). Never blocks twice in a row.
in=$(cat)
[ "$(printf '%s' "$in" | /usr/bin/jq -r '.stop_hook_active // false')" = "true" ] && exit 0

msg=$(printf '%s' "$in" | /usr/bin/jq -r '.last_assistant_message // empty')
if [ -z "$msg" ]; then
  tp=$(printf '%s' "$in" | /usr/bin/jq -r '.transcript_path // empty')
  [ -r "$tp" ] && msg=$(/usr/bin/grep '"role":"assistant"' "$tp" | tail -1 \
    | /usr/bin/jq -r '[.message.content[]? | select(.type=="text") | .text] | join("\n")' 2>/dev/null)
fi
[ -n "$msg" ] || exit 0

defers=$(printf '%s' "$msg" | /usr/bin/grep -Eic \
  '\b(next steps?|follow[- ]?ups?|defer(red|ring)?|in a (later|future|separate|follow-up) (pr|pass|session|turn)|left for later|for a later (pr|pass|session)|remaining work)\b')
excused=$(printf '%s' "$msg" | /usr/bin/grep -Eic '\b(blocked:|not attempted|human decision|say go|approved command away|needs your (go|approval|call))')

if [ "$defers" -gt 0 ] && [ "$excused" -eq 0 ]; then
  cat >&2 <<'MSG'
Stop blocked: the reply defers work with no accepted reason. Either DO the deferred items now,
or label each one `blocked: <the failing command>`, `not attempted`, or `human decision` (merge/
deploy/delete — one approved command away, with a recommendation). "Next steps" the model is
allowed to take are not next steps; they are the rest of the task.
MSG
  exit 2
fi

dir=${CLAUDE_PROJECT_DIR:-.}
if git -C "$dir" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  dirty=$(git -C "$dir" status --porcelain 2>/dev/null | /usr/bin/grep -v '^??' | wc -l | tr -d ' ')
  claims=$(printf '%s' "$msg" | /usr/bin/grep -Eic '\b(done|completed?|shipped|merged|wrapped|landed)\b')
  if [ "$dirty" -gt 0 ] && [ "$claims" -gt 0 ]; then
    echo "Stop blocked: reply claims done but $dirty tracked file(s) are modified and uncommitted (/start rule 3: non-empty git status at a stopping point is a defect). Commit and push, or say why they cannot be committed." >&2
    exit 2
  fi
fi
exit 0
