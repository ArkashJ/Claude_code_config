#!/usr/bin/env bash
# Proves the STATIC analysers fire. Builds a throwaway repo carrying one planted
# instance of each class, then asserts inventory.mjs and classify.mjs find them.
# Needs nothing but node -- no browser, no install.
#
#   bash ~/.claude/skills/frontend-verify/selftest-static.sh
set -uo pipefail

SKILL="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$TMP/app/contacts" "$TMP/app/dashboard" "$TMP/src/api" "$TMP/src/store"
cat > "$TMP/tsconfig.json" <<'JSON'
{ "compilerOptions": { "baseUrl": ".", "paths": { "@/*": ["./*"] } } }
JSON

cat > "$TMP/src/api/contacts.ts" <<'TS'
import axios from 'axios'
export async function listContacts() { return axios.get('/api/contacts') }
export async function createContact(body: unknown) { return axios.post('/api/contacts', body) }
TS

# PLANTED: a mutation that writes /api/contacts and invalidates nothing, while
# two routes render that same resource.  -> syncRisks >= 1
cat > "$TMP/src/api/hooks.ts" <<'TS'
import { useMutation, useQuery } from '@tanstack/react-query'
import { createContact, listContacts } from '@/src/api/contacts'
export function useContacts() {
  return useQuery({ queryKey: ['contacts'], queryFn: listContacts })
}
export function useCreateContact() {
  return useMutation({ mutationFn: createContact })
}
TS

# PLANTED: missing-empty-state, index-as-list-key, unread-query-error
cat > "$TMP/app/contacts/page.tsx" <<'TSX'
'use client'
import { useContacts } from '@/src/api/hooks'
export default function ContactsPage() {
  const { data } = useContacts()
  return <ul>{(data ?? []).map((c: any, index: number) => <li key={index}>{c.name}</li>)}</ul>
}
TSX

# PLANTED: runtime-env-in-client-code, submit-without-pending-guard
cat > "$TMP/app/dashboard/page.tsx" <<'TSX'
'use client'
import { useContacts, useCreateContact } from '@/src/api/hooks'
export default function Dashboard() {
  const { data } = useContacts()
  const create = useCreateContact()
  const url = process.env.API_BASE_URL
  return (
    <form onSubmit={() => create.mutate({})}>
      <span>{url}</span><span>{(data ?? []).length}</span>
      <button type="submit">Save</button>
    </form>
  )
}
TSX

# PLANTED: server-state-in-client-store
cat > "$TMP/src/store/contacts.ts" <<'TS'
import { create } from 'zustand'
export const useContactStore = create((set) => ({
  items: [],
  load: async () => { const res = await fetch('/api/contacts'); set({ items: await res.json() }) },
}))
TS

fail=0
INV="$TMP/inventory.json"
node "$SKILL/bin/inventory.mjs" "$TMP" --stdout > "$INV" || { echo "FAIL: inventory.mjs crashed"; exit 1; }
node "$SKILL/bin/classify.mjs" "$TMP" --json > "$TMP/classify.json" || true

echo "--- inventory"
node -e '
const j = require(process.argv[1]); let bad = 0;
const check = (label, ok, got) => { console.log((ok ? "  ok    " : "  MISS  ") + label + "  (" + got + ")"); if (!ok) bad = 1; };
check("routes found",           j.counts.routes >= 2,        j.counts.routes);
check("queries found",          j.counts.queries >= 1,       j.counts.queries);
check("mutations found",        j.counts.mutations >= 1,     j.counts.mutations);
check("resource matrix built",  Object.keys(j.resourceMatrix).includes("contacts"), Object.keys(j.resourceMatrix).join(","));
check("sync risk detected",     j.syncRisks.length >= 1,     j.syncRisks.length);
check("blast radius resolved",  (j.syncRisks[0] && j.syncRisks[0].staleRoutes || []).length >= 2,
      JSON.stringify((j.syncRisks[0] || {}).staleRoutes));
process.exit(bad);
' "$INV" || fail=1

echo "--- classifier"
for rule in missing-empty-state index-as-list-key runtime-env-in-client-code server-state-in-client-store submit-without-pending-guard; do
  if grep -q "\"rule\": \"$rule\"" "$TMP/classify.json"; then echo "  ok    $rule"
  else echo "  MISS  $rule  <- planted, rule did not fire"; fail=1; fi
done

echo
if [ "$fail" -eq 0 ]; then echo "STATIC SELFTEST PASS"; else echo "STATIC SELFTEST FAIL"; fi
exit "$fail"
