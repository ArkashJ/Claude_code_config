#!/usr/bin/env python3
"""Intake: read every file ONCE, in code, before anyone reasons about the set.

INCIDENTS (Spot BEN-175 document study, 2026-09-29) this exists to prevent:
  (1) the client's two spec files had names SWAPPED vs her email (Spot.docx was the detailed spec) -- so
      words/pages are printed per file and Jev classifies by CONTENT, never by filename;
  (2) 1 of 28 "agreements" (form3 'version 9'.doc) was an LLC OPERATING agreement, found only by reading --
      classification + folder-majority check flags it (MISFILED) without a human reading 28 files;
  (3) pandoc renders Word auto-numbering as roman-numeral items -- 27 of 28 agreements were auto-numbered, so
      real section numbers had to be rebuilt from numbering XML; intake warns and (--text-dir) writes them;
  (4) "Working Capital" appeared in 0 of 28 agreements -- the client's headline example had no coverage;
      --probe prints "N of M files" and shouts ZERO COVERAGE.
(Incidents 5-6 are handled by pdf-pages.sh / pdf_chart_triage.py / check_chart_json.py / verify_golden.py.)

Text: docx -> pandoc -t plain --wrap=none --track-changes=accept (the "final" view; quotes in a golden key
must come from this view. `all` keeps deleted text inline: 165,261 vs 149,487 chars on the same redlined
agreement, so `--track-changes all` is available but NOT the default); .doc -> textutil; pdf -> pdftotext -layout.
Tracked changes are still COUNTED (w:ins/w:del) so a redlined file is never silently read as clean.

Jev is used only for the document-type call (Choice, first ~4000 chars). Top probability < 0.70 -> REVIEW.
No key/API -> "unmeasured (jev unavailable)" and exit 2 (after everything code can do is printed). --no-jev skips
the classification on purpose (exit 0, classes shown as "-").

usage: intake.py PATH... [--json out.json] [--text-dir DIR] [--classes "a,b,c"] [--probe "Term A,Term B"]
                         [--track-changes accept|all|reject] [--no-jev]
--text-dir DIR writes DIR/<folder>__<name>.txt (+ DIR/num/<...>.txt = recovered numbering) for verify_golden.py.
"""
import argparse, collections, json, os, re, subprocess, sys, zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import jevlib
from docx_numbering import dump as numbering_dump

EXTS = {".docx", ".doc", ".pdf", ".txt", ".md"}
DEFAULT_CLASSES = {
    "purchase agreement": "An asset, equity or stock purchase agreement between a buyer and seller: purchase price, closing, representations and warranties, indemnification.",
    "operating agreement": "Governance agreement of an LLC or partnership: members, capital contributions, management, distributions. Not a sale of a business.",
    "spec or notes": "A product or feature specification, requirements list, term sheet, meeting notes, or client email saying what to build.",
    "study or report": "A survey, study or research report: statistics, prevalence percentages, charts, methodology.",
    "other": "Does not fit any of the other types.",
}
CONF_FLOOR = 0.70
CLASSIFY_CHARS = 4000


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{cmd[0]} exit {r.returncode}: {r.stderr.strip()[:200]}")
    return r.stdout


def norm(s):
    return re.sub(r"\s+", " ", s)


def out_names(path):
    """Same naming the golden key already uses: <folder>__<sanitized basename>.txt, numbering without .docx."""
    stem = re.sub(r"[ ()]", "_", path.name)
    return f"{path.parent.name}__{stem}.txt", f"{path.parent.name}__{re.sub(r'.docx$', '', stem)}.txt"


