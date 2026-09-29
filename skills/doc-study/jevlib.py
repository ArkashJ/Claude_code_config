"""Shared Jev (TypeSafe System One) helper for the doc-study kit. Reuses ~/.claude/skills/qa/hunt.py's
client (MODEL, api_key, ask) -- one client, one pinned model.

INCIDENT (Spot BEN-175, 2026-09-29): 1 of 28 "agreements" was an LLC operating agreement, found only by reading;
the Jev Choice classifies it 'operating agreement' at p=1.00 vs 5 of 6 in its folder, and the two client spec files
had swapped names -- so Jev judges CONTENT. When Jev is down the answer is "unmeasured", never a guess.

Rule (owner, 2026-09-29): Jev only makes the semantic call code cannot. If the key or API is
unavailable the step says "unmeasured (jev unavailable)" and exits non-zero -- it never guesses.
Bands: no < 0.30 <= review <= 0.70 < yes.
"""
import concurrent.futures as cf
import os
import sys

UNMEASURED = "unmeasured (jev unavailable)"
EXIT_UNMEASURED = 2


class JevUnavailable(Exception):
    pass


def _client():
    try:
        sys.path.insert(0, os.path.expanduser("~/.claude/skills/qa"))
        from hunt import MODEL, api_key, ask
    except Exception as e:  # hunt.py missing/broken
        raise JevUnavailable(f"cannot import qa/hunt.py: {e}")
    try:
        key = api_key()
    except SystemExit:  # hunt.api_key() sys.exit()s when TYPESAFE_API_KEY / TYPESAFE_JEV_KEY are unset
        raise JevUnavailable("TYPESAFE_API_KEY / TYPESAFE_JEV_KEY not set")
    return MODEL, key, ask


def ask_safe(state, questions):
    """-> (model, answers). Any transport/HTTP failure becomes JevUnavailable (never a guess)."""
    model, key, ask = _client()
    try:
        r = ask(key, state, questions)
        return r.get("model", model), r["answers"]
    except Exception as e:
        raise JevUnavailable(f"{type(e).__name__}: {str(e)[:160]}")


def band(p, lo=0.30, hi=0.70):
    return "no" if p < lo else "yes" if p > hi else "review"


def pmap(fn, items, workers=6):  # 6 in flight: the shared key rate-limits above ~8
    with cf.ThreadPoolExecutor(workers) as ex:
        return list(ex.map(fn, items))
