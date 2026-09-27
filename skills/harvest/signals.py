#!/usr/bin/env python3
"""Mine THIS session's transcript for harvest signals and wrap asks: code reduces, Jev judges.

    python3 ~/.claude/skills/harvest/signals.py [TRANSCRIPT.jsonl] [--related]

--related: also search every repo under $HARVEST_REPO_ROOTS (default ~/Developer:~/Benmore)
for code in the same state space as what this session changed. Example: a notifications PR
finds the other repos' notification, RBAC-gating and streaming code that the same fix or
helper would improve. Code shortlists files by the session's own identifiers, and Jev judges
each (same concern / reusable here / same gap). Each result is a lead for Claude to verify,
never a finding. The rerank cannot surface a file the identifier shortlist missed.

Why: across 187 deduped Claude+Codex sessions (2026-09-27 study), /harvest was run from
memory, never from the transcript, and the follow-up was "are you sure thats ALL YOU
LEARNT???" (9fc47df2), "there were tons of mistakes no??" (b10f8486), "so you acted on
those signals??" (a Codex session). The transcript already has every correction and re-ask;
this makes reading it one command.

Output: every human turn judged once (one Jev request per turn, all questions fanned
out), then
  SIGNALS: turns where the human corrected, re-asked, doubted a claim, or asked for depth.
           Harvest must disposition every one: guard / issue / fix / discard-with-reason.
  ASKS:    each request the human made, routed to the check kind that proves it
           (push, merge, deploy, ...). Wrap verifies each with a command, not a reread
           of its own replies.
Exit 0 ok · 1 any Jev request failed (the counts are then partial) · 2 no transcript.
"""
import concurrent.futures as cf, glob, json, os, re, subprocess, sys, tempfile, time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".claude/skills/qa"))
from hunt import api_key, ask  # noqa: E402  (shared Jev client: retries, pinned model, UA fix)

LEAD, READ = 0.70, 0.30  # jev.md band: act above LEAD, Claude reads the middle, drop below READ

APPROVAL = ("a go-ahead or approval ('yes run jev', 'all approved', 'go with all recs', 'do MAXIMUM WORK'), "
            "an answer to a question the assistant asked, or a brand-new task")