def read_file(path, track):
    """-> dict(fmt, text, pages, docx facts). Raises on unreadable (reported, never skipped silently)."""
    ext = path.suffix.lower()
    d = {"fmt": ext.lstrip("."), "pages": None, "ins": 0, "dele": 0, "comments": False, "numbered": 0}
    if ext == ".docx":
        d["text"] = run(["pandoc", "-t", "plain", "--wrap=none", f"--track-changes={track}", str(path)])
        z = zipfile.ZipFile(path)
        xml = z.read("word/document.xml").decode("utf8", "replace")
        d["ins"], d["dele"] = len(re.findall(r"<w:ins\b", xml)), len(re.findall(r"<w:del\b", xml))
        d["comments"] = "word/comments.xml" in z.namelist()
        if "word/numbering.xml" in z.namelist():
            d["numbered"] = sum(1 for lab, t in numbering_dump(str(path)) if lab and t.strip())
        if "docProps/app.xml" in z.namelist():
            m = re.search(r"<Pages>(\d+)</Pages>", z.read("docProps/app.xml").decode("utf8", "replace"))
            d["pages"] = int(m.group(1)) if m else None
    elif ext == ".doc":
        d["text"] = run(["textutil", "-convert", "txt", "-stdout", str(path)])
    elif ext == ".pdf":
        d["text"] = run(["pdftotext", "-layout", str(path), "-"])
        m = re.search(r"^Pages:\s+(\d+)", run(["pdfinfo", str(path)]), re.M)
        d["pages"] = int(m.group(1)) if m else None
    else:
        d["text"] = path.read_text(errors="replace")
    d["words"] = len(d["text"].split())
    return d


def classifier(classes):
    crit = {c: DEFAULT_CLASSES.get(c, c) for c in classes}  # unknown class: its own name is the description
    return {"cls": {"type": "choice", "criteria": crit,
                    "instructions": "What kind of document is `doc`? Judge by its content and purpose, never by any file name."}}


def classify(rec, classes):
    try:
        model, a = jevlib.ask_safe({"doc": norm(rec["text"])[:CLASSIFY_CHARS], "facts": {"words": rec["words"], "pages": rec["pages"]}},
                                   classifier(classes))
    except jevlib.JevUnavailable as e:
        return {"unavailable": str(e)}
    c = a["cls"]
    top = c["probabilities"][c["choice"]]
    return {"cls": c["choice"], "p": round(top, 3), "confidence": round(c["confidence"], 3), "model": model,
            "review": top < CONF_FLOOR}


def misfiled(recs):
    """Class disagrees with the majority of its folder. Needs >=3 classified files and a strict majority (>50%)."""
    by = collections.defaultdict(list)
    for r in recs:
        if "cls" in r.get("jev", {}):
            by[r["folder"]].append(r)
    out = []
    for folder, rs in by.items():
        if len(rs) < 3:
            continue
        cls, n = collections.Counter(r["jev"]["cls"] for r in rs).most_common(1)[0]
        if n * 2 <= len(rs):
            continue
        out += [(r, cls, n, len(rs)) for r in rs if r["jev"]["cls"] != cls]
    return out


def probe_counts(recs, terms):
    res = {}
    for t in terms:
        rx = re.compile(re.escape(norm(t)), re.I)
        per = {r["path"]: len(rx.findall(norm(r["text"]))) for r in recs}
        res[t] = {"files_with_hit": sum(1 for n in per.values() if n), "files": len(per), "hits": sum(per.values()), "per_file": per}
    return res


