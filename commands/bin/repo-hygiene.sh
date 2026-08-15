#!/usr/bin/env bash
# repo-hygiene.sh — report stale worktrees, branches, and doc claims. REPORTS ONLY.
#
#   repo-hygiene.sh [--brief] [DIR]
#
# Deletes nothing, ever. Blast radius belongs to a human; this only removes the excuse
# that nobody knew. Exit 1 = something is stale, so /start and /wrap can gate on it.
#
# --brief prints ONE line and is SILENT when clean: it runs from the SessionStart hook,
# where every line costs context in all 100+ sessions, most of which are clean.
#
# Every check exists because a harvested session paid for it:
#   prunable worktrees       71d1d872, 4f58d912, 0b192049 — "cleanup only when human shouts"
#   merged-PR branches       71d1d872, 4ed30d92 — `git branch --merged` LIES after a squash
#                            merge, so merge state comes from `gh pr`, never from git
#   open-PR branches         0b192049 — a sweep declared "cleanup done" while the survivors
#                            were the contents of two open PRs
#   worktree on merged br.   ca8cacbc — a forgotten worktree owned main and blocked a checkout
#   dirty agent-instr files  39771011 — session opened with both CLAUDE.md files uncommitted
#                            from a prior session, costing a triage turn
#   dead paths in CLAUDE.md  c83056ea, 3ba29048 — an auto-loaded file pointed at a launch
#                            checklist that did not exist; agents read this file every session
set -uo pipefail

BRIEF=0
DIR="$PWD"
for arg in "$@"; do
  case "$arg" in --brief) BRIEF=1 ;; --*) ;; *) DIR="$arg" ;; esac
done
cd "$DIR" 2>/dev/null || exit 0
git rev-parse --git-dir >/dev/null 2>&1 || exit 0

out=()          # collected report lines; counts come from array lengths, not subshells
n_wt=0; n_br=0; n_wtm=0; n_doc=0; n_path=0

# 1. worktrees whose directory is gone
n_wt=$(git worktree list 2>/dev/null | grep -c 'prunable' || true)
[ "$n_wt" -gt 0 ] && out+=("  $n_wt prunable worktree(s) — dir gone: git worktree prune")

# 2/3/4. branch + worktree classification from PR state, never from git's merge base
n_open=0
if command -v gh >/dev/null && git remote get-url origin >/dev/null 2>&1; then
  merged=$(timeout 10 gh pr list --state merged --limit 200 --json headRefName -q '.[].headRefName' 2>/dev/null | sort -u)
  open=$(timeout 10 gh pr list --state open --limit 200 --json headRefName -q '.[].headRefName' 2>/dev/null | sort -u)
  n_open=$(printf '%s' "$open" | grep -c . || true)
  cur=$(git branch --show-current)

  while read -r b; do
    [ -z "$b" ] && continue
    [ "$b" = "$cur" ] && continue
    if printf '%s\n' "$merged" | grep -qxF "$b"; then
      out+=("  branch '$b' — PR merged, branch still here: git branch -D $b")
      n_br=$((n_br + 1))
    fi
  done < <(git for-each-ref --format='%(refname:short)' refs/heads)

  # a worktree parked on a merged branch: the work landed, the checkout did not
  while IFS=$'\t' read -r wt br; do
    [ -z "$br" ] && continue
    if printf '%s\n' "$merged" | grep -qxF "$br"; then
      out+=("  worktree '$wt' on merged branch '$br' — safe to remove")
      n_wtm=$((n_wtm + 1))
    fi
  done < <(git worktree list --porcelain 2>/dev/null |
           awk '/^worktree /{w=$2} /^branch /{sub("refs/heads/","",$2); print w"\t"$2}')
fi

# 5. auto-loaded instruction files left dirty for the next session to inherit
while read -r line; do
  [ -z "$line" ] && continue
  out+=("  uncommitted agent-instruction file (next session auto-reads it): $line")
  n_doc=$((n_doc + 1))
done < <(git status --porcelain -- '*CLAUDE.md' '*AGENTS.md' '*RUNBOOK.md' 2>/dev/null)

# 6. paths an auto-loaded file tells agents to use, that do not exist
for f in CLAUDE.md AGENTS.md; do
  [ -f "$f" ] || continue
  while read -r p; do
    [ -z "$p" ] && continue
    [ -e "$p" ] && continue
    # A leading slash means a route or URL, not a file on disk (`/skills.json`).
    case "$p" in /*) continue ;; esac
    # Docs legitimately name files that must NOT exist — gitignored lockfiles, guard
    # targets, "there is no X" corrections. Absent is the documented state, not a rot.
    if grep -F -- "$p" "$f" |
       grep -qiE 'gitignore|exclude|does not exist|there is no|rejects|stray|never'; then
      continue
    fi
    out+=("  $f names '$p' which does not exist"); n_path=$((n_path + 1))
  done < <(grep -oE '`[a-zA-Z0-9_./-]+\.(sh|py|go|ts|js|md|yaml|yml|json)`' "$f" 2>/dev/null |
           tr -d '`' | sort -u)
done

total=$((n_wt + n_br + n_wtm + n_doc + n_path))

if [ "$BRIEF" -eq 1 ]; then
  [ "$total" -eq 0 ] && exit 0        # silent when clean
  parts=()
  [ "$n_wt"   -gt 0 ] && parts+=("${n_wt} prunable worktree(s)")
  [ "$n_br"   -gt 0 ] && parts+=("${n_br} merged-PR branch(es)")
  [ "$n_wtm"  -gt 0 ] && parts+=("${n_wtm} worktree(s) on merged branches")
  [ "$n_doc"  -gt 0 ] && parts+=("${n_doc} dirty agent-instruction file(s)")
  [ "$n_path" -gt 0 ] && parts+=("${n_path} dead path(s) named in CLAUDE.md/AGENTS.md")
  msg=$(printf '%s, ' "${parts[@]}"); msg=${msg%, }
  echo "[hygiene] $msg — run ~/.claude/commands/bin/repo-hygiene.sh for detail. Deletions need your OK."
  exit 1
fi

echo "== repo hygiene: $(basename "$PWD") =="
if [ "$total" -eq 0 ]; then
  echo "  clean"
else
  printf '%s\n' "${out[@]}"
fi
[ "$n_open" -gt 0 ] && echo "  (keeping $n_open branch(es) owned by open PRs — never delete these)"
exit $([ "$total" -eq 0 ]; echo $?)
