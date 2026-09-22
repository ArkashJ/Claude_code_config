#!/usr/bin/env python3
"""Jev bug hunt: enumerate React/TanStack surfaces in code, ask Jev narrow yes/no
questions about each one in parallel, and rank the suspicious ones for a deeper read.

Code finds the surfaces and computes exact facts; Jev only makes the semantic
judgment; Claude reads the top of the ranking and proves or dismisses each lead.

usage: hunt.py REPO [--src src] [--invariants FILE] [--out DIR] [--limit N] [--workers N]
"""
import argparse, concurrent.futures as cf, json, os, re, sys, time, urllib.error, urllib.request
from pathlib import Path

API = "https://api.typesafe.ai/v1/systemone"
MODEL = os.environ.get("TYPESAFE_DEFAULT_MODEL", "jev-1.13.0")  # pinned: thresholds are tuned per version
HOOKS = {
    "useEffect": "effect", "useLayoutEffect": "effect",
    "useQuery": "query", "useSuspenseQuery": "query", "useInfiniteQuery": "query",
    "useMutation": "mutation",
}
HOOK_RE = re.compile(r"\b(" + "|".join(HOOKS) + r")\s*(?:<[^()]*?>)?\s*\(")
DECL_RE = re.compile(r"^(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:function\s+(\w+)|const\s+(\w+)\s*[=:])", re.M)
SKIP = re.compile(r"(\.test\.|\.spec\.|/mocks?/|/generated/|routeTree\.gen|\.d\.ts$|/e2e/)")
CACHE_WRITE = re.compile(r"invalidateQueries|setQueryData|setQueriesData|refetchQueries|resetQueries|removeQueries|\.refetch\(")
MAX_SNIPPET, MAX_CONTEXT = 120, 160  # lines; Jev loses accuracy on large irrelevant state

# Generic questions. Each is literal and atomic (Jev reads questions at face value).
GENERIC = {
    "effect": {
        # url_sync_one_way = writes high AND reads-back low (composed in leads()). Replaced broad
        # derived_state / event_in_effect questions: 0 of 9 and 2 of 9 real on repo A.
        "writes_input_to_url": ("Does the effect in `snippet` copy a local input value into the URL search params (navigate or setSearchParams), usually after a debounce timer?",
                                {"true": "Typed text or a local filter value is pushed into the URL by this effect",
                                 "false": "The effect does not write to the URL, or writes a value that did not come from a local input"}),
        "url_read_back": ("Does `context` also update that local input state when the URL search param changes on its own (back/forward, a link, or a tab click), for example with an effect that sets the input from the search param?",
                          {"true": "There is a URL-to-input sync as well as input-to-URL",
                           "false": "The input is initialised from the URL once and never updated from it again"}),
        "missing_cleanup": "Does the effect in `snippet` start something that keeps running (an event listener, interval, timeout, subscription, observer, or socket) without returning a cleanup function that stops it?",
        "async_race": ("Does the effect in `snippet` set state after an await or a promise callback without an abort signal, cancelled flag, or ignore flag that stops a stale result from being applied?",
                       {"true": "An input that can change while the request is in flight decides what the stale result overwrites",
                        "false": "The request runs once behind a ref guard, its input cannot change during the component's life, its success path navigates away, or it sets no React state"}),
        # draft_clobber = both of these high (composed in leads()). Replaces a broad
        # "is server data copied into state" question that was ~90% noise on repo A.
        "overwrites_user_draft": ("Does the effect in `snippet` overwrite state that the user edits (a draft, form value, or in-progress selection) with values taken from query or API data?",
                                  {"true": "Server values are written into state the user can change before saving",
                                   "false": "It only picks a default when nothing is selected yet, stores a one-shot command or mutation result, builds an object URL for a file, or mirrors URL search params"}),
        # repo B 2026-09-22: 5 of 6 "real" draft_clobber verdicts were wrong: TanStack structural
        # sharing keeps an unchanged record's reference across refetches. The live hazard is a
        # dependency rebuilt during render, or a server field that really changes (repo A user-detail-dialog:49).
        "reruns_on_refetch": ("Would the effect in `snippet` run again while the user is editing, without a different record being opened?",
                              {"true": "A dependency is an object or array built during render (inline literal, spread, .map() or adapter call), or a server object whose fields change on refetch because of another action (a status toggle, timestamps, counts)",
                               "false": "Its dependency list contains only an id, a key, or an open/closed flag; or query data passed through unchanged (TanStack structural sharing keeps the same reference when a refetch returns the same values)"}),
    },
    "query": {
        "key_missing_input": ("Does the query function in `snippet` send a value that changes which records come back (such as an id, filter, page, sort, or search term) that does not appear in the queryKey of `snippet`?",
                              {"true": "A server-side filter or selector is sent in the request but missing from the queryKey",
                               "false": "Only the infinite-query pageParam, hard-coded literals, filters applied client-side after the fetch, or auth credentials that don't choose the record are missing; or the queryKey factory is passed the same params object that is sent as the request's query or body"}),
        "runs_without_param": ("Can the query in `snippet` send a request with a required id or path segment that is undefined or empty, because nothing (such as an `enabled` condition) prevents it?",
                               {"true": "A required id or path value can be undefined, producing a URL like /items/undefined or a request the server rejects",
                                "false": "The missing value is an optional filter whose absence means no filter, the parameter is typed as a required string (route param, a loaded object's id, or a caller-supplied default), or `enabled` requires it to be non-empty"}),
    },
    "mutation": {
        "writes_shown_data": ("Does the mutation in `snippet` create, update, or delete server data that the application displays in a list, detail view, or count?",
                              {"true": "It changes records or fields that a query elsewhere reads back and shows",
                               "false": "Login, logout, password reset, invitation acceptance, MFA, export, download, a read-only lookup, or only sending an email or notification"}),
        "optimistic_no_rollback": "Does the mutation in `snippet` change the query cache in onMutate without restoring the previous value in onError?",
    },
}