Q = {
    "corrects": {"type": "noul",
        "instructions": "Does `human` correct, reject, or complain about something the assistant did or claimed earlier in this session?",
        "criteria": {"true": {"what": "points out an error, omission, false claim, wasted effort, or wrong direction; or voices frustration with a result",
                              "examples": ["there were tons of mistakes no??", "you cannot rerun ci cd after every push", "Dont ADD TYPESAFE HERE"]},
                     "false": {"what": "does not fault anything the assistant did", "not_for": APPROVAL}}},
    "reask": {"type": "noul",
        "instructions": "Is `human` asking again for something already requested in `earlier_human_turns` that the assistant has not yet delivered?",
        "criteria": {"true": {"what": "repeats or re-demands an earlier request, often with frustration",
                              "examples": ["status?", "commit and push eveerything and give me a handoff prompt", "ensure evertything is pushed"]},
                     "false": {"what": "a first request, or a follow-up that narrows work still in progress", "not_for": APPROVAL}}},
    "doubts_claim": {"type": "noul",
        "instructions": "Does `human` question whether something the assistant reported as done, merged, pushed, deployed, running, or verified is really true?",
        "criteria": {"true": {"examples": ["did you merge and deploy??", "Are the files on main or no??", "so you acted on those signals??", "are the workflows running though or not???"]},
                     "false": "asks for new work or information without doubting a reported result"}},
    "wants_depth": {"type": "noul",
        "instructions": "Does `human` say the assistant's work was too shallow and ask it to cover what it skipped?",
        "criteria": {"true": {"examples": ["are you sure thats ALL YOU LEARNT???", "did you use jev across the codebase to study patterns??", "are you sure the above prompt covers everything"]},
                     "false": {"what": "no complaint that finished work was shallow", "not_for": APPROVAL,
                               "examples": ["status?", "v1 your rec", "Do you have a prompt where I can merge all open prs?", "merge it into main"]}}},
    "area": {"type": "choice",
        "instructions": "If `human` faults the assistant's work, which kind of failure is it?",
        "criteria": {"incomplete": "work left undone, steps skipped, not everything landed",
                     "false_claim": "a status or verification claim that was wrong or unproven",
                     "missed_sources": "did not read transcripts, comments, files, history, or visuals it should have",
                     "cost_or_speed": "too slow, too many tokens or agents, repeated CI/deploys, spend limits",
                     "wrong_scope": "did the wrong thing, or changed what it was told not to",
                     "output_format": "missing the prompt, table, ticket, or interactive questions the human wanted",
                     "tool_or_env": "a tool, auth, permission, hook, or environment failure",
                     "none": "the message does not fault the assistant's work"}},
    "request": {"type": "choice",
        "instructions": "What is the main thing `human` asks the assistant to get done?",
        "criteria": {"push": "commit and push work, get files onto the remote or main",
                     "merge": "merge pull requests", "deploy": "deploy or release to an environment",
                     "cleanup": "delete or prune branches, worktrees, scratch files",
                     "issues_board": "create or update issues, tickets, kanban or project board",
                     "handoff": {"what": "a prompt, plan, next steps, or handoff for a next session",
                                 "examples": ["Do you have a prompt where I can merge all open prs?", "what are next steps?? what does the prompt do?"]},
                     "code_change": "fix, build, or change code or tests",
                     "study": "research, audit, review, or explain something",
                     "none": {"what": "no new request", "examples": ["v1 your rec", "status?", "all approved"]}}},
}


def transcript(argv):
    if argv:
        return Path(argv[0])
    home = Path.home()
    sid = os.environ.get("CLAUDE_CODE_SESSION_ID")
    hits = glob.glob(str(home / f".claude/projects/*/{sid}.jsonl")) if sid else []
    if not hits:
        # Codex exposes no session-id variable, so pick the newest transcript FOR THIS CWD across
        # both harnesses: the running session is the one being written right now. Without the Codex
        # half, a Codex $harvest silently analysed the newest Claude session in the same directory.
        mangled = re.sub(r"[^A-Za-z0-9]", "-", os.getcwd())
        hits = glob.glob(str(home / f".claude/projects/{mangled}/*.jsonl"))
        for f in glob.glob(str(home / ".codex/sessions/*/*/*/*.jsonl")):
            if time.time() - os.path.getmtime(f) < 2 * 86400:
                with open(f, errors="replace") as fh:
                    if json.loads(fh.readline() or "{}").get("payload", {}).get("cwd") == os.getcwd():
                        hits.append(f)
    return Path(max(hits, key=os.path.getmtime)) if hits else None


STOP = set("""return const function import export default string number boolean props children className
await async useState useEffect useMemo useCallback value error response request result undefined context
params config options handler update create delete items length filter render component string object
console assert expect describe self none true false print super class public private static void
index query state false args kwargs typing optional""".split())


SRC_EXT = set("ts tsx js jsx mjs py go rb java kt swift sql rs php cs".split())
SRC = [*(f"*.{e}" for e in "ts tsx js jsx mjs py go rb java kt swift sql rs php cs".split()),
       ":!*.min.*", ":!*.gen.*", ":!**/generated/**", ":!**/vendor/**", ":!**/dist/**"]


def git(repo, *a):
    return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True).stdout


