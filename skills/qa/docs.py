#!/usr/bin/env python3
"""Jev layer for doc consolidation (pairs with the document-consolidation skill's preserve.py guard).
Generalised from the eVillage run (2026-09-22: 184 → 53 docs, PR #677).

  docs.py REPO docs     classify every .md: kind, area, still-guidance, filler score
  docs.py REPO claims   check each code-citing claim against the code it cites
  docs.py REPO decide   per-doc disposition + destination owner (hard keeps enforced in code)
  docs.py REPO plan     tasks with Jev-picked model, need, and effort
  docs.py REPO dropped  after writers finish: claims from deleted docs missing from their owner → review queue

Config: REPO/.qa/docs.json = {"goal": str, "owners": {path: scope}, "risk": {path: note},
        "code_dirs": [...], "exclude": [glob...]}. Outputs: ~/.claude/qa-runs/<repo>/docs/*.json
"""
import collections, concurrent.futures as cf, fnmatch, json, re, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from hunt import api_key, ask

HARD_KEEP = {"client_source", "agent_instructions", "generated", "third_party"}  # Jev tried to delete transcripts once
BODY_CHARS = 90_000
REF = re.compile(r"(?<![\w/.-])(?:[\w-]+/)+[\w.-]+\.\w{1,5}|`[A-Za-z_][\w.]{2,}`")

DOC_Q = {
    "kind": {"type": "choice", "instructions": "What kind of document is `doc`? Judge by content and purpose, not only `path`.", "criteria": {
        "client_source": "Record of what a client said or asked for: call/meeting transcript or client-supplied requirements.",
        "current_reference": "How the system works now, or standing rules: architecture, conventions, runbook, contract, design system, test guide.",
        "agent_instructions": "Instructions or prompts for an AI coding agent: skill, slash command, workflow or handoff prompt.",
        "plan_or_spec": "Forward-looking plan, spec, or proposal organised as tasks, phases, or steps.",
        "dated_report": "Point-in-time record: audit, verification results, session handoff, status update, log of what was done.",
        "generated": "Machine-generated output: graph report, evidence dump, snapshot, auto-built index.",
        "third_party": "License notices or docs vendored from another project."}},
    "still_guidance": {"type": "noul", "instructions": "Does `doc` contain requirements, rules, decisions with rationale, or facts that someone changing this codebase today still needs, beyond a record of what happened when it was written?"},
    "filler": {"type": "score", "instructions": "How much of `doc` is filler rather than information: restatement, progress narration, self-assessment, lists repeating code or other docs, hedging?", "criteria": [
        "Dense: nearly every sentence carries a requirement, number, decision, or fact.",
        "Mostly dense with some repetition or narration.",
        "About half filler around real content.",
        "Mostly filler: a few real facts buried in narration.",
        "Almost entirely filler or a transient status dump."]},
}
CLAIM_Q = {
    "verdict": {"type": "choice", "instructions": "How does the code in `code` relate to the documentation claim in `claim`? `code` holds the files and grep hits the claim cites, read today.", "criteria": {
        "supports": "The code does what the claim says; cited names, values and behaviour are present as described.",
        "contradicts": "The code shows the claim is now false: a cited file or symbol is missing or renamed, a value differs, or behaviour changed.",
        "says_nothing": "The code shown does not address the claim either way (intent, rationale, client asks, live data, external APIs, framework behaviour)."}},
    "open_item": {"type": "noul", "instructions": "Does `claim` describe an open problem, missing feature, TODO, or unfixed bug, rather than existing behaviour or finished work?"},
    "rationale": {"type": "noul", "instructions": "Does `claim` explain WHY (a decision and its reason, a trap and its cause, a rejected alternative) rather than only WHAT exists?"},
}
PLAN_MODEL = {"type": "choice", "instructions": "Which model should an orchestrator assign to `task`? Pick the cheapest that will do it correctly; errors cost in proportion to `task.risk_notes`.", "criteria": {
    "haiku": "Mechanical, fully specified, little judgement, and an automated guard catches mistakes: deleting listed files, running a checker. NOT for edits to citations, links inside source text, or tests.",
    "sonnet": "Reading several long sources in full and rewriting their durable content into one owner doc, keeping every number, rule, negation and example.",
    "opus": "High-stakes judgement: money math, security, tenancy/permissions, resolving contradictions between sources, or an adversarial review that must catch what a writer missed."}}


def cfg(repo):
    return json.loads((Path(repo) / ".qa/docs.json").read_text())


def out_dir(repo):
    d = Path.home() / ".claude/qa-runs" / Path(repo).resolve().name / "docs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def md_files(repo, c):
    files = subprocess.run(["git", "-C", repo, "ls-files", "*.md"], capture_output=True, text=True, check=True).stdout.split()
    return [f for f in files if not any(fnmatch.fnmatch(f, g) for g in c.get("exclude", []))]


