"""python3 ~/.claude/skills/qa/test_hunt.py — offline checks for hunt.py's code-side facts."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import hunt

src = '''const a = () => qc.invalidateQueries({queryKey:["x"]})
function useInv() { const qc = useQueryClient(); return () => qc.invalidateQueries() }
const refresh = useInv()
const qc2 = useQueryClient()
const b = useCallback(() => { qc.setQueryData(k, v) }, [])
const c = () => { doThing() }
const d = useQuery({ queryKey: k })
function useSave() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: save, onSuccess: () => qc.invalidateQueries() })
}'''
# pcs_frontend 2026-09-22: body scan ran past `useQueryClient()` into the next line's useMutation,
# so `qc` became a "helper" and every mutation mentioning qc counted as refreshing the cache.
helpers = hunt.cache_helpers(src)
assert helpers == {"a", "useInv", "refresh", "b", "useSave"}, f"cache helper set drifted: {helpers} (qc must never be a helper)"
assert hunt.updates_cache("useMutation({ onSuccess: refresh.users })", helpers)
assert not hunt.updates_cache("useMutation({ onSuccess: () => close() })", helpers)

text = "useEffect(() => { f(')') /* ) */ }, [a])\nnext()"
assert text[: hunt.match_paren(text, text.index("("))].endswith("[a])")

assert hunt.leads({"answers": {"overwrites_user_draft": 0.9, "reruns_on_refetch": 0.2}, "facts": {}}) == [("draft_clobber", 0.2)]
assert hunt.leads({"answers": {"writes_shown_data": 0.9}, "facts": {"updates_query_cache": True}}) == []
print("ok")

import review
pr = {"additions": 50, "deletions": 10, "mergeable": "MERGEABLE"}
calm = {"touches_auth": .1, "changes_shared": .1, "data_write": .1, "tests_cover": .9, "risk": {"score": .5, "confidence": .9}}
assert review.tier(pr, calm, "passing", None)[0] == "skim"
assert review.tier(pr, {**calm, "risk": {"score": .5, "confidence": .3}}, "passing", None)[0] == "review"  # unsure → up
assert review.tier(pr, {**calm, "touches_auth": .9}, "passing", None)[0] == "deep"
assert review.tier({**pr, "additions": 5000}, calm, "passing", None)[0] == "deep"
t, why = review.tier(pr, {**calm, "touches_auth": .9}, "failing", None)
assert t == "blocked" and "then deep" in why, why
assert review.tier(pr, calm, "passing", 1525) == ("covered", "contained in #1525")
print("review ok")

import docs, json as _j, tempfile, pathlib
d = pathlib.Path(tempfile.mkdtemp())
(d / "a.py").write_text("def pay(): pass\n")
ev = docs.evidence(str(d), {"code_dirs": ["."]}, "The `a.py` file defines pay; see `missing/x.py` for more words here")
assert "def pay" in ev["`a.py`"] and ev["missing/x.py"] == "(file does not exist)", ev
assert "client_source" in docs.HARD_KEEP and "haiku" in docs.PLAN_MODEL["criteria"]
print("docs ok")

# SKILL.md's check table drifted from GENERIC on 2026-09-22 (listed derived_state/event_in_effect after
# they were deleted for being 0/9 and 2/9 real). The table must name exactly the lead names hunt emits.
import re as _re
table = {m.group(1): {x.strip().split(" ")[0] for x in m.group(2).split(",")}
         for m in _re.finditer(r"^\| (effect|query|mutation) \| (.+?) \|$", (pathlib.Path(__file__).parent / "SKILL.md").read_text(), _re.M)}
for kind, qs in hunt.GENERIC.items():
    emitted = {k for k, _ in hunt.leads({"answers": {q: 0.9 for q in qs}, "facts": {}})}
    assert table.get(kind) == emitted, f"SKILL.md check table for {kind} says {table.get(kind)}, hunt.py emits {emitted}: update the table"
print("skill table ok")
assert not hunt.updates_cache("useMutation({ mutationFn: f }) // invalidateQueries happens in the caller", set())
assert not hunt.updates_cache("useMutation({ /* setQueryData later */ mutationFn: f })", set())
assert hunt.updates_cache("useMutation({ onSuccess: () => qc.invalidateQueries({ queryKey: ['https://x'] }) })", set())
print("comments ok")
