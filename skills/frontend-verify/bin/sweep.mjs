#!/usr/bin/env node
// Runtime sweep. Drives every route in the inventory and applies the universal
// invariants. Exits non-zero on P0/P1 -- that exit code is the definition of done.
//
//   node sweep.mjs --repo <repoRoot> --base http://localhost:3000
//                  [--routes /,/dashboard] [--width 1280] [--auth state.json]
//                  [--leak-check] [--json <path>]
//
// --repo anchors everything: the inventory is read from <repo>/.verify/inventory.json
// and the report is written to <repo>/.verify/sweep.json. Nothing resolves against
// the current working directory, because this skill runs against many repos and a
// cwd-relative path drops one repo's report into another's directory.
//
// Playwright is resolved from the TARGET repo, not from here: the skill carries
// no node_modules and must not pin a version against the repo under test.

import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';

const argv = process.argv.slice(2);
const arg = (n, d) => { const i = argv.indexOf('--' + n); return i >= 0 ? argv[i + 1] : d; };
const flag = (n) => argv.includes('--' + n);

const BASE = (arg('base') ?? 'http://localhost:3000').replace(/\/$/, '');
const WIDTH = Number(arg('width', '1280'));
const HEIGHT = Number(arg('height', '900'));
const SETTLE_MS = Number(arg('settle', '1200'));
const REPO = path.resolve(arg('repo', '.'));
const INVENTORY = arg('inventory', path.join(REPO, '.verify', 'inventory.json'));
const AUTH = arg('auth');
const JSON_OUT = arg('json', path.join(REPO, '.verify', 'sweep.json'));
const PROBE = path.join(path.dirname(new URL(import.meta.url).pathname), 'probe.js');

/* ------------------------------------------------------------- playwright */

// Both packages are CJS, so the browser launchers arrive under `.default`
// depending on the interop path. Unwrap before use -- reading `.chromium` off the
// raw namespace gives `undefined` and fails at launch() with nothing to explain it.
const unwrap = (mod) => (mod?.chromium ? mod : mod?.default?.chromium ? mod.default : null);

// Where a self-installed Playwright lives. Shared on purpose: the browser binary
// is already a global cache, so only the npm package needs a home, and putting
// that home in the skill keeps every repo's package.json and lockfile untouched.
// --install=repo opts into a real devDependency for repos that want one checked in.
const SHARED = path.join(path.dirname(path.dirname(new URL(import.meta.url).pathname)), '.playwright');

async function tryLoad(root) {
  for (const pkg of ['playwright', '@playwright/test']) {
    try {
      const req = createRequire(path.join(root, 'package.json'));
      const got = unwrap(await import(pathToFileURL(req.resolve(pkg)).href));
      if (got) return got;
    } catch { /* next package */ }
  }
  return null;
}

function run(cmd, args, cwd) {
  const r = spawnSync(cmd, args, { cwd, stdio: 'inherit', encoding: 'utf8' });
  return r.status === 0;
}

function installInto(dir) {
  fs.mkdirSync(dir, { recursive: true });
  if (!fs.existsSync(path.join(dir, 'package.json')))
    fs.writeFileSync(path.join(dir, 'package.json'), JSON.stringify({ name: 'frontend-verify-runtime', private: true }, null, 2) + '\n');
  console.error('\n  installing @playwright/test into ' + dir + ' (one time)\n');
  if (!run('npm', ['install', '--no-audit', '--no-fund', '--save-dev', '@playwright/test'], dir)) return false;
  // The browser binary lands in a shared OS cache, so this is a no-op after the
  // first ever install on the machine, whichever repo triggered it.
  console.error('\n  ensuring the chromium binary is present (shared cache)\n');
  run('npx', ['--yes', 'playwright', 'install', 'chromium'], dir);
  return true;
}

