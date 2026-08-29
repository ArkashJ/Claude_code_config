// frontend-verify in-page probe. Deterministic runtime invariants.
//
// Returns { findings: [{kind, severity, detail, at}], metrics: {...} }.
//
// HARD CONSTRAINT: no backticks, no dollar signs anywhere in this file. It is
// passed through a double-quoted shell argument by playwright-cli; the shell
// eats both. Use string concatenation. (Same rule as ui-stress/probe.js.)
//
// Everything here is decidable without vision. Screenshots are for the residual.

async page => {
  const out = await page.evaluate(async () => {
    const V = [];
    const add = (kind, severity, detail, at) => V.push({ kind, severity, detail, at: at || '(page)' });

    const sel = el => {
      if (!el || el.nodeType !== 1) return '(page)';
      const t = el.getAttribute && el.getAttribute('data-testid');
      if (t) return '[data-testid=' + t + ']';
      if (el.id) return '#' + el.id;
      const c = (el.className && String(el.className).split(/\s+/)[0]) || '';
      return el.tagName.toLowerCase() + (c ? '.' + c : '');
    };
    const vis = el => {
      if (!el || el.nodeType !== 1) return false;
      const s = getComputedStyle(el);
      if (s.display === 'none' || s.visibility === 'hidden' || Number(s.opacity) < 0.02) return false;
      const r = el.getBoundingClientRect();
      return r.width > 0 && r.height > 0;
    };
    // Screen-reader-only elements are 1x1 by design. Measuring them as tap
    // targets is how a ticket claims 103 failures and a browser finds one.
    const srOnly = el => {
      const s = getComputedStyle(el);
      const r = el.getBoundingClientRect();
      return (r.width <= 2 && r.height <= 2) || s.clip === 'rect(0px, 0px, 0px, 0px)' || s.clipPath === 'inset(50%)';
    };

    /* -- L5: values that leaked through formatting ------------------------ */

    const LEAKS = [
      [/\[object Object\]/, '[object Object] rendered as text'],
      [/\bNaN\b/, 'NaN rendered as text'],
      [/\bundefined\b/, 'undefined rendered as text'],
      [/\bInvalid Date\b/, 'Invalid Date rendered as text'],
      [/\bnull\b/, 'the string "null" rendered as text'],
      [/\bTypeError\b|\bReferenceError\b|is not a function|Cannot read propert/, 'raw JS error text in the DOM'],
      [/\{\{[\w.]+\}\}|\$\{[\w.]+\}/, 'unresolved template variable in the DOM'],
    ];
    const bodyText = (document.body && document.body.innerText) || '';
    for (const pair of LEAKS) {
      const hit = bodyText.match(pair[0]);
      if (!hit) continue;
      const at = Math.max(0, (hit.index || 0) - 50);
      add('value.leak', 'P1', pair[1] + ' -- ...' + bodyText.slice(at, at + 140).replace(/\s+/g, ' ') + '...');
    }

    /* -- L4: states that were never built --------------------------------- */

    const root = document.querySelector('#root,#__next,[data-reactroot],main') || document.body;
    if (!root || (root.innerText || '').trim().length < 2)
      add('render.empty', 'P0', 'page root rendered with no text content');

    // A spinner still mounted after the settle loop is a query that never
    // resolved -- the other half of "the data did not load".
    const spinners = [...document.querySelectorAll('[aria-busy="true"],[role="progressbar"],.spinner,.loading,.skeleton,[class*="skeleton" i],[class*="animate-pulse"]')].filter(vis);
    if (spinners.length)
      add('render.stuck-loading', 'P1', spinners.length + ' loading indicator(s) still visible after settle', sel(spinners[0]));

    // An empty list with no empty state is indistinguishable from a failed fetch.
    const lists = [...document.querySelectorAll('ul,ol,tbody,[role="list"],[role="table"],[role="grid"]')].filter(vis);
    for (const l of lists) {
      const rows = [...l.children].filter(vis);
      if (rows.length) continue;
      const near = ((l.parentElement && l.parentElement.innerText) || '').toLowerCase();
      if (!/no |empty|none |nothing|0 result|get started|add your first/.test(near))
        add('render.empty-list-no-state', 'P1', 'list rendered with zero rows and no empty-state message', sel(l));
    }

    /* -- L8: layout under the real viewport ------------------------------- */

    if (document.documentElement.scrollWidth > window.innerWidth + 1) {
      const wide = [...document.querySelectorAll('body *')].filter(el => {
        const r = el.getBoundingClientRect();
        return r.width > 0 && (r.right > window.innerWidth + 1 || r.left < -1) && vis(el);
      });
      add('layout.h-scroll', 'P1',
        'page scrolls horizontally at ' + window.innerWidth + 'px (content ' + document.documentElement.scrollWidth + 'px)',
        wide.length ? sel(wide[0]) : '(page)');
    }

    const INTERACTIVE = 'a[href],button,input,select,textarea,summary,[role="button"],[role="link"],[role="tab"],[role="menuitem"]';
    const small = [...document.querySelectorAll(INTERACTIVE)].filter(el => {
      if (!vis(el) || srOnly(el)) return false;
      const r = el.getBoundingClientRect();
      return Math.min(r.width, r.height) < 24;
    });
    if (small.length)
      add('a11y.tap-target', 'P2', small.length + ' interactive element(s) under 24px (sr-only excluded)', sel(small[0]));

    const unlabeled = [...document.querySelectorAll('button,[role="button"],a[href]')].filter(el =>
      vis(el) && !(el.innerText || '').trim() && !el.getAttribute('aria-label')
      && !el.getAttribute('aria-labelledby') && !el.getAttribute('title'));
    if (unlabeled.length)
      add('a11y.unlabeled-control', 'P2', unlabeled.length + ' control(s) with no accessible name', sel(unlabeled[0]));

    /* -- L10: what the main thread actually did --------------------------- */

    const metrics = { longTasks: 0, longestTaskMs: 0, cls: 0, lcpMs: null, forcedReflows: 0, resources: 0, transferKB: 0 };

    const readBuffered = (type, fn) => {
      try { performance.getEntriesByType(type).forEach(fn); } catch (e) { /* unsupported */ }
    };
    readBuffered('longtask', e => { metrics.longTasks++; metrics.longestTaskMs = Math.max(metrics.longestTaskMs, Math.round(e.duration)); });
    readBuffered('layout-shift', e => { if (!e.hadRecentInput) metrics.cls += e.value; });
    readBuffered('largest-contentful-paint', e => { metrics.lcpMs = Math.round(e.startTime); });
    readBuffered('resource', e => { metrics.resources++; metrics.transferKB += (e.transferSize || 0) / 1024; });
    metrics.cls = Math.round(metrics.cls * 1000) / 1000;
    metrics.transferKB = Math.round(metrics.transferKB);

    // Thresholds are the published Core Web Vitals "needs improvement" line, so
    // a finding here means something a real user feels, not a preference.
    if (metrics.longestTaskMs > 200)
      add('perf.long-task', 'P2', 'longest main-thread task ' + metrics.longestTaskMs + 'ms (' + metrics.longTasks + ' over 50ms) -- input is blocked for that whole window');
    if (metrics.cls > 0.1)
      add('perf.layout-shift', 'P2', 'cumulative layout shift ' + metrics.cls + ' (over the 0.1 threshold) -- content moves under the cursor');
    if (metrics.lcpMs !== null && metrics.lcpMs > 2500)
      add('perf.lcp', 'P2', 'largest contentful paint at ' + metrics.lcpMs + 'ms (over 2500ms)');

    // Forced synchronous layout: a geometry read after a style write, in the
    // same frame, makes the browser lay out again. In a loop it is the classic
    // layout-thrash stall. Counted by patching the read for one frame.
    metrics.forcedReflows = await new Promise(resolve => {
      let reads = 0, wrote = false;
      const proto = Element.prototype;
      const realRect = proto.getBoundingClientRect;
      const realStyle = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'style');
      proto.getBoundingClientRect = function () { if (wrote) { reads++; wrote = false; } return realRect.apply(this, arguments); };
      const obs = new MutationObserver(() => { wrote = true; });
      try { obs.observe(document.body, { attributes: true, childList: true, subtree: true }); } catch (e) { /* detached */ }
      requestAnimationFrame(() => requestAnimationFrame(() => {
        proto.getBoundingClientRect = realRect;
        if (realStyle) { /* left untouched: we never replaced it */ }
        obs.disconnect();
        resolve(reads);
      }));
    });
    if (metrics.forcedReflows > 20)
      add('perf.layout-thrash', 'P2', metrics.forcedReflows + ' geometry reads interleaved with DOM writes in one frame -- forced synchronous layout');

    /* -- L4: hydration and boundaries ------------------------------------- */

    // React marks a hydration-mismatched root; the visible symptom is content
    // that renders then silently swaps or disappears.
    if (document.querySelector('[data-nextjs-error],[data-nextjs-dialog]'))
      add('render.dev-overlay', 'P0', 'a framework error overlay is present on the page');

    return { findings: V, metrics };
  });
  return out;
}
