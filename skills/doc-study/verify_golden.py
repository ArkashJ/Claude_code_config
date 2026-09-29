#!/usr/bin/env python3
"""Machine-verify a golden answer key: every verbatim quote is an exact substring of its source text and every
section_ref exists in that document. Exit 1 on any miss. Generalised from /tmp/golden/build.py (2026-09-29).

INCIDENT (Spot BEN-175, 2026-09-29): the PCPPA golden key (28 files) carries 272 quotes + 332 section refs.
Both were machine-verified -- 272/272 exact substrings, 332/332 refs present -- and that is the ONLY reason the
key could be trusted as ground truth for grading extraction. A key that is merely "read carefully" is a second
LLM opinion. The refs needed the auto-numbering recovered from numbering XML (pandoc gives roman numerals), so
verification reads two texts per document: the plain text (quotes) and the recovered-numbering map (refs).

Golden format (the shape build.py produced; ANY nesting works): a list of records (or {"records":[...]}); each
record has source_text_path, optional section_number_map_path, optional excluded:true, and anywhere inside it
dicts carrying `verbatim_quote` and/or `section_ref` (answers.Qn, adjacent_mechanisms[], ...). Quotes compare
whitespace-normalised; curly quotes are NOT folded (a straight-quote quote of a curly-quote text is a miss).
Files are found in TEXT_DIR by the basename of the recorded path, else TEXT_DIR/num/<basename> for the map,
else intake.py's own naming from the record's `file` (<folder>__<name>.txt). Produce TEXT_DIR with:
    intake.py <docs dir> --text-dir TEXT_DIR --no-jev
Fail-closed: a missing text file, a missing declared map, an unrecognised ref form, or ZERO quotes checked is
a failure (CLAUDE.md: a calibration test "parsed 0/0 docs" and PASSED). `--fold-quotes` is deliberately absent.

usage: verify_golden.py GOLDEN.json TEXT_DIR
prints: quotes N/N, refs M/M     exit 0 only if every check passed
"""
import json, re, sys
from pathlib import Path

HEAD = re.compile(r"^(Section \d+\.\d+ |\d+\.\d+\) |Article [IVXL]+ |[A-Z][A-Z ,;&’'-]{8,}$)")


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


def ref_ok(ref, lines):
    """Does every ';'-separated part of `ref` exist in the numbering map `lines`? Forms: 'Art. IV', 'Section 2.7',
    'Section 2.7(b)', 'Section 2.7(b)-(c)' (range -> first part). Anything else is a miss (fail-closed)."""
    if not ref:
        return True
    ref = re.sub(r"\(([a-z])\)-\([a-z]\)", r"(\1)", ref)  # (a)-(e) -> (a)
    for part in (p.strip() for p in ref.split(";")):
        m = re.match(r"Art\. ([IVXL]+)\b", part)
        if m:
            if not any(l.startswith(f"Article {m.group(1)} ") for l in lines):
                return False
            continue
        m = re.match(r"(?:Section|§)\s*(\d+)\.(\d+)(.*)$", part)
        if not m:
            return False
        X, Y, rest = m.groups()
        idx = None
        for i, l in enumerate(lines):
            if l.startswith((f"Section {X}.{Y} ", f"{X}.{Y}) ", f"§ {X}.{Y} ")):
                idx = i  # LAST match, as build.py: exhibits restart numbering, the main body precedes them
        if idx is None:
            return False
        subs = re.findall(r"\(([a-z0-9]+)\)", rest)
        if subs:
            end = len(lines)
            for j in range(idx + 1, len(lines)):
                if HEAD.match(lines[j]) and not lines[j].startswith("("):
                    end = j
                    break
            if not any(l.startswith(f"({subs[0]}) ") for l in lines[idx:end]):
                return False
    return True


def collect(node, path, out):
    """Every dict holding verbatim_quote / section_ref, with a readable location."""
    if isinstance(node, dict):
        if "verbatim_quote" in node or "section_ref" in node:
            out.append((path, node.get("section_ref") or "", node.get("verbatim_quote") or ""))
        for k, v in node.items():
            collect(v, f"{path}.{k}", out)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            collect(v, f"{path}[{i}]", out)


def find(text_dir, recorded, alt_dirs=("", "num")):
    if recorded:
        for d in alt_dirs:
            p = text_dir / d / Path(recorded).name
            if p.is_file():
                return p
    return None


def intake_names(rec):
    f = Path(rec.get("file") or "")
    if not f.name:
        return None, None
    stem = re.sub(r"[ ()]", "_", f.name)
    fam = rec.get("family") or f.parent.name
    return f"{fam}__{stem}.txt", f"{fam}__{re.sub(r'.docx$', '', stem)}.txt"


def verify(golden, text_dir):
    recs = golden.get("records") if isinstance(golden, dict) else golden
    if not isinstance(recs, list):
        raise SystemExit("golden: expected a list of records or {'records': [...]}")
    q_ok = q_n = r_ok = r_n = 0
    errors, excluded = [], 0
    for rec in recs:
        rid = rec.get("id") or rec.get("file") or "?"
        if rec.get("excluded"):
            excluded += 1
            continue
        tname, nname = intake_names(rec)
        tpath = find(text_dir, rec.get("source_text_path")) or find(text_dir, tname)
        if not tpath:
            errors.append(f"MISSING TEXT {rid}: no text file for {rec.get('source_text_path')!r} in {text_dir}")
            continue
        text = norm(tpath.read_text(encoding="utf-8"))
        items = []
        collect(rec, rid, items)
        lines = None
        if any(ref for _, ref, _ in items):
            mp = rec.get("section_number_map_path")
            mpath = find(text_dir, mp) or (None if mp else find(text_dir, nname))
            if mp and not mpath:
                errors.append(f"MISSING NUMBER MAP {rid}: {mp!r} not found in {text_dir} or {text_dir}/num")
                continue
            lines = (mpath or tpath).read_text(encoding="utf-8").splitlines()
        for where, ref, quote in items:
            if quote:
                q_n += 1
                if norm(quote) in text:
                    q_ok += 1
                else:
                    errors.append(f"QUOTE MISS {where}: {quote[:90]!r}")
            if ref:
                r_n += 1
                if ref_ok(ref, lines):
                    r_ok += 1
                else:
                    errors.append(f"REF MISS {where}: {ref!r}")
    return q_ok, q_n, r_ok, r_n, excluded, len(recs), errors


def main(argv):
    if len(argv) != 3:
        sys.exit(__doc__.split("usage:")[1].strip())
    q_ok, q_n, r_ok, r_n, excl, n, errors = verify(json.load(open(argv[1])), Path(argv[2]))
    for e in errors:
        print(e)
    if q_n == 0 and r_n == 0:
        errors.append("nothing checked")
        print("NOTHING CHECKED: 0 quotes and 0 refs -- a verifier that checks nothing has verified nothing")
    print(f"quotes {q_ok}/{q_n}, refs {r_ok}/{r_n}  (records {n}, excluded {excl}, errors {len(errors)})")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
