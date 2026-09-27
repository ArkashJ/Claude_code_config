#!/usr/bin/env python3
"""SWEEP: code selects every site of a pattern, Jev judges each site, code ranks. Any repo(s).

    python3 ~/.claude/skills/qa/sweep.py calibrate FAMILY --repo R          # gate: must PASS first
    python3 ~/.claude/skills/qa/sweep.py run FAMILY --repo R [--repo R2 ...|--all-repos]

A family lives in <repo>/.qa/families.json (or --families FILE), so repo-specific wording stays in
that repo:
  {"swallowed_errors": {
     "extract": {"kind": "py_except"}                                   # or:
              | {"kind": "grep", "pattern": "cache_set\\(", "include": ["*.py"], "scope": "function",
                 "before": 30, "after": 15, "file_context": "APIRouter\\("}
              | {"kind": "file", "include": ["*.tsx"], "pattern": "useQuery"},
     "questions": {"hides_failure": {"type": "noul", "instructions": "...`handler_body`...", "criteria": {...}}},
     "score": "hides_failure",                      # expression over noul ids; high = finding
     "calibration": [{"file": "a.py", "line": 40, "expect": true, "rev": "abc123^"},   # the pre-fix bug
                     {"file": "a.py", "line": 40, "expect": false}]}}                   # the fixed code

Ported from the repo-A sweep that judged 2,670 sites with 0 errors and fed ~15 fix commits
(2026-09-20/21). What made it work, kept here as rules:
- One narrow question per site, never "is this code good?". Code finds the sites.
- Calibrate before sweeping: labelled positives must score >= 0.70 and negatives <= 0.30. The first
  cache-key wording scored 0.50/0.08 and would have produced a useless 96-site run.
- A labelled bug can be the PRE-fix version of a bug this session fixed (`rev`), so every fix becomes
  its own known-answer test. Then sweep every repo for its siblings.
- Precision is low (3/26 and 14/57 in that run): a flagged site is a lead for an agent to verify,
  and each false-positive class becomes a new question or a `not_for` next run.
- Questions whose answers barely vary (sd < 0.05) are flagged FLAT: rewrite or drop them.
Exit: 0 ok · 1 request errors or calibration FAIL · 2 cannot measure (no family, no sites, no labels).
"""
import argparse, ast, fnmatch, hashlib, json, os, re, statistics, subprocess, sys
import concurrent.futures as cf
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from hunt import MODEL, api_key, ask  # noqa: E402  shared client: retries, UA, pinned model

MAX_STATE = 12_000
SKIP = re.compile(r"(^|/)(node_modules|\.venv|venv|dist|build|__pycache__|\.worktrees|worktrees|tests?|__tests__|e2e|"
                  r"mocks?|migrations|alembic|generated|vendor)/|\.(test|spec)\.|\.d\.ts$|\.min\.")
# Anything that looks like a credential is replaced before state leaves the machine. Quoted keys and
# a `Bearer ` prefix are both covered: the first version matched neither (repo A, P1 inline review).
REDACT = re.compile(r"(?i)(['\"]?(?:api[_-]?key|secret|token|password|passwd|authorization|bearer)['\"]?"
                    r"\s*[:=]\s*['\"]?(?:bearer\s+)?)([^'\"\s,}]{8,})")
PASS_POS, PASS_NEG = 0.70, 0.30


def clip(s):
    s = REDACT.sub(r"\1<redacted>", s)
    return (s[:MAX_STATE] + "\n…[truncated]", True) if len(s) > MAX_STATE else (s, False)


def git(repo, *a):
    return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True).stdout


def all_repos():
    roots = [os.path.expanduser(r) for r in os.environ.get("HARVEST_REPO_ROOTS", "~/Developer:~/Benmore").split(":")]
    out = subprocess.run(["find", *[r for r in roots if os.path.isdir(r)], "-maxdepth", "4", "(", "-name", "node_modules",
                          "-o", "-name", "worktrees", "-o", "-name", "tmp", ")", "-prune", "-o", "-name", ".git", "-type", "d",
                          "-print"], capture_output=True, text=True).stdout
    return sorted({Path(g).parent for g in out.split()})