def session_change(repo, since, until):
    """What this session changed: commit subjects, files, added lines. Falls back to the
    uncommitted diff when the session committed nothing."""
    me = git(repo, "config", "user.email").strip()  # --all also fetches teammates' commits from the window
    log = git(repo, "log", "--all", "--no-merges", f"--author={me}", f"--since={since}", f"--until={until}", "-p", "--format=@@C %s",
              "--", ".", ":!*.lock", ":!*lock.json", ":!*.snap", ":!*.min.*")
    log = log or git(repo, "diff", "HEAD")
    subjects = [l[4:] for l in log.splitlines() if l.startswith("@@C ")]
    files = sorted({l[6:] for l in log.splitlines() if l.startswith("+++ b/")})
    added, code = [], False
    for l in log.splitlines():  # added lines of source files only; docs and JSON artifacts are not concerns
        if l.startswith("+++ b/"):
            code = l.rsplit(".", 1)[-1] in SRC_EXT
        elif code and l.startswith("+"):
            added.append(l[1:])
    added = "\n".join(added)
    return subjects, files, added


def related(meta, key):
    cwd = Path(meta.get("cwd") or os.getcwd())
    top = git(cwd, "rev-parse", "--show-toplevel").strip()
    # A session run from a folder of repos (e.g. ~/Developer/<client>/ holding backend, frontend,
    # infra) changes several repos; read every repo under it that the session committed to.
    mine = [Path(top)] if top else [Path(g).parent for g in glob.glob(str(cwd / "*/.git")) + glob.glob(str(cwd / "*/*/.git"))]
    subjects, files, added = [], set(), ""
    for rp in mine:
        su, fi, ad = session_change(rp, meta.get("start", "1 day ago"), meta.get("end", "now"))
        subjects += su; files |= {(rp, f) for f in fi}; added += ad + "\n"
    if not mine:
        return print(f"\nRELATED: no git repo at or under {cwd}: unable to measure"), 1
    # Domain terms only: compound identifiers (sendNotification, notify_user) from added CODE lines.
    # Plain words ("button", "portal") and the repo's own name matched 24,603 files in the first
    # trial and every lead was noise (2026-09-27, session 9fc47df2).
    ids = Counter(t for t in re.findall(r"\b[a-z]+(?:[A-Z][a-z0-9]+)+\b|\b[a-z]+(?:_[a-z0-9]+)+\b|\b[A-Z][a-z]+(?:[A-Z][a-z0-9]+)+\b", added)
                  if t not in STOP and not any(rp.name.lower() in t.lower() for rp in mine))
    roots = [Path(os.path.expanduser(r)) for r in os.environ.get("HARVEST_REPO_ROOTS", "~/Developer:~/Benmore").split(":")]
    found = subprocess.run(["find", *map(str, filter(Path.exists, roots)), "-maxdepth", "4", "(", "-name", "node_modules", "-o", "-name", "worktrees",
                            "-o", "-name", "tmp", ")", "-prune", "-o", "-name", ".git", "-type", "d", "-print"], capture_output=True, text=True).stdout
    repos = sorted({Path(g).parent for g in found.split()})
    df, hits = Counter(), {}
    for t, _ in ids.most_common(30):  # ponytail: one git grep per term per repo; swap for an index if roots grow
        hits[t] = [(rp, f) for rp in repos for f in git(rp, "grep", "-l", "-I", "-w", "-F", t, "--", *SRC).splitlines()
                   if (rp, f) not in files]
        df[t] = len(hits[t])
    terms = [t for t in hits if 0 < df[t] <= 150][:14]  # a term in >150 files is vocabulary, not a concern
    if not terms:
        return print(f"\nRELATED: no distinctive identifiers in this session's code changes ({len(ids)} candidates, all too common or unique)"), 0
    score = Counter()
    for t in terms:
        for k in hits[t]:
            score[k] += 1 / (1 + df[t]) ** 0.5  # rarer shared identifiers weigh more
    per_repo, cands = Counter(), []
    for (rp, f), n in score.most_common():
        if per_repo[rp] >= 6 or len(cands) >= 36:  # ponytail: 6/repo, 36 total keeps it one short pass
            continue
        per_repo[rp] += 1
        text = (rp / f).read_text(errors="replace").splitlines()
        hit = next((i for i, l in enumerate(text) if any(t in l for t in terms)), 0)
        cands.append({"repo": rp.name, "path": f, "shared_terms": [t for t in terms if (rp, f) in hits[t]],
                      "snippet": "\n".join(text[max(0, hit - 12):hit + 25])[:1800]})
    change = {"commit_subjects": subjects[:15], "files": sorted(f for _, f in files)[:20], "added_code_excerpt": added[:2500]}
    RQ = {
        "same_concern": {"type": "noul", "instructions": "Does `candidate.snippet` handle the same concern as `session_change`: the same feature area, data flow, or control (for example notifications, permissions, streaming)?",
                         "criteria": {"true": "the same kind of behaviour, even in another repo or language",
                                      "false": {"what": "a different concern", "not_for": "code that shares only a common word, a generic utility, or a library name"}}},
        "reusable": {"type": "noul", "instructions": "Could a helper, pattern, hook, or fix from `session_change` be applied to `candidate.snippet` to improve it?"},
        "same_gap": {"type": "noul", "instructions": "Does `candidate.snippet` show the same defect, missing check, or gap that `session_change` fixed or added?"},
    }

    def one(c):
        try:
            a = ask(key, {"session_change": change, "candidate": c}, RQ)["answers"]
            return c | {k: round(v["noul"], 2) for k, v in a.items()}
        except Exception as e:
            return c | {"error": str(e)[:160]}

    with cf.ThreadPoolExecutor(6) as ex:
        res = list(ex.map(one, cands))
    errs = sum("error" in r for r in res)
    ok = [r for r in res if "error" not in r]
    for r in ok:  # composite in code (jev.md): concern gates, reuse/gap ranks
        r["rank"] = round(0.4 * r["same_concern"] + 0.6 * max(r["reusable"], r["same_gap"]), 2)
    ok.sort(key=lambda r: -r["rank"])
    leads = [r for r in ok if r["same_concern"] > LEAD and max(r["reusable"], r["same_gap"]) > LEAD]
    print(f"\nRELATED: session terms {terms}\n  {len(repos)} repos searched, {len(score)} files share a term, "
          f"{len(cands)} judged, {errs} errors, {len(leads)} leads (concern and reuse/gap both > {LEAD})")
    # Every listed file costs Claude a read, and the user is token-constrained: leads plus the top 5 of the band.
    reads = [r for r in ok if r not in leads and r["rank"] >= READ][:5]
    print(f"  read list: {len(leads)} leads + {len(reads)} band files (band total {sum(r['rank'] >= READ for r in ok) - len(leads)})")
    for r in leads + reads:
        mark = "LEAD" if r in leads else "read"
        print(f"  {mark} {r['rank']:.2f} concern={r['same_concern']} reuse={r['reusable']} gap={r['same_gap']}  {r['repo']}/{r['path']}")
    return ok, 1 if errs else 0