def pmap(fn, items, workers=8):
    with cf.ThreadPoolExecutor(workers) as ex:
        return list(ex.map(fn, items))


def safe_ask(state, qs):
    try:
        return ask(api_key(), state, qs)["answers"]
    except Exception as e:  # recorded, counted, never silently dropped
        return {"error": str(e)[:200]}


def docs(repo, c):
    def one(p):
        t = (Path(repo) / p).read_text(errors="replace")
        return p, safe_ask({"path": p, "outline": [l for l in t.splitlines() if l.startswith("#")][:120], "doc": t[:BODY_CHARS]}, DOC_Q)
    return dict(pmap(one, md_files(repo, c)))


def evidence(repo, c, claim):
    ev, budget = {}, 60_000
    for ref in dict.fromkeys(REF.findall(claim)):
        if budget <= 0:
            break
        sym = ref.strip("`")
        fp = Path(repo) / sym.rstrip(".,:;)")
        if fp.is_file():
            txt = fp.read_text(errors="replace")[:20_000]
        elif ref.startswith("`"):
            txt = subprocess.run(["git", "-C", repo, "grep", "-n", "-w", "-F", "-C", "6", "--max-count", "2", sym, "--", *c.get("code_dirs", ["."])],
                                 capture_output=True, text=True).stdout[:12_000] or "(no occurrence in code)"
        else:
            txt = "(file does not exist)"
        ev[ref] = txt
        budget -= len(txt)
    return ev


def claims(repo, c):
    D = json.loads((out_dir(repo) / "docs.json").read_text())
    work = []
    for p, a in D.items():
        if "error" in a or a["kind"]["choice"] in HARD_KEEP:
            continue
        text = re.sub(r"```.*?```", "", (Path(repo) / p).read_text(errors="replace"), flags=re.S)
        for i, para in enumerate(re.split(r"\n\s*\n|\n(?=\s*[-*|] )|\n(?=\d+\. )", text)):
            if len(para.split()) >= 8 and REF.search(para):
                work.append((p, i, para.strip()[:6000]))
    return pmap(lambda w: {"path": w[0], "i": w[1], "claim": w[2],
                           "a": safe_ask({"doc_path": w[0], "claim": w[2], "code": evidence(repo, c, w[2])}, CLAIM_Q)}, work, 12)


def decide(repo, c):
    D = json.loads((out_dir(repo) / "docs.json").read_text())
    C = json.loads((out_dir(repo) / "claims.json").read_text())
    st = collections.defaultdict(collections.Counter)
    for r in C:
        if "error" in r["a"]:
            continue
        A, s = r["a"], st[r["path"]]
        s[A["verdict"]["choice"]] += 1
        s["open_items"] += A["open_item"]["noul"] >= 0.7
        s["rationale"] += A["rationale"]["noul"] >= 0.7
    Q = {"disposition": {"type": "choice", "instructions": "What should a doc cleanup (far fewer files, zero lost knowledge) do with the document in `doc`?", "criteria": {
            "keep_in_place": "Current owner doc, README beside its code, agent prompt the tooling loads, or a doc many files link to.",
            "merge_into_owner": "Fold its still-true rules, decisions, numbers, rationale and open items into one owner, then delete it.",
            "delete_after_lift": "Point-in-time report, handoff, finished plan or evidence dump: lift the few open items or decisions, then delete.",
            "delete_duplicate": "Nothing unique: fully present in another doc or entirely stale."}},
         "destination": {"type": "choice", "instructions": "If content from `doc` must move, which owner in `owners` should receive most of it?",
                         "criteria": {**c["owners"], "none": "Nothing needs to move."}}}

    def one(p):
        a = D[p]
        if "error" in a:
            return p, {"disposition": "keep_in_place", "why": "Jev error: kept"}
        if a["kind"]["choice"] in HARD_KEEP:
            return p, {"disposition": "keep_in_place", "why": f"hard keep: {a['kind']['choice']}"}
        body = (Path(repo) / p).read_text(errors="replace")
        doc = {"path": p, "bytes": len(body), "kind": a["kind"]["choice"], "filler_0_4": round(a["filler"]["score"], 1),
               "still_guidance": round(a["still_guidance"], 2), "claims": dict(st[p]), "opening": body[:3000]}
        r = safe_ask({"doc": doc, "owners": c["owners"]}, Q)
        if "error" in r:
            return p, {"disposition": "keep_in_place", "why": "Jev error: kept"}
        return p, {"disposition": r["disposition"]["choice"], "confidence": r["disposition"]["confidence"],
                   "destination": r["destination"]["choice"], "claims": dict(st[p])}
    return dict(pmap(one, list(D)))


