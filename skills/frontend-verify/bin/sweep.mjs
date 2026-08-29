#!/usr/bin/env node
// Runtime sweep. Drives every route in the inventory and applies the universal
// invariants. Exits non-zero on P0/P1 -- that exit code is the definition of done.
//
//   node sweep.mjs --base http://localhost:3000 [--inventory .verify/inventory.json]
//                  [--routes /,/dashboard] [--width 1280] [--auth state.json]
//                  [--leak-check] [--json report.json]
//
// Playwright is resolved from the TARGET repo, not from here: the skill carries
// no node_modules and must not pin a version against the repo under test.

import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';

const argv = process.argv.slice(2);
const arg = (n, d) => { const i = argv.indexOf('--' + n); return i >= 0 ? argv[i + 1] : d; };
const flag = (n) => argv.includes('--' + n);

const BASE = (arg('base') ?? 'http://localhost:3000').replace(/\/$/, '');
const WIDTH = Number(arg('width', '1280'));
const HEIGHT = Number(arg('height', '900'));
const SETTLE_MS = Number(arg('settle', '1200'));
const INVENTORY = arg('inventory', '.verify/inventory.json');
const AUTH = arg('auth');
const JSON_OUT = arg('json');
const PROBE = path.join(path.dirname(new URL(import.meta.url).pathname), 'probe.js');

/* ------------------------------------------------------------- playwright */

async function loadPlaywright() {
  for (const from of [process.cwd(), path.resolve(arg('repo', '.'))]) {
    try {
      const req = createRequire(path.join(from, 'package.json'));
      return await import(pathToFileURL(req.resolve('playwright')).href);
    } catch { /* try the next root */ }
    try {
      const req = createRequire(path.join(from, 'package.json'));
      return await import(pathToFileURL(req.resolve('@playwright/test')).href);
    } catch { /* try the next root */ }
  }
  try { return await import('playwright'); } catch { /* fall through */ }
  console.error('Playwright not found. Install it in the repo under test:\n  npm i -D @playwright/test && npx playwright install chromium');
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

const report = { base: BASE, width: WIDTH, started: new Date().toISOString(), routes: [], summary: {} };
const sevOf = (f) => f.severity ?? 'P2';

for (const route of routes) {
  const page = await context.newPage();
  const findings = [];
  const requests = [];
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
    if (res.status() >= 400)
      push('network.http-' + res.status(), res.status() >= 500 ? 'P0' : 'P1', res.request().method() + ' ' + u.pathname + ' -> ' + res.status());
  });

  let probe = { findings: [], metrics: {} };
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
    probe = await probeFn(page);
  } catch (e) {
    push('route.unreachable', 'P0', String(e).split('\n')[0].slice(0, 200));
  }

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
    route, findings: [...findings, ...(probe.findings ?? [])], metrics: probe.metrics ?? {},
    apiRequests: api.length,
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

if (JSON_OUT) fs.writeFileSync(JSON_OUT, JSON.stringify(report, null, 2));

console.log('\n  ' + BASE + '  ' + report.routes.length + ' routes at ' + WIDTH + 'px');
console.log('  ' + all.length + ' findings  ' + Object.entries(bySev).map(([k, v]) => k + ':' + v).join('  ') + '\n');
for (const [kind, n] of Object.entries(byKind).sort((a, b) => b[1] - a[1])) {
  const first = all.find((f) => f.kind === kind);
  console.log('  ' + String(n).padStart(4) + '  ' + sevOf(first) + '  ' + kind);
  for (const f of all.filter((x) => x.kind === kind).slice(0, 3))
    console.log('        ' + f.route + '  ' + f.detail.slice(0, 130));
  if (n > 3) console.log('        ... and ' + (n - 3) + ' more');
}
if (report.leak) console.log('\n  heap after GC across navigation: ' + report.leak.beforeMB + 'MB -> ' + report.leak.afterMB + 'MB (+' + report.leak.growthMB + 'MB)');
console.log('');

process.exit((bySev.P0 ?? 0) + (bySev.P1 ?? 0) > 0 ? 1 : 0);
