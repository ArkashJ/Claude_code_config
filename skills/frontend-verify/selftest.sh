#!/usr/bin/env bash
# Proves the probes actually fire. Serves references/fixture.html, which carries
# one planted instance of each class, and asserts every one is found. Then runs
# the journey engine and the --mutate staleness engine against a two-variant SPA
# (one caches stale, one refetches) and asserts the engine tells them apart.
#
#   bash ~/.claude/skills/frontend-verify/selftest.sh
#
# A probe nobody has watched fail is not a gate. Run this after any edit to
# probe.js or sweep.mjs -- a rule that silently stops matching keeps reporting
# green while measuring nothing.
set -uo pipefail

SKILL="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${PORT:-8749}"
PORT2="${PORT2:-8751}"
PORT3="${PORT3:-8752}"
TMP="$(mktemp -d)"
trap 'kill "${SRV:-0}" "${SRV2:-0}" "${SRV3:-0}" 2>/dev/null; rm -rf "$TMP"' EXIT

cp "$SKILL/references/fixture.html" "$TMP/index.html"
echo '[{"id":1},{"id":2},{"id":3}]' > "$TMP/items.json"
echo '/* preloaded but never consumed */' > "$TMP/preload-unused.css"
python3 -m http.server "$PORT" --directory "$TMP" >/dev/null 2>&1 &
SRV=$!

# Wait for the port instead of sleeping blind.
for _ in $(seq 1 40); do
  curl -fsS "http://127.0.0.1:$PORT/" >/dev/null 2>&1 && break
  perl -e 'select undef,undef,undef,0.25'
done

# PLAYWRIGHT_HOME lets the selftest borrow an install from any repo, since the
# skill itself carries no node_modules by design.
# --settle 4000: Chrome emits the unused-preload warning "a few seconds" after
# load; the default settle would close the page before it arrives.
node "$SKILL/bin/sweep.mjs" --repo "${PLAYWRIGHT_HOME:-$PWD}" --base "http://127.0.0.1:$PORT" \
  --routes / --settle 4000 --json "$TMP/report.json" >"$TMP/out.txt" 2>&1
echo "--- sweep output"; cat "$TMP/out.txt"

if grep -q "Playwright not found" "$TMP/out.txt"; then
  echo
  echo "SELFTEST SKIPPED -- Playwright is not installed anywhere this script can reach."
  echo "The static half (inventory.mjs, classify.mjs) needs nothing and is covered by"
  echo "selftest-static.sh. To cover the runtime half, install it in any repo and rerun"
  echo "from there:"
  echo "    npm i -D @playwright/test && npx playwright install chromium"
  exit 2
fi
if [ ! -s "$TMP/report.json" ]; then
  echo "FAIL: sweep produced no report -- see the output above"; exit 1
fi

fail=0
have() {
  if grep -q "\"kind\": \"$1\"" "$TMP/report.json"; then
    echo "  ok    $1"
  else
    echo "  MISS  $1  <- planted in the fixture, probe did not fire"; fail=1
  fi
}
have_exact() {
  if grep -q "$1" "$TMP/report.json"; then echo "  ok    exact: $1"
  else echo "  MISS  expected exactly: $1"; fail=1; fi
}
absent() {
  if grep -q "$1" "$TMP/report.json"; then
    echo "  FALSE-POSITIVE  $1"; fail=1
  else
    echo "  ok    no false positive: $1"
  fi
}

echo "--- planted defects"
have value.leak
have render.stuck-loading
have render.empty-list-no-state
have layout.h-scroll
have a11y.tap-target
have a11y.unlabeled-control
have network.http-404
have data.rendered-zero-of-n
have network.waterfall
have interact.click-occluded
have perf.unused-preload

echo "--- planted console/page errors, each in its own class"
have console.error
have console.pageerror
have delivery.chunk-load
have render.hydration-mismatch
have security.csp-violation
have render.resize-observer-loop
# Exactly ONE plain console.error: the four classified texts must not ALSO land
# there, and the browser's own "Failed to load resource" line for the planted
# 404 must not surface as a second finding for one root failure.
ncerr=$(grep -c '"kind": "console.error"' "$TMP/report.json")
if [ "$ncerr" = "1" ]; then echo "  ok    console.error reported exactly once (classified texts + 404 log line excluded)"
else echo "  FAIL  console.error reported $ncerr times, expected 1"; fail=1; fi

