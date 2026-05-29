#!/usr/bin/env bash
# Merged statusline: shell prompt info + context-mode savings.
# Claude Code pipes a JSON blob on stdin with model, workspace, session, version.

set -u

input="$(cat)"

extract() {
  printf '%s' "$input" | /usr/bin/python3 -c "
import json,sys
try:
  d=json.loads(sys.stdin.read())
  cur=d
  for k in '''$1'''.split('.'):
    cur=cur.get(k) if isinstance(cur,dict) else None
    if cur is None: break
  print(cur if cur is not None else '')
except Exception:
  print('')
"
}

cwd="$(extract 'workspace.current_dir')"
[ -z "$cwd" ] && cwd="$(extract 'cwd')"
[ -z "$cwd" ] && cwd="$PWD"
short_cwd="${cwd/#$HOME/~}"
model="$(extract 'model.display_name')"
[ -z "$model" ] && model="$(extract 'model.id')"

branch=""
if git -C "$cwd" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  branch="$(git -C "$cwd" symbolic-ref --short HEAD 2>/dev/null \
    || git -C "$cwd" rev-parse --short HEAD 2>/dev/null)"
fi

ctx_out=""
ctx_bin="$HOME/.claude/plugins/marketplaces/context-mode/bin/statusline.mjs"
if [ -x "$ctx_bin" ] || [ -f "$ctx_bin" ]; then
  ctx_out="$(printf '%s' "$input" | node "$ctx_bin" 2>/dev/null | head -n1)"
fi

transcript="$(extract 'transcript_path')"
model_id="$(extract 'model.id')"
ctx_pct="$(printf '%s' "$input" | /usr/bin/python3 -c "
import json,sys,os
try:
  d=json.loads(sys.stdin.read())
  tp=d.get('transcript_path') or ''
  mid=(d.get('model') or {}).get('id') or ''
  win=1000000 if '1m' in mid.lower() or 'opus-4-7' in mid.lower() else 200000
  if not tp or not os.path.exists(tp):
    sys.exit(0)
  used=0
  with open(tp,'r') as f:
    for line in f:
      try:
        m=json.loads(line)
      except: continue
      u=(((m.get('message') or {}).get('usage')) or {})
      if u:
        v=(u.get('input_tokens') or 0)+(u.get('cache_read_input_tokens') or 0)+(u.get('cache_creation_input_tokens') or 0)
        if v>used: used=v
  if used<=0: sys.exit(0)
  pct=used*100.0/win
  print(f'{pct:.0f}% ctx ({used//1000}k/{win//1000}k)')
except Exception:
  pass
" 2>/dev/null)"

DIM=$'\033[2m'; CYAN=$'\033[36m'; GREEN=$'\033[32m'; MAGENTA=$'\033[35m'; YELLOW=$'\033[33m'; RESET=$'\033[0m'

out="${CYAN}${short_cwd}${RESET}"
[ -n "$branch" ] && out+=" ${DIM}·${RESET} ${GREEN}${branch}${RESET}"
[ -n "$model" ]  && out+=" ${DIM}·${RESET} ${MAGENTA}${model}${RESET}"
[ -n "$ctx_pct" ] && out+=" ${DIM}·${RESET} ${YELLOW}${ctx_pct}${RESET}"
[ -n "$ctx_out" ] && out+=" ${DIM}·${RESET} ${ctx_out}"

printf '%s' "$out"
