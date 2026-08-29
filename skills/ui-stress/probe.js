// ui-stress probe - deterministic UI violation detector.
//
// Invoke: see SKILL.md (the file is passed as a double-quoted shell argument).
//
// HARD CONSTRAINT: no backticks and no dollar signs anywhere in this file.
// It is passed through a double-quoted shell argument; the shell would eat
// them. Use string concatenation, never template literals. Keep it that way.

async page => {
  let axeOk = false;
  try {
    await page.addScriptTag({ url: 'https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.2/axe.min.js' });
    axeOk = true;
  } catch (e) { axeOk = false; }

  const out = await page.evaluate(async () => {
    const INTERACTIVE = 'a[href],button,input,select,textarea,summary,[role="button"],[role="link"],[role="tab"],[role="menuitem"],[tabindex]:not([tabindex="-1"])';
    const V = [];

    const vis = el => {
      if (!el || el.nodeType !== 1) return false;
      const s = getComputedStyle(el);
      if (s.display === 'none' || s.visibility === 'hidden' || Number(s.opacity) < 0.02) return false;
      const r = el.getBoundingClientRect();
      return r.width > 0 && r.height > 0;
    };

    const sel = el => {
      if (!el || el.nodeType !== 1) return '(page)';
      const t = el.getAttribute && el.getAttribute('data-testid');
      if (t) return '[data-testid="' + t + '"]';
      if (el.id) return '#' + el.id;
      let s = el.tagName.toLowerCase();
      const cls = (el.getAttribute('class') || '').trim().split(/\s+/)
        .filter(c => c && c.length < 30).slice(0, 2);
      if (cls.length) s += '.' + cls.join('.');
      const p = el.parentElement;
      if (p && p !== document.body && p !== document.documentElement) s = p.tagName.toLowerCase() + ' > ' + s;
      return s;
    };

    const label = el => {
      if (!el || !el.textContent) return '';
      const t = el.textContent.trim().replace(/\s+/g, ' ');
      return t.length > 48 ? t.slice(0, 48) + '...' : t;
    };

    const add = (rule, sev, el, detail) => {
      V.push({ rule: rule, sev: sev, sel: sel(el), text: label(el), detail: detail });
    };

    const interactives = () => Array.prototype.slice.call(document.querySelectorAll(INTERACTIVE));
    const all = () => Array.prototype.slice.call(document.querySelectorAll('body *'));

    // 1. Horizontal overflow - the single most common mobile bug.
    const de = document.documentElement;
    const vw = de.clientWidth;
    if (de.scrollWidth > vw + 1) {
      add('overflow-x', 'P0', null,
        'page scrolls sideways: ' + de.scrollWidth + 'px of content in a ' + vw + 'px viewport');
      const wide = all().filter(el => {
        if (!vis(el)) return false;
        const s = getComputedStyle(el);
        if (s.position === 'fixed') return false;
        return el.getBoundingClientRect().right > vw + 1;
      });
      // innermost culprits only - do not report every ancestor
      wide.filter(el => !wide.some(o => o !== el && el.contains(o)))
        .slice(0, 5)
        .forEach(el => add('overflow-x-culprit', 'P1', el,
          'extends ' + Math.round(el.getBoundingClientRect().right - vw) + 'px past the right edge'));
    }

    // 2. Text clipped by an overflow-hidden box with no ellipsis.
    all().forEach(el => {
      if (!vis(el)) return;
      const s = getComputedStyle(el);
      if (!/hidden|clip/.test(s.overflowY) && !/hidden|clip/.test(s.overflowX)) return;
      if (!el.textContent || !el.textContent.trim()) return;
      if (el.querySelector('img,svg,canvas,video')) return;
      const clamped = s.webkitLineClamp && s.webkitLineClamp !== 'none';
      const ellipsis = s.textOverflow === 'ellipsis';
      if (el.scrollHeight > el.clientHeight + 2 && !clamped) {
        add('text-clipped', 'P1', el,
          Math.round(el.scrollHeight - el.clientHeight) + 'px of text cut off vertically with no ellipsis');
      } else if (el.scrollWidth > el.clientWidth + 2 && !ellipsis) {
        add('text-clipped', 'P1', el, 'text cut off horizontally with no ellipsis');
      }
    });

    // 3. Interactive element covered by something else - clicks land elsewhere.
    interactives().forEach(el => {
      if (!vis(el)) return;
      const r = el.getBoundingClientRect();
      const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
      if (cx < 0 || cy < 0 || cx > innerWidth || cy > innerHeight) return;
      const top = document.elementFromPoint(cx, cy);
      if (!top || el.contains(top) || top.contains(el)) return;
      add('covered', 'P0', el, 'covered by ' + sel(top) + ' - clicks hit the wrong element');
    });

    // 4/5. Target size and zero-size focusables.
    interactives().forEach(el => {
      const r = el.getBoundingClientRect();
      const s = getComputedStyle(el);
      if (r.width < 1 && r.height < 1) {
        if (s.display !== 'none' && s.visibility !== 'hidden') {
          add('zero-size-interactive', 'P1', el, 'focusable but has no size - a keyboard trap with no target');
        }
        return;
      }
      if (!vis(el)) return;
      // WCAG 2.5.8 inline exception: links inside running text are exempt
      if (s.display.indexOf('inline') === 0 && el.closest('p,li,td,figcaption')) return;
      if (r.width < 24 || r.height < 24) {
        add('touch-target', 'P1', el,
          Math.round(r.width) + 'x' + Math.round(r.height) + 'px - under the 24px minimum');
      }
    });

    // 6/7. Accessible names. axe owns the general case; the placeholder-only
    // check always runs because axe accepts a placeholder AS an accessible name.
    {
      interactives().forEach(el => {
        if (!vis(el)) return;
        const aria = (el.getAttribute('aria-label') || '').trim();
        const by = (el.getAttribute('aria-labelledby') || '').split(/\s+/)
          .map(id => { const n = document.getElementById(id); return n ? n.textContent : ''; }).join(' ').trim();
        const own = (el.textContent || '').trim();
        const img = el.querySelector('img[alt]');
        const alt = img ? (img.getAttribute('alt') || '').trim() : '';
        const title = (el.getAttribute('title') || '').trim();
        const lab = el.labels && el.labels[0] ? el.labels[0].textContent.trim() : '';
        if (aria || by || own || alt || title || lab) return;
        const ph = (el.getAttribute('placeholder') || '').trim();
        if (ph) add('placeholder-only-label', 'P1', el, 'labelled only by its placeholder - the label vanishes as soon as the user types');
        else if (!window.axe) add('no-accessible-name', 'P0', el, 'no name for screen readers or voice control');
      });
    }

    // 8. Broken and unlabelled images.
    Array.prototype.slice.call(document.images).forEach(img => {
      if (img.complete && img.naturalWidth === 0) {
        add('broken-image', 'P1', img, 'src failed to load: ' + (img.currentSrc || img.src || '(empty)'));
      }
      if (!img.hasAttribute('alt')) add('missing-alt', 'P2', img, 'no alt attribute');
    });

    // 9. Containers that render empty with no message - the missing empty state.
    Array.prototype.slice.call(document.querySelectorAll('main,[role="main"],ul,ol,tbody,[role="list"],[role="grid"],[role="table"]'))
      .forEach(el => {
        // deliberately NOT vis(): an empty container collapses to 0px high,
        // which is the very symptom being detected.
        if (el.offsetParent === null && getComputedStyle(el).position !== 'fixed') return;
        if (el.children.length === 0 && !(el.textContent || '').trim()) {
          add('empty-no-message', 'P1', el, 'renders empty with no message and no next action');
        }
      });

    // 10. Dead end - nothing to read and nothing to do.
    const main = document.querySelector('main,[role="main"]') || document.body;
    const words = (main.innerText || '').trim().split(/\s+/).filter(Boolean).length;
    const acts = Array.prototype.slice.call(main.querySelectorAll(INTERACTIVE)).filter(vis).length;
    if (words < 5 && acts === 0) {
      add('dead-end', 'P0', main, 'nothing rendered: no text, no action - the user is stuck here');
    }

    // 11. Focus indicator - sampled, and honest that it needs confirming.
    const prev = document.activeElement;
    const shot = el => { const s = getComputedStyle(el); return [s.outlineStyle, s.outlineWidth, s.outlineColor, s.boxShadow, s.borderColor, s.backgroundColor, s.color].join('|'); };
    interactives().filter(vis).slice(0, 15).forEach(el => {
      try {
        const before = shot(el);
        el.focus({ preventScroll: true });
        if (document.activeElement !== el) return;
        if (shot(el) === before) {
          add('no-focus-indicator', 'P1', el, 'nothing changes visually on focus - confirm with a real Tab press');
        }
      } catch (e) {}
    });
    try { if (prev && prev.focus) prev.focus({ preventScroll: true }); } catch (e) {}

    // 12. Off-token colour drift, against custom properties declared on :root.
    const rootStyle = getComputedStyle(de);
    const tokens = new Set();
    for (let i = 0; i < rootStyle.length; i++) {
      const p = rootStyle[i];
      if (p.indexOf('--') !== 0) continue;
      const v = rootStyle.getPropertyValue(p).trim().toLowerCase();
      if (v) tokens.add(v.replace(/\s/g, ''));
    }
    if (tokens.size > 3) {
      const probe = document.createElement('span');
      document.body.appendChild(probe);
      const resolved = new Set();
      tokens.forEach(v => {
        probe.style.color = '';
        probe.style.color = v;
        const c = getComputedStyle(probe).color.replace(/\s/g, '');
        if (c) resolved.add(c);
      });
      probe.remove();
      const stray = new Map();
      all().forEach(el => {
        if (!vis(el)) return;
        const s = getComputedStyle(el);
        ['color', 'backgroundColor', 'borderTopColor'].forEach(p => {
          const c = String(s[p]).replace(/\s/g, '').toLowerCase();
          if (!c || c === 'rgba(0,0,0,0)' || c === 'transparent') return;
          if (resolved.has(c)) return;
          stray.set(c, (stray.get(c) || 0) + 1);
        });
      });
      Array.from(stray)
        .sort((a, b) => b[1] - a[1]).slice(0, 8)
        .forEach(pair => add('off-token-color', 'P2', null, pair[0] + ' used ' + pair[1] + 'x - not in the token palette'));
    }

    // 13. axe-core, if it loaded.
    let axeCount = 0;
    if (window.axe) {
      try {
        const r = await window.axe.run(document, { resultTypes: ['violations'] });
        const map = { critical: 'P0', serious: 'P1', moderate: 'P2', minor: 'P3' };
        r.violations.forEach(v => {
          axeCount++;
          const nodes = v.nodes.slice(0, 3).map(n => n.target.join(' '));
          V.push({
            rule: 'axe:' + v.id, sev: map[v.impact] || 'P2',
            sel: nodes[0] || '(page)', text: '',
            detail: v.help + ' (' + v.nodes.length + ' node' + (v.nodes.length === 1 ? '' : 's') + ')'
          });
        });
      } catch (e) {}
    }

    // Collapse: one row per rule, up to 3 examples. Volume must not drown signal.
    const groups = new Map();
    V.forEach(v => {
      const g = groups.get(v.rule) || { rule: v.rule, sev: v.sev, count: 0, examples: [] };
      g.count++;
      if (g.examples.length < 3) g.examples.push({ sel: v.sel, text: v.text, detail: v.detail });
      if (['P0', 'P1', 'P2', 'P3'].indexOf(v.sev) < ['P0', 'P1', 'P2', 'P3'].indexOf(g.sev)) g.sev = v.sev;
      groups.set(v.rule, g);
    });
    const order = { P0: 0, P1: 1, P2: 2, P3: 3 };
    const findings = Array.from(groups.values())
      .sort((a, b) => (order[a.sev] - order[b.sev]) || (b.count - a.count));

    return {
      url: location.pathname + location.search,
      viewport: innerWidth + 'x' + innerHeight,
      dark: matchMedia('(prefers-color-scheme: dark)').matches ||
            /dark/i.test(de.getAttribute('data-theme') || de.className || ''),
      axe: !!window.axe,
      axeViolations: axeCount,
      total: V.length,
      findings: findings
    };
  });

  return JSON.stringify(out);
}