echo "--- perf gates (require pre-navigation observers; zero here means unmeasured)"
have perf.long-task
have perf.layout-shift
have perf.layout-thrash

echo "--- must NOT fire"
# The sr-only skip link is 1x1 BY DESIGN. Counting it is how an accessibility
# ticket claims 103 failures and a browser finds one.
# Exactly ONE small target (.tiny). If the sr-only skip link were counted it
# would be 2 -- which is how an accessibility ticket claims 103 failures.
have_exact '1 interactive element(s) under 24px'
absent '2 interactive element(s) under 24px'
# Exactly TWO nameless controls (bare button + bare input). Three or more means
# the label-wrapped / aria-labeled / placeholder inputs were miscounted.
have_exact '2 control(s) with no accessible name'
absent '3 control(s) with no accessible name'
# Exactly ONE occluded control: the pointer-events:none overlay must pass through.
have_exact '1 interactive element(s) whose center is covered'
absent '2 interactive element(s) whose center is covered'

# The 404 must be reported ONCE. Twice means the in-page recorder and Playwright's
# network layer are both firing without deduping -- which on a real app would
# double every network finding.
n404=$(grep -c '"kind": "network.http-404"' "$TMP/report.json")
if [ "$n404" = "1" ]; then echo "  ok    404 reported exactly once (in-page + network deduped)"
else echo "  FAIL  404 reported $n404 times, expected 1"; fail=1; fi

# value.leak must report all four leaked shapes, not just the first.
for s in NaN undefined "object Object" "Invalid Date"; do
  grep -q "$s" "$TMP/report.json" && echo "  ok    leak reported: $s" || { echo "  MISS  leak not reported: $s"; fail=1; }
done

# ---------------------------------------------------------------------------
# DIFFERENTIAL CHECK. Two deliberately different pages must produce DIFFERENT
# findings. Byte-identical output across distinct inputs is the signature of an
# experiment that never ran -- a sweep that intercepts at the wrong layer, or
# that captures before render, reports the same clean result for every input and
# looks like a pass. Only a differential assertion catches that.
mkdir -p "$TMP/clean"
cat > "$TMP/clean/index.html" <<'HTML'
<!doctype html><meta charset="utf-8"><title>clean</title>
<main><h1>Clean</h1><p>Everything is fine here.</p>
<ul><li>one</li><li>two</li></ul>
<button style="width:44px;height:44px" aria-label="ok">OK</button></main>
HTML
node "$SKILL/bin/sweep.mjs" --repo "${PLAYWRIGHT_HOME:-$PWD}" --base "http://127.0.0.1:$PORT" \
  --routes /clean/ --json "$TMP/clean.json" >/dev/null 2>&1

mkdir -p "$TMP/ghost"
cat > "$TMP/ghost/index.html" <<'HTML'
<!doctype html><meta charset="utf-8"><title>ghost</title>
<main><h1>404 - Page not found</h1><p>No such record.</p></main>
HTML
node "$SKILL/bin/sweep.mjs" --repo "${PLAYWRIGHT_HOME:-$PWD}" --base "http://127.0.0.1:$PORT" \
  --routes /ghost/ --json "$TMP/ghost.json" >/dev/null 2>&1
echo "--- not-found shell"
if grep -q '"kind": "route.not-found-shell"' "$TMP/ghost.json"; then
  echo "  ok    not-found surface reported as its own finding"
else echo "  MISS  a not-found page was measured as if it were the route"; fail=1; fi

