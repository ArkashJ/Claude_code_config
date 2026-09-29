#!/usr/bin/env python3
"""Self-test for the doc-study kit: `python3 ~/.claude/skills/doc-study/test_doc_study.py`.

Each guard is proved twice -- a GOOD fixture passes and a MUTATED fixture is REJECTED with the specific error --
because a checker that cannot fail is worse than none (Spot BEN-175, 2026-09-29: TestRealDocsDirectionCalibration
printed "parsed 0/0 docs" and PASSED). Offline: no Jev, no network. Prints "N passed" / exits 1 on any failure.
"""
import copy, json, os, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).parent
PY = sys.executable
ENV_NO_JEV = {k: v for k, v in os.environ.items() if not k.startswith("TYPESAFE")}
sys.path.insert(0, str(HERE))
import check_chart_json as cc
import pdf_chart_triage as tri


def run(*cmd, env=None):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, env=env)
    return r.returncode, r.stdout + r.stderr


# ------------------------------------------------------------------ check_chart_json
GOOD_REC = {"page": 11, "topic": "Earnout", "question": "Is an earnout included?", "subset": "All deals",
            "outcomes": {"No earnout": 82, "Earnout": 18}, "multi_select": False, "market": "No earnout (82%)"}


def chart_file(tmp, recs, name="c.json"):
    p = Path(tmp) / name
    p.write_text(json.dumps({"charts": recs}))
    return p


def test_chart_good_passes(tmp):
    rc, out = run(PY, HERE / "check_chart_json.py", chart_file(tmp, [GOOD_REC]))
    assert rc == 0 and "violations 0" in out, out


def test_chart_sum_mutation_rejected(tmp):
    bad = copy.deepcopy(GOOD_REC)
    bad["outcomes"]["Earnout"] = 30  # sums to 112
    rc, out = run(PY, HERE / "check_chart_json.py", chart_file(tmp, [bad]))
    assert rc == 1 and "sum to 112" in out, out


def test_chart_market_mutation_rejected(tmp):
    bad = copy.deepcopy(GOOD_REC)
    bad["market"] = "Earnout (18%)"  # not the tallest bar, and 18 != 82
    rc, out = run(PY, HERE / "check_chart_json.py", chart_file(tmp, [bad]))
    assert rc == 1 and "does not match argmax" in out, out


def test_chart_schema_mutation_rejected(tmp):
    bad = {k: v for k, v in GOOD_REC.items() if k != "subset"}
    rc, out = run(PY, HERE / "check_chart_json.py", chart_file(tmp, [bad]))
    assert rc == 1 and "subset missing" in out, out


def test_chart_multiselect_exempt_from_sum_but_not_market(tmp):
    multi = {**GOOD_REC, "multi_select": True, "outcomes": {"War": 97, "Law": 97, "Tax": 60}, "market": "War / Law (97% each)"}
    assert cc.check(multi) == []
    assert [c for c, _ in cc.check({**multi, "market": "Tax (60%)"})] == ["market"]


def test_chart_waiver_needs_a_reason(tmp):
    two_panel = {**GOOD_REC, "outcomes": {"A": 60, "B": 40, "C": 55, "D": 45}, "market": "A (60%)"}
    assert [c for c, _ in cc.check(two_panel)] == ["sum"]
    ok = {**two_panel, "waive": {"sum": "two panels, each sums to 100"}}
    assert [c for c, _ in cc.check(ok)] == ["waiver"]
    empty = {**two_panel, "waive": {"sum": "  "}}
    assert [c for c, _ in cc.check(empty)] == ["sum"]


def test_chart_note_list_and_empty_page_rule(tmp):
    divider = {**GOOD_REC, "outcomes": {}, "market": "n/a", "note": "clause-only page"}
    assert cc.check(divider) == []
    assert [c for c, _ in cc.check({**divider, "note": ""})] == ["market"]  # empty page must be explained
    rc, out = run(PY, HERE / "check_chart_json.py", chart_file(tmp, [GOOD_REC, {**GOOD_REC, "note": "ambiguous legend"}]))
    assert rc == 0 and "1 of 2 records carry a note" in out and "ambiguous legend" in out, out


def test_chart_zero_records_is_not_a_pass(tmp):
    rc, out = run(PY, HERE / "check_chart_json.py", chart_file(tmp, []))
    assert rc == 1 and "nothing was checked" in out, out