def api_key():
    key = os.environ.get("TYPESAFE_API_KEY") or os.environ.get("TYPESAFE_JEV_KEY")
    if not key:
        sys.exit("set TYPESAFE_API_KEY (or TYPESAFE_JEV_KEY)")
    return key


def match_paren(text, i):
    """Index just past the ')' matching text[i]=='('. Skips strings, templates, comments.
    ponytail: lexer ignores regex literals and ${} nesting inside templates; good enough to
    bound a hook call, swap for the TS compiler API if snippets come back truncated."""
    depth, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in "\"'`":
            q, i = c, i + 1
            while i < n and text[i] != q:
                i += 2 if text[i] == "\\" else 1
        elif text.startswith("//", i):
            i = text.find("\n", i)
            i = n if i < 0 else i
        elif text.startswith("/*", i):
            i = text.find("*/", i)
            i = n if i < 0 else i + 1
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return n


NAMED_BLOCK = re.compile(r"(?:const|let|function)\s+(\w+)\s*(?:=\s*(?:async\s*)?)?")


def body_end(text, j):
    """End of a declaration's value: bracket groups chained by `=>`, a type annotation, or a call,
    e.g. `(a) => { … }`, `useCallback(() => …, [])`, `function f() { … }`, `() => qc.invalidate(…)`."""
    n = len(text)
    while j < n:
        k = j
        while k < n and text[k] in " \t\n":
            k += 1
        if "\n" in text[j:k] and not (text.startswith("=>", k) or text.startswith(".", k)):
            break  # a new statement starts on the next line
        j = k
        if j < n and text[j] in "({":
            j = match_paren(text, j)
        elif text.startswith("=>", j):
            j += 2
            while j < n and text[j] in " \t\n":
                j += 1
            if j < n and text[j] not in "({":  # expression body: to end of line
                e = text.find("\n", j)
                return n if e < 0 else e
        elif j < n and (text[j].isalnum() or text[j] in "_.:<>"):  # callee name, type annotation
            j += 1
        else:
            break
    return j