def files(repo, ex):
    inc = ex.get("include", ["*"])
    skip = re.compile(ex["exclude"]) if "exclude" in ex else SKIP
    return [f for f in git(repo, "ls-files").splitlines()
            if any(fnmatch.fnmatch(Path(f).name, g) for g in inc) and not skip.search("/" + f)]


def func_span(tree, line):
    """Innermost function covering `line`, decorators included (a decorator sits above `def`)."""
    best = None
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start = min([n.lineno] + [d.lineno for d in n.decorator_list])
            if start <= line <= (n.end_lineno or n.lineno) and (best is None or start > best[0]):
                best = (start, n.end_lineno or n.lineno, n.name)
    return best


def sites(rel, text, ex):
    """Sites of one file. Pure function of (path, text) so calibration can run it on a git revision."""
    lines, kind = text.splitlines(), ex["kind"]
    tree = None
    if rel.endswith(".py"):
        try:
            tree = ast.parse(text)
        except SyntaxError:
            pass
    ctx = "\n".join(l for l in lines if re.search(ex["file_context"], l))[:1500] if ex.get("file_context") else None
    if ex.get("absent") and re.search(ex["absent"], text):  # case-sensitive: `export function` is not an export feature
        return  # the feature is already there: an opportunity family must not flag it
    if kind == "file":
        if not ex.get("pattern") or re.search(ex["pattern"], text):
            body, tr = clip(text)
            yield {"line": 1, "function": Path(rel).stem, "truncated": tr, "state": {"file": rel, "source": body}}
    elif kind == "py_except" and tree:
        types = set(ex.get("types", ["Exception", "BaseException"]))
        for n in ast.walk(tree):
            for h in getattr(n, "handlers", []) if isinstance(n, ast.Try) else []:
                if isinstance(h.type, ast.Name) and h.type.id in types or h.type is None:
                    fn, end = func_span(tree, h.lineno), h.end_lineno or h.lineno
                    tb, tr = clip("\n".join(lines[n.lineno - 1:h.lineno - 1]))
                    doc = next((ast.get_docstring(f) or "" for f in ast.walk(tree) if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef))
                                and fn and f.name == fn[2] and f.lineno >= fn[0]), "")
                    yield {"line": h.lineno, "function": fn and fn[2], "truncated": tr,
                           "state": {"file": rel, "function": fn and fn[2], "docstring": doc[:400], "try_body": tb,
                                     "handler_body": clip("\n".join(lines[h.lineno - 1:end]))[0],
                                     "code_after_handler": "\n".join(lines[end:end + 8])}}
    elif kind == "grep":
        pat, seen = re.compile(ex["pattern"]), set()
        for i, l in enumerate(lines, 1):
            if not pat.search(l):
                continue
            fn = func_span(tree, i) if tree and ex.get("scope") == "function" else None
            lo, hi = (fn[0], fn[1]) if fn else (max(1, i - ex.get("before", 30)), min(len(lines), i + ex.get("after", 15)))
            if (lo, hi) in seen:  # one site per function, however many matching lines it has
                continue
            seen.add((lo, hi))
            snip, tr = clip("\n".join(f"{n}: {lines[n - 1]}" for n in range(lo, hi + 1)))
            st = {"file": rel, "function": fn and fn[2], "snippet": snip}
            if ctx:
                st["file_context"] = ctx
            yield {"line": i, "function": fn and fn[2], "truncated": tr, "state": st}
    else:
        raise SystemExit(f"unknown extract kind {kind!r} (grep | py_except | file)")


def add_facts(repo, s):
    """Code-computed evidence Jev cannot see from one snippet (jev.md: facts go in state, never in a question).
    A handler that sets `_consumer_start_failed = True` is fail-closed only if something else reads that
    flag; the reader was in another file, so Jev flagged a fixed site at 0.81 (repo A, 2026-09-27)."""
    body = s["state"].get("handler_body") or ""
    facts = []
    for name in sorted(set(re.findall(r"\b(\w*(?:fail|error|healthy|ready|status|ok)\w*)\s*=(?!=)", body, re.I))):
        readers = [f for f in git(repo, "grep", "-l", "-w", "-F", name, "--", "*.py").splitlines() if f != s["file"]]
        if readers:
            facts.append(f"`{name}` set in this handler is read by {', '.join(readers[:3])}")
    if facts:
        s["state"]["facts"] = facts
    return s