# ------------------------------------------------------------------ verify_golden
TEXT = "ARTICLE II\nThe Purchase Price shall be paid in cash at Closing.\nBuyer may set off any amount owed under Section 2.7.\n"
NUM = "Article I DEFINITIONS\nArticle II PURCHASE AND SALE\nSection 2.7 Purchase Price Adjustment\n(a) Estimate. Seller delivers it.\n(b) Statement. Buyer delivers it.\nSection 2.8 Closing\n"
GOLDEN = [
    {"id": "A", "file": "fam/Doc A.docx", "source_text_path": "/x/fam__Doc_A.docx.txt", "section_number_map_path": "/x/num/fam__Doc_A.txt",
     "answers": {"Q1": {"section_ref": "Section 2.7(b)", "verbatim_quote": "The Purchase Price shall be paid in cash"},
                 "Q2": {"section_ref": "Art. II; Section 2.8", "verbatim_quote": ""}},
     "adjacent_mechanisms": [{"section_ref": "Section 2.7(a)-(b)", "verbatim_quote": "Buyer may set off\n any amount owed"}]},
    {"id": "B", "excluded": True, "source_text_path": "/x/does_not_exist.txt", "answers": {"Q1": {"section_ref": "Section 9.9", "verbatim_quote": "never checked"}}},
]


def vg_setup(tmp, golden=GOLDEN, text=TEXT, num=NUM):
    d = Path(tmp) / "text"
    (d / "num").mkdir(parents=True)
    (d / "fam__Doc_A.docx.txt").write_text(text)
    (d / "num" / "fam__Doc_A.txt").write_text(num)
    g = Path(tmp) / "golden.json"
    g.write_text(json.dumps(golden))
    return g, d


def test_golden_good_passes(tmp):
    g, d = vg_setup(tmp)
    rc, out = run(PY, HERE / "verify_golden.py", g, d)
    assert rc == 0 and "quotes 2/2, refs 3/3" in out, out  # 2 non-empty quotes, 3 ref strings; excluded record B is not checked


def test_golden_quote_mutation_rejected(tmp):
    g, d = vg_setup(tmp, text=TEXT.replace("paid in cash", "paid in cach"))  # one character changed in the source
    rc, out = run(PY, HERE / "verify_golden.py", g, d)
    assert rc == 1 and "QUOTE MISS" in out and "quotes 1/2" in out, out


def test_golden_ref_mutation_rejected(tmp):
    bad = copy.deepcopy(GOLDEN)
    bad[0]["answers"]["Q1"]["section_ref"] = "Section 2.9(b)"  # no 2.9 in the number map
    g, d = vg_setup(tmp, golden=bad)
    rc, out = run(PY, HERE / "verify_golden.py", g, d)
    assert rc == 1 and "REF MISS" in out and "Section 2.9(b)" in out, out
    bad[0]["answers"]["Q1"]["section_ref"] = "Section 2.7(c)"  # 2.7 exists, sub-clause (c) does not
    g, d = vg_setup(Path(tmp) / "b", golden=bad) if Path(tmp, "b").mkdir() is None else None
    rc, out = run(PY, HERE / "verify_golden.py", g, d)
    assert rc == 1 and "REF MISS" in out, out


def test_golden_missing_text_or_map_is_a_failure(tmp):
    g, d = vg_setup(tmp)
    (d / "fam__Doc_A.docx.txt").unlink()
    rc, out = run(PY, HERE / "verify_golden.py", g, d)
    assert rc == 1 and "MISSING TEXT" in out, out
    g2, d2 = vg_setup(Path(tmp) / "m") if Path(tmp, "m").mkdir() is None else None
    (d2 / "num" / "fam__Doc_A.txt").unlink()
    rc, out = run(PY, HERE / "verify_golden.py", g2, d2)
    assert rc == 1 and "MISSING NUMBER MAP" in out, out


def test_golden_checking_nothing_is_not_a_pass(tmp):
    g, d = vg_setup(tmp, golden=[{"id": "A", "file": "fam/Doc A.docx", "source_text_path": "x/fam__Doc_A.docx.txt", "answers": {}}])
    rc, out = run(PY, HERE / "verify_golden.py", g, d)
    assert rc == 1 and "NOTHING CHECKED" in out, out


# ------------------------------------------------------------------ intake / pdf / triage (offline parts)
def test_intake_probe_counts_and_zero_coverage(tmp):
    for n, body in (("a", "The Independent Accountant decides."), ("b", "no adjustment here"), ("c", "independent accountant; Independent Accountant")):
        (Path(tmp) / f"{n}.txt").write_text(body)
    rc, out = run(PY, HERE / "intake.py", tmp, "--no-jev", "--probe", "Independent Accountant,Working Capital")
    assert rc == 0, out
    assert "'Independent Accountant': 2 of 3 files (3 hits)" in out, out
    assert "'Working Capital': 0 of 3 files (0 hits)   <-- ZERO COVERAGE" in out, out


