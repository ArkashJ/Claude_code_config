#!/usr/bin/env python3
"""Mine THIS session's transcript for harvest signals and wrap asks: code reduces, Jev judges.

    python3 ~/.claude/skills/harvest/signals.py [TRANSCRIPT.jsonl]

Cross-repo follow-through lives in ~/.claude/skills/qa/sweep.py (harvest step 0b): each fix
from the session becomes a calibrated Jev family swept across every repo.

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


def main():
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
    print(f"transcript ({'codex' if '/.codex/' in str(path) else 'claude'}): {path}\nsession: {red['meta'].get('session')}  start: {red['meta'].get('start')}  cwd: {red['meta'].get('cwd')}  human turns: {len(turns)}")
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
    out.write_text(json.dumps({"transcript": str(path), "start": red["meta"].get("start"), "signals": signals, "asks": asks, "tool_failures": dict(fails),
                               "jev": {"requests": len(res), "errors": errors, "models": dict(models)}}, indent=1))
    print(f"\njson: {out}")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