async function loadPlaywright() {
  const repo = path.resolve(arg('repo', '.'));
  const roots = [repo, SHARED, process.cwd(), ...(process.env.PLAYWRIGHT_HOME ? [path.resolve(process.env.PLAYWRIGHT_HOME)] : [])];
  for (const root of roots) { const got = await tryLoad(root); if (got) return got; }
  try { const got = unwrap(await import('playwright')); if (got) return got; } catch { /* fall through */ }

  if (flag('no-install')) {
    console.error('Playwright not found and --no-install was passed.\n  npm i -D @playwright/test && npx playwright install chromium');
    process.exit(2);
  }
  const target = arg('install') === 'repo' ? repo : SHARED;
  if (!installInto(target)) {
    console.error('Automatic install failed. Install manually:\n  npm i -D @playwright/test && npx playwright install chromium');
    process.exit(2);
  }
  const got = await tryLoad(target);
  if (got) return got;
  console.error('Installed Playwright but could not load it from ' + target);
  process.exit(2);
}

/* ----------------------------------------------------------------- routes */

function routesToSweep() {
  const explicit = arg('routes');
  if (explicit) return explicit.split(',').map((s) => s.trim()).filter(Boolean);
  if (fs.existsSync(INVENTORY)) {
    const inv = JSON.parse(fs.readFileSync(INVENTORY, 'utf8'));
    // Dynamic segments need a real id; without one the route 404s and the sweep
    // reports a false failure. Skip them here and cover them in the journeys,
    // which have a seeded record to address.
    return inv.routes.map((r) => r.path).filter((p) => !/[:[]/.test(p));
  }
  return ['/'];
}

/* ------------------------------------------------------------------ sweep */

const playwright = await loadPlaywright();
const routes = routesToSweep();
const probeSrc = fs.readFileSync(PROBE, 'utf8').replace(/^\s*\/\/[^\n]*\n/gm, '').trim();
const probeFn = eval('(' + probeSrc + ')');

const browser = await playwright.chromium.launch();
const context = await browser.newContext({
  viewport: { width: WIDTH, height: HEIGHT },
  ...(AUTH && fs.existsSync(AUTH) ? { storageState: AUTH } : {}),
});

// Playwright's network events only see traffic that reaches the browser's network
// stack. A service worker (MSW and every mock-first setup) answers fetches INSIDE
// the page, so page.on('response') fires zero times and every network invariant
// silently passes -- the tool reports clean on an app it never measured. Patching
// window.fetch and XHR before app JS runs is the only vantage point that sees both
// real and intercepted traffic.
await context.addInitScript(() => {
  const log = [];
  Object.defineProperty(window, '__fv_net', { get: () => log, configurable: true });
  const realFetch = window.fetch;
  window.fetch = async function (...args) {
    const url = String(args[0]?.url ?? args[0] ?? '');
    const method = (args[1]?.method ?? args[0]?.method ?? 'GET').toUpperCase();
    const start = performance.now();
    try {
      const res = await realFetch.apply(this, args);
      log.push({ url, method, status: res.status, ok: res.ok, start, end: performance.now(), via: 'fetch' });
      return res;
    } catch (e) {
      log.push({ url, method, status: 0, ok: false, error: String(e), start, end: performance.now(), via: 'fetch' });
      throw e;
    }
  };
  const RealXHR = window.XMLHttpRequest;
  if (RealXHR) {
    const open = RealXHR.prototype.open, send = RealXHR.prototype.send;
    RealXHR.prototype.open = function (m, u, ...rest) { this.__fv = { url: String(u), method: String(m).toUpperCase() }; return open.call(this, m, u, ...rest); };
    RealXHR.prototype.send = function (...a) {
      const meta = this.__fv;
      if (meta) {
        meta.start = performance.now();
        this.addEventListener('loadend', () => log.push({ ...meta, status: this.status, ok: this.status >= 200 && this.status < 400, end: performance.now(), via: 'xhr' }));
      }
      return send.apply(this, a);
    };
  }
});

const report = { base: BASE, width: WIDTH, started: new Date().toISOString(), routes: [], summary: {} };
const sevOf = (f) => f.severity ?? 'P2';

// Destinations already probed. An unauthenticated sweep of a gated app redirects
// every route to /login, and probing each one attributes the login page's contents
// to 50 routes it never reached -- 45 copies of one finding, reading as app-wide.
// Worse, it reports coverage of routes nobody saw. Measure each destination once.
const measured = new Set();

for (const route of routes) {
  const page = await context.newPage();
  const findings = [];
  const requests = [];
  // Keyed method+path+status, so the same failure seen at BOTH the network layer
  // and in-page is reported once. Without this every network finding doubles on
  // any app where both vantage points can see the traffic.
  const reported = new Set();
  const netKey = (method, pathname, status) => method + ' ' + pathname + ' ' + status;
  const push = (kind, severity, detail, at) => findings.push({ kind, severity, detail, at: at ?? '(page)' });

  page.on('console', (m) => {
    if (m.type() !== 'error') return;
    const t = m.text();
    // ResizeObserver's loop warning is a real signal (an observer callback that
    // writes layout, re-triggering itself) and belongs in its own class.
    if (/ResizeObserver loop/.test(t)) return push('render.resize-observer-loop', 'P2', t.slice(0, 200));
    if (/ChunkLoadError|Loading chunk \d+ failed/.test(t)) return push('delivery.chunk-load', 'P0', t.slice(0, 200));
    if (/Hydration failed|did not match|Text content does not match|#418|#423|#425/.test(t))
      return push('render.hydration-mismatch', 'P0', t.slice(0, 250));
    if (/Content Security Policy|Refused to (load|execute|connect)/.test(t))
      return push('security.csp-violation', 'P1', t.slice(0, 200));
    push('console.error', 'P1', t.slice(0, 250));
  });
  page.on('pageerror', (e) => push('console.pageerror', 'P0', String(e).slice(0, 250)));
  page.on('requestfailed', (r) => {
    const u = new URL(r.url());
    const same = u.origin === new URL(BASE).origin;
    push(same ? 'network.requestfailed' : 'network.requestfailed.external', same ? 'P1' : 'P3',
      r.method() + ' ' + u.pathname + ' -- ' + (r.failure()?.errorText ?? 'unknown'));
  });
  page.on('request', (r) => requests.push({ url: r.url(), type: r.resourceType(), start: Date.now(), end: null }));
  page.on('response', async (res) => {
    const rec = requests.find((x) => x.url === res.url() && x.end === null);
    if (rec) rec.end = Date.now();
    const u = new URL(res.url());
    if (u.origin !== new URL(BASE).origin) return;
    if (res.status() >= 400) {
      reported.add(netKey(res.request().method(), u.pathname, res.status()));
      push('network.http-' + res.status(), res.status() >= 500 ? 'P0' : 'P1', res.request().method() + ' ' + u.pathname + ' -> ' + res.status());
    }
  });

  let probe = { findings: [], metrics: {} };
  let redirectedTo = null;
  try {
    const resp = await page.goto(BASE + route, { waitUntil: 'domcontentloaded', timeout: 30000 });
    if (resp && resp.status() >= 400) push('route.status-' + resp.status(), 'P0', 'route returned HTTP ' + resp.status());
    // Readiness is NOT networkidle: long polling, websockets and background
    // refetches keep the network busy forever, and a capture taken before the
    // client renders measures nothing at all.
    await page.waitForLoadState('load', { timeout: 15000 }).catch(() => {});
    await page.waitForFunction(
      () => { const r = document.querySelector('#root,#__next,[data-reactroot],main') || document.body; return r && (r.innerText || '').trim().length > 1; },
      { timeout: 8000 },
    ).catch(() => {});
    await page.waitForTimeout(SETTLE_MS);

    // Where did we actually land?
    let landedPath = route;
    try { landedPath = new URL(page.url()).pathname.replace(/\/$/, '') || '/'; } catch { /* keep */ }
    const wanted = route.replace(/\/$/, '') || '/';
    if (landedPath !== wanted) {
      push('route.not-reached', 'P1', 'requested ' + wanted + ' but landed on ' + landedPath
        + (/\b(login|signin|sign-in|auth)\b/.test(landedPath) ? ' -- the sweep is unauthenticated; pass --auth <storageState.json> to cover this route' : ''));
      redirectedTo = landedPath;
    }
    // A not-found shell is not the route's surface either. A sweep that
    // substitutes a synthetic :id which exists in no fixture measures the
    // not-found page under every detail route's name -- same family as a
    // redirect, and just as good at manufacturing a confident wrong number.
    if (!redirectedTo) {
      const notFound = await page.evaluate(() => {
        const t = ((document.body && document.body.innerText) || '').slice(0, 600).toLowerCase();
        return /\b(404|not found|page not found|does(n't| not) exist|no such|couldn't find|could not find)\b/.test(t);
      }).catch(() => false);
      if (notFound) {
        push('route.not-found-shell', 'P1', 'route rendered a not-found surface -- if this path has a dynamic segment, the sweep used an id that exists in no fixture, so nothing below measures the real route');
        redirectedTo = landedPath + ' (not-found)';
      }
    }

    // Probe a destination once. Everything found on /login belongs to /login.
    if (!measured.has(landedPath)) {
      measured.add(landedPath);
      probe = await probeFn(page);
    } else {
      probe = { findings: [], metrics: {}, skipped: 'destination already measured: ' + landedPath };
    }
  } catch (e) {
    push('route.unreachable', 'P0', String(e).split('\n')[0].slice(0, 200));
  }

  // Merge what the page itself saw. On a service-worker app this is the ONLY
  // source with anything in it; on a normal app it agrees with Playwright and
  // the dedupe below keeps findings from doubling.
  let inPage = [];
  try { inPage = await page.evaluate(() => (window.__fv_net ?? []).map((r) => ({ ...r }))); } catch { /* page closed */ }
  const seen = new Set(requests.map((r) => r.url));
  for (const r of inPage) {
    let abs = r.url, pathname = r.url;
    try { const u = new URL(r.url, BASE); abs = u.href; pathname = u.pathname; } catch { /* keep raw */ }
    const key = netKey(r.method, pathname, r.status);
    if (!reported.has(key)) {
      if (r.status >= 400) {
        reported.add(key);
        push('network.http-' + r.status, r.status >= 500 ? 'P0' : 'P1', r.method + ' ' + pathname + ' -> ' + r.status + ' (seen in-page)');
      } else if (!r.ok && r.status === 0) {
        reported.add(key);
        push('network.requestfailed', 'P1', r.method + ' ' + pathname + ' -- ' + (r.error ?? 'failed') + ' (seen in-page)');
      }
    }
    if (!seen.has(abs)) requests.push({ url: abs, type: 'fetch', start: r.start, end: r.end, inPageOnly: true });
  }
  if (!requests.some((r) => r.type === 'xhr' || r.type === 'fetch') && inPage.length === 0)
    push('verify.no-data-traffic', 'P2', 'no data requests observed at either the network layer or in-page -- either this route needs none, or the sweep is measuring nothing');

  // Request waterfall: B starting right after A finished, repeatedly, is a
  // dependent chain. Every link is a full round trip added to time-to-data, and
  // the page is partially populated at every step of it.
  const api = requests.filter((r) => (r.type === 'xhr' || r.type === 'fetch') && r.end);
  api.sort((a, b) => a.start - b.start);
  let chain = 1, worst = 1;
  for (let i = 1; i < api.length; i++) {
    if (api[i].start >= api[i - 1].end - 5 && api[i].start - api[i - 1].end < 400) { chain++; worst = Math.max(worst, chain); }
    else chain = 1;
  }
  if (worst >= 3) push('network.waterfall', 'P2', worst + ' data requests fired in a dependent chain -- each one is a round trip before the page is complete');

  report.routes.push({
    route, redirectedTo, findings: [...findings, ...(probe.findings ?? [])], metrics: probe.metrics ?? {},
    apiRequests: api.length, ...(probe.skipped ? { skipped: probe.skipped } : {}),
  });
  await page.close();
}

/* ----------------------------------------------------- leak check (opt-in) */

if (flag('leak-check') && routes.length >= 2) {
  const page = await context.newPage();
  const cdp = await context.newCDPSession(page);
  const heap = async () => {
    await cdp.send('HeapProfiler.collectGarbage');
    const { usedSize } = await cdp.send('Runtime.getHeapUsage');
    return usedSize;
  };
  await page.goto(BASE + routes[0], { waitUntil: 'load' }).catch(() => {});
  const before = await heap();
  for (let i = 0; i < 5; i++) {
    for (const r of routes.slice(0, 4)) await page.goto(BASE + r, { waitUntil: 'load' }).catch(() => {});
  }
  await page.goto(BASE + routes[0], { waitUntil: 'load' }).catch(() => {});
  const after = await heap();
  const growthMB = Math.round(((after - before) / 1048576) * 10) / 10;
  report.leak = { beforeMB: Math.round(before / 1048576), afterMB: Math.round(after / 1048576), growthMB };
  // Heap that does not come back after GC across repeated navigation is retained
  // by something the unmount did not release: a listener, a timer, a subscription.
  if (growthMB > 8) {
    report.routes.push({
      route: '(navigation loop)', metrics: {},
      findings: [{ kind: 'perf.memory-leak', severity: 'P1', at: '(page)',
        detail: growthMB + 'MB retained after GC across 20 navigations -- detached nodes or un-removed listeners' }],
    });
  }
  await page.close();
}

await browser.close();

/* ---------------------------------------------------------------- report */

const all = report.routes.flatMap((r) => r.findings.map((f) => ({ ...f, route: r.route })));
const bySev = all.reduce((a, f) => ((a[sevOf(f)] = (a[sevOf(f)] ?? 0) + 1), a), {});
const byKind = all.reduce((a, f) => ((a[f.kind] = (a[f.kind] ?? 0) + 1), a), {});
report.summary = { routes: report.routes.length, findings: all.length, ...bySev };
report.finished = new Date().toISOString();

fs.mkdirSync(path.dirname(JSON_OUT), { recursive: true });
fs.writeFileSync(JSON_OUT, JSON.stringify(report, null, 2));

const reached = report.routes.filter((r) => !r.redirectedTo).length;
report.summary.routesRequested = report.routes.length;
report.summary.routesReached = reached;
console.log('\n  ' + BASE + '  ' + report.routes.length + ' routes at ' + WIDTH + 'px');
if (reached < report.routes.length)
  console.log('  REACHED ' + reached + '/' + report.routes.length + ' -- the rest redirected (auth?); they were NOT measured');
console.log('  ' + all.length + ' findings  ' + Object.entries(bySev).map(([k, v]) => k + ':' + v).join('  ') + '\n');
for (const [kind, n] of Object.entries(byKind).sort((a, b) => b[1] - a[1])) {
  const first = all.find((f) => f.kind === kind);
  console.log('  ' + String(n).padStart(4) + '  ' + sevOf(first) + '  ' + kind);
  for (const f of all.filter((x) => x.kind === kind).slice(0, 3))
    console.log('        ' + f.route + '  ' + f.detail.slice(0, 130));
  if (n > 3) console.log('        ... and ' + (n - 3) + ' more');
}
console.log('  -> ' + JSON_OUT);
if (report.leak) console.log('\n  heap after GC across navigation: ' + report.leak.beforeMB + 'MB -> ' + report.leak.afterMB + 'MB (+' + report.leak.growthMB + 'MB)');
console.log('');

process.exit((bySev.P0 ?? 0) + (bySev.P1 ?? 0) > 0 ? 1 : 0);
