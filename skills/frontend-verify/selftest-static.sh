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

# PLANTED: a GENERIC wrapper primitive (key + fn as parameters) plus a concrete
# hook built on it. Repos wrap the data layer this way, and matching only the bare
# library names reports ZERO queries on such a codebase -- so syncRisks comes back
# empty because nothing was found, not because the app is clean.
mkdir -p "$TMP/src/lib" "$TMP/app/invoices"
cat > "$TMP/src/lib/api-hooks.ts" <<'TS'
import { useMutation, useQuery } from '@tanstack/react-query'
export function useApiQuery(key: unknown[], fn: () => Promise<unknown>) {
  return useQuery({ queryKey: key, queryFn: fn })
}
export function useQueuedWrite(key: unknown[], fn: (b: unknown) => Promise<unknown>) {
  return useMutation({ mutationKey: key, mutationFn: fn })
}
TS
cat > "$TMP/app/invoices/page.tsx" <<'TSX'
'use client'
import { useApiQuery, useQueuedWrite } from '@/src/lib/api-hooks'
import { createInvoice, listInvoices } from '@/src/api/invoices'
export default function InvoicesPage() {
  const { data, isError } = useApiQuery(['invoices'], listInvoices)
  const add = useQueuedWrite(['invoices'], createInvoice)
  if (isError) return <p>failed</p>
  if (!(data as unknown[])?.length) return <p>No invoices yet</p>
  return <button onClick={() => add.mutate({})}>Add</button>
}
TSX
mkdir -p "$TMP/src/api"
cat > "$TMP/src/api/invoices.ts" <<'TS'
import axios from 'axios'
export async function listInvoices() { return axios.get('/api/invoices') }
export async function createInvoice(b: unknown) { return axios.post('/api/invoices', b) }
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
check("wrapper query counted",  j.routes.some((r) => r.queries.some((x) => x.via === "useApiQuery")),
      j.routes.flatMap((r) => r.queries).filter((x) => x.via).map((x) => x.via).join(",") || "none");
check("wrapper mutation counted", j.routes.some((r) => r.mutations.some((x) => x.via === "useQueuedWrite")),
      j.routes.flatMap((r) => r.mutations).filter((x) => x.via).map((x) => x.via).join(",") || "none");
check("blast radius resolved",  (j.syncRisks[0] && j.syncRisks[0].staleRoutes || []).length >= 2,
      JSON.stringify((j.syncRisks[0] || {}).staleRoutes));
process.exit(bad);
' "$INV" || fail=1

echo "--- classifier"
for rule in missing-empty-state index-as-list-key runtime-env-in-client-code server-state-in-client-store submit-without-pending-guard; do
  if grep -q "\"rule\": \"$rule\"" "$TMP/classify.json"; then echo "  ok    $rule"
  else echo "  MISS  $rule  <- planted, rule did not fire"; fail=1; fi
done

# ---------------------------------------------------------------------------
# MONOREPO regression. Reproduces the exact shape that reported modules:1 and
# zero queries on a real app: no tsconfig at the repo root, paths declared in
# apps/web/tsconfig.json, the route three hops from its data, and the wrapper
# typed with NESTED generics between the identifier and the paren.
MONO="$(mktemp -d)"
trap 'rm -rf "$TMP" "$MONO"' EXIT
mkdir -p "$MONO/apps/web/src/app/(app)/accounts" "$MONO/apps/web/src/components/accounts" "$MONO/apps/web/src/hooks" "$MONO/apps/web/src/lib"
cat > "$MONO/package.json" <<'JSON'
{ "name": "mono-root", "private": true, "workspaces": ["apps/*"] }
JSON
cat > "$MONO/apps/web/tsconfig.json" <<'JSON'
{ "compilerOptions": { "baseUrl": ".", "paths": { "@/*": ["./src/*"] } } }
JSON
cat > "$MONO/apps/web/src/lib/api-hooks.ts" <<'TS'
import { useQuery } from '@tanstack/react-query'
type GetResponse<P> = { data: P }
export function useApiQuery<Path, Data>(key: unknown[], fn: () => Promise<Data>) {
  return useQuery<GetResponse<Path>, Error, Data, unknown[]>({ queryKey: key, queryFn: fn })
}
TS
cat > "$MONO/apps/web/src/hooks/use-accounts.ts" <<'TS'
import axios from 'axios'
import { useApiQuery } from '@/lib/api-hooks'
export const listAccounts = async () => axios.get('/v1/accounts')
export function useAccounts() { return useApiQuery(['accounts'], listAccounts) }
TS
cat > "$MONO/apps/web/src/components/accounts/accounts-route.tsx" <<'TSX'
import { useAccounts } from '@/hooks/use-accounts'
export function AccountsRoute() { const { data } = useAccounts(); return <div>{String(data)}</div> }
TSX
cat > "$MONO/apps/web/src/app/(app)/accounts/page.tsx" <<'TSX'
'use client'
import { AccountsRoute } from '@/components/accounts/accounts-route'
export default function Page() { return <AccountsRoute /> }
TSX

cat >> "$TMP/src/api/hooks.ts" <<'TS'
// Hierarchical children of ['contacts'] -- idiomatic TanStack, NOT duplicates:
// invalidating the parent covers them.
export function useContactOrders(id: string) {
  return useQuery({ queryKey: ['contacts', id, 'orders'], queryFn: () => fetch('/api/contacts/' + id + '/orders') })
}
export function useContactFavorites(id: string) {
  return useQuery({ queryKey: ['contacts', id, 'order-favorites'], queryFn: () => fetch('/api/contacts/' + id + '/favorites') })
}
TS
node "$SKILL/bin/inventory.mjs" "$TMP" --stdout > "$INV"
echo "--- key hierarchy vs duplicate source"
node -e '
const j = require(process.argv[1]);
const hits = j.duplicateSources.map((d) => d.endpoint).join(",");
if (j.duplicateSources.length === 0) console.log("  ok    hierarchical keys not flagged as duplicate sources");
else { console.log("  FALSE-POSITIVE  key hierarchy flagged: " + hits); process.exit(1); }
' "$INV" || fail=1

echo "--- monorepo traversal"
node "$SKILL/bin/inventory.mjs" "$MONO" --stdout > "$MONO/inv.json" || { echo "  FAIL: crashed"; fail=1; }
node -e '
const j = require(process.argv[1]); let bad = 0;
const check = (l, ok, got) => { console.log((ok ? "  ok    " : "  MISS  ") + l + "  (" + got + ")"); if (!ok) bad = 1; };
const r = j.routes.find((x) => x.path === "/accounts");
check("route found under apps/web",  !!r,                 j.routes.map((x) => x.path).join(",") || "none");
check("import walk left the page",   (r?.modules ?? 0) > 1, r?.modules ?? 0);
check("query found 3 hops out",      (r?.queries.length ?? 0) >= 1, r?.queries.length ?? 0);
check("generic wrapper matched",     r?.queries.some((q) => q.via === "useApiQuery"), (r?.queries ?? []).map((q) => q.via ?? "bare").join(","));
check("entity resolved",             r?.entities.includes("accounts"), (r?.entities ?? []).join(",") || "none");
check("endpoint resolved",           r?.queries.some((q) => q.endpoint === "/v1/accounts"), (r?.queries ?? []).map((q) => q.endpoint).join(","));
process.exit(bad);
' "$MONO/inv.json" || fail=1

echo
if [ "$fail" -eq 0 ]; then echo "STATIC SELFTEST PASS"; else echo "STATIC SELFTEST FAIL"; fi
exit "$fail"