def cache_helpers(text):
    """Names in this file whose own body touches the query cache: local helpers, useCallback
    wrappers, and custom hooks returning invalidators (followed one hop, same file only)."""
    names = set()
    for m in NAMED_BLOCK.finditer(text):
        if CACHE_WRITE.search(strip_comments(text[m.end():body_end(text, m.end())])):
            names.add(m.group(1))
    for m in re.finditer(r"const\s+(?:\{[^}]*\}|(\w+))\s*=\s*(\w+)\(", text):  # vars bound to those hooks
        if m.group(1) and m.group(2) in names:
            names.add(m.group(1))
    return names


def strip_comments(code):
    # repo C 2026-09-22: every one of 30+ trap-regex hits was a comment documenting the trap.
    return re.sub(r"/\*.*?\*/|(?<![:'\"])//[^\n]*", "", code, flags=re.S)


def updates_cache(snippet, helpers):
    snippet = strip_comments(snippet)
    if CACHE_WRITE.search(snippet):
        return True
    return any(re.search(rf"\b{re.escape(h)}\b", snippet) for h in helpers)


def call_site_updates(root, src, hook_name, files_text):
    """An exported mutation hook whose callers invalidate after mutate/mutateAsync."""
    for text in files_text.values():
        for m in re.finditer(rf"\b{re.escape(hook_name)}\(", text):
            window = text[m.start(): m.start() + 4000]  # ponytail: fixed window, not a real scope
            if re.search(r"mutate(Async)?\(", window) and CACHE_WRITE.search(window):
                return True
    return False


WRAPPER_DEF = re.compile(r"^(?:export\s+)?(?:function\s+(use[A-Z]\w*)|const\s+(use[A-Z]\w*)\s*=)", re.M)


def passes_through(args, p):
    """The caller supplies the key/fn: `queryKey: key,` (whole value), `...opts`, `useQuery(opts)`,
    `opts.queryKey`, or a queryFn/mutationFn body that calls a function from the param (`options.write(v)`).
    NOT `queryKey: id ? keys.detail(id) : …` (repo A useUser): that builds a concrete key from the param."""
    if re.search(rf"(queryKey|queryFn|mutationFn)\s*:\s*{p}\s*[,}}\n]|\.\.\.{p}\b|^\s*{p}\s*[,)]|\b{p}\.(queryKey|queryFn|mutationFn)\b", args):
        return True
    for m in re.finditer(r"(queryFn|mutationFn)\s*:", args):
        if re.search(rf"\b{p}\.\w+\(", args[m.end(): m.end() + 800]):
            return True
    return False


def wrapper_hooks(files_text):
    """Generic repo hooks that wrap a known hook AND pass their own parameters through as the
    key/fn/options (repo B: 96% of reads went through `useApiQuery(key, fn)`, so matching TanStack
    names alone judged 7 of ~190 queries). Domain hooks with a concrete key (repo A `useMisSummary`) are
    NOT wrappers: their inner call is where key bugs live; treating them as wrappers dropped repo A recall to 3/5."""
    found, base = {}, dict(HOOKS)
    for _ in range(2):  # a wrapper of a wrapper
        for text in files_text.values():
            for m in WRAPPER_DEF.finditer(text):
                name = m.group(1) or m.group(2)
                if name in base or name in found:
                    continue
                j = text.find("(", m.end() - 1) if m.group(1) else m.end()
                decl = strip_comments(text[m.start(): body_end(text, j)])
                sig = re.search(r"\(([^)]*)\)", decl)
                params = [re.split(r"[:=?]", x)[0].strip().strip(".{}[]") for x in (sig.group(1).split(",") if sig else [])]
                params = [x for x in params if re.fullmatch(r"\w+", x)]
                calls = [(h, decl[c.end():match_paren(decl, c.end() - 1)]) for c in re.finditer(r"\b(use[A-Z]\w*)\s*(?:<[^()]*?>)?\s*\(", decl)
                         for h in [c.group(1)] if h in base or h in found]
                kinds = {base.get(h) or found.get(h) for h, _ in calls}
                passthrough = any(passes_through(args, p) for _, args in calls for p in params)
                if len(kinds) == 1 and passthrough:
                    found[name] = kinds.pop()
        base.update(found)
    return found


