#!/usr/bin/env python3
"""Validate chart records read off rendered PDF pages. Exit 1 on any violation. No Jev: this is arithmetic.

INCIDENT (Spot BEN-175, 2026-09-29): the 134-page ABA study keeps its data in CHARTS, so text extraction was
useless and 152 chart readings were made by eyeballing rendered pages (pdftoppm -r 110). Readings are the
one place an LLM's eyes can silently transpose a number; 51 of the 152 carried an ambiguity 'note'. This
checker is the cheap mechanical net: a single-select chart must sum to ~100, and the headline `market`
must be the tallest bar. Measured on the real file (docs/plans/topic-issues-list/aba-2025-charts.json):
37 violations in 30 of 152 records -- 23 sum!=100 (two-panel non-RWI/RWI charts sum to ~200; partial-segment
charts sum to 21-89; one is deal COUNTS not percent), 8 market labels that disagree with the tallest bar
(mostly the COMPLEMENT, e.g. 'Not included (~79%)' when only 'Includes' = 21 is a bar), 5 empty-outcome
pages lacking market 'n/a' + note (statistics live in `quant`), 1 non-numeric outcomes (strings '5.55/4.90/..').
The file was NOT edited; the fix loop is re-read -> correct or add a reasoned `waive`.

Record: {page, topic, question, subset, outcomes{label: number}, multi_select, market, note?, waive?}
  required: page (int>=1), topic/question/subset (non-empty str), outcomes (dict of numbers), multi_select (bool),
            market (str).  Extra keys are ignored (section, trend, footnotes, quant ...).
  1. single-select outcomes sum to 100 +/- 3 (multi_select charts are exempt: they legitimately exceed 100).
  2. `market` names the argmax outcome. `market` is free text ("Silent (69%)"), so it passes if the argmax
     label's words appear in it (or it appears in the label), or if a percent figure in it equals the max value.
     Ties: any tied label passes.
  3. empty outcomes (a divider / clause-only page) are allowed only with market "n/a" AND a note.
  Waiver, after a human re-read: {"waive": {"sum": "reason", "market": "reason"}}. A waiver with an empty
  reason is itself a violation. Waivers are reported, never silent.
Records with a 'note' are printed as the re-read list (informational; not violations by themselves).

usage: check_chart_json.py FILE.json      (a list of records, or {"charts": [...]} / {"records": [...]})
"""
import json, re, sys

REQ_STR = ("topic", "question", "subset", "market")


def toks(s):
    return re.findall(r"[a-z0-9]+", str(s).lower())


def has_seq(hay, needle):
    return bool(needle) and any(hay[i:i + len(needle)] == needle for i in range(len(hay) - len(needle) + 1))


def market_ok(market, outcomes):
    """True if `market` is consistent with the argmax of outcomes. The label must match (whole label inside the
    market text, or the market's leading phrase is a PREFIX of the label -- never a suffix: 'Earnout' is not
    'No earnout'); if the market quotes percents, one must equal the max value (+/-1)."""
    mx = max(outcomes.values())
    tops = [k for k, v in outcomes.items() if v == mx]
    m = toks(market)
    head = toks(re.split(r"[(,;]| -- ", str(market))[0])
    pcts = [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)\s*%", str(market))]
    for lab in tops:
        lt = toks(re.sub(r"^\[[^\]]*\]\s*", "", lab))  # "[Payer] Buyer Only" -> "buyer only"
        if has_seq(m, lt) or (head and lt[:len(head)] == head):
            return not pcts or any(abs(x - mx) <= 1 for x in pcts)  # any: the label itself may hold '0.5%'
    return any(abs(x - mx) <= 0.5 for x in pcts)  # label reworded: accept only if the figure is the tallest bar


def check(rec):
    """-> list of (code, message). code in {'schema','sum','market','waiver'}."""
    v = []
    if not isinstance(rec.get("page"), int) or isinstance(rec.get("page"), bool) or rec["page"] < 1:
        v.append(("schema", f"page must be an int >= 1, got {rec.get('page')!r}"))
    for k in REQ_STR:
        if not isinstance(rec.get(k), str) or not rec[k].strip():
            v.append(("schema", f"{k} missing or empty"))
    if not isinstance(rec.get("multi_select"), bool):
        v.append(("schema", f"multi_select must be a bool, got {rec.get('multi_select')!r}"))
    o = rec.get("outcomes")
    if not isinstance(o, dict):
        return v + [("schema", "outcomes must be an object {label: number}")]
    bad = {k: x for k, x in o.items() if isinstance(x, bool) or not isinstance(x, (int, float))}
    if bad:
        return v + [("schema", f"non-numeric outcomes: {bad}")]
    if v:  # do not derive sum/market checks from a record that failed the schema
        return v
    waive = rec.get("waive") if isinstance(rec.get("waive"), dict) else {}
    found = []
    if not o:
        if str(rec["market"]).strip().lower() != "n/a" or not str(rec.get("note") or "").strip():
            found.append(("market", "empty outcomes need market 'n/a' and a note (clause-only page?)"))
    else:
        s = sum(o.values())
        if rec["multi_select"] is False and abs(s - 100) > 3:
            found.append(("sum", f"single-select outcomes sum to {s:g}, not 100+/-3"))
        if not market_ok(rec["market"], o):
            mx = max(o.values())
            found.append(("market", f"market {rec['market']!r} does not match argmax {[k for k, x in o.items() if x == mx]} = {mx:g}"))
    for code, msg in found:
        reason = waive.get(code)
        if isinstance(reason, str) and reason.strip():
            v.append(("waiver", f"{code} waived: {reason.strip()}"))
        else:
            v.append((code, msg + (" [waiver has no reason]" if code in waive else "")))
    return v


def load(path):
    d = json.load(open(path))
    if isinstance(d, dict):
        d = d.get("charts", d.get("records"))
    if not isinstance(d, list):
        sys.exit(f"{path}: expected a list of records or an object with 'charts'/'records'")
    return d


def main(argv):
    if len(argv) != 2 or argv[1] in ("-h", "--help"):
        # `--help` used to be opened as a filename and crash with a traceback (2026-09-29).
        print(__doc__.split("usage:")[1].strip())
        return 0 if len(argv) == 2 else 2
    recs = load(argv[1])
    if not recs:
        print("0 records: nothing was checked")
        return 1
    viol = waived = 0
    for i, r in enumerate(recs):
        if not isinstance(r, dict):
            print(f"VIOLATION [{i}] not an object")
            viol += 1
            continue
        for code, msg in check(r):
            tag = "WAIVED   " if code == "waiver" else "VIOLATION"
            viol += code != "waiver"
            waived += code == "waiver"
            print(f"{tag} [{i}] p.{r.get('page')} {str(r.get('topic'))[:50]!r}: {msg}")
    noted = [(i, r) for i, r in enumerate(recs) if isinstance(r, dict) and str(r.get("note") or "").strip()]
    print(f"\nRE-READ list: {len(noted)} of {len(recs)} records carry a note")
    for i, r in noted:
        print(f"  [{i}] p.{r.get('page')} {str(r.get('topic'))[:45]!r}: {str(r['note'])[:110]}")
    print(f"\nrecords {len(recs)}, violations {viol}, waived {waived}, with-note {len(noted)}")
    return 1 if viol else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
