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
n_kept=0
# The first line of `git worktree list --porcelain` is always the main checkout.
main_wt=$(git worktree list --porcelain 2>/dev/null | awk '/^worktree /{print $2; exit}')
if command -v gh >/dev/null && git remote get-url origin >/dev/null 2>&1; then
  merged=$(timeout 10 gh pr list --state merged --limit 200 --json headRefName -q '.[].headRefName' 2>/dev/null | sort -u)
  open=$(timeout 10 gh pr list --state open --limit 200 --json headRefName -q '.[].headRefName' 2>/dev/null | sort -u)
  n_open=$(printf '%s' "$open" | grep -c . || true)
  cur=$(git branch --show-current)
  # Long-lived branches are merged HEADS too: a dev->staging PR puts 'dev' in the
  # merged list, so this script recommended `git branch -D dev` from any feature
  # branch. It was masked only by the "$b" = "$cur" skip below, i.e. it never
  # fired while you happened to be standing on dev. Found 2026-08-18 when an
  # unrelated fix moved off dev and the recommendation appeared.
  default_br=$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's#^origin/##')
  protected=$(printf '%s\n' "$default_br" main master dev develop staging production | grep -v '^$' | sort -u)

  while read -r b; do
    [ -z "$b" ] && continue
    [ "$b" = "$cur" ] && continue
    if printf '%s\n' "$protected" | grep -qxF "$b"; then
      continue
    fi
    # An OPEN PR outranks a merged one on the same head. A branch reused across
    # PRs (merge #957, then reopen #999 off the same head) appears in BOTH
    # lists, and recommending -D there destroys the in-flight PR's branch.
    # 2026-08-18: this fired on feat/pcs-admin-organization-operations while
    # #999 was open and CI-green, i.e. exactly the case the header warns about.
    if printf '%s\n' "$open" | grep -qxF "$b"; then
      n_kept=$((n_kept + 1))
      continue
    fi
    if printf '%s\n' "$merged" | grep -qxF "$b"; then
      out+=("  branch '$b' — PR merged, branch still here: git branch -D $b")
      n_br=$((n_br + 1))
    fi
  done < <(git for-each-ref --format='%(refname:short)' refs/heads)

  # a worktree parked on a merged branch: the work landed, the checkout did not
  while IFS=$'\t' read -r wt br; do
    [ -z "$br" ] && continue
    # Same precedence, and never the main worktree: it is the checkout you are
    # standing in, so "safe to remove" is always wrong for it.
    if printf '%s\n' "$open" | grep -qxF "$br"; then
      continue
    fi
    if [ "$wt" = "$main_wt" ]; then
      continue
    fi
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
    # A monorepo's per-module CLAUDE.md names paths relative to ITS module, not the repo
    # root: apps/web/CLAUDE.md says `internal/notify/templates/templates.go`, which exists at
    # apps/api/internal/... So resolve as a suffix of any TRACKED file before calling it dead.
    # Without this the check reported 21 dead paths in a repo where every one existed, which
    # pins the exit code at 1 forever and trains the reader to ignore the whole report.
    git ls-files --cached -- "*/$p" 2>/dev/null | grep -q . && continue
    # Docs legitimately name files that must NOT exist — gitignored lockfiles, guard
    # targets, "there is no X" corrections. Absent is the documented state, not a rot.
    # "deleted, recover with git show" is a DOCUMENTED state, same as the cases above: the
    # file is meant to be absent and the doc says how to retrieve it. Without these terms the
    # check flags correct, actionable prose and can never go green, which is how a report
    # earns the reader's contempt. Likewise "needs/requires": a doc naming another repo's
    # prerequisite ("TS/JS needs `tsconfig.json`") is not naming a file of THIS repo.
    if grep -F -- "$p" "$f" |
       grep -qiE 'gitignore|exclude|does not exist|there is no|rejects|stray|never|deleted|removed|git show|git history|needs|requires'; then
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
[ "$n_kept" -gt 0 ] && echo "  (kept $n_kept local branch(es) owned by an OPEN PR — never delete these)"
exit $([ "$total" -eq 0 ]; echo $?)