echo "--- differential (distinct inputs must give distinct output)"
node -e '
const a = require(process.argv[1]), b = require(process.argv[2]);
const kinds = (r) => [...new Set(r.routes.flatMap((x) => x.findings.map((f) => f.kind)))].sort().join(",");
const ka = kinds(a), kb = kinds(b);
if (ka === kb) { console.log("  FAIL  identical findings for the buggy and clean pages -- the sweep measured nothing"); process.exit(1); }
if (!ka.includes("value.leak")) { console.log("  FAIL  buggy page lost its findings"); process.exit(1); }
if (kb.includes("value.leak")) { console.log("  FAIL  clean page reported a leak: " + kb); process.exit(1); }
console.log("  ok    buggy: " + (ka.split(",").length) + " kinds, clean: " + (kb ? kb.split(",").length : 0) + " kinds, and they differ");
' "$TMP/report.json" "$TMP/clean.json" || fail=1

# ---------------------------------------------------------------------------
# STALENESS ENGINE. A two-view SPA with a real POST endpoint, in two variants:
# STALE renders the list from a cache it never refreshes after a write; FIXED
# refetches on navigation. The --mutate engine (driven by a syncRisk from the
# inventory) must flag the first and stay silent on the second -- a staleness
# detector that fires on both, or on neither, is measuring nothing.

cat > "$TMP/spa-server.mjs" <<'JS'
import http from 'node:http';
import fs from 'node:fs';
const [, , port, htmlPath] = process.argv;
const items = [{ id: 1, name: 'alpha' }];
const html = fs.readFileSync(htmlPath, 'utf8');
http.createServer((req, res) => {
  if (req.url.startsWith('/api/items')) {
    if (req.method === 'POST') {
      let b = '';
      req.on('data', (c) => (b += c));
      req.on('end', () => {
        try { items.push(JSON.parse(b)); } catch { items.push({ name: 'x' }); }
        res.writeHead(201, { 'content-type': 'application/json' }); res.end('{}');
      });
      return;
    }
    res.writeHead(200, { 'content-type': 'application/json' }); res.end(JSON.stringify(items));
    return;
  }
  // PLANTED: legacy_session is SameSite=None with no Secure (browsers reject
  // it); good_session is correctly SameSite=None; Secure and must NOT be flagged.
  res.writeHead(200, {
    'content-type': 'text/html',
    'set-cookie': ['legacy_session=abc; Path=/; SameSite=None', 'good_session=def; Path=/; SameSite=None; Secure'],
  });
  res.end(html);
}).listen(Number(port));
JS

spa_html() {  # $1 = onNav body: "render()" (stale) or "load().then(render)" (fixed)
cat <<HTML
<!doctype html><meta charset="utf-8"><title>spa</title>
<style>a{display:inline-block;min-width:44px;min-height:24px} button{width:44px;height:44px} input{width:200px;height:32px}</style>
<main id="root"></main>
<script>
let cache = null;
async function load() { cache = await (await fetch('/api/items')).json(); }
function render() {
  const root = document.getElementById('root');
  if (location.pathname === '/list') {
    root.innerHTML = '<h1>Items</h1><ul>' + cache.map(i => '<li>' + i.name + '</li>').join('') + '</ul><a href="/">back</a>';
  } else {
    root.innerHTML = '<h1>Add</h1><form id="f"><input name="name" aria-label="name"><button type="submit">Add</button></form> <a href="/list">list</a>';
    document.getElementById('f').onsubmit = async (e) => {
      e.preventDefault();
      await fetch('/api/items', { method: 'POST', headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ name: new FormData(e.target).get('name') }) });
    };
  }
}
document.addEventListener('click', (e) => {
  const a = e.target.closest('a'); if (!a) return;
  e.preventDefault(); history.pushState({}, '', a.getAttribute('href'));
  $1;
});
load().then(render);
</script>
HTML
}

spa_html "render()" > "$TMP/spa-stale.html"
spa_html "load().then(render)" > "$TMP/spa-fixed.html"

# The repo the engine is pointed at: a fabricated inventory carrying one P1
# syncRisk (the shape inventory.mjs emits), plus a journeys file to prove the
# journey harness runs and probes.
mkdir -p "$TMP/repo/.verify"
cat > "$TMP/repo/.verify/inventory.json" <<'JSON'
{ "counts": { "routes": 2 },
  "routes": [{ "path": "/" }, { "path": "/list" }],
  "syncRisks": [{ "severity": "P1", "kind": "no-invalidation", "route": "/", "hook": "useAddItem",
                  "endpoint": "/api/items", "entity": "items", "staleRoutes": ["/list"] }] }