def test_intake_without_jev_says_unmeasured_and_exits_2(tmp):
    (Path(tmp) / "a.txt").write_text("hello world " * 30)
    rc, out = run(PY, HERE / "intake.py", tmp, env=ENV_NO_JEV)
    assert rc == 2 and "unmeasured (jev unavailable)" in out, (rc, out)


def test_intake_misfiled_needs_folder_majority(tmp):
    import intake
    mk = lambda folder, cls: {"folder": folder, "path": f"{folder}/{cls}", "jev": {"cls": cls, "p": 1.0}}
    recs = [mk("f", "apa")] * 3 + [mk("f", "llc")] + [mk("g", "apa"), mk("g", "llc")]
    got = [(r["jev"]["cls"], cls, n, tot) for r, cls, n, tot in intake.misfiled(recs)]
    assert got == [("llc", "apa", 3, 4)], got  # folder g has only 2 files: no verdict, no accusation


PDF_OBJS = None


def make_pdf(path, pages):
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", None]
    kids = []
    for i, txt in enumerate(pages):
        pn, cn = 3 + 2 * i, 4 + 2 * i
        kids.append(f"{pn} 0 R")
        stream = f"BT /F1 24 Tf 72 700 Td ({txt}) Tj ET".encode()
        objs += [f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {cn} 0 R /Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> >>".encode(),
                 b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream"]
    objs[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(pages)} >>".encode()
    out, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode() + b"".join(f"{o:010d} 00000 n \n".encode() for o in offs)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    Path(path).write_bytes(out)


def test_pdf_pages_renders_every_page_and_rejects_bad_range(tmp):
    pdf = Path(tmp) / "t.pdf"
    make_pdf(pdf, ["Earnout Chart 82 percent", "Financial Provisions"])
    rc, out = run(HERE / "pdf-pages.sh", pdf, 1, 2, Path(tmp) / "o")
    assert rc == 0 and "rendered 2/2 pages at 110dpi" in out and "page 002  Financial Provisions" in out, out
    assert (Path(tmp) / "o" / "page-001.png").stat().st_size > 0 and (Path(tmp) / "o" / "page-002.txt").is_file()
    rc, out = run(HERE / "pdf-pages.sh", pdf, 1, 3, Path(tmp) / "o2")  # 3 > Pages
    assert rc == 2 and "invalid for a 2-page PDF" in out, out
    rc, out = run(HERE / "pdf-pages.sh", Path(tmp) / "missing.pdf", 1, 1, Path(tmp) / "o3")
    assert rc == 2, out


def test_triage_facts_and_no_text_is_never_guessed(tmp):
    f = tri.facts("Earnout\nSubset: All deals\nNo 82%   Yes 18%\n")
    assert f["has_subset"] and f["percent_tokens"] == 2 and f["digit_density"] > 0.1, f
    assert tri.facts("Contents ........ 5\nDefinitions ..... 9\n")["toc_leaders"] == 2
    assert tri.decide(tri.facts(""), 0.99) == ("REVIEW", "no text layer: render and look")
    assert tri.decide(tri.facts("x" * 100), 0.95)[0] == "READ"
    assert tri.decide(tri.facts("x" * 100), 0.50)[0] == "REVIEW"
    assert tri.decide(tri.facts("x" * 100), 0.10)[0] == "SKIP"
    assert tri.ranges([1, 2, 3, 7, 9, 10]) == "1-3,7,9-10"


def test_triage_without_jev_is_unmeasured_exit_2(tmp):
    pdf = Path(tmp) / "t.pdf"
    make_pdf(pdf, ["Earnout Chart 82 percent 18 percent and more words here to pass the text floor"])
    rc, out = run(PY, HERE / "pdf_chart_triage.py", pdf, env=ENV_NO_JEV)
    assert rc == 2 and "unmeasured (jev unavailable)" in out, (rc, out)


def main():
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        with tempfile.TemporaryDirectory() as tmp:
            try:
                fn(tmp)
                print(f"ok    {name}")
            except Exception as e:  # AssertionError or a crash: both are red
                failed += 1
                print(f"FAIL  {name}: {type(e).__name__}: {str(e)[:400]}")
    print(f"\n{len(tests) - failed} passed, {failed} failed of {len(tests)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