def dep_kinds(snippet, context):
    """Code fact for draft_clobber (repo B 2026-09-22: an opus recheck with a real QueryObserver
    overturned 5 of 6 Jev 'real' verdicts; TanStack structural sharing keeps an unchanged record's
    reference). Each effect dependency is `rebuilt` (object/array literal, spread, .map/.filter or a
    call, built during render: new every render) or `passthrough` (anything else, e.g. query data)."""
    deps = re.search(r",\s*\[([^\[\]]*)\]\s*\)\s*;?\s*$", snippet.strip())
    out = {}
    for d in (deps.group(1).split(",") if deps else []):
        d = d.strip()
        root = re.match(r"[A-Za-z_]\w*", d)
        if not root:
            continue
        name = root.group(0)
        m = re.search(rf"(?:const|let)\s+{name}\s*=\s*([^\n;]+)", context or "")
        rhs = m.group(1).strip() if m else ""
        rebuilt = bool(re.match(r"[{\[]|\.\.\.", rhs)) or bool(re.search(r"\.(map|filter|reduce|slice|concat)\(|^\w+\(", rhs)) and not re.match(r"use[A-Z]", rhs)
        out[d] = "rebuilt" if rebuilt else "passthrough"
    return out


def surfaces(repo, src, waivers=()):
    root = Path(repo)
    paths = [p for p in sorted((root / src).rglob("*.ts*")) if not SKIP.search("/" + str(p.relative_to(root)))]
    files_text = {p: p.read_text(errors="replace") for p in paths}
    wrappers = wrapper_hooks(files_text)
    hooks = {**HOOKS, **wrappers}
    hook_re = re.compile(r"\b(" + "|".join(sorted(hooks, key=len, reverse=True)) + r")\s*(?:<[^()]*?>)?\s*\(")
    for path in paths:
        rel = str(path.relative_to(root))
        text = files_text[path]
        helpers = cache_helpers(text)
        decls = [(m.start(), m.group(1) or m.group(2)) for m in DECL_RE.finditer(text)]
        for m in hook_re.finditer(text):
            start, end = m.start(), match_paren(text, m.end() - 1)
            line_start = text.rfind("\n", 0, start) + 1
            prefix = text[line_start:start]
            if re.match(r"\s*(\*|//|/\*)", prefix) or re.search(r"(function\s+|const\s+)$", prefix):
                continue  # mentioned in a comment, or the wrapper's own definition
            enclosing = [d for d in decls if d[0] <= start]
            if enclosing and enclosing[-1][1] in wrappers:
                continue  # the inner call inside a wrapper; its callers are judged instead
            line = text.count("\n", 0, start) + 1
            snippet = "\n".join(text[start:end].splitlines()[:MAX_SNIPPET])
            # Enclosing top-level declaration = the component or hook this call lives in.
            before = [d for d in decls if d[0] <= start]
            after = [d for d in decls if d[0] > start]
            ctx_start = before[-1][0] if before else 0
            ctx_end = after[0][0] if after else len(text)
            context = "\n".join(text[ctx_start:ctx_end].splitlines()[:MAX_CONTEXT])
            kind = hooks[m.group(1)]
            facts = {}
            if kind == "effect":
                facts["dependency_kinds"] = dep_kinds(snippet, context)
            if kind == "mutation":
                owner = before[-1][1] if before else ""
                facts["updates_query_cache"] = updates_cache(snippet, helpers) or (
                    owner.startswith("use") and call_site_updates(root, src, owner, files_text))
            lead_in = text[max(0, line_start - 300):start]  # a sign-off comment sits just above the call
            waived = sorted({c for w in waivers if re.search(w["pattern"], lead_in + snippet) for c in w["checks"]})
            yield {
                "file": rel, "line": line, "hook": m.group(1), "kind": kind, "waived": waived,
                "owner": before[-1][1] if before else None,
                "snippet": snippet, "context": context if context != snippet else None, "facts": facts,
            }