TSX_SKIP = r"(^|/)(node_modules|dist|build|e2e|__tests__|mocks?|stories)/|\.(test|spec|stories)\.|\.d\.ts$"
# Generic families: repo-agnostic wording, calibrated only on inline fixtures, so a ledger from one says
# "fixture-calibrated" until the repo adds real labels in its own .qa/families.json (which overrides these).
# Chosen from a Jev pass over 733 human turns in 188 sessions: the areas the user most often had to point
# the assistant at (nice-to-have additions, permissions, notifications). Hooks/effects/mutations are hunt.py's.
DEFAULTS = {
    "export_opportunity": {
        "extract": {"kind": "file", "include": ["*.tsx"], "exclude": TSX_SKIP, "pattern": r"<(Table|DataTable|DataGrid)\b|columns\s*[:=]\s*\[",
                    "absent": r"[Cc]sv|CSV|[Ee]xport(To|As|Csv|CSV|Data|Button|Menu|Rows)|<Export|[Dd]ownload|xlsx"},
        "questions": {"export_useful": {"type": "noul",
            "instructions": "`source` is a page or component that lists records in a table and has no export. Would its users plausibly need these records outside the app, for reports, audits, reconciliation, or sharing with people who have no account?",
            "criteria": {"true": {"what": "business records people report on or hand to others", "examples": ["invoices", "orders", "employees", "audit events", "compliance findings"]},
                         "false": {"what": "records nobody takes outside the app", "not_for": "UI configuration lists, navigation menus, a table of the user's own settings, or a picker inside a form"}}}},
        "score": "export_useful",
        "calibration": [
            {"file": "OrdersPage.tsx", "expect": True, "text": "export function OrdersPage() {\n  const { data } = useOrders();\n  return <DataTable columns={[{key: 'id'}, {key: 'customer'}, {key: 'total'}, {key: 'status'}]} rows={data} />;\n}"},
            {"file": "AuditLog.tsx", "expect": True, "text": "export function AuditLog() {\n  const { data } = useAuditEvents();\n  return <Table columns={[{key: 'actor'}, {key: 'action'}, {key: 'at'}]} rows={data} />;\n}"},
            {"file": "ThemePicker.tsx", "expect": False, "text": "export function ThemePicker({ onPick }) {\n  return <Table columns={[{key: 'name'}, {key: 'preview'}]} rows={THEMES} onRowClick={onPick} />;\n}"},
            {"file": "SidebarLinks.tsx", "expect": False, "text": "export function SidebarLinks() {\n  const columns = [{key: 'label'}];\n  return <Table columns={columns} rows={NAV_ITEMS} dense />;\n}"}]},
    "bulk_opportunity": {
        "extract": {"kind": "file", "include": ["*.tsx"], "exclude": TSX_SKIP,
                    "pattern": r"onClick=\{[^}]*\b(delete|remove|archive|approve|assign|resend|cancel)\w*\(\s*\w+(\.id)?",
                    "absent": r"selectAll|selectedRows|selectedIds|rowSelection|bulk"},
        "questions": {"bulk_useful": {"type": "noul",
            "instructions": "`source` offers an action on one row at a time and has no multi-select. Is this the kind of action a person repeats across many rows in one sitting, working through a queue of records (approving, assigning, archiving, resending)?",
            "criteria": {"true": {"what": "a queue-style action people apply row after row", "examples": ["approve each timesheet in a list of pending timesheets", "assign each ticket in an inbox", "archive old orders"]},
                         "false": {"what": "the action is rare, one-off, or must be judged record by record", "not_for": "deleting the user's own account, a single settings row, or an action that needs per-record review"}}}},
        "score": "bulk_useful",
        "calibration": [
            {"file": "Timesheets.tsx", "expect": True, "text": "export function Timesheets({ rows }) {\n  return rows.map(r => <Row key={r.id}>{r.employee} {r.hours}<Button onClick={() => approveTimesheet(r.id)}>Approve</Button></Row>);\n}"},
            {"file": "Tickets.tsx", "expect": True, "text": "export function Tickets({ rows }) {\n  return rows.map(t => <Row key={t.id}>{t.subject}<Button onClick={() => assignTicket(t.id)}>Assign to me</Button></Row>);\n}"},
            {"file": "ApiKeys.tsx", "expect": False, "text": "export function ApiKeys({ keys }) {\n  // one key per integration; rotating is rare and deliberate\n  return keys.map(k => <Row key={k.id}>{k.name}<Button onClick={() => deleteKey(k.id)}>Revoke</Button></Row>);\n}"},
            {"file": "Account.tsx", "expect": False, "text": "export function Account({ me }) {\n  return <Row>{me.email}<Button onClick={() => deleteAccount(me.id)}>Delete my account</Button></Row>;\n}"}]},
    "destructive_ungated": {
        "extract": {"kind": "grep", "include": ["*.tsx"], "exclude": TSX_SKIP, "scope": "window", "before": 40, "after": 10,
                    # DOM/storage cleanup is not a destructive action (repo A sweep 2026-09-27: removeItem and
                    # removeEventListener were the top two flags, both false).
                    "pattern": r"\b(?!removeEventListener|removeItem|removeChild|removeAttribute|removeProperty|removeQueries)"
                               r"(delete|remove|revoke|archive|deactivate|purge)\w*\s*\(|useDelete\w*\("},
        "questions": {"persists": {"type": "noul",
            "instructions": "Does the destructive call in `snippet` change data stored on a server (calls an API, a mutation hook, or a service), rather than only local UI state such as a form's list or a component's useState?",
            "criteria": {"true": {"examples": ["deleteUser(u.id)", "useDeleteOrder().mutate(id)", "api.revokeKey(k.id)"]},
                         "false": {"examples": ["removeTag(i) on a setTags list", "remove(index) from useFieldArray", "setItems(items.filter(...))"]}}},
                      "gated": {"type": "noul",
            "instructions": "Look at the destructive action in `snippet` (delete, remove, revoke, archive, deactivate). Is showing or running it guarded by a permission, role, or ownership check visible in the snippet?",
            "criteria": {"true": {"what": "a check such as can('orders.delete'), hasPermission, a role test, or an ownership test guards the control or the call",
                                  "examples": ["{can('user.delete') && <Button onClick={() => deleteUser(u.id)}>", "if (!hasPermission(p, 'archive')) return null"]},
                         "false": {"what": "any signed-in user sees and can trigger it", "not_for": "removing an item from the user's own unsaved local list, form field arrays, or UI-only state"}}}},
        "score": "persists * (1 - gated)",
        "calibration": [
            {"file": "Users.tsx", "line": 4, "expect": True, "text": "import { deleteUser } from '../api/users';\nexport function Users({ users }) {\n  return users.map(u => <Row key={u.id}>{u.name}\n    <Button onClick={() => deleteUser(u.id)}>Delete</Button></Row>);\n}"},
            {"file": "Users2.tsx", "line": 5, "expect": False, "text": "import { deleteUser } from '../api/users';\nexport function Users({ users }) {\n  const can = usePermissions();\n  return users.map(u => <Row key={u.id}>{u.name}\n    {can('user.delete') && <Button onClick={() => deleteUser(u.id)}>Delete</Button>}</Row>);\n}"},
            {"file": "TagInput.tsx", "line": 3, "expect": False, "text": "export function TagInput({ tags, setTags }) {\n  return tags.map((t, i) => <Chip key={t}>{t}\n    <X onClick={() => removeTag(i)} /></Chip>);\n}"}]},
    "notify_recipients": {
        "extract": {"kind": "grep", "include": ["*.py", "*.ts"], "scope": "function",
                    # calls only: not the sender's own `def send_email(` or a docstring mention (both flagged 2026-09-27)
                    "pattern": r"(?<!def )(?<![`\w])(send_(email|notification|sms)|notify\w*|sendNotification|sendEmail|publish_notification)\s*\("},
        "questions": {"recipients_scoped": {"type": "noul",
            "instructions": "Look at who receives the notification sent in `snippet`. Is the recipient list restricted to the right tenant/organization AND to users whose role or permission entitles them to this content?",
            "criteria": {"true": "recipients are filtered by tenant and by role/permission, or the recipient is exactly the acting user or a single explicitly addressed person",
                         "false": {"what": "recipients come from an unscoped query or list, or role/permission is not checked", "examples": ["User.query.all()", "every member of any org", "all admins across tenants"]}}}},
        "score": "1 - recipients_scoped",
        "calibration": [
            {"file": "n1.py", "line": 3, "expect": True, "text": "def alert_admins(msg):\n    admins = db.query(User).filter(User.role == 'admin').all()\n    for a in admins: send_email(a.email, msg)\n"},
            {"file": "n2.py", "line": 4, "expect": False, "text": "def alert_admins(org_id, msg):\n    admins = db.query(User).filter(User.org_id == org_id, User.permissions.contains('alerts.read')).all()\n    for a in admins:\n        send_email(a.email, msg)\n"},
            {"file": "n3.py", "line": 2, "expect": False, "text": "def confirm_signup(user):\n    send_email(user.email, 'Welcome')\n"}]},
}


