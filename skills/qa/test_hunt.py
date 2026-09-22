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
# repo A 2026-09-22: body scan ran past `useQueryClient()` into the next line's useMutation,
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
t, why = review.tier(pr, calm, "not_run", None)
assert t == "blocked" and "never ran" in why, why
print("not_run ok")

# repo B 2026-09-22: 96% of reads went through the repo's own useApiQuery; matching TanStack
# names only judged 7 of ~190 queries. Wrappers must be found, their own definition and inner
# call skipped, comment mentions skipped, and `verify-ignore` sign-offs honoured.
w = pathlib.Path(tempfile.mkdtemp()); (w / "src").mkdir()
(w / "src/hooks.ts").write_text('''export function useApiQuery<P extends X, D = R<P>>(
  key: QueryKey,
  path: P,
) {
  return useQuery<R<P>, E, D, QueryKey>({ queryKey: key, queryFn: () => get(path) })
}
export const useQueuedWrite = (f) => useMutation({ mutationFn: f })
/** Call useApiQuery(key, fn) from a component. */
''')
(w / "src/page.tsx").write_text('''export function Page() {
  const a = useApiQuery(["x", id], () => get(id))
  // verify-ignore: sync-risk (list refreshes on navigation)
  const s = useQueuedWrite(save)
  return null
}
''')
found = list(hunt.surfaces(str(w), "src", [{"pattern": r"verify-ignore:\s*sync-risk", "checks": ["mutation_no_cache_update"]}]))
got = sorted((x["file"], x["hook"], x["kind"]) for x in found)
assert got == [("src/page.tsx", "useApiQuery", "query"), ("src/page.tsx", "useQueuedWrite", "mutation")], f"wrapper surfaces wrong: {got}"
mut = next(x for x in found if x["kind"] == "mutation")
assert mut["waived"] == ["mutation_no_cache_update"], mut["waived"]
assert hunt.leads({"answers": {"writes_shown_data": .9}, "facts": {}, "waived": mut["waived"]}) == []
print("wrappers ok")
d2 = pathlib.Path(tempfile.mkdtemp()); (d2 / "src").mkdir()
(d2 / "src/hooks.ts").write_text('''export function useMis(slug, year) {
  return useQuery({ queryKey: keys.mis(slug, year), queryFn: () => get(slug, year, authority) })
}
''')
(d2 / "src/page.tsx").write_text('export function P() { const m = useMis(slug, 2026); return null }\n')
dom = sorted((x["file"], x["hook"]) for x in hunt.surfaces(str(d2), "src"))
assert dom == [("src/hooks.ts", "useQuery")], f"domain hook must be judged at its inner useQuery, not its callers: {dom}"
print("domain hooks ok")
assert not hunt.passes_through("({ queryKey: id ? usersKeys.detail(id) : usersKeys.detail('_none'), queryFn: () => getUser(id) })", "id"), "repo A useUser is a domain hook, not a wrapper"
assert hunt.passes_through("({ networkMode: 'offlineFirst', mutationFn: async (v) => { const r = await options.write(v); return r } })", "options")
assert hunt.passes_through("({ queryKey: key, queryFn: () => getApi(path) })", "key")
print("passthrough ok")

# repo B 2026-09-22: pass-through query data can't be a strong draft_clobber lead (structural sharing);
# a dependency rebuilt in render (contact-workspace.tsx:837 inline `{mode, contact}`) can.
ctx = "const input = { mode, contact }\nconst user = query.data\nconst rows = items.map(f)\n"
assert hunt.dep_kinds("useEffect(() => { setDraft(input) }, [input])", ctx) == {"input": "rebuilt"}
assert hunt.dep_kinds("useEffect(() => { setDraft(user) }, [user, open])", ctx) == {"user": "passthrough", "open": "passthrough"}
assert hunt.dep_kinds("useEffect(() => { f() }, [rows])", ctx) == {"rows": "rebuilt"}
hi = {"overwrites_user_draft": .9, "reruns_on_refetch": .9}
assert hunt.leads({"answers": hi, "facts": {"dependency_kinds": {"user": "passthrough"}}}) == [("draft_clobber", 0.69)]
assert hunt.leads({"answers": hi, "facts": {"dependency_kinds": {"input": "rebuilt"}}}) == [("draft_clobber", 0.9)]
print("dep kinds ok")