def gather(paths):
    files, skipped = [], []
    for p in map(Path, paths):
        if p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file() and not f.name.startswith("~$") and not any(x.startswith(".") for x in f.relative_to(p).parts):
                    (files if f.suffix.lower() in EXTS else skipped).append(f)
        elif p.is_file():
            (files if p.suffix.lower() in EXTS else skipped).append(p)
        else:
            sys.exit(f"intake: no such path: {p}")
    return files, skipped


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--json")
    ap.add_argument("--text-dir")
    ap.add_argument("--classes", default=",".join(DEFAULT_CLASSES))
    ap.add_argument("--probe", default="")
    ap.add_argument("--track-changes", default="accept", choices=["accept", "all", "reject"])
    ap.add_argument("--no-jev", action="store_true")
    a = ap.parse_args(argv)
    classes = [c.strip() for c in a.classes.split(",") if c.strip()]
    terms = [t.strip() for t in a.probe.split(",") if t.strip()]

    files, skipped = gather(a.paths)
    if not files:
        sys.exit("intake: 0 readable files (.docx .doc .pdf .txt .md) under the given paths")
    recs, failed = [], []
    for f in files:
        try:
            r = read_file(f, a.track_changes)
        except Exception as e:
            failed.append((f, str(e)))
            continue
        r.update(path=str(f), folder=str(f.parent), name=f.name)
        recs.append(r)
        if a.text_dir:
            tn, nn = out_names(f)
            Path(a.text_dir).mkdir(parents=True, exist_ok=True)
            (Path(a.text_dir) / tn).write_text(r["text"], encoding="utf-8")
            if r["numbered"]:
                (Path(a.text_dir) / "num").mkdir(exist_ok=True)
                (Path(a.text_dir) / "num" / nn).write_text(
                    "\n".join((lab + " " if lab else "") + t for lab, t in numbering_dump(str(f)) if t.strip()) + "\n", encoding="utf-8")

    jev_down = None
    if a.no_jev:
        for r in recs:
            r["jev"] = {}
    else:
        for r, j in zip(recs, jevlib.pmap(lambda r: classify(r, classes), recs)):
            r["jev"] = j
        downs = [r["jev"]["unavailable"] for r in recs if "unavailable" in r["jev"]]
        jev_down = downs[0] if downs else None

    # ---- table
    print(f"{'file':<58} {'fmt':<4} {'pages':>5} {'words':>7}  {'class (p)':<30} flags")
    for r in recs:
        j = r["jev"]
        cl = "-" if not j else (jevlib.UNMEASURED if "unavailable" in j else f"{j['cls']} ({j['p']:.2f})")
        fl = []
        if j.get("review"):
            fl.append("REVIEW")
        if r["ins"] or r["dele"]:
            fl.append(f"REDLINE ins={r['ins']} del={r['dele']}")
        if r["comments"]:
            fl.append("COMMENTS")
        if r["numbered"] >= 5:
            fl.append(f"auto-numbered({r['numbered']}): section numbers need numbering XML")
        if r["words"] < 50:
            fl.append("NO TEXT: render pages and read images")
        short = "/".join(Path(r["path"]).parts[-2:])
        short = short if len(short) <= 58 else "…" + short[-57:]
        print(f"{short:<58} {r['fmt']:<4} {str(r['pages'] or '-'):>5} {r['words']:>7}  {cl:<30} {'; '.join(fl)}")

    # ---- verdict
    print("\n== verdict ==")
    print(f"files: {len(files)} found, {len(recs)} read, {len(failed)} unreadable, {len(skipped)} unsupported")
    for f, e in failed:
        print(f"  UNREADABLE {f}: {e}")
    for f in skipped:
        print(f"  UNSUPPORTED {f}")
    red = [r for r in recs if r["ins"] or r["dele"]]
    print(f"redlined: {len(red)} of {len(recs)} files carry tracked changes; comments.xml in {sum(r['comments'] for r in recs)}; "
          f"auto-numbered (>=5 numbered paragraphs): {sum(r['numbered'] >= 5 for r in recs)}")
    probes = probe_counts(recs, terms)
    for t, p in probes.items():
        z = "   <-- ZERO COVERAGE: no file contains this term" if p["files_with_hit"] == 0 else ""
        print(f"probe {t!r}: {p['files_with_hit']} of {p['files']} files ({p['hits']} hits){z}")
    mis = []
    if jev_down:
        print(f"classification: {jevlib.UNMEASURED} -- {jev_down}")
    elif not a.no_jev:
        cnt = collections.Counter(r["jev"]["cls"] for r in recs)
        print("classes: " + ", ".join(f"{c} {n}" for c, n in cnt.most_common()) + f"  (model {recs[0]['jev']['model']})")
        rv = [r for r in recs if r["jev"]["review"]]
        print(f"REVIEW (top p < {CONF_FLOOR}): {len(rv)} of {len(recs)}")
        for r in rv:
            print(f"  REVIEW {r['path']}: {r['jev']['cls']} p={r['jev']['p']}")
        mis = misfiled(recs)
        print(f"likely MISFILED: {len(mis)}")
        for r, cls, n, tot in mis:
            print(f"  MISFILED {r['path']}: reads as '{r['jev']['cls']}' (p={r['jev']['p']}) but {n} of {tot} files in its folder are '{cls}'")
    if a.text_dir:
        print(f"text written: {len(recs)} files to {a.text_dir}")
    if a.json:
        json.dump({"files": [{k: v for k, v in r.items() if k != "text"} for r in recs], "probes": probes,
                   "misfiled": [r["path"] for r, *_ in mis], "unsupported": [str(f) for f in skipped],
                   "unreadable": [str(f) for f, _ in failed], "jev_unavailable": jev_down}, open(a.json, "w"), indent=1)
        print(f"json: {a.json}")
    return 2 if jev_down else (1 if failed else 0)


if __name__ == "__main__":
    sys.exit(main())