JSON
cat > "$TMP/repo/verify.journeys.mjs" <<'JS'
export default [
  { name: 'view-list', start: '/', run: async (page) => { await page.click('a[href="/list"]'); } },
];
JS

node "$TMP/spa-server.mjs" "$PORT2" "$TMP/spa-stale.html" & SRV2=$!
node "$TMP/spa-server.mjs" "$PORT3" "$TMP/spa-fixed.html" & SRV3=$!
for _ in $(seq 1 40); do
  curl -fsS "http://127.0.0.1:$PORT2/" >/dev/null 2>&1 && curl -fsS "http://127.0.0.1:$PORT3/" >/dev/null 2>&1 && break
  perl -e 'select undef,undef,undef,0.25'
done

node "$SKILL/bin/sweep.mjs" --repo "$TMP/repo" --base "http://127.0.0.1:$PORT2" \
  --routes / --mutate --json "$TMP/stale.json" >"$TMP/stale-out.txt" 2>&1
node "$SKILL/bin/sweep.mjs" --repo "$TMP/repo" --base "http://127.0.0.1:$PORT3" \
  --routes / --mutate --json "$TMP/fixed.json" >"$TMP/fixed-out.txt" 2>&1

echo "--- cookie rejection (hard browser rule, header-level check)"
if grep -q '"kind": "security.cookie-samesite-none-insecure"' "$TMP/stale.json" && grep -q 'legacy_session' "$TMP/stale.json"; then
  echo "  ok    SameSite=None without Secure flagged"
else echo "  MISS  insecure SameSite=None cookie not flagged"; fail=1; fi
if grep -q 'good_session' "$TMP/stale.json"; then
  echo "  FALSE-POSITIVE  SameSite=None; Secure cookie was flagged"; fail=1
else echo "  ok    correctly secured cookie not flagged"; fi

echo "--- journey engine"
if grep -q '(journey: view-list)' "$TMP/stale.json"; then echo "  ok    app-owned journey ran under the harness"
else echo "  MISS  journey did not run -- see $TMP/stale-out.txt"; cat "$TMP/stale-out.txt"; fail=1; fi
if grep -q '"kind": "journey.failed"' "$TMP/stale.json"; then
  echo "  FAIL  journey crashed"; grep -A2 'journey.failed' "$TMP/stale.json" | head -5; fail=1
else echo "  ok    journey completed without failure"; fi

echo "--- staleness engine (differential: stale flagged, fixed silent)"
if grep -q '"kind": "sync.stale-after-write"' "$TMP/stale.json"; then
  echo "  ok    stale variant: write + client-side nav with no refetch flagged P0"
else echo "  MISS  the stale SPA was not flagged -- the mutate engine measured nothing"; cat "$TMP/stale-out.txt" | tail -20; fail=1; fi
if grep -q '"kind": "sync.stale-after-write"' "$TMP/fixed.json"; then
  echo "  FALSE-POSITIVE  the fixed SPA (refetches on nav) was flagged stale"; fail=1
else echo "  ok    fixed variant: refetch on navigation, no finding"; fi