def load_family(args):
    path = Path(args.families) if args.families else Path(args.repo[0] if args.repo else ".") / ".qa/families.json"
    fams = {**DEFAULTS, **(json.loads(path.read_text()) if path.exists() else {})}
    if args.family not in fams:
        sys.exit(print(f"no family {args.family!r} in {path} (have: {', '.join(fams) or 'none'})", file=sys.stderr) or 2)
    return fams[args.family], path


def score(fam, answers):
    names = {k: v["noul"] for k, v in answers.items() if "noul" in v}
    # Families are repo config the user runs, not model output; builtins are still withheld.
    return float(eval(fam["score"], {"__builtins__": {}, "max": max, "min": min}, names))


def qhash(fam):
    return hashlib.sha1(json.dumps([fam["questions"], fam["score"], MODEL], sort_keys=True).encode()).hexdigest()[:12]


def judge_all(key, fam, todo):
    def one(s):
        try:
            r = ask(key, s["state"], fam["questions"])
            return s | {"answers": {k: {kk: vv for kk, vv in v.items() if kk != "type"} for k, v in r["answers"].items()},
                        "model": r.get("model"), "tokens": r.get("usage", {}).get("input_tokens", 0)}
        except Exception as e:
            return s | {"error": str(e)[:200]}
    with cf.ThreadPoolExecutor(6) as ex:  # jev.md rule 18
        return list(ex.map(one, todo))


