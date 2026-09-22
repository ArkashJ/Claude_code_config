#!/usr/bin/env python3
"""PR queue triage: code computes stacks, containment, overlap, CI and size; Jev judges each
diff's risk; code turns both into a review tier, a model, and a merge order. Read-only.

usage: review.py OWNER/REPO [--limit 100] [--out DIR]
"""
import argparse, collections, concurrent.futures as cf, json, re, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from hunt import api_key, ask

DIFF_CHARS = 60_000  # ~15k tokens; Jev's state budget is 32k and irrelevant detail costs accuracy
TESTS = re.compile(r"(^|/)(tests?|__tests__|e2e|spec)/|\.(test|spec)\.\w+$")
FIELDS = "number,title,isDraft,additions,deletions,changedFiles,files,mergeable,reviewDecision,createdAt,headRefName,headRefOid,baseRefName,statusCheckRollup,author"

# Tier → who reviews. Used by the review workflow and as the default model map for agents.
TIERS = {
    "blocked": ("—", "Fix first: CI failing or conflicting. Don't spend review on it."),
    "covered": ("—", "Already contained in another open PR; review that one, then close this."),
    "skim": ("haiku", "Small, contained, tested. Read the diff; approve or raise one issue."),
    "review": ("sonnet", "Normal review: correctness, edge cases, tests match the behaviour."),
    "deep": ("opus", "Auth/data/shared-surface/huge. Opus review plus `qa` PLAN on the blast radius."),
}

QUESTIONS = {
    "touches_auth": {"type": "noul", "instructions": "Does `diff` change authentication, authorization, permission checks, session handling, or tenant scoping?"},
    "changes_shared": {"type": "noul", "instructions": "Does `diff` change a component, hook, helper, style, or module that several screens or features use, rather than a single page or feature?"},
    "data_write": {"type": "noul", "instructions": "Does `diff` change how data is created, updated, deleted, migrated, or stored?"},
    "behavior_change": {"type": "noul", "instructions": "Does `diff` change behaviour a user can notice, rather than only refactoring, renaming, formatting, docs, tests, or config?"},
    "tests_cover": {"type": "noul", "instructions": "Do the tests added or changed in `diff` exercise the behaviour that `diff` changes?",
                    "criteria": {"true": "A test in the diff would fail if the changed behaviour broke", "false": "No tests in the diff, or the tests don't touch the changed behaviour"}},
    "risk": {"type": "score", "instructions": "If `diff` had a bug, how bad would it be for users?",
             "criteria": ["Cosmetic: text, styling, docs, or tests only",
                          "Contained: one screen or feature misbehaves, easy to notice and roll back",
                          "Spreading: a shared component, API contract, or cross-feature flow breaks in several places",
                          "Severe: wrong data saved, access granted wrongly, billing or migration damage, hard to undo"]},
}


def gh(*args):
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=True).stdout