def load_invariants(path):
    if not path:
        return []
    rules = json.loads(Path(path).read_text())["invariants"]
    for r in rules:
        r["_when"] = re.compile(r["when"]) if r.get("when") else None
    return rules


def noul(q):
    if isinstance(q, tuple):
        return {"type": "noul", "instructions": q[0], "criteria": q[1]}
    return {"type": "noul", "instructions": q}


def questions_for(s, invariants):
    qs = {k: noul(v) for k, v in GENERIC.get(s["kind"], {}).items()}
    for r in invariants:
        if s["kind"] not in r["kinds"] or ("hooks" in r and s["hook"] not in r["hooks"]):
            continue
        if r.get("files") and not re.search(r["files"], s["file"]):
            continue
        if r["_when"] and not r["_when"].search(s["snippet"] if r.get("when_scope") == "snippet" else (s["context"] or s["snippet"])):
            continue
        q = {"type": "noul", "instructions": r["question"]}
        if r.get("true") or r.get("false"):
            q["criteria"] = {"true": r.get("true", "The rule is violated"), "false": r.get("false", "The rule is followed")}
        qs["inv:" + r["id"]] = q
    return qs


def ask(key, state, questions, tries=5):
    body = json.dumps({"state": state, "model": MODEL, "questions": questions}).encode()
    for attempt in range(tries):
        req = urllib.request.Request(API, body, {"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 529, 500, 502, 503) and attempt < tries - 1:
                time.sleep(float(e.headers.get("retry-after") or 2 ** attempt))  # backoff between API retries
                continue
            raise RuntimeError(f"{e.code}: {e.read()[:300]!r}")


def judge(key, s, invariants):
    qs = questions_for(s, invariants)
    if not qs:
        return {**s, "answers": {}, "tokens": 0}
    state = {"file": s["file"], "snippet": s["snippet"]}
    if s["context"]:
        state["context"] = s["context"]
    if s["facts"]:
        state["facts"] = s["facts"]
    res = ask(key, state, qs)
    answers = {k: round(v["noul"], 3) for k, v in res["answers"].items()}
    return {**s, "answers": answers, "tokens": res["usage"]["input_tokens"], "model": res["model"]}


def leads(r):
    """Turn raw probabilities into ranked leads. Composition lives here, in code."""
    out = _leads(r)
    return [(k, p) for k, p in out if k not in r.get("waived", [])]  # repo sign-offs (waivers in invariants.json)


def _leads(r):
    a, out = r["answers"], []
    if "overwrites_user_draft" in a:
        p = min(a["overwrites_user_draft"], a["reruns_on_refetch"])
        kinds = r.get("facts", {}).get("dependency_kinds") or {}
        if kinds and "rebuilt" not in kinds.values():
            p = min(p, 0.69)  # pass-through deps: review band, not a lead (real only if another action changes the record)
        out.append(("draft_clobber", p))
    if "writes_input_to_url" in a:
        out.append(("url_sync_one_way", min(a["writes_input_to_url"], 1 - a["url_read_back"])))
    for k, p in a.items():
        if k in ("overwrites_user_draft", "reruns_on_refetch", "writes_input_to_url", "url_read_back"):
            continue
        if k == "writes_shown_data":
            # Jev judges whether it writes displayed data; code knows whether it touches the cache.
            if not r["facts"].get("updates_query_cache"):
                out.append(("mutation_no_cache_update", p))
        else:
            out.append((k, p))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--src", default="src")
    ap.add_argument("--invariants")
    ap.add_argument("--out", default=None)
    ap.add_argument("--limit", type=int, default=0, help="only judge the first N surfaces (smoke run)")
    ap.add_argument("--workers", type=int, default=8)  # endpoint throttles above ~8 in flight
    ap.add_argument("--threshold", type=float, default=0.7, help="lead band floor")
    ap.add_argument("--review", type=float, default=0.3, help="review band floor; noise straddles 0.5")
    args = ap.parse_args()

    key = api_key()
    inv_path = args.invariants or (Path(args.repo) / ".qa/invariants.json")
    invariants = load_invariants(inv_path if Path(inv_path).exists() else None)
    waivers = json.loads(Path(inv_path).read_text()).get("waivers", []) if Path(inv_path).exists() else []
    found = list(surfaces(args.repo, args.src, waivers))
    todo = found[: args.limit] if args.limit else found
    print(f"surfaces: {len(found)} total, judging {len(todo)}; invariants: {len(invariants)}", file=sys.stderr)

    results, errors = [], []
    with cf.ThreadPoolExecutor(args.workers) as pool:
        futs = {pool.submit(judge, key, s, invariants): s for s in todo}
        for f in cf.as_completed(futs):
            try:
                results.append(f.result())
            except Exception as e:  # keep going; failures are reported, never silently dropped
                s = futs[f]
                errors.append({"file": s["file"], "line": s["line"], "error": str(e)})

    ranked = sorted(
        ({"file": r["file"], "line": r["line"], "owner": r["owner"], "hook": r["hook"], "check": k, "p": p}
         for r in results for k, p in leads(r) if p >= args.review),
        key=lambda x: -x["p"],
    )
    out = Path(args.out or Path.home() / ".claude/qa-runs" / Path(args.repo).resolve().name)
    out.mkdir(parents=True, exist_ok=True)
    (out / "hunt.json").write_text(json.dumps({"model": MODEL, "results": results, "errors": errors}, indent=1))
    by_check = {}
    for x in ranked:
        lead, rev = by_check.get(x["check"], (0, 0))
        by_check[x["check"]] = (lead + 1, rev) if x["p"] >= args.threshold else (lead, rev + 1)
    n_lead = sum(v[0] for v in by_check.values())
    row = lambda x: f"| {x['p']:.2f} | {x['check']} | `{x['file']}:{x['line']}` | {x['owner']} |"
    lines = [f"# Jev hunt: {args.repo}", "",
             f"surfaces judged {len(results)}/{len(todo)} (found {len(found)}), errors {len(errors)}, "
             f"input tokens {sum(r['tokens'] for r in results):,}, leads ≥{args.threshold}: {n_lead}, "
             f"review {args.review}–{args.threshold}: {len(ranked) - n_lead}", "",
             "| check | leads | review |", "|---|---|---|",
             *[f"| {k} | {v[0]} | {v[1]} |" for k, v in sorted(by_check.items(), key=lambda kv: -kv[1][0])], "",
             "## Leads", "", "| p | check | location | owner |", "|---|---|---|---|",
             *[row(x) for x in ranked if x["p"] >= args.threshold], "",
             "## Review band (read if time allows; noise straddles 0.5)", "", "| p | check | location | owner |", "|---|---|---|---|",
             *[row(x) for x in ranked if x["p"] < args.threshold]]
    known_path = Path(args.repo) / ".qa/known-bugs.json"
    if known_path.exists():  # recall check: tuning must never drop a confirmed bug
        all_known = json.loads(known_path.read_text())["bugs"]
        known = [b for b in all_known if b.get("hunt_covers", True)]  # denominator = bugs a check targets
        hit = {(x["file"], x["line"], x["check"]) for x in ranked}
        missed = [b for b in known if (b["file"], b["line"], b["check"]) not in hit]
        lines[3:3] = [f"recall on known bugs a check targets: {len(known) - len(missed)}/{len(known)}"
                      f" (+{len(all_known) - len(known)} known bugs no check targets yet)"
                      + "".join(f"\n- MISSED {b['severity']} {b['check']} `{b['file']}:{b['line']}`" for b in missed), ""]
    (out / "hunt.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:8 + len(by_check)]))
    print(f"\nfull report: {out / 'hunt.md'}")
    if errors:
        print(f"{len(errors)} surfaces failed; see hunt.json errors", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