def main():
    want_related = "--related" in sys.argv
    sys.argv = [a for a in sys.argv if a != "--related"]
    path = transcript(sys.argv[1:])
    if not path or not path.exists():
        sys.exit(print("no transcript found; pass its path", file=sys.stderr) or 2)
    # The brew/pipx harness-extractor 1.0.0 predates Codex support: it reads a Codex rollout as
    # 0 turns and exits 0, so this script reported "0 signals" on a session full of them. Prefer
    # the source checkout when present, and treat 0 turns as unable-to-measure, never as clean.
    src = Path.home() / "Developer/personal/extractor/harness_extractor.py"
    cmd = [sys.executable, str(src)] if src.exists() else ["harness-extractor"]
    r = subprocess.run([*cmd, "--json", str(path)], capture_output=True, text=True)
    red = json.loads(r.stdout)[0] if r.returncode == 0 and r.stdout.strip() else {"meta": {}, "turns": []}
    turns = [t for t in red["turns"] if not t["human"].startswith("[invoked ")]
    if not turns:
        sys.exit(print(f"0 human turns read from {path} by {cmd[-1]}: unable to measure (Codex needs extractor > 1.0.0)", file=sys.stderr) or 2)
    print(f"transcript ({'codex' if '/.codex/' in str(path) else 'claude'}): {path}\nsession: {red['meta'].get('session')}  cwd: {red['meta'].get('cwd')}  human turns: {len(turns)}")
    key = api_key()

    def judge(i):
        t = turns[i]
        state = {"human": t["human"][:1500],
                 "earlier_human_turns": [u["human"][:300] for u in turns[max(0, i - 6):i]],
                 "assistant_reply_before": turns[i - 1]["reply"][:600] if i else ""}
        try:
            r = ask(key, state, Q)
            return i, {k: (v["noul"] if "noul" in v else {"choice": v["choice"], "conf": round(v["confidence"], 2)})
                       for k, v in r["answers"].items()}, r.get("model")
        except Exception as e:
            return i, {"error": str(e)[:200]}, None

    with cf.ThreadPoolExecutor(6) as ex:  # jev.md rule 18: stay at 6-8 in flight
        res = list(ex.map(judge, range(len(turns))))
    errors = sum("error" in a for _, a, _ in res)
    models = Counter(m for _, _, m in res if m)
    print(f"jev: {len(res)} requests, {errors} errors, model {dict(models)}")

    flags = ("corrects", "reask", "doubts_claim", "wants_depth")
    signals, asks, reads = [], [], 0
    for i, a, _ in res:
        if "error" in a:
            continue
        t, top = turns[i], max(a[f] for f in flags)
        hit = [f for f in flags if a[f] > LEAD]
        reads += not hit and top >= READ
        if hit:
            signals.append({"turn": t["n"], "flags": hit, "area": a["area"]["choice"], "p": round(top, 2),
                            "emphatic": t["emphatic"], "human": t["human"][:220], "failed_before": turns[i - 1]["failed"][:2] if i else []})
        if a["request"]["choice"] != "none":
            asks.append({"turn": t["n"], "kind": a["request"]["choice"], "conf": a["request"]["conf"], "human": t["human"][:160]})
    signals.sort(key=lambda s: (-s["p"], -s["emphatic"]))
    fails = Counter(re.sub(r"\d+", "N", f.split("\n")[0])[:70] for t in turns for f in t["failed"])

    print(f"\nSIGNALS: {len(signals)} of {len(turns)} turns above {LEAD} ({reads} more in the {READ}-{LEAD} band: read those turns yourself)")
    for s in signals:
        print(f"  t{s['turn']:<3} {','.join(s['flags']):<28} {s['area']:<14} p={s['p']}  {s['human']!r}")
    print(f"\nTOOL FAILURES: {sum(fails.values())} total, {len(fails)} shapes")
    for f, c in fails.most_common(8):
        print(f"  {c:>3}x {f}")
    print(f"\nASKS: {len(asks)} requests. Wrap proves each kind with a command, never by rereading its own replies:")
    for a in asks:
        print(f"  t{a['turn']:<3} {a['kind']:<12} conf={a['conf']}  {a['human']!r}")
    out = Path(tempfile.gettempdir()) / f"harvest-signals-{red['meta'].get('session') or path.stem}.json"
    out.write_text(json.dumps({"transcript": str(path), "signals": signals, "asks": asks, "tool_failures": dict(fails),
                               "jev": {"requests": len(res), "errors": errors, "models": dict(models)}}, indent=1))
    rel, rel_err = related(red["meta"], key) if want_related else (None, 0)
    out.write_text(json.dumps({"transcript": str(path), "signals": signals, "asks": asks, "tool_failures": dict(fails), "related": rel,
                               "jev": {"requests": len(res), "errors": errors, "models": dict(models)}}, indent=1))
    print(f"\njson: {out}")
    sys.exit(1 if errors or rel_err else 0)


if __name__ == "__main__":
    main()
