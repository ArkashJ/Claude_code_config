#!/usr/bin/env python3
"""Triage PDF pages BEFORE spending image-reading agents: which pages present quantitative chart/table data?

INCIDENT (Spot BEN-175, 2026-09-29): the 134-page ABA deal-points study yielded 152 chart readings; dividers,
the table of contents, definitions and clause-only pages (5 records came back with empty `outcomes` and a
market of 'n/a') were rendered and read by agents that could have skipped them. Code computes the facts
(digit/percent density, 'Subset', TOC dot-leaders, text length); Jev makes the ONE semantic call code cannot:
"is this a page of quantitative data?". Bands: p > 0.70 READ, p < 0.30 SKIP, else REVIEW (a human/agent looks).
A page with almost no text layer (chart pixels, not text) is never guessed: it is REVIEW ("render it").

usage: pdf_chart_triage.py PDF [--pages 5-40] [--json out.json]
Jev unavailable -> prints "unmeasured (jev unavailable)" and exits 2 (facts are still printed).
"""
import argparse, json, re, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import jevlib

NO_TEXT_CHARS = 40
QUESTION = {"noul": {"type": "noul",
    "instructions": {"question": "Does `page` present quantitative chart or table data: percentages, counts, medians or other numbers that answer a survey or study question?",
                     "inspect": "`page` text and `facts`"},
    "criteria": {"true": {"what": "A results page: a question or topic with a distribution of outcomes and numbers, often a 'Subset' line and percent values or a table of statistics.",
                          "examples": ["Earnout - Included? 82% No, 18% Yes. Subset: All deals"]},
                 "false": {"what": "A page with no results to record.",
                           "not_for": "a page that merely contains a few numbers such as page numbers or years",
                           "examples": ["Table of Contents", "Section divider: Financial Provisions", "Definitions and methodology prose", "Clause-only text quoting sample agreement language"]}}}}


def page_texts(pdf, first, last):
    """{page: text} via one pdftotext per page (layout mode keeps chart labels on their lines)."""
    out = {}
    for p in range(first, last + 1):
        r = subprocess.run(["pdftotext", "-layout", "-f", str(p), "-l", str(p), pdf, "-"], capture_output=True, text=True)
        if r.returncode:
            raise SystemExit(f"pdftotext failed on page {p}: {r.stderr.strip()[:150]}")
        out[p] = r.stdout
    return out


def facts(text):
    nonspace = re.sub(r"\s", "", text)
    return {"text_chars": len(nonspace),
            "digit_density": round(sum(c.isdigit() for c in nonspace) / len(nonspace), 3) if nonspace else 0.0,
            "percent_tokens": len(re.findall(r"\d+(?:\.\d+)?\s*%", text)),
            "has_subset": bool(re.search(r"\bSub-?set\b", text, re.I)),
            "toc_leaders": len(re.findall(r"\.{4,}\s*\d+\s*$", text, re.M))}


def decide(f, p):
    """Code-side verdict from Jev's p and the facts. Jev never overrides 'no text layer'."""
    if f["text_chars"] < NO_TEXT_CHARS:
        return "REVIEW", "no text layer: render and look"
    b = jevlib.band(p)
    return {"yes": "READ", "no": "SKIP", "review": "REVIEW"}[b], ""


def ranges(pages):
    out, i = [], 0
    while i < len(pages):
        j = i
        while j + 1 < len(pages) and pages[j + 1] == pages[j] + 1:
            j += 1
        out.append(f"{pages[i]}" if i == j else f"{pages[i]}-{pages[j]}")
        i = j + 1
    return ",".join(out) or "-"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--pages")
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    if not Path(a.pdf).is_file():
        sys.exit(f"no such file: {a.pdf}")
    total = int(re.search(r"^Pages:\s+(\d+)", subprocess.run(["pdfinfo", a.pdf], capture_output=True, text=True).stdout, re.M).group(1))
    first, last = (int(x) for x in a.pages.split("-")) if a.pages and "-" in a.pages else ((int(a.pages),) * 2 if a.pages else (1, total))
    if not 1 <= first <= last <= total:
        sys.exit(f"--pages {first}-{last} invalid for a {total}-page PDF")
    texts = page_texts(a.pdf, first, last)
    F = {p: facts(t) for p, t in texts.items()}

    def one(p):
        try:
            _, ans = jevlib.ask_safe({"page": re.sub(r"[ \t]+", " ", texts[p])[:6000], "facts": F[p]}, QUESTION)
            return p, ans["noul"]["noul"], None
        except jevlib.JevUnavailable as e:
            return p, None, str(e)
    res = jevlib.pmap(one, [p for p in texts if F[p]["text_chars"] >= NO_TEXT_CHARS])
    P = {p: v for p, v, _ in res}
    down = next((e for _, _, e in res if e), None)

    rows, tally = [], {"READ": [], "SKIP": [], "REVIEW": []}
    print(f"{'page':>4}  {'chars':>5} {'digit':>5} {'pct#':>4} subset  {'p':>5}  verdict")
    for p in sorted(texts):
        f, pv = F[p], P.get(p)
        if pv is None and f["text_chars"] >= NO_TEXT_CHARS:
            v, why = jevlib.UNMEASURED, ""
        else:
            v, why = decide(f, pv if pv is not None else 0.5)
            tally[v].append(p)
        rows.append({"page": p, "p": pv, "verdict": v, "why": why, **f})
        ps = "-" if pv is None else f"{pv:.2f}"
        print(f"{p:>4}  {f['text_chars']:>5} {f['digit_density']:>5.2f} {f['percent_tokens']:>4} {'yes' if f['has_subset'] else '-':<6}  {ps:>5}  {v} {why}")
    print(f"\npages {first}-{last}: READ {len(tally['READ'])}, SKIP {len(tally['SKIP'])}, REVIEW {len(tally['REVIEW'])} of {len(texts)}")
    for k in ("READ", "REVIEW", "SKIP"):
        print(f"{k}: {ranges(tally[k])}")
    if a.json:
        json.dump({"pdf": a.pdf, "model": "jev", "rows": rows}, open(a.json, "w"), indent=1)
    if down:
        print(f"\n{jevlib.UNMEASURED}: {down}")
        return jevlib.EXIT_UNMEASURED
    return 0


if __name__ == "__main__":
    sys.exit(main())