# ---------------------------------------------------------------------------
# AUTO-LOGIN. A gated server: every route redirects to /login until the real
# form is posted with the right credentials. The sweep, given --login-user/
# --login-pass, must log itself in, save the state, and actually measure the
# route -- and without credentials it must honestly report not-reached.
PORT4="${PORT4:-8753}"
cat > "$TMP/login-server.mjs" <<'JS'
import http from 'node:http';
const [, , port] = process.argv;
http.createServer((req, res) => {
  const authed = /session=ok/.test(req.headers.cookie || '');
  if (req.url === '/login' && req.method === 'POST') {
    let b = '';
    req.on('data', (c) => (b += c));
    req.on('end', () => {
      if (/user=qa%40example\.com/.test(b) && /pass=secret/.test(b)) {
        res.writeHead(302, { 'set-cookie': 'session=ok; Path=/', location: '/' }); res.end();
      } else { res.writeHead(302, { location: '/login' }); res.end(); }
    });
    return;
  }
  if (!authed && req.url !== '/login') { res.writeHead(302, { location: '/login' }); res.end(); return; }
  if (req.url === '/login') {
    res.writeHead(200, { 'content-type': 'text/html' });
    res.end('<main><h1>Login</h1><form method="post" action="/login"><input type="email" name="user" aria-label="email" style="width:200px;height:32px"><input type="password" name="pass" aria-label="password" style="width:200px;height:32px"><button type="submit" style="width:44px;height:44px">Go</button></form></main>');
    return;
  }
  res.writeHead(200, { 'content-type': 'text/html' });
  res.end('<main><h1>Secret dashboard</h1><p>Welcome back.</p><ul><li>row one</li></ul></main>');
}).listen(Number(port));
JS
node "$TMP/login-server.mjs" "$PORT4" & SRV4=$!
trap 'kill "${SRV:-0}" "${SRV2:-0}" "${SRV3:-0}" "${SRV4:-0}" 2>/dev/null; rm -rf "$TMP"' EXIT
for _ in $(seq 1 40); do curl -fsS "http://127.0.0.1:$PORT4/login" >/dev/null 2>&1 && break; perl -e 'select undef,undef,undef,0.25'; done

mkdir -p "$TMP/repo-auth/.verify"
echo "--- auto-login"
node "$SKILL/bin/sweep.mjs" --repo "$TMP/repo-auth" --base "http://127.0.0.1:$PORT4" \
  --routes / --json "$TMP/noauth.json" >/dev/null 2>&1
if grep -q '"kind": "route.not-reached"' "$TMP/noauth.json"; then
  echo "  ok    without credentials, the gated route honestly reports not-reached"
else echo "  MISS  gated route measured as reached without auth"; fail=1; fi

node "$SKILL/bin/sweep.mjs" --repo "$TMP/repo-auth" --base "http://127.0.0.1:$PORT4" \
  --routes / --login-user "qa@example.com" --login-pass "secret" \
  --json "$TMP/auth.json" >"$TMP/auth-out.txt" 2>&1
if [ -s "$TMP/repo-auth/.verify/auth.json" ]; then echo "  ok    storage state saved for future runs"
else echo "  MISS  auth state not saved"; fail=1; fi
if grep -q '"kind": "route.not-reached"' "$TMP/auth.json"; then
  echo "  MISS  auto-login did not unlock the gated route"; cat "$TMP/auth-out.txt" | tail -5; fail=1
else echo "  ok    auto-login unlocked and measured the gated route"; fi
if grep -q 'Secret' "$TMP/auth.json" || ! grep -q '"kind": "render.empty"' "$TMP/auth.json"; then
  echo "  ok    the real page behind the gate was rendered"
else echo "  MISS  gate page empty after login"; fail=1; fi

# ---------------------------------------------------------------------------
# PARALLEL smoke: three routes, three workers, one report -- records must land
# in inventory order with per-route findings intact.
echo "--- parallel sweep"
node "$SKILL/bin/sweep.mjs" --repo "${PLAYWRIGHT_HOME:-$PWD}" --base "http://127.0.0.1:$PORT" \
  --routes /,/clean/,/ghost/ --parallel 3 --json "$TMP/par.json" >/dev/null 2>&1
node -e '
const r = require(process.argv[1]);
const routes = r.routes.map((x) => x.route);
let bad = 0;
const check = (l, ok) => { console.log((ok ? "  ok    " : "  MISS  ") + l); if (!ok) bad = 1; };
check("3 routes swept in order", routes.join(",") === "/,/clean/,/ghost/");
check("buggy route kept its findings", r.routes[0].findings.some((f) => f.kind === "value.leak"));
check("clean route stayed clean of leaks", !r.routes[1].findings.some((f) => f.kind === "value.leak"));
process.exit(bad);
' "$TMP/par.json" || fail=1

echo
if [ "$fail" -eq 0 ]; then echo "SELFTEST PASS"; else echo "SELFTEST FAIL"; fi
exit "$fail"
