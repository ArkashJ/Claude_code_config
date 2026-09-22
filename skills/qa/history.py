#!/usr/bin/env python3
"""Where do this repo's bugs actually escape? Classify every fix commit by surface and
failure mechanism with Jev, so HUNT and PLAN target the classes that keep shipping.

usage: history.py REPO [--grep '^fix'] [--since 2026-01-01]
"""
import argparse, collections, concurrent.futures as cf, json, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from hunt import api_key, ask

SURFACES = {
    "query_cache": "TanStack Query keys, caching, staleTime, select, placeholder or initial data",
    "mutation_refresh": "A write that did not refresh, invalidate, or roll back what the UI shows",
    "effect_lifecycle": "useEffect/useLayoutEffect timing, cleanup, dependency arrays, re-render loops",
    "url_state": "URL search params, route params, navigation, redirects, back/forward",
    "form": "Form fields, validation schemas, defaults, dirty state, submit handling",
    "permission": "RBAC gates, role or permission checks, who can see or do what",
    "api_contract": "Request or response shape, types, OpenAPI drift, field names, nullability",
    "states": "Loading, empty, error, or partial-data states and fallbacks",
    "auth_session": "Login, tokens, refresh, MFA, session expiry, tenant scoping",
    "table_list": "Tables, pagination, sorting, filtering, search over lists",
    "formatting": "Dates, time zones, numbers, currency, units, text formatting",
    "layout_visual": "CSS, layout, responsive behavior, visual styling, animation",
    "a11y": "Accessibility: labels, focus, keyboard, ARIA, contrast",
    "files_docs": "File upload, download, PDF, export, CSV",
    "build_tooling": "Build, lint, tests, CI, env config, dependencies, scripts",
    "none": "None of these",
}
MECHANISMS = {
    "stale_or_wrong_data": "The UI showed outdated, mismatched, or incorrect data",
    "crash": "An exception, blank screen, or failed render",
    "missing_state": "A loading, empty, error, or edge state was missing or wrong",
    "access": "Someone could see or do something they should not, or was wrongly blocked",
    "race_ordering": "A timing, ordering, or concurrency problem",
    "contract": "The frontend and backend disagreed about data shape or behavior",
    "ux_visual": "It worked but looked or behaved poorly for the user",
    "tooling": "A build, test, lint, or developer-workflow problem, not user-facing",
}


def commits(repo, grep, since):
    fmt = "%x1e%H%x1f%s%x1f%b"
    args = ["git", "-C", repo, "log", "-i", f"--grep={grep}", "--no-merges", f"--format={fmt}", "--name-only"]
    if since:
        args.append(f"--since={since}")
    out = subprocess.run(args, capture_output=True, text=True, check=True).stdout
    for rec in out.split("\x1e")[1:]:
        head, _, files = rec.partition("\n\n") if "\x1f" in rec.split("\n", 1)[0] else (rec, "", "")
        sha, subject, body = (head.split("\x1f") + ["", ""])[:3]
        yield {"sha": sha[:10], "subject": subject.strip(), "body": body.strip()[:1500],
               "files": [f for f in files.split("\n") if f.strip()][:40]}


def classify(key, c):
    state = {"commit_subject": c["subject"], "commit_body": c["body"], "files_changed": c["files"]}
    qs = {
        "surface": {"type": "choice", "instructions": "Which part of the frontend did the bug fixed by this commit live in?", "criteria": SURFACES},
        "mechanism": {"type": "choice", "instructions": "How did the bug fixed by this commit fail?", "criteria": MECHANISMS},
        "user_facing": {"type": "noul", "instructions": "Would an end user of the application have noticed the bug this commit fixes?"},
    }
    a = ask(key, state, qs)["answers"]
    return {**c, "surface": a["surface"]["choice"], "surface_conf": a["surface"]["confidence"],
            "mechanism": a["mechanism"]["choice"], "user_facing": a["user_facing"]["noul"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--grep", default="^fix")
    ap.add_argument("--since")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    key, cs = api_key(), list(commits(args.repo, args.grep, args.since))
    rows, errors = [], 0
    with cf.ThreadPoolExecutor(args.workers) as pool:
        for f in cf.as_completed([pool.submit(classify, key, c) for c in cs]):
            try:
                rows.append(f.result())
            except Exception:
                errors += 1
    out = Path.home() / ".claude/qa-runs" / Path(args.repo).resolve().name
    out.mkdir(parents=True, exist_ok=True)
    (out / "history.json").write_text(json.dumps(rows, indent=1))
    uf = [r for r in rows if r["user_facing"] >= 0.5]
    pair = collections.Counter((r["surface"], r["mechanism"]) for r in uf)
    surf = collections.Counter(r["surface"] for r in uf)
    print(f"fix commits: {len(cs)} total, classified {len(rows)}, errors {errors}, user-facing {len(uf)}")
    print("\nuser-facing bugs by surface:")
    for s, n in surf.most_common():
        print(f"  {n:4d}  {s}")
    print("\ntop surface × mechanism:")
    for (s, m), n in pair.most_common(12):
        print(f"  {n:4d}  {s} × {m}")
    print(f"\nrows: {out / 'history.json'}")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