def out_dir(fam_path, family):
    d = Path.home() / ".claude/qa-runs" / (fam_path.resolve().parent.parent.name if fam_path.exists() else "_defaults") / "sweep"
    d.mkdir(parents=True, exist_ok=True)
    return d


def calibrate(args):
    fam, fpath = load_family(args)
    repo = Path(args.repo[0] if args.repo else ".")
    labels = fam.get("calibration", [])
    npos, nneg = sum(l["expect"] for l in labels), sum(not l["expect"] for l in labels)
    if npos < 1 or nneg < 1:
        sys.exit(print(f"calibration needs >=1 true and >=1 false label (have {npos}/{nneg})", file=sys.stderr) or 2)
    todo = []
    for lb in labels:
        text = lb["text"] if "text" in lb else git(repo, "show", f"{lb['rev']}:{lb['file']}") if lb.get("rev") \
            else (repo / lb["file"]).read_text(errors="replace")
        cand = list(sites(lb["file"], text, fam["extract"]))
        if not cand:
            sys.exit(print(f"label {lb} matched no site: the extractor cannot see it, fix the extractor first", file=sys.stderr) or 2)
        site = min(cand, key=lambda s: abs(s["line"] - lb.get("line", 1))) | {"label": lb, "file": lb["file"]}
        todo.append(add_facts(repo, site))
    res = judge_all(api_key(), fam, todo)
    errs = [r for r in res if "error" in r]
    if errs:
        sys.exit(print(f"{len(errs)} calibration requests failed: {errs[0]['error']}", file=sys.stderr) or 1)
    for r in res:
        r["score"] = score(fam, r["answers"])
        print(f"  expect={str(r['label']['expect']):<5} score={r['score']:.2f}  {r['label']['file']}:{r['line']}"
              f"{' @' + r['label']['rev'] if r['label'].get('rev') else ''}")
    pos = statistics.mean(r["score"] for r in res if r["label"]["expect"])
    neg = statistics.mean(r["score"] for r in res if not r["label"]["expect"])
    ok = pos >= PASS_POS and neg <= PASS_NEG
    # Means hide a per-label miss (repo A: held-out bug at 0.64 under a PASSing 0.79 mean). Name each one.
    for r in res:
        if r["label"]["expect"] and r["score"] < args.threshold or not r["label"]["expect"] and r["score"] > PASS_NEG:
            print(f"  MISS at --threshold {args.threshold}: expect={r['label']['expect']} score={r['score']:.2f} "
                  f"{r['label']['file']}:{r['line']}  {r['label'].get('why', '')}")
    fixture_only = all("text" in lb for lb in labels)
    rec = {"family": args.family, "qhash": qhash(fam), "model": MODEL, "fixture_only": fixture_only, "pos_mean": round(pos, 2), "neg_mean": round(neg, 2),
           "labels": len(res), "result": "PASS" if ok else "FAIL"}
    (out_dir(fpath, args.family) / f"{args.family}.calibration.json").write_text(json.dumps(rec, indent=1))
    print(f"{args.family}: positives {pos:.2f} (need >= {PASS_POS}), negatives {neg:.2f} (need <= {PASS_NEG}) -> {rec['result']}")
    if not ok:
        print("Reword the question: name the narrowest deciding fact; put the reason a negative is fine into "
              "criteria.false.not_for (jev.md rules 2-4). Never loosen the gate.", file=sys.stderr)
    sys.exit(0 if ok else 1)