def plan(repo, c):
    X = json.loads((out_dir(repo) / "decide.json").read_text())
    by_dest = collections.defaultdict(list)
    deletes = [p for p, r in X.items() if r["disposition"] != "keep_in_place"]
    for p, r in X.items():
        if r["disposition"] in ("merge_into_owner", "delete_after_lift") and r.get("destination", "none") != "none":
            by_dest[r["destination"]].append(p)
    tasks = [{"id": f"write:{d}", "sources": s, "risk_notes": c.get("risk", {}).get(d, "general guidance"),
              "description": f"Read {len(s)} docs in full; fold still-true rules, decisions+rationale, numbers and open items into {d}. Write ONLY to your own output path."}
             for d, s in by_dest.items()]
    tasks += [
        {"id": "delete", "description": f"git rm {len(deletes)} docs after their owner tasks land; originals stay in git history.", "risk_notes": "guarded by preserve.py check"},
        {"id": "links", "description": "Fix incoming links to moved/deleted docs; never rewrite source citations or tests.", "risk_notes": "a Haiku link pass once rewrote citations to point at themselves"},
        {"id": "stale-kept", "description": "In kept docs, verify each claim Jev marked contradicts against code; fix or label only the confirmed ones.", "risk_notes": "Jev contradicts was right 4 of 33 times on eVillage: triage signal only"},
        {"id": "dropped-review", "description": "Run `docs.py dropped`, then have agents classify every queued claim LOST / FIXED / NOT_DURABLE and restore LOST.", "risk_notes": "first writing pass lost ~10% of dropped claims on eVillage (105 of 1,110)"},
        {"id": "review", "description": "Independent adversarial review: every frozen source vs its owner doc, body for body.", "risk_notes": "must catch what writers missed"},
    ]
    Q = {"model": PLAN_MODEL,
         "needed": {"type": "noul", "instructions": "Is `task` needed to reach `goal`: would skipping it lose knowledge, break links, or leave the cleanup unverified?"},
         "effort": {"type": "score", "instructions": "How much work is `task`?", "criteria": ["Minutes", "Under an hour", "Several hours", "A day or more"]}}

    def one(t):
        a = safe_ask({"goal": c["goal"], "task": t}, Q)
        if "error" not in a:
            m = a["model"]
            t |= {"model": m["choice"] if m["confidence"] >= 0.5 else {"haiku": "sonnet", "sonnet": "opus"}.get(m["choice"], "opus"),
                  "model_conf": round(m["confidence"], 2), "needed": round(a["needed"], 2), "effort": round(a["effort"]["score"], 1)}
        return t
    return pmap(one, tasks)


def dropped(repo, c):
    """Claims from deleted docs whose distinctive tokens are mostly absent from the destination owner."""
    X = json.loads((out_dir(repo) / "decide.json").read_text())
    C = json.loads((out_dir(repo) / "claims.json").read_text())
    owners = {o: (Path(repo) / o).read_text(errors="replace").lower() if (Path(repo) / o).exists() else "" for o in c["owners"]}
    queue = []
    for r in C:
        d = X.get(r["path"], {})
        if d.get("disposition") == "keep_in_place" or "error" in r["a"]:
            continue
        durable = r["a"]["open_item"]["noul"] >= 0.5 or r["a"]["rationale"]["noul"] >= 0.5 or r["a"]["verdict"]["choice"] != "contradicts"
        toks = {t for t in re.findall(r"[a-z0-9_]{5,}", r["claim"].lower())}
        body = owners.get(d.get("destination"), "") or " ".join(owners.values())
        hit = sum(t in body for t in toks) / max(1, len(toks))
        if durable and hit < 0.6:  # ponytail: token overlap, not semantics; agents make the final LOST call
            queue.append({"path": r["path"], "destination": d.get("destination"), "overlap": round(hit, 2), "claim": r["claim"][:1500]})
    return sorted(queue, key=lambda q: q["overlap"])


def main():
    repo, cmd = sys.argv[1], sys.argv[2]
    c = cfg(repo)
    res = {"docs": docs, "claims": claims, "decide": decide, "plan": plan, "dropped": dropped}[cmd](repo, c)
    (out_dir(repo) / f"{cmd}.json").write_text(json.dumps(res, indent=1))
    rows = res.values() if isinstance(res, dict) else res
    errs = sum("error" in (r.get("a", r) if isinstance(r, dict) else {}) for r in rows)
    print(f"{cmd}: {len(res)} rows, errors {errs} → {out_dir(repo) / (cmd + '.json')}")
    if cmd == "decide":
        print(dict(collections.Counter(r["disposition"] for r in res.values())))
    if cmd == "plan":
        for t in res:
            print(f"  {t['id']:<40} model={t.get('model')}({t.get('model_conf')}) needed={t.get('needed')} effort={t.get('effort')}")
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