def ci_state(pr):
    states = {(c.get("conclusion") or c.get("state") or "").upper() for c in pr.get("statusCheckRollup") or []}
    if states & {"FAILURE", "ERROR", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED"}:
        return "failing"
    if states & {"PENDING", "QUEUED", "IN_PROGRESS", ""} and states:
        return "pending"
    return "passing" if states else "none"


def never_ran(repo, sha):
    """repo B 2026-09-22: every "failing" check was 'The job was not started because an Actions
    budget is preventing further use' (0 steps), and triage called it CI failure. True when every
    failed check-run on `sha` carries a not-started annotation."""
    ids = gh("api", f"repos/{repo}/commits/{sha}/check-runs", "--jq", '.check_runs[] | select(.conclusion=="failure") | .id').split()
    return bool(ids) and all("not started" in gh("api", f"repos/{repo}/check-runs/{i}/annotations", "--jq", ".[].message") for i in ids)


def contained_in(repo, prs):
    """head of A is an ancestor of head of B (B open, bigger) → A is covered by B."""
    out = {}
    big = sorted(prs, key=lambda p: -(p["additions"] + p["deletions"]))
    for a in prs:
        for b in big:
            if b is a or b["additions"] + b["deletions"] <= a["additions"] + a["deletions"]:
                continue
            try:
                st = json.loads(gh("api", f"repos/{repo}/compare/{b['headRefOid']}...{a['headRefOid']}", "--jq", "{status}"))["status"]
            except subprocess.CalledProcessError:
                continue
            if st in ("behind", "identical"):
                out[a["number"]] = b["number"]
                break
    return out


def patches(repo, n):
    """Per-file patches (works for PRs too big for `gh pr diff`)."""
    raw = gh("api", "--paginate", f"repos/{repo}/pulls/{n}/files?per_page=100", "--jq", ".[] | {filename, patch}")
    return [json.loads(l) for l in raw.splitlines() if l.strip()]


def judge(key, repo, pr):
    """Chunk files into ≤DIFF_CHARS requests; a PR is as risky as its riskiest chunk."""
    chunks, cur = [], []
    for f in patches(repo, pr["number"]):
        piece = f"--- {f['filename']}\n{(f.get('patch') or '(binary or too large)')[:DIFF_CHARS]}\n"
        if cur and sum(map(len, cur)) + len(piece) > DIFF_CHARS:
            chunks.append(cur); cur = []
        cur.append(piece)
    chunks.append(cur)
    worst, hot = None, []
    for c in chunks[:40]:  # ponytail: caps a mega-PR at ~40 requests; the rest is marked unjudged
        a = ask(key, {"title": pr["title"], "diff": "".join(c)}, QUESTIONS)["answers"]
        j = {k: (v["noul"] if v["type"] == "noul" else {"score": v["score"], "confidence": v["confidence"]}) for k, v in a.items()}
        if j["risk"]["score"] >= 2:
            hot += [p.split("\n", 1)[0][4:] for p in c]
        if worst is None:
            worst = j
        else:
            for k, v in j.items():
                if k == "tests_cover":
                    worst[k] = min(worst[k], v)
                elif k == "risk":
                    worst[k] = max(worst[k], v, key=lambda x: x["score"])
                else:
                    worst[k] = max(worst[k], v)
    worst["chunks"], worst["unjudged_chunks"], worst["hot_files"] = len(chunks), max(0, len(chunks) - 40), hot[:15]
    return worst


def tier(pr, j, ci, covered_by):
    """Routing policy lives here, in code, where it can be read and changed."""
    if covered_by:
        return "covered", f"contained in #{covered_by}"
    if ci in ("failing", "not_run") or pr["mergeable"] == "CONFLICTING":
        after, why = tier(pr, j, "passing", None)
        cause = {"failing": "CI failing", "not_run": "CI never ran (Actions budget/runner): fix billing, not code"}.get(ci, "merge conflict")
        return "blocked", f"{cause} → then {after} ({TIERS[after][0]}): {why}"
    size = pr["additions"] + pr["deletions"]
    r = j["risk"]
    why = []
    if size > 2000: why.append(f"{size:,} lines")
    if r["score"] >= 2: why.append(f"risk {r['score']:.1f}")
    if j["touches_auth"] >= 0.7: why.append("auth")
    if j["data_write"] >= 0.7: why.append("data writes")
    if j["changes_shared"] >= 0.7 and j["tests_cover"] < 0.5: why.append("shared surface, untested")
    if j.get("hot_files"):
        why.append("hot: " + ", ".join(Path(f).name for f in j["hot_files"][:4]))
    if j.get("unjudged_chunks"):
        why.append(f"{j['unjudged_chunks']} chunks unjudged")
    if size > 2000 or r["score"] >= 2 or j["touches_auth"] >= 0.7 or j["data_write"] >= 0.7 or (j["changes_shared"] >= 0.7 and j["tests_cover"] < 0.5):
        return "deep", ", ".join(why)
    t = "skim" if size < 150 and r["score"] < 1.2 and j["tests_cover"] >= 0.5 else "review"
    if r["confidence"] < 0.5 and t == "skim":  # unsure → one tier up
        t = "review"
    return t, f"risk {r['score']:.1f} (conf {r['confidence']:.2f}), tests {'yes' if j['tests_cover'] >= 0.5 else 'no'}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo", help="OWNER/REPO")
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--out")
    args = ap.parse_args()
    key = api_key()
    prs = json.loads(gh("pr", "list", "-R", args.repo, "--state", "open", "--limit", str(args.limit), "--json", FIELDS))
    heads = {p["headRefName"]: p["number"] for p in prs}
    covered = contained_in(args.repo, prs)
    with cf.ThreadPoolExecutor(8) as pool:
        futs = {p["number"]: pool.submit(judge, key, args.repo, p) for p in prs if p["number"] not in covered}
    judged, errors = {}, []
    for n, f in futs.items():
        try:
            judged[n] = f.result()
        except Exception as e:
            errors.append((n, str(e)[:200]))

    files_of = {p["number"]: {f["path"] for f in p["files"]} for p in prs}
    rows = []
    for p in prs:
        n, ci = p["number"], ci_state(p)
        if ci == "failing" and never_ran(args.repo, p["headRefOid"]):
            ci = "not_run"
        j = judged.get(n)
        if j or n in covered:
            t, why = tier(p, j, ci, covered.get(n))
        else:  # Jev failed: route on size alone, never downgrade
            size = p["additions"] + p["deletions"]
            t, why = ("deep" if size > 2000 else "review"), "Jev failed; routed on size"
        overlap = sorted(m for m in files_of if m != n and files_of[n] & files_of[m] and m not in covered)
        rows.append({"n": n, "title": p["title"][:70], "draft": p["isDraft"], "size": p["additions"] + p["deletions"],
                     "ci": ci, "tier": t, "model": TIERS[t][0], "why": why, "stacked_on": heads.get(p["baseRefName"]),
                     "overlap": overlap, "jev": j})

    # Merge order: stack parents before children; then unblocked, low risk, small, few overlaps.
    rank = {"skim": 0, "review": 1, "deep": 2, "blocked": 3, "covered": 4}
    by_n = {r["n"]: r for r in rows}
    def depth(r):
        d, seen = 0, set()
        while r["stacked_on"] in by_n and r["n"] not in seen:
            seen.add(r["n"]); r = by_n[r["stacked_on"]]; d += 1
        return d
    rows.sort(key=lambda r: (rank[r["tier"]], depth(r), len(r["overlap"]), r["size"]))

    out = Path(args.out or Path.home() / ".claude/qa-runs" / args.repo.replace("/", "_"))
    out.mkdir(parents=True, exist_ok=True)
    (out / "review.json").write_text(json.dumps(rows, indent=1))
    tally = collections.Counter(r["tier"] for r in rows)
    lines = [f"# PR queue: {args.repo}", "", f"open PRs: {len(prs)} · " + " · ".join(f"{t} {tally[t]}" for t in TIERS if tally[t])
             + (f" · Jev errors {len(errors)}" if errors else ""), "",
             "| # | PR | draft | size | CI | tier | model | stacked on | overlaps | why |", "|---|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(rows, 1):
        lines.append(f"| {i} | #{r['n']} {r['title']} | {'y' if r['draft'] else ''} | {r['size']:,} | {r['ci']} | {r['tier']} | {r['model']} | "
                     f"{'#' + str(r['stacked_on']) if r['stacked_on'] else ''} | {', '.join('#' + str(m) for m in r['overlap'][:6])} | {r['why']} |")
    lines += ["", "Tiers: " + " · ".join(f"**{t}** ({m}): {d}" for t, (m, d) in TIERS.items())]
    (out / "review.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