def run(args):
    fam, fpath = load_family(args)
    od = out_dir(fpath, args.family)
    cal_path = od / f"{args.family}.calibration.json"
    cal = json.loads(cal_path.read_text()) if cal_path.exists() else {}
    calibrated = cal.get("result") == "PASS" and cal.get("qhash") == qhash(fam)
    if not calibrated and not args.uncalibrated:
        sys.exit(print(f"{args.family}: not calibrated for these questions+model (run `calibrate` first, or pass "
                       f"--uncalibrated and the ledger will say so)", file=sys.stderr) or 2)
    repos = all_repos() if args.all_repos else [Path(r).resolve() for r in args.repo]
    found = []
    for rp in repos:
        changed = None
        if args.since:  # wrap/harvest: judge only what this session touched
            changed = set(git(rp, "log", f"--since={args.since}", "--name-only", "--format=").split()) | set(git(rp, "diff", "--name-only", "HEAD").split())
        for f in files(rp, fam["extract"]):
            if changed is not None and f not in changed:
                continue
            try:
                text = (rp / f).read_text(errors="replace")
            except OSError:
                continue
            for s in sites(f, text, fam["extract"]):
                found.append(add_facts(rp, s | {"repo": rp.name, "file": f}))
    if not found:
        sys.exit(print(f"{args.family}: 0 sites in {len(repos)} repo(s): unable to measure, check the extractor", file=sys.stderr) or 2)
    # Cache on hash(state, questions, model) (jev.md rule 15): an edited question never serves a stale answer.
    cache_path = od / f"{args.family}.answers.jsonl"
    cache = {}
    if cache_path.exists():
        for l in cache_path.read_text().splitlines():
            r = json.loads(l)
            cache[r["h"]] = r
    for s in found:
        s["h"] = hashlib.sha1(json.dumps([s["state"], fam["questions"], MODEL], sort_keys=True).encode()).hexdigest()
    todo = [s for s in found if s["h"] not in cache]
    todo = todo[: args.limit] if args.limit else todo
    print(f"{args.family}: {len(found)} sites in {len(repos)} repo(s), {len(found) - len(todo)} cached, judging {len(todo)}"
          f"{'' if calibrated else '  [UNCALIBRATED]'}", file=sys.stderr)
    res = judge_all(api_key(), fam, todo)
    with cache_path.open("a") as fh:
        for r in res:
            if "answers" in r:
                fh.write(json.dumps({k: r[k] for k in ("h", "answers", "model")}) + "\n")
                cache[r["h"]] = r
    errors = sum("error" in r for r in res)
    rows = [s | {"answers": cache[s["h"]]["answers"]} for s in found if s["h"] in cache]
    for r in rows:
        r["score"] = round(score(fam, r["answers"]), 3)
    rows.sort(key=lambda r: -r["score"])
    flagged = [r for r in rows if r["score"] >= args.threshold]
    flat = [q for q, v in fam["questions"].items() if v.get("type", "noul") == "noul" and len(rows) > 5
            and statistics.pstdev(r["answers"][q]["noul"] for r in rows if q in r["answers"]) < 0.05]
    L = [f"# Jev sweep ledger: {args.family}. Code selected sites, Jev judged, code ranked. Probabilities, not verdicts.",
         f"model: {MODEL}  calibration: {('fixture-calibrated (add real labels in .qa/families.json)' if cal.get('fixture_only') else cal.get('result')) if calibrated else 'UNCALIBRATED'}"
         f"{' pos ' + str(cal['pos_mean']) + ' neg ' + str(cal['neg_mean']) if calibrated else ''}",
         f"sites: {len(found)}  judged: {len(rows)}  errors: {errors}  truncated: {sum(r['truncated'] for r in rows)}  "
         f"flagged >= {args.threshold}: {len(flagged)}  repos: {', '.join(sorted({r['repo'] for r in rows}))}",
         *(f"FLAT: {q} barely varies (sd < 0.05): rewrite or drop it" for q in flat),
         "", "Verify each flagged site (read it, prove or dismiss); record false-positive classes as new "
         "questions or criteria.false.not_for for the next run.", ""]
    for r in flagged[: args.top]:
        ans = {k: v.get("noul", v.get("choice")) for k, v in r["answers"].items()}
        L.append(f"- {r['score']:.2f}  {r['repo']}/{r['file']}:{r['line']}  {r['function'] or ''}  {json.dumps(ans)}")
    if len(flagged) > args.top:
        L.append(f"  … {len(flagged) - args.top} more flagged in {od / (args.family + '.ledger.md')}")
    (od / f"{args.family}.ledger.md").write_text("\n".join(L[:6] + [f"- {r['score']:.2f}  {r['repo']}/{r['file']}:{r['line']}"
                                                                   for r in flagged]) + "\n")
    print("\n".join(L))
    sys.exit(1 if errors else 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["calibrate", "run"])
    ap.add_argument("family")
    ap.add_argument("--repo", action="append", default=[], help="repeatable; the first also locates .qa/families.json")
    ap.add_argument("--all-repos", action="store_true", help="every git repo under $HARVEST_REPO_ROOTS (default ~/Developer:~/Benmore)")
    ap.add_argument("--families", help="families JSON (default <first --repo>/.qa/families.json)")
    ap.add_argument("--threshold", type=float, default=0.75)
    ap.add_argument("--top", type=int, default=25, help="flagged sites to print (all go to the ledger file)")
    ap.add_argument("--limit", type=int, default=0, help="judge at most N uncached sites (smoke run)")
    ap.add_argument("--since", help="only files changed since this date/time plus uncommitted (session-end runs)")
    ap.add_argument("--uncalibrated", action="store_true", help="run without a PASSing calibration; the ledger says so")
    a = ap.parse_args()
    calibrate(a) if a.cmd == "calibrate" else run(a)


if __name__ == "__main__":
    main()
