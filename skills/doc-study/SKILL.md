---
name: doc-study
description: Study a corpus of client documents (Word/PDF agreements, specs, chart-heavy reports) and produce a golden answer key you can trust. Use when asked to read/compare/extract from many documents, when a PDF keeps its data in charts, or when an answer key or benchmark must be machine-verified. Ships intake (format/redline/numbering/probe/Jev classification), page rendering + chart-page triage, chart-JSON validation, and golden-key verification. Cross-repo, user-level.
---

# doc-study

Built from the Spot BEN-175 study on 2026-09-29: 28 client agreements (5 families, 4 redlined), one
134-page chart-only ABA report, two client spec files. Code computes and verifies; Jev only makes the
semantic call code cannot (document type, "is this a data page"); agents read images and write the key.

Location: `~/.claude/skills/doc-study/`. Self-test: `python3 ~/.claude/skills/doc-study/test_doc_study.py`
(19 tests, offline; prints `N passed, 0 failed`). Jev key: env `TYPESAFE_API_KEY` or `TYPESAFE_JEV_KEY`.
No key/API -> the Jev step prints `unmeasured (jev unavailable)` and exits 2. It never guesses.

## When to use
- "Read all of these" / "how do the deals differ" / "what does the study say about X" over more than ~5 documents.
- A PDF whose numbers live in charts (`pdftotext` gives labels but not bars).
- Any golden key / benchmark / answer set that will later grade an extractor.

## The method (order matters)
1. **Intake** -- `intake.py <dirs/files> --probe "Term A,Term B" --text-dir /tmp/txt --json /tmp/intake.json`
   Read every file once in code before reasoning. Look at: pages/words per file, REDLINE counts, `auto-numbered`
   warnings, `MISFILED`, `REVIEW`, and every probe's `N of M files` (a `ZERO COVERAGE` line means the client's
   headline example is not in the corpus: tell them, do not invent a test for it).
2. **Triage** (chart PDFs) -- `pdf_chart_triage.py study.pdf --json /tmp/tri.json` -> READ / REVIEW / SKIP page
   ranges. Only READ and REVIEW pages go to readers.
3. **Render + read images with parallel agents** -- `pdf-pages.sh study.pdf 11 24 /tmp/pages` per range (PNG +
   layout text + title map). One agent per ~12-20 pages, sonnet or haiku, each writing records
   `{page, topic, question, subset, outcomes{label: pct}, multi_select, market, note?}`. Instruct: put every
   doubt in `note`; `outcomes` are the values printed on the chart, never computed.
4. **Validate** -- `check_chart_json.py charts.json` (exit 1 on any violation). Then **re-read every flagged
   record and every record with a `note`** from the page image. Fix the value, or add
   `"waive": {"sum": "two panels, each sums to 100"}` with a real reason. Never edit the checker to pass.
5. **Golden key with verification** -- write the answers with `section_ref` + `verbatim_quote`, then
   `verify_golden.py golden.json /tmp/txt` -> must print `quotes N/N, refs M/M` and exit 0. A key that is not
   machine-verified is one more LLM opinion.

## Commands
| Script | What it does | Exit |
|---|---|---|
| `intake.py PATH... [--json F] [--text-dir D] [--classes "a,b"] [--probe "x,y"] [--track-changes accept\|all\|reject] [--no-jev]` | table + verdict; writes `D/<folder>__<name>.txt` and `D/num/*.txt` (recovered numbering) | 0 ok, 1 unreadable file, 2 jev unavailable |
| `pdf-pages.sh PDF FIRST LAST OUTDIR [DPI=110]` | `page-NNN.png` + `page-NNN.txt`, prints `page NNN  <title>` | 0 only if every page rendered |
| `pdf_chart_triage.py PDF [--pages a-b] [--json F]` | READ/SKIP/REVIEW per page with p | 0, 2 jev unavailable |
| `check_chart_json.py FILE` | schema, sum 100+/-3 (single-select), market = tallest bar, re-read list | 1 on any violation |
| `verify_golden.py GOLDEN TEXT_DIR` | quotes are substrings, refs exist | 1 on any miss or 0 checked |
| `docx_numbering.py FILE.docx` | real section numbers from numbering XML | - |

Jev bands everywhere: `no < 0.30 <= review <= 0.70 < yes`. Classification: top probability < 0.70 -> `REVIEW`.
Jev is for tooling only; never put it in product code.

## The six incidents (2026-09-29) and which step catches each
1. **Two spec files had names swapped vs the client's email** (`Spot.docx` was the detailed spec). Names lie.
   Intake prints words/pages per file and classifies by content, never by filename. Compare those to what the
   sender said each file is BEFORE you cite either. (Not automated: the email claim is not machine-readable.)
2. **1 of 28 "agreements" was an LLC operating agreement** (`form3 ... version 9.doc`), found only by reading.
   Intake: `MISFILED ... reads as 'operating agreement' (p=1.0) but 5 of 6 files in its folder are 'purchase agreement'`.
   Needs >=3 classified files in the folder and a strict majority.
3. **pandoc renders Word auto-numbering as roman-numeral list items** so "Section 2.7" is not in the text; all 29
   docx files in the intake were auto-numbered. Intake warns `auto-numbered(N)` and `--text-dir` writes `num/` files rebuilt from
   `numbering.xml`; `verify_golden.py` checks refs against them.
4. **"Working Capital" appeared in 0 of 28 agreements** -- the client's headline example had no coverage.
   `--probe "Working Capital"` prints `0 of 30 files (0 hits)   <-- ZERO COVERAGE`.
5. **The 134-page ABA study keeps its data in charts.** Text extraction was useless; pages were rendered
   (`pdftoppm -r 110`) and read as images: 152 readings, 51 carrying an ambiguity note. Triage measured on the real
   PDF: READ 104 / REVIEW 7 / SKIP 23 of 134, and all 101 pages that hold a chart outcome landed in READ (0 data
   pages skipped). `check_chart_json.py` on the real file: 37 violations in 30 of 152 records (23 sum!=100, 8 market
   vs tallest bar, 5 empty-page, 1 non-numeric). Expect two-panel charts (non-RWI + RWI = ~200): waive with a reason.
6. **272 quotes + 332 section refs were machine-verified as exact substrings / existing sections** -- the only reason
   the golden key could be trusted. `verify_golden.py` on `docs/plans/topic-issues-list/golden/pcppa_golden.json`
   reproduces `quotes 272/272, refs 332/332`.

## Gotchas
- Quotes come from `--track-changes=accept` (the "final" view; the default). `all` leaves deleted text inline
  (165,261 vs 149,487 chars on one redlined agreement). Tracked changes are still COUNTED so a redline is flagged.
- `.doc` is read with macOS `textutil` (no numbering, no redline counts).
- Quote matching is whitespace-normalised, NOT curly-quote-folded. Copy quotes from the extracted text.
- `verify_golden.py` is fail-closed: missing text/number map, unknown ref form, or 0 checks = exit 1.
- Golden-key section refs use `Section X.Y(a)`, `Art. IV`, ranges `(a)-(c)`; other forms need `ref_ok` extending.
- Bump `--probe` terms to the client's own examples; a term at 0 hits is a finding, not noise.
- Keep <= 6-8 Jev requests in flight (the scripts use 6).
- Never run `cd X && cmd` here (the global hook blocks it); use absolute paths.
